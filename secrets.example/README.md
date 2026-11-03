Esempi del formato, senza credenziali utilizzabili:

| File locale ignorato da Git | Contenuto |
| --- | --- |
| `secrets/openai_api_key` | La sola chiave runtime OpenAI |
| `secrets/vikunja_authorization` | `Bearer ` seguito dal token MCP Vikunja |

Usare `python3 scripts/setup.py` nel terminale locale: non copiare token in chat,
argomenti shell o file di esempio. Directory 0700, file 0600, proprietario uguale
all'utente del container. Compose monta questi file in sola lettura; non li cifra.
Il prefisso `file:` del client risolve l'intero valore dell'header: non usare
`Bearer file:/…`, interpolazioni `${TOKEN}` o un inesistente suffisso `_FILE`.
