"""Nomi dei quartieri di Busto Arsizio per la mappa, da OpenStreetMap.

Uso: python scripts/build_quartieri.py data/quartieri.json   (serve shapely, come build_mappa.py; si rilancia a mano)

OpenStreetMap ha solo il punto di ogni quartiere (place=suburb o neighbourhood), non i confini (verificato il
25/11/2026): la mappa mostra i nomi e nessun confine, per non far sembrare ufficiali dei confini stimati.
Coordinate nello stesso formato di data/mappa.json. Dati © OpenStreetMap contributors, licenza ODbL.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_mappa import AREA, flat, overpass  # noqa: E402


def main(out_path):
    els = overpass(f'[out:json][timeout:120];{AREA}node(area.a)["place"~"^(suburb|neighbourhood)$"]["name"];out;')
    quartieri = sorted(({'n': e['tags']['name'], 'p': flat([(e['lon'], e['lat'])]),
                         'tipo': e['tags']['place']} for e in els), key=lambda q: q['n'])
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'fonte': 'OpenStreetMap (ODbL)', 'quartieri': quartieri}, f, ensure_ascii=False, indent=1)
    print(f'Scritto {out_path}: {len(quartieri)} quartieri')


if __name__ == '__main__':
    main(sys.argv[1])
