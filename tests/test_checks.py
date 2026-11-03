"""Security and protocol checks, using only generated credentials and local TLS."""
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import ConfigError, read_secret, validate_tunnel, validate_url, write_private
from check import NoRedirect, rpc
import urllib.error
import urllib.request


def certificate(directory):
    cert, key = directory / "ca.pem", directory / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
                    "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
                    "-addext", "basicConstraints=critical,CA:TRUE"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return cert, key


def https_server(handler, cert, key):
    class QuietServer(ThreadingHTTPServer):
        def handle_error(self, request, address):
            if not isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
                super().handle_error(request, address)
    server = QuietServer(("127.0.0.1", 0), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class SecurityChecks(unittest.TestCase):
    def test_reject_insecure_or_ambiguous_urls(self):
        for url in ["http://example.org/api/v2/mcp", "https://user:pass@example.org/api/v2/mcp",
                    "https://example.org/api/v2/mcp?token=secret", "https://example.org/api/v2/mcp#x",
                    "https://example.org/mcp", "https://example.org:0/api/v2/mcp",
                    "https://example.org/api/v2/mcp\n", "https://example.org:99999/api/v2/mcp"]:
            with self.assertRaises(ConfigError):
                validate_url(url)

    def test_allow_https_port_ipv6_and_namespaced_tunnel(self):
        validate_url("https://[::1]:8443/api/v2/mcp")
        validate_tunnel("tunnel_ab12_" + "0" * 32)
        with self.assertRaises(ConfigError):
            validate_tunnel("tunnel_wrong")

    def test_private_file_and_complete_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            write_private(path, "Bearer fixture-only\n")
            self.assertTrue(read_secret(path, bearer=True).startswith("Bearer "))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o644)
            with self.assertRaises(ConfigError):
                read_secret(path, bearer=True)

    def test_reject_multiline_bare_token_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secret"
            for text in ["bare-token", "Bearer one\nInjected: value"]:
                write_private(path, text)
                with self.assertRaises(ConfigError):
                    read_secret(path, bearer=True)
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(ConfigError):
                read_secret(link)
            with self.assertRaises(ConfigError):
                write_private(link, "replacement")

    def test_probe_cannot_call_tools(self):
        with self.assertRaises(ConfigError):
            rpc(None, "unused", "fixture-only", "tools/call", 1)


class ProtocolChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.cert, cls.key = certificate(Path(cls.directory.name))
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/redirect":
                    self.send_response(307)
                    self.send_header("Location", "/target")
                    self.end_headers()
                    return
                result = {"jsonrpc": "2.0", "id": data["id"], "result": {"tools": []}}
                body = json.dumps(result).encode()
                self.send_response(200)
                if self.path == "/sse":
                    self.send_header("Content-Type", "text/event-stream")
                    body = b": heartbeat\n\ndata: " + body + b"\n\n"
                else:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "fixture-session")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        cls.server = https_server(Handler, cls.cert, cls.key)
        cls.base = f"https://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.directory.cleanup()

    def opener(self, trusted=True):
        ctx = ssl.create_default_context(cafile=str(self.cert)) if trusted else ssl.create_default_context()
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                          urllib.request.HTTPSHandler(context=ctx))

    def test_json_and_sse(self):
        for path in ["/json", "/sse"]:
            result, session = rpc(self.opener(), self.base + path, "Bearer fixture-only", "tools/list", 1)
            self.assertEqual(result, {"tools": []})
            self.assertEqual(session, "fixture-session")

    def test_no_credential_redirect(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            rpc(self.opener(), self.base + "/redirect", "Bearer fixture-only", "tools/list", 1)
        self.assertEqual(caught.exception.code, 307)

    def test_untrusted_tls_rejected(self):
        with self.assertRaises(urllib.error.URLError):
            rpc(self.opener(False), self.base + "/json", "Bearer fixture-only", "tools/list", 1)


if __name__ == "__main__":
    unittest.main()
