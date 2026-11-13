"""Riconosce nei testi delle notizie le vie e i luoghi di Busto Arsizio, con lo stradario di data/mappa.json.

Serve da filtro prima del modello linguistico: un articolo senza nessuna via o luogo di Busto non può dare un
episodio da mettere sulla mappa, quindi non va analizzato. Le vie trovate diventano anche l'unica scelta possibile
per il campo `via` dell'estrazione, e da lì i quadrati della mappa, senza geocoder esterni.

Come riconosce una via: dopo "via", "viale", "piazza", "largo", "corso"... cerca il nome della via com'è nello
stradario ("via Quintino Sella"), oppure il solo cognome preceduto da nomi propri o titoli ("via Sella",
"via Don Minzoni"), oppure la sola prima parola se nessun'altra via inizia così ("via Lonate"). Il nome deve
iniziare con la maiuscola o una cifra, così "via mail" o "in via precauzionale" non contano.
Se più vie dello stradario vanno bene ("via Repubblica" e "Viale della Repubblica"), vince quella col prefisso
uguale; se restano più vie lontane tra loro, il risultato è segnato come ambiguo.
Lo stradario contiene solo Busto: una "via Roma" di Castellanza viene presa per quella di Busto. Per questo
`filtro` scarta gli articoli che non nominano Busto o un suo quartiere; il passo successivo decide comunque se il
fatto è avvenuto nel comune.
"""
import json
import re
import unicodedata
from pathlib import Path

MAPPA = Path(__file__).parents[1] / 'data' / 'mappa.json'
PREFISSI = {'via': 'via', 'viale': 'viale', 'v.le': 'viale', 'piazza': 'piazza', 'p.za': 'piazza', 'p.zza': 'piazza',
            'piazzale': 'piazzale', 'piazzetta': 'piazzetta', 'largo': 'largo', 'corso': 'corso', 'vicolo': 'vicolo',
            'strada': 'strada'}
PARTICELLE = {'d', 'da', 'di', 'de', 'del', 'dei', 'della', 'delle', 'degli', 'dello', 'dell', 'l', 'la', 'lo', 'le', 'e'}
NON_NOMI = {'san', 'santa', 'sant', 'santi', 'santo', 'monte', 'fratelli', 'martiri', 'caduti', 'madonna', 'beata',
            'beato', 'xx', 'iv', 'xxv', 'i', 'ii'}
MESI = {'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
        'novembre', 'dicembre'}
FINE_FRASE = re.compile(r'[.!?…][»”"’)]*$')
CERCA_PREFISSO = re.compile(r'\b(' + '|'.join(re.escape(p) for p in sorted(PREFISSI, key=len, reverse=True)) + r')\s+',
                            re.I)
# Busto o un suo quartiere nominati da qualche parte: senza, le vie trovate sono quasi sempre di un altro comune
BUSTO = re.compile(r"\b(busto|bustocc|bustes|sacconago|borsano|beata giuliana|sant.anna|redentore|veroncora|"
                   r"madonna regina|santi apostoli|sant.edoardo|san michele)", re.I)
PAROLA = re.compile(r"[^\W_]+(?:['’][^\W_]+)?")
# Stazioni e parchi: il nome del luogo, o un modo comune di chiamarlo
ALIAS_LUOGHI = {'Busto Arsizio FS': ['stazione fs', 'stazione centrale', 'stazione delle fs', 'stazione ferroviaria'],
                'Busto Arsizio Nord': ['stazione nord', 'stazione delle nord', 'ferrovienord', 'ferrovie nord']}


# Numeri delle vie dedicate a una data, scritti in cifre o in numeri romani: "via XX Settembre", "via 4 Novembre"
NUMERI = {'1': 'primo', '4': 'quattro', 'iv': 'quattro', '11': 'undici', 'xi': 'undici', '20': 'venti', 'xx': 'venti',
          '24': 'ventiquattro', 'xxiv': 'ventiquattro', '25': 'venticinque', 'xxv': 'venticinque'}


def norma(testo):
    testo = unicodedata.normalize('NFKD', testo).encode('ascii', 'ignore').decode().lower()
    return [NUMERI.get(p, p) for p in re.findall(r'[a-z0-9]+', testo)]


def significative(parole):
    return tuple(p for p in parole if p not in PARTICELLE)


def pulisci_testo(testo):
    """Toglie le righe che non sono frasi: titoli di articoli collegati, sottotitoli, didascalie, piè di pagina.
    Le righe brevi senza punteggiatura finale sono quasi sempre questo; il testo dell'articolo resta."""
    righe = []
    for riga in (testo or '').splitlines():
        riga = riga.strip()
        if riga in ('I più letti', 'Leggi anche'):
            break
        # Una riga breve resta solo se finisce con un punto, anche dentro le virgolette: «basta.» sì, «basta» no
        if riga and (FINE_FRASE.search(riga) or len(riga) >= 200):
            righe.append(riga)
    return '\n'.join(righe)


