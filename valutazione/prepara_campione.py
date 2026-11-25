"""Campione per la prova del motore delle notizie: sceglie gli articoli e ne scarica il testo, solo in locale.

Uso: uv run --no-project --python 3.12 --with trafilatura python -I valutazione/prepara_campione.py articoli.jsonl [n]
     ... prepara_campione.py articoli.jsonl arricchito
     ... prepara_campione.py articoli.jsonl resto
     ... prepara_campione.py articoli.jsonl nuovi

Campione a caso: metà dalla cronaca di ilBustese, dove gli episodi sono più frequenti, metà a caso dalle altre
testate, in parti uguali. Il seme è fisso, così il campione si può rifare uguale.
Campione arricchito: tutti gli articoli che nominano Busto (o un suo quartiere) e una parola di cronaca nel titolo,
nel riassunto o nel link, esclusi quelli già nel campione a caso. Serve ad avere abbastanza episodi veri e fatti
raccontati da più testate; non misura la frequenza degli episodi.
Resto: tutti gli altri articoli, per cercarvi nuovi candidati con il filtro delle vie (valutazione/candidati_vie.py).
Nuovi: gli articoli raccolti dopo i campioni precedenti, mai usati per scrivere le regole (id n001...).
Storico90: gli articoli dello storico a 90 giorni non presenti in nessun file precedente (id v001...).
Storico150: lo storico dal 26/06; `... storico150 ilbustese` per ilBustese da solo (id x...), senza testata per le
altre (id w...). ilBustese rallenta molto le richieste in blocco e si scarica a parte.
Storico2026: gli ultimi 365 giorni non ancora scaricati (prima solo il 2026, da qui il nome), dal più recente; `... storico2026 ilbustese` per ilBustese (id y + 10
cifre del link), senza testata per le altre (id z...). Si può interrompere e rilanciare: riparte da dove era.
I testi finiscono in valutazione/dati/, esclusa da git: servono solo alla prova e poi si cancellano.
"""
import hashlib
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import trafilatura

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from raccogli_notizie import scarica_entro  # noqa: E402

SEME = 20261113
DATI = Path(__file__).parent / 'dati'
PAUSA = 1.5
CRONACA = re.compile(r'furt|ladr|rapin|scipp|borseg|aggre|rissa|minacc|coltell|spacci|droga|cocain|hashish|pusher|'
                     r'vandal|danneg|degrado|molest|baby gang|maranza|arrest|denunc|sicurezza|polizia|carabinier|'
                     r'incendi', re.I)
BUSTO = re.compile(r'busto|sacconago|borsano|beata giuliana|sant.anna|redentore|veroncora', re.I)


