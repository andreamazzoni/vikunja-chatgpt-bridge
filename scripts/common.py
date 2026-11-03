"""Local configuration helpers. No dependencies, no secret-bearing diagnostics."""
import json
import os
from pathlib import Path
import re
import ssl
import stat
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class ConfigError(Exception):
    pass


def validate_url(value):
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        raise ConfigError("Invalid MCP URL") from None
    if (not value.isascii() or any(c.isspace() for c in value)
            or url.scheme != "https" or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment or "?" in value or "#" in value
            or url.path != "/api/v2/mcp" or (port is not None and port < 1)
            or not re.fullmatch(r"[A-Za-z0-9.:[\]-]+", url.netloc)):
        raise ConfigError("Use https://host[:port]/api/v2/mcp without credentials, query, or fragment")
    return value


def validate_tunnel(value):
    if not re.fullmatch(r"tunnel_(?:[a-z0-9]{4}_)?[a-z0-9]{32}", value):
        raise ConfigError("Invalid tunnel ID. Copy the full ID from the OpenAI portal")
    return value


def read_env(root=ROOT):
    result = {}
    for line in (root / ".env").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key] = json.loads(value) if value.startswith('"') else value
    return result


def private_dir(path):
    if path.is_symlink():
        raise ConfigError("A local configuration directory is a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def write_private(path, content):
    if path.is_symlink():
        raise ConfigError("A local configuration file is a symlink")
    fd, temporary = tempfile.mkstemp(prefix=".bridge-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_secret(path, bearer=False):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise ConfigError("Secret files must be regular files owned by the current user with mode 0600")
    value = path.read_text().removesuffix("\n").removesuffix("\r")
    check_secret(value[7:] if bearer and value.startswith("Bearer ") else value)
    if bearer and not value.startswith("Bearer "):
        raise ConfigError("The Authorization file must start with Bearer followed by a space")
    return value


def check_secret(value):
    if not value or not value.isascii() or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in value):
        raise ConfigError("Credential is empty or contains invalid characters")
    return value


def tls_context(cfg, root=ROOT):
    ca = cfg.get("BRIDGE_CA_FILE", "/etc/ssl/certs/ca-certificates.crt")
    if ca == "/etc/ssl/certs/ca-certificates.crt":
        return ssl.create_default_context()
    if ca != "/etc/vikunja-bridge/ca.pem":
        raise ConfigError("Unsupported CA path. Run setup.py")
    return ssl.create_default_context(cafile=str(root / "config/local/ca.pem"))
