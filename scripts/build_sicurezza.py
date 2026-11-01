"""Conteggi pubblici della sezione Sicurezza, dalle segnalazioni su Firestore.

Uso: GOOGLE_APPLICATION_CREDENTIALS=chiave.json python scripts/build_sicurezza.py data/sicurezza.json

Gira ogni notte nel workflow sicurezza.yml con un account di servizio (ruolo Cloud Datastore User).
Pubblica solo conteggi degli ultimi 90 giorni: per quadrato della mappa, tipo, fascia, fattori e denuncia,
e per quadrato incrociato con una sola altra voce (tipo, fascia o fattore), per i filtri della mappa.
Nasconde i conteggi sotto SOGLIA (i quadrati sotto soglia non compaiono proprio). Cancella le segnalazioni più vecchie di 12 mesi, come dice privacy.html.
Gli elenchi devono coincidere con firestore.rules e js/sicurezza-config.js.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

PROJECT_ID = "osservatorio-civico-busto"
COLLECTION = "segnalazioni"
FINESTRA_GIORNI = 90
CONSERVAZIONE_GIORNI = 365
SOGLIA = 3  # conteggi da 1 a SOGLIA-1 pubblicati come "meno di SOGLIA"

CATEGORIE = ["insicurezza", "furto", "molestia", "aggressione", "vandalismo", "altro"]
FASCE = ["mattina", "pomeriggio", "sera", "notte"]
FATTORI = ["illuminazione", "isolata", "persone-moleste", "degrado", "trasporti", "nessuno-intorno"]
DENUNCIA = ["si", "no", "non-dico"]


def published_counts(counter, keys):
    """0 resta 0; da 1 a SOGLIA-1 diventa None (la pagina mostra "meno di SOGLIA")."""
    return {k: (None if 0 < counter[k] < SOGLIA else counter[k]) for k in keys}


def celle_per_voce(per_cella, celle_pubbliche, keys, esclusive):
    """Per ogni voce, i quadrati con almeno SOGLIA segnalazioni di quella voce, dal più segnalato.

    Tipo e fascia sono esclusivi (una sola voce per segnalazione) e il totale del quadrato è pubblico:
    se le voci nascoste sommassero a 1 o 2, chi sottrae dal totale quelle visibili ricaverebbe un numero
    sotto soglia. In quel caso si nasconde anche la voce visibile più piccola.
    """
    out = {k: {} for k in keys}
    for cella, conteggi in per_cella.items():
        if cella not in celle_pubbliche:
            continue  # quadrato sotto soglia: lo sono anche tutte le sue voci
        visibili = {k: n for k, n in conteggi.items() if k in out and n >= SOGLIA}
        if esclusive and visibili and 0 < celle_pubbliche[cella] - sum(visibili.values()) < SOGLIA:
            del visibili[min(visibili, key=visibili.get)]
        for k, n in visibili.items():
            out[k][cella] = n
    return {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in out.items()}


def delete_expired(client, now):
    expired = client.collection(COLLECTION).where(
        filter=FieldFilter("creato", "<", now - timedelta(days=CONSERVAZIONE_GIORNI))).stream()
    deleted = 0
    for doc in expired:
        doc.reference.delete()
        deleted += 1
    return deleted


def build(client, now):
    start = now - timedelta(days=FINESTRA_GIORNI)
    docs = client.collection(COLLECTION).where(filter=FieldFilter("data", ">=", start)).stream()
    celle, categorie, fasce, fattori, denuncia = Counter(), Counter(), Counter(), Counter(), Counter()
    per_tipo, per_fascia, per_fattore = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    totale = 0
    for doc in docs:
        d = doc.to_dict()
        totale += 1
        celle[d.get("cella")] += 1
        categorie[d.get("categoria")] += 1
        fasce[d.get("fascia")] += 1
        fattori.update(d.get("fattori") or [])  # una segnalazione può indicarne più di uno
        denuncia[d.get("denuncia")] += 1
        per_tipo[d.get("cella")][d.get("categoria")] += 1
        per_fascia[d.get("cella")][d.get("fascia")] += 1
        per_fattore[d.get("cella")].update(d.get("fattori") or [])
    pubbliche = {k: n for k, n in celle.most_common() if k and n >= SOGLIA}
    return {
        "generato": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finestra_giorni": FINESTRA_GIORNI,
        "da": start.strftime("%Y-%m-%d"),
        "a": now.strftime("%Y-%m-%d"),
        "soglia": SOGLIA,
        "totale": totale,
        # Quadrati di scripts/build_mappa.py, dal più segnalato
        "celle": pubbliche,
        # Gli stessi quadrati per una sola voce alla volta: i filtri della mappa non incrociano due voci
        "celle_per": {
            "categoria": celle_per_voce(per_tipo, pubbliche, CATEGORIE, esclusive=True),
            "fascia": celle_per_voce(per_fascia, pubbliche, FASCE, esclusive=True),
            "fattori": celle_per_voce(per_fattore, pubbliche, FATTORI, esclusive=False),
        },
        "categorie": published_counts(categorie, CATEGORIE),
        "fasce": published_counts(fasce, FASCE),
        "fattori": published_counts(fattori, FATTORI),
        "denuncia": published_counts(denuncia, DENUNCIA),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/build_sicurezza.py <output.json>")
    client = firestore.Client(project=PROJECT_ID)
    now = datetime.now(timezone.utc)
    deleted = delete_expired(client, now)
    data = build(client, now)
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Scritto {sys.argv[1]}: {data['totale']} segnalazioni negli ultimi {FINESTRA_GIORNI} giorni, {deleted} cancellate perché oltre i {CONSERVAZIONE_GIORNI} giorni")
