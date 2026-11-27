"""Riassunti dei fatti dalle notizie, per la pagina di revisione (revisione.html): 2 o 3 frasi su cosa è successo,
scritte da Haiku con `claude -p` e l'abbonamento (niente API a pagamento). Gira sul PC, dopo
`scripts/episodi_notizie.py carica`, perché servono i testi degli articoli, che restano solo sul PC.

Uso: uv run --no-project --python 3.12 --with google-cloud-firestore==2.34.1 python -I scripts/riassunti_notizie.py \
         <cartella con i testi *.jsonl> <memoria.jsonl> [--paralleli 2]

Riassume solo i fatti che finiscono sulla mappa e non hanno ancora un riassunto, uno per fatto, dal primo articolo
(lo stesso che dà l'id al fatto). Il riassunto va nel documento Firestore di quell'articolo, campo `riassunti`, con
chiave tipo|via|giorno; build_notizie.py lo mette in data/notizie.json. `memoria.jsonl` tiene i riassunti già fatti,
fuori dal repo: se il giro si interrompe (limite delle 5 ore) si riparte da lì.
Mai nomi, età o altri dettagli sulle persone: il riassunto è pubblico.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_notizie import FINESTRA_GIORNI, chiave_riassunto, episodi_validi, primo_episodio  # noqa: E402
from conciliazione import aggancia_seguiti, carica_mappa, raggruppa  # noqa: E402
from episodi_notizie import RIASSUNTI, aggiungi_riassunti, client, esporta, leggi  # noqa: E402

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
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['riassunto'],
          'properties': {'riassunto': {'type': 'string', 'maxLength': 400}}}


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


def da_riassumere(righe):
    """(articolo, chiave, tipo, via, giorno) dei fatti sulla mappa senza riassunto."""
    oggi = date.today()
    mappa = carica_mappa()
    fatti = {r['url']: r.get(RIASSUNTI) or {} for r in righe}
    out = []
    for gruppo in aggancia_seguiti(raggruppa(episodi_validi(righe, mappa, oggi - timedelta(days=FINESTRA_GIORNI), oggi), mappa)):
        primo, giorno, via = primo_episodio(gruppo)
        chiave = chiave_riassunto(gruppo[0]['categoria'], via, giorno)
        if chiave not in fatti.get(primo, {}):
            out.append((primo, chiave, gruppo[0]['categoria'], via, giorno))
    return out


def chiedi(messaggio, cartella):
    comando = [shutil.which('claude') or 'claude', '-p', '--model', 'haiku', '--system-prompt', PROMPT,
               '--json-schema', json.dumps(SCHEMA), '--output-format', 'json', '--tools', '',
               '--no-session-persistence', '--setting-sources', '', '--strict-mcp-config']
    uscita = subprocess.run(comando, input=messaggio, capture_output=True, text=True, encoding='utf-8',
                            cwd=cartella, timeout=300)
    try:
        r = json.loads(uscita.stdout)
    except json.JSONDecodeError:
        return None, (uscita.stderr or uscita.stdout)[-200:]
    if r.get('is_error') or 'structured_output' not in r:
        return None, str(r.get('result'))[-200:]
    return r['structured_output']['riassunto'].strip(), None


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
    fatti = da_riassumere(righe)
    memoria = {}
    if Path(arg.memoria).exists():
        for r in leggi(arg.memoria):
            memoria[(r['url'], r['chiave'])] = r['riassunto']
    articoli = testi(arg.testi)
    da_fare = [f for f in fatti if (f[0], f[1]) not in memoria and f[0] in articoli]
    print(f'{len(fatti)} fatti senza riassunto: {len(fatti) - len(da_fare)} già in memoria o senza testo, '
          f'{len(da_fare)} da chiedere a Haiku')

    def uno(fatto):
        url, chiave, tipo, via, giorno = fatto
        a = articoli[url]
        messaggio = (f"Fatto da riassumere: {NOMI_TIPI.get(tipo, tipo)}, in {via}, il {giorno}\n\n"
                     f"Testata: {a.get('fonte')}\nPubblicato: {(a.get('pubblicato') or a.get('visto') or '')[:10]}\n"
                     f"Titolo: {a.get('titolo', '')}\n\nTesto:\n{a['testo'][:MAX_TESTO]}")
        return fatto, *chiedi(messaggio, cartella)

    cartella = tempfile.mkdtemp(prefix='riassunti-notizie-')
    errori = 0
    with open(arg.memoria, 'a', encoding='utf-8', newline='\n') as f, ThreadPoolExecutor(arg.paralleli) as pool:
        for (url, chiave, *_), riassunto, errore in pool.map(uno, da_fare):
            if errore:
                errori += 1
                print(f'ERRORE {chiave}: {errore[:100]}', flush=True)
                continue
            memoria[(url, chiave)] = riassunto
            f.write(json.dumps({'url': url, 'chiave': chiave, 'riassunto': riassunto}, ensure_ascii=False) + '\n')
            f.flush()
            print(f'ok {chiave}', flush=True)

    nuovi = {}
    for url, chiave, *_ in fatti:
        if (url, chiave) in memoria:
            nuovi.setdefault(url, {})[chiave] = memoria[(url, chiave)]
    aggiungi_riassunti(db, nuovi)
    if errori:
        print(f'{errori} errori: rilancia lo stesso comando più tardi per finirli')


if __name__ == '__main__':
    sys.exit(main())
