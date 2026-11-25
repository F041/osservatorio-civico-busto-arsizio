"""Regole per riconoscere lo stesso fatto tra articoli diversi.

Le usano scripts/build_notizie.py e valutazione/punteggio.py, così la prova misura le stesse regole del sito.
- Nello stesso articolo, episodi con lo stesso tipo e la stessa via a un giorno al massimo sono un episodio solo:
  un articolo non deve poter raggiungere da solo la soglia raccontando più colpi dello stesso fatto. Le lamentele
  ricorrenti su una via dove l'articolo racconta già un fatto preciso non contano a parte.
- Tra articoli diversi, due episodi sono lo stesso fatto se hanno lo stesso tipo, sono a un giorno al massimo di
  distanza, in quadrati uguali o vicini, e in fasce uguali o vicine quando entrambe sono note. Se una delle due vie è
  lunga deve essere la stessa via, il suo incrocio o lo stesso giorno: una via lunga risulta vicina a troppe altre.
- Un fatto raccontato solo da articoli senza data, con un fatto dello stesso tipo nella stessa via nei 7 giorni
  prima, è un seguito di quello (verifica del 25/11/2026: commenti e provvedimenti pubblicati giorni dopo).
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

MAPPA = Path(__file__).parents[1] / 'data' / 'mappa.json'
VUOTE = {'via', 'viale', 'piazza', 'piazzale', 'largo', 'corso', 'vicolo', 'strada', 'p', 'za', 'v', 'le',
         'di', 'del', 'della', 'dei', 'delle', 'degli', 'dello', 'd', 'l', 'e'}
VIA_LUNGA = 6  # quadrati
FASCE = ['mattina', 'pomeriggio', 'sera', 'notte']  # in ordine: la notte confina con la mattina
GIORNI_SEGUITO = 7


def parole(nome):
    nome = unicodedata.normalize('NFKD', nome or '').encode('ascii', 'ignore').decode().lower()
    return frozenset(p for p in re.findall(r'[a-z0-9]+', nome) if p not in VUOTE)


def carica_mappa():
    m = json.load(open(MAPPA, encoding='utf-8'))
    return [(v['n'], parole(v['n']), set(v['c'])) for v in m['vie']] + \
           [(l['n'], parole(l['n']), {l['c']}) for l in m['luoghi']]


def quadrati(e, mappa):
    """Quadrati della via (o del luogo) di un episodio: la voce con lo stesso nome, se no con le stesse parole;
    vuoto se manca o è ambigua ("Via Repubblica" e "Viale della Repubblica" hanno le stesse parole)."""
    via = e.get('via') or ''
    uguali = ([q for n, _, q in mappa if n.lower() == via.lower()]
              or [q for _, p, q in mappa if parole(via) and p == parole(via)])
    return set().union(*uguali) if uguali and all(q == uguali[0] for q in uguali) else set()


def vicini(a, b):
    rc = lambda q: (int(q[1:3]), int(q[4:6]))
    return any(abs(rc(x)[0] - rc(y)[0]) <= 1 and abs(rc(x)[1] - rc(y)[1]) <= 1 for x in a for y in b)


def stessa_strada(e1, e2):
    """Vero se i due episodi hanno in comune la via o l'incrocio."""
    nomi = lambda e: {(e.get(k) or '').lower() for k in ('via', 'incrocio')} - {''}
    return bool(nomi(e1) & nomi(e2))


def stessa_zona(e1, e2, mappa):
    q1, q2 = quadrati(e1, mappa), quadrati(e2, mappa)
    return stessa_strada(e1, e2) or (bool(q1 & q2) and max(len(q1), len(q2)) < VIA_LUNGA)


