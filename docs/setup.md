# Configurazione e collegamento a ChatGPT

Usare `python3 scripts/bridge.py install` per il primo avvio guidato.
Le sezioni seguenti documentano anche la procedura manuale.

## 1. Verificare Vikunja e creare il token

Controllare la versione nell'interfaccia Vikunja, nei dettagli dell'app installata
su TrueNAS o con una richiesta pubblica, senza token:

```sh
curl --fail --silent --show-error https://vikunja.example.net/api/v1/info
```

Verificare il campo `version` del backend: il numero di pacchetto del catalogo
TrueNAS è distinto dalla versione Vikunja. Sono richiesti almeno **2.7.0** e la
scheda **Impostazioni → MCP**. Se la versione è precedente, fermarsi e pianificare
separatamente l'aggiornamento dell'app; questo progetto non lo esegue.

In Vikunja:

1. Aprire il menu utente → **Settings / Impostazioni → MCP**.
2. Creare un token con nome riconoscibile, per esempio `ChatGPT Vikunja lettura`.
3. Selezionare esplicitamente **Read only**. Il preset predefinito permette anche
   scritture, quindi controllare la selezione prima di confermare.
4. Mantenere **MCP → Access**, necessario per ogni connessione, e solo i permessi
   di lettura necessari. Impostare una scadenza adeguata.
5. Annotare l'endpoint mostrato dalla pagina e copiare il token solo nel prompt
   nascosto di setup. Il valore viene mostrato una sola volta.

Il token rispetta anche l'accesso ai progetti dell'utente che lo crea. Per isolare
ulteriormente i dati, usare un account dedicato con accesso soltanto ai progetti
necessari. Non presumere che il nome del token limiti i progetti.

Per abilitare scritture in un secondo momento, creare un **nuovo token** con i
singoli permessi richiesti o il preset **Typed tools read + write**, rivedendone
l'elenco. Evitare Full access come soluzione a un errore di autorizzazione.
Fermare e rimuovere il container di questo progetto, rilanciare setup, sostituire
il token Vikunja e ricreare il container; verificare il nuovo accesso, poi revocare
il vecchio token da Vikunja. Aggiornare il catalogo degli strumenti in ChatGPT.

## 2. Creare il tunnel e associarlo al workspace

