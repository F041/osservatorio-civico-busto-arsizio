"""Testo della issue che avvisa dei fatti dalle notizie ancora da controllare (.github/workflows/pubblica.yml).

Uso: python scripts/avviso_revisione.py data/notizie.json revisione/notizie.tsv corpo.md

Stampa quanti fatti del sito sono ancora da controllare (build_notizie.da_controllare). La revisione è a posteriori (decisione
dell'utente del 27/11/2026): i fatti sono già sulla mappa e si controllano da revisione.html.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_notizie import da_controllare, revisione  # noqa: E402

SITO = 'https://f041.github.io/osservatorio-civico-busto-arsizio/'


def main(notizie, tsv, corpo):
    esiti = revisione(tsv)
    n = sum(da_controllare(f, esiti) for f in json.load(open(notizie, encoding='utf-8'))['fatti'])
    Path(corpo).write_text('\n'.join([
        f'Ci sono {n} fatti dalle notizie da controllare. Sono già sulla mappa.',
        '',
        f'Apri la [pagina di revisione]({SITO}revisione.html), decidi fatto per fatto e premi «Invia».',
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