def compatta(episodi):
    """Unisce gli episodi di un articolo con lo stesso tipo, la stessa via e al massimo un giorno di distanza, o senza
    data."""
    tenuti = []
    for e in sorted(episodi, key=lambda x: x.get('data') or '9999'):
        uguale = next((t for t in tenuti if t['categoria'] == e['categoria'] and t.get('via') == e.get('via')
                       and (not t.get('data') or not e.get('data')
                            or abs((date.fromisoformat(t['data']) - date.fromisoformat(e['data'])).days) <= 1)), None)
        if uguale is None:
            tenuti.append(dict(e))
        else:
            for campo in ('data', 'fascia', 'incrocio', 'luogo'):
                uguale[campo] = uguale.get(campo) or e.get(campo)
    # Le lamentele ricorrenti su una via dove lo stesso articolo racconta già un fatto preciso ripetono quel fatto
    concrete = {t.get('via') for t in tenuti if t['categoria'] != 'insicurezza'}
    return [t for t in tenuti if t['categoria'] != 'insicurezza' or t.get('via') not in concrete]


def stesso_fatto(e1, e2, mappa):
    if e1['categoria'] != e2['categoria'] or not e1.get('data') or not e2.get('data'):
        return False
    if abs((date.fromisoformat(e1['data']) - date.fromisoformat(e2['data'])).days) > 1:
        return False
    # Fasce vicine vanno bene: "tardo pomeriggio" diventa pomeriggio in un articolo e sera in un altro
    if e1.get('fascia') in FASCE and e2.get('fascia') in FASCE:
        distanza = abs(FASCE.index(e1['fascia']) - FASCE.index(e2['fascia']))
        if min(distanza, len(FASCE) - distanza) > 1:
            return False
    q1, q2 = quadrati(e1, mappa), quadrati(e2, mappa)
    # Un incrocio può essere attribuito a due vie diverse: con una via lunga si uniscono solo se il giorno è lo stesso
    if max(len(q1), len(q2)) >= VIA_LUNGA and not stessa_strada(e1, e2) and e1['data'] != e2['data']:
        return False
    return vicini(q1, q2)


def raggruppa(episodi, mappa):
    """Gruppi di episodi che raccontano lo stesso fatto. Ogni episodio ha il campo `articolo`: due episodi dello stesso
    articolo non si uniscono qui, perché `compatta` ha già unito quelli uguali."""
    padre = list(range(len(episodi)))

    def radice(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i, a in enumerate(episodi):
        for j in range(i):
            if a['articolo'] != episodi[j]['articolo'] and stesso_fatto(a, episodi[j], mappa):
                padre[radice(i)] = radice(j)
    gruppi = {}
    for i, e in enumerate(episodi):
        gruppi.setdefault(radice(i), []).append(e)
    return aggancia_seguiti(list(gruppi.values()))


def aggancia_seguiti(gruppi):
    """Un fatto raccontato solo da articoli senza data (vale il giorno di pubblicazione) è spesso un seguito non
    riconosciuto: se nei GIORNI_SEGUITO giorni prima c'è un fatto dello stesso tipo nella stessa via, si unisce a quello,
    il più vicino."""
    # La prova (valutazione/punteggio.py) lascia episodi senza data: lì non si aggancia niente
    if any(not e.get('data') for g in gruppi for e in g):
        return gruppi
    senza = lambda g: all(e.get('senza_data') for e in g)
    giorno = lambda g: date.fromisoformat(min(e['data'] for e in g))
    # In ordine di giorno, i fatti datati prima: un seguito si aggancia anche a un fatto senza data uscito prima
    tenuti = []
    for g in sorted(gruppi, key=lambda g: (giorno(g), senza(g))):
        adatti = [d for d in tenuti if d[0]['categoria'] == g[0]['categoria']
                  and any(stessa_strada(a, b) for a in g for b in d)
                  and 0 <= (giorno(g) - giorno(d)).days <= GIORNI_SEGUITO] if senza(g) else []
        if adatti:
            max(adatti, key=giorno).extend(g)
        else:
            tenuti.append(g)
    return tenuti
