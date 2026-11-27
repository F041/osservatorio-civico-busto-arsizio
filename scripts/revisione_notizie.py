"""Fatti nuovi da rivedere: aggiunge a revisione/notizie.tsv i fatti di data/notizie.json che non ci sono ancora e scrive
il testo della pull request di revisione (.github/workflows/pubblica.yml).

Uso: python scripts/revisione_notizie.py data/notizie.json revisione/notizie.tsv tsv_di_main corpo.md

La revisione è a posteriori (decisione dell'utente del 27/11/2026): i fatti sono già sul sito, chi rivede scrive `no`
nella colonna esito di quelli sbagliati e build_notizie.py li toglie alla pubblicazione successiva.
Nel file vanno solo id, esito, giorno, tipo e via: mai i link, che contengono i titoli e a volte i nomi.
Stampa quanti fatti ha aggiunto; il testo elenca tutti quelli del file che main non ha ancora.
"""
import csv
import json
import sys
from pathlib import Path

CAMPI = ['id', 'esito', 'data', 'tipo', 'via']
SITO = 'https://f041.github.io/osservatorio-civico-busto-arsizio/'


def leggi(percorso):
    if not Path(percorso).exists():
        return []
    with open(percorso, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f, delimiter='\t'))


def main(notizie, tsv, tsv_main, corpo):
    righe = leggi(tsv)
    noti = {r['id'] for r in righe}
    fatti = json.load(open(notizie, encoding='utf-8'))['fatti']
    nuovi = [{'id': f['id'], 'esito': 'ok', 'data': f['data'], 'tipo': f['tipo'], 'via': f['via']}
             for f in fatti if f['id'] not in noti]
    if nuovi:
        righe = sorted(righe + nuovi, key=lambda r: (r['data'], r['id']))
        Path(tsv).parent.mkdir(exist_ok=True)
        with open(tsv, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, CAMPI, delimiter='\t', lineterminator='\n', extrasaction='ignore')
            w.writeheader()
            w.writerows(righe)

    in_main = {r['id'] for r in leggi(tsv_main)}
    da_rivedere = [r for r in righe if r['id'] not in in_main]
    ids = ','.join(r['id'] for r in da_rivedere)
    testo = [
        f'Fatti dalle notizie da controllare: {len(da_rivedere)}. Sono già sulla mappa.',
        '',
        f'1. Apri la [pagina di revisione]({SITO}revisione.html?id={ids}): ha i link agli articoli di ogni fatto.',
        '2. Per ogni fatto sbagliato, in `revisione/notizie.tsv` di questa pull request scrivi `no` al posto di `ok` '
        'nella colonna esito (scheda "Files changed", poi i tre puntini del file e "Edit file").',
        '3. Fai il merge. Alla pubblicazione successiva i fatti segnati `no` spariscono dalla mappa.',
        '',
        'Questa pull request si allunga ogni giorno con i fatti nuovi finché non la chiudi con il merge.',
        '',
        '| Giorno | Tipo | Via o luogo | Id |',
        '|---|---|---|---|',
        *(f"| {r['data']} | {r['tipo']} | {r['via'].replace('|', '/')} | `{r['id']}` |" for r in reversed(da_rivedere)),
    ]
    Path(corpo).write_text('\n'.join(testo) + '\n', encoding='utf-8')
    print(len(nuovi))


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
