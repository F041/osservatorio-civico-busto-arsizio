#!/usr/bin/env bash
# Recupero del periodo tenuto dalla raccolta, 24 mesi (all'inizio solo il 2026, da qui i nomi dei file), per Malpensa24, Prealpina e VareseNews, poi testi e analisi. Rilanciato, riparte da dove era.
# Uso, da Git Bash nella cartella del repo: bash valutazione/recupero_veloci.sh
# L'avanzamento finisce anche in valutazione/dati/veloci-2026.log
set -u
cd "$(dirname "$0")/.."
D=valutazione/dati
mkdir -p "$D"
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
FS="--with google-cloud-firestore==2.34.1"
py() { uv run --no-project --python 3.12 "$@" 2>&1 | grep --line-buffered -v -i "socks\|warnings.warn"; }
passo() { echo "== $(date '+%d/%m %H:%M') $*"; }

{
# Ogni copia completa legge tutta la collezione (oltre 10.000 letture della quota giornaliera, vedi storico_2026.py):
# quella del giro precedente basta per le date già note
if [ ! -s "$D/articoli-2026.jsonl" ]; then
  passo "1. copia locale dell'elenco attuale (date già note)"
  py $FS python -I valutazione/storico_2026.py esporta "$D/articoli-2026.jsonl"
fi

passo "2. elenco dall'inizio del periodo"
py $FS python -I valutazione/storico_2026.py veloci "$D/articoli-2026.jsonl"

passo "3. copia locale dell'elenco nuovo"
py $FS python -I valutazione/storico_2026.py esporta "$D/articoli-2026.jsonl"

passo "4. testi, dai più recenti"
py --with trafilatura python -I valutazione/prepara_campione.py "$D/articoli-2026.jsonl" storico2026

passo "5. analisi"
py python -I valutazione/prova_claude.py "$D/testi-storico2026-altre.jsonl" "$D/risposte-vie-haiku-storico2026-altre.jsonl" \
  --modello haiku --paralleli 3 | grep --line-buffered -vE "filtrato|episodi="
passo "fine"
} 2>&1 | tee -a "$D/veloci-2026.log"
