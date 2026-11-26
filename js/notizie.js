// Vista Notizie della mappa: vie e luoghi con almeno `soglia` fatti raccontati dalle testate (scripts/build_notizie.py).
// Ha un segno diverso dalle segnalazioni (linee e punti al posto dei quadrati) e i suoi numeri non si sommano mai a quelli.
// Sotto la mappa un navigatore come quelli dei grafici dei prezzi: l'area dei fatti per settimana su tutto lo storico e
// due maniglie per scegliere il periodo. Conteggi, soglia e tipi si calcolano qui, sul periodo scelto.
import { punti } from './mappa.js';

const L = window.L;
const integer = new Intl.NumberFormat('it-IT');
const nomeMese = new Intl.DateTimeFormat('it-IT', { month: 'short', timeZone: 'UTC' });
const GIORNO = 864e5;
const giorno = iso => Math.round(Date.parse(iso) / GIORNO);
const iso = g => new Date(g * GIORNO).toISOString().slice(0, 10);
const formatDate = s => s.split('-').reverse().join('/');
const quantiFatti = n => `${integer.format(n)} ${n === 1 ? 'fatto' : 'fatti'}`;
const tra = (v, min, max) => Math.min(max, Math.max(min, v));

const TESTATE = { ilbustese: 'ilBustese', malpensa24: 'Malpensa24', prealpina: 'Prealpina', varesenews: 'VareseNews' };
const TIPI = {
    furto: 'Furto o tentato furto',
    aggressione: 'Aggressione o minaccia',
    molestia: 'Molestia',
    vandalismo: 'Vandalismo o degrado',
    spaccio: 'Spaccio',
    insicurezza: 'Problemi ricorrenti denunciati dai residenti',
    allagamento: 'Allagamento',
    altro: 'Altro',
};
// Sui pulsanti del filtro, per stare in una riga: la prima parte del nome intero, così si riconosce lo stesso tipo
const TIPI_BREVI = { furto: 'Furto', aggressione: 'Aggressione', vandalismo: 'Vandalismo', insicurezza: 'Problemi ricorrenti' };

// Icone dei tipi da Lucide (https://lucide.dev), licenza ISC:
// Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright
// (c) for Lucide are held by Lucide Contributors 2022. Permission to use, copy, modify, and/or distribute this software
// for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission
// notice appear in all copies. THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES.
const ICONE = {
    furto: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    aggressione: '<polyline points="14.5 17.5 3 6 3 3 6 3 17.5 14.5"/><line x1="13" x2="19" y1="19" y2="13"/><line x1="16" x2="20" y1="16" y2="20"/><line x1="19" x2="21" y1="21" y2="19"/><polyline points="14.5 6.5 18 3 21 3 21 6 17.5 9.5"/><line x1="5" x2="9" y1="14" y2="18"/><line x1="7" x2="4" y1="17" y2="20"/><line x1="3" x2="5" y1="19" y2="21"/>',
    molestia: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    vandalismo: '<path d="M3 3h.01"/><path d="M7 5h.01"/><path d="M11 7h.01"/><path d="M3 7h.01"/><path d="M7 9h.01"/><path d="M3 11h.01"/><rect width="4" height="4" x="15" y="5"/><path d="m19 9 2 2v10c0 .6-.4 1-1 1h-6c-.6 0-1-.4-1-1V11l2-2"/><path d="m13 14 8-2"/><path d="m13 19 8-2"/>',
    spaccio: '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>',
    insicurezza: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    allagamento: '<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/>',
    altro: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
};

function icona(tipo) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    for (const [k, v] of Object.entries({ viewBox: '0 0 24 24', width: 16, height: 16, fill: 'none', stroke: 'currentColor',
        'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', class: 'news-icon' })) {
        svg.setAttribute(k, v);
    }
    svg.innerHTML = ICONE[tipo] ?? ICONE.altro;
    return svg;
}

