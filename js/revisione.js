// Revisione dei fatti delle notizie (revisione.html). Mostra i fatti di data/notizie.json che non sono ancora in
// revisione/notizie.tsv, con riassunto e link agli articoli. Per ogni fatto chi controlla sceglie Giusto, Togli o un
// altro tipo; la riga sparisce e si passa alla successiva. Nessuna scelta è preimpostata. Le decisioni restano nel
// browser finché non si inviano, anche a lotti: il pulsante apre una issue su GitHub già scritta, e
// .github/workflows/revisione.yml aggiorna il file e ripubblica il sito.
import { formatDate } from './formato.js';
import { TESTATE, TIPI } from './notizie.js';

const REPO = 'https://github.com/F041/osservatorio-civico-busto-arsizio';
// Una issue nuova si apre con un link: oltre gli 8.000 caratteri GitHub lo rifiuta. 400 id stanno in circa 5.500
const MASSIMO = 400;
const MEMORIA = 'revisione-esiti';
const GIUSTO = 'giusto';
const TOGLI = 'togli';

const tabella = document.getElementById('fatti');
const stato = document.getElementById('stato');
const barra = document.getElementById('barra');
const conteggio = document.getElementById('conteggio');
const ultimaRiga = document.getElementById('ultima');
const annulla = document.getElementById('annulla');
const invia = document.getElementById('invia');

// Decisioni non ancora applicate, per id: GIUSTO, TOGLI oppure il tipo giusto
let esiti = new Map();
try {
    esiti = new Map(Object.entries(JSON.parse(localStorage.getItem(MEMORIA) ?? '{}')));
    // Prima versione della pagina: solo la casella "Sbagliato"
    for (const id of JSON.parse(localStorage.getItem('revisione-sbagliati') ?? '[]')) esiti.set(id, TOGLI);
    localStorage.removeItem('revisione-sbagliati');
} catch { /* memoria del browser non disponibile */ }
let fatti = [];
let inviati = new Set();
let vista = 'da-decidere';
let ultima = null;

function ricorda() {
    try { localStorage.setItem(MEMORIA, JSON.stringify(Object.fromEntries(esiti))); } catch { /* niente */ }
}

function leggiTsv(testo) {
    const [testa, ...righe] = testo.trim().split('\n');
    const id = (testa ?? '').split('\t').indexOf('id');
    return id < 0 ? new Set() : new Set(righe.map(r => r.split('\t')[id]));
}

function plurale(n, uno, tanti) {
    return `${n} ${n === 1 ? uno : tanti}`;
}

function descrivi(valore) {
    return valore === GIUSTO ? 'giusto' : valore === TOGLI ? 'da togliere' : `tipo da cambiare in «${TIPI[valore] ?? valore}»`;
}

const elenchi = {
    'da-decidere': () => fatti.filter(f => !inviati.has(f.id) && !esiti.has(f.id)),
    decisi: () => fatti.filter(f => esiti.has(f.id)),
    inviati: () => fatti.filter(f => inviati.has(f.id) && !esiti.has(f.id)),
};

function cella(riga, etichetta, testo) {
    const c = riga.insertCell();
    c.dataset.label = etichetta;
    if (testo !== undefined) c.textContent = testo;
    return c;
}

function riassunto(cellaTesto, f) {
    cellaTesto.className = 'review-summary';
    if (!f.riassunto) {
        cellaTesto.textContent = 'Riassunto non ancora pronto: apri l\'articolo.';
        cellaTesto.classList.add('review-missing');
    } else if (f.riassunto.includes('Dubbio')) {
        // Haiku scrive "Dubbio:" quando l'articolo non torna con il fatto, anche a metà riassunto
        const inizio = f.riassunto.indexOf('Dubbio');
        const forte = document.createElement('strong');
        forte.textContent = 'Dubbio';
        cellaTesto.append(f.riassunto.slice(0, inizio), forte, f.riassunto.slice(inizio + 'Dubbio'.length));
    } else {
        cellaTesto.textContent = f.riassunto;
    }
}

