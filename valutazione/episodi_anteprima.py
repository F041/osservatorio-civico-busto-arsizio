"""Episodi per l'anteprima locale della mappa: le risposte del modello su tutti i testi scaricati, nel formato che legge
scripts/build_notizie.py. Solo in locale: l'uscita contiene i link e va in valutazione/dati/ o in una cartella temporanea.

Uso: python -I valutazione/episodi_anteprima.py valutazione/dati/ uscita.jsonl
     poi: python -I scripts/build_notizie.py uscita.jsonl <copia del sito>/data/notizie.json
"""
import json
import sys
from pathlib import Path

COPPIE = (('campione', 'risposte-vie-haiku'), ('campione-arricchito', 'risposte-vie-haiku-arricchito'),
          ('testi-resto', 'risposte-vie-haiku-resto'), ('testi-nuovi-unici', 'risposte-vie-haiku-nuovi'),
          ('testi-storico90', 'risposte-vie-haiku-storico90'),
          ('testi-storico150-altre', 'risposte-vie-haiku-storico150-altre'),
          ('testi-storico182-altre', 'risposte-vie-haiku-storico182-altre'),
          ('testi-storico2026-altre', 'risposte-vie-haiku-storico2026-altre'),
          ('testi-storico2026-ilbustese', 'risposte-vie-haiku-storico2026-ilbustese'))


def main(dati, uscita):
    n, visti = 0, set()
    with open(uscita, 'w', encoding='utf-8', newline='\n') as f:
        for testi, risposte in COPPIE:
            # I file del recupero in corso possono mancare o essere a metà
            if not (dati / f'{testi}.jsonl').exists() or not (dati / f'{risposte}.jsonl').exists():
                continue
            articoli = {a['id']: a for a in map(json.loads, open(dati / f'{testi}.jsonl', encoding='utf-8'))}
            for r in map(json.loads, open(dati / f'{risposte}.jsonl', encoding='utf-8')):
                a = articoli.get(r['id'])
                if not a or a['url'] in visti:
                    continue
                visti.add(a['url'])
                episodi = ((r['estrazione'] or {}).get('risposta') or {}).get('episodi', [])
                f.write(json.dumps({'fonte': a['fonte'], 'url': a['url'], 'pubblicato': a.get('pubblicato') or a['visto'],
                                    'episodi': episodi}, ensure_ascii=False) + '\n')
                n += 1
    print(n, 'articoli')


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
