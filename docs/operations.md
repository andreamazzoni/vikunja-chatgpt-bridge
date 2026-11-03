# Operations

Use `python3 scripts/bridge.py status` for container state and the last saved
probe. Run `python3 scripts/bridge.py probe` for a fresh MCP handshake and
catalog. Add `--json` to either command for structured output.

| Operation | Command |
| --- | --- |
| Stop | `python3 scripts/bridge.py stop` |
| Start after checking for other clients on the tunnel | `python3 scripts/bridge.py start --single-instance-confirmed` |
| Recreate and wait for health | `python3 scripts/bridge.py restart` |
| Inspect deployment health | `docker compose exec -T tunnel-client /bin/sh /opt/bridge/healthcheck.sh` |
| Check the running binary version | `docker compose exec -T tunnel-client /usr/bin/tunnel-client --version` |
| Run client diagnostics | `docker compose exec -T tunnel-client /usr/bin/tunnel-client doctor --control-plane.api-key=file:/run/secrets/openai_api_key --explain` |

`doctor` can contact the configured services and initialize MCP. The
ChatGPT call is a separate end-to-end test. Keep raw HTTP tracing disabled
and review diagnostics before sharing them. Docker retains three log files
of up to 10 MiB each.

## Update and rollback

The default pin is recorded in `compose.yaml` and `versions.lock.json`.
Check the ARM64 and AMD64 manifests and test the candidate before changing
the pin. [Official releases](https://github.com/openai/tunnel-client/releases)

Run `python3 scripts/bridge.py update --image PINNED_IMAGE` with the official
image reference including its version and digest. Omitting `--image` selects
the checkout pin. Update pulls the candidate, recreates the container, and
saves the image selection to `.env` after a successful health check. If
startup fails, it attempts to restore the running image.

`python3 scripts/bridge.py rollback` uses the previous image in
`.local/rollback.json`. Both commands require a running bridge. Rollback
uses the current local configuration. Restore matching Git revisions and
backups separately when reverting configuration or code.

## Migration and reset

Stop the previous instance before migrating. Transfer `.env`, `secrets/`,
and `config/local/` securely, then check UID/GID and TLS on the new host.
Keep encrypted backups outside the checkout.

Run `python3 scripts/bridge.py reset` in a local terminal and type `RESET`
to remove the container, network, and local configuration, including any
credentials in those directories. Revoke credentials separately in their
respective portals. Vikunja stores the task data.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| DNS or timeout | The host and container must resolve and reach Vikunja. Check routing, firewall rules, and HTTPS access to OpenAI. Use a hostname reachable from the container. |
| Host works, container fails | Use `doctor` and check Docker DNS. A Git-ignored Compose override can configure DNS or `extra_hosts`. Preserve the TLS hostname. |
| TLS error | Verify the host clock, hostname/SAN, expiry, and certificate chain. For a private CA, provide its verified public PEM file in setup. |
| HTTP redirect | Use the final HTTPS MCP endpoint from Vikunja Settings. Verify that the route accepts MCP requests directly. |
| MCP 404 or missing settings | Check Vikunja 2.7.0+, the `/api/v2/mcp` path, and reverse-proxy routing. |
| MCP 401 | Check expiry, revocation, the `Bearer ` prefix, and MCP Access. Select **No Authentication** in ChatGPT so the client supplies the local authorization header. |
| MCP 403 or permission error | Check the token scope and the user's project access. The Read only preset blocks writes. |
| Tunnel 401 or 403 | Check the runtime key, organization ID, workspace association, and Tunnels Read + Use. |
| Tunnel missing in ChatGPT | Check the target workspace and its policies for custom apps. |
| Container unhealthy | Run the deployment health script and inspect client diagnostics. Check MCP initialization and successful control-plane polling separately. |
| OAuth discovery pending | Check that Compose sets `CONTROL_PLANE_POLL_CHANNELS=main` and recreate the container. The deployment uses its own health script because upstream `/readyz` can stay pending when OAuth discovery returns HTML. |
| Healthy, but tools missing | Repeat the probe, check permissions, refresh the app's tool catalog, and try a new chat. |
| Token rotation ignored | Use `docker compose down`, setup, and start. Recreating the container remounts replaced secret files. |
| Secret mount denied | Check file ownership, modes 0700/0600, BRIDGE_UID/GID, and Docker UID remapping. |

For reverse-proxy deployments, verify that the existing route preserves
Authorization and supports POST and SSE. Check TLS separately on the
proxy-to-Vikunja connection.
