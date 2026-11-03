#!/usr/bin/env python3
"""Local read-only checks: never tools/call; print neither tokens nor response data."""
import argparse
import json
import os
import ssl
import sys
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from common import (ROOT, ConfigError, read_env, read_secret, tls_context,
                    validate_tunnel, validate_url)

LIMIT = 4 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never risk forwarding credentials to a redirect target.
        return None


def client(cfg, root=ROOT):
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                      urllib.request.HTTPSHandler(context=tls_context(cfg, root)))


def rpc(opener, url, authorization, method, request_id, params=None, session=None, protocol="2025-03-26"):
    if method not in {"initialize", "notifications/initialized", "tools/list"}:
        raise ConfigError("Il controllo non consente chiamate agli strumenti")
    data = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        data["id"] = request_id
    if params is not None:
        data["params"] = params
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "Authorization": authorization, "MCP-Protocol-Version": protocol}
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    with opener.open(req, timeout=20) as response:
        session = response.headers.get("Mcp-Session-Id", session)
        if request_id is None:
            return {}, session
        if response.headers.get_content_type() == "text/event-stream":
            # Stop when the matching JSON-RPC response arrives: the stream may stay open.
            size, event = 0, []
            while True:
                line = response.readline(LIMIT + 1)
                size += len(line)
                if size > LIMIT:
                    raise ConfigError("Risposta MCP oltre il limite locale")
                if not line or line in (b"\n", b"\r\n"):
                    if event:
                        message = json.loads(b"\n".join(event))
                        if message.get("id") == request_id:
                            break
                        event = []
                    if not line:
                        raise ConfigError("Stream MCP terminato senza risposta")
                elif line.startswith(b"data:"):
                    event.append(line[5:].strip())
        else:
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ConfigError("Risposta MCP oltre il limite locale")
            message = json.loads(raw)
    if (not isinstance(message, dict) or message.get("id") != request_id
            or "error" in message or not isinstance(message.get("result"), dict)):
        raise ConfigError("MCP ha restituito un errore o una risposta inattesa; contenuto omesso")
    return message["result"], session


def probe(cfg, root=ROOT):
    authorization = read_secret(root / "secrets/vikunja_authorization", bearer=True)
    opener = client(cfg, root)
    url = cfg["VIKUNJA_MCP_URL"]
    result, session = rpc(opener, url, authorization, "initialize", 1, {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "vikunja-bridge-readonly-check", "version": "0.1.0"}})
    protocol = result.get("protocolVersion", "2025-03-26")
    rpc(opener, url, authorization, "notifications/initialized", None, session=session, protocol=protocol)
    tools, cursor, seen = [], None, set()
    for page in range(50):
        result, session = rpc(opener, url, authorization, "tools/list", page + 2,
                              {"cursor": cursor} if cursor else {}, session, protocol)
        page_tools = result.get("tools")
        if not isinstance(page_tools, list) or not all(isinstance(t, dict) for t in page_tools):
            raise ConfigError("Catalogo MCP non valido; contenuto omesso")
        tools.extend(page_tools)
        cursor = result.get("nextCursor")
        if not cursor:
            break
        if cursor in seen:
            raise ConfigError("Paginazione MCP ripetuta")
        seen.add(cursor)
    else:
        raise ConfigError("Catalogo MCP oltre il limite di pagine")
    # Do not print server descriptions, task contents, arbitrary errors or schemas.
    names = [t.get("name", "") for t in tools]
    if not all(isinstance(n, str) and n and len(n) <= 128 and all(c.isalnum() or c in "_.-" for c in n) for n in names):
        raise ConfigError("Nome strumento non valido; contenuto omesso")
    print(json.dumps({"mcp_connection": "ok", "transport": "Streamable HTTP", "tool_count": len(names),
                      "tools": sorted(names), "tools_called": 0}, ensure_ascii=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["config", "tls", "mcp"])
    args = parser.parse_args()
    cfg = read_env()
    validate_url(cfg["VIKUNJA_MCP_URL"])
    validate_tunnel(cfg["OPENAI_TUNNEL_ID"])
    if cfg["BRIDGE_UID"] != str(os.getuid()) or cfg["BRIDGE_GID"] != str(os.getgid()):
        raise ConfigError("UID/GID devono corrispondere all'utente che esegue i controlli")
    read_secret(ROOT / "secrets/openai_api_key")
    read_secret(ROOT / "secrets/vikunja_authorization", bearer=True)
    tls_context(cfg)
    if args.command == "mcp":
        probe(cfg)
    elif args.command == "tls":
        url = urlsplit(cfg["VIKUNJA_MCP_URL"])
        # TLS-only preflight; no token is sent.
        import socket
        with socket.create_connection((url.hostname, url.port or 443), timeout=10) as sock:
            with tls_context(cfg).wrap_socket(sock, server_hostname=url.hostname):
                pass
        print("DNS, TCP e TLS verificati dall'host; nessun token inviato")
    else:
        print("URL, tunnel ID, UID/GID, CA e file segreti: OK (valori omessi)")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"Controllo fallito: HTTP {exc.code}; corpo e header omessi", file=sys.stderr)
        sys.exit(1)
    except (ConfigError, OSError, ValueError, KeyError, TypeError, ssl.SSLError, urllib.error.URLError) as exc:
        print(str(exc) if isinstance(exc, ConfigError) else "Controllo fallito: verificare configurazione, rete, TLS e autenticazione", file=sys.stderr)
        sys.exit(1)
