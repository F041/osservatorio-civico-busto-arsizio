"""Precalcola i dati di cruscotto.html dal database dei pagamenti.

Uso: python scripts/build_cruscotto.py busto_pagamenti.db data/cruscotto.json

Solo libreria standard: gira così com'è anche nel workflow di aggiornamento.
La pagina carica qualche decina di KB di JSON invece dei ~20 MB del database.
"""
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

PARTECIPATE = "Partecipate"
ENTI_CONTROLLATI = "Enti controllati e vigilati"
ALTRI_PUBBLICI = "Altri enti pubblici"
PERSONALE_FISCO = "Personale, fisco e giroconti"
PRIVATI = "Privati"
CATEGORIE = [PARTECIPATE, ENTI_CONTROLLATI, ALTRI_PUBBLICI, PERSONALE_FISCO, PRIVATI]

# Fonte: Amministrazione trasparente del Comune > Enti controllati
# (Società partecipate agg. 11/2025, Enti di diritto privato controllati agg. 12/2025,
# Enti pubblici vigilati agg. 11/2025). Le regole lavorano sul nome normalizzato (vedi normalize_name).
# Terzo elemento: nota mostrata in pagina per i soggetti non più presenti nell'elenco 2025.
CLASSIFICATION_RULES = [
    (r"^AGESP ATTIVITA' STRUMENTALI\b", PARTECIPATE, "Non più nell'elenco 2025"),
    (r"^AGESP SERVIZI\b", PARTECIPATE, "Non più nell'elenco 2025"),
    (r"^AGESP\b", PARTECIPATE, None),
    (r"^ALFA SRL$", PARTECIPATE, None),
    (r"\(ORA ALFA\)$", PARTECIPATE, "Confluita in ALFA srl"),
    (r"^PREALPI GAS SRL$", PARTECIPATE, None),
    (r"^PREALPI SERVIZI SRL\b", PARTECIPATE, None),
    (r"^NEUTALIA SRL$", PARTECIPATE, None),
    (r"^CENTRO TESSILE COTONIERO\b", PARTECIPATE, None),
    (r"^SEA SOCIETA' PA ESERCIZI AEROPORTUALI$", PARTECIPATE, None),
    (r"^ACCAM SPA$", PARTECIPATE, "Storica, predecessore di Neutalia"),
    (r"^CONSORZIO PARCO ALTO MILANESE\b", ENTI_CONTROLLATI, None),
    (r"^ASSOCIAZIONE DEL DISTRETTO URBANO DEL COMMERCIO\b", ENTI_CONTROLLATI, None),
    (r"^FONDAZIONE ISTITUTO INSUBRICO DI RICERCA PER LA VITA\b", ENTI_CONTROLLATI, None),
    # Mandati cumulativi (stipendi, tributi), ritenute e contributi, giroconti verso il Comune stesso
    (r"^DIVERSI\b", PERSONALE_FISCO, None),
    (r"^ERARIO\b", PERSONALE_FISCO, None),
    (r"^COMUNE DI BUSTO ARSIZIO\b", PERSONALE_FISCO, None),
    (r"^(INPDAP|INPS|INAIL)\b", PERSONALE_FISCO, None),
    (r"^AGENZIA DELLE ENTRATE\b", PERSONALE_FISCO, None),
    # Altri soggetti pubblici (regole ancorate: "PROVINCIA ITALIANA CONGREGAZIONE..." resta privato)
    (r"^CASSA DEPOSITI E PRESTITI\b", ALTRI_PUBBLICI, None),
    (r"^ISTITUTO PER IL CREDITO SPORTIVO\b", ALTRI_PUBBLICI, None),
    (r"^(REGIONE|PROVINCIA DI|COMUNE DI|MINISTERO|PREFETTURA|ATS|ASST|ALER)\b", ALTRI_PUBBLICI, None),
]
COMPILED_RULES = [(re.compile(pattern), categoria, nota) for pattern, categoria, nota in CLASSIFICATION_RULES]

TOP_PER_PERIOD = 100  # restano >= 20 privati anche togliendo i soggetti pubblici in cima


def normalize_name(name):
    """Chiave di raggruppamento: unisce varianti come 'SODEXO ITALIA S.P.A.' e 'SODEXO ITALIA SPA'."""
    name = name.upper().replace("’", "'").replace(".", "").replace(",", " ")
    return re.sub(r"\s+", " ", name).strip()


def classify(normalized_name):
    for pattern, categoria, nota in COMPILED_RULES:
        if pattern.search(normalized_name):
            return categoria, nota
    return PRIVATI, None


def build(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT Anno, Beneficiario, ImportoEuro, DataMandato FROM pagamenti "
        "WHERE Beneficiario IS NOT NULL AND ImportoEuro IS NOT NULL"
    ).fetchall()
    conn.close()

    variants = defaultdict(Counter)  # chiave -> conteggio varianti del nome originale
    totals = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))  # periodo -> chiave -> [importo, n]
    year_dates = defaultdict(list)
    for anno, beneficiario, importo, data in rows:
        key = normalize_name(beneficiario)
        variants[key][beneficiario.strip()] += 1
        for period in ("tutti", str(anno)):
            totals[period][key][0] += importo
            totals[period][key][1] += 1
        if data:
            year_dates[str(anno)].append(data[:10])

    output_periods = {}
    for period, by_key in totals.items():
        per_categoria = {c: [0.0, 0] for c in CATEGORIE}
        entries = []
        for key, (importo, n) in by_key.items():
            categoria, nota = classify(key)
            per_categoria[categoria][0] += importo
            per_categoria[categoria][1] += n
            entries.append({"b": variants[key].most_common(1)[0][0], "q": key, "cat": categoria,
                            "nota": nota, "imp": round(importo, 2), "n": n})
        entries.sort(key=lambda e: e["imp"], reverse=True)
        # Oltre la classifica servono tutte le partecipate/controllate, per la loro sezione
        kept = entries[:TOP_PER_PERIOD] + [e for e in entries[TOP_PER_PERIOD:] if e["cat"] in (PARTECIPATE, ENTI_CONTROLLATI)]
        for e in kept:
            if e["nota"] is None: del e["nota"]
        output_periods[period] = {
            "totale": round(sum(v[0] for v in per_categoria.values()), 2),
            "n": sum(v[1] for v in per_categoria.values()),
            "categorie": {c: {"imp": round(v[0], 2), "n": v[1]} for c, v in per_categoria.items()},
            "beneficiari": kept,
        }

    anni = sorted((p for p in output_periods if p != "tutti"), key=int, reverse=True)
    coperture = {a: {"da": min(year_dates[a]), "a": max(year_dates[a])} for a in anni if year_dates[a]}
    all_dates = [d for a in anni for d in year_dates[a]]
    return {
        "generato": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "periodo": {"da": min(all_dates), "a": max(all_dates)},
        "anni": anni,
        "coperture": coperture,
        "categorie": CATEGORIE,
        "periodi": output_periods,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python scripts/build_cruscotto.py <database.db> <output.json>")
    data = build(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Scritto {sys.argv[2]}: {len(data['anni'])} anni, periodo {data['periodo']['da']} - {data['periodo']['a']}")
