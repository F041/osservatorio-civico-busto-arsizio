"""Recupero una tantum degli articoli passati, per la prova del motore prima di avere settimane di raccolta.

Uso: GOOGLE_APPLICATION_CREDENTIALS=chiave.json python scripts/storico_notizie.py [giorni] [testate...]
     (30 giorni e tutte le testate se non indicati; testate: ilbustese malpensa24 prealpina varesenews)

Scrive nella stessa collezione di raccogli_notizie.py e salta i link già presenti. Si lancia a mano.
Archivi usati, verificati a novembre 2026:
- ilBustese: mappa del sito (circa 5 settimane, con titoli e date), sezioni Cronaca e Busto; per i giorni prima,
  la ricerca dell'archivio un giorno alla volta, 20 articoli per pagina.
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
from raccogli_notizie import (MALPENSA24, SITEMAP_NS, VARESENEWS_TAG, articolo, client_firestore, pulisci,  # noqa: E402
                              scarica, scarica_entro, unisci)

PAUSA = 1.5
ILBUSTESE_SITEMAP = 'https://www.ilbustese.it/sitemap.xml'
ILBUSTESE_SEZIONI = ('/argomenti/cronaca-26/', '/argomenti/busto-1/')
PREALPINA_SITEMAP = 'https://www.prealpina.it/siteMap.jsp'
VARESENEWS_MESE = 'https://www.varesenews.it/sitemap-pt-post-{:%Y-%m}.xml'
MAX_PAGINE_TAG = 400
MAX_PAGINE_MALPENSA24 = 80
# Link già noti con la data di pubblicazione: Prealpina non riapre quelle pagine. Lo riempie chi chiama
DATE_NOTE = {}
ILBUSTESE_ARCHIVIO = 'https://www.ilbustese.it/nc/istituzionale/archivio/argomenti/{sezione}{pagina}.html?{query}'
ILBUSTESE_LINK = re.compile(r'<a href="(https://www\.ilbustese\.it/20\d\d/\d\d/\d\d/leggi-notizia/[^"]+)" title="([^"]*)"')


def data_iso(testo):
    """Data delle mappe del sito in UTC, come le altre fonti."""
    return datetime.fromisoformat(testo).astimezone(timezone.utc).isoformat() if testo else None


def ilbustese_archivio(dal, fino):
    """Sezioni Busto e Cronaca dalla ricerca dell'archivio, un giorno alla volta, da `dal` al giorno prima di `fino`."""
    out, giorno = {}, datetime.fromisoformat(dal).date()
    while giorno.isoformat() < fino[:10]:
        query = f'tx_ttnews%5Bstart_full%5D={giorno}&tx_ttnews%5Bend_full%5D={giorno}'
        data = datetime(giorno.year, giorno.month, giorno.day, tzinfo=timezone.utc).isoformat()
        for sezione in ('busto-1', 'cronaca-26'):
            for pagina in range(10):
                time.sleep(PAUSA)
                html = scarica_entro(ILBUSTESE_ARCHIVIO.format(sezione=sezione, pagina=f'/browse/{pagina}' if pagina else '',
                                                         query=query)).decode('utf-8', errors='replace')
                nuovi = 0
                for url, titolo in ILBUSTESE_LINK.findall(html):
                    if url not in out:
                        nuovi += 1
                        out[url] = articolo('ilbustese', url, titolo, pubblicato=data)
                # Pagina non piena: il giorno è finito
                if nuovi < 20:
                    break
        giorno += timedelta(days=1)
    return list(out.values())


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
    # La mappa del sito tiene poche settimane: i giorni prima vengono dall'archivio
    primo = min((a['pubblicato'] for a in out), default=datetime.now(timezone.utc).isoformat())
    if primo[:10] > dal[:10]:
        out += ilbustese_archivio(dal, primo)
    return out


def malpensa24(dal):
    out = []
    for pagina in range(1, MAX_PAGINE_MALPENSA24 + 1):
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
    mappe = sorted((m.findtext('s:loc', namespaces=SITEMAP_NS) for m in indice.findall('s:sitemap', SITEMAP_NS)
                    if '/28_busto-valle-olona_' in m.findtext('s:loc', namespaces=SITEMAP_NS)),
                   key=lambda u: int(re.search(r'_(\d+)\.xml', u).group(1)))
    out = []
    titolo = lambda url: url.rsplit('/', 1)[-1].removesuffix('.html').replace('-', ' ')
    # Le mappe sono numerate dalla più vecchia: si parte dall'ultima e ci si ferma quando sono tutte prima di `dal`
    for mappa in reversed(mappe):
        time.sleep(PAUSA)
        voci = [(v.findtext('s:loc', default='', namespaces=SITEMAP_NS),
                 data_iso(v.findtext('s:lastmod', namespaces=SITEMAP_NS)))
                for v in ET.fromstring(scarica(mappa)).findall('s:url', SITEMAP_NS)]
        if not any(data for _, data in voci):
            # Le mappe vecchie non hanno date (verificato a novembre 2026): il numero dell'articolo cresce nel tempo, si
            # leggono le pagine dalla più recente e ci si ferma alla prima pubblicata prima di `dal`, anche nelle mappe
            # precedenti
            nuovi, finito = prealpina_senza_date([u for u, _ in voci], dal, {a['url'] for a in out}, titolo)
            out += nuovi
            print(f'prealpina: {mappa.rsplit("/", 1)[-1]}, {len(nuovi)} articoli', flush=True)
            if finito:
                break
            continue
        recenti = 0
        for url, data in voci:
            if data and data >= dal:
                recenti += 1
                out.append(articolo('prealpina', url, titolo(url), pubblicato=data))
        if not recenti:
            break
    return out


def prealpina_senza_date(urls, dal, gia, titolo):
    """Articoli dal `dal` in una mappa senza date, e se la lettura si è fermata prima della fine della mappa."""
    numero = lambda u: int(re.search(r'/news/busto-valle-olona/(\d+)/', u).group(1))
    out = []
    for i, url in enumerate(sorted((u for u in urls if '/news/busto-valle-olona/' in u and u not in gia),
                                   key=numero, reverse=True), 1):
        # Le date già note (dai recuperi precedenti) non richiedono di riaprire la pagina
        data = DATE_NOTE.get(url)
        if not data:
            time.sleep(PAUSA)
            try:
                trovata = re.search(r'article:published_time" content="([^"]+)"',
                                    scarica(url).decode('utf-8', errors='replace'))
            except Exception as err:
                print(f'::warning::prealpina: {err}', flush=True)
                continue
            if not trovata:
                continue
            data = data_iso(trovata.group(1))
        if data < dal:
            return out, True
        out.append(articolo('prealpina', url, titolo(url), pubblicato=data))
        if i % 200 == 0:
            print(f'prealpina: {i} pagine lette, arrivato al {data[:10]}', flush=True)
    return out, False


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


FONTI = {f.__name__: f for f in (ilbustese, malpensa24, prealpina, varesenews)}


def main(giorni=30, fonti=()):
    """`fonti` limita il recupero ad alcune testate: ilBustese rallenta molto le richieste in blocco e va da sola."""
    dal = (datetime.now(timezone.utc) - timedelta(days=giorni)).isoformat()
    print(f'Articoli pubblicati dal {dal[:10]}')
    unisci(client_firestore(), [FONTI[f] for f in (fonti or FONTI)], dal)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2:])
