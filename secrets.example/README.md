# Local secret files

| Git-ignored file | Contents |
| --- | --- |
| `secrets/openai_api_key` | The OpenAI runtime API key |
| `secrets/vikunja_authorization` | `Bearer ` followed by the Vikunja MCP token |

Run `python3 scripts/setup.py` in a private terminal. Enter secrets only
at the hidden prompts. The directory uses mode 0700 and the files use mode
0600. Their owner matches the container user. Compose mounts the files
read-only. Use encrypted storage if you require encryption at rest.

The client's `file:` reference resolves the entire header value. Put the
`Bearer ` prefix inside the file, followed by the token.
