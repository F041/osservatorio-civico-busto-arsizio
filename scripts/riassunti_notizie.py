"""Riassunti e sottotipi dei fatti dalle notizie, per la mappa e la pagina di revisione (revisione.html): 2 o 3 frasi
su cosa è successo e, per furti e vandalismi, il sottotipo (build_notizie.SOTTOTIPI). Li scrive Haiku con `claude -p`
e l'abbonamento (niente API a pagamento). Gira sul PC, dopo `scripts/episodi_notizie.py carica`, perché servono i
testi degli articoli, che restano solo sul PC.

Uso: uv run --no-project --python 3.12 --with google-cloud-firestore==2.34.1 python -I scripts/riassunti_notizie.py \
         <cartella con i testi *.jsonl> <memoria.jsonl> [--paralleli 2]

Lavora solo sui fatti che finiscono sulla mappa e non hanno ancora riassunto o sottotipo: una domanda per fatto, sul
primo articolo (lo stesso che dà l'id al fatto; i fatti già pubblicati tengono il loro, vedi
build_notizie.primo_episodio, per questo legge data/notizie.json e revisione/notizie.tsv dal sito). Riassunto e
sottotipo vanno nel documento Firestore di quell'articolo, campi `riassunti` e `sottotipi`, con chiave tipo|via|giorno;
build_notizie.py li mette in data/notizie.json. `memoria.jsonl` tiene le risposte già avute, fuori dal repo: se il giro
si interrompe (limite delle 5 ore) si riparte da lì.
Mai nomi, età o altri dettagli sulle persone: il riassunto è pubblico.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from avviso_revisione import SITO  # noqa: E402
from build_notizie import (FINESTRA_GIORNI, NESSUNO, SOTTOTIPI, chiave_riassunto, episodi_validi, noti,  # noqa: E402
                           primo_episodio, revisione)
from conciliazione import aggancia_seguiti, carica_mappa, raggruppa  # noqa: E402
from episodi_notizie import (RIASSUNTI, SOTTOTIPI as CAMPO_SOTTOTIPI, aggiungi_riassunti, client, esporta,  # noqa: E402
                             leggi)

MAX_TESTO = 8000
NOMI_TIPI = {'furto': 'furto', 'molestia': 'molestia', 'aggressione': 'aggressione', 'vandalismo': 'vandalismo o degrado',
             'spaccio': 'spaccio', 'insicurezza': 'problemi ricorrenti', 'allagamento': 'allagamento', 'altro': 'altro'}
PROMPT = """Riassumi un fatto raccontato in un articolo di una testata locale di Busto Arsizio. Il riassunto va in una \
pagina pubblica, accanto al tipo di fatto, e serve a chi controlla che il fatto sia giusto.

- 2 o 3 frasi, al massimo 300 caratteri, in italiano semplice.
- Scrivi cosa è successo e dove di preciso (via, negozio, parco, fermata). Se il testo dice come è finita (arresto,
denuncia, fuga), scrivilo; se non lo dice, non scrivere niente al riguardo.
- Il giorno è già accanto al riassunto: non ripeterlo, e non scrivere "a Busto Arsizio". Se l'articolo colloca il fatto
in un giorno diverso da quello indicato, segnalalo con "Dubbio: ".
- Racconta solo il fatto indicato (tipo, via, giorno). Se l'articolo ne racconta altri, lasciali fuori.
- Mai nomi, età, nazionalità, provenienza, professioni, parentele o altri dettagli sulle persone: scrivi "un uomo", \
"due ragazzi", "una donna". Niente targhe e niente numeri civici.
- Niente citazioni e niente frasi copiate dall'articolo: usa parole tue.
- Se l'articolo non racconta quel fatto, o lo colloca fuori da Busto Arsizio, scrivi "Dubbio: " e il motivo in poche \
parole."""
# Decisione dell'utente del 28/11/2026: nel furto in casa entrano anche box, cantine e parti comuni dei condomini
REGOLE_SOTTOTIPO = {
    'furto': """Sottotipo del furto: "casa" se il furto o il tentato furto è avvenuto in un'abitazione o nelle sue \
pertinenze: appartamento, casa, villa, box o garage, cantina, solaio, parti comuni di un condominio (androne, cortile, \
scale, garage condominiale). "nessuno" in tutti gli altri casi: negozi, bar, aziende, uffici, scuole, chiese, cimiteri, \
cantieri, auto o moto in strada, furti alle persone (borseggi, scippi, rapine in strada).""",
    'vandalismo': """Sottotipo del vandalismo o degrado: "rifiuti" se il fatto è un abbandono di rifiuti: sacchi, \
ingombranti, scarti edili, pneumatici, amianto, discariche abusive. "nessuno" per gli altri danneggiamenti e per il \
degrado senza rifiuti abbandonati (scritte, vetri rotti, arredi rotti, incendi).""",
}
PROMPT_SOLO_SOTTOTIPO = """Leggi un articolo di una testata locale di Busto Arsizio e scegli il sottotipo di un fatto già \
individuato (tipo, via e giorno sono indicati). Guarda solo quel fatto, non gli altri dell'articolo."""


