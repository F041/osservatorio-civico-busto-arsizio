"""Applica una revisione inviata da revisione.html come issue su GitHub (.github/workflows/revisione.yml).

Uso: python scripts/applica_revisione.py corpo_issue.txt notizie.json revisione/notizie.tsv

Il corpo ha quattro righe: `controllati: id id …`, `sbagliati: id id …`, `tipo: id=categoria …` (o
`id=categoria:sottotipo`) e `sottotipo: id=sottotipo …`. I fatti controllati entrano nel file con esito `ok`, quelli
sbagliati con `no` (anche se c'erano già con `ok`), quelli col tipo sbagliato con esito `ok` e il tipo giusto nella
colonna tipo_giusto. La riga sottotipo conferma o corregge il sottotipo dei furti e dei vandalismi (colonna
sottotipo_giusto; `nessuno` se non ne hanno). build_notizie.py toglie i `no` e corregge tipi e sottotipi.
Giorno, tipo e via vengono da notizie.json, il file pubblicato sul sito. Nel tsv mai i link: contengono i titoli.
Stampa una riga di riepilogo per il commento sulla issue.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_notizie import NESSUNO, SOTTOTIPI, TIPI  # noqa: E402

CAMPI = ['id', 'esito', 'data', 'tipo', 'via', 'tipo_giusto', 'sottotipo_giusto']
ID = re.compile(r'^[0-9a-f]{12}$')


def coppie(corpo, etichetta):
    riga = re.search(rf'^{etichetta}:(.*)$', corpo, re.M)
    return [c.split('=', 1) for c in (riga.group(1).split() if riga else []) if '=' in c and ID.match(c.split('=', 1)[0])]


def tipi(corpo):
    """{id: (tipo, sottotipo o None)} dalla riga `tipo:`; `furto:casa` dà anche il sottotipo."""
    out = {}
    for i, valore in coppie(corpo, 'tipo'):
        tipo, _, sottotipo = valore.partition(':')
        if tipo in TIPI and (not sottotipo or sottotipo in (*SOTTOTIPI.get(tipo, ()), NESSUNO)):
            out[i] = (tipo, sottotipo or None)
    return out


def sottotipi(corpo):
    validi = {NESSUNO, *(s for v in SOTTOTIPI.values() for s in v)}
    return {i: s for i, s in coppie(corpo, 'sottotipo') if s in validi}


def ids(corpo, etichetta):
    riga = re.search(rf'^{etichetta}:(.*)$', corpo, re.M)
    return [i for i in (riga.group(1).split() if riga else []) if ID.match(i)]


def main(corpo, notizie, tsv):
    testo = Path(corpo).read_text(encoding='utf-8')
    controllati, sbagliati, corretti = ids(testo, 'controllati'), set(ids(testo, 'sbagliati')), tipi(testo)
    confermati = sottotipi(testo)
    if not controllati and not sbagliati and not corretti and not confermati:
        sys.exit('Nessun id valido nella issue')
    fatti = {f['id']: f for f in json.load(open(notizie, encoding='utf-8'))['fatti']}

    righe = {}
    if Path(tsv).exists():
        with open(tsv, encoding='utf-8', newline='') as f:
            righe = {r['id']: r for r in csv.DictReader(f, delimiter='\t')}
    nuovi = 0
    for i in dict.fromkeys([*controllati, *sbagliati, *corretti, *confermati]):
        if i not in righe:
            f = fatti.get(i, {})
            righe[i] = {'id': i, 'esito': 'ok', 'data': f.get('data', ''), 'tipo': f.get('tipo', ''), 'via': f.get('via', '')}
            nuovi += 1
        if i in sbagliati:
            righe[i]['esito'] = 'no'
        elif i in corretti:
            righe[i]['esito'] = 'ok'
            tipo, sottotipo = corretti[i]
            righe[i]['tipo_giusto'] = tipo
            # Senza sottotipo scelto, un furto o un vandalismo torna da controllare (build_notizie.da_controllare)
            righe[i]['sottotipo_giusto'] = sottotipo or ''
        if i in confermati and i not in sbagliati and i not in corretti:
            righe[i]['sottotipo_giusto'] = confermati[i]

    Path(tsv).parent.mkdir(exist_ok=True)
    with open(tsv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, CAMPI, delimiter='\t', lineterminator='\n', extrasaction='ignore')
        w.writeheader()
        w.writerows(sorted(righe.values(), key=lambda r: (r['data'], r['id'])))
    t, c, st = len(sbagliati), len(set(corretti) - sbagliati), len(set(confermati) - sbagliati - set(corretti))
    print(f"{nuovi} {'fatto controllato' if nuovi == 1 else 'fatti controllati'}, "
          f"{t} {'tolto' if t == 1 else 'tolti'} dalla mappa, {c} con il tipo corretto, "
          f"{st} {'sottotipo controllato' if st == 1 else 'sottotipi controllati'}")


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