class Stradario:
    def __init__(self, percorso=MAPPA):
        mappa = json.load(open(percorso, encoding='utf-8'))
        self.vie = []
        for v in mappa['vie']:
            primo, _, resto = v['n'].partition(' ')
            tipo = PREFISSI.get(primo.lower())
            # Nomi come "Via Sella ang. Depretis" sono incroci scritti nel nome dell'oggetto OSM, non vie
            if not tipo or not resto or re.search(r'\bang\b', resto):
                continue
            parole = significative(norma(resto))
            if not parole:
                continue
            breve = None
            if len(parole) >= 2 and parole[0] not in NON_NOMI and parole[-1] not in MESI and not parole[-1].isdigit():
                breve = parole[-1:]
            self.vie.append({'nome': v['n'], 'tipo': tipo, 'parole': parole, 'breve': breve, 'celle': set(v['c'])})
        # Anche la sola prima parola, se nessun'altra via inizia così: "via Lonate" per Via Lonate Pozzolo
        prime = {}
        for v in self.vie:
            if len(v['parole']) >= 2:
                prime[v['parole'][0]] = prime.get(v['parole'][0], 0) + 1
        for v in self.vie:
            p0 = v['parole'][0]
            v['prima'] = (p0,) if len(v['parole']) >= 2 and prime[p0] == 1 and p0 not in NON_NOMI else None
        self.luoghi = []
        for l in mappa['luoghi']:
            frasi = ALIAS_LUOGHI.get(l['n'], [])
            if re.match(r'(Parco|Giardin)', l['n']):
                frasi = frasi + [l['n']]
            for f in frasi:
                self.luoghi.append({'nome': l['n'], 'frase': ' '.join(norma(f)), 'celle': {l['c']}})

    def _vie_in(self, testo):
        for m in CERCA_PREFISSO.finditer(testo):
            tipo = PREFISSI[m.group(1).lower()]
            coda = re.split(r'[,.;:()\[\]«»"“”\n–—]', testo[m.end():m.end() + 80], maxsplit=1)[0]
            originali = PAROLA.findall(coda)[:6]
            if not originali:
                continue
            finestra = [norma(p)[0] if norma(p) else '' for p in originali]
            # Indici delle parole significative con la loro forma originale
            sig = [(f, o) for f, o in zip(finestra, originali) if f and f not in PARTICELLE]
            if not sig or not (sig[0][1][0].isupper() or sig[0][1][0].isdigit()):
                continue
            parole = tuple(f for f, _ in sig)
            maiuscole = [o[0].isupper() or o[0].isdigit() for _, o in sig]
            punteggi = []
            for v in self.vie:
                n = len(v['parole'])
                if parole[:n] == v['parole']:
                    punteggi.append((10 + n, v))
                elif v['prima'] and parole[:1] == v['prima']:
                    punteggi.append((2, v))
                elif v['breve']:
                    # Cognome dopo al massimo tre nomi o titoli con la maiuscola: "via Don Giovanni Minzoni"
                    for j in range(min(4, len(parole))):
                        if parole[j:j + 1] == v['breve'] and all(maiuscole[:j + 1]):
                            punteggi.append((1, v))
                            break
            if not punteggi:
                continue
            migliore = max(p for p, _ in punteggi)
            scelte = [v for p, v in punteggi if p == migliore]
            stesse = [v for v in scelte if v['tipo'] == tipo]
            scelte = stesse or scelte
            yield m.group(0) + coda.strip(), scelte

    def filtro(self, articolo):
        """Testo pulito e vie di Busto di un articolo (url, titolo, sommario, testo). Nessuna via se l'articolo non
        nomina Busto o un suo quartiere: nel link, nel titolo, nel sommario o nel testo intero, didascalie comprese."""
        pulito = pulisci_testo(articolo.get('testo'))
        campi = (articolo.get('url'), articolo.get('titolo'), articolo.get('sommario'), articolo.get('testo'))
        if not any(BUSTO.search(t or '') for t in campi):
            return pulito, []
        return pulito, self.trova(articolo.get('titolo'), articolo.get('sommario'), pulito)

    def trova(self, *testi):
        """Vie e luoghi di Busto nei testi, senza doppioni, nell'ordine in cui compaiono."""
        trovati = {}
        for testo in testi:
            if not testo:
                continue
            for frase, scelte in self._vie_in(testo):
                celle = set().union(*(v['celle'] for v in scelte))
                nomi = sorted({v['nome'] for v in scelte})
                ambigua = len(nomi) > 1 and not all(v['celle'] & scelte[0]['celle'] for v in scelte)
                chiave = nomi[0] if not ambigua else ' / '.join(nomi)
                trovati.setdefault(chiave, {'nome': chiave, 'tipo': 'via', 'celle': celle, 'ambigua': ambigua,
                                            'testo': frase[:60]})
            piano = ' '.join(norma(testo))
            for l in self.luoghi:
                if re.search(r'\b' + re.escape(l['frase']) + r'\b', piano):
                    trovati.setdefault(l['nome'], {'nome': l['nome'], 'tipo': 'luogo', 'celle': l['celle'],
                                                   'ambigua': False, 'testo': l['frase']})
        return list(trovati.values())


if __name__ == '__main__':
    import sys
    s = Stradario()
    for riga in sys.stdin:
        print([(t['nome'], t['ambigua']) for t in s.trova(riga)])
