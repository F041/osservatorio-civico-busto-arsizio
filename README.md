# Raccolta notizie

Articoli di Busto Arsizio raccolti ogni 2 ore da ilBustese, Malpensa24, Prealpina e VareseNews
(`scripts/raccogli_notizie.py` sul ramo `main`, workflow `notizie.yml`).

`articoli.jsonl` ha una riga per articolo: fonte, link, titolo, riassunto, data di pubblicazione, categorie della
testata e momento in cui è stato visto la prima volta. Il testo degli articoli non viene salvato.
Le righe più vecchie di 12 mesi vengono cancellate.

Questo ramo non viene pubblicato sul sito: serve al passo di analisi, che decide quali articoli
raccontano un episodio da segnalare.
