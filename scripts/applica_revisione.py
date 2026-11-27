"""Applica una revisione inviata da revisione.html come issue su GitHub (.github/workflows/revisione.yml).

Uso: python scripts/applica_revisione.py corpo_issue.txt notizie.json revisione/notizie.tsv

Il corpo ha due righe: `controllati: id id …` e `sbagliati: id id …`. I fatti controllati entrano nel file con esito
`ok`, quelli sbagliati con `no` (anche se c'erano già con `ok`); build_notizie.py toglie i `no` alla pubblicazione.
Giorno, tipo e via vengono da notizie.json, il file pubblicato sul sito. Nel tsv mai i link: contengono i titoli.
Stampa una riga di riepilogo per il commento sulla issue.
"""
import csv
import json
import re
import sys
from pathlib import Path

CAMPI = ['id', 'esito', 'data', 'tipo', 'via']
ID = re.compile(r'^[0-9a-f]{12}$')


def ids(corpo, etichetta):
    riga = re.search(rf'^{etichetta}:(.*)$', corpo, re.M)
    return [i for i in (riga.group(1).split() if riga else []) if ID.match(i)]


def main(corpo, notizie, tsv):
    testo = Path(corpo).read_text(encoding='utf-8')
    controllati, sbagliati = ids(testo, 'controllati'), set(ids(testo, 'sbagliati'))
    if not controllati and not sbagliati:
        sys.exit('Nessun id valido nella issue')
    fatti = {f['id']: f for f in json.load(open(notizie, encoding='utf-8'))['fatti']}

    righe = {}
    if Path(tsv).exists():
        with open(tsv, encoding='utf-8', newline='') as f:
            righe = {r['id']: r for r in csv.DictReader(f, delimiter='\t')}
    nuovi = 0
    for i in dict.fromkeys([*controllati, *sbagliati]):
        esito = 'no' if i in sbagliati else 'ok'
        if i in righe:
            if esito == 'no':
                righe[i]['esito'] = 'no'
            continue
        f = fatti.get(i, {})
        righe[i] = {'id': i, 'esito': esito, 'data': f.get('data', ''), 'tipo': f.get('tipo', ''), 'via': f.get('via', '')}
        nuovi += 1

    Path(tsv).parent.mkdir(exist_ok=True)
    with open(tsv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, CAMPI, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        w.writeheader()
        w.writerows(sorted(righe.values(), key=lambda r: (r['data'], r['id'])))
    t = len(sbagliati)
    print(f"{nuovi} {'fatto controllato' if nuovi == 1 else 'fatti controllati'}, "
          f"{t} {'tolto' if t == 1 else 'tolti'} dalla mappa")


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
