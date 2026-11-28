#!/usr/bin/env bash
# Recupero del 2024 prima della finestra della raccolta, per gli studi statistici: elenco, testi e analisi con Haiku,
# tutto in locale (valutazione/dati, esclusa da git), niente Firestore. Vedi valutazione/storico_2024.py.
# Si può fermare quando si vuole (Ctrl+C o spegnendo il PC): rilanciato, riparte da dove era.
# Le altre testate partono subito. ilBustese rallenta le richieste in blocco: si comincia solo quando il recupero
# del 2026 (riprendi_ilbustese.sh) ha finito di scaricare, poi si riprovano una volta i suoi testi rimasti senza
# risposta (503) e si passa al 2024. Mentre questo script scarica da ilBustese non lanciare riprendi_ilbustese.sh.
# Uso, da Git Bash nella cartella del repo: bash valutazione/riprendi_2024.sh
# L'avanzamento finisce anche in valutazione/dati/storico-2024.log
set -u
cd "$(dirname "$0")/.."
D=valutazione/dati
mkdir -p "$D"
export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
py() { uv run --no-project --python 3.12 "$@" 2>&1 | grep --line-buffered -v -i "socks\|warnings.warn"; }
passo() { echo "== $(date '+%d/%m %H:%M') $*"; }
analizza() {
  [ -s "$D/testi-$1.jsonl" ] || return 0
  py python -I valutazione/prova_claude.py "$D/testi-$1.jsonl" "$D/risposte-vie-haiku-$1.jsonl" --modello haiku \
    --paralleli 2 | grep --line-buffered -vE "filtrato|episodi="
}
analisi() { analizza storico2024-altre; analizza storico2024-ilbustese; }
# Quanti processi scaricano i testi del 2026 da ilBustese (Python visto da Windows, con la sua riga di comando)
scarica_2026() {
  powershell.exe -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'storico2026 ilbustese' }).Count" | tr -d '\r'
}
# Aspetta finché la condizione è vera, con l'analisi dei testi scaricati ogni ora
aspetta() {
  while eval "$1"; do
    for _ in $(seq 60); do eval "$1" || break; sleep 60; done
    passo "analisi dei testi del 2024 scaricati finora"
    analisi
  done
}

{
passo "1. elenco 2024 di Malpensa24, VareseNews e Prealpina"
py python -I valutazione/storico_2024.py veloci

passo "2. testi 2024 delle altre testate, in sottofondo"
py --with trafilatura python -I valutazione/prepara_campione.py "$D/articoli-2024.jsonl" storico2024 &
ALTRE=$!

passo "3. ilBustese: si aspetta che il recupero del 2026 finisca di scaricare"
aspetta '[ "$(scarica_2026)" != 0 ]'

passo "4. testi del 2026 di ilBustese rimasti senza risposta, una volta, e la loro analisi"
py --with trafilatura python -I valutazione/prepara_campione.py "$D/articoli-2026-ilbustese.jsonl" storico2026 ilbustese
analizza storico2026-ilbustese

passo "5. elenco 2024 di ilBustese, due giri per i giorni rimasti con un errore"
py python -I valutazione/storico_2024.py ilbustese
py python -I valutazione/storico_2024.py ilbustese

passo "6. testi 2024 di ilBustese, dai più recenti; un secondo giro per quelli senza risposta"
( py --with trafilatura python -I valutazione/prepara_campione.py "$D/articoli-2024.jsonl" storico2024 ilbustese
  py --with trafilatura python -I valutazione/prepara_campione.py "$D/articoli-2024.jsonl" storico2024 ilbustese ) &
BUSTESE=$!
aspetta 'kill -0 $ALTRE 2>/dev/null || kill -0 $BUSTESE 2>/dev/null'

passo "7. analisi finale"
analisi
passo "fine"
} 2>&1 | tee -a "$D/storico-2024.log"
