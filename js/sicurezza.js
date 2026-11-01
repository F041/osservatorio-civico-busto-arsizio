// Panoramica Sicurezza: legge i conteggi aggregati da scripts/build_sicurezza.py (data/sicurezza.json)
import { CATEGORIE, FASCE, FATTORI, DENUNCIA } from './sicurezza-config.js';
import { caricaMappa, creaMappa, confiniCella, descriviCella } from './mappa.js';

const overview = document.getElementById('overview');
const overviewTitle = document.getElementById('overview-title');
const overviewNote = document.getElementById('overview-note');

const integer = new Intl.NumberFormat('it-IT');
const formatDate = iso => iso.split('-').reverse().join('/');

// Classi della mappa: soglie delle quattro intensità, dalla più alta. La più bassa parte dalla soglia.
const CLASSI = [20, 10, 5, 0];

// Scale a quattro intensità, dalla più chiara (validate con la skill dataviz: tinta unica, contrasto >= 2:1 sulla mappa).
// Ogni tipo ha la sua tinta, ripresa dalle barre di "Per tipo"; tutte le altre viste usano il blu.
const SCALA_BLU = ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b'];
const COLORI_TIPO = {
    insicurezza: { barra: '#eb6834', scala: ['#fe8e66', '#e05e29', '#b03e03', '#7b2903'] },
    furto: { barra: '#1baf7a', scala: ['#40c68f', '#08a26f', '#007d54', '#025639'] },
    molestia: { barra: '#6250d6', scala: ['#a7a6fe', '#8174fd', '#604ed4', '#4324ab'] },
    aggressione: { barra: '#eda100', scala: ['#eaa015', '#bb7e03', '#8d5e03', '#614003'] },
    vandalismo: { barra: '#008300', scala: ['#5dc657', '#37a332', '#068005', '#055804'] },
    altro: { barra: '#898781', scala: ['#b3b1ab', '#8e8c86', '#6b6963', '#494842'] },
};

// Viste della mappa: tutte le segnalazioni o una sola voce alla volta (mai due incrociate, per non rendere riconoscibile nessuno)
const GRUPPI_FILTRO = [
    { campo: 'categoria', titolo: 'Tipo', voci: CATEGORIE },
    { campo: 'fascia', titolo: 'Fascia oraria', voci: FASCE },
    { campo: 'fattori', titolo: 'Cosa ha contribuito', voci: FATTORI },
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
function barTable(options, counts, threshold, colori) {
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
                if (colori?.[option.id]) bar.style.background = colori[option.id].barra;
                barCell.append(bar);
            }
            numCell.textContent = integer.format(value);
        }
    }
    return table;
}

