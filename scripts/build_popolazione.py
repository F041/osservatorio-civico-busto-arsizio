"""Residenti stimati per gruppo di quartieri, dagli elettori di ogni sezione elettorale e dai residenti ISTAT.

Uso: python scripts/build_popolazione.py data/popolazione.json

Fonti, tutte pubbliche e lette a ogni esecuzione:
- elettori per sezione e totale del Comune, dalle pagine dei risultati dell'ultima consultazione (dati ufficiosi
  dell'Ufficio elettorale, rilevazione finale);
- residenti dell'ultimo mese disponibile, dal bilancio demografico mensile ISTAT (dati provvisori).

Metodo (foglio di calcolo preparato dall'utente a novembre 2026): ogni sezione vale per il quartiere della scuola dove
si vota. I residenti di un gruppo sono i suoi elettori per K, con K = residenti del Comune / elettori del Comune.
È una stima: dove vivono più minorenni o più stranieri, che non votano, i residenti sono più di quelli stimati.
Le attribuzioni delle scuole ai gruppi sono in PLESSI, con il criterio e la fonte di ciascuna. Due ("secondo la
traccia") restano come nel foglio originale per decisione dell'utente del 25/11/2026, anche se la fonte non è nota.

Per una consultazione nuova: cambia CONSULTAZIONE e controlla che le sezioni di PLESSI coincidano con il prospetto.
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

CONSULTAZIONE = {
    'nome': 'Referendum costituzionale del 22 e 23 marzo 2026',
    'sezioni': 'https://elezionibustoarsizio.risele.it/web2603/referendum/AFFLSEZ_1_12026_R4.xml',
    'comune': 'https://elezionibustoarsizio.risele.it/web2603/referendum/AFFLTOT_1_12026.xml',
}
ISTAT = {
    'servizio': 'https://demo.istat.it/app/RPCCerca.php',
    'pagina': 'https://demo.istat.it/app/?i=D7B&l=it',
    'comune': '012026', 'provincia': '012', 'regione': '03', 'ripartizione': '1',
}
USER_AGENT = 'osservatorio-civico-busto/1.0 (+https://github.com/F041/osservatorio-civico-busto-arsizio)'

SPECIALI = 'Sezioni speciali (ospedale e istituto La Provvidenza)'
GRUPPI = ['Centro / Zona Stazione / Frati', 'San Michele / Centro Nord', 'Sant’Edoardo', 'Beata Giuliana',
          'Redentore / Santi Apostoli', 'Madonna Regina', 'Borsano', 'Sacconago', SPECIALI]

COMUNE_REFERENDUM = 'https://www.comune.bustoarsizio.va.it/it/page/referendum-costituzionale-del-22-23-marzo-2026-160980-162166'
# Scuola o sede, sezioni (prima e ultima), zona della scuola, gruppo, criterio, nota, fonte
PLESSI = [
    ('Ezio Crespi', 1, 5, 'San Giuseppe', 'Centro / Zona Stazione / Frati', 'Aggregazione',
     'San Giuseppe è compreso nel gruppo centrale insieme alla zona stazione.', 'https://comprensivocrespi.edu.it/la-scuola/'),
    ('Sant’Anna', 6, 8, 'Sant’Anna', 'Redentore / Santi Apostoli', 'Aggregazione',
     'Come nel foglio originale ("secondo la traccia"): la fonte di questa scelta non è nota.',
     'https://comprensivocrespi.edu.it/la-scuola/'),
    ('Beata Giuliana – Puricelli', 9, 13, 'Beata Giuliana', 'Beata Giuliana', 'Scuola nel quartiere',
     'L’istituto conferma scuola e indirizzo.', 'https://icpertinibusto.edu.it/luogo/istituto/beata-giuliana-puricelli/'),
    ('Marco Polo', 14, 16, 'Confine Redentore / Beata Giuliana', 'Redentore / Santi Apostoli', 'Confine',
     'Attribuita al Redentore come nel foglio originale ("secondo la traccia"): la fonte di questa scelta non è nota.',
     'https://www.malpensa24.it/busto-un-anno-di-piazza-scolastica-alle-marco-polo-unidea-per-le-tommaseo/'),
    ('Ospedale di Circolo', 17, 17, 'Sede sanitaria', SPECIALI, 'A parte',
     'Sede ospedaliera indicata nel prospetto del referendum, tenuta separata dai quartieri.', COMUNE_REFERENDUM),
    ('Luigi Morelli', 18, 22, 'Santi Apostoli', 'Redentore / Santi Apostoli', 'Scuola nel quartiere',
     'L’istituto colloca le Morelli in Santi Apostoli.', 'https://comprensivocrespi.edu.it/la-scuola/'),
    ('Istituto La Provvidenza', 23, 23, 'Sede assistenziale', SPECIALI, 'A parte',
     'Sede assistenziale indicata nel prospetto del referendum, tenuta separata dai quartieri.', COMUNE_REFERENDUM),
    ('Nicolò Tommaseo', 24, 27, 'Frati', 'Centro / Zona Stazione / Frati', 'Scuola nel quartiere',
     'L’istituto indica i Frati e la vicinanza alla stazione.', 'https://www.tommaseobusto.edu.it/pagine/la-storia'),
    ('G. Bertacchi', 28, 33, 'Sant’Edoardo', 'Sant’Edoardo', 'Scuola nel quartiere',
     'L’istituto colloca le Bertacchi a Sant’Edoardo.', 'https://www.istitutobertacchi.edu.it/luoghi?id=339'),
    ('Liceo artistico Paolo Candiani', 34, 37, 'Centro sud-est', 'Centro / Zona Stazione / Frati', 'Indirizzo',
     'Via Manara parte da piazza Trento e Trieste, sul lato sud-est del centro.',
     'https://it.wikipedia.org/wiki/Toponomastica_storica_di_Busto_Arsizio'),
    ('Primaria Edmondo De Amicis', 38, 42, 'Zona stazione Ferrovienord', 'Centro / Zona Stazione / Frati', 'Indirizzo',
     'La sede di via Dante è vicino alla stazione di Busto Arsizio Nord.', 'https://www.icbossibusto.edu.it/luoghi?id=19'),
    ('Pontida, via Pontida', 43, 48, 'Confine San Michele / Redentore', 'San Michele / Centro Nord', 'Confine',
     'L’istituto descrive la scuola a cavallo tra San Michele e Redentore. Attribuita a San Michele.',
     'https://icdeamicis.edu.it/luogo/primaria-pontida-via-montello/'),
    ('Pontida, viale Montello', 49, 51, 'Confine San Michele / Redentore', 'San Michele / Centro Nord', 'Confine',
     'Seconda sede della Pontida, attribuita come quella di via Pontida.',
     'https://icdeamicis.edu.it/luogo/primaria-pontida-via-montello/'),
    ('Sandro Pertini', 52, 56, 'Beata Giuliana (ovest)', 'Beata Giuliana', 'Scuola nel quartiere',
     'L’istituto indica la parte ovest di Beata Giuliana.',
     'https://icpertinibusto.edu.it/struttura/istituto-comprensivo/plesso-sandro-pertini/'),
    ('Giovanni Pascoli', 57, 62, 'Madonna Regina', 'Madonna Regina', 'Scuola nel quartiere',
     'L’istituto colloca la scuola a Madonna Regina.', 'https://icdeamicis.edu.it/struttura/il-nostro-istituto/'),
    ('Ada Negri', 63, 67, 'Sacconago', 'Sacconago', 'Scuola nel quartiere',
     'L’IC Galilei colloca la primaria Negri a Sacconago.', 'https://www.galileibusto.edu.it/pagine/presentazione'),
    ('Galilei / Parini', 68, 71, 'Sacconago', 'Sacconago', 'Indirizzo',
     'Il seggio di via Quadrelli è la Galilei di Sacconago.', 'https://www.galileibusto.edu.it/pagine/presentazione'),
    ('G. Rossi', 72, 77, 'Borsano', 'Borsano', 'Scuola nel quartiere',
     'L’IC Galilei colloca la primaria Rossi a Borsano.', 'https://www.galileibusto.edu.it/pagine/presentazione'),
    ('Biagio Bellotti', 78, 81, 'Sant’Edoardo', 'Sant’Edoardo', 'Scuola nel quartiere',
     'L’istituto colloca le Bellotti a Sant’Edoardo.', 'https://www.istitutobertacchi.edu.it/luoghi?id=345'),
]


def scarica(url, dati=None):
    comando = ['curl', '-sSL', '--fail', '--max-time', '60', '-A', USER_AGENT, url]
    if dati:
        comando += ['--data', dati]
    return subprocess.run(comando, capture_output=True, check=True).stdout


def leggi_consultazione():
    sezioni = []
    radice = ET.fromstring(scarica(CONSULTAZIONE['sezioni']))
    for sv in radice.iter('SV'):
        sezioni.append({
            'numero': int(sv.get('NUMERO')),
            'ubicazione': sv.get('UBICAZIONE'),
            'elettori_m': int(sv.get('ELETTORIM')),
            'elettori_f': int(sv.get('ELETTORIF')),
            'elettori': int(sv.get('ELETTORI')),
        })
    data_consultazione = datetime.strptime(radice.get('DATA'), '%d/%m/%Y').date()
    # Una riga per rilevazione dell'affluenza: gli elettori sono gli stessi in tutte, si prende l'ultima
    totale = list(ET.fromstring(scarica(CONSULTAZIONE['comune'])).iter('SV'))[-1]
    comune = {k: int(totale.get(a)) for k, a in (('elettori', 'ELETTORI'), ('elettori_m', 'ELETTORIM'),
                                                 ('elettori_f', 'ELETTORIF'))}
    aggiornamento = radice.get('ORAAGGIORNAMENTO')  # es. 23/03/2026-17.54
    return sorted(sezioni, key=lambda s: s['numero']), comune, data_consultazione, aggiornamento


def leggi_istat():
    """Residenti a fine mese, tutti i mesi pubblicati dell'anno in corso (o dell'anno prima, a gennaio)."""
    for anno in (date.today().year, date.today().year - 1):
        dati = '&'.join(f'{k}={v}' for k, v in {
            'a': anno, 'ripartizione': ISTAT['ripartizione'], 'regione': ISTAT['regione'],
            'provincia': ISTAT['provincia'], 'comune': ISTAT['comune'], 'hid-i': 'D7B', 'hid-a': anno, 'hid-l': 'it',
            'hid-cat': 'D7B', 'hid-dati': 'dati-form-0', 'hid-tavola': 'tavola-form-0'}.items())
        risposta = json.loads(scarica(ISTAT['servizio'], dati))
        righe = [r for r in (risposta.get('datatable') or {}).get('data', []) if r['sesso'] == 9]
        if righe:
            return [{'mese': f"{anno}-{r['mese']:02d}", 'residenti': r['pop_finale'], 'provvisorio': r['flag'] == 'p'}
                    for r in sorted(righe, key=lambda r: r['mese'])]
    raise RuntimeError('ISTAT: nessun mese pubblicato')


def arrotonda(valori, totale):
    """Arrotonda a interi che sommano esattamente `totale` (resti maggiori)."""
    interi = [int(v) for v in valori]
    for i in sorted(range(len(valori)), key=lambda i: valori[i] - interi[i], reverse=True)[:totale - sum(interi)]:
        interi[i] += 1
    return interi


def costruisci(sezioni, comune, data_consultazione, aggiornamento, mesi, adesso):
    if sum(s['elettori'] for s in sezioni) != comune['elettori']:
        raise ValueError('La somma degli elettori delle sezioni non coincide con il totale del Comune')
    numeri = [s['numero'] for s in sezioni]
    coperte = sorted(n for _, da, a, *_ in PLESSI for n in range(da, a + 1))
    if numeri != coperte:
        raise ValueError('Le sezioni di PLESSI non coincidono con quelle della consultazione')

    plessi = []
    for nome, da, a, zona, gruppo, criterio, nota, fonte in PLESSI:
        if gruppo not in GRUPPI:
            raise ValueError(f'Gruppo sconosciuto: {gruppo}')
        sue = [s for s in sezioni if da <= s['numero'] <= a]
        # Tutte le sezioni di una scuola hanno lo stesso seggio nel prospetto (a parte gli spazi: "SC. ELEM."L. MORELLI")
        if len({''.join(s['ubicazione'].split()) for s in sue}) != 1:
            raise ValueError(f'{nome}: sezioni {da}-{a} in seggi diversi')
        for s in sue:
            s['scuola'] = nome
            s['gruppo'] = gruppo
        plessi.append({'nome': nome, 'seggio': sue[0]['ubicazione'], 'sezioni': [da, a], 'zona': zona, 'gruppo': gruppo,
                       'criterio': criterio, 'nota': nota, 'fonte': fonte,
                       'elettori': sum(s['elettori'] for s in sue)})

    ultimo = mesi[-1]
    k = ultimo['residenti'] / comune['elettori']
    elettori = {g: sum(s['elettori'] for s in sezioni if s['gruppo'] == g) for g in GRUPPI}
    stime = arrotonda([elettori[g] * k for g in GRUPPI], ultimo['residenti'])
    gruppi = [{'nome': g, 'sezioni': sum(1 for s in sezioni if s['gruppo'] == g), 'elettori': elettori[g],
               'quota_elettori': round(elettori[g] / comune['elettori'], 4), 'residenti_stimati': n}
              for g, n in zip(GRUPPI, stime)]

    return {
        'generato': adesso.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'residenti': {
            'mese': ultimo['mese'], 'valore': ultimo['residenti'], 'provvisorio': ultimo['provvisorio'],
            'fonte': 'ISTAT, bilancio demografico mensile', 'link': ISTAT['pagina'],
            'mesi': mesi,
        },
        'consultazione': {
            'nome': CONSULTAZIONE['nome'], 'data': data_consultazione.isoformat(), 'aggiornamento': aggiornamento,
            'fonte': 'Comune di Busto Arsizio, Ufficio elettorale (dati ufficiosi)',
            'link_sezioni': CONSULTAZIONE['sezioni'], 'link_comune': CONSULTAZIONE['comune'],
            **comune,
        },
        'k': round(k, 6),
        'gruppi': gruppi,
        'plessi': plessi,
        'sezioni': [{k: s[k] for k in ('numero', 'scuola', 'gruppo', 'ubicazione', 'elettori_m', 'elettori_f', 'elettori')}
                    for s in sezioni],
    }


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Uso: python scripts/build_popolazione.py data/popolazione.json')
    dati = costruisci(*leggi_consultazione(), leggi_istat(), datetime.now(timezone.utc))
    with open(sys.argv[1], 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
        f.write('\n')
    r = dati['residenti']
    print(f"Scritto {sys.argv[1]}: {r['valore']} residenti a {r['mese']}, "
          f"{dati['consultazione']['elettori']} elettori, K = {dati['k']:.4f}")
