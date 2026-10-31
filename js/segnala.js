// Modulo di segnalazione: scrive su Firestore solo campi a scelta chiusa (vedi firestore.rules)
import { initializeApp } from 'https://www.gstatic.com/firebasejs/13.0.0/firebase-app.js';
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from 'https://www.gstatic.com/firebasejs/13.0.0/firebase-app-check.js';
import { getFirestore, connectFirestoreEmulator, collection, addDoc, serverTimestamp, Timestamp } from 'https://www.gstatic.com/firebasejs/13.0.0/firebase-firestore.js';
import { FIREBASE_CONFIG, RECAPTCHA_SITE_KEY, GIORNI_INDIETRO, CATEGORIE, FASCE, FATTORI, DENUNCIA } from './sicurezza-config.js';
import { caricaMappa, creaMappa, punti, confiniCella, centroCella, cellaDi, descriviCella } from './mappa.js';

const SEND_TIMEOUT_MS = 15000;

const isLocal = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
const app = initializeApp(FIREBASE_CONFIG);
// App Check con Fraud Defense: Firestore accetta solo richieste dalle pagine vere. La chiave vale solo per f041.github.io
if (RECAPTCHA_SITE_KEY && !isLocal) {
    initializeAppCheck(app, { provider: new ReCaptchaEnterpriseProvider(RECAPTCHA_SITE_KEY), isTokenAutoRefreshEnabled: true });
}
const db = getFirestore(app);
// In locale (python -m http.server + firebase emulators:start) si scrive sull'emulatore, mai sul database vero
if (isLocal) connectFirestoreEmulator(db, '127.0.0.1', 8085);

const form = document.getElementById('report-form');
const dateInput = document.getElementById('report-date');
const consent = document.getElementById('report-consent');
const submitButton = document.getElementById('report-submit');
const status = document.getElementById('report-status');
const thanks = document.getElementById('report-thanks');

function renderChoices(containerId, name, options, type) {
    const container = document.getElementById(containerId);
    for (const option of options) {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = type;
        input.name = name;
        input.value = option.id;
        const text = document.createElement('span');
        text.textContent = option.label;
        if (option.desc) {
            const desc = document.createElement('span');
            desc.className = 'choice-desc';
            desc.textContent = option.desc;
            text.append(desc);
        }
        label.append(input, text);
        container.append(label);
    }
}

// yyyy-mm-dd nel fuso del dispositivo (toISOString darebbe la data UTC)
const isoDate = date => [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');

renderChoices('choices-categoria', 'categoria', CATEGORIE, 'radio');
renderChoices('choices-fascia', 'fascia', FASCE, 'radio');
renderChoices('choices-fattori', 'fattori', FATTORI, 'checkbox');
renderChoices('choices-denuncia', 'denuncia', DENUNCIA, 'radio');

const today = new Date();
dateInput.max = isoDate(today);
dateInput.min = isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - GIORNI_INDIETRO));
dateInput.value = dateInput.max;

// Dove: si salva solo il codice del quadrato. Il testo cercato non lascia mai il dispositivo.
const searchInput = document.getElementById('place-search');
const placeCells = document.getElementById('place-cells');
const cellChosen = document.getElementById('cell-chosen');
let cellaScelta = null;

const normalizza = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();

