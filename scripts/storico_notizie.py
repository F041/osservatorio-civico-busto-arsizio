"""Recupero una tantum degli articoli passati, per la prova del motore prima di avere settimane di raccolta.

Uso: python scripts/storico_notizie.py articoli.jsonl [giorni]   (giorni: 30 se non indicato)

Scrive nello stesso formato di raccogli_notizie.py e salta i link già presenti. Si lancia a mano.
Archivi usati, verificati a novembre 2026:
- ilBustese: mappa del sito (circa 5 settimane, con titoli e date), sezioni Cronaca e Busto.
- Malpensa24: API WordPress della categoria 12, una pagina da 100 articoli alla volta.
- Prealpina: mappa del sito della sezione Busto e Valle Olona; non ha titoli, si ricavano dal link.
- VareseNews: pagine del tag Busto, all'indietro; le date vengono dalle mappe mensili del sito.
Fra una richiesta e l'altra alla stessa testata passa PAUSA secondi.
"""
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from raccogli_notizie import MALPENSA24, SITEMAP_NS, VARESENEWS_TAG, articolo, pulisci, scarica, unisci  # noqa: E402

PAUSA = 1.5
ILBUSTESE_SITEMAP = 'https://www.ilbustese.it/sitemap.xml'
ILBUSTESE_SEZIONI = ('/argomenti/cronaca-26/', '/argomenti/busto-1/')
PREALPINA_SITEMAP = 'https://www.prealpina.it/siteMap.jsp'
VARESENEWS_MESE = 'https://www.varesenews.it/sitemap-pt-post-{:%Y-%m}.xml'
MAX_PAGINE_TAG = 40


def data_iso(testo):
    """Data delle mappe del sito in UTC, come le altre fonti."""
    return datetime.fromisoformat(testo).astimezone(timezone.utc).isoformat() if testo else None


def ilbustese(dal):
    out = []
    for voce in ET.fromstring(scarica(ILBUSTESE_SITEMAP)).findall('s:url', SITEMAP_NS):
        url = voce.findtext('s:loc', default='', namespaces=SITEMAP_NS)
        if not any(s in url for s in ILBUSTESE_SEZIONI):
            continue
        # Solo gli ultimi giorni hanno i dati di Google News; per gli altri la data sta nel link (/2026/10/09/)
        data = data_iso(voce.findtext('n:news/n:publication_date', namespaces=SITEMAP_NS))
        giorno = re.search(r'/(20\d\d)/(\d\d)/(\d\d)/', url)
        if not data and giorno:
            data = datetime(*map(int, giorno.groups()), tzinfo=timezone.utc).isoformat()
        if data and data >= dal:
            titolo = (voce.findtext('n:news/n:title', namespaces=SITEMAP_NS)
                      or url.rsplit('/', 1)[-1].removesuffix('.html').replace('-', ' '))
            out.append(articolo('ilbustese', url, titolo, pubblicato=data))
    return out


def malpensa24(dal):
    out = []
    for pagina in range(1, 30):
        posts = json.loads(scarica(f'{MALPENSA24}&page={pagina}'))
        for p in posts:
            data = p['date_gmt'] + '+00:00'
            if data >= dal:
                out.append(articolo('malpensa24', p['link'], p['title']['rendered'], p['excerpt']['rendered'],
                                    data, ['BUSTO | VALLE OLONA']))
        if not posts or posts[-1]['date_gmt'] + '+00:00' < dal:
            return out
        time.sleep(PAUSA)
    return out


def prealpina(dal):
    indice = ET.fromstring(scarica(PREALPINA_SITEMAP))
    mappe = sorted(m.findtext('s:loc', namespaces=SITEMAP_NS) for m in indice.findall('s:sitemap', SITEMAP_NS)
                   if '/28_busto-valle-olona_' in m.findtext('s:loc', namespaces=SITEMAP_NS))
    out = []
    # Le mappe sono numerate dalla più vecchia: si parte dall'ultima e ci si ferma quando sono tutte prima di `dal`
    for mappa in reversed(mappe):
        time.sleep(PAUSA)
        recenti = 0
        for voce in ET.fromstring(scarica(mappa)).findall('s:url', SITEMAP_NS):
            url = voce.findtext('s:loc', default='', namespaces=SITEMAP_NS)
            data = data_iso(voce.findtext('s:lastmod', namespaces=SITEMAP_NS))
            if data and data >= dal:
                recenti += 1
                titolo = url.rsplit('/', 1)[-1].removesuffix('.html').replace('-', ' ')
                out.append(articolo('prealpina', url, titolo, pubblicato=data))
        if not recenti:
            break
    return out


def varesenews(dal):
    # Date di pubblicazione dalle mappe mensili (il tag non le mostra)
    date = {}
    mese = datetime.now(timezone.utc).replace(day=1)
    inizio = datetime.fromisoformat(dal).replace(day=1)
    while mese >= inizio:
        for voce in ET.fromstring(scarica(VARESENEWS_MESE.format(mese))).findall('s:url', SITEMAP_NS):
            date[voce.findtext('s:loc', namespaces=SITEMAP_NS)] = data_iso(voce.findtext('s:lastmod', namespaces=SITEMAP_NS))
        mese = (mese - timedelta(days=1)).replace(day=1)
        time.sleep(PAUSA)

    out = []
    visti = set()
    for pagina in range(1, MAX_PAGINE_TAG + 1):
        html = scarica(VARESENEWS_TAG if pagina == 1 else f'{VARESENEWS_TAG}page/{pagina}/').decode('utf-8', errors='replace')
        # Ogni pagina ripete in cima gli articoli in evidenza: conta solo i link non ancora visti
        trovati = 0
        for blocco in re.findall(r'<article[^>]*>(.*?)</article>', html, re.S):
            link = re.search(r'href="(https://www\.varesenews\.it/20\d\d/\d\d/[^"/]+/\d+/)"', blocco)
            if not link or link.group(1) in visti:
                continue
            visti.add(link.group(1))
            testi = [pulisci(t) for t in re.findall(r'<a[^>]*href="' + re.escape(link.group(1)) + r'"[^>]*>(.*?)</a>', blocco, re.S)]
            titolo = max(testi, key=len, default='')
            if titolo.startswith('»'):
                continue
            data = date.get(link.group(1))
            if data and data >= dal:
                trovati += 1
                out.append(articolo('varesenews', link.group(1),
                                    titolo or link.group(1).rstrip('/').split('/')[-2].replace('-', ' '), pubblicato=data))
        if not trovati:
            break
        time.sleep(PAUSA)
    return out


def main(percorso, giorni=30):
    dal = (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat()
    print(f'Articoli pubblicati dal {dal[:10]}')
    unisci(percorso, [ilbustese, malpensa24, prealpina, varesenews], dal)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30)
