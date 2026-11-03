# Project principles

- Align the layout, operations guide, and CLI with the TrueNAS bridge. Adapt
  them to Vikunja's built-in MCP server and the official tunnel-client image.
- Use Docker Compose and pin images by version and digest. Track ARM64 and
  AMD64 verification separately.
- Keep private configuration, credentials, and local state out of Git.
  Collect credentials with hidden input and mount them read-only.
- Verify TLS, run as a non-root user, and keep diagnostics on loopback.
- Distinguish container health, the MCP probe, and acceptance from ChatGPT.
- Use isolated test fixtures. Writing to real data requires an explicit request.
- Publish source to the Forgejo repository designated by the operator.
