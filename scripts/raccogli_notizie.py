"""Raccolta degli articoli di Busto Arsizio da quattro testate locali, per le segnalazioni dalle notizie.

Uso: GOOGLE_APPLICATION_CREDENTIALS=chiave.json python scripts/raccogli_notizie.py
     ... python scripts/raccogli_notizie.py --esporta articoli.jsonl   (copia locale dell'elenco, per la prova)

Gira una volta al giorno nel workflow notizie.yml e scrive nella collezione Firestore `notizie_articoli`, che le
regole chiudono al sito. Si salvano solo testata, link e date: titoli e riassunti riportano testo delle testate e
nomi di persone. Anche i link contengono spesso il titolo, per questo l'elenco non sta nel repo pubblico.
Titolo e testo li legge dal link il passo di analisi. Nessun modello linguistico in questo passo.

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
I documenti più vecchi di CONSERVAZIONE_GIORNI vengono cancellati, come le segnalazioni.
"""
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = 'OsservatorioCivicoBusto/0.1 (+https://f041.github.io/osservatorio-civico-busto-arsizio/)'
CONSERVAZIONE_GIORNI = 365
MAX_SOMMARIO = 500
CAMPI_SALVATI = ('fonte', 'url', 'pubblicato', 'visto')
PROJECT_ID = 'osservatorio-civico-busto'
COLLEZIONE = 'notizie_articoli'
BLOCCO = 400  # documenti per ogni scrittura o lettura multipla

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


def scarica(url, attese=(20, 60)):
    """Con un giro al giorno un errore momentaneo del server costerebbe un giorno: si riprova dopo le attese."""
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for attesa in (*attese, None):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as err:
            if err.code < 500 or attesa is None:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attesa is None:
                raise
        time.sleep(attesa)


def scarica_entro(url, secondi=90):
    """Come scarica, ma con un limite sull'intera richiesta. Il timeout di urllib vale per ogni singola lettura: un
    server che tiene aperta la connessione senza mandare nulla l'ha bloccata per ore (novembre 2026). ilBustese
    risponde alle richieste in blocco dopo circa 30 secondi, da qui il margine largo. Usa curl (Windows e Linux)."""
    r = subprocess.run(['curl', '-sSL', '--fail', '--max-time', str(secondi), '-A', USER_AGENT, url],
                       capture_output=True, timeout=secondi + 10)
    if r.returncode:
        raise RuntimeError(f'curl {r.returncode}: {r.stderr.decode(errors="replace").strip()[:200]}')
    return r.stdout


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


def client_firestore():
    # Importato qui: gli script di prova usano `scarica` senza avere questo pacchetto
    from google.cloud import firestore
    return firestore.Client(project=PROJECT_ID)


def id_articolo(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:32]


def a_blocchi(voci):
    for i in range(0, len(voci), BLOCCO):
        yield voci[i:i + BLOCCO]


def salva(client, articoli):
    raccolta = client.collection(COLLEZIONE)
    for blocco in a_blocchi(articoli):
        scrittura = client.batch()
        for a in blocco:
            scrittura.set(raccolta.document(id_articolo(a['url'])), {k: a.get(k) for k in CAMPI_SALVATI})
        scrittura.commit()


def gia_salvati(client, articoli):
    """Id degli articoli già in collezione: legge solo quelli degli elenchi di oggi, non tutta la collezione."""
    raccolta = client.collection(COLLEZIONE)
    riferimenti = [raccolta.document(i) for i in {id_articolo(a['url']) for a in articoli}]
    noti = set()
    for blocco in a_blocchi(riferimenti):
        noti |= {d.id for d in client.get_all(blocco, field_paths=['url']) if d.exists}
    return noti


def cancella_scaduti(client, limite):
    from google.cloud.firestore_v1.base_query import FieldFilter
    scaduti = [d.reference for d in client.collection(COLLEZIONE).where(filter=FieldFilter('visto', '<', limite)).stream()]
    for blocco in a_blocchi(scaduti):
        scrittura = client.batch()
        for riferimento in blocco:
            scrittura.delete(riferimento)
        scrittura.commit()
    return len(scaduti)


def unisci(client, fonti, *argomenti):
    """Aggiunge alla collezione gli articoli nuovi di ogni fonte (chiamata con `argomenti`), senza doppioni per link."""
    adesso = datetime.now(timezone.utc)
    cancellati = cancella_scaduti(client, (adesso - timedelta(days=CONSERVAZIONE_GIORNI)).isoformat(timespec='seconds'))

    riuscite, aggiunti = 0, 0
    for fonte in fonti:
        try:
            trovati = [a for a in fonte(*argomenti) if a['url']]
        except Exception as err:  # una fonte giù non deve fermare le altre
            print(f'::warning::{fonte.__name__}: {err}')
            continue
        riuscite += 1
        noti = gia_salvati(client, trovati)
        nuovi = {}
        for a in trovati:
            i = id_articolo(a['url'])
            if i not in noti and i not in nuovi:
                nuovi[i] = {**a, 'visto': adesso.isoformat(timespec='seconds')}
        salva(client, list(nuovi.values()))
        aggiunti += len(nuovi)
        print(f'{fonte.__name__}: {len(trovati)} nell\'elenco, {len(nuovi)} nuovi')

    print(f'Aggiunti {aggiunti} articoli, cancellati {cancellati} oltre i {CONSERVAZIONE_GIORNI} giorni')
    if not riuscite:
        sys.exit('Nessuna fonte raggiungibile')


def esporta(client, percorso):
    righe = sorted((d.to_dict() for d in client.collection(COLLEZIONE).stream()), key=lambda r: (r['visto'], r['url']))
    with open(percorso, 'w', encoding='utf-8', newline='\n') as f:
        for r in righe:
            f.write(json.dumps({k: r.get(k) for k in CAMPI_SALVATI}, ensure_ascii=False) + '\n')
    print(f'Esportati {len(righe)} articoli in {percorso}')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--esporta']:
        esporta(client_firestore(), sys.argv[2])
    else:
        unisci(client_firestore(), FONTI)
