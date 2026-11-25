"""Dati pubblici della vista Notizie della mappa, dagli episodi già approvati nella revisione.

Uso: python scripts/build_notizie.py episodi.jsonl data/notizie.json

`episodi.jsonl` ha una riga per articolo: fonte, url, pubblicato ed episodi (categoria, data, fascia, via, incrocio,
seguito). Unisce gli episodi che raccontano lo stesso fatto (scripts/conciliazione.py) e scrive un fatto per riga:
giorno, via o luogo, tipo e link agli articoli. Il periodo lo sceglie chi guarda la mappa (js/notizie.js), quindi
conteggi, soglia e tipi si calcolano nella pagina: per un periodo qualsiasi servono i singoli fatti.
Non pubblica titoli, testi, nomi o età. I conteggi non si sommano mai a quelli delle segnalazioni (build_sicurezza.py).
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conciliazione import carica_mappa, compatta, quadrati, raggruppa  # noqa: E402

# Decisioni dell'utente del 24/11/2026: soglia 2, perché i fatti nelle notizie sono pochi e sparsi su molte vie (le
# segnalazioni dei cittadini restano a 3); periodo scelto a mano sulla mappa, fino a un anno indietro
SOGLIA = 2
FINESTRA_GIORNI = 365
RIASSUNTI = ('prealpina.it/video/tg/',)


def episodi_validi(righe, mappa, inizio, oggi):
    """Episodi della finestra con una via sulla mappa. Senza data vale la pubblicazione, tranne per i seguiti: un
    articolo su un processo non è un fatto di quel giorno."""
    out = []
    for r in righe:
        # I notiziari video ripetono le notizie del giorno già raccontate negli articoli
        if any(parte in r['url'] for parte in RIASSUNTI):
            continue
        pubblicato = (r.get('pubblicato') or r.get('visto') or '')[:10]
        for e in compatta(r.get('episodi', [])):
            if not e.get('data') and e.get('seguito'):
                continue
            giorno = e.get('data') or pubblicato
            if giorno and inizio <= date.fromisoformat(giorno) <= oggi and quadrati(e, mappa):
                out.append({**e, 'data': giorno, 'senza_data': not e.get('data'), 'articolo': r['url'],
                            'fonte': r['fonte']})
    return out


def costruisci(righe, mappa, adesso):
    oggi = adesso.date()
    inizio = oggi - timedelta(days=FINESTRA_GIORNI)
    fatti = []
    for gruppo in raggruppa(episodi_validi(righe, mappa, inizio, oggi), mappa):
        # Il fatto va sulla via nominata da più articoli; a pari merito (due vie dello stesso incrocio) sulla più
        # corta, la più precisa
        per_via = {}
        for e in gruppo:
            per_via.setdefault(e['via'], set()).add(e['articolo'])
        via = min(per_via, key=lambda v: (-len(per_via[v]), len(quadrati({'via': v}, mappa)), v))
        articoli = {e['articolo']: {'fonte': e['fonte'], 'data': e['data'], 'url': e['articolo']} for e in gruppo}
        fatti.append({
            'data': min(e['data'] for e in gruppo),
            'via': via,
            'tipo': gruppo[0]['categoria'],
            'articoli': sorted(articoli.values(), key=lambda a: (a['data'], a['fonte']), reverse=True),
        })
    fatti.sort(key=lambda f: (f['data'], f['via']))
    # La raccolta può coprire meno di FINESTRA_GIORNI: la serie parte dal primo articolo, non da prima
    pubblicati = [(r.get('pubblicato') or r.get('visto') or '')[:10] for r in righe]
    primo = max(date.fromisoformat(min((p for p in pubblicati if p), default=inizio.isoformat())), inizio)
    return {
        'generato': adesso.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'soglia': SOGLIA,
        'da': primo.isoformat(),
        'a': oggi.isoformat(),
        'fatti': fatti,
    }


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('Uso: python scripts/build_notizie.py episodi.jsonl data/notizie.json')
    with open(sys.argv[1], encoding='utf-8') as f:
        righe = [json.loads(r) for r in f if r.strip()]
    dati = costruisci(righe, carica_mappa(), datetime.now(timezone.utc))
    with open(sys.argv[2], 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    print(f"Scritto {sys.argv[2]}: {len(dati['fatti'])} fatti dal {dati['da']} al {dati['a']}")
