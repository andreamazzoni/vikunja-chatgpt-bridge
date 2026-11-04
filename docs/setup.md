# Setup

Start with the [quickstart](../README.md#quickstart). Use one active client per
tunnel ID.

## Create a Vikunja token

Vikunja **2.7.0 or later** exposes **Settings → MCP**. Find the backend version
in Vikunja or query its info endpoint. The TrueNAS catalog package version is
separate from the Vikunja backend version.

```sh
curl --fail --silent --show-error https://vikunja.example.net/api/v1/info
```

1. Open **Settings → MCP** from the Vikunja user menu and copy the full HTTPS
   MCP URL.
2. Create a token named, for example, `ChatGPT Vikunja read only`.
3. Select **Read only** explicitly. The default preset grants write access.
4. Keep **MCP → Access** and the required read permissions. Set an expiry.
5. Copy the token when Vikunja displays it and enter it at the hidden prompt
   during installation.

The token inherits the account's project access. Use a dedicated account to
limit access to the projects you need. [Token changes and rotation](operations.md#change-or-rotate-the-vikunja-token)

## Create the tunnel

1. In the intended OpenAI Platform organization, create a dedicated tunnel
   and copy the complete `tunnel_id`. Creating or editing tunnels requires
   **Tunnels Read + Manage**.
2. Associate the tunnel with the target ChatGPT workspace so it appears there
   when you add the custom MCP server.
3. Create an organization runtime API key with **Tunnels Read + Use** for the
   bridge. Save the optional `org-…` ID if your organization requires it.

Organization administrators can manage permissions in Roles or Groups. Allow
time for permission changes to propagate. Contact OpenAI support if an
enterprise workspace association cannot be verified.

[Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels) ·
[Runtime API keys](https://platform.openai.com/settings/organization/api-keys) ·
[Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) ·
[Client onboarding](https://github.com/openai/tunnel-client/blob/v0.0.19/docs/onboarding.md)

## Configure the host

Use a private terminal as the non-root user who operates Docker. The
[quickstart installer](../README.md#quickstart) pulls the pinned image, prompts
for configuration, checks Compose and TLS, and offers to start the client. Enter
the bare Vikunja token at the hidden prompt. Setup adds the `Bearer ` prefix.
Keep secret values out of shell arguments, shell traces, chats, and screenshots.

| Git-ignored path | Contents |
| --- | --- |
| `.env` | MCP URL, tunnel and organization IDs, UID/GID, CA path, and optional image pin |
| `secrets/openai_api_key` | OpenAI runtime API key |
| `secrets/vikunja_authorization` | Complete `Bearer …` value |
| `config/local/ca.pem` | Optional public CA certificate |

Setup uses mode 0700 for private directories and 0600 for files. Secrets are
stored as plaintext on disk. Compose mounts them read-only and runs the client
with the operator's UID/GID. Check file access separately when using rootless
Docker or user namespace remapping.

### HTTPS with a private CA

For a publicly trusted certificate, use the default CA setting. For a private
CA, obtain its public PEM certificate through a trusted administrative channel,
verify its fingerprint and the Vikunja server name, and enter the PEM path when
prompted. Enter `-` to restore the default CA setting. Keep TLS certificate and
hostname verification enabled.

The client uses `SSL_CERT_FILE` and can also load CA certificates from the system
directory. With the default CA setting, the host probe uses the host's trust
store.

### Manual installation

Use these commands to run installation in separate steps. If you are
reconfiguring an existing deployment, remove the project containers with
`docker compose down` before running setup. This lets Compose mount the updated
credential files on the next start. Press Enter at an existing credential prompt
to keep its value. If setup is interrupted, finish it before starting the bridge.

```sh
python3 scripts/setup.py
python3 scripts/bridge.py validate
python3 scripts/bridge.py build
python3 scripts/bridge.py probe
```

Verify that any other client on this tunnel has stopped, then run the following
commands.

```sh
python3 scripts/bridge.py start --single-instance-confirmed
python3 scripts/bridge.py status
```

## Connect the custom app in ChatGPT

Keep the client running during discovery. Menu labels and access depend on
your account and workspace policy.

1. In the target workspace, open **Plugins / Apps → + → Add custom MCP server**.
2. Name the app `Vikunja` and describe its access to your self-hosted instance.
3. Select **Tunnel** and choose the dedicated tunnel or enter its ID.
4. Select **No Authentication**. Workspace permissions govern access to the
   tunnel, and the bridge adds the Vikunja token on the HTTPS request to Vikunja.
   Keep the Vikunja URL and credentials in the local bridge configuration.
5. Complete the portal prompts, install the app, and inspect the discovered
   tools. If the UI requires OAuth, check the workspace policy.
6. Enable the app in a new chat through the app picker or `@Vikunja`.

For each new deployment, ask ChatGPT to list open tasks in a known project and
compare the result with the Vikunja UI. [Verification](verification.md)

[Add a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server) ·
[Test a ChatGPT plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt) ·
[Vikunja MCP guide](https://vikunja.io/help/mcp/)
