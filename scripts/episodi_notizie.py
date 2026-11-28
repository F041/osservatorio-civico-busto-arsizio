"""Episodi trovati dal modello negli articoli, nella collezione Firestore `notizie_episodi` (chiusa al sito come
`notizie_articoli`: i link contengono i titoli). L'analisi gira sul PC, con Claude e l'abbonamento; la pubblicazione
del sito (.github/workflows/pubblica.yml) li legge da qui e scrive data/notizie.json senza metterlo nel repo.

Uso: python scripts/episodi_notizie.py carica episodi.jsonl     (sul PC, con gcloud)
     GOOGLE_APPLICATION_CREDENTIALS=chiave.json python scripts/episodi_notizie.py esporta episodi.jsonl

`episodi.jsonl` ha una riga per articolo analizzato: fonte, url, pubblicato ed episodi (il formato di
scripts/build_notizie.py). Si salvano solo gli articoli con almeno un episodio, così la pubblicazione legge poche
centinaia di documenti e non le migliaia di articoli analizzati: la quota gratuita è di 50.000 letture al giorno.
Il primo giorno analizzato, che dice da quando parte la mappa, sta nel documento `_copertura`.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from raccogli_notizie import PROJECT_ID, CONSERVAZIONE_GIORNI, a_blocchi, client_firestore, id_articolo  # noqa: E402

COLLEZIONE = 'notizie_episodi'
COPERTURA = '_copertura'
CAMPI = ('fonte', 'url', 'pubblicato', 'episodi')
# Riassunti e sottotipi dei fatti, scritti a parte da scripts/riassunti_notizie.py: {"tipo|via|giorno": testo} e
# {"tipo|via|giorno": "casa" | "rifiuti" | "nessuno"}
RIASSUNTI = 'riassunti'
SOTTOTIPI = 'sottotipi'
AGGIUNTI = (RIASSUNTI, SOTTOTIPI)


def client():
    """Sulle Actions la chiave dell'account di servizio (GOOGLE_APPLICATION_CREDENTIALS); sul PC l'accesso gcloud di
    chi lo lancia, senza file di chiavi."""
    if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        return client_firestore()
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials
    gcloud = shutil.which('gcloud') or shutil.which('gcloud.cmd')
    token = subprocess.run([gcloud, 'auth', 'print-access-token'], capture_output=True, text=True, check=True).stdout.strip()
    return firestore.Client(project=PROJECT_ID, credentials=Credentials(token))


def leggi(percorso):
    with open(percorso, encoding='utf-8') as f:
        return [json.loads(r) for r in f if r.strip()]


def carica(client, righe):
    """Scrive gli articoli con episodi nuovi o cambiati, toglie quelli che un'analisi nuova ha svuotato e quelli
    usciti da più di CONSERVAZIONE_GIORNI. Scrive solo quello che cambia: le scritture gratuite sono 20.000 al giorno."""
    raccolta = client.collection(COLLEZIONE)
    salvati = {d.id: d.to_dict() for d in raccolta.stream()}
    copertura = salvati.pop(COPERTURA, {}).get('da')
    limite = (datetime.now(timezone.utc) - timedelta(days=CONSERVAZIONE_GIORNI)).date().isoformat()

    scrivi, togli = {}, set()
    for r in righe:
        i = id_articolo(r['url'])
        voce = {k: r.get(k) for k in CAMPI}
        # Un'analisi nuova non ha riassunti e sottotipi: si tengono quelli già scritti
        for campo in AGGIUNTI:
            valori = {**(salvati.get(i) or {}).get(campo, {}), **(r.get(campo) or {})}
            if valori:
                voce[campo] = valori
        if r['episodi'] and (voce['pubblicato'] or '')[:10] >= limite:
            if salvati.get(i) != voce:
                scrivi[i] = voce
        elif i in salvati:
            togli.add(i)
    togli |= {i for i, v in salvati.items() if (v.get('pubblicato') or '')[:10] < limite}

    analizzati = [g for g in ((r.get('pubblicato') or '')[:10] for r in righe) if g]
    nuova_copertura = max(min([copertura, *analizzati] if copertura else analizzati, default=limite), limite)

    operazioni = [('set', i, v) for i, v in scrivi.items()] + [('delete', i, None) for i in togli]
    if nuova_copertura != copertura:
        operazioni.append(('set', COPERTURA, {'da': nuova_copertura}))
    for blocco in a_blocchi(operazioni):
        batch = client.batch()
        for tipo, i, v in blocco:
            if tipo == 'set':
                batch.set(raccolta.document(i), v)
            else:
                batch.delete(raccolta.document(i))
        batch.commit()
    print(f'{len(scrivi)} articoli scritti, {len(togli)} tolti, {len(salvati) + len(scrivi) - len(togli & set(salvati))} '
          f'in collezione (circa), mappa dal {nuova_copertura}')


def esporta(client, percorso):
    """Una riga per articolo con episodi, più in testa una riga senza episodi col primo giorno analizzato: a
    build_notizie.py serve per sapere da quando parte la serie."""
    righe, da = [], None
    for d in client.collection(COLLEZIONE).stream():
        if d.id == COPERTURA:
            da = d.to_dict().get('da')
        else:
            righe.append(d.to_dict())
    righe.sort(key=lambda r: (r.get('pubblicato') or '', r['url']))
    if da:
        righe.insert(0, {'fonte': '', 'url': '', 'pubblicato': da, 'episodi': []})
    with open(percorso, 'w', encoding='utf-8', newline='\n') as f:
        for r in righe:
            f.write(json.dumps({k: r[k] for k in (*CAMPI, *AGGIUNTI) if k in r}, ensure_ascii=False) + '\n')
    print(f'Esportati {len(righe) - bool(da)} articoli con episodi, analisi dal {da}')


def aggiungi_riassunti(client, nuovi, campo=RIASSUNTI):
    """nuovi: {url: {chiave: valore}}, nel campo `riassunti` o `sottotipi`. Scrive solo gli articoli che cambiano."""
    raccolta = client.collection(COLLEZIONE)
    operazioni = []
    for url, testi in nuovi.items():
        rif = raccolta.document(id_articolo(url))
        doc = rif.get()
        if not doc.exists:
            continue
        voce = doc.to_dict()
        unione = {**voce.get(campo, {}), **testi}
        if unione != voce.get(campo):
            operazioni.append((rif, {**voce, campo: unione}))
    for blocco in a_blocchi(operazioni):
        batch = client.batch()
        for rif, voce in blocco:
            batch.set(rif, voce)
        batch.commit()
    print(f'{campo.capitalize()} scritti in {len(operazioni)} articoli')


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('carica', 'esporta'):
        sys.exit(__doc__)
    if sys.argv[1] == 'carica':
        carica(client(), leggi(sys.argv[2]))
    else:
        esporta(client(), sys.argv[2])
