// Revisione dei fatti delle notizie (revisione.html). Mostra i fatti di data/notizie.json che non sono ancora in
// revisione/notizie.tsv, con riassunto e link agli articoli. Per ogni fatto chi controlla sceglie: giusto, da togliere
// o tipo da correggere. Il pulsante di invio apre una issue su GitHub già scritta, e .github/workflows/revisione.yml
// aggiorna il file e ripubblica il sito.
import { formatDate } from './formato.js';
import { TESTATE, TIPI } from './notizie.js';

const REPO = 'https://github.com/F041/osservatorio-civico-busto-arsizio';
// Una issue nuova si apre con un link: oltre gli 8.000 caratteri GitHub lo rifiuta. 400 id stanno in circa 5.500
const MASSIMO = 400;
const MEMORIA = 'revisione-esiti';
const TOGLI = 'togli';

const tabella = document.getElementById('fatti');
const stato = document.getElementById('stato');
const anche = document.getElementById('anche-controllati');
const barra = document.getElementById('barra');
const conteggio = document.getElementById('conteggio');
const invia = document.getElementById('invia');

// Esiti scelti, per id: TOGLI oppure il tipo giusto. Restano nel browser finché non si invia
let esiti = new Map();
try {
    esiti = new Map(Object.entries(JSON.parse(localStorage.getItem(MEMORIA) ?? '{}')));
    // Prima versione della pagina: solo la casella "Sbagliato"
    for (const id of JSON.parse(localStorage.getItem('revisione-sbagliati') ?? '[]')) esiti.set(id, TOGLI);
    localStorage.removeItem('revisione-sbagliati');
} catch { /* memoria del browser non disponibile */ }
let fatti = [];
let controllati = new Set();

function ricorda() {
    try { localStorage.setItem(MEMORIA, JSON.stringify(Object.fromEntries(esiti))); } catch { /* niente */ }
}

function leggiTsv(testo) {
    const [testa, ...righe] = testo.trim().split('\n');
    const id = (testa ?? '').split('\t').indexOf('id');
    return id < 0 ? new Set() : new Set(righe.map(r => r.split('\t')[id]));
}

function daControllare() {
    return fatti.filter(f => !controllati.has(f.id)).slice(0, MASSIMO);
}

function cella(riga, etichetta, testo) {
    const c = riga.insertCell();
    c.dataset.label = etichetta;
    if (testo !== undefined) c.textContent = testo;
    return c;
}

function plurale(n, uno, tanti) {
    return `${n} ${n === 1 ? uno : tanti}`;
}

function aggiornaInvio() {
    const visti = daControllare().map(f => f.id);
    const presenti = fatti.filter(f => esiti.has(f.id));
    const tolti = presenti.filter(f => esiti.get(f.id) === TOGLI).map(f => f.id);
    const corretti = presenti.filter(f => esiti.get(f.id) !== TOGLI).map(f => `${f.id}=${esiti.get(f.id)}`);
    barra.hidden = !visti.length && !presenti.length;
    conteggio.textContent = [
        plurale(visti.length, 'fatto da controllare', 'fatti da controllare'),
        plurale(tolti.length, 'da togliere', 'da togliere'),
        plurale(corretti.length, 'con il tipo da correggere', 'con il tipo da correggere'),
    ].join(' · ');
    const corpo = [
        'Revisione dei fatti dalle notizie, preparata da revisione.html.',
        'Premi «Create»: GitHub aggiorna revisione/notizie.tsv e ripubblica il sito in un paio di minuti.',
        '',
        `controllati: ${visti.join(' ')}`,
        `sbagliati: ${tolti.join(' ')}`,
        `tipo: ${corretti.join(' ')}`,
    ].join('\n');
    const parti = [tolti.length && `${tolti.length} da togliere`, corretti.length && plurale(corretti.length, 'tipo da correggere', 'tipi da correggere')].filter(Boolean);
    const titolo = `Revisione notizie: ${parti.length ? parti.join(', ') : 'tutto giusto'}`;
    invia.href = `${REPO}/issues/new?${new URLSearchParams({ title: titolo, body: corpo })}`;
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

function scelta(f, riga) {
    const menu = document.createElement('select');
    menu.className = 'review-select';
    menu.setAttribute('aria-label', `Esito del fatto del ${formatDate(f.data)} in ${f.via}`);
    menu.append(new Option('Giusto', ''), new Option('Da togliere', TOGLI));
    const gruppo = document.createElement('optgroup');
    gruppo.label = 'Il tipo giusto è:';
    for (const [tipo, nome] of Object.entries(TIPI)) {
        if (tipo !== f.tipo) gruppo.append(new Option(nome, tipo));
    }
    menu.append(gruppo);
    menu.value = esiti.get(f.id) ?? '';
    const colora = () => {
        riga.classList.toggle('review-wrong', menu.value === TOGLI);
        riga.classList.toggle('review-fix', menu.value !== '' && menu.value !== TOGLI);
    };
    menu.addEventListener('change', () => {
        if (menu.value) esiti.set(f.id, menu.value); else esiti.delete(f.id);
        colora();
        ricorda();
        aggiornaInvio();
    });
    colora();
    return menu;
}

function disegna() {
    const corpo = tabella.tBodies[0];
    corpo.replaceChildren();
    const elenco = anche.checked ? fatti : daControllare();
    for (const f of elenco) {
        const riga = corpo.insertRow();
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
        if (controllati.has(f.id)) {
            const gia = document.createElement('span');
            gia.className = 'review-done';
            gia.textContent = 'Già controllato';
            esito.append(gia);
        }
        esito.append(scelta(f, riga));
    }
    tabella.hidden = !elenco.length;
    const quanti = fatti.filter(f => !controllati.has(f.id)).length;
    stato.textContent = !quanti ? 'Nessun fatto da controllare: li hai già visti tutti.'
        : quanti > MASSIMO ? `${quanti} fatti da controllare. Qui ci sono i primi ${MASSIMO}: dopo l'invio ricarica la pagina per gli altri.`
            : `${plurale(quanti, 'fatto', 'fatti')} da controllare.`;
    aggiornaInvio();
}

Promise.all([
    fetch('data/notizie.json').then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
    // Il file non c'è finché non arriva la prima revisione
    fetch('revisione/notizie.tsv', { cache: 'no-cache' }).then(r => (r.ok ? r.text() : '')),
])
    .then(([dati, tsv]) => {
        fatti = dati.fatti.slice().reverse();
        controllati = leggiTsv(tsv);
        // I fatti tolti da una revisione già inviata non sono più sulla mappa: non serve ricordarli. Nemmeno i tipi
        // già corretti, che ora il file ha già giusti
        for (const [id, valore] of esiti) {
            const f = fatti.find(x => x.id === id);
            if (!f || f.tipo === valore) esiti.delete(id);
        }
        ricorda();
        anche.addEventListener('change', disegna);
        disegna();
    })
    .catch(err => {
        console.error('Errore nel caricamento dei fatti:', err);
        stato.textContent = `Non riesco a caricare i fatti (${err.message}).`;
    });