// Etichetta di un tipo con la sua icona davanti
function conIcona(tipo, testo) {
    const span = crea('span', 'news-type');
    span.append(icona(tipo), testo);
    return span;
}
// Punto a metà del tratto più lungo di una via, dove mettere le icone
function metaLinea(linee) {
    const linea = linee.reduce((x, y) => (y.length > x.length ? y : x));
    return linea[Math.floor(linea.length / 2)];
}
const PRESET = [['1m', '1 mese', 30], ['3m', '3 mesi', 91], ['6m', '6 mesi', 182], ['tutto', 'Tutto', Infinity]];
// Periodo con cui si apre la vista
const PREDEFINITO = '6m';
// Misure dei gruppi di icone sulla mappa, come in css/style.css (.news-pin 24 px, gap 2 px), più un margine:
// servono a capire quali gruppi si accavallano
const ICONA_PASSO = 26;
const ICONA_ALTEZZA = 30;
const ICONA_SOPRA_LUOGO = 40;
const MIN_GIORNI = 7;

// Quattro intensità di una sola tinta, dalla più chiara, tutte con contrasto >= 3:1 sul fondo della mappa
const SCALA = ['#e0569b', '#bd3480', '#8f1f60', '#5c1140'];

// Classi di colore come quelle delle segnalazioni, ma partendo dalla soglia delle notizie
function classiNotizie(soglia) {
    const limiti = [20, 10, 5, soglia].filter((da, i, tutti) => i === tutti.length - 1 || da > soglia);
    return limiti.map((da, i) => ({ da, label: i === 0 ? `${da} e più` : `${da}–${limiti[i - 1] - 1}` }));
}

function crea(tag, classe, testo) {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (testo !== undefined) el.textContent = testo;
    return el;
}

// Gli allagamenti non sono reati: "Tutti" li lascia fuori, si vedono solo scegliendo il loro tipo (decisione
// dell'utente del 26/11/2026)
const A_PARTE = new Set(['allagamento']);
const diTipo = (fatti, tipo) => fatti.filter(f => (tipo ? f.tipo === tipo : !A_PARTE.has(f.tipo)));

// Vie e luoghi con almeno `soglia` fatti tra i giorni `da` e `a` compresi
function vieNelPeriodo(fatti, da, a, soglia) {
    const perVia = new Map();
    for (const f of fatti) {
        const g = giorno(f.data);
        if (g < da || g > a) continue;
        if (!perVia.has(f.via)) perVia.set(f.via, []);
        perVia.get(f.via).push(f);
    }
    const vie = [];
    for (const [n, lista] of perVia) {
        if (lista.length < soglia) continue;
        const conteggi = {};
        for (const f of lista) conteggi[f.tipo] = (conteggi[f.tipo] ?? 0) + 1;
        const articoli = new Map(lista.flatMap(f => f.articoli).map(x => [x.url, x]));
        const giorni = lista.map(f => f.data).sort();
        vie.push({
            n,
            fatti: lista.length,
            da: giorni[0],
            a: giorni[giorni.length - 1],
            // Tutti i tipi, anche con un fatto solo: i singoli fatti sono già nel file (decisione dell'utente del 26/11/2026)
            tipi: Object.entries(conteggi).sort((x, y) => y[1] - x[1]),
            articoli: [...articoli.values()].sort((x, y) => (y.data + y.fonte).localeCompare(x.data + x.fonte)),
        });
    }
    return vie.sort((x, y) => y.fatti - x.fatti || x.n.localeCompare(y.n));
}

