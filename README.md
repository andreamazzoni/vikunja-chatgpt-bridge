# Vikunja plugin for ChatGPT

Use your self-hosted Vikunja as a private ChatGPT plugin. The Docker Compose
bridge connects Vikunja's built-in MCP server through OpenAI Secure MCP Tunnel.

> “Which tasks in my Home project are overdue or due this week?”

**Start with a read-only Vikunja token.** Plugin users share it. If you grant
write permissions, ChatGPT can create, change, or delete real data within those
permissions. Results pass through OpenAI even in read-only mode.
[Security details](docs/architecture.md)

## Quickstart

**Requirements**

- Vikunja 2.7.0+ with its MCP endpoint (`/api/v2/mcp`) reachable over HTTPS from the bridge.
- Linux with Docker Engine, Compose v2+, Python 3.11+, and HTTPS access to OpenAI.
- A ChatGPT workspace that allows custom MCP apps and an OpenAI Platform organization.

1. **Vikunja.** In **Settings → MCP**, copy the HTTPS endpoint and create a
   token with the **Read only** preset.
2. **OpenAI.** Create a dedicated tunnel, associate it with your ChatGPT
   workspace, and copy its ID. Create a runtime API key with
   **Tunnels Read + Use**. [Tunnel setup](docs/setup.md#create-the-tunnel)
3. **Bridge host.** Run this from the checkout in a local terminal as a
   non-root user with Docker access.

   ```sh
   python3 scripts/bridge.py install
   ```

   Enter the MCP URL, tunnel ID, and credentials at the prompts. Credential
   input is hidden. Type `yes` once you've checked that no other client uses
   the tunnel.
4. **ChatGPT.** Add a custom MCP server, select **Tunnel** and your tunnel, then
   choose **No Authentication**. Install the app and enable it in a new chat.
   Try the example above with one of your projects and compare the result with Vikunja.
   [ChatGPT setup](docs/setup.md#connect-the-custom-app-in-chatgpt)

## Example prompts

- **Read.** “Summarize the open tasks in Move and flag those without a due date.”
- **Create.** “Add a task in Home to book the boiler service by Friday.”
- **Edit.** “Set the boiler service task's due date to Monday.”

The last two examples require the corresponding write permissions.
[Enable writes or rotate a token](docs/operations.md#change-or-rotate-the-vikunja-token)

## Basic commands

| Command | What it does |
| --- | --- |
| `python3 scripts/bridge.py status` | Show container health and the last saved probe. |
| `python3 scripts/bridge.py probe` | Check MCP directly and list tools without running them. |
| `python3 scripts/bridge.py stop` | Stop the bridge. |
| `python3 scripts/bridge.py start --single-instance-confirmed` | Start after checking the tunnel is free. |
| `python3 scripts/bridge.py restart` | Recreate the container and wait for health. |

## Guides

[Setup](docs/setup.md) · [Operations](docs/operations.md) ·
[Architecture](docs/architecture.md) · [Verification](docs/verification.md) ·
[Development](docs/development.md) · [Licensing](docs/licensing.md)
