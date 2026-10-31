// Panoramica Sicurezza: legge i conteggi aggregati da scripts/build_sicurezza.py (data/sicurezza.json)
import { CATEGORIE, FASCE, ZONE } from './sicurezza-config.js';

const overview = document.getElementById('overview');
const overviewTitle = document.getElementById('overview-title');
const overviewNote = document.getElementById('overview-note');

const integer = new Intl.NumberFormat('it-IT');
const formatDate = iso => iso.split('-').reverse().join('/');

function card(title) {
    const section = document.createElement('div');
    section.className = 'safety-card';
    const heading = document.createElement('h3');
    heading.textContent = title;
    section.append(heading);
    return section;
}

// Una riga per voce, nell'ordine del modulo; null = meno della soglia, mostrato senza barra
function barTable(options, counts, threshold) {
    const max = Math.max(1, ...options.map(o => counts[o.id] ?? 0));
    const table = document.createElement('table');
    table.className = 'bar-table';
    for (const option of options) {
        const value = counts[option.id];
        const row = table.insertRow();
        const label = document.createElement('th');
        label.scope = 'row';
        label.textContent = option.label;
        row.append(label);
        const barCell = row.insertCell();
        barCell.className = 'bar-cell';
        const numCell = row.insertCell();
        numCell.className = 'num';
        if (value === null) {
            const few = document.createElement('span');
            few.className = 'few';
            few.textContent = `meno di ${threshold}`;
            numCell.append(few);
        } else {
            if (value > 0) {
                const bar = document.createElement('div');
                bar.className = 'bar';
                bar.style.width = `${(value / max) * 100}%`;
                barCell.append(bar);
            }
            numCell.textContent = integer.format(value);
        }
    }
    return table;
}

fetch('data/sicurezza.json')
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(data => {
        overview.replaceChildren();
        overviewTitle.textContent = `Ultimi ${data.finestra_giorni} giorni (${formatDate(data.da)} – ${formatDate(data.a)})`;

        const totalCard = card('Segnalazioni');
        const total = document.createElement('p');
        total.className = 'safety-total';
        total.textContent = integer.format(data.totale);
        totalCard.append(total);
        if (data.totale === 0) {
            const empty = document.createElement('p');
            empty.className = 'safety-muted';
            empty.innerHTML = 'Ancora nessuna segnalazione. <a href="segnala.html">Fai la prima</a>.';
            totalCard.append(empty);
        }
        overview.append(totalCard);

        for (const [title, options, counts] of [['Per quartiere', ZONE, data.zone], ['Per tipo', CATEGORIE, data.categorie], ['Per fascia oraria', FASCE, data.fasce]]) {
            const section = card(title);
            section.append(barTable(options, counts, data.soglia));
            overview.append(section);
        }
        overviewNote.textContent = `Aggiornato il ${formatDate(data.generato.slice(0, 10))}. ` +
            `Per non rendere riconoscibile nessuno, i numeri sotto ${data.soglia} non vengono mostrati.`;
    })
    .catch(error => {
        console.error('Errore caricamento conteggi:', error);
        overview.replaceChildren();
        overviewNote.textContent = `Errore nel caricamento dei conteggi (${error.message}).`;
    });
