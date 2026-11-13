# Osservatorio civico Busto Arsizio

Sito statico su GitHub Pages (https://f041.github.io/osservatorio-civico-busto-arsizio/), pubblicato
dal ramo `main`. Due sezioni: Pagamenti (dati dal repo della pipeline, aggiornati da
`update_database_from_release.yml`) e Sicurezza (segnalazioni anonime). Lingua del sito e dei commit: italiano.

## Dove stanno le cose
- Sicurezza: `index.html` (panoramica), `segnala.html` (modulo), `prossimi-passi.html`, `privacy.html`;
  codice in `js/sicurezza.js`, `js/segnala.js`, `js/mappa.js`, elenchi in `js/sicurezza-config.js`.
- Le segnalazioni vanno su Firestore (progetto `osservatorio-civico-busto`, collezione `segnalazioni`),
  protette da `firestore.rules` e da App Check con reCAPTCHA Enterprise.
- Gli elenchi (categorie, fasce, fattori, denuncia) devono coincidere in `firestore.rules`,
  `js/sicurezza-config.js` e `scripts/build_sicurezza.py`. Se ne cambi uno, cambiali tutti.
- `scripts/build_sicurezza.py` (workflow `sicurezza.yml`, ogni notte) calcola `data/sicurezza.json`:
  ultimi 90 giorni, soglia 3, soppressione dei numeri ricavabili per sottrazione, cancellazione dopo 12 mesi.
- Mappa: griglia di quadrati di circa 250 m (`rRRcCC`), disegnata da `data/mappa.json`
  (`scripts/build_mappa.py`, dati OpenStreetMap), Leaflet in `vendor/leaflet`, nessun server di mappe esterno.
- Notizie: `scripts/raccogli_notizie.py` (workflow `notizie.yml`, ogni 2 ore) scrive `articoli.jsonl`
  sul ramo `notizie`, non su main.

## Regole fisse
- Mai salvare in locale, mostrare in chat o committare segreti: chiave segreta di reCAPTCHA, account di servizio,
  chiavi API. I secret di GitHub li crea l'utente.
- Se un'azione viene bloccata (deploy Firebase, chiavi, permessi IAM, repo pubblici), non aggirarla:
  dai all'utente il comando da lanciare.
- Non pubblicare contatti, numeri o dettagli che non hai trovato in una fonte ufficiale. Se non sono verificati, scrivilo.
- I segnaposto dell'informativa (titolare, contatti, base giuridica) restano com'erano: li decide il gruppo.
- Le operazioni sui dati veri (cancellare segnalazioni, ripubblicare i conteggi) sono in `GESTIONE-SICUREZZA.md`,
  solo in locale. Prima di cancellare, elenca e mostra i documenti; dopo, verifica che non esistano più
  (una DELETE su un id inesistente risponde comunque 200).
- Niente spese (Strix, crediti, API a pagamento) senza il sì esplicito dell'utente.

## Testi e interfaccia
- Testi del sito: usa la skill antislop-copywriting. Niente formule, passivi senza soggetto, trattini lunghi,
  né dettagli senza fonte.
- Interfaccia e mappe: usa ux-heuristics; per colori e grafici dataviz, con `validate_palette.js`.
- Controlla il risultato con screenshot a 1280 px e 390 px prima di dire che è fatto.

## Verifiche
- Regole Firestore: `firebase emulators:exec --only firestore --project demo-osservatorio "node tests/regole/regole.test.mjs firestore.rules"`
  (Java in `D:\Users\Gabriele\tools\jdk-21.0.12.1+1-jre\bin`; dipendenze con `npm install` in `tests/regole`).
  Aggiungi una prova per ogni regola nuova.
- Python: `uv run --no-project --python 3.12 python -I ...`, con `--with pacchetto` se serve.
- I file del repo hanno fine riga CRLF: quando li modifichi con uno script, conservali.

## GitHub
- Le Actions committano su main ogni notte: fai `git pull --rebase` prima di ogni push.
- Se la pubblicazione fallisce con "in progress deployment", aspetta che si sblocchi prima di rilanciare.
  A novembre 2026 GitHub registrava run e deploy un'ora avanti, e il blocco è durato un'ora.

## Lavoro delegato
- Il lavoro meccanico e ripetitivo va al sottoagente `osservatorio-helper` (Haiku): scaricare e contare i feed,
  lanciare script e prove, controllare le Actions, fare screenshot, elencare le segnalazioni in sola lettura.
- Nella sessione principale restano: progetto del codice, testi del sito, decisioni su privacy e dati,
  cancellazioni, cosa conta come segnalazione, revisione di quello che riporta il sottoagente.
- Il passaggio di consegne deve bastare da solo: comandi, percorsi, cosa non toccare, formato del rapporto.
  Per compiti brevi non serve: ogni sottoagente parte da zero.

## Segnalazioni dalle notizie (in costruzione)
Decisioni prese con l'utente a novembre 2026:
- Fonti: ilBustese, Malpensa24, Prealpina, VareseNews. Raccolta ogni 2 ore, analisi una volta al giorno.
- Analisi in due passi: selezione da titolo e riassunto, poi estrazione dal testo completo nello schema delle
  segnalazioni (categoria, data dell'episodio, fascia, via o luogo, fattori, seguito di un fatto già noto).
  Solo episodi nello spazio pubblico del comune di Busto (la sezione di Prealpina comprende la Valle Olona).
- Via e luoghi diventano quadrati con `data/mappa.json`, senza geocoder esterni.
- Conciliazione tra fonti: stesso episodio se vicino per giorno, quadrato e tipo; si uniscono i campi e i link.
- Categorie: escluse truffe, violenza domestica e incidenti stradali; spaccio come categoria solo per le notizie.
- Mappa: le notizie sono un livello separato, spento all'inizio, disegnato con un altro stile. I conteggi
  delle due fonti non si sommano mai.
- Revisione umana: gli episodi nuovi arrivano in una pull request, pubblicati solo dopo l'approvazione.
- Dati personali: mai nomi o età, solo i campi dello schema e il link; cancellazione dopo 12 mesi.
  Link agli articoli solo nella vista del singolo quadrato, con almeno 3 episodi. Soglia 3 anche per le notizie.
- Diritto d'autore: il testo serve solo a estrarre i fatti, non si ripubblica né si conserva.
- Prima del via: due settimane di articoli, circa 100 classificati a mano con l'utente, e misura di episodi
  trovati e inventati. Sullo stesso campione si confrontano i modelli: Claude via API (gira nelle Actions,
  costa pochi dollari al mese) e Gemma 4 in locale sul PC dell'utente (gratis, ma serve il PC acceso).
- La nuova fonte va spiegata in "Come funziona e privacy".