// Navigatore: area dei fatti per settimana su tutto lo storico, parte scelta evidenziata, due maniglie.
// Si trascinano le maniglie o la parte scelta; un tocco fuori sposta lì il periodo. Le maniglie vanno anche da tastiera
function navigatore(dati, cambia) {
    const d0 = giorno(dati.da);
    const d1 = giorno(dati.a);
    const durata = Math.max(1, d1 - d0);
    let settimane = [];
    let massimo = 1;
    // La serie si rifà quando cambia il tipo scelto
    function calcolaSerie(fatti) {
        settimane = Array(Math.floor(durata / 7) + 1).fill(0);
        for (const f of fatti) settimane[tra(Math.floor((giorno(f.data) - d0) / 7), 0, settimane.length - 1)] += 1;
        massimo = Math.max(1, ...settimane);
    }
    calcolaSerie(diTipo(dati.fatti, ''));
    let da = Math.max(d0, d1 - PRESET.find(([valore]) => valore === PREDEFINITO)[2]);
    let a = d1;

    const blocco = crea('div', 'news-nav-block');
    const testa = crea('div', 'map-source');
    const etichetta = crea('span', 'map-source-label', 'Periodo');
    etichetta.id = 'news-period-label';
    const gruppo = crea('div', 'map-source-options');
    gruppo.setAttribute('role', 'radiogroup');
    gruppo.setAttribute('aria-labelledby', etichetta.id);
    const radio = PRESET.map(([valore, testo, giorni]) => {
        const label = crea('label');
        const input = crea('input');
        input.type = 'radio';
        input.name = 'news-period';
        input.value = valore;
        input.checked = valore === PREDEFINITO;
        input.addEventListener('change', () => imposta(Math.max(d0, d1 - giorni), d1, valore));
        label.append(input, crea('span', '', testo));
        gruppo.append(label);
        return { input };
    });
    const riassunto = crea('p', 'news-nav-summary');
    riassunto.setAttribute('aria-live', 'polite');
    testa.append(etichetta, gruppo);

    const nav = crea('div', 'news-nav');
    const fondo = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    fondo.setAttribute('aria-hidden', 'true');
    const scelta = crea('div', 'news-nav-sel');
    const maniglie = ['Inizio', 'Fine'].map(nome => {
        const m = crea('div', 'news-handle');
        m.tabIndex = 0;
        m.setAttribute('role', 'slider');
        m.setAttribute('aria-label', `${nome} del periodo`);
        nav.append(m);
        return m;
    });
    nav.prepend(fondo, scelta);
    const didascalia = crea('p', 'safety-muted news-nav-caption',
        'Fatti per settimana in tutta Busto. Trascina le maniglie o la parte evidenziata per cambiare periodo.');
    blocco.append(testa, riassunto, nav, didascalia);

    const larghezza = () => nav.clientWidth;
    const x = g => ((g - d0) / durata) * larghezza();
    const giornoDa = clientX => d0 + Math.round(((clientX - nav.getBoundingClientRect().left) / Math.max(1, larghezza())) * durata);

    function disegnaFondo() {
        const W = larghezza();
        const H = nav.clientHeight;
        if (!W) return;
        fondo.setAttribute('viewBox', `0 0 ${W} ${H}`);
        const alto = 8;
        const y = n => H - (n / massimo) * (H - alto);
        const punti = settimane.map((n, i) => `${tra(x(d0 + i * 7 + 3.5), 0, W).toFixed(1)},${y(n).toFixed(1)}`);
        const linea = `M0,${y(settimane[0]).toFixed(1)} L${punti.join(' L')} L${W},${y(settimane[settimane.length - 1]).toFixed(1)}`;
        let mesi = '';
        const inizio = new Date(d0 * GIORNO);
        for (let m = new Date(Date.UTC(inizio.getUTCFullYear(), inizio.getUTCMonth() + 1, 1)); m.getTime() / GIORNO <= d1;
            m = new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth() + 1, 1))) {
            const xm = x(m.getTime() / GIORNO).toFixed(1);
            const testo = m.getUTCMonth() === 0 ? `${nomeMese.format(m)} ${m.getUTCFullYear()}` : nomeMese.format(m);
            mesi += `<line x1="${xm}" x2="${xm}" y1="0" y2="${H}" class="news-nav-grid"/>` +
                `<text x="${(+xm + 4).toFixed(1)}" y="${H - 5}" class="news-nav-month">${testo}</text>`;
        }
        fondo.innerHTML = `${mesi}<path d="${linea} L${W},${H} L0,${H} Z" class="news-nav-area"/>` +
            `<path d="${linea}" class="news-nav-line"/>`;
    }

    function posiziona() {
        scelta.style.left = `${x(da)}px`;
        scelta.style.width = `${Math.max(2, x(a) - x(da))}px`;
        [da, a].forEach((g, i) => {
            maniglie[i].style.left = `${x(g)}px`;
            maniglie[i].setAttribute('aria-valuemin', String(i ? da + MIN_GIORNI - d0 : 0));
            maniglie[i].setAttribute('aria-valuemax', String(i ? durata : a - MIN_GIORNI - d0));
            maniglie[i].setAttribute('aria-valuenow', String(g - d0));
            maniglie[i].setAttribute('aria-valuetext', formatDate(iso(g)));
        });
    }

    let inAttesa = false;
    function imposta(nuovoDa, nuovoA, preset = null) {
        da = tra(nuovoDa, d0, d1 - MIN_GIORNI);
        a = tra(nuovoA, da + MIN_GIORNI, d1);
        for (const r of radio) r.input.checked = r.input.value === preset;
        posiziona();
        if (inAttesa) return;
        inAttesa = true;
        requestAnimationFrame(() => {
            inAttesa = false;
            cambia(da, a);
        });
    }

    // Trascinamento con il puntatore (mouse, dito, penna)
    let presa = null;
    nav.addEventListener('pointerdown', ev => {
        const g = giornoDa(ev.clientX);
        const durataScelta = a - da;
        if (ev.target === maniglie[0]) presa = { tipo: 'da' };
        else if (ev.target === maniglie[1]) presa = { tipo: 'a' };
        else if (ev.target === scelta) presa = { tipo: 'sposta', inizio: g, da0: da };
        else {
            // Un tocco fuori porta lì il centro del periodo, poi si può continuare a trascinare
            const nuovoDa = tra(g - Math.round(durataScelta / 2), d0, d1 - durataScelta);
            imposta(nuovoDa, nuovoDa + durataScelta);
            presa = { tipo: 'sposta', inizio: g, da0: da };
        }
        nav.setPointerCapture(ev.pointerId);
        ev.preventDefault();
    });
    nav.addEventListener('pointermove', ev => {
        if (!presa) return;
        const g = giornoDa(ev.clientX);
        if (presa.tipo === 'da') imposta(Math.min(g, a - MIN_GIORNI), a);
        else if (presa.tipo === 'a') imposta(da, Math.max(g, da + MIN_GIORNI));
        else {
            const durataScelta = a - da;
            const nuovoDa = tra(presa.da0 + g - presa.inizio, d0, d1 - durataScelta);
            imposta(nuovoDa, nuovoDa + durataScelta);
        }
    });
    const lascia = () => { presa = null; };
    nav.addEventListener('pointerup', lascia);
    nav.addEventListener('pointercancel', lascia);

    // Tastiera: frecce di un giorno, Maiusc + frecce di una settimana, Inizio e Fine agli estremi
    maniglie.forEach((m, i) => m.addEventListener('keydown', ev => {
        const passo = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[ev.key];
        let g = i ? a : da;
        if (passo) g += passo * (ev.shiftKey ? 7 : 1);
        else if (ev.key === 'Home') g = d0;
        else if (ev.key === 'End') g = d1;
        else return;
        ev.preventDefault();
        if (i) imposta(da, Math.max(g, da + MIN_GIORNI)); else imposta(Math.min(g, a - MIN_GIORNI), a);
    }));

    // Il pannello parte nascosto: si disegna quando ha una larghezza, e di nuovo se la cambia
    new ResizeObserver(() => { disegnaFondo(); posiziona(); }).observe(nav);

    return {
        blocco,
        riassunto,
        serie: fatti => { calcolaSerie(fatti); disegnaFondo(); },
        periodo: () => [da, a],
    };
}

