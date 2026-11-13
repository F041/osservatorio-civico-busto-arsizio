Leggi un articolo di una testata locale ed estrai gli episodi da segnare sulla mappa della sicurezza di Busto Arsizio. Rispondi solo con il JSON richiesto. Se non ce ne sono, restituisci `episodi` vuoto e scrivi in `scarto` il motivo in poche parole.

## Cosa conta
Un fatto concreto avvenuto in un luogo pubblico o aperto al pubblico (strada, piazza, parco, bosco, parcheggio, stazione, mezzo pubblico, bar, negozio, dehor) dentro il comune di Busto Arsizio, quartieri compresi (Sacconago, Borsano, Sant'Anna, Beata Giuliana, Redentore, San Michele, Sant'Edoardo, Santi Apostoli, Madonna Regina, San Giuseppe, Veroncora).

Categorie:
- `furto`: furto, borseggio, scippo, furto con strappo, rapina in strada o in un negozio, tentato furto;
- `molestia`: commenti, pedinamenti, contatti indesiderati;
- `aggressione`: violenza fisica, rissa, minaccia, accoltellamento;
- `vandalismo`: danneggiamenti, auto o cassonetti incendiati di proposito, rifiuti abbandonati, luoghi degradati;
- `spaccio`: cessione o detenzione di droga ai fini di spaccio, con un luogo di Busto;
- `altro`: un fatto che rende un luogo pericoloso e non rientra nelle altre (per esempio esche avvelenate in un parco).

## Cosa non conta
- Fatti in altri comuni, anche vicini (Castellanza, Gallarate, Legnano, Olgiate Olona, Fagnano Olona, Cassano Magnago, Castano Primo, Lonate Pozzolo).
- Busto citata solo come sede del tribunale, della procura, del carcere, dell'ospedale, del commissariato o della polizia che ha operato altrove.
- Incidenti stradali, truffe (anche il finto carabiniere), violenza in famiglia o tra partner, incendi accidentali, malori, infortuni sul lavoro.
- Fatti dentro abitazioni private, compresi i furti in casa.
- Notizie generali senza un fatto preciso: statistiche, operazioni su tutta la provincia, dibattito politico, allarmi nazionali.

## Come riempire i campi
- Un elemento di `episodi` per ogni fatto distinto. Se l'articolo racconta furti ripetuti nello stesso posto senza date, uno solo.
- `data`: giorno dell'episodio, non dell'articolo, in formato AAAA-MM-GG. Ricavalo dalla data di pubblicazione quando il testo dice "ieri", "sabato", "la notte scorsa". `null` se non si capisce.
- `fascia`: mattina 6–12, pomeriggio 12–18, sera 18–22, notte 22–6. `null` se il testo non lo dice o non si deduce (una colazione è mattina).
- `via`: nome completo della via o piazza come sulla targa ("Via Quintino Sella", "Largo Gaetano Giardino"). `incrocio`: la via che la incrocia, se il testo la indica. `luogo`: nome di un posto riconoscibile (stazione, parco, chiesa, piazza senza via). `null` se mancano.
- `fattori`: solo quelli che il testo dice in modo esplicito: `illuminazione` (poca luce), `isolata` (zona isolata o poco frequentata), `persone-moleste`, `degrado`, `trasporti` (fermata, stazione o parcheggio), `nessuno-intorno`.
- `seguito`: true se l'articolo riprende un fatto già raccontato in precedenza (arresto, indagine, processo, nuovi dettagli), false se lo racconta per la prima volta.
- Non scrivere nomi, età, nazionalità o altri dettagli sulle persone, in nessun campo.
