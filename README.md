# vikunja-chatgpt-bridge

Collega Vikunja self-hosted a ChatGPT tramite **OpenAI Secure MCP Tunnel**, con un
solo container: il `tunnel-client` ufficiale. Nessun server MCP aggiuntivo, proxy,
porta pubblicata o modifica alla configurazione di Vikunja/TrueNAS.

```text
ChatGPT → servizio Secure MCP Tunnel OpenAI
          ↑ HTTPS in uscita: polling e risposte
          tunnel-client sul Raspberry Pi → HTTPS → Vikunja su TrueNAS
                                          Authorization: Bearer …
```

Il Bearer Vikunja è risolto da un file locale dal client, mediante
`MCP_EXTRA_HEADERS: "Authorization: file:/run/secrets/vikunja_authorization"`.
Il file contiene **l'intero valore `Bearer …`**, non solo il token. Non servono
script di avvio, variabili con il token o interpolazioni nel file YAML.

| Componente | Versione / requisito |
| --- | --- |
| Vikunja con MCP integrato | **2.7.0+**; endpoint `/api/v2/mcp`, Streamable HTTP |
| tunnel-client | **0.0.19**, immagine ufficiale fissata anche per digest |
| Piattaforme dell'immagine | Linux ARM64 e AMD64 |
| Host | Docker Engine, Docker Compose v2+, Python 3.11+ per gli script locali |

## Requisiti

Linux ARM64 o AMD64, Docker con Compose, Python 3.11+, Vikunja raggiungibile
via HTTPS e un tunnel OpenAI dedicato associato al workspace ChatGPT.
Per il primo avvio usare un token MCP Vikunja **Read only**.

## Avvio rapido

Dalla cartella del progetto, dopo aver creato tunnel e credenziali, eseguire
in un terminale locale:

```sh
python3 scripts/bridge.py install
```

L’installazione scarica l’immagine fissata, chiede i segreti con input
nascosto, verifica Compose e TLS e avvia il container dopo la conferma.
Collegare quindi il tunnel a ChatGPT con **No Authentication**. Il client
aggiunge il token Vikunja sul collegamento locale.

## Comandi

| Operazione | Comando |
| --- | --- |
| Prima installazione guidata | `python3 scripts/bridge.py install` |
| Preparare l’immagine fissata | `python3 scripts/bridge.py build` |
| Verificare configurazione e TLS | `python3 scripts/bridge.py validate` |
| Stato e ultimo probe | `python3 scripts/bridge.py status` |
| Handshake e catalogo MCP | `python3 scripts/bridge.py probe` |
| Avvio | `python3 scripts/bridge.py start --single-instance-confirmed` |
| Arresto | `python3 scripts/bridge.py stop` |
| Riavvio | `python3 scripts/bridge.py restart` |
| Aggiornamento | `python3 scripts/bridge.py update --image IMMAGINE_FISSATA` |
| Ripristino immagine precedente | `python3 scripts/bridge.py rollback` |
| Rimozione del deployment e dei segreti locali | `python3 scripts/bridge.py reset` |

`status` e `probe` accettano `--json`. Il probe elenca gli strumenti MCP
senza eseguirli. Per `build` il bridge Vikunja usa l’immagine ufficiale
direttamente.

## Guide

[Configurazione](docs/setup.md) · [Operazioni](docs/operations.md) ·
[Architettura](docs/architecture.md) · [Sviluppo](docs/development.md) ·
[Verifiche](docs/verification.md) · [Licenze](docs/licensing.md)
