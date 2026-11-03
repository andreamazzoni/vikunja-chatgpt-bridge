# Development and testing

```sh
docker compose --env-file .env.example config --quiet
python3 -m unittest discover -s tests -p 'test_*.py' -v
docker compose --env-file .env.example pull
python3 tests/integration.py
```

The tests require Python and OpenSSL. Integration also requires Docker on
Linux. The fixture generates a temporary CA and test credentials, starts
loopback HTTPS servers, and runs the pinned client in a uniquely named
Compose project. The fixture uses host networking to reach loopback.
The normal deployment uses the Compose network.

The integration test checks file-backed headers, MCP initialization, and
`tools/list` through a simulated control plane. It covers header precedence,
HTTP 401, credential separation, TLS rejection, health, restart, and
recreation from local files. Tests use isolated credentials and remove the
temporary containers. Run one integration test at a time per host.

Review staged files before pushing. Use `git status --short` and
`git diff --cached` to check that local configuration and credentials are
excluded. Keep Forgejo as `origin` and use a separate `github` remote for
the GitHub copy.
