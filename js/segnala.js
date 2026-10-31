// Modulo di segnalazione: scrive su Firestore solo campi a scelta chiusa (vedi firestore.rules)
import { initializeApp } from 'https://www.gstatic.com/firebasejs/13.0.0/firebase-app.js';
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from 'https://www.gstatic.com/firebasejs/13.0.0/firebase-app-check.js';
import { getFirestore, connectFirestoreEmulator, collection, addDoc, serverTimestamp, Timestamp } from 'https://www.gstatic.com/firebasejs/13.0.0/firebase-firestore.js';
import { FIREBASE_CONFIG, RECAPTCHA_SITE_KEY, GIORNI_INDIETRO, CATEGORIE, FASCE, ZONE, FATTORI, DENUNCIA } from './sicurezza-config.js';

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
const zoneSelect = document.getElementById('report-zone');
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
zoneSelect.append(new Option('Scegli il quartiere', ''), ...ZONE.map(z => new Option(z.label, z.id)));

const today = new Date();
dateInput.max = isoDate(today);
dateInput.min = isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - GIORNI_INDIETRO));
dateInput.value = dateInput.max;

const checked = name => form.querySelector(`input[name="${name}"]:checked`)?.value;

function readForm() {
    const missing = [];
    const categoria = checked('categoria');
    const fascia = checked('fascia');
    const denuncia = checked('denuncia');
    if (!categoria) missing.push('cosa è successo');
    if (!dateInput.value || dateInput.value < dateInput.min || dateInput.value > dateInput.max) missing.push('un giorno negli ultimi 90');
    if (!fascia) missing.push('la fascia oraria');
    if (!zoneSelect.value) missing.push('il quartiere');
    if (!denuncia) missing.push('se hai sporto denuncia');
    if (!consent.checked) missing.push('la conferma in fondo');
    if (missing.length) return { error: `Manca: ${missing.join(', ')}.` };

    const [year, month, day] = dateInput.value.split('-').map(Number);
    return {
        data: {
            categoria,
            data: Timestamp.fromDate(new Date(year, month - 1, day)), // mezzanotte locale del giorno scelto
            fascia,
            zona: zoneSelect.value,
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
