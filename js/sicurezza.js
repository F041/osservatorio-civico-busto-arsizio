// Panoramica Sicurezza: legge i conteggi aggregati da scripts/build_sicurezza.py (data/sicurezza.json)
import { CATEGORIE, FASCE } from './sicurezza-config.js';
import { caricaMappa, creaMappa, confiniCella, descriviCella } from './mappa.js';

const overview = document.getElementById('overview');
const overviewTitle = document.getElementById('overview-title');
const overviewNote = document.getElementById('overview-note');

const integer = new Intl.NumberFormat('it-IT');
const formatDate = iso => iso.split('-').reverse().join('/');

// Classi della mappa: un solo tono di blu, più segnalazioni = più scuro. La prima parte dalla soglia.
const CLASSI = [
    { da: 20, colore: '#104281' },
    { da: 10, colore: '#256abf' },
    { da: 5, colore: '#5598e7' },
    { da: 0, colore: '#9ec5f4' },
];

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

// Quadrati con almeno `soglia` segnalazioni: mappa, legenda e la stessa informazione in tabella
function mapCard(data, mappa) {
    const section = card(`Dove: zone con almeno ${data.soglia} segnalazioni`);
    section.classList.add('safety-card-wide');
    const mapDiv = document.createElement('div');
    mapDiv.className = 'overview-map';
    mapDiv.setAttribute('aria-label', 'Mappa delle zone con più segnalazioni; gli stessi dati sono nella tabella sotto');
    section.append(mapDiv);

    const classi = CLASSI.map((c, i) => {
        const da = Math.max(c.da, data.soglia);
        const a = i > 0 ? CLASSI[i - 1].da - 1 : null;
        return { ...c, da, label: a === null ? `${da} e più` : `${da}–${a}` };
    });
    const legend = document.createElement('ul');
    legend.className = 'chart-legend';
    for (const classe of [...classi].reverse()) {
        const item = document.createElement('li');
        const swatch = document.createElement('span');
        swatch.className = 'chart-swatch';
        swatch.style.background = classe.colore;
        item.append(swatch, classe.label);
        legend.append(item);
    }
    section.append(legend);

    const celle = Object.entries(data.celle).sort((a, b) => b[1] - a[1]);
    const note = document.createElement('p');
    note.className = 'safety-muted';
    section.append(note);

    // Leaflet va creato quando la scheda è già nella pagina, altrimenti non ne conosce le dimensioni
    requestAnimationFrame(() => {
        const L = window.L;
        const map = creaMappa(mapDiv, mappa, { griglia: false, tenue: true });
        const quadrati = new Map();
        for (const [id, n] of celle) {
            const colore = classi.find(c => n >= c.da).colore;
            quadrati.set(id, L.rectangle(confiniCella(mappa.griglia, id), { color: '#ffffff', weight: 1.5, fillColor: colore, fillOpacity: 0.85 })
                .bindTooltip(`${descriviCella(mappa, id)}: ${integer.format(n)} segnalazioni`, { sticky: true })
                .addTo(map));
        }
        // Si parte inquadrando le zone segnalate, non tutto il comune
        if (quadrati.size) map.fitBounds(L.featureGroup([...quadrati.values()]).getBounds(), { padding: [40, 40], maxZoom: 15 });
        for (const row of section.querySelectorAll('tr[data-cella]')) {
            row.querySelector('button').addEventListener('click', () => {
                const rect = quadrati.get(row.dataset.cella);
                map.fitBounds(rect.getBounds(), { maxZoom: 16 });
                rect.openTooltip(rect.getBounds().getCenter());
                mapDiv.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            });
        }
    });

    if (!celle.length) {
        note.textContent = `Ancora nessuna zona con almeno ${data.soglia} segnalazioni negli ultimi ${data.finestra_giorni} giorni.`;
        return section;
    }
    note.textContent = 'Ogni zona è un quadrato di circa 250 metri, indicato con le vie principali che contiene.';
    const table = document.createElement('table');
    table.className = 'bar-table zone-table';
    table.createCaption().textContent = 'Zone con più segnalazioni';
    for (const [id, n] of celle.slice(0, 10)) {
        const row = table.insertRow();
        row.dataset.cella = id;
        const label = document.createElement('th');
        label.scope = 'row';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'link-button';
        button.textContent = descriviCella(mappa, id);
        button.title = 'Mostra sulla mappa';
        label.append(button);
        row.append(label);
        const barCell = row.insertCell();
        barCell.className = 'bar-cell';
        const bar = document.createElement('div');
        bar.className = 'bar';
        bar.style.width = `${(n / celle[0][1]) * 100}%`;
        barCell.append(bar);
        const numCell = row.insertCell();
        numCell.className = 'num';
        numCell.textContent = integer.format(n);
    }
    section.append(table);
    return section;
}

Promise.all([
    fetch('data/sicurezza.json').then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); }),
    caricaMappa(),
])
    .then(([data, mappa]) => {
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
        const byType = card('Per tipo');
        byType.append(barTable(CATEGORIE, data.categorie, data.soglia));
        const byTime = card('Per fascia oraria');
        byTime.append(barTable(FASCE, data.fasce, data.soglia));
        overview.append(mapCard(data, mappa), totalCard, byType, byTime);

        overviewNote.textContent = `Aggiornato il ${formatDate(data.generato.slice(0, 10))}. ` +
            `Per non rendere riconoscibile nessuno, i numeri sotto ${data.soglia} non vengono mostrati.`;
    })
    .catch(error => {
        console.error('Errore caricamento conteggi:', error);
        overview.replaceChildren();
        overviewNote.textContent = `Errore nel caricamento dei conteggi (${error.message}).`;
    });
