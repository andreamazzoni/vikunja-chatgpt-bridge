# Architettura e sicurezza

## Sicurezza e dati

- Il token Vikunja viene aggiunto dal client solo sull'origine MCP configurata,
  anche per i probe/discovery della stessa origine. Il meccanismo non lo invia
  al control plane OpenAI né a un authorization server su un'altra origine.
- Gli header inoltrati dal connettore vengono applicati **dopo** quelli statici
  e possono sostituire Authorization. La credenziale è statica e condivisa da
  chi può usare questo tunnel/app: non esiste un token Vikunja distinto per ogni
  utente ChatGPT. Limitare workspace, app, account Vikunja e privilegi.
- La chiave runtime OpenAI è locale come file, ma **viene inviata a OpenAI**
  per autenticare polling e risposte. Non viene inoltrata a Vikunja.
- Richieste MCP, argomenti, catalogo, risultati e dati task richiesti attraversano
  OpenAI/ChatGPT. Un server o uno strumento che riflettesse un segreto nel payload
  lo farebbe attraversare a sua volta: evitare log e strumenti che espongono token.
  Il tunnel non è una soluzione per mantenere tutti i dati o tutti gli artefatti
  di autenticazione esclusivamente nella LAN.
- Il controllo dei permessi deve stare anche in Vikunja; indicazioni nel prompt
  e annotazioni `readOnlyHint` non sostituiscono l'autorizzazione del backend.
- Non ci sono porte pubblicate, socket Docker, volumi NAS o privilegi nel
  container. L'amministratore host/Docker può comunque leggere i segreti montati.
  Il tunnel non applica un filtro di rete in uscita: eventuali restrizioni si
  configurano sul firewall del proprio ambiente.

L'architettura è adatta a un'integrazione **privata**. Il repository può essere
pubblicato open source dopo revisione; questo è distinto dalla distribuzione di
un plugin pubblico ChatGPT. Secure MCP Tunnel non soddisfa i requisiti per la
pubblicazione di plugin pubblici, che richiedono un endpoint HTTPS pubblico stabile.
Non vengono pubblicati automaticamente repository, immagini o plugin.
