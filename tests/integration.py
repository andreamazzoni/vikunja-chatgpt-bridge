#!/usr/bin/env python3
"""Exercise the pinned official image against HTTPS fixtures, never real services.

Requires Docker access and openssl. The test override uses host networking only
to reach ephemeral 127.0.0.1 fixtures. Production Compose publishes no ports.
"""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

from test_checks import certificate, https_server

ROOT = Path(__file__).resolve().parents[1]
IMAGE = json.loads((ROOT / "versions.lock.json").read_text())["tunnel_client"]["image"]


def main():
    commands, responses = queue.Queue(), queue.Queue()
    cp_requests, mcp_requests = [], []
    poll_queries = []
    local_auth, plane_key = "Bearer fixture-vikunja-" + uuid.uuid4().hex, "fixture-openai-" + uuid.uuid4().hex
    expected_auth = [local_auth]
    tunnel = "tunnel_" + "0" * 32

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, data=None):
            payload = json.dumps(data).encode() if data is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    class Plane(Handler):
        def do_GET(self):
            cp_requests.append(dict(self.headers))
            if self.headers.get("Authorization") != "Bearer " + plane_key:
                self.send(401)
            elif "/poll" in self.path:
                poll_queries.append(parse_qs(urlsplit(self.path).query))
                try:
                    item = commands.get(timeout=0.25)
                    self.send(200, {"commands": [item]})
                except queue.Empty:
                    self.send(204)
            else:
                self.send(200, {"id": tunnel, "name": "fixture", "organization_ids": [], "workspace_ids": []})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            cp_requests.append({"headers": dict(self.headers), "body": body})
            responses.put(body)
            self.send(200, {})

    class MCP(Handler):
        def do_GET(self):
            mcp_requests.append({"headers": dict(self.headers), "method": "GET"})
            if self.path.startswith("/.well-known/"):
                # Real Vikunja's frontend fallback serves HTML 200 here, not 404.
                body = b"<!DOCTYPE html><html><body>Fixture frontend</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send(404)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if not raw:
                # Upstream also sends an empty WWW-Authenticate discovery probe.
                mcp_requests.append({"headers": dict(self.headers), "method": "probe"})
                self.send(400, {"error": "JSON-RPC body required"})
                return
            body = json.loads(raw)
            mcp_requests.append({"headers": dict(self.headers), "method": body.get("method")})
            if self.headers.get("Authorization") != expected_auth[0]:
                self.send(401, {"error": "authentication required"})
            elif body["method"] == "initialize":
                self.send(200, {"jsonrpc": "2.0", "id": body["id"], "result": {
                    "protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fixture-vikunja", "version": "2.7.1"}}})
            elif body["method"] == "tools/list":
                self.send(200, {"jsonrpc": "2.0", "id": body["id"], "result": {"tools": [{
                    "name": "fixture_read", "description": "Fixture only", "inputSchema": {"type": "object"},
                    "annotations": {"readOnlyHint": True}}]}})
            elif "id" in body:
                # Modern clients try server/discover before legacy initialize.
                self.send(200, {"jsonrpc": "2.0", "id": body["id"],
                                "error": {"code": -32601, "message": "Method not found"}})
            else:
                self.send(202)

    with tempfile.TemporaryDirectory(prefix="vikunja-bridge-fixture-") as directory:
        root = Path(directory)
        local = root / "config/local"
        secrets = root / "secrets"
        local.mkdir(parents=True)
        secrets.mkdir(mode=0o700)
        cert, key = certificate(root)
        shutil.copyfile(cert, local / "ca.pem")
        for name, value in [("openai_api_key", plane_key), ("vikunja_authorization", local_auth)]:
            path = secrets / name
            path.write_text(value + "\n")
            path.chmod(0o600)
        cp = https_server(Plane, cert, key)
        mcp = https_server(MCP, cert, key)
        # Mimic operator endpoints to ensure a historical poll does not stay healthy.
        from http.server import ThreadingHTTPServer
        poll_stamp = [int(time.time())]
        startup_probe = ["succeeded"]
        class Admin(Handler):
            def do_GET(self):
                if self.path == "/metrics":
                    payload = f"commands_poll_last_successful_timestamp_seconds {poll_stamp[0]}\n".encode()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                elif self.path == "/health/mcp":
                    self.send(200, {"details": {"startup_probe": {"state": startup_probe[0]}}})
                else:
                    self.send(200, {"status": "ok", "detail": "ready"})
        admin = ThreadingHTTPServer(("127.0.0.1", 0), Admin)
        threading.Thread(target=admin.serve_forever, daemon=True).start()
        # Reserve a free loopback health port; the client binds it after release.
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            health_port = sock.getsockname()[1]
        health_url = f"http://127.0.0.1:{health_port}"
        health = ["/bin/sh", "/opt/bridge/healthcheck.sh"]
        override = root / "fixture.json"
        override.write_text(json.dumps({"services": {"tunnel-client": {
            "network_mode": "host", "restart": "no",
            "environment": {"CONTROL_PLANE_BASE_URL": f"https://127.0.0.1:{cp.server_port}",
                            "HEALTH_LISTEN_ADDR": f"127.0.0.1:{health_port}"},
            "volumes": [{"type": "bind", "source": str(ROOT / "bridge/healthcheck.sh"),
                         "target": "/opt/bridge/healthcheck.sh", "read_only": True}],
            "healthcheck": {"test": ["CMD"] + health, "interval": "1s", "start_period": "1s"}
        }}}))
        envfile = root / ".env"
        values = {"BRIDGE_UID": str(os.getuid()), "BRIDGE_GID": str(os.getgid()),
                  "VIKUNJA_MCP_URL": f"https://127.0.0.1:{mcp.server_port}/api/v2/mcp",
                  "OPENAI_TUNNEL_ID": tunnel, "OPENAI_ORGANIZATION_ID": "",
                  "BRIDGE_CA_FILE": "/etc/vikunja-bridge/ca.pem"}
        envfile.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
        env = os.environ | values
        compose = ["docker", "compose", "--project-directory", str(root), "--env-file", str(envfile),
                   "-p", "vikunja-bridge-test-" + uuid.uuid4().hex[:10],
                   "-f", str(ROOT / "compose.yaml"), "-f", str(override)]

        def run(*args, ok=True):
            result = subprocess.run(compose + list(args), capture_output=True, text=True, env=env, timeout=90)
            if ok and result.returncode:
                # Docker output could contain secret-bearing upstream logs; do not echo it.
                raise AssertionError("Docker fixture command failed: " + args[0])
            return result

        def wait_ready():
            for _ in range(60):
                if run("exec", "-T", "tunnel-client", *health, ok=False).returncode == 0:
                    return
                time.sleep(0.3)
            logs = run("logs", "--no-color", ok=False).stdout
            logs = logs.replace(local_auth, "[redacted]").replace(plane_key, "[redacted]")
            Path("/tmp/vikunja-bridge-fixture-failure.log").write_text(logs)
            raise AssertionError("Fixture client did not become ready; sanitized diagnostics in /tmp/vikunja-bridge-fixture-failure.log")

        def dispatch(headers=None):
            request_id = "fixture-" + uuid.uuid4().hex
            commands.put({"request_id": request_id, "shard_token": "fixture-shard", "command_type": "jsonrpc",
                          "channel": "main", "response_timeout": "10s", "headers": headers or {},
                          "jsonrpc": {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}})
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                result = responses.get(timeout=20)
                if result.get("request_id") == request_id:
                    return result
            raise AssertionError("No fixture response")

        try:
            run("config", "--quiet")
            run("up", "-d")
            wait_ready()
            assert poll_queries and all(q.get("channel") == ["main"] for q in poll_queries)
            global_health = run("exec", "-T", "tunnel-client", "/usr/bin/tunnel-client", "health",
                                "--url", health_url, "--require-control-plane-poll", "--json", ok=False)
            report = json.loads(global_health.stdout)
            assert global_health.returncode != 0 and report["readyz"]["body"] == "oauth discovery pending"
            assert report["healthz"]["ok"] and report["control_plane_poll"]["ok"]
            print("PASS: main-only polling and deployment health work with HTML 200 OAuth discovery; global OAuth readiness stays pending", flush=True)
            version = run("exec", "-T", "tunnel-client", "/usr/bin/tunnel-client", "--version").stdout
            assert "0.0.19" in version, "Unexpected image version"
            result = dispatch()
            assert result["resp_code"] == 200, "Local Authorization injection failed"
            assert result["resp_json"]["result"]["tools"][0]["name"] == "fixture_read"
            assert any(x["method"] == "initialize" and x["headers"].get("Authorization") == local_auth for x in mcp_requests)
            print("PASS: official 0.0.19, file-backed MCP Bearer, initialize and forwarded tools/list over verified TLS", flush=True)
            # A connector-supplied header has priority over the static credential.
            forwarded = "Bearer fixture-forwarded"
            expected_auth[0] = forwarded
            assert dispatch({"authorization": [forwarded]})["resp_code"] == 200
            expected_auth[0] = local_auth
            assert dispatch({"Authorization": [forwarded]})["resp_code"] == 401
            assert dispatch()["resp_code"] == 200
            print("PASS: connector Authorization overrides static header; 401 is preserved; recovery succeeds", flush=True)
            assert local_auth not in json.dumps(cp_requests), "MCP credential reached mock control plane"
            assert plane_key not in json.dumps(mcp_requests), "Control-plane key reached mock MCP"
            logs = run("logs", "--no-color").stdout
            assert local_auth not in logs and plane_key not in logs, "Credential appeared in logs"
            print("PASS: credentials separated between hops and absent from client logs", flush=True)
            admin_env = f"HEALTH_LISTEN_ADDR=127.0.0.1:{admin.server_port}"
            poll_stamp[0] = int(time.time())
            assert run("exec", "-T", "-e", admin_env, "tunnel-client", *health, ok=False).returncode == 0
            startup_probe[0] = "failed"
            assert run("exec", "-T", "-e", admin_env, "tunnel-client", *health, ok=False).returncode != 0
            startup_probe[0] = "auth_required"
            assert run("exec", "-T", "-e", admin_env, "tunnel-client", *health, ok=False).returncode != 0
            startup_probe[0] = "succeeded"
            poll_stamp[0] = int(time.time()) - 180
            assert run("exec", "-T", "-e", admin_env, "tunnel-client", *health, ok=False).returncode != 0
            poll_stamp[0] = 0
            assert run("exec", "-T", "-e", admin_env, "tunnel-client", *health, ok=False).returncode != 0
            print("PASS: health accepts a recent poll and rejects stale or missing successful polls", flush=True)
            # Local probe also exercises the real checker, without any tool calls.
            sys.path.insert(0, str(ROOT / "scripts"))
            from check import probe
            probe(values, root)
            assert not any(x["method"] == "tools/call" for x in mcp_requests)
            run("restart")
            wait_ready()
            assert dispatch()["resp_code"] == 200
            run("down", "--timeout", "10")
            run("up", "-d")
            wait_ready()
            assert dispatch()["resp_code"] == 200
            print("PASS: restart and restore from unchanged local files", flush=True)
            # A fresh client must refuse the fixture certificate without its trusted CA.
            run("down", "--timeout", "10")
            env["BRIDGE_CA_FILE"] = "/etc/ssl/certs/ca-certificates.crt"
            before = len(mcp_requests)
            run("up", "-d")
            time.sleep(3)
            assert run("exec", "-T", "tunnel-client", *health, ok=False).returncode != 0
            assert len(mcp_requests) == before, "Untrusted TLS allowed authenticated HTTP"
            print("PASS: untrusted TLS rejected and health remains unsuccessful", flush=True)
        finally:
            run("down", "--timeout", "10", ok=False)
            cp.shutdown()
            mcp.shutdown()
            admin.shutdown()
            cp.server_close()
            mcp.server_close()
            admin.server_close()


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, subprocess.SubprocessError, queue.Empty, KeyError) as exc:
        print("FAIL: " + (str(exc) if isinstance(exc, AssertionError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