export function creaVistaNotizie(dati, mappa, leggiMappa, mapDiv) {
    const g = mappa.griglia;
    const renderer = L.canvas({ padding: 0.5, tolerance: 10 });
    const strato = L.layerGroup();
    const classi = classiNotizie(dati.soglia);
    const colore = n => SCALA[classi.length - 1 - classi.findIndex(c => n >= c.da)];
    let segni = new Map();
    // Icone dei tipi: in un gruppo a parte, perché quelle che si accavallano si nascondono (vedi diradaIcone)
    const stratoIcone = L.layerGroup().addTo(strato);
    let icone = [];
    let zoomAscoltato = false;
    // Da lontano le vie del centro sono vicine: si tengono le icone delle vie con più fatti e si nascondono quelle
    // che coprirebbero un gruppo già messo. Avvicinando la mappa ricompaiono.
    function diradaIcone() {
        const map = leggiMappa();
        if (!map || !map.hasLayer(strato)) return;
        const messi = [];
        for (const { marker, quante, luogo } of icone) {
            const p = map.latLngToLayerPoint(marker.getLatLng());
            const w = quante * ICONA_PASSO + 6;
            const box = { x: p.x - w / 2, y: p.y - (luogo ? ICONA_SOPRA_LUOGO : ICONA_ALTEZZA / 2), w, h: ICONA_ALTEZZA };
            const urta = messi.some(m => box.x < m.x + m.w && m.x < box.x + box.w && box.y < m.y + m.h && m.y < box.y + box.h);
            if (urta) stratoIcone.removeLayer(marker);
            else { stratoIcone.addLayer(marker); messi.push(box); }
        }
    }
    strato.on('add', () => {
        if (!zoomAscoltato) { leggiMappa().on('zoomend', diradaIcone); zoomAscoltato = true; }
        diradaIcone();
    });

    const pannello = crea('div');
    const legenda = crea('ul', 'chart-legend');
    legenda.append(...classi.map((classe, i) => {
        const voce = crea('li');
        const campione = crea('span', 'chart-swatch chart-swatch-line');
        campione.style.background = SCALA[classi.length - 1 - i];
        voce.append(campione, classe.label);
        return voce;
    }).reverse());
    const nota = crea('p', 'safety-muted', `Fatti raccontati da ilBustese, Malpensa24, Prealpina e VareseNews. Sulla mappa ` +
        `compaiono le vie con almeno ${dati.soglia} fatti nel periodo scelto. Questi numeri sono separati dalle ` +
        'segnalazioni dei cittadini.');
    const dettaglio = crea('div', 'news-detail');
    dettaglio.setAttribute('aria-live', 'polite');
    // Le due tabelle (vie e tipi) affiancate dove c'è spazio, una sotto l'altra sul telefono
    const tabelle = crea('div', 'news-tables');
    const elenco = crea('div');
    const perTipo = crea('div');
    tabelle.append(elenco, perTipo);
    const nav = navigatore(dati, (da, a) => disegna(da, a));
    pannello.append(nav.blocco, legenda, nota, dettaglio, tabelle);

    // Filtro per tipo, sopra la mappa: pulsanti con l'icona, la stessa che compare sulla mappa. Un tipo alla volta o tutti
    const filtro = crea('div', 'map-filter news-filter');
    const etichettaFiltro = crea('span', 'map-source-label', 'Mostra');
    etichettaFiltro.id = 'news-filter-label';
    const scelte = crea('div', 'news-filter-options');
    scelte.id = 'news-filter';
    scelte.setAttribute('role', 'radiogroup');
    scelte.setAttribute('aria-labelledby', etichettaFiltro.id);
    const presenti = new Set(dati.fatti.map(f => f.tipo));
    const tipiPresenti = Object.entries(TIPI).filter(([id]) => presenti.has(id));
    const opzioni = [['', 'Tutti'], ...tipiPresenti.filter(([id]) => !A_PARTE.has(id)), ...tipiPresenti.filter(([id]) => A_PARTE.has(id))];
    const radio = opzioni.map(([id, testo]) => {
        const label = crea('label');
        const input = crea('input');
        input.type = 'radio';
        input.name = 'news-filter';
        input.value = id;
        input.checked = id === '';
        input.addEventListener('change', () => scegli(id));
        const nome = crea('span');
        if (id) nome.append(icona(id));
        const parole = crea('span', 'news-filter-text', TIPI_BREVI[id] ?? testo);
        nome.append(parole);
        label.title = id ? testo : 'Tutti i tipi, tranne gli allagamenti';
        // Gli allagamenti stanno in fondo, separati dai tipi che contano in "Tutti"
        if (A_PARTE.has(id)) label.className = 'news-filter-apart';
        label.append(input, nome);
        scelte.append(label);
        return input;
    });
    filtro.append(etichettaFiltro, scelte);
    let tipoScelto = '';
    const fattiScelti = () => diTipo(dati.fatti, tipoScelto);
    function scegli(id) {
        tipoScelto = id;
        for (const r of radio) r.checked = r.value === id;
        nav.serie(fattiScelti());
        disegna(...nav.periodo());
    }

    // Sopra la mappa, quando nessuna via raggiunge la soglia: la mappa vuota da sola sembra un errore
    const vuota = crea('div', 'news-map-empty');
    vuota.hidden = true;
    vuota.setAttribute('role', 'status');
    mapDiv.append(vuota);

    function evidenzia(nome) {
        for (const [n, { segno, bordo }] of segni) {
            const scelto = n === nome;
            if (bordo) {
                bordo.setStyle({ weight: scelto ? 12 : 9 });
                segno.setStyle({ weight: scelto ? 8 : 5 });
            } else {
                segno.setRadius(scelto ? 12 : 9);
            }
        }
        const { segno, bordo } = segni.get(nome);
        bordo?.bringToFront();
        segno.bringToFront();
    }

    function mostraDettaglio(voce) {
        const periodo = voce.da === voce.a ? `il ${formatDate(voce.da)}` : `tra il ${formatDate(voce.da)} e il ${formatDate(voce.a)}`;
        const parti = [crea('h4', '', voce.n), crea('p', '', `${quantiFatti(voce.fatti)} ${periodo}.`)];
        if (voce.tipi.length) {
            const tipi = crea('ul', 'news-types');
            tipi.append(...voce.tipi.map(([t, n]) => {
                const riga = crea('li');
                riga.append(conIcona(t, `${TIPI[t] ?? t}: ${integer.format(n)}`));
                return riga;
            }));
            parti.push(tipi);
        }
        if (segni.get(voce.n)?.bordo) parti.push(crea('p', 'safety-muted', 'Le notizie spesso non dicono il punto esatto: coloriamo tutta la via.'));
        const link = crea('ul', 'news-links');
        link.append(...voce.articoli.map(x => {
            const riga = crea('li');
            const ancora = crea('a', '', `${TESTATE[x.fonte] ?? x.fonte}, ${formatDate(x.data)}`);
            ancora.href = x.url;
            ancora.target = '_blank';
            ancora.rel = 'noopener noreferrer';
            riga.append(ancora);
            return riga;
        }));
        parti.push(crea('p', 'news-links-title', 'Articoli'), link);
        dettaglio.replaceChildren(...parti);
    }

    function seleziona(voce, centra) {
        evidenzia(voce.n);
        mostraDettaglio(voce);
        if (centra) {
            leggiMappa().fitBounds(segni.get(voce.n).limiti, { maxZoom: 16, padding: [30, 30] });
            mapDiv.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    // Fatti per tipo nel periodo, in tutta Busto e non solo nelle vie sopra la soglia; ogni riga sceglie quel tipo
    function disegnaTipi(da, a) {
        const conta = {};
        for (const f of dati.fatti) {
            if (giorno(f.data) >= da && giorno(f.data) <= a) conta[f.tipo] = (conta[f.tipo] ?? 0) + 1;
        }
        const righe = Object.entries(conta).sort((x, y) => y[1] - x[1]);
        perTipo.replaceChildren();
        if (!righe.length) return;
        const tabella = crea('table', 'bar-table zone-table news-type-table');
        tabella.createCaption().textContent = 'Fatti per tipo nel periodo, in tutta Busto';
        for (const [t, n] of righe) {
            const riga = tabella.insertRow();
            // Con un tipo scelto gli altri restano come contesto, in grigio: la mappa e il riassunto contano solo quello
            const spento = tipoScelto ? t !== tipoScelto : A_PARTE.has(t);
            if (spento) riga.className = 'news-type-off';
            const intestazione = crea('th');
            intestazione.scope = 'row';
            const bottone = crea('button', 'link-button');
            bottone.type = 'button';
            bottone.title = tipoScelto === t ? 'Torna a tutti i tipi' : 'Mostra solo questo tipo sulla mappa';
            bottone.setAttribute('aria-pressed', String(tipoScelto === t));
            bottone.append(conIcona(t, TIPI[t] ?? t));
            bottone.addEventListener('click', () => scegli(tipoScelto === t ? '' : t));
            intestazione.append(bottone);
            riga.append(intestazione);
            const cellaBarra = riga.insertCell();
            cellaBarra.className = 'bar-cell';
            const barra = crea('div', 'bar');
            barra.style.width = `${(n / righe[0][1]) * 100}%`;
            barra.style.background = spento ? '#d6d5d0' : SCALA[1];
            cellaBarra.append(barra);
            const numero = riga.insertCell();
            numero.className = 'num';
            numero.textContent = integer.format(n);
        }
        perTipo.append(tabella);
    }

    function disegna(da, a) {
        const fatti = fattiScelti();
        const nelPeriodo = fatti.filter(f => giorno(f.data) >= da && giorno(f.data) <= a);
        const quanteVie = new Set(nelPeriodo.map(f => f.via)).size;
        const tipo = tipoScelto ? ` (${TIPI[tipoScelto].toLowerCase()})` : '';
        const esclusi = !tipoScelto && dati.fatti.some(f => A_PARTE.has(f.tipo) && giorno(f.data) >= da && giorno(f.data) <= a)
            ? ', senza contare gli allagamenti' : '';
        nav.riassunto.textContent = `Dal ${formatDate(iso(da))} al ${formatDate(iso(a))}: ${quantiFatti(nelPeriodo.length)}` +
            `${tipo} in tutta Busto, in ${integer.format(quanteVie)} ${quanteVie === 1 ? 'via o luogo' : 'vie e luoghi'}${esclusi}.`;
        pannello.dispatchEvent(new CustomEvent('periodo', { detail: { da: iso(da), a: iso(a) } }));
        disegnaTipi(da, a);
        const vie = vieNelPeriodo(fatti, da, a, dati.soglia);
        strato.clearLayers();
        stratoIcone.clearLayers();
        strato.addLayer(stratoIcone);
        icone = [];
        segni = new Map();
        for (const voce of vie) {
            const via = mappa.vie.find(v => v.n === voce.n);
            const luogo = via ? null : mappa.luoghi.find(l => l.n === voce.n);
            if (!via && !luogo) continue;
            let segno, bordo, limiti, linee;
            if (via) {
                linee = via.g.map(l => punti(g, l));
                bordo = L.polyline(linee, { renderer, color: '#ffffff', weight: 9, lineCap: 'round', interactive: false });
                strato.addLayer(bordo);
                segno = L.polyline(linee, { renderer, color: colore(voce.fatti), weight: 5, lineCap: 'round' });
                limiti = segno.getBounds();
            } else {
                const punto = punti(g, luogo.p)[0];
                segno = L.circleMarker(punto, { renderer, radius: 9, color: '#ffffff', weight: 2, fillColor: colore(voce.fatti), fillOpacity: 1 });
                limiti = L.latLngBounds([punto, punto]);
            }
            segno.bindTooltip(`${voce.n}: ${quantiFatti(voce.fatti)} dalle notizie`, { sticky: true });
            segno.on('click', () => seleziona(voce, false));
            strato.addLayer(segno);
            // Le icone dei tipi accanto alla via, una per tipo, dal più frequente
            const perTipoVia = new Map();
            for (const f of nelPeriodo) if (f.via === voce.n) perTipoVia.set(f.tipo, (perTipoVia.get(f.tipo) ?? 0) + 1);
            const tipiVia = [...perTipoVia].sort((x, y) => y[1] - x[1]);
            const gruppoIcone = crea('span', 'news-pins');
            for (const [t] of tipiVia) {
                const pin = crea('span', 'news-pin');
                pin.append(icona(t));
                gruppoIcone.append(pin);
            }
            const marker = L.marker(via ? metaLinea(linee) : punti(g, luogo.p)[0], {
                icon: L.divIcon({ className: `news-pins-icon${via ? '' : ' news-pins-luogo'}`, html: gruppoIcone, iconSize: null }),
                keyboard: false, pane: 'markerPane',
            });
            marker.bindTooltip(`${voce.n}: ${tipiVia.map(([t, n]) => `${TIPI[t] ?? t} ${n}`).join(', ')}`, { direction: 'top' });
            marker.on('click', () => seleziona(voce, false));
            stratoIcone.addLayer(marker);
            icone.push({ marker, quante: tipiVia.length, luogo: !via });
            segni.set(voce.n, { segno, bordo, limiti });
        }

        diradaIcone();
        const visibili = vie.filter(v => segni.has(v.n));
        elenco.replaceChildren();
        vuota.hidden = visibili.length > 0;
        if (!visibili.length) {
            // Si consiglia di allargare il periodo solo se così comparirebbe almeno una via; se no di tornare a tutti i tipi
            const tuttoIlPeriodo = da <= giorno(dati.da) && a >= giorno(dati.a);
            const allargareServe = !tuttoIlPeriodo &&
                vieNelPeriodo(fatti, giorno(dati.da), giorno(dati.a), dati.soglia).some(v => mappa.vie.some(x => x.n === v.n) || mappa.luoghi.some(x => x.n === v.n));
            const quando = tuttoIlPeriodo ? 'in tutti i dati raccolti' : 'in questo periodo';
            const diTipo = tipoScelto ? ` di tipo "${TIPI[tipoScelto]}"` : '';
            const consiglio = allargareServe ? ' Allarga il periodo sotto la mappa.'
                : !tipoScelto ? ''
                : tuttoIlPeriodo ? ' Scegli "Tutti" sopra la mappa per vedere gli altri tipi.'
                : ` Neanche allargando il periodo una via arriva a ${dati.soglia} fatti di questo tipo: scegli "Tutti" sopra la mappa.`;
            const testo = (nelPeriodo.length
                ? `Nessuna via ha almeno ${dati.soglia} fatti${diTipo} ${quando}: ${quantiFatti(nelPeriodo.length)} sparsi in ` +
                  `${integer.format(quanteVie)} ${quanteVie === 1 ? 'via' : 'vie diverse'}.`
                : `Nessun fatto${diTipo} ${quando}.`) + consiglio;
            // Il messaggio sta già sulla mappa: il riquadro del dettaglio si nasconde invece di ripeterlo
            vuota.textContent = testo;
            dettaglio.replaceChildren();
            dettaglio.hidden = true;
            return;
        }
        dettaglio.hidden = false;
        dettaglio.replaceChildren(crea('p', 'safety-muted', 'Tocca una via sulla mappa o nell\'elenco per vedere i fatti e gli articoli.'));
        const tabella = crea('table', 'bar-table zone-table');
        tabella.createCaption().textContent = 'Vie e luoghi con più fatti nel periodo';
        for (const voce of visibili.slice(0, 10)) {
            const riga = tabella.insertRow();
            const intestazione = crea('th');
            intestazione.scope = 'row';
            const bottone = crea('button', 'link-button', voce.n);
            bottone.type = 'button';
            bottone.title = 'Mostra sulla mappa';
            bottone.addEventListener('click', () => seleziona(voce, true));
            intestazione.append(bottone);
            riga.append(intestazione);
            const cellaBarra = riga.insertCell();
            cellaBarra.className = 'bar-cell';
            const barra = crea('div', 'bar');
            barra.style.width = `${(voce.fatti / visibili[0].fatti) * 100}%`;
            barra.style.background = SCALA[1];
            cellaBarra.append(barra);
            const numero = riga.insertCell();
            numero.className = 'num';
            numero.textContent = integer.format(voce.fatti);
        }
        elenco.append(tabella);
    }
    // Si disegna subito il periodo predefinito: i limiti delle vie servono per inquadrare la mappa
    disegna(...nav.periodo());

    const limitiTutti = () => {
        const tutti = [...segni.values()].map(s => s.limiti);
        return tutti.length ? tutti.reduce((x, y) => L.latLngBounds(x.getSouthWest(), x.getNorthEast()).extend(y)) : null;
    };
    const periodo = () => { const [da, a] = nav.periodo(); return { da: iso(da), a: iso(a) }; };
    return { pannello, filtro, strato, limiti: limitiTutti, periodo };
}
