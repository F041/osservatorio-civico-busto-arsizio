Leggi un articolo di una testata locale ed estrai gli episodi da segnare sulla mappa della sicurezza di Busto Arsizio. Rispondi solo con il JSON richiesto. Se non ce ne sono, restituisci `episodi` vuoto e scrivi in `scarto` il motivo in poche parole.

Insieme all'articolo ricevi l'elenco delle vie e dei luoghi di Busto che compaiono nel testo, trovati con lo stradario. Un episodio va sulla mappa solo se è avvenuto in una di quelle vie o in uno di quei luoghi.

## Cosa conta
Un fatto concreto avvenuto nel comune di Busto Arsizio, quartieri compresi, in un luogo pubblico o aperto al pubblico (strada, piazza, parco, bosco, parcheggio, stazione, mezzo pubblico, bar, negozio, dehor). Contano anche i furti e i tentati furti in casa.

Categorie:
- `furto`: furto, borseggio, scippo, furto con strappo, rapina in strada o in un negozio, furto in casa o in auto, tentato furto;
- `molestia`: commenti, pedinamenti, contatti indesiderati, atti osceni;
- `aggressione`: violenza fisica, rissa, minaccia, accoltellamento;
- `vandalismo`: danneggiamenti, incendi appiccati o sospetti in luoghi abbandonati, rifiuti abbandonati, luoghi degradati, esche avvelenate per animali;
- `spaccio`: cessione o detenzione di droga ai fini di spaccio, anche uno spaccio ripetuto in un luogo preciso senza una data (per esempio droga nascosta in un posto e venduta lì): è `spaccio`, non `insicurezza`;
- `insicurezza`: residenti o commercianti che denunciano problemi ricorrenti in una via precisa (risse, schiamazzi, degrado), senza un singolo fatto con una data;
- `allagamento`: sottopasso, strada o piazza allagata dalla pioggia, con pericolo o disagi per chi passa (auto bloccate, sottopasso chiuso). Un episodio per ogni via o sottopasso allagato;
- `altro`: un fatto che rende un luogo pericoloso e non rientra nelle altre.

## Cosa non conta
- Fatti in altri comuni, anche vicini (Castellanza, Gallarate, Legnano, Olgiate Olona, Fagnano Olona, Cassano Magnago, Castano Primo, Lonate Pozzolo). Lo stradario è solo di Busto, ma una "via Roma" nel testo può essere di un altro comune: controlla dove è avvenuto il fatto.
- Busto citata solo come sede del tribunale, della procura, del carcere, dell'ospedale, del commissariato o della polizia che ha operato altrove.
- Incidenti stradali, truffe (anche il finto carabiniere), violenza in famiglia o tra partner, incendi accidentali, malori, suicidi e tentati suicidi, infortuni sul lavoro, fatti dentro il carcere.
- Restauri, lavori e riqualificazioni di un luogo, anche se l'articolo ricorda che era rovinato o abbandonato. Crolli e guasti di edifici o strutture.
- Inseguimenti in auto e fughe dalla polizia, se il testo non racconta un altro reato accertato in quella via.
- Fatti dentro abitazioni private, tranne i furti.
- Notizie generali senza un fatto o un luogo preciso: statistiche, operazioni su tutta la provincia, dibattito politico, allarmi nazionali. Non contano gli allarmi bomba o le minacce mandate via mail, anche se hanno fatto evacuare una scuola di Busto.
- Fatti di cui il testo non dice la via o il luogo, o avvenuti in una via che non è nell'elenco.
- Ricordi e aneddoti di anni prima, anche se raccontano una molestia o un furto.
- Sporcizia, macchie o danni lasciati da mercati, fiere, concerti ed eventi autorizzati.
- Volantini, manifesti, striscioni e proteste politiche; insulti o contestazioni a un politico.
- Auto, cassonetti o altro che prendono fuoco se il testo non parla di incendio doloso o sospetto.
- Altri danni del maltempo (alberi caduti, tetti scoperchiati), buche, guasti e disservizi: non sono fatti di
  sicurezza, anche se un luogo diventa pericoloso. Gli allagamenti invece contano, come `allagamento`.
- Elenchi di luoghi citati in un consiglio comunale, in un'assemblea o in un dibattito, senza un fatto preciso.
- Fatti su un treno: contano solo se avvenuti in una stazione di Busto o sul treno fermo lì. Non contano se a Busto
  c'è stato solo l'arresto, la fuga o l'intervento della polizia.

## Come riempire i campi
- Un elemento di `episodi` per ogni fatto distinto. Se l'articolo racconta furti ripetuti nello stesso posto senza date, uno solo. Più colpi nella stessa via e nello stesso giorno sono un episodio solo. Furti segnalati in un'altra via nei giorni precedenti, senza date, sono un episodio con `data` null.
- `via`: la via o il luogo dell'elenco dove è avvenuto il fatto, scritto esattamente come nell'elenco. `incrocio`: un'altra via dell'elenco, se il testo dice che il fatto è avvenuto all'incrocio. `luogo`: il posto preciso in poche parole (un bar, una fermata, un parcheggio), senza nomi di persone.
- `data`: giorno dell'episodio, non dell'articolo, in formato AAAA-MM-GG. Ricavalo dalla data di pubblicazione quando il testo dice "ieri", "sabato", "la notte scorsa". Se un fatto è stato scoperto dopo, vale il giorno in cui è avvenuto. `null` se non si capisce.
- `fascia`: mattina 6–12, pomeriggio 12–18, sera 18–22, notte 22–6. `null` se il testo non lo dice e non si deduce.
- `fattori`: solo quelli che il testo dice in modo esplicito: `illuminazione` (poca luce), `isolata` (zona isolata o poco frequentata), `persone-moleste`, `degrado`, `trasporti` (fermata, stazione o parcheggio), `nessuno-intorno`.
- `seguito`: true solo se il testo mostra che il fatto era già noto: cita una notizia precedente, oppure parla del processo o degli sviluppi di un fatto avvenuto tempo prima (convalida, foglio di via, espulsione), oppure riporta commenti, reazioni o polemiche su un fatto già raccontato. false se l'articolo racconta il fatto per la prima volta, anche quando si chiude con un arresto.
- Non scrivere nomi, età, nazionalità o altri dettagli sulle persone, in nessun campo.
