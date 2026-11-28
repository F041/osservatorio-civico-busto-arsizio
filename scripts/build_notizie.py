"""Dati pubblici della vista Notizie della mappa, dagli episodi già approvati nella revisione.

Uso: python scripts/build_notizie.py episodi.jsonl data/notizie.json [revisione/notizie.tsv [precedente.json]]

`precedente.json` è data/notizie.json com'è pubblicato adesso: i fatti già pubblicati tengono il loro id (vedi
primo_episodio).

`episodi.jsonl` ha una riga per articolo: fonte, url, pubblicato, episodi (categoria, data, fascia, via, incrocio,
seguito) e, se ci sono, riassunti e sottotipi dei fatti (scripts/riassunti_notizie.py). Unisce gli episodi che raccontano lo stesso fatto (scripts/conciliazione.py) e scrive un fatto per riga:
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
# Sottotipi (decisione dell'utente del 28/11/2026): un campo in più accanto al tipo, non tipi nuovi, così l'id dei
# fatti non cambia. casa: furti e tentati furti in case, appartamenti, box, cantine e parti comuni dei condomini;
# rifiuti: abbandono di rifiuti, dentro vandalismo o degrado. `nessuno` dice che il fatto è stato guardato e non ne ha
SOTTOTIPI = {'furto': ('casa',), 'vandalismo': ('rifiuti',)}
NESSUNO = 'nessuno'


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


def candidati(gruppo):
    """(id, articolo, giorno, via) per ogni articolo del fatto, in ordine di link; giorno e via sono quelli che
    l'articolo dà al fatto (un articolo può raccontare due furti in due vie)."""
    out = []
    for articolo in sorted({e['articolo'] for e in gruppo}):
        giorno, via = min((e['data'], e['via']) for e in gruppo if e['articolo'] == articolo)
        i = hashlib.sha256(f"{articolo}|{giorno}|{via}|{gruppo[0]['categoria']}".encode('utf-8')).hexdigest()[:12]
        out.append((i, articolo, giorno, via))
    return out


def primo_episodio(gruppo, noti=frozenset()):
    """Id, articolo, giorno e via che identificano il fatto; dallo stesso articolo vengono le chiavi di riassunto e
    sottotipo. Un fatto nuovo prende l'id dal primo articolo per link. Un fatto già pubblicato o già nella revisione
    (`noti`) tiene il suo anche quando arriva un articolo che viene prima nell'ordine dei link, per esempio dal recupero
    dell'archivio di ilBustese: altrimenti la revisione già fatta su quel fatto andrebbe persa."""
    tutti = candidati(gruppo)
    return next((c for c in tutti if c[0] in noti), tutti[0])


def noti(precedente, esiti):
    """Id dei fatti già pubblicati (data/notizie.json di adesso) o già nella revisione."""
    ids = set(esiti)
    if precedente and Path(precedente).exists():
        with open(precedente, encoding='utf-8') as f:
            ids |= {fatto['id'] for fatto in json.load(f)['fatti']}
    return frozenset(ids)


def chiave_riassunto(categoria, via, giorno):
    """Chiave del riassunto nel campo `riassunti` dell'articolo (scripts/riassunti_notizie.py)."""
    return f'{categoria}|{via}|{giorno}'


def id_fatto(gruppo, noti=frozenset()):
    """Serve alla revisione (revisione/notizie.tsv) per riconoscere i fatti già visti (vedi primo_episodio)."""
    return primo_episodio(gruppo, noti)[0]


TIPI = ('furto', 'molestia', 'aggressione', 'vandalismo', 'spaccio', 'insicurezza', 'allagamento', 'altro')


def revisione(percorso):
    """Esiti della revisione per id: colonna esito (`no` toglie il fatto), tipo_giusto (corregge il tipo) e
    sottotipo_giusto (corregge il sottotipo; `nessuno` lo toglie)."""
    if not percorso or not Path(percorso).exists():
        return {}
    with open(percorso, encoding='utf-8', newline='') as f:
        return {r['id']: r for r in csv.DictReader(f, delimiter='\t')}


