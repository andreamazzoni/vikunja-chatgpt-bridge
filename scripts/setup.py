#!/usr/bin/env python3
"""Prepare local configuration; never start a service or contact real data."""
import getpass
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import warnings

from common import (ROOT, ConfigError, check_secret, private_dir, read_env,
                    validate_tunnel, validate_url, write_private)


def prompt(label, previous=""):
    return input(label + (f" [{previous}]" if previous else "") + ": ").strip() or previous


def main():
    if not sys.stdin.isatty() or not sys.stderr.isatty() or os.getuid() == 0:
        raise ConfigError("Run as a non-root user in a private interactive terminal")
    # Stop before touching a mounted file. Include exited containers retaining mounts.
    result = subprocess.run(["docker", "ps", "-aq", "--filter",
                             "label=com.docker.compose.project=vikunja-chatgpt-bridge"],
                            capture_output=True, text=True, check=True)
    if result.stdout.strip():
        raise ConfigError("Remove the project containers with docker compose down, then rerun setup")
    cfg = read_env() if (ROOT / ".env").exists() else {}
    url = prompt("Complete HTTPS MCP URL", cfg.get("VIKUNJA_MCP_URL", "https://vikunja.example.invalid/api/v2/mcp"))
    validate_url(url)
    tunnel = validate_tunnel(prompt("Dedicated Vikunja tunnel ID", cfg.get("OPENAI_TUNNEL_ID", "")))
    org = prompt("Optional organization ID (enter - to clear)", cfg.get("OPENAI_ORGANIZATION_ID", ""))
    org = "" if org == "-" else org
    if org and not re.fullmatch(r"org-[A-Za-z0-9_-]+", org):
        raise ConfigError("Invalid organization ID")
    local = ROOT / "config/local"
    private_dir(local)
    private_dir(ROOT / "secrets")
    previous_ca = cfg.get("BRIDGE_CA_FILE", "") == "/etc/vikunja-bridge/ca.pem"
    ca = prompt("Verified CA PEM path (enter - for system CAs, Enter to keep current)", "" )
    custom_ca = previous_ca and ca != "-"
    if ca and ca != "-":
        pem = Path(ca).expanduser().read_text()
        if "PRIVATE KEY" in pem:
            raise ConfigError("The CA file must contain public certificates only")
        ssl.create_default_context(cadata=pem)
        write_private(local / "ca.pem", pem)
        custom_ca = True
    # getpass must not fall back to visible input.
    warnings.simplefilter("error", getpass.GetPassWarning)
    for name, label, prefix in [
        ("openai_api_key", "OpenAI runtime API key (non admin)", ""),
        ("vikunja_authorization", "Vikunja MCP token without the Bearer prefix", "Bearer "),
    ]:
        path = ROOT / "secrets" / name
        suffix = " (Enter keeps the existing value)" if path.exists() else ""
        value = getpass.getpass(label + suffix + ": ")
        if not value and path.exists():
            continue
        check_secret(value)
        if prefix and value.startswith("Bearer"):
            raise ConfigError("Enter the token without the Bearer prefix")
        write_private(path, prefix + value + "\n")
    values = {
        "BRIDGE_UID": str(os.getuid()), "BRIDGE_GID": str(os.getgid()),
        "VIKUNJA_MCP_URL": url, "OPENAI_TUNNEL_ID": tunnel,
        "OPENAI_ORGANIZATION_ID": org,
        "BRIDGE_CA_FILE": "/etc/vikunja-bridge/ca.pem" if custom_ca else "/etc/ssl/certs/ca-certificates.crt",
    }
    if cfg.get("BRIDGE_IMAGE"):
        values["BRIDGE_IMAGE"] = cfg["BRIDGE_IMAGE"]
    write_private(ROOT / ".env", "# Local configuration without credentials\n" +
                  "".join(f"{key}={value}\n" for key, value in values.items()))
    print("Configuration saved. Credential files use mode 0600.")
    print("Run python3 scripts/bridge.py validate to check the configuration")


if __name__ == "__main__":
    try:
        main()
    except (ConfigError, OSError, ValueError, ssl.SSLError, subprocess.CalledProcessError,
            getpass.GetPassWarning, EOFError, KeyboardInterrupt) as exc:
        print(str(exc) if isinstance(exc, ConfigError) else "Setup interrupted. Check Docker, local files, and CA settings", file=sys.stderr)
        sys.exit(1)
