"""Conteggi pubblici della sezione Sicurezza, dalle segnalazioni su Firestore.

Uso: GOOGLE_APPLICATION_CREDENTIALS=chiave.json python scripts/build_sicurezza.py data/sicurezza.json

Gira ogni notte nel workflow sicurezza.yml con un account di servizio (ruolo Cloud Datastore User).
Pubblica solo conteggi degli ultimi 90 giorni per quadrato della mappa, tipo e fascia, presi separatamente,
e nasconde quelli sotto SOGLIA (i quadrati sotto soglia non compaiono proprio). Cancella le segnalazioni più vecchie di 12 mesi, come dice privacy.html.
Gli elenchi devono coincidere con firestore.rules e js/sicurezza-config.js.
"""
import json
import sys
from collections import Counter
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


def published_counts(counter, keys):
    """0 resta 0; da 1 a SOGLIA-1 diventa None (la pagina mostra "meno di SOGLIA")."""
    return {k: (None if 0 < counter[k] < SOGLIA else counter[k]) for k in keys}


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
    celle, categorie, fasce = Counter(), Counter(), Counter()
    totale = 0
    for doc in docs:
        d = doc.to_dict()
        totale += 1
        celle[d.get("cella")] += 1
        categorie[d.get("categoria")] += 1
        fasce[d.get("fascia")] += 1
    return {
        "generato": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finestra_giorni": FINESTRA_GIORNI,
        "da": start.strftime("%Y-%m-%d"),
        "a": now.strftime("%Y-%m-%d"),
        "soglia": SOGLIA,
        "totale": totale,
        # Quadrati di scripts/build_mappa.py, dal più segnalato
        "celle": {k: n for k, n in celle.most_common() if k and n >= SOGLIA},
        "categorie": published_counts(categorie, CATEGORIE),
        "fasce": published_counts(fasce, FASCE),
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