Seguire la [guida Secure MCP Tunnel ufficiale](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
e l'[onboarding del client fissato](https://github.com/openai/tunnel-client/blob/v0.0.19/docs/onboarding.md).

1. Aprire [Platform → Organization → Tunnels](https://platform.openai.com/settings/organization/tunnels)
   nell'organizzazione corretta. Creare un tunnel dedicato, chiamato per esempio
   `vikunja-chatgpt-bridge`; copiare il `tunnel_id` completo.
2. Associare il tunnel sia all'organizzazione Platform che lo gestisce sia al
   **workspace ChatGPT di destinazione**. La sola associazione all'organizzazione
   Platform non garantisce che ChatGPT lo elenchi. Usare le opzioni offerte dal
   portale; per associazioni enterprise non verificabili serve l'assistenza OpenAI.
3. Creare una chiave nelle [Runtime API keys dell'organizzazione](https://platform.openai.com/settings/organization/api-keys).
   Non utilizzare una chiave admin per il processo permanente. Il principal della
   chiave deve avere **Tunnels Read + Use** per quel contesto.
4. La creazione/modifica del tunnel richiede invece **Read + Manage**. I ruoli
   sono a livello organizzazione, separati dai permessi di progetto e dalle
   autorizzazioni ChatGPT. L'amministratore può gestirli in Roles / Groups.
5. Se richiesto dal contesto dell'organizzazione, conservare anche l'ID `org-…`
   per il setup. Attendere la propagazione dei ruoli prima di riprovare.

Login, creazione chiave, associazioni e conferme del portale sono passaggi manuali.
Il progetto non automatizza il browser né crea tunnel usando credenziali del
bridge TrueNAS. Non è necessario configurare OAuth in Vikunja per questa
architettura con credenziale statica locale.

## 3. Configurare localmente, senza token in chat

Nel terminale privato del Raspberry Pi, come utente con accesso a Docker:

```sh
python3 scripts/setup.py
docker compose config --quiet
python3 scripts/check.py config
python3 scripts/check.py tls
docker compose pull
```

Il setup chiede URL MCP completo, tunnel ID, organization ID opzionale e i due
segreti con input nascosto. Per Vikunja inserire **solo il token**: il programma
aggiunge `Bearer `. Non eseguire il setup tramite una chat o un terminale che
registra l'input. Non usare `set -x`, token negli argomenti shell, `echo TOKEN`,
variabili in `.env`, screenshot o copie dei segreti nel repository.

Il setup non avvia nulla e non accede ai task. Rifiuta di modificare file quando
esistono container di questo progetto, anche arrestati: prima usare
`docker compose down`. Al nuovo avvio Compose rimonta i file aggiornati.
Invio mantiene i segreti esistenti; non li mostra. Un setup interrotto può aver
salvato parte dei file: ripeterlo prima di avviare il servizio.

| File locale ignorato da Git | Contenuto |
| --- | --- |
| `.env` | URL, tunnel/org ID, UID/GID dell'operatore e percorso CA; nessun token |
| `secrets/openai_api_key` | Solo chiave runtime OpenAI |
| `secrets/vikunja_authorization` | Valore completo `Bearer …` |
| `config/local/ca.pem` | CA pubblica opzionale; nessuna chiave privata |

Directory locali 0700 e file 0600; il container usa UID/GID dell'operatore.
I secrets Compose sono file montati in sola lettura, **non cifrati a riposo**.
Non impostare `uid`/`gid` sui secrets pensando che Compose rimappi la proprietà
dei file. Docker rootless/user namespace remapping richiede una verifica separata
dei permessi; non è incluso nel collaudo.

Per un certificato pubblico valido lasciare vuota la richiesta CA. Per una CA
privata, ottenere il certificato pubblico da un canale amministrativo affidabile,
verificarne fingerprint e nome/SAN, poi indicare il file PEM nel setup. Il client
usa `SSL_CERT_FILE`; le CA della distribuzione rimangono disponibili nella
directory di sistema. Con CA di sistema il probe Python usa le CA dell'host:
host e container possono avere trust store diversi. Se serve tornare alle CA di
sistema, rispondere `-`. Non disabilitare mai la verifica TLS o il nome del server.

## 4. Verificare MCP e avviare

Quando è presente il token Vikunja, eseguire:

```sh
python3 scripts/check.py mcp
```

Questo controllo dall'**host** invia solo `initialize`,
`notifications/initialized` e `tools/list`, inclusa la paginazione. Non invia
`tools/call`, non legge task e non modifica dati. Stampa solo conteggio e nomi
degli strumenti, mai token, descrizioni, risposte grezze o corpi degli errori.
Rifiuta redirect per proteggere il Bearer. Supporta risposte JSON e SSE.

Controllare che non ci siano altri client che usano questo tunnel ID, quindi:

```sh
docker compose up -d --wait --wait-timeout 180
docker compose ps
docker compose exec -T tunnel-client /bin/sh /opt/bridge/healthcheck.sh
```

Il client legge nativamente entrambi i segreti da file. L'immagine esegue già
`tunnel-client run` come entrypoint: non aggiungere un secondo `run` al command.
Non viene compilato o eseguito un server MCP locale; l'MCP rimane quello di Vikunja.

Il controllo di salute è uno script shell montato in sola lettura. Usa le
superfici ufficiali `/healthz`, `/health/mcp` e `/metrics`: richiede processo vivo,
probe MCP iniziale **riuscito** e un polling riuscito negli ultimi 120 secondi.
Non chiama strumenti e non prova l'accesso Vikunja continuativo, una chiamata
ChatGPT riuscita o i permessi per una specifica lettura. Ripetere il probe MCP
e il collaudo ChatGPT quando serve. Lo script non stampa nulla se riesce;
Compose ne interpreta il codice di uscita.

Il polling è limitato ufficialmente a **`CONTROL_PLANE_POLL_CHANNELS=main`**:
si usa soltanto l'MCP Vikunja, senza canale Harpoon. Questa scelta è necessaria
quando le URL `/.well-known/oauth-protected-resource…` restituiscono la pagina
HTML del frontend con HTTP 200. In 0.0.19 il polling non limitato aspetterebbe
indefinitamente il catalogo OAuth. Vikunja qui usa un Bearer statico e non
fornisce quel catalogo. Nessuna modifica a Vikunja o al reverse proxy è richiesta.

La discovery OAuth continua in background e può produrre warning. Il controllo
globale upstream `tunnel-client health` e `/readyz` rimangono negativi con
`oauth discovery pending` in questo caso: **non sono il controllo di salute
di questo deployment**. La salute del canale usato è verificata separatamente;
non si finge che OAuth sia configurato. Questa modalità è collaudata anche con
HTML 200 nelle fixture. Una futura integrazione OAuth richiederà una revisione
delle sottoscrizioni e dei controlli.

`restart: unless-stopped` riavvia il processo se termina e dopo il riavvio di
Docker/host, salvo arresto esplicito dell'operatore. Lo stato `unhealthy` da solo
**non** causa un riavvio Docker. Il client ha i propri tentativi di riconnessione;
non usare un watchdog che possa ripetere operazioni di scrittura.

## 5. Collegare l'app personalizzata a ChatGPT

Consultare [Add custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)
e [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt).
Le etichette della UI e la disponibilità dipendono dall'account e dalle policy del
workspace; il client deve restare attivo durante la discovery.

1. Nel workspace corretto aprire **Plugins / App → + → Add custom MCP server**,
   con accesso alla modalità sviluppatore/server personalizzati se richiesto.
2. Nome: `Vikunja`; descrizione: accesso alla propria istanza self-hosted.
3. In **Connection** scegliere **Tunnel**, poi il tunnel dedicato o il suo ID.
   Non inserire l'URL privato Vikunja come URL pubblico né incollare token.
4. Per questa connessione con autenticazione locale scegliere **No Authentication**:
   ChatGPT non deve inviare un proprio Bearer che sovrascriva quello statico.
   L'accesso al tunnel rimane protetto da autorizzazioni OpenAI/workspace e Vikunja
   continua a richiedere il token sul tratto locale.
5. Completare le conferme di rischio del portale, creare/installare l'app e
   controllare il catalogo scoperto. Se la UI impone OAuth, fermarsi: non simulare
   OAuth e non aggiungere proxy senza prima verificare policy e disponibilità.
6. Abilitare l'app in una nuova conversazione, tramite selezione app o `@Vikunja`.

La [guida Vikunja](https://vikunja.io/help/mcp/) avverte che il collegamento
**diretto** ChatGPT → Vikunja non supporta il suo Bearer senza OAuth. Qui si usa
un percorso diverso: il client del tunnel autentica localmente la richiesta.
L'iniezione è collaudata con servizi fittizi; l'accettazione end-to-end in ChatGPT
va ancora verificata nel workspace effettivo. Non dichiarare il plugin attivo
solo perché la discovery locale o il controllo di salute riescono.

Come primo collaudo concordato chiedere una **lettura circoscritta**, per esempio:

> Usa Vikunja per mostrarmi il titolo del progetto che ti indico. Non creare,
> modificare o cancellare nulla.

Scegliere esplicitamente un progetto accessibile e uno strumento di lettura fra
quelli realmente elencati. Le informazioni lette arrivano a OpenAI/ChatGPT.
Controllare il risultato nell'interfaccia Vikunja.

Solo dopo un'esplicita richiesta dell'operatore, attivare i permessi di scrittura
e concordare **progetto, titolo e contenuto** di un task di prova. Verificare
prima la lettura con il nuovo token, poi eseguire una sola creazione. Modifiche o
cancellazione del task di prova richiedono a loro volta una richiesta esplicita.
Questo repository non esegue quel test automaticamente.
