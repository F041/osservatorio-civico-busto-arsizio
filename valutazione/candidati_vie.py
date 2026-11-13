"""Nuovi candidati per la prova: articoli dello storico non ancora etichettati che passano il filtro delle vie e
parlano di cronaca.

Uso: uv run --no-project --python 3.12 python -I valutazione/candidati_vie.py

Legge valutazione/dati/testi-resto.jsonl (prepara_campione.py ... resto) e scrive campione-vie.jsonl con id c001...
La lista di parole è più larga di quella del campione arricchito: comprende furti in casa e lamentele dei residenti.
Si cerca in titolo, riassunto e testo pulito.
"""
import json
import re
import sys
from pathlib import Path

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI.parent / 'scripts'))
from vie_busto import Stradario  # noqa: E402

DATI = QUI / 'dati'
CRONACA = re.compile(
    r'furt|ladr|rapin|scipp|borseg|svaligi|scasso|effrazion|intrus|appartament[oi] (?:visitat|svaligiat)|'
    r'aggre|rissa|risse|picchiat|pestagg|minacc|coltell|accoltell|molest|osceni|'
    r'spacci|droga|cocain|hashish|eroina|pusher|stupefacent|'
    r'vandal|danneg|imbratt|degrado|incivilt|bivacc|schiamazz|baby gang|maranza|insicurezz|esasperat|'
    r'arrest|denunciat|fermat[oi] dall?a? polizia', re.I)


def main():
    s = Stradario()
    articoli = [json.loads(r) for r in open(DATI / 'testi-resto.jsonl', encoding='utf-8') if r.strip()]
    scelti = []
    for a in articoli:
        pulito, vie = s.filtro(a)
        if vie and CRONACA.search(f"{a['titolo']} {a.get('sommario', '')} {pulito}"):
            scelti.append(a)
    with open(DATI / 'campione-vie.jsonl', 'w', encoding='utf-8', newline='\n') as f:
        for n, a in enumerate(scelti, 1):
            riga = {**a, 'id': f'c{n:03d}', 'id_resto': a['id']}
            f.write(json.dumps(riga, ensure_ascii=False) + '\n')
            print(f"{riga['id']} {a['fonte']:10} {a['titolo'][:90]}")
    passati = sum(bool(s.filtro(a)[1]) for a in articoli)
    print(f'{len(articoli)} articoli, {passati} passano il filtro delle vie, {len(scelti)} anche con parole di cronaca')


if __name__ == '__main__':
    main()
