"""Prova del motore delle notizie con Claude da Claude Code (`claude -p`), con l'abbonamento: niente API a pagamento.

Uso: uv run --no-project --python 3.12 python -I valutazione/prova_claude.py valutazione/dati/campione.jsonl \
         valutazione/dati/risposte-vie-haiku.jsonl [--modello haiku] [--paralleli 4]

Due passi, come nella pipeline:
1. filtro delle vie (scripts/vie_busto.py): l'articolo passa se nomina Busto e almeno una sua via o un suo luogo;
2. estrazione col modello, solo sugli articoli passati. Il campo `via` può essere solo una delle vie trovate.
Le chiamate partono da una cartella vuota, senza strumenti, impostazioni o server MCP, e non lasciano sessioni
salvate. Se il file di uscita esiste già, salta gli articoli fatti senza errori (si può riprendere).
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

QUI = Path(__file__).parent
sys.path.insert(0, str(QUI.parent / 'scripts'))
from vie_busto import Stradario  # noqa: E402

MAX_TESTO = 8000
CATEGORIE = ['furto', 'molestia', 'aggressione', 'vandalismo', 'spaccio', 'insicurezza', 'altro']
FASCE = ['mattina', 'pomeriggio', 'sera', 'notte']
FATTORI = ['illuminazione', 'isolata', 'persone-moleste', 'degrado', 'trasporti', 'nessuno-intorno']


def schema(vie):
    nomi = [v['nome'] for v in vie]
    return {
        'type': 'object', 'additionalProperties': False, 'required': ['episodi', 'scarto'],
        'properties': {
            'episodi': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['categoria', 'data', 'fascia', 'via', 'incrocio', 'luogo', 'fattori', 'seguito'],
                'properties': {
                    'categoria': {'enum': CATEGORIE},
                    'data': {'type': ['string', 'null'], 'pattern': r'^\d{4}-\d{2}-\d{2}$'},
                    'fascia': {'enum': FASCE + [None]},
                    'via': {'enum': nomi},
                    'incrocio': {'enum': nomi + [None]},
                    'luogo': {'type': ['string', 'null'], 'maxLength': 80},
                    'fattori': {'type': 'array', 'items': {'enum': FATTORI}},
                    'seguito': {'type': 'boolean'},
                }}},
            'scarto': {'type': ['string', 'null'], 'maxLength': 160},
        },
    }


def chiedi(modello, prompt, sch, messaggio, cartella):
    comando = [shutil.which('claude') or 'claude', '-p', '--model', modello, '--system-prompt', prompt,
               '--json-schema', json.dumps(sch), '--output-format', 'json', '--tools', '',
               '--no-session-persistence', '--setting-sources', '', '--strict-mcp-config']
    inizio = time.monotonic()
    uscita = subprocess.run(comando, input=messaggio, capture_output=True, text=True, encoding='utf-8',
                            cwd=cartella, timeout=300)
    secondi = round(time.monotonic() - inizio, 1)
    try:
        r = json.loads(uscita.stdout)
    except json.JSONDecodeError:
        return {'errore': (uscita.stderr or uscita.stdout)[-300:], 'secondi': secondi}
    if r.get('is_error') or 'structured_output' not in r:
        return {'errore': str(r.get('result'))[-300:], 'secondi': secondi}
    return {'risposta': r['structured_output'], 'secondi': secondi, 'costo_listino': r.get('total_cost_usd')}


def analizza(a, modello, prompt, stradario, cartella):
    pulito, vie = stradario.filtro(a)
    riga = {'id': a['id'], 'modello': modello, 'vie': [v['nome'] for v in vie]}
    if not vie:
        return riga | {'estrazione': None}
    elenco = '\n'.join(f"- {v['nome']}" + (' (nome ambiguo nello stradario)' if v['ambigua'] else '') for v in vie)
    messaggio = (f"Testata: {a['fonte']}\nPubblicato: {(a.get('pubblicato') or a['visto'])[:10]}\n"
                 f"Titolo: {a['titolo']}\nVie e luoghi di Busto nel testo:\n{elenco}\n\nTesto:\n{pulito[:MAX_TESTO]}")
    return riga | {'estrazione': chiedi(modello, prompt, schema(vie), messaggio, cartella)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('campione')
    p.add_argument('uscita')
    p.add_argument('--modello', default='haiku')
    p.add_argument('--paralleli', type=int, default=4)
    arg = p.parse_args()

    prompt = (QUI / 'prompt_estrazione.md').read_text(encoding='utf-8')
    stradario = Stradario()
    articoli = [json.loads(r) for r in open(arg.campione, encoding='utf-8') if r.strip()]
    fatte = []
    if Path(arg.uscita).exists():
        fatte = [json.loads(r) for r in open(arg.uscita, encoding='utf-8') if r.strip()]
        fatte = [r for r in fatte if not (r['estrazione'] or {}).get('errore')]
    noti = {r['id'] for r in fatte}
    da_fare = [a for a in articoli if a['id'] not in noti]
    print(f'{len(da_fare)} articoli da analizzare con {arg.modello}')

    cartella = tempfile.mkdtemp(prefix='prova-notizie-')
    with open(arg.uscita, 'w', encoding='utf-8', newline='\n') as f, ThreadPoolExecutor(arg.paralleli) as pool:
        for r in fatte:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
        for r in pool.map(lambda a: analizza(a, arg.modello, prompt, stradario, cartella), da_fare):
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
            f.flush()
            est = r['estrazione']
            stato = ('filtrato' if est is None else 'ERRORE ' + est['errore'][:80] if 'errore' in est
                     else f"episodi={len(est['risposta']['episodi'])} in {est['secondi']}s")
            print(f"{r['id']} {stato}", flush=True)


if __name__ == '__main__':
    sys.exit(main())
