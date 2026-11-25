"""Scheda per verificare a mano i fatti pubblicati: per ogni fatto delle vie scelte, gli articoli, gli episodi estratti
dal modello e i passaggi del testo che nominano la via. Solo in locale: l'uscita contiene link e pezzi di testo e va in
valutazione/dati/.

Uso: python -I valutazione/scheda_verifica.py valutazione/dati/ notizie.json uscita.md [fatti minimi per via]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from episodi_anteprima import COPPIE  # noqa: E402

FINESTRA = 350


def chiavi(via):
    if via.endswith(' FS'):
        return ['stazione', ' fs']
    nome = re.sub(r"^(Via|Viale|Piazza|Piazzale|Corso|Largo|Vicolo|Giardini del|Parco)\s+", '', via)
    return [nome.lower(), nome.split()[-1].lower()]


def passaggi(testo, via):
    basso = testo.lower().replace('’', "'")
    for chiave in chiavi(via):
        punti = [m.start() for m in re.finditer(re.escape(chiave), basso)]
        if punti:
            break
    out, fine = [], -1
    for p in punti:
        if p < fine:
            continue
        da, a = max(0, p - FINESTRA), min(len(testo), p + FINESTRA)
        out.append(testo[da:a].replace('\n', ' '))
        fine = a
        if len(out) == 3:
            break
    return out


def main(dati, notizie, uscita, minimo=3):
    testi, risposte = {}, {}
    for t, r in COPPIE:
        if not (dati / f'{t}.jsonl').exists() or not (dati / f'{r}.jsonl').exists():
            continue
        per_id = {}
        for a in map(json.loads, open(dati / f'{t}.jsonl', encoding='utf-8')):
            per_id[a['id']] = a
            if a.get('testo'):
                testi.setdefault(a['url'], a)
        for x in map(json.loads, open(dati / f'{r}.jsonl', encoding='utf-8')):
            if x['id'] in per_id:
                risposte.setdefault(per_id[x['id']]['url'], x)

    fatti = json.load(open(notizie, encoding='utf-8'))['fatti']
    conta = Counter(f['via'] for f in fatti)
    vie = [v for v, n in conta.most_common() if n >= minimo]
    n = 0
    with open(uscita, 'w', encoding='utf-8', newline='\n') as f:
        for via in vie:
            f.write(f'\n# {via} ({conta[via]} fatti)\n')
            for fatto in sorted((x for x in fatti if x['via'] == via), key=lambda x: x['data']):
                n += 1
                f.write(f"\n## F{n:03d} {fatto['data']} {fatto['tipo']} ({len(fatto['articoli'])} articoli)\n")
                for art in fatto['articoli']:
                    a = testi.get(art['url'], {})
                    r = risposte.get(art['url'], {})
                    f.write(f"\n- {art['fonte']} {art['data']} | {a.get('titolo', '?')}\n  {art['url']}\n")
                    for e in ((r.get('estrazione') or {}).get('risposta') or {}).get('episodi', []):
                        f.write(f"  - estratto: {e['categoria']} {e['data']} {e['via']} luogo={e['luogo']} "
                                f"incrocio={e['incrocio']} seguito={e['seguito']}\n")
                    for p in passaggi(a.get('testo', ''), via):
                        f.write(f'  > {p}\n')
    print(f'{n} fatti di {len(vie)} vie in {uscita}')


if __name__ == '__main__':
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 3)