def a_caso(articoli, n):
    cronaca = [a for a in articoli if a['fonte'] == 'ilbustese' and '/argomenti/cronaca-26/' in a['url']]
    altre = {f: [a for a in articoli if a['fonte'] == f] for f in ('malpensa24', 'prealpina', 'varesenews')}
    caso = random.Random(SEME)
    scelti = caso.sample(cronaca, n // 2)
    resto = n - len(scelti)
    for i, (fonte, gruppo) in enumerate(altre.items()):
        quanti = resto // 3 + (1 if i < resto % 3 else 0)
        scelti += caso.sample(gruppo, quanti)
    return scelti


def gia_scelti(*nomi):
    return {json.loads(r)['url'] for n in nomi if (DATI / n).exists() for r in open(DATI / n, encoding='utf-8') if r.strip()}


def arricchito(articoli):
    gia = gia_scelti('campione.jsonl')
    # L'elenco salva solo il link: titolo e riassunto ci sono solo nei file vecchi
    testa = lambda a: f"{a.get('titolo', '')} {a.get('sommario', '')} {a['url']}"
    return [a for a in articoli if a['url'] not in gia and CRONACA.search(testa(a)) and BUSTO.search(testa(a))]


def main(percorso, quale='80', fonti=''):
    articoli = [json.loads(r) for r in open(percorso, encoding='utf-8') if r.strip()]
    if quale == 'arricchito':
        scelti, uscita, prefisso = arricchito(articoli), DATI / 'campione-arricchito.jsonl', 'b'
    elif quale == 'resto':
        gia = gia_scelti('campione.jsonl', 'campione-arricchito.jsonl')
        scelti, uscita, prefisso = [a for a in articoli if a['url'] not in gia], DATI / 'testi-resto.jsonl', 'r'
    elif quale == 'nuovi':
        gia = gia_scelti('campione.jsonl', 'campione-arricchito.jsonl', 'testi-resto.jsonl')
        scelti, uscita, prefisso = [a for a in articoli if a['url'] not in gia], DATI / 'testi-nuovi.jsonl', 'n'
    elif quale == 'storico90':
        gia = gia_scelti('campione.jsonl', 'campione-arricchito.jsonl', 'testi-resto.jsonl', 'testi-nuovi.jsonl')
        scelti, uscita, prefisso = [a for a in articoli if a['url'] not in gia], DATI / 'testi-storico90.jsonl', 'v'
    elif quale == 'storico2026':
        # Gli ultimi 365 giorni, in più giri: l'id viene dal link e non dalla posizione nell'elenco, così resta lo stesso anche se
        # l'elenco cresce fra un giro e l'altro. Si scaricano prima i più recenti
        solo_ilbustese = fonti == 'ilbustese'
        inizio = (date.today() - timedelta(days=365)).isoformat()
        uscita = DATI / f"testi-storico2026-{'ilbustese' if solo_ilbustese else 'altre'}.jsonl"
        gia = gia_scelti(*(p.name for p in DATI.glob('*.jsonl')
                           if p.name.startswith(('testi-', 'campione')) and p.name != uscita.name))
        scelti = sorted((a for a in articoli if a['url'] not in gia and (a['fonte'] == 'ilbustese') == solo_ilbustese
                         and (a.get('pubblicato') or a['visto']) >= inizio),
                        key=lambda a: a.get('pubblicato') or a['visto'], reverse=True)
        prefisso = None
    elif quale.startswith('storico'):
        # storico150, storico182...: tutto quello che non è in nessun file di testi precedente; ilBustese va in un file
        # suo (id x...), le altre testate insieme (id w...). Il numero dei giorni entra nell'id, così file diversi
        # non hanno id uguali
        solo_ilbustese = fonti == 'ilbustese'
        uscita = DATI / f"testi-{quale}-{'ilbustese' if solo_ilbustese else 'altre'}.jsonl"
        gia = gia_scelti(*(p.name for p in DATI.glob('*.jsonl')
                           if p.name.startswith(('testi-', 'campione')) and p.name != uscita.name))
        scelti = [a for a in articoli if a['url'] not in gia and (a['fonte'] == 'ilbustese') == solo_ilbustese]
        prefisso = ('x' if solo_ilbustese else 'w') + ('' if quale == 'storico150' else quale[7:] + '-')
    else:
        scelti, uscita, prefisso = a_caso(articoli, int(quale)), DATI / 'campione.jsonl', 'a'
    DATI.mkdir(exist_ok=True)

    def leggi(a):
        try:
            pagina = scarica_entro(a['url']).decode('utf-8', errors='replace')
            testo = trafilatura.extract(pagina, include_comments=False, include_tables=False) or ''
            meta = trafilatura.extract_metadata(pagina)
            return testo, (meta.title if meta and meta.title else a.get('titolo', ''))
        except Exception as err:
            print(f'::warning::{a["url"]}: {err}', flush=True)
            return '', a.get('titolo', '')

    # Ogni articolo si salva appena letto: se il lavoro si interrompe, al giro dopo riparte da dove era.
    # Nello storico 2026 gli articoli rimasti senza testo (503 di ilBustese) si riprovano al giro dopo
    if quale == 'storico2026' and uscita.exists():
        righe = [r for r in open(uscita, encoding='utf-8') if r.endswith('\n') and r.strip()]
        piene = [r for r in righe if json.loads(r)['testo']]
        if len(piene) < len(righe):
            with open(uscita, 'w', encoding='utf-8', newline='\n') as f:
                f.writelines(piene)
            print(f'{len(righe) - len(piene)} articoli senza testo da riprovare', flush=True)
    fatti = gia_scelti(uscita.name)
    if prefisso is None:
        numeri = {a['url']: ('y' if a['fonte'] == 'ilbustese' else 'z') + hashlib.sha1(a['url'].encode()).hexdigest()[:10]
                  for a in scelti}
    else:
        numeri = {a['url']: f'{prefisso}{i:03d}' for i, a in enumerate(scelti, 1)}
    blocco = threading.Lock()
    conta = {'letti': 0, 'vuoti': 0}

    # Una testata alla volta con la pausa tra le richieste, le quattro testate in parallelo
    def leggi_fonte(gruppo):
        for a in gruppo:
            testo, titolo = leggi(a)
            riga = {'id': numeri[a['url']], **a, 'titolo': titolo, 'testo': testo}
            with blocco, open(uscita, 'a', encoding='utf-8', newline='\n') as f:
                f.write(json.dumps(riga, ensure_ascii=False) + '\n')
                conta['letti'] += 1
                conta['vuoti'] += not testo
                if conta['letti'] % 100 == 0:
                    print(f"{conta['letti'] + len(fatti)}/{len(scelti)} articoli", flush=True)
            time.sleep(PAUSA)

    gruppi = {}
    for a in scelti:
        if a['url'] not in fatti:
            gruppi.setdefault(a['fonte'], []).append(a)
    print(f'{len(fatti)} già scaricati, {sum(map(len, gruppi.values()))} da scaricare', flush=True)
    with ThreadPoolExecutor(max_workers=len(gruppi) or 1) as pool:
        list(pool.map(leggi_fonte, gruppi.values()))
    print(f"Salvato {uscita}: {len(scelti)} articoli, {conta['vuoti']} senza testo in questo giro")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '80', sys.argv[3] if len(sys.argv) > 3 else '')
