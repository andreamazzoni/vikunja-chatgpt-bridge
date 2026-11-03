# Verifiche del 2 novembre 2026

## Esito e ambito

L'architettura senza proxy è supportata dalla documentazione e il comportamento
di iniezione locale è stato verificato con **il client ufficiale 0.0.19 dentro
l'immagine Docker fissata** su Linux ARM64. Dopo il setup locale dell'operatore,
è stato verificato anche l'accesso MCP autenticato reale: handshake riuscito e
**27 strumenti elencati**, senza chiamarne alcuno. Il 3 novembre 2026
l'operatore ha confermato il funzionamento anche da ChatGPT.

| Verifica | Risultato effettivo |
| --- | --- |
| Bridge TrueNAS preesistente | Ispezionati in sola lettura Compose, build, lock, codice e documentazione; nessun file credenziale consultato o riutilizzato, nessuna modifica |
| Requisiti MCP Vikunja | Guida ufficiale: 2.7.0+, Streamable HTTP, `/api/v2/mcp`, Bearer e permessi MCP Access |
| Versione istanza reale | TrueNAS segnala app attiva con Vikunja 2.7.1; endpoint pubblico info conferma `v2.7.1` |
| Endpoint reale senza credenziali | POST `initialize` senza Authorization: **HTTP 401**; nessuna lettura o modifica di task |
| Rete/TLS reali | DNS e HTTPS verificati dall'host; GET pubblico info riuscito anche dalla rete Docker dell'immagine ufficiale; nessun bypass TLS |
| Release client | 0.0.19, pubblicata il 30 ottobre 2026; verificati manifesti ufficiali ARM64 e AMD64 |
| Immagine eseguita | Digest indice `sha256:dcae53be336c062ffdc3f250a287b2a07724c344b8c370a50f54ad033af43151`; binario riporta 0.0.19 |
| Validazione Compose | `docker compose --env-file .env.example config --quiet` riuscito, Compose 5.6.1 |
| Controlli Python locali | **8 test passati**: URL, TLS, permessi/symlink dei file, protocollo JSON/SSE, redirect negati e divieto tools/call nel probe |
| Test Docker HTTPS isolato | Passato con il Compose del progetto e override temporaneo; tutti i dettagli sotto |
| Tunnel reale dopo la correzione | Container `running / healthy`, script di salute con uscita 0 e polling OpenAI riuscito osservato negli ultimi 10 secondi |
| Regole Git e contesto build | Verificate esclusioni `.env`, secrets, CA e override in un repository temporaneo; `.env.example` resta versionabile; nessuna build locale necessaria |

L'URL dell'installazione è salvato soltanto nel `.env` locale ignorato da Git.
Il repository pubblico contiene esempi generici. Durante la preparazione non
sono stati salvati token reali; l'operatore li ha poi inseriti localmente con
setup e ha configurato il tunnel. I controlli usano i file protetti senza
mostrarne i valori. Nessun task reale è stato letto, creato, modificato o
cancellato. Nessun servizio preesistente, repository remoto, push, plugin
pubblico o connessione ChatGPT è stato modificato o creato automaticamente.

## Correzione della discovery dopo l'avvio reale

Il primo avvio ha evidenziato un limite non presente nella fixture originaria:
le due URL `/.well-known/oauth-protected-resource…` dell'istanza rispondono
**HTTP 200 con HTML**, anziché HTTP 404 per indicare l'assenza di OAuth.
Il probe MCP del container riesce, ma 0.0.19 ritenta la discovery OAuth e il
polling non limitato rimane bloccato con `startup catalog pending`.

Verificata nel sorgente e nella documentazione ufficiale l'opzione
`CONTROL_PLANE_POLL_CHANNELS=main`. Viene usato soltanto quel canale, senza
attendere il catalogo Harpoon. La discovery OAuth continua in background e
il `/readyz` globale rimane negativo: non è usato per dichiarare la salute del
canale MCP statico. Lo script richiede invece `/healthz`, probe iniziale MCP
`succeeded` da `/health/mcp` e polling recente tramite `/metrics`.