def schema(riassunto, tipo):
    proprieta, richiesti = {}, []
    if riassunto:
        proprieta['riassunto'] = {'type': 'string', 'maxLength': 400}
        richiesti.append('riassunto')
    if tipo in SOTTOTIPI:
        proprieta['sottotipo'] = {'type': 'string', 'enum': [*SOTTOTIPI[tipo], NESSUNO]}
        richiesti.append('sottotipo')
    return {'type': 'object', 'additionalProperties': False, 'required': richiesti, 'properties': proprieta}


def istruzioni(riassunto, tipo):
    parti = [PROMPT if riassunto else PROMPT_SOLO_SOTTOTIPO]
    if tipo in SOTTOTIPI:
        parti.append(REGOLE_SOTTOTIPO[tipo])
    return '\n\n'.join(parti)


def testi(cartella):
    """Testi degli articoli per link, da tutti i file .jsonl della cartella che hanno il campo testo."""
    out = {}
    for percorso in sorted(Path(cartella).glob('*.jsonl')):
        with open(percorso, encoding='utf-8') as f:
            for riga in f:
                if '"testo"' not in riga:
                    continue
                try:
                    a = json.loads(riga)
                except json.JSONDecodeError:
                    continue
                if a.get('url') and a.get('testo') and len(a['testo']) > len(out.get(a['url'], {}).get('testo', '')):
                    out[a['url']] = a
    return out


def pubblicati():
    """Id dei fatti già pubblicati o già nella revisione, dal sito."""
    with tempfile.TemporaryDirectory() as tmp:
        for nome in ('data/notizie.json', 'revisione/notizie.tsv'):
            try:
                with urllib.request.urlopen(SITO + nome, timeout=60) as r:
                    (Path(tmp) / Path(nome).name).write_bytes(r.read())
            except urllib.error.HTTPError as err:
                # Il file della revisione non c'è finché non arriva la prima revisione
                if err.code != 404 or nome.endswith('.json'):
                    raise
        return noti(Path(tmp) / 'notizie.json', revisione(Path(tmp) / 'notizie.tsv'))


def da_fare(righe, ids):
    """(articolo, chiave, tipo, via, giorno, serve il riassunto, serve il sottotipo) dei fatti sulla mappa."""
    oggi = date.today()
    mappa = carica_mappa()
    riassunti = {r['url']: r.get(RIASSUNTI) or {} for r in righe}
    sottotipi = {r['url']: r.get(CAMPO_SOTTOTIPI) or {} for r in righe}
    out = []
    for gruppo in aggancia_seguiti(raggruppa(episodi_validi(righe, mappa, oggi - timedelta(days=FINESTRA_GIORNI), oggi), mappa)):
        _, primo, giorno, via = primo_episodio(gruppo, ids)
        tipo = gruppo[0]['categoria']
        chiave = chiave_riassunto(tipo, via, giorno)
        manca_riassunto = chiave not in riassunti.get(primo, {})
        manca_sottotipo = tipo in SOTTOTIPI and chiave not in sottotipi.get(primo, {})
        if manca_riassunto or manca_sottotipo:
            out.append((primo, chiave, tipo, via, giorno, manca_riassunto, manca_sottotipo))
    return out


