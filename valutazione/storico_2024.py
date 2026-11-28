"""Elenco degli articoli del 2024 prima della finestra della raccolta, per gli studi statistici (pagina studi.html).
Solo in locale: niente Firestore, perché la raccolta cancella gli articoli oltre CONSERVAZIONE_GIORNI e li toglierebbe
il giorno dopo. Il recupero del 2026 (storico_2026.py) parte dal 27/11/2024: qui si va dal 1/1/2024 al giorno prima.

Uso, dalla cartella del repo:
  uv run --no-project --python 3.12 python -I valutazione/storico_2024.py veloci
  ... storico_2024.py ilbustese

veloci: Malpensa24, VareseNews e Prealpina, una testata alla volta; una testata già letta non si rilegge (file .fatto).
ilbustese: l'archivio un giorno alla volta, dal più recente. Il sito rallenta le richieste in blocco (circa 30 secondi
  l'una): si può interrompere quando si vuole e riparte dal primo giorno mancante. Va lanciato quando il recupero del
  2026 non sta scaricando da ilBustese (valutazione/riprendi_2024.sh aspetta da solo).
L'elenco finisce in valutazione/dati/articoli-2024.jsonl (esclusa da git), con gli stessi campi di quello del 2026.
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

QUI = Path(__file__).parent
DATI = QUI / 'dati'
sys.path.insert(0, str(QUI.parent / 'scripts'))
import storico_notizie as s  # noqa: E402

DAL = date(2024, 1, 1)
# Escluso: da qui in avanti ci sono il recupero del 2026 e la raccolta
FINO = date(2024, 11, 27)
ELENCO = DATI / 'articoli-2024.jsonl'
CACHE = DATI / 'ilbustese-archivio-2024.jsonl'
GIA = ('articoli-2026.jsonl', 'articoli-2026-ilbustese.jsonl')


def nel_periodo(a):
    return DAL.isoformat() <= (a.get('pubblicato') or '')[:10] < FINO.isoformat()


def aggiungi(articoli):
    """Aggiunge all'elenco gli articoli del periodo non ancora presenti; `visto` è la data di uscita, come serve a
    prepara_campione.py."""
    noti = set()
    for nome in (ELENCO.name, *GIA):
        if (DATI / nome).exists():
            noti |= {json.loads(r)['url'] for r in open(DATI / nome, encoding='utf-8') if r.strip()}
    nuovi = {}
    for a in articoli:
        if a.get('url') and a['url'] not in noti and nel_periodo(a):
            nuovi[a['url']] = {'fonte': a['fonte'], 'url': a['url'], 'titolo': a.get('titolo', ''),
                               'pubblicato': a['pubblicato'], 'visto': a['pubblicato']}
    with open(ELENCO, 'a', encoding='utf-8', newline='\n') as f:
        f.writelines(json.dumps(a, ensure_ascii=False) + '\n' for a in nuovi.values())
    return len(nuovi)


def veloci():
    DATI.mkdir(exist_ok=True)
    # Le pagine per testata bastano per la finestra della raccolta, non per arrivare a gennaio 2024
    s.MAX_PAGINE_MALPENSA24 = 2000
    s.MAX_PAGINE_TAG = 2000
    # Le date già note evitano di riaprire migliaia di pagine di Prealpina
    for nome in GIA[:1]:
        if (DATI / nome).exists():
            s.DATE_NOTE.update({a['url']: a['pubblicato'] for a in map(json.loads, open(DATI / nome, encoding='utf-8'))
                                if a.get('pubblicato')})
    for nome in ('malpensa24', 'varesenews', 'prealpina'):
        fatto = DATI / f'articoli-2024-{nome}.fatto'
        if fatto.exists():
            print(f'{nome}: già letto', flush=True)
            continue
        inizio = time.time()
        try:
            elenco = s.FONTI[nome](f'{DAL.isoformat()}T00:00:00+00:00')
        except Exception as err:
            print(f'::warning::{nome}: {err}', flush=True)
            continue
        print(f'{nome}: {aggiungi(elenco)} articoli del 2024 in {(time.time() - inizio) / 60:.0f} minuti', flush=True)
        fatto.touch()


def ilbustese():
    DATI.mkdir(exist_ok=True)
    letti = set()
    if CACHE.exists():
        letti = {json.loads(r)['giorno'] for r in open(CACHE, encoding='utf-8') if r.strip()}
    giorni = []
    giorno = FINO - timedelta(days=1)
    while giorno >= DAL:
        if giorno.isoformat() not in letti:
            giorni.append(giorno)
        giorno -= timedelta(days=1)
    print(f'ilbustese 2024: {len(letti)} giorni già letti, {len(giorni)} da leggere', flush=True)
    for i, giorno in enumerate(giorni, 1):
        inizio = time.time()
        try:
            articoli = s.ilbustese_archivio(giorno.isoformat(), (giorno + timedelta(days=1)).isoformat())
        except Exception as err:
            # Il giorno resta mancante e si riprova al giro dopo
            print(f'::warning::ilbustese {giorno:%d/%m/%Y}: {err}', flush=True)
            continue
        aggiungi(articoli)
        with open(CACHE, 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps({'giorno': giorno.isoformat(), 'articoli': articoli}, ensure_ascii=False) + '\n')
        print(f'ilbustese {giorno:%d/%m/%Y}: {len(articoli)} articoli in {time.time() - inizio:.0f}s '
              f'({i}/{len(giorni)})', flush=True)


if __name__ == '__main__':
    comando = sys.argv[1] if len(sys.argv) > 1 else ''
    if comando == 'veloci':
        veloci()
    elif comando == 'ilbustese':
        ilbustese()
    else:
        sys.exit(__doc__)
