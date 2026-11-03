# Sviluppo e test

## Sviluppo e verifiche ripetibili

```sh
docker compose --env-file .env.example config --quiet
python3 -m unittest discover -s tests -p 'test_*.py' -v
docker compose pull
python3 tests/integration.py
```

I test richiedono Python, OpenSSL e, per l'integrazione, Docker su Linux. Creano
certificati e credenziali **fittizi**, server HTTPS su loopback e un progetto
Compose temporaneo con nome casuale. L'override di test usa la rete host soltanto
per raggiungere le fixture loopback; il deployment normale usa la rete Docker.
Non caricano `.env` o secrets reali, non contattano OpenAI/Vikunja reali e rimuovono
i container di prova alla fine. Non eseguire contemporaneamente più copie del
test sulla stessa macchina.

Il test verifica il vero client dell'immagine fissata, l'header letto da file,
`initialize`, una richiesta `tools/list` proveniente dal control plane simulato,
la precedenza dell'header inoltrato, gli errori 401, la separazione delle chiavi,
assenza delle credenziali fittizie nei log, TLS, riavvio e ricreazione da file.
Non simula una sessione utente ChatGPT né costituisce un collaudo sui dati reali.

Per versionare su Forgejo: creare un repository indipendente e revisionare i
file prima del primo commit. `.gitignore` esclude tutti i file privati noti;
verificare comunque con `git status --short` e `git diff --cached`. Non usare
`git add -f` sui file locali. Nessun remote o push viene configurato automaticamente.
