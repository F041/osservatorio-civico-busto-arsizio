"""Confronta le risposte del filtro delle vie e del modello con le etichette fatte a mano.

Uso: uv run --no-project --python 3.12 python -I valutazione/punteggio.py valutazione/dati/etichette.jsonl \
         valutazione/dati/risposte-vie-haiku.jsonl

Contano solo gli episodi etichettati con una via o un luogo che si trovano sulla mappa: gli altri la pipeline li
scarta per scelta (decisione del 13/11/2026), quindi non sono attesi.
Misure:
- filtro: quanti articoli passano al modello e quanti articoli con episodi lascia fuori;
- per articolo: articoli con episodi trovati, persi e inventati;
- per episodio: prima si uniscono gli episodi di un articolo con lo stesso tipo, la stessa via e al massimo un giorno
  di distanza. Ogni episodio atteso si abbina poi a uno dato nella stessa via, o in una via corta con quadrati in
  comune; sulle coppie si contano categoria, data, fascia, quadrato e seguito;
- conciliazione: due articoli raccontano lo stesso fatto se hanno episodi dello stesso tipo, a un giorno al massimo
  di distanza, in quadrati uguali o vicini, e non in due fasce diverse quando entrambe sono note. Se una delle due
  vie è lunga, deve essere la stessa via, il suo incrocio o lo stesso giorno. Le coppie in `salta_coppie` non contano
  né in un senso né nell'altro.
"""
import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from conciliazione import carica_mappa, compatta, quadrati, stessa_strada, stessa_zona, stesso_fatto  # noqa: E402

CAMPI = ('categoria', 'data', 'fascia', 'quadrato', 'seguito')


def abbina(attesi, dati, mappa):
    liberi, coppie = list(dati), []
    for a in attesi:
        adatti = [d for d in liberi if stessa_zona(a, d, mappa)]
        scelta = max(adatti, default=None, key=lambda d: (d['categoria'] == a['categoria'], stessa_strada(a, d),
                                                          d.get('data') == a['data']))
        if scelta is not None:
            liberi.remove(scelta)
        coppie.append((a, scelta))
    return coppie, liberi


def leggi(percorso):
    return {r['id']: r for r in map(json.loads, open(percorso, encoding='utf-8')) if r}


def main(etichette, risposte):
    et, ri, mappa = leggi(etichette), leggi(risposte), carica_mappa()
    errori = [i for i, r in ri.items() if r['estrazione'] and 'errore' in r['estrazione']]
    ids = sorted(i for i in et if i in ri and i not in errori)
    attesi = {i: [e for e in et[i].get('episodi', []) if quadrati(e, mappa)] for i in ids}
    episodi = {i: compatta((ri[i]['estrazione'] or {}).get('risposta', {}).get('episodi', [])) for i in ids}
    vero = {i for i in ids if attesi[i]}
    passati = {i for i in ids if ri[i]['vie']}
    trovati = {i for i in ids if episodi[i]}
    senza_luogo = sorted(i for i in ids if et[i]['episodio'] and not attesi[i])

    print(f'Articoli valutati: {len(ids)} (errori: {errori or "nessuno"}); con episodi sulla mappa: {len(vero)}')
    print(f'  episodi etichettati senza via né luogo sulla mappa, non attesi: {senza_luogo or "nessuno"}')
    print(f'Filtro delle vie: passano {len(passati)}/{len(ids)}; articoli con episodi lasciati fuori: '
          f'{sorted(vero - passati) or "nessuno"}')
    print(f'Modello: articoli trovati {len(vero & trovati)}/{len(vero)}, persi {sorted(vero - trovati) or "nessuno"}, '
          f'inventati {sorted(trovati - vero) or "nessuno"}')

    print('\nEpisodi negli articoli giusti:')
    conta, n_attesi, n_trovati, in_piu = dict.fromkeys(CAMPI, 0), 0, 0, 0
    for i in sorted(vero & trovati):
        coppie, avanzi = abbina(attesi[i], episodi[i], mappa)
        in_piu += len(avanzi)
        for atteso, dato in coppie:
            n_attesi += 1
            if dato is None:
                print(f'  {i}: episodio perso {atteso["categoria"]} {atteso["data"]} {atteso["via"]}')
                continue
            n_trovati += 1
            esiti = {
                'categoria': atteso['categoria'] == dato['categoria'],
                'data': atteso['data'] == dato.get('data'),
                'fascia': atteso['fascia'] == dato.get('fascia'),
                'quadrato': bool(quadrati(atteso, mappa) & quadrati(dato, mappa)),
                'seguito': atteso['seguito'] == dato['seguito'],
            }
            for k, ok in esiti.items():
                conta[k] += ok
            diversi = {k: (atteso.get(k), dato.get(k)) for k, ok in esiti.items() if not ok and k != 'quadrato'}
            if diversi:
                print(f'  {i}: {diversi}')
        for d in avanzi:
            print(f'  {i}: episodio in più {d["categoria"]} {d.get("data")} {d.get("via")} ({d.get("luogo")})')
    n_attesi += sum(len(attesi[i]) for i in vero - trovati)
    print(f'  Episodi trovati {n_trovati}/{n_attesi}, in più {in_piu}. Sui trovati: '
          + ', '.join(f'{k} {v}/{n_trovati}' for k, v in conta.items()))

    for i in sorted(trovati - vero):
        print(f'\nInventato {i} ({et[i].get("motivo")}): {episodi[i]}')
    for i in sorted((vero & passati) - trovati):
        print(f'\nPerso {i}: {ri[i]["estrazione"]["risposta"]["scarto"]}')

    salta = {frozenset((i, j)) for i in ids for j in et[i].get('salta_coppie', [])}
    # Coppie attese: articoli segnati come stesso fatto che hanno quel fatto tutti e due con una via sulla mappa
    attese = {frozenset((i, j)) for i in vero for j in et[i].get('stesso_evento', []) if j in vero
              and any(stesso_fatto(x, y, mappa) for x in attesi[i] for y in attesi[j])} - salta
    date_ = {frozenset((i, j)) for i, j in combinations(sorted(trovati), 2)
             if any(stesso_fatto(x, y, mappa) for x in episodi[i] for y in episodi[j])} - salta
    if attese or date_:
        print(f'\nConciliazione: coppie attese {len(attese)}, riconosciute {len(attese & date_)}, '
              f'unite a torto {len(date_ - attese)}')
        print(f'  mancate: {sorted(tuple(sorted(c)) for c in attese - date_)}')
        print(f'  a torto: {sorted(tuple(sorted(c)) for c in date_ - attese)}')

    chiamate = [r['estrazione'] for r in ri.values() if r['estrazione']]
    secondi = sum(c['secondi'] for c in chiamate)
    costo = sum(c.get('costo_listino') or 0 for c in chiamate)
    print(f'\nChiamate al modello: {len(chiamate)}, {secondi:.0f} s in tutto, {secondi / max(len(chiamate), 1):.1f} s '
          f'in media; costo a listino (coperto dall\'abbonamento, non pagato a parte): {costo:.3f} USD')


if __name__ == '__main__':
    main(*sys.argv[1:3])
