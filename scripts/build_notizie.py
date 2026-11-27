"""Dati pubblici della vista Notizie della mappa, dagli episodi già approvati nella revisione.

Uso: python scripts/build_notizie.py episodi.jsonl data/notizie.json

`episodi.jsonl` ha una riga per articolo: fonte, url, pubblicato, episodi (categoria, data, fascia, via, incrocio,
seguito) e, se ci sono, i riassunti dei fatti (scripts/riassunti_notizie.py). Unisce gli episodi che raccontano lo stesso fatto (scripts/conciliazione.py) e scrive un fatto per riga:
giorno, via o luogo, tipo, riassunto e link agli articoli. Il periodo lo sceglie chi guarda la mappa (js/notizie.js), quindi
conteggi, soglia e tipi si calcolano nella pagina: per un periodo qualsiasi servono i singoli fatti.
Non pubblica titoli, testi, nomi o età. I conteggi non si sommano mai a quelli delle segnalazioni (build_sicurezza.py).
"""
import csv
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conciliazione import aggancia_seguiti, carica_mappa, compatta, quadrati, raggruppa  # noqa: E402
from raccogli_notizie import CONSERVAZIONE_GIORNI  # noqa: E402

# Decisioni dell'utente del 24/11/2026: soglia 2, perché i fatti nelle notizie sono pochi e sparsi su molte vie (le
# segnalazioni dei cittadini restano a 3); periodo scelto a mano sulla mappa. La mappa arriva indietro quanto la raccolta tiene gli articoli (24 mesi)
SOGLIA = 2
FINESTRA_GIORNI = CONSERVAZIONE_GIORNI
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


def primo_episodio(gruppo):
    """Articolo, giorno e via del fatto secondo il primo articolo (per link): danno l'id e la chiave del riassunto."""
    primo = min(e['articolo'] for e in gruppo)
    giorno, via = min((e['data'], e['via']) for e in gruppo if e['articolo'] == primo)
    return primo, giorno, via


def chiave_riassunto(categoria, via, giorno):
    """Chiave del riassunto nel campo `riassunti` dell'articolo (scripts/riassunti_notizie.py)."""
    return f'{categoria}|{via}|{giorno}'


def id_fatto(gruppo):
    """Serve alla revisione (revisione/notizie.tsv) per riconoscere i fatti già visti. Viene dal primo articolo (per
    link) e da giorno, via e tipo che quell'articolo dà al fatto: un articolo può raccontare due furti in due vie. Resta
    uguale quando altri articoli raccontano lo stesso fatto, a meno che uno non venga prima nell'ordine dei link."""
    primo, giorno, via = primo_episodio(gruppo)
    return hashlib.sha256(f"{primo}|{giorno}|{via}|{gruppo[0]['categoria']}".encode('utf-8')).hexdigest()[:12]


def esclusi(percorso):
    """Id dei fatti che la revisione ha segnato come sbagliati (colonna esito = no)."""
    if not percorso or not Path(percorso).exists():
        return set()
    with open(percorso, encoding='utf-8', newline='') as f:
        return {r['id'] for r in csv.DictReader(f, delimiter='\t') if (r.get('esito') or '').strip().lower() == 'no'}


def costruisci(righe, mappa, adesso):
    oggi = adesso.date()
    inizio = oggi - timedelta(days=FINESTRA_GIORNI)
    riassunti = {r['url']: r.get('riassunti') or {} for r in righe}
    fatti = []
    for gruppo in aggancia_seguiti(raggruppa(episodi_validi(righe, mappa, inizio, oggi), mappa)):
        # Il fatto va sulla via nominata da più articoli; a pari merito (due vie dello stesso incrocio) sulla più
        # corta, la più precisa
        per_via = {}
        for e in gruppo:
            per_via.setdefault(e['via'], set()).add(e['articolo'])
        via = min(per_via, key=lambda v: (-len(per_via[v]), len(quadrati({'via': v}, mappa)), v))
        primo, giorno, via_primo = primo_episodio(gruppo)
        riassunto = riassunti.get(primo, {}).get(chiave_riassunto(gruppo[0]['categoria'], via_primo, giorno))
        articoli = {e['articolo']: {'fonte': e['fonte'], 'data': e['data'], 'url': e['articolo']} for e in gruppo}
        fatti.append({
            'id': id_fatto(gruppo),
            'data': min(e['data'] for e in gruppo),
            'via': via,
            'tipo': gruppo[0]['categoria'],
            **({'riassunto': riassunto} if riassunto else {}),
            'articoli': sorted(articoli.values(), key=lambda a: (a['data'], a['fonte'], a['url']), reverse=True),
        })
    fatti.sort(key=lambda f: (f['data'], f['via'], f['id']))
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
    if len(sys.argv) not in (3, 4):
        sys.exit('Uso: python scripts/build_notizie.py episodi.jsonl data/notizie.json [revisione/notizie.tsv]')
    with open(sys.argv[1], encoding='utf-8') as f:
        righe = [json.loads(r) for r in f if r.strip()]
    dati = costruisci(righe, carica_mappa(), datetime.now(timezone.utc))
    tolti = esclusi(sys.argv[3] if len(sys.argv) == 4 else None)
    if tolti:
        prima = len(dati['fatti'])
        dati['fatti'] = [f for f in dati['fatti'] if f['id'] not in tolti]
        print(f'Fatti segnati come sbagliati nella revisione e tolti: {prima - len(dati["fatti"])}')
    with open(sys.argv[2], 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    print(f"Scritto {sys.argv[2]}: {len(dati['fatti'])} fatti dal {dati['da']} al {dati['a']}")
