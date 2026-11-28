// Revisione dei fatti delle notizie (revisione.html). Mostra i fatti di data/notizie.json che non sono ancora in
// revisione/notizie.tsv, con riassunto e link agli articoli. Chi controlla spunta quelli sbagliati e invia: il link
// apre una issue su GitHub già scritta, e .github/workflows/revisione.yml aggiorna il file e ripubblica il sito.
import { formatDate } from './formato.js';
import { TESTATE, TIPI } from './notizie.js';

const REPO = 'https://github.com/F041/osservatorio-civico-busto-arsizio';
// Una issue nuova si apre con un link: oltre gli 8.000 caratteri GitHub lo rifiuta. 400 id stanno in circa 5.500
const MASSIMO = 400;
const MEMORIA = 'revisione-sbagliati';

const tabella = document.getElementById('fatti');
const stato = document.getElementById('stato');
const anche = document.getElementById('anche-controllati');
const barra = document.getElementById('barra');
const conteggio = document.getElementById('conteggio');
const invia = document.getElementById('invia');

let sbagliati = new Set();
try { sbagliati = new Set(JSON.parse(localStorage.getItem(MEMORIA) ?? '[]')); } catch { /* memoria del browser non disponibile */ }
let fatti = [];
let controllati = new Set();

function ricorda() {
    try { localStorage.setItem(MEMORIA, JSON.stringify([...sbagliati])); } catch { /* niente */ }
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

function aggiornaInvio() {
    const visti = daControllare().map(f => f.id);
    const tolti = fatti.filter(f => sbagliati.has(f.id)).map(f => f.id);
    barra.hidden = !visti.length && !tolti.length;
    conteggio.textContent = `${visti.length} ${visti.length === 1 ? 'fatto' : 'fatti'} da controllare, ` +
        `${tolti.length} ${tolti.length === 1 ? 'segnato come sbagliato' : 'segnati come sbagliati'}`;
    const corpo = [
        'Revisione dei fatti dalle notizie, preparata da revisione.html.',
        'Premi «Create»: GitHub aggiorna revisione/notizie.tsv e ripubblica il sito in un paio di minuti.',
        '',
        `controllati: ${visti.join(' ')}`,
        `sbagliati: ${tolti.join(' ')}`,
    ].join('\n');
    const titolo = tolti.length ? `Revisione notizie: ${tolti.length} da togliere` : 'Revisione notizie: tutto giusto';
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

function disegna() {
    const corpo = tabella.tBodies[0];
    corpo.replaceChildren();
    const elenco = anche.checked ? fatti : daControllare();
    for (const f of elenco) {
        const riga = corpo.insertRow();
        riga.classList.toggle('review-wrong', sbagliati.has(f.id));
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
        const scelta = cella(riga, 'Esito');
        if (controllati.has(f.id)) {
            const gia = document.createElement('span');
            gia.className = 'review-done';
            gia.textContent = 'Già controllato';
            scelta.append(gia);
        }
        const etichetta = document.createElement('label');
        etichetta.className = 'review-check';
        const casella = document.createElement('input');
        casella.type = 'checkbox';
        casella.checked = sbagliati.has(f.id);
        casella.addEventListener('change', () => {
            if (casella.checked) sbagliati.add(f.id); else sbagliati.delete(f.id);
            riga.classList.toggle('review-wrong', casella.checked);
            ricorda();
            aggiornaInvio();
        });
        etichetta.append(casella, ' Sbagliato');
        scelta.append(etichetta);
    }
    tabella.hidden = !elenco.length;
    const quanti = fatti.filter(f => !controllati.has(f.id)).length;
    stato.textContent = !quanti ? 'Nessun fatto da controllare: li hai già visti tutti.'
        : quanti > MASSIMO ? `${quanti} fatti da controllare. Qui ci sono i primi ${MASSIMO}: dopo l'invio ricarica la pagina per gli altri.`
            : `${quanti} ${quanti === 1 ? 'fatto' : 'fatti'} da controllare.`;
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
        // I fatti tolti da una revisione già inviata non sono più sulla mappa: non serve ricordarli
        sbagliati = new Set([...sbagliati].filter(id => fatti.some(f => f.id === id)));
        ricorda();
        anche.addEventListener('change', disegna);
        disegna();
    })
    .catch(err => {
        console.error('Errore nel caricamento dei fatti:', err);
        stato.textContent = `Non riesco a caricare i fatti (${err.message}).`;
    });
