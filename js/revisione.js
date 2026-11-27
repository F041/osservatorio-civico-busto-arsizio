// Revisione dei fatti delle notizie: elenca i fatti di data/notizie.json con i link agli articoli, per controllarli.
// La pull request di revisione apre questa pagina con ?id=… e i soli fatti nuovi; senza, tutti, dai più recenti.
import { formatDate } from './formato.js';
import { TESTATE, TIPI } from './notizie.js';

const tabella = document.getElementById('fatti');
const stato = document.getElementById('stato');
const titolo = document.getElementById('titolo');
const scelti = new Set((new URLSearchParams(location.search).get('id') ?? '').split(',').filter(Boolean));

function cella(riga, testo) {
    const c = riga.insertCell();
    c.textContent = testo;
    return c;
}

fetch('data/notizie.json')
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(dati => {
        const fatti = dati.fatti.filter(f => !scelti.size || scelti.has(f.id)).reverse();
        if (scelti.size) titolo.textContent = 'Fatti nuovi da controllare';
        const mancanti = scelti.size - fatti.length;
        stato.textContent = `${fatti.length} ${fatti.length === 1 ? 'fatto' : 'fatti'}` +
            (mancanti === 1 ? '. Uno non è più sulla mappa: già tolto o uscito dai 24 mesi.'
                : mancanti > 1 ? `. ${mancanti} non sono più sulla mappa: già tolti o usciti dai 24 mesi.` : '.');
        const corpo = tabella.tBodies[0];
        for (const f of fatti) {
            const riga = corpo.insertRow();
            cella(riga, formatDate(f.data));
            cella(riga, TIPI[f.tipo] ?? f.tipo);
            cella(riga, f.via);
            const articoli = riga.insertCell();
            const elenco = document.createElement('ul');
            for (const a of f.articoli) {
                const voce = document.createElement('li');
                const link = document.createElement('a');
                link.href = a.url;
                link.target = '_blank';
                link.rel = 'noopener';
                link.textContent = `${TESTATE[a.fonte] ?? a.fonte}, ${formatDate(a.data)}`;
                voce.append(link);
                elenco.append(voce);
            }
            articoli.append(elenco);
            cella(riga, f.id).className = 'review-id';
        }
        tabella.hidden = !fatti.length;
    })
    .catch(err => {
        console.error('Errore nel caricamento dei fatti:', err);
        stato.textContent = `Non riesco a caricare i fatti (${err.message}).`;
    });
