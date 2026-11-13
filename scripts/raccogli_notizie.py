"""Raccolta degli articoli di Busto Arsizio da quattro testate locali, per le segnalazioni dalle notizie.

Uso: python scripts/raccogli_notizie.py articoli.jsonl

Gira una volta al giorno nel workflow notizie.yml e scrive sul ramo `notizie`, non su main (così non
riparte la pubblicazione del sito). Salva solo i dati che le testate espongono nei loro elenchi: link,
titolo, riassunto, data e categorie. Il testo degli articoli non viene scaricato qui: lo legge, per i soli
candidati, il passo di analisi. Nessun modello linguistico in questo passo.

Ogni elenco deve coprire più di un giorno, così un giro in ritardo o saltato da GitHub perde poco.
Fonti e scelte, verificate a novembre 2026 (tra parentesi quanto copriva ogni elenco):
- ilBustese: feed delle sezioni Cronaca (3 giorni) e Busto (un giorno e mezzo). Il feed generale
  conteneva solo 7 ore.
- Malpensa24: API WordPress della categoria 12, BUSTO | VALLE OLONA (100 articoli, 17 giorni);
  il feed della categoria ne ha solo 2.
- Prealpina: nessun feed; mappa del sito per Google News, filtrata sulla sezione Busto e Valle Olona
  (quasi 3 giorni). La pagina della sezione mostra solo 8 articoli.
- VareseNews: il feed del tag Busto è vietato dal robots.txt (/*/feed/$). Si legge il feed generale,
  tenendo la categoria "Busto Arsizio/Altomilanese" (circa 20 ore), e la pagina del tag Busto per i
  restanti (circa 2 giorni, senza data né riassunto).
Le righe più vecchie di CONSERVAZIONE_GIORNI vengono cancellate, come le segnalazioni.
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = 'OsservatorioCivicoBusto/0.1 (+https://f041.github.io/osservatorio-civico-busto-arsizio/)'
CONSERVAZIONE_GIORNI = 365
MAX_SOMMARIO = 500

ILBUSTESE = ['https://www.ilbustese.it/links/rss/argomenti/cronaca-26/rss.xml',
             'https://www.ilbustese.it/links/rss/argomenti/busto-1/rss.xml']
MALPENSA24 = ('https://www.malpensa24.it/wp-json/wp/v2/posts?categories=12&per_page=100'
              '&_fields=link,date_gmt,title,excerpt')
PREALPINA = 'https://www.prealpina.it/siteMapNews.jsp'
PREALPINA_SEZIONE = 'https://www.prealpina.it/news/busto-valle-olona/'
VARESENEWS = 'https://www.varesenews.it/feed/'
VARESENEWS_CATEGORIA = 'Busto Arsizio/Altomilanese'
VARESENEWS_TAG = 'https://www.varesenews.it/citta/busto-arsizio-tag/'
SITEMAP_NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'n': 'http://www.google.com/schemas/sitemap-news/0.9'}


def scarica(url):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def pulisci(testo):
    """Testo semplice da HTML: niente tag, entità risolte, spazi compattati."""
    testo = html.unescape(re.sub(r'<[^>]+>', ' ', testo or ''))
    testo = ' '.join(testo.split())
    return testo[:MAX_SOMMARIO]


def articolo(fonte, url, titolo, sommario='', pubblicato=None, categorie=()):
    return {'fonte': fonte, 'url': url.strip(), 'titolo': pulisci(titolo), 'sommario': pulisci(sommario),
            'pubblicato': pubblicato, 'categorie': list(categorie)}


def da_rss(fonte, dati, tieni=lambda categorie: True):
    out = []
    for it in ET.fromstring(dati).iter('item'):
        categorie = [(c.text or '').strip() for c in it.findall('category')]
        if not tieni(categorie):
            continue
        data = it.findtext('pubDate')
        try:
            data = parsedate_to_datetime(data).astimezone(timezone.utc).isoformat() if data else None
        except (TypeError, ValueError):
            data = None
        out.append(articolo(fonte, it.findtext('link') or '', it.findtext('title'), it.findtext('description'),
                            data, categorie))
    return out


def ilbustese():
    # Un articolo può stare in entrambe le sezioni: i doppioni per link li toglie main()
    return [a for url in ILBUSTESE for a in da_rss('ilbustese', scarica(url))]


def varesenews():
    return da_rss('varesenews', scarica(VARESENEWS), lambda categorie: VARESENEWS_CATEGORIA in categorie)


def varesenews_tag():
    """Articoli dell'elenco principale della pagina del tag. Quelli col titolo che inizia per «»» sono
    la colonna delle ultime notizie di tutta la provincia, e restano fuori."""
    pagina = scarica(VARESENEWS_TAG).decode('utf-8', errors='replace')
    out = []
    for blocco in re.findall(r'<article[^>]*>(.*?)</article>', pagina, re.S):
        link = re.search(r'href="(https://www\.varesenews\.it/20\d\d/\d\d/[^"/]+/\d+/)"', blocco)
        if not link:
            continue
        testi = [pulisci(t) for t in re.findall(r'<a[^>]*href="' + re.escape(link.group(1)) + r'"[^>]*>(.*?)</a>', blocco, re.S)]
        titolo = max(testi, key=len, default='')
        if titolo.startswith('»'):
            continue
        if not titolo:  # alcuni blocchi hanno solo l'immagine: il titolo si ricava dal link
            titolo = link.group(1).rstrip('/').split('/')[-2].replace('-', ' ')
        out.append(articolo('varesenews', link.group(1), titolo))
    return out


def malpensa24():
    out = []
    for p in json.loads(scarica(MALPENSA24)):
        data = p.get('date_gmt')
        out.append(articolo('malpensa24', p['link'], p['title']['rendered'], p['excerpt']['rendered'],
                            data + '+00:00' if data else None, ['BUSTO | VALLE OLONA']))
    return out


def prealpina():
    out = []
    for voce in ET.fromstring(scarica(PREALPINA)).findall('s:url', SITEMAP_NS):
        url = voce.findtext('s:loc', default='', namespaces=SITEMAP_NS)
        if url.startswith(PREALPINA_SEZIONE):
            out.append(articolo('prealpina', url, voce.findtext('n:news/n:title', namespaces=SITEMAP_NS),
                                pubblicato=voce.findtext('n:news/n:publication_date', namespaces=SITEMAP_NS)))
    return out


# Il feed di VareseNews prima della pagina del tag: a parità di link resta la riga con data e riassunto
FONTI = [ilbustese, malpensa24, prealpina, varesenews, varesenews_tag]


def main(percorso):
    adesso = datetime.now(timezone.utc)
    try:
        with open(percorso, encoding='utf-8') as f:
            righe = [json.loads(r) for r in f if r.strip()]
    except FileNotFoundError:
        righe = []
    limite = (adesso - timedelta(days=CONSERVAZIONE_GIORNI)).isoformat()
    righe = [r for r in righe if r['visto'] >= limite]
    noti = {r['url'] for r in righe}

    riuscite = 0
    for fonte in FONTI:
        try:
            trovati = fonte()
        except Exception as err:  # una fonte giù non deve fermare le altre
            print(f'::warning::{fonte.__name__}: {err}')
            continue
        riuscite += 1
        nuovi = [a for a in trovati if a['url'] and a['url'] not in noti]
        for a in nuovi:
            a['visto'] = adesso.isoformat(timespec='seconds')
            noti.add(a['url'])
        righe.extend(nuovi)
        print(f'{fonte.__name__}: {len(trovati)} nell\'elenco, {len(nuovi)} nuovi')

    with open(percorso, 'w', encoding='utf-8', newline='\n') as f:
        for r in righe:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'Totale: {len(righe)} articoli')
    if not riuscite:
        sys.exit('Nessuna fonte raggiungibile')


if __name__ == '__main__':
    main(sys.argv[1])
