"""Campione per la prova del motore delle notizie: sceglie gli articoli e ne scarica il testo, solo in locale.

Uso: uv run --no-project --python 3.12 --with trafilatura python -I valutazione/prepara_campione.py articoli.jsonl [n]
     ... prepara_campione.py articoli.jsonl arricchito
     ... prepara_campione.py articoli.jsonl resto

Campione a caso: metà dalla cronaca di ilBustese, dove gli episodi sono più frequenti, metà a caso dalle altre
testate, in parti uguali. Il seme è fisso, così il campione si può rifare uguale.
Campione arricchito: tutti gli articoli che nominano Busto (o un suo quartiere) e una parola di cronaca nel titolo,
nel riassunto o nel link, esclusi quelli già nel campione a caso. Serve ad avere abbastanza episodi veri e fatti
raccontati da più testate; non misura la frequenza degli episodi.
Resto: tutti gli altri articoli, per cercarvi nuovi candidati con il filtro delle vie (valutazione/candidati_vie.py).
I testi finiscono in valutazione/dati/, esclusa da git: servono solo alla prova e poi si cancellano.
"""
import json
import random
import re
import sys
import time
from pathlib import Path

import trafilatura

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from raccogli_notizie import scarica  # noqa: E402

SEME = 20261113
DATI = Path(__file__).parent / 'dati'
PAUSA = 1.5
CRONACA = re.compile(r'furt|ladr|rapin|scipp|borseg|aggre|rissa|minacc|coltell|spacci|droga|cocain|hashish|pusher|'
                     r'vandal|danneg|degrado|molest|baby gang|maranza|arrest|denunc|sicurezza|polizia|carabinier|'
                     r'incendi', re.I)
BUSTO = re.compile(r'busto|sacconago|borsano|beata giuliana|sant.anna|redentore|veroncora', re.I)


def a_caso(articoli, n):
    cronaca = [a for a in articoli if a['fonte'] == 'ilbustese' and '/argomenti/cronaca-26/' in a['url']]
    altre = {f: [a for a in articoli if a['fonte'] == f] for f in ('malpensa24', 'prealpina', 'varesenews')}
    caso = random.Random(SEME)
    scelti = caso.sample(cronaca, n // 2)
    resto = n - len(scelti)
    for i, (fonte, gruppo) in enumerate(altre.items()):
        quanti = resto // 3 + (1 if i < resto % 3 else 0)
        scelti += caso.sample(gruppo, quanti)
    return scelti


def gia_scelti(*nomi):
    return {json.loads(r)['url'] for n in nomi if (DATI / n).exists() for r in open(DATI / n, encoding='utf-8') if r.strip()}


def arricchito(articoli):
    gia = gia_scelti('campione.jsonl')
    return [a for a in articoli if a['url'] not in gia
            and CRONACA.search(f"{a['titolo']} {a['sommario']}") and BUSTO.search(f"{a['titolo']} {a['sommario']} {a['url']}")]


def main(percorso, quale='80'):
    articoli = [json.loads(r) for r in open(percorso, encoding='utf-8') if r.strip()]
    if quale == 'arricchito':
        scelti, uscita, prefisso = arricchito(articoli), DATI / 'campione-arricchito.jsonl', 'b'
    elif quale == 'resto':
        gia = gia_scelti('campione.jsonl', 'campione-arricchito.jsonl')
        scelti, uscita, prefisso = [a for a in articoli if a['url'] not in gia], DATI / 'testi-resto.jsonl', 'r'
    else:
        scelti, uscita, prefisso = a_caso(articoli, int(quale)), DATI / 'campione.jsonl', 'a'
    DATI.mkdir(exist_ok=True)
    with open(uscita, 'w', encoding='utf-8', newline='\n') as f:
        for i, a in enumerate(scelti, 1):
            try:
                pagina = scarica(a['url']).decode('utf-8', errors='replace')
                testo = trafilatura.extract(pagina, include_comments=False, include_tables=False) or ''
                meta = trafilatura.extract_metadata(pagina)
                titolo = (meta.title if meta and meta.title else a['titolo'])
            except Exception as err:
                print(f'::warning::{a["url"]}: {err}')
                testo, titolo = '', a['titolo']
            riga = {'id': f'{prefisso}{i:03d}', **a, 'titolo': titolo, 'testo': testo}
            f.write(json.dumps(riga, ensure_ascii=False) + '\n')
            print(f'{riga["id"]} {a["fonte"]:10} {len(testo.split()):5} parole  {titolo[:70]}')
            time.sleep(PAUSA)
    print(f'Salvato {uscita}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '80')
