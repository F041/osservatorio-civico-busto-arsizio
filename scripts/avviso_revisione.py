"""Testo della issue che avvisa dei fatti dalle notizie ancora da controllare (.github/workflows/pubblica.yml).

Uso: python scripts/avviso_revisione.py data/notizie.json revisione/notizie.tsv corpo.md

Stampa quanti fatti del sito non sono ancora in revisione/notizie.tsv. La revisione è a posteriori (decisione
dell'utente del 27/11/2026): i fatti sono già sulla mappa e si controllano da revisione.html.
"""
import csv
import json
import sys
from pathlib import Path

SITO = 'https://f041.github.io/osservatorio-civico-busto-arsizio/'


def main(notizie, tsv, corpo):
    visti = set()
    if Path(tsv).exists():
        with open(tsv, encoding='utf-8', newline='') as f:
            visti = {r['id'] for r in csv.DictReader(f, delimiter='\t')}
    n = sum(f['id'] not in visti for f in json.load(open(notizie, encoding='utf-8'))['fatti'])
    Path(corpo).write_text('\n'.join([
        f'Ci sono {n} fatti dalle notizie da controllare. Sono già sulla mappa.',
        '',
        f'Apri la [pagina di revisione]({SITO}revisione.html), spunta quelli sbagliati e premi «Invia la revisione».',
        '',
        'Questa issue si chiude da sola quando li hai controllati tutti.',
        '',
        f'<!-- da-controllare: {n} -->',
    ]) + '\n', encoding='utf-8')
    print(n)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
