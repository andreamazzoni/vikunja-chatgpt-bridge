# Operazioni

## Gestione, aggiornamento e ripristino

| Operazione | Comando |
| --- | --- |
| Stato | `docker compose ps` |
| Salute con polling recente | `docker compose exec -T tunnel-client /bin/sh /opt/bridge/healthcheck.sh` |
| Arresto, conservando il container | `docker compose stop` |
| Riavvio processo | `docker compose restart` |
| Arresto e rimozione container/rete del progetto | `docker compose down` |
| Nuovo avvio | `docker compose up -d --wait --wait-timeout 180` |
| Verificare il binario fissato | `docker compose exec -T tunnel-client /usr/bin/tunnel-client --version` |
| Diagnostica locale aggiuntiva | `docker compose exec -T tunnel-client /usr/bin/tunnel-client doctor --control-plane.api-key=file:/run/secrets/openai_api_key --explain` |

`doctor` può contattare i servizi configurati e inizializzare MCP; non sostituisce
il test ChatGPT. Evitare il debug HTTP grezzo e non esportare indiscriminatamente
log o diagnostica. I normali log sono limitati a 3 file da 10 MiB; possono
contenere indirizzi e metadati anche se non devono contenere segreti.

Il pin predefinito è in `compose.yaml` e `versions.lock.json`. Prima di
cambiare versione verificare i manifesti ARM64 e AMD64 e ripetere i test del
client candidato. [Release ufficiali](https://github.com/openai/tunnel-client/releases)

`bridge.py update --image IMMAGINE_FISSATA` accetta l'immagine ufficiale con tag
di versione e digest. Senza `--image` usa il pin del checkout. Il comando
scarica il candidato, ricrea il container e salva la selezione in `.env`
dopo il controllo di salute. Se la prova fallisce tenta di riavviare l'immagine
precedente. `bridge.py rollback` usa l'immagine annotata in
`.local/rollback.json`. I due comandi richiedono un bridge in esecuzione.

Il rollback dell'immagine usa la configurazione locale corrente. Per
ripristinare anche codice o configurazione recuperare la revisione Git e il
backup corrispondenti. Per migrare, fermare l'istanza precedente, trasferire in
modo sicuro `.env`, `secrets/` e `config/local/` e verificare UID/GID e TLS.

`bridge.py reset` richiede di digitare `RESET` in un terminale locale.
Rimuove container, rete e configurazione locale, comprese le copie dei segreti
in quelle directory. Revocare separatamente le credenziali nei rispettivi portali.

Conservare questi file in un backup **cifrato fuori dal checkout**, con accesso
ristretto; non creare archivi contenenti segreti dentro Git o nel contesto Docker.
Non ci sono dati task da ripristinare qui: rimangono in Vikunja. La rimozione
dell'app ChatGPT o del container non revoca token Vikunja o chiavi OpenAI.

## Troubleshooting

| Sintomo | Verifiche |
| --- | --- |
| DNS o timeout | Pi e container devono risolvere l'hostname e raggiungere Vikunja; controllare firewall/routing/VLAN e uscita 443 verso OpenAI. Un DNS o `/etc/hosts` valido solo sull'host non basta dentro Docker. Nessun `localhost` per indicare TrueNAS. |
| Host funziona, container no | Verificare con `doctor` nel container. Se serve, usare un override Compose locale ignorato da Git per DNS o `extra_hosts`, mantenendo hostname e certificato coerenti. Non usare `network_mode: host` come correzione predefinita. |
| Errore TLS | Controllare orologio del Pi, SAN/hostname, scadenza e catena completa; per CA privata fornire il PEM verificato. Non usare `curl -k`, `InsecureSkipVerify` o HTTP con Bearer. |
| HTTP 301/302/307/308 | Copiare l'endpoint HTTPS finale da Impostazioni MCP. Evitare redirect, login web intermedio o autenticazione aggiuntiva del reverse proxy; non inviare il token al login. |
| MCP 404 o assenza scheda MCP | Verificare backend 2.7.0+, percorso `/api/v2/mcp` e routing esistente. Un 404 non giustifica installare un altro server MCP. |
| MCP 401 | Token scaduto/revocato, file vuoto o senza `Bearer `, permesso MCP Access mancante. Verificare tramite setup senza stampare il file. ChatGPT deve usare No Authentication: un Authorization inoltrato prevale sul valore statico. |
| MCP 403 o errore JSON-RPC di permessi | Controllare diritti del token e accesso dell'utente al progetto. Read only nega le scritture; non aumentare i permessi per fare passare un test di lettura. |
| Tunnel 401/403 | Problema distinto dal token Vikunja: chiave runtime, organizzazione, associazioni e Tunnels Read + Use. Controllare il contesto `org-…`. |
| Tunnel invisibile in ChatGPT | Associare il workspace corretto e verificare i permessi dell'operatore e le policy per app personalizzate. La configurazione del solo Platform project non basta. |
| Container unhealthy | Eseguire lo script `healthcheck.sh` nel container e usare `doctor` per la diagnostica. Il primo polling può richiedere tempo. Verificare entrambi i collegamenti senza aumentare i timeout alla cieca. |
| `startup catalog pending` / `oauth discovery pending` | Verificare `CONTROL_PLANE_POLL_CHANNELS=main` nel Compose e ricreare il container con `docker compose up -d --force-recreate`. Le pagine HTML 200 sulle URL OAuth bloccano il polling non limitato in 0.0.19. Il controllo globale `/readyz` può restare negativo; usare lo script di salute del progetto, che richiede probe MCP riuscito e polling recente. |
| Healthy ma strumenti assenti/non utilizzabili | Ripetere `check.py mcp`, controllare il catalogo reale, autenticazione e permessi; usare Refresh nell'app ChatGPT e una nuova conversazione. Non presumere che ogni tool esposto sia autorizzato. |
| Token nuovo non usato | Il client risolve il file all'avvio; un bind mount può conservare il vecchio inode. Usare `down`, setup e `up`, non il solo `restart`. |
| Permission denied sui secrets | Verificare proprietario, modi 0700/0600, BRIDGE_UID/GID e assenza di rimappatura UID; non rendere i token leggibili a tutti. |

Con Nginx Proxy Manager o un altro reverse proxy, verificare che il routing
esistente inoltri Authorization e supporti POST/SSE senza buffering incompatibile.
Anche il collegamento proxy → Vikunja deve essere valutato: un HTTPS valido dal
Pi al proxy **non dimostra** che il successivo tratto sia cifrato. Non modificare
automaticamente il proxy o aggirare problemi spegnendo TLS.