// Una decisione: la riga esce dalla vista "Da decidere" e il fuoco passa alla riga che prende il suo posto
function decidi(f, valore) {
    const prima = esiti.get(f.id);
    if (prima === valore) return;
    const righe = [...tabella.tBodies[0].rows];
    const posto = righe.findIndex(r => r.dataset.id === f.id);
    if (valore) esiti.set(f.id, valore); else esiti.delete(f.id);
    ultima = { f, prima, valore };
    ricorda();
    disegna(posto);
}

function comandi(f, riga) {
    const scelto = esiti.get(f.id);
    const gruppo = document.createElement('div');
    gruppo.className = 'review-actions';
    const luogo = `${formatDate(f.data)}, ${f.via}`;
    for (const [valore, testo] of [[GIUSTO, 'Giusto'], [TOGLI, 'Togli']]) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = `review-button review-${valore}`;
        b.textContent = testo;
        b.setAttribute('aria-label', `${testo}: ${luogo}`);
        b.setAttribute('aria-pressed', String(scelto === valore));
        b.addEventListener('click', () => decidi(f, valore));
        gruppo.append(b);
    }
    const menu = document.createElement('select');
    menu.className = 'review-select';
    menu.setAttribute('aria-label', `Cambia tipo: ${luogo}`);
    menu.append(new Option('Cambia tipo…', ''));
    for (const [tipo, nome] of Object.entries(TIPI)) {
        if (tipo !== f.tipo) menu.append(new Option(nome, tipo));
    }
    menu.value = scelto && scelto !== GIUSTO && scelto !== TOGLI ? scelto : '';
    menu.addEventListener('change', () => { if (menu.value) decidi(f, menu.value); });
    gruppo.append(menu);
    if (scelto) {
        const togli = document.createElement('button');
        togli.type = 'button';
        togli.className = 'link-button';
        togli.textContent = 'Rimetti da decidere';
        togli.addEventListener('click', () => decidi(f, null));
        gruppo.append(togli);
    }
    riga.classList.toggle('review-wrong', scelto === TOGLI);
    riga.classList.toggle('review-fix', !!scelto && scelto !== GIUSTO && scelto !== TOGLI);
    return gruppo;
}

function aggiornaBarra() {
    const decisi = elenchi.decisi();
    const daDecidere = elenchi['da-decidere']().length;
    const lotto = decisi.slice(0, MASSIMO);
    const conta = valore => lotto.filter(f => (valore === 'tipo' ? ![GIUSTO, TOGLI].includes(esiti.get(f.id)) : esiti.get(f.id) === valore)).length;
    const [giusti, tolti, cambiati] = [conta(GIUSTO), conta(TOGLI), conta('tipo')];
    barra.hidden = !daDecidere && !decisi.length;
    // Il dettaglio tra parentesi sul telefono si nasconde (CSS), per non coprire mezzo schermo
    const dettaglio = document.createElement('span');
    dettaglio.className = 'review-detail';
    dettaglio.textContent = decisi.length
        ? ` (${plurale(giusti, 'giusto', 'giusti')}, ${tolti} da togliere, ${plurale(cambiati, 'tipo', 'tipi')} da cambiare)` : '';
    conteggio.replaceChildren(`${daDecidere} da decidere · ${decisi.length} da inviare`, dettaglio);
    invia.hidden = !decisi.length;
    invia.textContent = decisi.length > MASSIMO ? `Invia i primi ${MASSIMO}` : `Invia ${plurale(decisi.length, 'deciso', 'decisi')}`;
    const id = valore => lotto.filter(f => esiti.get(f.id) === valore).map(f => f.id).join(' ');
    const corpo = [
        'Revisione dei fatti dalle notizie, preparata da revisione.html.',
        'Premi «Create»: GitHub aggiorna revisione/notizie.tsv e ripubblica il sito in un paio di minuti.',
        '',
        `controllati: ${id(GIUSTO)}`,
        `sbagliati: ${id(TOGLI)}`,
        `tipo: ${lotto.filter(f => ![GIUSTO, TOGLI].includes(esiti.get(f.id))).map(f => `${f.id}=${esiti.get(f.id)}`).join(' ')}`,
    ].join('\n');
    const parti = [giusti && plurale(giusti, 'giusto', 'giusti'), tolti && `${tolti} da togliere`, cambiati && plurale(cambiati, 'tipo da cambiare', 'tipi da cambiare')].filter(Boolean);
    invia.href = `${REPO}/issues/new?${new URLSearchParams({ title: `Revisione notizie: ${parti.join(', ')}`, body: corpo })}`;
    annulla.hidden = !ultima;
    ultimaRiga.textContent = ultima
        ? (ultima.valore ? `Ultima scelta: ${ultima.f.via}, ${formatDate(ultima.f.data)}: ${descrivi(ultima.valore)}.`
            : `${ultima.f.via}, ${formatDate(ultima.f.data)}: di nuovo da decidere.`)
        : '';
}

