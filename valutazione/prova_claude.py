"""Prova del motore delle notizie con Claude da Claude Code (`claude -p`), con l'abbonamento: niente API a pagamento.

Uso: uv run --no-project --python 3.12 python -I valutazione/prova_claude.py valutazione/dati/campione.jsonl \
         valutazione/dati/risposte-haiku.jsonl [--modello haiku] [--paralleli 4]

Per ogni articolo lancia tutti e due i passi, anche quando la selezione scarterebbe l'articolo, così si misura
quanto perde il primo passo. Le chiamate partono da una cartella vuota, senza strumenti, impostazioni o server MCP,
e non lasciano sessioni salvate. Se il file di uscita esiste già, salta gli articoli fatti (si può riprendere).
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
MAX_TESTO = 8000
CATEGORIE = ['furto', 'molestia', 'aggressione', 'vandalismo', 'spaccio', 'altro']
FASCE = ['mattina', 'pomeriggio', 'sera', 'notte']
FATTORI = ['illuminazione', 'isolata', 'persone-moleste', 'degrado', 'trasporti', 'nessuno-intorno']


def nullabile(tipo, **extra):
    return {'type': [tipo, 'null'], **extra}


SCHEMA_SELEZIONE = {
    'type': 'object', 'additionalProperties': False, 'required': ['candidato', 'motivo'],
    'properties': {'candidato': {'type': 'boolean'}, 'motivo': {'type': 'string', 'maxLength': 120}},
}
SCHEMA_ESTRAZIONE = {
    'type': 'object', 'additionalProperties': False, 'required': ['episodi', 'scarto'],
    'properties': {
        'episodi': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['categoria', 'data', 'fascia', 'via', 'incrocio', 'luogo', 'fattori', 'seguito'],
            'properties': {
                'categoria': {'enum': CATEGORIE},
                'data': nullabile('string', pattern=r'^\d{4}-\d{2}-\d{2}$'),
                'fascia': {'enum': FASCE + [None]},
                'via': nullabile('string'), 'incrocio': nullabile('string'), 'luogo': nullabile('string'),
                'fattori': {'type': 'array', 'items': {'enum': FATTORI}},
                'seguito': {'type': 'boolean'},
            }}},
        'scarto': nullabile('string', maxLength=160),
    },
}


def chiedi(modello, prompt, schema, messaggio, cartella):
    comando = [shutil.which('claude') or 'claude', '-p', '--model', modello, '--system-prompt', prompt,
               '--json-schema', json.dumps(schema), '--output-format', 'json', '--tools', '',
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


def analizza(a, modello, prompt_sel, prompt_est, cartella):
    pubblicato = (a.get('pubblicato') or a['visto'])[:10]
    testata = f"Testata: {a['fonte']}\nPubblicato: {pubblicato}\n"
    sel = chiedi(modello, prompt_sel, SCHEMA_SELEZIONE,
                 testata + f"Categorie: {', '.join(a.get('categorie') or []) or '-'}\nTitolo: {a['titolo']}\n"
                 f"Riassunto: {a.get('sommario') or '-'}", cartella)
    est = chiedi(modello, prompt_est, SCHEMA_ESTRAZIONE,
                 testata + f"Titolo: {a['titolo']}\n\nTesto:\n{(a.get('testo') or '')[:MAX_TESTO]}", cartella)
    return {'id': a['id'], 'modello': modello, 'selezione': sel, 'estrazione': est}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('campione')
    p.add_argument('uscita')
    p.add_argument('--modello', default='haiku')
    p.add_argument('--paralleli', type=int, default=4)
    arg = p.parse_args()

    prompt_sel = (QUI / 'prompt_selezione.md').read_text(encoding='utf-8')
    prompt_est = (QUI / 'prompt_estrazione.md').read_text(encoding='utf-8')
    articoli = [json.loads(r) for r in open(arg.campione, encoding='utf-8') if r.strip()]
    fatti = set()
    if Path(arg.uscita).exists():
        fatti = {json.loads(r)['id'] for r in open(arg.uscita, encoding='utf-8') if r.strip()}
    da_fare = [a for a in articoli if a['id'] not in fatti]
    print(f'{len(da_fare)} articoli da analizzare con {arg.modello}')

    cartella = tempfile.mkdtemp(prefix='prova-notizie-')
    with open(arg.uscita, 'a', encoding='utf-8', newline='\n') as f, ThreadPoolExecutor(arg.paralleli) as pool:
        for r in pool.map(lambda a: analizza(a, arg.modello, prompt_sel, prompt_est, cartella), da_fare):
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
            f.flush()
            sel, est = r['selezione'], r['estrazione']
            stato = 'ERRORE' if 'errore' in sel or 'errore' in est else (
                f"sel={sel['risposta']['candidato']!s:5} episodi={len(est['risposta']['episodi'])}")
            print(f"{r['id']} {stato}  {sel['secondi']}s + {est['secondi']}s", flush=True)


if __name__ == '__main__':
    sys.exit(main())
