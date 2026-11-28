# Osservatorio civico Busto Arsizio

Sito statico su GitHub Pages (https://f041.github.io/osservatorio-civico-busto-arsizio/), pubblicato
dal ramo `main`. Tre sezioni: Sicurezza (segnalazioni anonime), Pagamenti (dati dal repo della pipeline, aggiornati da
`update_database_from_release.yml`) e Popolazione (residenti stimati per gruppo di quartieri). Lingua del sito e dei commit: italiano.

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
- Notizie: `scripts/raccogli_notizie.py` (workflow `notizie.yml`, ogni giorno alle 4:41 UTC) scrive
  nella collezione Firestore `notizie_articoli`, chiusa al sito: solo testata, link e date. Mai nel repo, che è
  pubblico: i link contengono i titoli, con nomi di persone. Ogni elenco letto deve coprire più di un giorno.

- Popolazione: `popolazione.html`, `js/popolazione.js`, dati in `data/popolazione.json` da `scripts/build_popolazione.py`
  (elettori per sezione dai file XML dell'Ufficio elettorale, residenti dal servizio del bilancio mensile ISTAT, tutto
  scaricato a ogni esecuzione). Dati pubblici e aggregati: stanno nel repo, non su Firestore, così git ne tiene la storia.
  Metodo e attribuzioni delle scuole ai gruppi vengono dal foglio dell'utente (novembre 2026); le due "secondo la
  traccia" restano così per sua decisione. Confini dei quartieri: il Comune non li pubblica; le zone OMI dell'Agenzia
  delle Entrate sono fasce di mercato (centro, semicentro, periferia), non quartieri; quelle di immobiliare.it sono di un
  portale commerciale e non si riusano.

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
- Se cambiano i campi di uno script `build_*`, aggiorna lo schema in `data/schemi/` e il dizionario in `dati-aperti.html`.
- Dati del sito: licenza CC BY 4.0 (`data/mappa.json` resta ODbL, da OpenStreetMap). Il codice è MIT.
- Contatti: niente email sul sito (spam). Le segnalazioni passano dalle issue di GitHub.

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
- Fonti: ilBustese, Malpensa24, Prealpina, VareseNews. Raccolta e analisi una volta al giorno.
- Analisi in due passi: filtro delle vie (`scripts/vie_busto.py`: l'articolo nomina Busto o un quartiere e almeno
  una via o un luogo dello stradario di `data/mappa.json`), poi estrazione col modello dal testo completo nello
  schema delle segnalazioni (categoria, data dell'episodio, fascia, via o luogo, fattori, seguito di un fatto già
  noto). La via può essere solo una di quelle trovate dal filtro; da lì i quadrati, senza geocoder esterni.
  Un episodio senza via o luogo sulla mappa si scarta (i quartieri sono troppo generici). Se un luogo noto si perde
  al filtro, si aggiungono i suoi sinonimi in `vie_busto.py` (es. "pronto soccorso di Busto" per l'ospedale), non un
  modello in più: la comprensione del testo la fa già il passo col modello.
- Solo episodi nel comune di Busto (la sezione di Prealpina comprende la Valle Olona), in spazi pubblici o aperti
  al pubblico, compresi i bar. Contano anche i furti in casa; il resto di quello che succede in casa no.
- Conciliazione tra fonti: stesso episodio se vicino per giorno, quadrato e tipo; si uniscono i campi e i link.
  Prima si tolgono le copie dello stesso articolo con link diversi. Nello stesso articolo, stesso tipo e stessa via a
  un giorno di distanza sono un episodio solo. Se una via ha 6 o più quadrati, due vie diverse si uniscono solo nello stesso giorno.
- Categorie: escluse truffe, violenza domestica, incidenti stradali, allarmi bomba via mail, inseguimenti senza un altro reato, crolli, suicidi, restauri e fatti dentro il carcere. Solo per le notizie:
  spaccio; insicurezza per le lamentele ricorrenti su una via senza un fatto datato. Furti ripetuti nello stesso
  posto senza date sono un episodio solo. Un processo per un fatto vecchio è un seguito. Dalla verifica dei fatti
  del 25/11/2026: esclusi ricordi di anni prima, danni lasciati da mercati ed eventi, volantini e proteste politiche,
  auto in fiamme senza dolo, elenchi di luoghi letti in consiglio; i fatti sul treno contano solo se avvenuti in
  stazione o col treno fermo a Busto (decisione dell'utente); commenti e reazioni a un fatto già raccontato sono seguiti.
  I rifiuti abbandonati restano in "Vandalismo o degrado" (decisione dell'utente del 25/11/2026). Categoria
  "Allagamento" solo per le notizie (sottopassi, strade o piazze allagate con pericolo o disagi); gli altri danni del
  maltempo, le buche e i guasti no. Sulla mappa si separano dai reati col filtro "Mostra": "Tutti" li esclude e
  si vedono solo scegliendo "Allagamento" (decisione dell'utente del 26/11/2026). Nel dettaglio di una via e sulle icone
  compaiono tutti i tipi, anche con un fatto solo (stessa data).
- Mappa: selettore "Fonte" con due viste, una alla volta e mai sovrapposte. Segnalazioni (predefinita) con i quadrati,
  Notizie (`js/notizie.js`, `?vista=notizie`) con vie evidenziate e un punto per parchi e stazioni. Senza
  `data/notizie.json` il selettore non compare. I conteggi delle due fonti non si sommano mai.
- Quartieri: `scripts/build_quartieri.py` scrive `data/quartieri.json` da OpenStreetMap, che ha solo i punti (i confini
  mancano, verificato il 25/11/2026). La mappa mostra i nomi, mai confini stimati. Icone dei tipi: Lucide (ISC), nel filtro, nelle tabelle e
  sulla mappa (una per tipo, affiancate sulla stessa via; quelle che si accavallano si nascondono, prima le vie con più fatti).
- Dati della vista: `scripts/conciliazione.py` unisce gli episodi, `scripts/build_notizie.py` scrive i fatti
  (via, giorno, tipo, link) degli ultimi 24 mesi, quanti ne tiene la raccolta (CONSERVAZIONE_GIORNI in raccogli_notizie.py). Il navigatore del periodo sotto la
  mappa (1 mese, 3 mesi, 6 mesi, Tutto, o maniglie trascinabili) conta le vie nel browser. Che i singoli fatti
  siano leggibili nel file, sotto la soglia, va bene (decisione dell'utente del 25/11/2026). `data/notizie.json` non va mai nel
  repo: si genera durante la pubblicazione del sito (decisione del 24/11/2026), così i link spariscono davvero
  quando scadono. Pubblicazione: `.github/workflows/pubblica.yml` (GitHub Pages da Actions, non più dal ramo) legge gli
  episodi dalla collezione Firestore `notizie_episodi` (solo gli articoli con almeno un episodio, circa 500 letture) e
  costruisce il file. Gli episodi li carica dal PC `scripts/episodi_notizie.py carica`, perché l'analisi gira sul PC.
- Storico: ilBustese rallenta di proposito le richieste in blocco (circa 30 secondi per pagina degli articoli e
  dell'archivio; feed e mappa del sito no). Non fingersi un browser: si scarica da solo, a parte e con calma.
  Prealpina: le mappe del sito più vecchie non hanno date, si leggono dalla pagina dell'articolo.
- Revisione umana a posteriori (decisione dell'utente del 27/11/2026): i fatti vanno sul sito subito. `pubblica.yml`
  apre una issue "Fatti dalle notizie da controllare" (un commento quando ne arrivano di nuovi, si chiude quando sono
  tutti visti). `revisione.html` (fuori dai menu, noindex) mostra i fatti non ancora in `revisione/notizie.tsv`, con
  riassunto e link; per ogni fatto l'utente sceglie Giusto, Togli o Cambia tipo (nessuna scelta preimpostata, la riga
  sparisce), e "Invia" apre, anche a lotti (decisione dell'utente del 28/11/2026), solo per i fatti decisi
  una issue già scritta. Quando la crea
  il proprietario del repo, `revisione.yml` aggiorna il tsv su main (`scripts/applica_revisione.py`) e ripubblica.
  Il tsv ha solo id, esito, giorno, tipo, via e tipo_giusto, mai i link; `esito = no` toglie il fatto dalla mappa,
  `tipo_giusto` ne cambia il tipo (build_notizie.py, funzione `applica`).
- Riassunti: 2 o 3 frasi per fatto, per la revisione, scritte da Haiku sul PC con `scripts/riassunti_notizie.py` dopo
  `episodi_notizie.py carica`. Stanno nel campo `riassunti` dei documenti di `notizie_episodi` e finiscono in
  data/notizie.json: sono pubblici, quindi mai nomi, età, nazionalità o targhe, e niente frasi copiate dall'articolo.
- Dati personali: mai nomi o età, solo i campi dello schema e il link. Articoli e link si cancellano 24 mesi dopo l'uscita
  (decisione dell'utente del 26/11/2026, scritta in privacy.html; le segnalazioni restano a 12 mesi).
  Link agli articoli solo nel dettaglio della singola via. Soglia 2 per le notizie (decisione dell'utente del
  24/11/2026: fatti pochi e sparsi), 3 per le segnalazioni dei cittadini.
- Diritto d'autore: il testo serve solo a estrarre i fatti, non si ripubblica né si conserva.
- Prima del via: due settimane di articoli, circa 100 classificati a mano con l'utente, e misura di episodi
  trovati e inventati. Sullo stesso campione si confrontano due strade, tutte e due sul PC dell'utente:
  Gemma 4 12B in locale (`C:\Users\GabrieleRig\.android\models\gemma-4-12b`) e Claude da Claude Code
  (`claude -p --json-schema`, con l'abbonamento). L'API a pagamento è esclusa.
- Storico per la prova: `scripts/storico_notizie.py` recupera a mano gli ultimi N giorni dagli archivi delle testate
  nella stessa collezione della raccolta (994 articoli per i 30 giorni fino al 13/11/2026). Copia locale per le
  prove: `python scripts/raccogli_notizie.py --esporta valutazione/dati/articoli.jsonl`.
  Gli ultimi 24 mesi, quanti ne mostra la mappa (dal 26/11/2026; prima solo il 2026, da qui i nomi dei file):
  `bash valutazione/recupero_veloci.sh` per Malpensa24, Prealpina e VareseNews;
  `bash valutazione/riprendi_ilbustese.sh` per ilBustese, che richiede più giorni: si ferma quando si vuole e riparte
  da dove era. Anteprima locale: `valutazione/episodi_anteprima.py`, poi `scripts/build_notizie.py`.
- Firestore è sul piano gratuito: 50.000 letture e 20.000 scritture al giorno, azzerate alle 9 italiane, condivise con
  la raccolta delle 14:28. Il 26/11/2026 il recupero le ha finite e la raccolta è fallita (429 Quota exceeded).
  Un'esportazione completa legge tutta la collezione (oltre 10.000 documenti): farne poche, meglio di una testata sola
  (`storico_2026.py esporta <file> <fonte>`). Il recupero di ilBustese legge al massimo 100 giorni per giro.
- La nuova fonte è spiegata in "Come funziona e privacy" (26/11/2026): se cambia qualcosa, aggiorna anche quel testo.