// Quadrati con almeno `soglia` segnalazioni: filtro, mappa, legenda e la stessa informazione in tabella
function mapCard(data, mappa) {
    const section = card(`Dove: zone con almeno ${data.soglia} segnalazioni`);
    section.classList.add('safety-card-wide');

    const filterRow = document.createElement('div');
    filterRow.className = 'map-filter';
    const filterLabel = document.createElement('label');
    filterLabel.htmlFor = 'map-filter';
    filterLabel.textContent = 'Mostra';
    const select = document.createElement('select');
    select.id = 'map-filter';
    select.append(new Option('Tutte le segnalazioni', ''));
    for (const gruppo of GRUPPI_FILTRO) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = gruppo.titolo;
        optgroup.append(...gruppo.voci.map(v => new Option(v.label, `${gruppo.campo}.${v.id}`)));
        select.append(optgroup);
    }
    const reset = document.createElement('button');
    reset.type = 'button';
    reset.className = 'link-button';
    reset.textContent = 'Mostra tutte';
    filterRow.append(filterLabel, select, reset);
    const filterHint = document.createElement('p');
    filterHint.className = 'safety-muted map-filter-hint';
    filterHint.textContent = 'Una voce alla volta: incrociarne due, per esempio tipo e orario, renderebbe più riconoscibili le persone.';
    section.append(filterRow, filterHint);

    const mapDiv = document.createElement('div');
    mapDiv.className = 'overview-map';
    mapDiv.setAttribute('aria-label', 'Mappa delle zone con più segnalazioni; gli stessi dati sono nella tabella sotto');
    const legend = document.createElement('ul');
    legend.className = 'chart-legend';
    const note = document.createElement('p');
    note.className = 'safety-muted';
    note.setAttribute('aria-live', 'polite');
    const tableWrap = document.createElement('div');
    section.append(mapDiv, legend, note, tableWrap);

    const classi = CLASSI.map((da, i) => {
        const minimo = Math.max(da, data.soglia);
        return { da: minimo, label: i === 0 ? `${minimo} e più` : `${minimo}–${CLASSI[i - 1] - 1}` };
    });

    // Leaflet va creato quando la scheda è già nella pagina, altrimenti non ne conosce le dimensioni
    let map = null;
    const quadrati = window.L.layerGroup();
    const rettangoli = new Map();
    const mappaPronta = new Promise(resolve => requestAnimationFrame(() => {
        map = creaMappa(mapDiv, mappa, { griglia: false, tenue: true });
        quadrati.addTo(map);
        // Si parte inquadrando le zone segnalate, non tutto il comune; cambiando filtro la vista resta ferma
        const tutte = Object.keys(data.celle).flatMap(id => confiniCella(mappa.griglia, id));
        if (tutte.length) map.fitBounds(window.L.latLngBounds(tutte), { padding: [40, 40], maxZoom: 15 });
        resolve();
    }));

    function mostra(valore) {
        const [campo, voce] = valore ? valore.split('.') : [];
        const opzione = campo && GRUPPI_FILTRO.find(g => g.campo === campo)?.voci.find(v => v.id === voce);
        if (valore && !opzione) return mostra('');
        select.value = valore;
        reset.hidden = !valore;
        const celle = Object.entries(valore ? data.celle_per?.[campo]?.[voce] ?? {} : data.celle).sort((a, b) => b[1] - a[1]);
        const scala = campo === 'categoria' ? COLORI_TIPO[voce].scala : SCALA_BLU;
        const colore = n => scala[3 - classi.findIndex(c => n >= c.da)];
        const nome = opzione ? `«${opzione.label}»` : '';

        // Il filtro resta nell'indirizzo, così la vista si può condividere (senza aggiungere passi al tasto Indietro)
        const url = new URL(location.href);
        if (valore) url.searchParams.set('mostra', valore); else url.searchParams.delete('mostra');
        history.replaceState(null, '', url);

        legend.replaceChildren(...classi.map((classe, i) => {
            const item = document.createElement('li');
            const swatch = document.createElement('span');
            swatch.className = 'chart-swatch';
            swatch.style.background = scala[3 - i];
            item.append(swatch, classe.label);
            return item;
        }).reverse());

        mappaPronta.then(() => {
            quadrati.clearLayers();
            rettangoli.clear();
            for (const [id, n] of celle) {
                const testo = `${descriviCella(mappa, id)}: ${integer.format(n)} segnalazioni${nome ? ` ${nome}` : ''}`;
                const rect = window.L.rectangle(confiniCella(mappa.griglia, id), { color: '#ffffff', weight: 1.5, fillColor: colore(n), fillOpacity: 0.85 })
                    .bindTooltip(testo, { sticky: true });
                quadrati.addLayer(rect);
                rettangoli.set(id, rect);
            }
        });

        tableWrap.replaceChildren();
        if (!celle.length) {
            note.textContent = valore
                ? `Nessuna zona con almeno ${data.soglia} segnalazioni ${nome} negli ultimi ${data.finestra_giorni} giorni.`
                : `Ancora nessuna zona con almeno ${data.soglia} segnalazioni negli ultimi ${data.finestra_giorni} giorni.`;
            return;
        }
        note.textContent = 'Ogni zona è un quadrato di circa 250 metri, indicato con le vie principali che contiene.';
        const table = document.createElement('table');
        table.className = 'bar-table zone-table';
        table.createCaption().textContent = valore ? `Zone con più segnalazioni ${nome}` : 'Zone con più segnalazioni';
        for (const [id, n] of celle.slice(0, 10)) {
            const row = table.insertRow();
            const label = document.createElement('th');
            label.scope = 'row';
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'link-button';
            button.textContent = descriviCella(mappa, id);
            button.title = 'Mostra sulla mappa';
            button.addEventListener('click', () => {
                const rect = rettangoli.get(id);
                map.fitBounds(rect.getBounds(), { maxZoom: 16 });
                rect.openTooltip(rect.getBounds().getCenter());
                mapDiv.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            });
            label.append(button);
            row.append(label);
            const barCell = row.insertCell();
            barCell.className = 'bar-cell';
            const bar = document.createElement('div');
            bar.className = 'bar';
            bar.style.width = `${(n / celle[0][1]) * 100}%`;
            bar.style.background = scala[1];
            barCell.append(bar);
            const numCell = row.insertCell();
            numCell.className = 'num';
            numCell.textContent = integer.format(n);
        }
        tableWrap.append(table);
    }

    select.addEventListener('change', () => mostra(select.value));
    reset.addEventListener('click', () => { mostra(''); select.focus(); });
    mostra(new URLSearchParams(location.search).get('mostra') ?? '');
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
        byType.append(barTable(CATEGORIE, data.categorie, data.soglia, COLORI_TIPO));
        const byTime = card('Per fascia oraria');
        byTime.append(barTable(FASCE, data.fasce, data.soglia));
        const byFactor = card('Cosa ha contribuito');
        byFactor.append(barTable(FATTORI, data.fattori, data.soglia));
        const factorNote = document.createElement('p');
        factorNote.className = 'safety-muted';
        factorNote.textContent = 'Domanda facoltativa: una segnalazione può indicare più fattori o nessuno.';
        byFactor.append(factorNote);
        const byReport = card('Hai sporto denuncia?');
        byReport.append(barTable(DENUNCIA, data.denuncia, data.soglia));
        overview.append(mapCard(data, mappa), totalCard, byType, byTime, byFactor, byReport);

        overviewNote.textContent = `Aggiornato il ${formatDate(data.generato.slice(0, 10))}. ` +
            `Per non rendere riconoscibile nessuno, i numeri sotto ${data.soglia} non vengono mostrati.`;
    })
    .catch(error => {
        console.error('Errore caricamento conteggi:', error);
        overview.replaceChildren();
        overviewNote.textContent = `Errore nel caricamento dei conteggi (${error.message}).`;
    });