def chiedi(messaggio, riassunto, tipo, cartella):
    comando = [shutil.which('claude') or 'claude', '-p', '--model', 'haiku', '--system-prompt', istruzioni(riassunto, tipo),
               '--json-schema', json.dumps(schema(riassunto, tipo)), '--output-format', 'json', '--tools', '',
               '--no-session-persistence', '--setting-sources', '', '--strict-mcp-config']
    uscita = subprocess.run(comando, input=messaggio, capture_output=True, text=True, encoding='utf-8',
                            cwd=cartella, timeout=300)
    try:
        r = json.loads(uscita.stdout)
    except json.JSONDecodeError:
        return None, (uscita.stderr or uscita.stdout)[-200:]
    if r.get('is_error') or 'structured_output' not in r:
        return None, str(r.get('result'))[-200:]
    return {k: v.strip() for k, v in r['structured_output'].items()}, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('testi')
    p.add_argument('memoria')
    p.add_argument('--paralleli', type=int, default=2)
    arg = p.parse_args()

    db = client()
    with tempfile.TemporaryDirectory() as tmp:
        esporta(db, Path(tmp) / 'episodi.jsonl')
        righe = leggi(Path(tmp) / 'episodi.jsonl')
    fatti = da_fare(righe, pubblicati())
    # memoria: {(url, chiave): {'riassunto': ..., 'sottotipo': ...}}; le righe vecchie hanno solo il riassunto
    memoria = {}
    if Path(arg.memoria).exists():
        for r in leggi(arg.memoria):
            memoria.setdefault((r['url'], r['chiave']), {}).update({k: r[k] for k in ('riassunto', 'sottotipo') if k in r})
    articoli = testi(arg.testi)
    domande = []
    for url, chiave, tipo, via, giorno, manca_riassunto, manca_sottotipo in fatti:
        visto = memoria.get((url, chiave), {})
        riassunto = manca_riassunto and 'riassunto' not in visto
        sottotipo = manca_sottotipo and 'sottotipo' not in visto
        if (riassunto or sottotipo) and url in articoli:
            domande.append((url, chiave, tipo, via, giorno, riassunto))
    print(f'{len(fatti)} fatti senza riassunto o sottotipo: {len(fatti) - len(domande)} già in memoria o senza testo, '
          f'{len(domande)} da chiedere a Haiku')

    def uno(domanda):
        url, chiave, tipo, via, giorno, riassunto = domanda
        a = articoli[url]
        messaggio = (f"Fatto: {NOMI_TIPI.get(tipo, tipo)}, in {via}, il {giorno}\n\n"
                     f"Testata: {a.get('fonte')}\nPubblicato: {(a.get('pubblicato') or a.get('visto') or '')[:10]}\n"
                     f"Titolo: {a.get('titolo', '')}\n\nTesto:\n{a['testo'][:MAX_TESTO]}")
        return domanda, *chiedi(messaggio, riassunto, tipo if tipo in SOTTOTIPI else None, cartella)

    cartella = tempfile.mkdtemp(prefix='riassunti-notizie-')
    errori = 0
    with open(arg.memoria, 'a', encoding='utf-8', newline='\n') as f, ThreadPoolExecutor(arg.paralleli) as pool:
        for (url, chiave, *_), risposta, errore in pool.map(uno, domande):
            if errore:
                errori += 1
                print(f'ERRORE {chiave}: {errore[:100]}', flush=True)
                continue
            memoria.setdefault((url, chiave), {}).update(risposta)
            f.write(json.dumps({'url': url, 'chiave': chiave, **risposta}, ensure_ascii=False) + '\n')
            f.flush()
            print(f"ok {chiave}{' · ' + risposta['sottotipo'] if 'sottotipo' in risposta else ''}", flush=True)

    for campo, nome in ((RIASSUNTI, 'riassunto'), (CAMPO_SOTTOTIPI, 'sottotipo')):
        nuovi = {}
        for url, chiave, *_ in fatti:
            if nome in memoria.get((url, chiave), {}):
                nuovi.setdefault(url, {})[chiave] = memoria[(url, chiave)][nome]
        aggiungi_riassunti(db, nuovi, campo)
    if errori:
        print(f'{errori} errori: rilancia lo stesso comando più tardi per finirli')


if __name__ == '__main__':
    sys.exit(main())
