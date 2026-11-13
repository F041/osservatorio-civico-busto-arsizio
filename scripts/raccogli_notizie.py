"""Raccolta degli articoli di Busto Arsizio da quattro testate locali, per le segnalazioni dalle notizie.

Uso: python scripts/raccogli_notizie.py articoli.jsonl

Gira ogni 2 ore nel workflow notizie.yml e scrive sul ramo `notizie`, non su main (così non riparte
la pubblicazione del sito). Salva solo i dati che le testate espongono nei loro elenchi: link, titolo,
riassunto, data e categorie. Il testo degli articoli non viene scaricato qui: lo legge, per i soli
candidati, il passo di analisi. Nessun modello linguistico in questo passo.

Perché ogni 2 ore: il feed di ilBustese contiene solo gli ultimi 20 articoli (circa 7 ore in un giorno
feriale), quello di VareseNews gli ultimi 100 di tutta la provincia (circa 20 ore).
Fonti e scelte, verificate a novembre 2026:
- ilBustese: feed RSS generale; non ha categorie, il passo di analisi scarta ciò che non è cronaca.
- Malpensa24: API WordPress della categoria 12 (BUSTO | VALLE OLONA); il feed della categoria ha solo 2 articoli.
- Prealpina: nessun feed; pagina della sezione 28, permessa dal robots.txt.
- VareseNews: il feed del tag Busto è vietato dal robots.txt (/*/feed/$): si legge il feed generale
  e si tengono gli articoli della categoria "Busto Arsizio/Altomilanese".
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
from html.parser import HTMLParser

USER_AGENT = 'OsservatorioCivicoBusto/0.1 (+https://f041.github.io/osservatorio-civico-busto-arsizio/)'
CONSERVAZIONE_GIORNI = 365
MAX_SOMMARIO = 500

ILBUSTESE = 'https://www.ilbustese.it/links/rss/argomenti/ilbusteseit/rss.xml'
MALPENSA24 = ('https://www.malpensa24.it/wp-json/wp/v2/posts?categories=12&per_page=30'
              '&_fields=link,date_gmt,title,excerpt')
PREALPINA = 'https://www.prealpina.it/sezioni/28/busto-valle-olona'
VARESENEWS = 'https://www.varesenews.it/feed/'
VARESENEWS_CATEGORIA = 'Busto Arsizio/Altomilanese'


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
    return da_rss('ilbustese', scarica(ILBUSTESE))


def varesenews():
    return da_rss('varesenews', scarica(VARESENEWS), lambda categorie: VARESENEWS_CATEGORIA in categorie)


def malpensa24():
    out = []
    for p in json.loads(scarica(MALPENSA24)):
        data = p.get('date_gmt')
        out.append(articolo('malpensa24', p['link'], p['title']['rendered'], p['excerpt']['rendered'],
                            data + '+00:00' if data else None, ['BUSTO | VALLE OLONA']))
    return out


class LinkPrealpina(HTMLParser):
    """Nella pagina della sezione ogni articolo ha due link: il primo col titolo, il secondo col riassunto."""
    PERCORSO = re.compile(r'^https://www\.prealpina\.it/news/busto-valle-olona/\d+/[^"]+\.html$')

    def __init__(self):
        super().__init__()
        self.testi = {}
        self._url = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href') or ''
            self._url = href if self.PERCORSO.match(href) else None
            if self._url:
                self.testi.setdefault(self._url, [])
                self.testi[self._url].append('')

    def handle_data(self, data):
        if self._url:
            self.testi[self._url][-1] += data

    def handle_endtag(self, tag):
        if tag == 'a':
            self._url = None


def prealpina():
    parser = LinkPrealpina()
    parser.feed(scarica(PREALPINA).decode('utf-8', errors='replace'))
    out = []
    for url, testi in parser.testi.items():
        testi = [t for t in (' '.join(t.split()) for t in testi) if t]
        if testi:
            # La pagina non mostra la data: resta quella in cui l'articolo è stato visto la prima volta
            out.append(articolo('prealpina', url, testi[0], testi[1] if len(testi) > 1 else ''))
    return out


FONTI = [ilbustese, malpensa24, prealpina, varesenews]


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
