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
