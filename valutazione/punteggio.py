"""Confronta le risposte di un modello con le etichette fatte a mano.

Uso: uv run --no-project --python 3.12 python -I valutazione/punteggio.py valutazione/dati/etichette.jsonl \
         valutazione/dati/risposte-haiku.jsonl

Misure:
- per articolo: episodi trovati, persi e inventati, dal solo secondo passo e dai due passi in fila;
- per episodio: ogni episodio etichettato si abbina a quello dato con la stessa categoria e data (se no la stessa
  categoria, se no il primo libero); sulle coppie si contano categoria, data, fascia, via, quadrato e seguito;
- conciliazione: due articoli raccontano lo stesso fatto se hanno episodi dello stesso tipo, a un giorno al massimo
  di distanza, in quadrati uguali o vicini (la regola decisa per la pipeline). Si confronta con le etichette.
"""
import json
import re
import sys
import unicodedata
from datetime import date
from itertools import combinations
from pathlib import Path

MAPPA = Path(__file__).parents[1] / 'data' / 'mappa.json'
VUOTE = {'via', 'viale', 'piazza', 'piazzale', 'largo', 'corso', 'vicolo', 'strada', 'p', 'za', 'v', 'le',
         'di', 'del', 'della', 'dei', 'delle', 'degli', 'dello', 'd', 'l', 'e'}
CAMPI = ('categoria', 'data', 'fascia', 'via', 'quadrato', 'seguito')


def parole(nome):
    nome = unicodedata.normalize('NFKD', nome or '').encode('ascii', 'ignore').decode().lower()
    return frozenset(p for p in re.findall(r'[a-z0-9]+', nome) if p not in VUOTE)


def carica_mappa():
    m = json.load(open(MAPPA, encoding='utf-8'))
    return ([(parole(v['n']), set(v['c'])) for v in m['vie']],
            [(parole(l['n']), {l['c']}) for l in m['luoghi']])


def cerca(nome, elenco):
    """Quadrati del nome: la voce con le stesse parole, se no l'unica che le contiene tutte. Se è ambiguo, nessuno."""
    cercate = parole(nome)
    if not cercate:
        return set()
    uguali = [q for p, q in elenco if p == cercate]
    simili = uguali or [q for p, q in elenco if cercate <= p]
    return set().union(*simili) if simili and all(s == simili[0] for s in simili) else set()


def quadrati(e, mappa):
    vie, luoghi = mappa
    return cerca(e.get('via'), vie) or cerca(e.get('luogo'), luoghi)


def vicini(a, b):
    rc = lambda q: (int(q[1:3]), int(q[4:6]))
    return any(abs(rc(x)[0] - rc(y)[0]) <= 1 and abs(rc(x)[1] - rc(y)[1]) <= 1 for x in a for y in b)


def stesso_fatto(e1, e2, mappa):
    if e1['categoria'] != e2['categoria'] or not e1.get('data') or not e2.get('data'):
        return False
    if abs((date.fromisoformat(e1['data']) - date.fromisoformat(e2['data'])).days) > 1:
        return False
    return vicini(quadrati(e1, mappa), quadrati(e2, mappa))


def abbina(attesi, dati):
    liberi, coppie = list(dati), []
    for a in attesi:
        scelta = (next((d for d in liberi if d['categoria'] == a['categoria'] and d.get('data') == a['data']), None)
                  or next((d for d in liberi if d['categoria'] == a['categoria']), None)
                  or (liberi[0] if liberi else None))
        if scelta is not None:
            liberi.remove(scelta)
        coppie.append((a, scelta))
    return coppie, liberi


def leggi(percorso):
    return {r['id']: r for r in map(json.loads, open(percorso, encoding='utf-8')) if r}


