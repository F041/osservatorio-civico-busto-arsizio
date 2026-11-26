"""Recupero dell'elenco degli articoli di tutto il 2026, per la prova del motore. Solo in locale, con le credenziali
gcloud di chi lo lancia (niente file di chiavi). Non stampa link.

Uso, dalla cartella del repo:
  uv run --no-project --python 3.12 --with google-cloud-firestore==2.34.1 python -I valutazione/storico_2026.py veloci \
      [valutazione/dati/articoli-2026.jsonl]
  ... storico_2026.py ilbustese
  ... storico_2026.py esporta valutazione/dati/articoli-2026.jsonl [fonte]

Il recupero copre quanto la raccolta tiene gli articoli e mostra la mappa (CONSERVAZIONE_GIORNI in
scripts/raccogli_notizie.py, 24 mesi dal 26/11/2026). Nato per il 2026, da qui i nomi dei file.
veloci: Malpensa24, VareseNews e Prealpina dall'inizio della finestra, in un solo giro (qualche ora per Prealpina).
ilbustese: l'archivio un giorno alla volta, dal 25/08 (i giorni dopo sono già nell'elenco) indietro fino all'inizio
  della finestra, al massimo MAX_GIORNI giorni per giro.
  Il sito rallenta le richieste in blocco (circa 30 secondi l'una), quindi servono più giorni. Ogni giorno letto finisce
  subito in valutazione/dati/ilbustese-archivio.jsonl: si può interrompere quando si vuole e al giro dopo riparte dal
  primo giorno mancante. I giorni con un errore restano mancanti e si riprovano al giro dopo. I giorni già scritti in
  Firestore sono in valutazione/dati/ilbustese-scritti.txt, così al giro dopo non si rileggono.
esporta: la copia locale dell'elenco, di una sola testata se c'è `fonte`.
L'elenco va in Firestore con un token gcloud nuovo a ogni scrittura: un token dura circa un'ora.

Firestore gratuito ha una quota al giorno (50.000 letture, 20.000 scritture), che si azzera alle 9 italiane, e la
raccolta delle 14:28 su GitHub usa la stessa. Il 26/11/2026 il recupero l'ha finita e la raccolta è fallita: per
questo i giri hanno un tetto e un'esportazione legge una testata sola. Con la quota finita lo script si ferma.
"""
import json
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

QUI = Path(__file__).parent
DATI = QUI / 'dati'
sys.path.insert(0, str(QUI.parent / 'scripts'))
import raccogli_notizie as r  # noqa: E402
import storico_notizie as s  # noqa: E402

INIZIO = date.today() - timedelta(days=r.CONSERVAZIONE_GIORNI)
DAL = f'{INIZIO.isoformat()}T00:00:00+00:00'
ILBUSTESE_DA = date(2026, 8, 25)
ILBUSTESE_FINO = INIZIO
CACHE = DATI / 'ilbustese-archivio.jsonl'
SCRITTI = DATI / 'ilbustese-scritti.txt'
SCRIVI_OGNI = 7
# Circa 1.500 articoli: altrettante letture e scritture, lontano dalla quota giornaliera
MAX_GIORNI = 100
QUOTA_FINITA = ('Quota giornaliera di Firestore finita: si azzera alle 9 italiane. Rilanciare dopo, lontano dalla '
                'raccolta delle 14:28.')


def client():
    from google.cloud import firestore
    from google.oauth2.credentials import Credentials
    gcloud = shutil.which('gcloud') or shutil.which('gcloud.cmd')
    token = subprocess.run([gcloud, 'auth', 'print-access-token'], capture_output=True, text=True, check=True).stdout.strip()
    return firestore.Client(project=r.PROJECT_ID, credentials=Credentials(token))


def scrivi(nome, elenco):
    from google.api_core.exceptions import ResourceExhausted

    def fonte(*_):
        return elenco
    fonte.__name__ = nome
    try:
        r.unisci(client(), [fonte])
    except ResourceExhausted:
        sys.exit(QUOTA_FINITA)