La fixture è stata aggiornata per riprodurre HTML 200. Il client reale nella
fixture inoltra correttamente `tools/list` con polling limitato a `main`, mentre
la diagnostica globale continua a dichiarare `oauth discovery pending`.
Verificato anche che il controllo del progetto rifiuti un probe MCP fallito
o che richieda autenticazione, oltre ai polling mancanti/obsoleti e ai TLS
non attendibili. Non sono stati aggiunti proxy, patch al client, downgrade o
modifiche a Vikunja/Nginx/TrueNAS.

Durante la ricreazione Docker ha segnalato che il limite memoria non viene
applicato per mancanza del supporto cgroup nell'ambiente host. Il progetto non
modifica kernel o cgroup; `mem_limit` non va considerato un limite effettivamente
applicato su questo host finché tale configurazione non è verificata separatamente.

## Prova del comportamento reale del client

`python3 tests/integration.py` crea servizi HTTPS su loopback con una CA
temporanea, credenziali generate e un container Compose con nome casuale.
Il servizio fittizio che rappresenta OpenAI restituisce richieste MCP tramite
il protocollo ufficiale di polling; quello che rappresenta Vikunja richiede il
Bearer. Viene eseguito il client distribuito da OpenAI, non un'implementazione
simulata del client.

Verificato:

- Lettura nativa di `control-plane.api-key=file:/…` e di
  `MCP_EXTRA_HEADERS="Authorization: file:/…"`.
- Bearer presente nei probe `initialize` e nelle richieste `tools/list`
  inoltrate dal control plane fittizio, su TLS con CA verificata.
- Fallback dal tentativo moderno `server/discover` a `initialize` per un server
  che risponde Method not found, come previsto dalla compatibilità MCP.
- Risposta con catalogo di strumenti fittizi restituita al control plane.
- `Authorization` del connettore ha precedenza sul valore statico anche se
  espresso con diversa capitalizzazione; un Bearer errato produce 401.
- Credenziale MCP assente nelle richieste al control plane fittizio e chiave
  OpenAI assente nelle richieste al server MCP fittizio; credenziali complete
  assenti dai log del client osservati.
- Health positivo con polling recente, negativo con timestamp obsoleto o zero.
- Probe locale con `initialize`/`notifications/initialized`/`tools/list`, senza
  alcuna chiamata `tools/call`.
- Ripresa dopo `restart`, arresto e ricreazione del container dagli stessi file.
- Rifiuto del certificato della fixture quando la CA non è più configurata:
  nessuna richiesta HTTP autenticata raggiunge MCP e health non positivo.

I container di test e i relativi file temporanei vengono rimossi. L'override
usa la rete host per contattare soltanto le fixture loopback; non è una modifica
alla rete del deployment normale.

## Verifiche per una nuova installazione

- Verifica dell'associazione al workspace corretto e dei permessi dell'operatore
  ChatGPT; la configurazione nel portale non viene modificata dagli script.
- Verifica del preset Read only selezionato dall'operatore per il token: il
  catalogo può esporre nomi di scrittura anche quando il token non li autorizza.
- Creazione dell'app privata ChatGPT tramite
  Connection: Tunnel e No Authentication; discovery nel workspace effettivo.
- Una lettura circoscritta concordata da ChatGPT, poi conferma del risultato
  nell'interfaccia Vikunja. Solo una richiesta esplicita potrà autorizzare un
  successivo test di scrittura, con progetto e contenuto definiti.
- Verifica indipendente del tratto reverse proxy → Vikunja se presente: non
  desumibile dal certificato presentato al Pi. Nessuna configurazione proxy è
  stata letta o modificata per eseguire questi test.

Il manifesto AMD64 è stato verificato, ma non è stato eseguito un container
AMD64. Non sono stati collaudati Docker rootless, rimappatura UID, riavvio fisico
del Pi, conservazione dei dati da parte di OpenAI o policy specifiche del workspace.

## Ripetizione

```sh
docker compose --env-file .env.example config --quiet
python3 -m unittest discover -s tests -p 'test_*.py' -v
docker compose pull
python3 tests/integration.py
```

I test non richiedono segreti reali. Nei sandbox che vietano socket locali o
accesso al daemon Docker devono essere eseguiti da un terminale autorizzato.
Non aggirare questi vincoli usando privilegi nel container di produzione.

Le fonti e il runbook di attivazione sono nel [README](../README.md).
