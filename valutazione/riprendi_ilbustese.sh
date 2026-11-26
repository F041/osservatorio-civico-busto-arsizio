#!/usr/bin/env bash
# Recupero di ilBustese per il periodo tenuto dalla raccolta, 24 mesi (all'inizio solo il 2026, da qui i nomi dei file), in più giorni. Si può fermare quando si vuole (Ctrl+C o spegnendo il PC): rilanciato,
# riparte da dove era. Il sito rallenta le richieste in blocco, quindi una richiesta alla volta.
# L'elenco legge al massimo 100 giorni per giro, per la quota giornaliera di Firestore (vedi storico_2026.py): lanciarlo
# dopo le 9 e una volta al giorno finché l'elenco non è completo.
# Uso, da Git Bash nella cartella del repo: bash valutazione/riprendi_ilbustese.sh
# L'avanzamento finisce anche in valutazione/dati/ilbustese-2026.log
set -u
cd "$(dirname "$0")/.."
D=valutazione/dati
mkdir -p "$D"
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
FS="--with google-cloud-firestore==2.34.1"
py() { uv run --no-project --python 3.12 "$@" 2>&1 | grep --line-buffered -v -i "socks\|warnings.warn"; }
passo() { echo "== $(date '+%d/%m %H:%M') $*"; }
analisi() {
  [ -s "$D/testi-storico2026-ilbustese.jsonl" ] || return 0
  py python -I valutazione/prova_claude.py "$D/testi-storico2026-ilbustese.jsonl" \
    "$D/risposte-vie-haiku-storico2026-ilbustese.jsonl" --modello haiku --paralleli 2 \
    | grep --line-buffered -vE "filtrato|episodi="
}

{
passo "1. elenco dell'archivio, un giorno alla volta, al massimo 100 giorni"
py $FS python -I valutazione/storico_2026.py ilbustese

passo "2. copia locale dell'elenco di ilBustese"
py $FS python -I valutazione/storico_2026.py esporta "$D/articoli-2026-ilbustese.jsonl" ilbustese

passo "3. testi, dai più recenti; ogni ora l'analisi di quelli già scaricati"
py --with trafilatura python -I valutazione/prepara_campione.py "$D/articoli-2026-ilbustese.jsonl" storico2026 ilbustese &
TESTI=$!
while kill -0 $TESTI 2>/dev/null; do
  for _ in $(seq 60); do kill -0 $TESTI 2>/dev/null || break; sleep 60; done
  passo "analisi dei testi scaricati finora"
  analisi
done

passo "4. analisi finale"
analisi
passo "fine"
} 2>&1 | tee -a "$D/ilbustese-2026.log"