caricaMappa().then(data => {
    const L = window.L;
    const g = data.griglia;
    const map = creaMappa(document.getElementById('report-map'), data);
    const valide = new Set(Object.keys(data.celle));

    const luoghi = new Map();
    for (const via of data.vie) luoghi.set(normalizza(via.n), { nome: via.n, celle: via.c, linee: via.g });
    for (const l of data.luoghi) if (!luoghi.has(normalizza(l.n))) luoghi.set(normalizza(l.n), { nome: l.n, celle: [l.c], punto: l.p });
    document.getElementById('place-list').append(...[...luoghi.values()].map(l => new Option(l.nome)));

    const evidenza = L.layerGroup().addTo(map);
    let selezione = null;

    function scegli(id) {
        cellaScelta = id;
        selezione?.remove();
        selezione = L.rectangle(confiniCella(g, id), { color: '#1c5cab', weight: 2, fillColor: '#2a78d6', fillOpacity: 0.35, interactive: false }).addTo(map);
        cellChosen.textContent = `Quadrato scelto: ${descriviCella(data, id)}.`;
        for (const radio of form.querySelectorAll('input[name="cella"]')) radio.checked = radio.value === id;
    }

    function mostraLuogo(luogo) {
        evidenza.clearLayers();
        if (luogo.linee) {
            const linea = L.polyline(luogo.linee.map(l => punti(g, l)), { color: '#eb6834', weight: 5, opacity: 0.85, interactive: false }).addTo(evidenza);
            map.fitBounds(linea.getBounds(), { maxZoom: 17, padding: [24, 24] });
        } else {
            map.setView(punti(g, luogo.punto)[0], 17);
        }
        for (const id of luogo.celle) {
            L.rectangle(confiniCella(g, id), { color: '#1c5cab', weight: 1.5, dashArray: '4 3', fill: false, interactive: false }).addTo(evidenza);
        }
        const container = document.getElementById('choices-cella');
        container.replaceChildren();
        if (luogo.celle.length === 1) {
            placeCells.hidden = true;
            scegli(luogo.celle[0]);
            return;
        }
        // Tratti in ordine lungo la via: da nord a sud o da ovest a est, secondo il verso in cui è più lunga
        const centri = luogo.celle.map(id => [id, centroCella(g, id)]);
        const lats = centri.map(([, c]) => c[0]), lons = centri.map(([, c]) => c[1]);
        const verticale = (Math.max(...lats) - Math.min(...lats)) / g.dlat >= (Math.max(...lons) - Math.min(...lons)) / g.dlon;
        centri.sort((a, b) => (verticale ? b[1][0] - a[1][0] : a[1][1] - b[1][1]));
        const tratto = id => {
            const d = descriviCella(data, id, luogo.nome);
            return d === 'zona senza vie' ? 'Tratto lontano da altre vie' : `Vicino a ${d.replace(/^vicino a /, '')}`;
        };
        renderChoices('choices-cella', 'cella', centri.map(([id]) => ({ id, label: tratto(id) })), 'radio');
        container.querySelectorAll('input').forEach(radio => radio.addEventListener('change', () => scegli(radio.value)));
        placeCells.hidden = false;
        cellChosen.textContent = `${luogo.nome} attraversa ${luogo.celle.length} quadrati: scegli il tratto qui sopra o tocca la mappa.`;
        if (cellaScelta && luogo.celle.includes(cellaScelta)) scegli(cellaScelta);
    }

    searchInput.addEventListener('input', () => {
        const luogo = luoghi.get(normalizza(searchInput.value));
        if (luogo) mostraLuogo(luogo);
    });
    map.on('click', event => {
        const id = cellaDi(g, event.latlng);
        if (id && valide.has(id)) scegli(id);
    });
}).catch(error => {
    console.error('Errore caricamento mappa:', error);
    cellChosen.classList.add('error');
    cellChosen.textContent = 'La mappa non si è caricata: ricarica la pagina.';
});

const checked = name => form.querySelector(`input[name="${name}"]:checked`)?.value;

function readForm() {
    const missing = [];
    const categoria = checked('categoria');
    const fascia = checked('fascia');
    const denuncia = checked('denuncia');
    if (!categoria) missing.push('cosa è successo');
    if (!dateInput.value || dateInput.value < dateInput.min || dateInput.value > dateInput.max) missing.push('un giorno negli ultimi 90');
    if (!fascia) missing.push('la fascia oraria');
    if (!cellaScelta) missing.push('il quadrato sulla mappa');
    if (!denuncia) missing.push('se hai sporto denuncia');
    if (!consent.checked) missing.push('la conferma in fondo');
    if (missing.length) return { error: `Manca: ${missing.join(', ')}.` };

    const [year, month, day] = dateInput.value.split('-').map(Number);
    return {
        data: {
            categoria,
            data: Timestamp.fromDate(new Date(year, month - 1, day)), // mezzanotte locale del giorno scelto
            fascia,
            cella: cellaScelta,
            fattori: [...form.querySelectorAll('input[name="fattori"]:checked')].map(input => input.value),
            denuncia,
            creato: serverTimestamp(),
        },
    };
}

form.addEventListener('submit', async event => {
    event.preventDefault();
    status.classList.remove('error');
    const { data, error } = readForm();
    if (error) {
        status.classList.add('error');
        status.textContent = error;
        return;
    }
    submitButton.disabled = true;
    status.textContent = 'Invio in corso…';
    try {
        // Senza rete addDoc resterebbe in attesa: dopo 15 secondi lo diamo per fallito
        await Promise.race([
            addDoc(collection(db, 'segnalazioni'), data),
            new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), SEND_TIMEOUT_MS)),
        ]);
        form.hidden = true;
        thanks.hidden = false;
        thanks.scrollIntoView({ block: 'center' });
    } catch (err) {
        console.error('Invio segnalazione non riuscito:', err);
        status.classList.add('error');
        status.textContent = err.message === 'timeout'
            ? 'Invio non riuscito: controlla la connessione e riprova.'
            : 'Invio non riuscito. Riprova tra qualche minuto.';
        submitButton.disabled = false;
    }
});