function disegna(posto) {
    const corpo = tabella.tBodies[0];
    corpo.replaceChildren();
    const elenco = elenchi[vista]();
    for (const f of elenco) {
        const riga = corpo.insertRow();
        riga.dataset.id = f.id;
        cella(riga, 'Giorno', formatDate(f.data));
        cella(riga, 'Tipo', TIPI[f.tipo] ?? f.tipo);
        riassunto(cella(riga, 'Cosa è successo'), f);
        cella(riga, 'Via o luogo', f.via);
        const lista = document.createElement('ul');
        for (const a of f.articoli) {
            const voce = document.createElement('li');
            const link = document.createElement('a');
            link.href = a.url;
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = `${TESTATE[a.fonte] ?? a.fonte}, ${formatDate(a.data)}`;
            voce.append(link);
            lista.append(voce);
        }
        cella(riga, 'Articoli').append(lista);
        const esito = cella(riga, 'Esito');
        if (esiti.has(f.id)) {
            const deciso = document.createElement('span');
            deciso.className = 'review-done';
            deciso.textContent = `Deciso: ${descrivi(esiti.get(f.id))}`;
            esito.append(deciso);
        }
        esito.append(comandi(f, riga));
    }
    tabella.hidden = !elenco.length;
    for (const [nome, quali] of Object.entries(elenchi)) {
        document.querySelector(`[data-quanti="${nome}"]`).textContent = `(${quali().length})`;
    }
    const vuoto = { 'da-decidere': 'Nessun fatto da decidere.', decisi: 'Nessuna decisione da inviare.', inviati: 'Nessun fatto inviato finora.' };
    stato.textContent = elenco.length ? `${plurale(elenco.length, 'fatto', 'fatti')} in questa lista.` : vuoto[vista];
    aggiornaBarra();
    if (posto !== undefined && elenco.length) {
        const righe = corpo.rows;
        righe[Math.min(posto, righe.length - 1)].querySelector('button')?.focus({ preventScroll: false });
    }
}

annulla.addEventListener('click', () => {
    if (!ultima) return;
    const { f, prima } = ultima;
    if (prima) esiti.set(f.id, prima); else esiti.delete(f.id);
    ultima = null;
    ricorda();
    disegna();
    tabella.querySelector(`tr[data-id="${f.id}"] button`)?.focus();
});

invia.addEventListener('click', () => {
    ultima = null;
    ultimaRiga.textContent = 'Si è aperta GitHub: premi «Create». Tra un paio di minuti ricarica questa pagina: i fatti inviati passano in «Già inviati».';
    annulla.hidden = true;
});

for (const scelta of document.querySelectorAll('input[name="vista"]')) {
    scelta.addEventListener('change', () => { vista = scelta.value; ultima = null; disegna(); });
}

Promise.all([
    fetch('data/notizie.json').then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
    // Il file non c'è finché non arriva la prima revisione
    fetch('revisione/notizie.tsv', { cache: 'no-cache' }).then(r => (r.ok ? r.text() : '')),
])
    .then(([dati, tsv]) => {
        fatti = dati.fatti.slice().reverse();
        inviati = leggiTsv(tsv);
        // Decisioni già applicate dal sito: i fatti tolti non ci sono più, i tipi cambiati sono già giusti, i giusti
        // sono nel file
        for (const [id, valore] of esiti) {
            const f = fatti.find(x => x.id === id);
            if (!f || f.tipo === valore || (valore === GIUSTO && inviati.has(id))) esiti.delete(id);
        }
        ricorda();
        disegna();
    })
    .catch(err => {
        console.error('Errore nel caricamento dei fatti:', err);
        stato.textContent = `Non riesco a caricare i fatti (${err.message}).`;
    });
