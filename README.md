# vikunja-chatgpt-bridge

Create a private **Vikunja plugin for ChatGPT** that you can enable in a chat
and use to ask about projects and tasks in your self-hosted instance.
The Docker Compose bridge runs the official tunnel-client and connects
the plugin to Vikunja over HTTPS through OpenAI Secure MCP Tunnel.

## Example prompts

Enable the Vikunja plugin in a ChatGPT conversation and try either prompt
with a read-only token:

- **Plan your week.** “In my Home project, which open tasks are overdue or
  due in the next seven days? Group them by due date.”
- **Catch up on a project.** “Summarize the open tasks in my Home project.
  Flag tasks without a due date and include links where available.”

| Component | Version or requirement |
| --- | --- |
| Vikunja | **2.7.0+** with built-in MCP at `/api/v2/mcp` over Streamable HTTP |
| tunnel-client | **0.0.19**, official image pinned by digest |
| Host | Docker Engine, Docker Compose v2+, Python 3.11+ for local scripts |

## Requirements

- A Linux host with HTTPS access to Vikunja and the OpenAI control plane.
- A dedicated OpenAI tunnel associated with the target ChatGPT workspace.
- A Vikunja MCP token with the **Read only** preset for the first connection.

The deployment was tested on ARM64 through ChatGPT. The official image also
provides an AMD64 manifest. See the [verification record](docs/verification.md).

## Quick start

After creating the tunnel and credentials, run this command from the project
directory in a local terminal:

```sh
python3 scripts/bridge.py install
```

The installer downloads the pinned image, collects credentials with hidden
input, checks Compose and TLS, and starts the container after confirmation.
In ChatGPT, add a custom MCP server named **Vikunja**, select **Tunnel** and
**No Authentication**, then install the plugin and enable it in a new chat.
The tunnel client adds the Vikunja Bearer token on the local HTTPS connection.
See the [ChatGPT setup steps](docs/setup.md#5-connect-the-custom-app-in-chatgpt).

## Commands

| Operation | Command |
| --- | --- |
| Guided installation | `python3 scripts/bridge.py install` |
| Download the pinned image | `python3 scripts/bridge.py build` |
| Validate configuration and TLS | `python3 scripts/bridge.py validate` |
| Container status and last probe | `python3 scripts/bridge.py status` |
| MCP handshake and tool catalog | `python3 scripts/bridge.py probe` |
| Start | `python3 scripts/bridge.py start --single-instance-confirmed` |
| Stop | `python3 scripts/bridge.py stop` |
| Restart | `python3 scripts/bridge.py restart` |
| Update | `python3 scripts/bridge.py update --image PINNED_IMAGE` |
| Restore the previous image | `python3 scripts/bridge.py rollback` |
| Remove the deployment and local credentials | `python3 scripts/bridge.py reset` |

`status` and `probe` accept `--json`. The probe lists MCP tools without
executing them. The CLI follows the TrueNAS bridge conventions. Here, `build`
pulls an existing official image.

## Guides

[Setup](docs/setup.md) · [Operations](docs/operations.md) ·
[Architecture](docs/architecture.md) · [Development](docs/development.md) ·
[Verification](docs/verification.md) · [Licensing](docs/licensing.md)
