# Verification

The official tunnel-client 0.0.19 image was run on Linux ARM64. The live
Vikunja MCP handshake returned **27 tool names** without tool execution.
On November 3, 2026, the operator confirmed the connection from ChatGPT.

| Check | Observed result |
| --- | --- |
| Vikunja backend | Version 2.7.1 confirmed by installed app metadata and the public info endpoint |
| Unauthenticated MCP | POST `initialize` returned HTTP 401 |
| Live DNS and TLS | Host and Docker network reached the public info endpoint with TLS verification |
| Official image | ARM64 and AMD64 manifests verified. The ARM64 binary reported 0.0.19 |
| Compose | Example configuration validated with Compose 5.6.1 |
| Python suite | Eight protocol and configuration tests passed. Two image lifecycle tests covered update and rollback |
| Docker integration | Isolated HTTPS fixture passed with the pinned image |
| Live tunnel | Container reported `running / healthy` with a successful OpenAI poll within the preceding 10 seconds |
| Git exclusions | Local environment, credentials, CA, and overrides were excluded. The example environment remained tracked |

## OAuth discovery on the live instance

The first launch exposed a case absent from the original fixture. Both
OAuth protected-resource discovery URLs returned HTTP 200 with frontend
HTML. MCP initialization succeeded, while unscoped polling in 0.0.19
stayed at `startup catalog pending`.

The documented `CONTROL_PLANE_POLL_CHANNELS=main` option limits polling to
the Vikunja channel. The deployment checks liveness, successful initial MCP
initialization, and recent polling separately from the upstream OAuth
readiness gate. The updated fixture reproduces the HTML response and
verifies successful `tools/list` forwarding while upstream OAuth readiness
remains pending.

Docker reported that the deployment host lacked cgroup support for its
configured memory limit. Verify host cgroup support before relying on
`mem_limit`.

## Isolated integration coverage

`python3 tests/integration.py` runs the official client against local HTTPS
fixtures. It verifies:

- Native resolution of file-backed OpenAI and Vikunja credentials.
- Bearer injection for MCP initialization and forwarded `tools/list`.
- Compatibility fallback from `server/discover` to `initialize`.
- Forwarded Authorization precedence and HTTP 401 for an invalid token.
- Credential separation between endpoints and absence of fixture credentials
  from the observed client logs.
- Health checks that reject failed MCP probes, absent or stale polls, and
  untrusted TLS.
- Restart and recreation from the same files.

The fixtures generate temporary credentials and CA material. The test uses
loopback with a temporary host-network override and removes its containers
afterward. [Reproduction commands](development.md)

## Coverage limits

AMD64 image availability was checked at the manifest level. Runtime testing
was performed on ARM64. Docker rootless operation, UID remapping, a physical
Pi reboot, and workspace-specific policies require separate verification.
If a reverse proxy is present, verify the TLS hop from that proxy to Vikunja
separately.

For each new installation, verify workspace association and token scope,
connect the app through **Tunnel** with **No Authentication**, and confirm
one read-only operation from ChatGPT. The tool catalog can include write
tools even when the token blocks them. Obtain an explicit request before
testing writes. [Setup guide](setup.md)
