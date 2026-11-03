# Setup and ChatGPT connection

Run `python3 scripts/bridge.py install` for guided installation once you
have a Vikunja token, tunnel ID, and OpenAI runtime key. Use one active client
per tunnel ID.

## 1. Check Vikunja and create a token

Check the backend version in Vikunja, in the installed TrueNAS app details,
or through the public info endpoint:

```sh
curl --fail --silent --show-error https://vikunja.example.net/api/v1/info
```

Use the response's `version` field. TrueNAS catalog package versions are
separate from Vikunja backend versions. Vikunja **2.7.0+** exposes **Settings →
MCP**. Upgrade Vikunja separately if the backend predates this feature.

1. Open **Settings → MCP** from the Vikunja user menu.
2. Create a token named, for example, `ChatGPT Vikunja read only`.
3. Select **Read only** explicitly. The default preset grants write access.
4. Keep **MCP → Access** and the required read permissions. Set an expiry.
5. Save the endpoint and enter the token at the hidden setup prompt. Vikunja
   shows the token value once.

The token inherits the user's project access. A dedicated account with access
to the required projects can narrow the scope further.

To enable writes later, create a new token with the specific permissions or
review the **Typed tools read + write** preset. Remove the bridge container
with `docker compose down`, run setup with the replacement token, and start
the bridge. Verify access, revoke the old token in Vikunja, and refresh the
ChatGPT tool catalog.

## 2. Create the tunnel

1. Open the tunnel settings for the intended Platform organization. Create a
   dedicated tunnel and copy its complete `tunnel_id`.
2. Associate it with the Platform organization and the **target ChatGPT
   workspace**. The target workspace association controls visibility in ChatGPT.
3. Create an organization runtime API key with **Tunnels Read + Use**. Use
   that key for the client process. Creating or editing a tunnel requires
   **Read + Manage**.
4. Save the optional `org-…` ID if required. Organization administrators can
   manage permissions in Roles or Groups. Allow time for changes to propagate.

Portal access, key creation, and workspace association are manual. Contact
OpenAI support if an enterprise workspace association cannot be verified.
The bridge uses local static Bearer authentication for Vikunja.

[Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels) ·
[Runtime API keys](https://platform.openai.com/settings/organization/api-keys) ·
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) ·
[Client onboarding](https://github.com/openai/tunnel-client/blob/v0.0.19/docs/onboarding.md)

## 3. Configure the host

Use a private terminal as the non-root user who operates Docker. For manual
setup, run:

```sh
python3 scripts/setup.py
python3 scripts/bridge.py validate
python3 scripts/bridge.py build
```

Setup asks for the MCP URL, tunnel ID, optional organization ID, and both
credentials. Enter the bare Vikunja token. Setup adds `Bearer `. Keep secret
values out of shell arguments, shell traces, chat, screenshots, and the checkout
apart from the designated secret files.

Remove existing project containers with `docker compose down` before running
setup again. This lets Compose mount the updated files on the next start.
Press Enter at an existing credential prompt to retain its value. If setup
is interrupted, finish it before starting the service.

| Git-ignored path | Contents |
| --- | --- |
| `.env` | URL, tunnel and organization IDs, UID/GID, CA path, and optional image pin |
| `secrets/openai_api_key` | OpenAI runtime API key |
| `secrets/vikunja_authorization` | Complete `Bearer …` value |
| `config/local/ca.pem` | Optional public CA certificate |

Private directories use mode 0700 and files use mode 0600. Compose mounts
the secret files read-only and runs with the operator's UID/GID. The files
remain plaintext at rest. Rootless Docker and user namespace remapping
require a separate permissions check.

For a publicly trusted certificate, use the default CA setting. For a private
CA, obtain its public PEM certificate through a trusted administrative
channel. Verify the fingerprint and server name before selecting the PEM
in setup. The client uses `SSL_CERT_FILE` and can also load CA certificates
from the system directory. The Python host probe uses the host's trust store
with the default CA setting. Enter `-` in setup to restore that setting.
Keep TLS certificate and hostname verification enabled.

## 4. Probe MCP and start

```sh
python3 scripts/bridge.py probe
python3 scripts/bridge.py start --single-instance-confirmed
python3 scripts/bridge.py status
```

Before using the start flag, verify that any previous client on this tunnel
has stopped. The host probe uses `initialize`, `notifications/initialized`,
and paginated `tools/list`. It accepts JSON and SSE, rejects redirects, and
prints tool names and counts only. The image already runs `tunnel-client run`
as its entrypoint and resolves both credentials from files.

Container health requires liveness, a successful initial MCP probe, and a
successful control-plane poll within 120 seconds. The read-only health script
uses `/healthz`, `/health/mcp`, and `/metrics`. A successful health check exits
silently. Repeat the MCP probe for a fresh local connection test and run a
read from ChatGPT to verify the full path.

`CONTROL_PLANE_POLL_CHANNELS=main` scopes polling to Vikunja. This matters
when OAuth discovery URLs return frontend HTML with HTTP 200. Unscoped
polling in 0.0.19 waits for the OAuth catalog in that case. Background
discovery can still log warnings and report `oauth discovery pending` in
upstream `/readyz`. The deployment health check measures the main channel
separately. Review the polling scope and health criteria before adding OAuth.

`restart: unless-stopped` restarts a terminated process and resumes the
container when Docker starts, unless the operator stopped it. Docker reports
`unhealthy` separately. The client retries control-plane connections itself.

## 5. Connect the custom app in ChatGPT

Keep the client running during discovery. Labels and access depend on the
account and workspace policy.

1. In the target workspace, open **Plugins / Apps → + → Add custom MCP server**.
2. Name the app `Vikunja` and describe its access to your self-hosted instance.
3. Select **Tunnel** as the connection and choose the dedicated tunnel or enter
   its ID.
4. Select **No Authentication** in ChatGPT. Tunnel access follows workspace
   permissions and the client adds the Vikunja token locally. Keep the private
   Vikunja URL and tokens in the bridge configuration.
5. Complete the portal prompts, install the app, and inspect the discovered
   catalog. If the UI requires OAuth, verify the workspace policy before
   proceeding.
6. Enable the app in a new chat through the app picker or `@Vikunja`.

This tunnel path supplies Bearer authentication to Vikunja locally. Each new
deployment needs its own end-to-end acceptance test from ChatGPT.

For the first test, pick a known project and request a read-only action:

> Use Vikunja to show me the title of this project. Leave all data unchanged.

Verify the result in the Vikunja UI. Data returned to the chat reaches OpenAI.
For a write test, first obtain an explicit request and agree on the project,
title, and content of one test task. Confirm read access with the replacement
token before creating it. Treat later edits or deletion as separate requests.

[Add a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server) ·
[Test a ChatGPT plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt) ·
[Vikunja MCP guide](https://vikunja.io/help/mcp/)
