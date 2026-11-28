// Revisione dei fatti delle notizie (revisione.html). Mostra i fatti di data/notizie.json che non sono ancora in
// revisione/notizie.tsv, con riassunto e link agli articoli. Per ogni fatto chi controlla sceglie Giusto, Togli o un
// altro tipo (per furti e vandalismi tipo e sottotipo insieme, per esempio «furto:casa»); la riga sparisce e si passa
// alla successiva. Torna da decidere anche un furto o un vandalismo inviato prima dei sottotipi, per guardare solo quello
// (la stessa regola di scripts/build_notizie.py, da_controllare). Nessuna scelta è preimpostata. Le decisioni restano nel
// browser finché non si inviano, anche a lotti: il pulsante apre una issue su GitHub già scritta, e
// .github/workflows/revisione.yml aggiorna il file e ripubblica il sito.
import { formatDate } from './formato.js';
import { SENZA_SOTTOTIPO, SOTTOTIPI, TESTATE, TIPI } from './notizie.js';

const REPO = 'https://github.com/F041/osservatorio-civico-busto-arsizio';
// Una issue nuova si apre con un link: oltre gli 8.000 caratteri GitHub lo rifiuta. Un fatto giusto con il sottotipo
// occupa circa 36 caratteri: 200 stanno in circa 7.500
const MASSIMO = 200;
const MEMORIA = 'revisione-esiti';
const GIUSTO = 'giusto';
const TOGLI = 'togli';
const NESSUNO = 'nessuno';
// Decisioni prese prima che la pagina mostrasse i sottotipi: un «giusto» non conferma un sottotipo mai visto
const SENZA_SOTTOTIPI = 'revisione-senza-sottotipi';

const tabella = document.getElementById('fatti');
const stato = document.getElementById('stato');
const barra = document.getElementById('barra');
const conteggio = document.getElementById('conteggio');
const ultimaRiga = document.getElementById('ultima');
const annulla = document.getElementById('annulla');
const invia = document.getElementById('invia');

// Decisioni non ancora applicate, per id: GIUSTO, TOGLI oppure il tipo giusto
let esiti = new Map();
let senzaSottotipi = new Set();
try {
    esiti = new Map(Object.entries(JSON.parse(localStorage.getItem(MEMORIA) ?? '{}')));
    // Prima versione della pagina: solo la casella "Sbagliato"
    for (const id of JSON.parse(localStorage.getItem('revisione-sbagliati') ?? '[]')) esiti.set(id, TOGLI);
    localStorage.removeItem('revisione-sbagliati');
    const salvati = localStorage.getItem(SENZA_SOTTOTIPI);
    senzaSottotipi = new Set(salvati === null ? esiti.keys() : JSON.parse(salvati));
} catch { /* memoria del browser non disponibile */ }
let fatti = [];
// Righe di revisione/notizie.tsv per id
let inviati = new Map();
let vista = 'da-decidere';
let ultima = null;

function ricorda() {
    try {
        localStorage.setItem(MEMORIA, JSON.stringify(Object.fromEntries(esiti)));
        localStorage.setItem(SENZA_SOTTOTIPI, JSON.stringify([...senzaSottotipi].filter(id => esiti.has(id))));
    } catch { /* niente */ }
}

function leggiTsv(testo) {
    const [testa, ...righe] = testo.trim().split('\n');
    const campi = (testa ?? '').split('\t');
    if (!campi.includes('id')) return new Map();
    return new Map(righe.map(r => {
        const valori = r.split('\t');
        const riga = Object.fromEntries(campi.map((c, i) => [c, (valori[i] ?? '').trim()]));
        return [riga.id, riga];
    }));
}

// Tipo e sottotipo come li sceglie il menu: «furto:casa», «furto:nessuno», «aggressione»
const voce = f => (SOTTOTIPI[f.tipo] ? `${f.tipo}:${f.sottotipo ?? NESSUNO}` : f.tipo);