def esporta(percorso, fonte=None):
    from google.api_core.exceptions import ResourceExhausted
    from google.cloud.firestore_v1.base_query import FieldFilter
    query = client().collection(r.COLLEZIONE)
    if fonte:
        query = query.where(filter=FieldFilter('fonte', '==', fonte))
    try:
        righe = sorted((d.to_dict() for d in query.stream()), key=lambda a: (a['visto'], a['url']))
    except ResourceExhausted:
        sys.exit(QUOTA_FINITA)
    # Il file vecchio resta finché il nuovo non è completo
    nuovo = Path(f'{percorso}.nuovo')
    with open(nuovo, 'w', encoding='utf-8', newline='\n') as f:
        for a in righe:
            f.write(json.dumps({k: a.get(k) for k in r.CAMPI_SALVATI}, ensure_ascii=False) + '\n')
    nuovo.replace(percorso)
    print(f'Esportati {len(righe)} articoli in {percorso}')


def veloci(noti=None):
    # Le date già note da un'esportazione precedente evitano di riaprire migliaia di pagine di Prealpina
    if noti and Path(noti).exists():
        s.DATE_NOTE.update({a['url']: a['pubblicato'] for a in map(json.loads, open(noti, encoding='utf-8'))
                            if a.get('pubblicato')})
        print(f'{len(s.DATE_NOTE)} date già note', flush=True)
    for nome in ('malpensa24', 'varesenews', 'prealpina'):
        inizio = time.time()
        try:
            elenco = s.FONTI[nome](DAL)
        except Exception as err:
            print(f'::warning::{nome}: {err}', flush=True)
            continue
        print(f'{nome}: elenco letto in {(time.time() - inizio) / 60:.0f} minuti', flush=True)
        scrivi(nome, elenco)


def ilbustese():
    DATI.mkdir(exist_ok=True)
    letti = {}
    if CACHE.exists():
        letti = {d['giorno']: d['articoli'] for d in map(json.loads, open(CACHE, encoding='utf-8'))}
    if SCRITTI.exists():
        scritti = set(SCRITTI.read_text(encoding='utf-8').split())
    else:
        # Prima di questo file ogni giro riscriveva tutto: era rimasto fuori al più l'ultimo blocco di giorni
        scritti = set(list(letti)[:-SCRIVI_OGNI])
        segna(scritti)

    # Quello letto in un giro interrotto prima della scrittura: unisci salta i link già presenti
    mancanti = [g for g in letti if g not in scritti]
    if mancanti:
        scrivi('ilbustese', [a for g in mancanti for a in letti[g]])
        segna(mancanti)
    giorni = []
    giorno = ILBUSTESE_DA
    while giorno >= ILBUSTESE_FINO:
        if giorno.isoformat() not in letti:
            giorni.append(giorno)
        giorno -= timedelta(days=1)
    print(f'ilbustese: {len(letti)} giorni già letti, {len(giorni)} da leggere, al massimo {MAX_GIORNI} in questo giro',
          flush=True)
    giorni = giorni[:MAX_GIORNI]

    da_scrivere, giorni_da_scrivere = [], []
    for i, giorno in enumerate(giorni, 1):
        inizio = time.time()
        try:
            articoli = s.ilbustese_archivio(giorno.isoformat(), (giorno + timedelta(days=1)).isoformat())
        except Exception as err:
            print(f'::warning::ilbustese {giorno:%d/%m}: {err}', flush=True)
            continue
        with open(CACHE, 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps({'giorno': giorno.isoformat(), 'articoli': articoli}, ensure_ascii=False) + '\n')
        da_scrivere += articoli
        giorni_da_scrivere.append(giorno.isoformat())
        print(f'ilbustese {giorno:%d/%m/%Y}: {len(articoli)} articoli in {time.time() - inizio:.0f}s '
              f'({i}/{len(giorni)})', flush=True)
        if i % SCRIVI_OGNI == 0:
            scrivi('ilbustese', da_scrivere)
            segna(giorni_da_scrivere)
            da_scrivere, giorni_da_scrivere = [], []
    if giorni_da_scrivere:
        scrivi('ilbustese', da_scrivere)
        segna(giorni_da_scrivere)


def segna(giorni):
    with open(SCRITTI, 'a', encoding='utf-8', newline='\n') as f:
        f.writelines(f'{g}\n' for g in giorni)


if __name__ == '__main__':
    comando = sys.argv[1]
    if comando == 'veloci':
        veloci(sys.argv[2] if len(sys.argv) > 2 else None)
    elif comando == 'ilbustese':
        ilbustese()
    elif comando == 'esporta':
        esporta(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        sys.exit(__doc__)
