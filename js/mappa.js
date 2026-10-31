// Mappa di Busto Arsizio disegnata da data/mappa.json (scripts/build_mappa.py), senza tessere da server esterni:
// nessuno riceve la zona che chi segnala sta guardando. Leaflet è caricato come script classico (vendor/leaflet).
const L = window.L;

let datiMappa;
export function caricaMappa() {
    datiMappa ??= fetch('data/mappa.json').then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
    });
    return datiMappa;
}

// Le coordinate sono interi relativi all'origine della griglia: [lat, lon, lat, lon, ...]
export function punti(g, flat) {
    const out = [];
    for (let i = 0; i < flat.length; i += 2) out.push([g.lat0 + flat[i] / g.scala, g.lon0 + flat[i + 1] / g.scala]);
    return out;
}

const idCella = (row, col) => `r${String(row).padStart(2, '0')}c${String(col).padStart(2, '0')}`;
const rigaColonna = id => [Number(id.slice(1, 3)), Number(id.slice(4, 6))];

export function confiniCella(g, id) {
    const [row, col] = rigaColonna(id);
    return [[g.lat0 + row * g.dlat, g.lon0 + col * g.dlon], [g.lat0 + (row + 1) * g.dlat, g.lon0 + (col + 1) * g.dlon]];
}

export function centroCella(g, id) {
    const [row, col] = rigaColonna(id);
    return [g.lat0 + (row + 0.5) * g.dlat, g.lon0 + (col + 0.5) * g.dlon];
}

export function cellaDi(g, latlng) {
    const row = Math.floor((latlng.lat - g.lat0) / g.dlat);
    const col = Math.floor((latlng.lng - g.lon0) / g.dlon);
    return row >= 0 && row < g.righe && col >= 0 && col < g.colonne ? idCella(row, col) : null;
}

// Un quadrato a parole: le vie più lunghe al suo interno, o quelle dei quadrati vicini se non ne ha
export function descriviCella(data, id, escludi) {
    const nomi = (data.celle[id] || []).filter(n => n !== escludi).slice(0, 2);
    if (nomi.length) return nomi.join(' e ');
    const [row, col] = rigaColonna(id);
    const vicine = new Set();
    for (const [dr, dc] of [[0, 1], [0, -1], [1, 0], [-1, 0], [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
        for (const n of data.celle[idCella(row + dr, col + dc)] || []) if (n !== escludi) vicine.add(n);
    }
    const lista = [...vicine].slice(0, 2);
    return lista.length ? `vicino a ${lista.join(' e ')}` : 'zona senza vie';
}

const STILE_VIE = [
    { color: '#a9a8a3', weight: 4 },
    { color: '#bebdb8', weight: 3 },
    { color: '#d2d1cc', weight: 2 },
    { color: '#d2d1cc', weight: 1.5, dashArray: '3 4' },
];
// Fondo più chiaro, per la panoramica: in primo piano ci sono i quadrati colorati
const STILE_VIE_TENUE = [
    { color: '#cfcec9', weight: 3 },
    { color: '#dbdad5', weight: 2 },
    { color: '#e5e4df', weight: 1.2 },
    { color: '#e5e4df', weight: 1, dashArray: '3 4' },
];

function etichetta(latlng, testo, classe) {
    const span = document.createElement('span');
    span.textContent = testo;
    return L.marker(latlng, {
        icon: L.divIcon({ className: `map-label ${classe}`, html: span, iconSize: null }),
        interactive: false, keyboard: false,
    });
}

// Punto a metà del tratto più lungo di una via, dove metterne il nome
function metaVia(g, via) {
    const linea = via.g.reduce((a, b) => (b.length > a.length ? b : a));
    const i = Math.floor(linea.length / 4) * 2;
    return [g.lat0 + linea[i] / g.scala, g.lon0 + linea[i + 1] / g.scala];
}

export function creaMappa(element, data, { griglia = true, tenue = false } = {}) {
    const g = data.griglia;
    const renderer = L.canvas({ padding: 0.5 });
    const confine = punti(g, data.confine);
    const limiti = L.latLngBounds(confine);
    const map = L.map(element, {
        renderer, minZoom: 12, maxZoom: 18, zoomSnap: 0.5,
        maxBounds: limiti.pad(0.3), scrollWheelZoom: false,
    });
    map.attributionControl.setPrefix(false)
        .addAttribution('Dati <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap</a>');
    map.fitBounds(limiti);

    L.polygon(confine, { renderer, color: '#8a8984', weight: 1.5, fillColor: '#fcfcfb', fillOpacity: 1, interactive: false }).addTo(map);
    const stili = tenue ? STILE_VIE_TENUE : STILE_VIE;
    for (let rango = stili.length - 1; rango >= 0; rango--) {
        for (const via of data.vie) {
            if (via.r === rango) L.polyline(via.g.map(l => punti(g, l)), { renderer, ...stili[rango], interactive: false }).addTo(map);
        }
    }
    for (const linea of data.ferrovie) {
        L.polyline(punti(g, linea), { renderer, color: tenue ? '#a9a8a3' : '#6b6a66', weight: 1.5, dashArray: '8 5', interactive: false }).addTo(map);
    }
    if (griglia) {
        for (const id of Object.keys(data.celle)) {
            L.rectangle(confiniCella(g, id), { renderer, color: '#2a78d6', opacity: 0.2, weight: 1, fill: false, interactive: false }).addTo(map);
        }
    }

    // Nomi: luoghi noti da subito, vie principali da vicino, tutte le vie solo molto da vicino
    const nomiLuoghi = L.layerGroup(data.luoghi.map(l => etichetta(punti(g, l.p)[0], l.n, 'map-label-place')));
    const nomiPrincipali = L.layerGroup(data.vie.filter(v => v.r <= 1).map(v => etichetta(metaVia(g, v), v.n, 'map-label-street')));
    const nomiAltri = L.layerGroup(data.vie.filter(v => v.r > 1).map(v => etichetta(metaVia(g, v), v.n, 'map-label-street')));
    const aggiornaNomi = () => {
        const zoom = map.getZoom();
        for (const [layer, daZoom] of [[nomiLuoghi, 14], [nomiPrincipali, 15.5], [nomiAltri, 17]]) {
            if (zoom >= daZoom) layer.addTo(map); else layer.remove();
        }
    };
    map.on('zoomend', aggiornaNomi);
    aggiornaNomi();
    return map;
}