function nomeSottotipo(tipo, sottotipo) {
    return sottotipo === NESSUNO ? SENZA_SOTTOTIPO[tipo] : SOTTOTIPI[tipo]?.[sottotipo] ?? sottotipo;
}

function nomeVoce(valore) {
    const [tipo, sottotipo] = valore.split(':');
    const nome = TIPI[tipo] ?? tipo;
    return sottotipo ? `${nome}: ${nomeSottotipo(tipo, sottotipo).toLowerCase()}` : nome;
}

// Inviato e completo: già nel file e, se è un furto o un vandalismo, con il sottotipo controllato
function completo(f) {
    const riga = inviati.get(f.id);
    return !!riga && (!SOTTOTIPI[f.tipo] || !!riga.sottotipo_giusto);
}

// Il menu ha tutte le voci tranne quella attuale del fatto
const VOCI = Object.keys(TIPI).flatMap(tipo => (SOTTOTIPI[tipo]
    ? [...Object.keys(SOTTOTIPI[tipo]), NESSUNO].map(s => `${tipo}:${s}`) : [tipo]));

function plurale(n, uno, tanti) {
    return `${n} ${n === 1 ? uno : tanti}`;
}

function descrivi(valore) {
    return valore === GIUSTO ? 'giusto' : valore === TOGLI ? 'da togliere' : `tipo da cambiare in «${nomeVoce(valore)}»`;
}

const elenchi = {
    'da-decidere': () => fatti.filter(f => !completo(f) && !esiti.has(f.id)),
    decisi: () => fatti.filter(f => esiti.has(f.id)),
    inviati: () => fatti.filter(f => completo(f) && !esiti.has(f.id)),
};

function crea(tag, classe, testo) {
    const el = document.createElement(tag);
    el.className = classe;
    el.textContent = testo;
    return el;
}

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
    senzaSottotipi.delete(f.id);
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
    for (const v of VOCI) {
        if (v !== voce(f)) menu.append(new Option(nomeVoce(v), v));
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
    // Un furto o un vandalismo giusto conferma anche il sottotipo che la pagina mostrava
    const confermati = lotto.filter(f => esiti.get(f.id) === GIUSTO && SOTTOTIPI[f.tipo] && !senzaSottotipi.has(f.id));
    const corpo = [
        'Revisione dei fatti dalle notizie, preparata da revisione.html.',
        'Premi «Create»: GitHub aggiorna revisione/notizie.tsv e ripubblica il sito in un paio di minuti.',
        '',
        `controllati: ${id(GIUSTO)}`,
        `sbagliati: ${id(TOGLI)}`,
        `tipo: ${lotto.filter(f => ![GIUSTO, TOGLI].includes(esiti.get(f.id))).map(f => `${f.id}=${esiti.get(f.id)}`).join(' ')}`,
        `sottotipo: ${confermati.map(f => `${f.id}=${f.sottotipo ?? NESSUNO}`).join(' ')}`,
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
        const cellaTipo = cella(riga, 'Tipo', TIPI[f.tipo] ?? f.tipo);
        if (SOTTOTIPI[f.tipo]) {
            cellaTipo.append(crea('span', 'review-subtype', nomeSottotipo(f.tipo, f.sottotipo ?? NESSUNO)));
        }
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
        if (inviati.has(f.id) && !esiti.has(f.id)) {
            // Inviato prima dei sottotipi: il resto è già controllato
            esito.append(crea('span', 'review-done', 'Già controllato: guarda solo il sottotipo.'));
        } else if (esiti.has(f.id)) {
            esito.append(crea('span', 'review-done', `Deciso: ${descrivi(esiti.get(f.id))}`));
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
            if (!f || voce(f) === valore || f.tipo === valore || (valore === GIUSTO && completo(f))
                || (valore === GIUSTO && senzaSottotipi.has(id) && inviati.has(id))) esiti.delete(id);
        }
        ricorda();
        disegna();
    })
    .catch(err => {
        console.error('Errore nel caricamento dei fatti:', err);
        stato.textContent = `Non riesco a caricare i fatti (${err.message}).`;
    });
