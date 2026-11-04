# Architecture and security

```text
ChatGPT → OpenAI Secure MCP Tunnel
            ↑ Outbound HTTPS polling and responses
            tunnel-client → HTTPS with Bearer authentication → Vikunja MCP
```

The official client reads the complete authorization value using
`MCP_EXTRA_HEADERS: "Authorization: file:/run/secrets/vikunja_authorization"`.
It sends the header to the configured MCP origin, including same-origin
probes and discovery. Forwarded connector headers take precedence.

The static Vikunja credential is shared by users of the tunnel and app.
Restrict access through workspace membership, the dedicated Vikunja account,
and token permissions. Vikunja enforces those permissions independently of
prompts and tool annotations such as `readOnlyHint`.

The OpenAI runtime key authenticates polling and responses to OpenAI. The
Vikunja token authenticates the local request to Vikunja. MCP requests,
arguments, catalogs, and results travel through OpenAI. Keep credentials
out of tool payloads and logs.

Compose runs the client as a non-root user with diagnostics on loopback
and no published ports, Docker socket, or NAS volume mounts. Host and
Docker administrators can access mounted secrets. Use the host firewall
for any required outbound network restrictions.

This deployment is intended for private ChatGPT integrations. Publishing
the repository source is separate from distributing a public ChatGPT
plugin. Public plugins require a stable public HTTPS endpoint.

## MCP probe and container health

The host probe sends `initialize`, `notifications/initialized`, and paginated
`tools/list`. It accepts JSON and SSE responses, rejects redirects, and
reports tool names and counts.

The container health script reads `/healthz`, `/health/mcp`, and `/metrics`
to check liveness, successful initial MCP initialization, and recent
control-plane polling. A successful check exits silently.

`CONTROL_PLANE_POLL_CHANNELS=main` limits polling to the Vikunja channel.
In tunnel-client 0.0.19, unscoped polling can wait for the OAuth catalog
when discovery URLs return frontend HTML with HTTP 200. Background discovery
can still log warnings and leave upstream `/readyz` at
`oauth discovery pending`. The bridge checks main-channel health separately.
Review the polling scope and health criteria before adding OAuth.
[Observed behavior and fixture coverage](verification.md#oauth-discovery-on-the-live-instance)