def da_controllare(fatto, esiti):
    """Fatto mai inviato nella revisione, o di un tipo con sottotipi inviato prima che i sottotipi ci fossero (senza
    sottotipo_giusto). La stessa regola è in js/revisione.js."""
    r = esiti.get(fatto['id'])
    return r is None or (fatto['tipo'] in SOTTOTIPI and r.get('esito') != 'no' and not (r.get('sottotipo_giusto') or '').strip())


def applica(fatti, esiti):
    """Toglie i fatti con esito `no` e corregge tipo e sottotipo dove la revisione ne ha indicato altri. Un sottotipo
    che non vale per il tipo corretto cade."""
    tenuti, tolti, corretti = [], 0, 0
    for f in fatti:
        r = esiti.get(f['id'], {})
        if (r.get('esito') or '').strip().lower() == 'no':
            tolti += 1
            continue
        prima = (f['tipo'], f.get('sottotipo'))
        giusto = (r.get('tipo_giusto') or '').strip()
        if giusto in TIPI and giusto != f['tipo']:
            f = {**f, 'tipo': giusto}
        sottotipo = (r.get('sottotipo_giusto') or '').strip() or f.get('sottotipo')
        f = {k: v for k, v in f.items() if k != 'sottotipo'}
        if sottotipo in SOTTOTIPI.get(f['tipo'], ()):
            f['sottotipo'] = sottotipo
        corretti += (f['tipo'], f.get('sottotipo')) != prima
        tenuti.append(f)
    return tenuti, tolti, corretti


def costruisci(righe, mappa, adesso, noti=frozenset()):
    oggi = adesso.date()
    inizio = oggi - timedelta(days=FINESTRA_GIORNI)
    riassunti = {r['url']: r.get('riassunti') or {} for r in righe}
    sottotipi = {r['url']: r.get('sottotipi') or {} for r in righe}
    fatti = []
    for gruppo in aggancia_seguiti(raggruppa(episodi_validi(righe, mappa, inizio, oggi), mappa)):
        # Il fatto va sulla via nominata da più articoli; a pari merito (due vie dello stesso incrocio) sulla più
        # corta, la più precisa
        per_via = {}
        for e in gruppo:
            per_via.setdefault(e['via'], set()).add(e['articolo'])
        via = min(per_via, key=lambda v: (-len(per_via[v]), len(quadrati({'via': v}, mappa)), v))
        i, primo, giorno, via_primo = primo_episodio(gruppo, noti)
        tipo = gruppo[0]['categoria']
        chiave = chiave_riassunto(tipo, via_primo, giorno)
        riassunto = riassunti.get(primo, {}).get(chiave)
        sottotipo = sottotipi.get(primo, {}).get(chiave)
        articoli = {e['articolo']: {'fonte': e['fonte'], 'data': e['data'], 'url': e['articolo']} for e in gruppo}
        fatti.append({
            'id': i,
            'data': min(e['data'] for e in gruppo),
            'via': via,
            'tipo': tipo,
            **({'sottotipo': sottotipo} if sottotipo in SOTTOTIPI.get(tipo, ()) else {}),
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
    if len(sys.argv) not in (3, 4, 5):
        sys.exit(__doc__)
    with open(sys.argv[1], encoding='utf-8') as f:
        righe = [json.loads(r) for r in f if r.strip()]
    esiti = revisione(sys.argv[3] if len(sys.argv) > 3 else None)
    dati = costruisci(righe, carica_mappa(), datetime.now(timezone.utc),
                      noti(sys.argv[4] if len(sys.argv) > 4 else None, esiti))
    dati['fatti'], tolti, corretti = applica(dati['fatti'], esiti)
    if tolti or corretti:
        print(f'Revisione: {tolti} fatti tolti, {corretti} con il tipo o il sottotipo corretto')
    with open(sys.argv[2], 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    print(f"Scritto {sys.argv[2]}: {len(dati['fatti'])} fatti dal {dati['da']} al {dati['a']}")