def main(etichette, risposte):
    et, ri, mappa = leggi(etichette), leggi(risposte), carica_mappa()
    errori = [i for i, r in ri.items() if 'errore' in r['selezione'] or 'errore' in r['estrazione']]
    ids = sorted(i for i in et if i in ri and i not in errori)
    episodi = {i: ri[i]['estrazione']['risposta']['episodi'] for i in ids}
    vero = {i for i in ids if et[i]['episodio']}
    sel = {i for i in ids if ri[i]['selezione']['risposta']['candidato']}
    est = {i for i in ids if episodi[i]}

    print(f'Articoli valutati: {len(ids)} (errori: {errori or "nessuno"}); con episodio secondo le etichette: {len(vero)}')
    print(f'\nPasso 1, selezione: tiene {len(sel)} articoli su {len(ids)}; positivi tenuti {len(vero & sel)}/{len(vero)}; '
          f'persi: {sorted(vero - sel) or "nessuno"}')
    for nome, trovati in (('Solo passo 2', est), ('Passo 1 + passo 2', sel & est)):
        print(f'{nome}: articoli trovati {len(vero & trovati)}/{len(vero)}, persi {sorted(vero - trovati) or "nessuno"}, '
              f'inventati {sorted(trovati - vero) or "nessuno"}')

    print('\nEpisodi negli articoli giusti (passo 2):')
    conta, n_attesi, n_trovati, in_piu = dict.fromkeys(CAMPI, 0), 0, 0, 0
    for i in sorted(vero & est):
        coppie, avanzi = abbina(et[i]['episodi'], episodi[i])
        in_piu += len(avanzi)
        for atteso, dato in coppie:
            n_attesi += 1
            if dato is None:
                print(f'  {i}: episodio perso {atteso["categoria"]} {atteso["data"]}')
                continue
            n_trovati += 1
            q_a, q_d = quadrati(atteso, mappa), quadrati(dato, mappa)
            esiti = {
                'categoria': atteso['categoria'] == dato['categoria'],
                'data': atteso['data'] == dato.get('data'),
                'fascia': atteso['fascia'] == dato.get('fascia'),
                'via': parole(atteso['via']) == parole(dato.get('via')),
                'quadrato': bool(q_a & q_d) or (not q_a and not q_d),
                'seguito': atteso['seguito'] == dato['seguito'],
            }
            for k, ok in esiti.items():
                conta[k] += ok
            diversi = {k: (atteso.get(k), dato.get(k)) for k, ok in esiti.items() if not ok and k != 'quadrato'}
            if not esiti['quadrato']:
                diversi['quadrato'] = (sorted(q_a)[:3], sorted(q_d)[:3])
            if diversi:
                print(f'  {i}: {diversi}  (luogo dato: {dato.get("luogo")})')
        for d in avanzi:
            print(f'  {i}: episodio in più {d["categoria"]} {d.get("data")} {d.get("via")} {d.get("luogo")}')
    print(f'  Episodi trovati {n_trovati}/{n_attesi}, in più {in_piu}. Sui trovati: '
          + ', '.join(f'{k} {v}/{n_trovati}' for k, v in conta.items()))

    for i in sorted(est - vero):
        print(f'\nInventato {i} ({et[i].get("motivo")}): {episodi[i]}')
    for i in sorted(vero - est):
        print(f'\nPerso {i}: {ri[i]["estrazione"]["risposta"]["scarto"]}')

    attese = {frozenset((i, j)) for i in vero for j in et[i].get('stesso_evento', []) if j in vero}
    date_ = {frozenset((i, j)) for i, j in combinations(sorted(est), 2)
             if any(stesso_fatto(x, y, mappa) for x in episodi[i] for y in episodi[j])}
    if attese or date_:
        print(f'\nConciliazione: coppie attese {len(attese)}, riconosciute {len(attese & date_)}, '
              f'unite a torto {len(date_ - attese)}')
        print(f'  mancate: {sorted(tuple(sorted(c)) for c in attese - date_)}')
        print(f'  a torto: {sorted(tuple(sorted(c)) for c in date_ - attese)}')

    secondi = [ri[i][p]['secondi'] for i in ri for p in ('selezione', 'estrazione')]
    costo = sum(ri[i][p].get('costo_listino') or 0 for i in ri for p in ('selezione', 'estrazione'))
    print(f'\nTempo: {sum(secondi):.0f} s di chiamate, {sum(secondi) / len(secondi):.1f} s in media; '
          f'costo a listino (coperto dall\'abbonamento, non pagato a parte): {costo:.3f} USD')


if __name__ == '__main__':
    main(*sys.argv[1:3])
