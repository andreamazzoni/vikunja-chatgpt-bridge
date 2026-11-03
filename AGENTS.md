# Principi del progetto

- Allineare struttura, guida operativa e CLI al bridge TrueNAS, adattandole al
  server MCP integrato di Vikunja e all'immagine ufficiale di tunnel-client.
- Usare Docker Compose e immagini fissate per versione e digest. Tenere
  verificato il supporto ARM64 e AMD64.
- Conservare configurazione privata, segreti e stato locale fuori da Git.
  Usare input nascosto e mount dei segreti in sola lettura.
- Mantenere TLS verificato, container non root e diagnostica su loopback.
- Distinguere stato del container, probe MCP e collaudo dall'app ChatGPT.
- Usare fixture isolate per i test. Le chiamate di scrittura su dati reali
  richiedono una richiesta esplicita.
- Pubblicare il sorgente sul Forgejo indicato dall'operatore.
