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
        raise ConfigError("Eseguire come utente non root in un terminale interattivo privato")
    # Stop before touching a mounted file. Include exited containers retaining mounts.
    result = subprocess.run(["docker", "ps", "-aq", "--filter",
                             "label=com.docker.compose.project=vikunja-chatgpt-bridge"],
                            capture_output=True, text=True, check=True)
    if result.stdout.strip():
        raise ConfigError("Rimuovere prima i container di questo progetto con docker compose down; poi ripetere setup")
    cfg = read_env() if (ROOT / ".env").exists() else {}
    url = prompt("URL HTTPS MCP completo", cfg.get("VIKUNJA_MCP_URL", "https://vikunja.example.invalid/api/v2/mcp"))
    validate_url(url)
    tunnel = validate_tunnel(prompt("Nuovo ID tunnel dedicato a Vikunja", cfg.get("OPENAI_TUNNEL_ID", "")))
    org = prompt("Organization ID opzionale ( - per cancellare)", cfg.get("OPENAI_ORGANIZATION_ID", ""))
    org = "" if org == "-" else org
    if org and not re.fullmatch(r"org-[A-Za-z0-9_-]+", org):
        raise ConfigError("Organization ID non valido")
    local = ROOT / "config/local"
    private_dir(local)
    private_dir(ROOT / "secrets")
    previous_ca = cfg.get("BRIDGE_CA_FILE", "") == "/etc/vikunja-bridge/ca.pem"
    ca = prompt("CA PEM verificata: percorso, - per CA di sistema, invio per mantenere", "" )
    custom_ca = previous_ca and ca != "-"
    if ca and ca != "-":
        pem = Path(ca).expanduser().read_text()
        if "PRIVATE KEY" in pem:
            raise ConfigError("La CA deve contenere solo certificati pubblici")
        ssl.create_default_context(cadata=pem)
        write_private(local / "ca.pem", pem)
        custom_ca = True
    # getpass must not fall back to visible input.
    warnings.simplefilter("error", getpass.GetPassWarning)
    for name, label, prefix in [
        ("openai_api_key", "Chiave runtime OpenAI (non admin)", ""),
        ("vikunja_authorization", "Token MCP Vikunja, senza Bearer", "Bearer "),
    ]:
        path = ROOT / "secrets" / name
        suffix = " (invio mantiene quello esistente)" if path.exists() else ""
        value = getpass.getpass(label + suffix + ": ")
        if not value and path.exists():
            continue
        check_secret(value)
        if prefix and value.startswith("Bearer"):
            raise ConfigError("Inserire solo il token, senza prefisso Bearer")
        write_private(path, prefix + value + "\n")
    values = {
        "BRIDGE_UID": str(os.getuid()), "BRIDGE_GID": str(os.getgid()),
        "VIKUNJA_MCP_URL": url, "OPENAI_TUNNEL_ID": tunnel,
        "OPENAI_ORGANIZATION_ID": org,
        "BRIDGE_CA_FILE": "/etc/vikunja-bridge/ca.pem" if custom_ca else "/etc/ssl/certs/ca-certificates.crt",
    }
    if cfg.get("BRIDGE_IMAGE"):
        values["BRIDGE_IMAGE"] = cfg["BRIDGE_IMAGE"]
    write_private(ROOT / ".env", "# Configurazione locale, senza segreti\n" +
                  "".join(f"{key}={value}\n" for key, value in values.items()))
    print("Configurazione salvata (segreti 0600). Nessun servizio avviato.")
    print("Proseguire con: docker compose config --quiet; python3 scripts/check.py config")


if __name__ == "__main__":
    try:
        main()
    except (ConfigError, OSError, ValueError, ssl.SSLError, subprocess.CalledProcessError,
            getpass.GetPassWarning, EOFError, KeyboardInterrupt) as exc:
        print(str(exc) if isinstance(exc, ConfigError) else "Setup interrotto; controllare Docker, file e CA locali", file=sys.stderr)
        sys.exit(1)
