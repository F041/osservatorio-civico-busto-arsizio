// Dati aperti: dizionari dei dati letti dagli schemi in data/schemi/ (Table Schema e JSON Schema) e date di aggiornamento
// lette dai file stessi. Gli schemi sono l'unica fonte delle descrizioni: si aggiornano lì, non qui.
import { formatDate } from './formato.js';

const dataLunga = new Intl.DateTimeFormat('it-IT', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const giorno = iso => dataLunga.format(new Date(`${iso}T00:00:00Z`));

async function leggi(url) {
    const risposta = await fetch(url);
    if (!risposta.ok) throw new Error(`${url}: HTTP ${risposta.status}`);
    return risposta.json();
}

const TIPI = {
    string: 'testo', integer: 'intero', number: 'numero', boolean: 'vero o falso', object: 'oggetto', array: 'elenco',
    null: 'null', year: 'anno', datetime: 'data e ora',
};
const FORMATI = { date: 'data AAAA-MM-GG', 'date-time': 'data e ora ISO 8601', uri: 'indirizzo web' };

function tipoJson(nodo, elemento) {
    if (FORMATI[nodo.format]) return FORMATI[nodo.format];
    if (nodo.type === 'array' && elemento.type && elemento.type !== 'object') {
        return `elenco di valori (${TIPI[elemento.type] || elemento.type})`;
    }
    return [].concat(nodo.type || []).map(t => TIPI[t] || t).join(' o ');
}

// "#/$defs/nome" -> nodo; le proprietà scritte accanto a $ref (per esempio description) vincono
function risolvi(nodo, radice) {
    if (!nodo || !nodo.$ref) return nodo || {};
    const base = nodo.$ref.replace(/^#\//, '').split('/').reduce((o, k) => o[k], radice);
    const { $ref, ...resto } = nodo;
    return { ...risolvi(base, radice), ...resto };
}

// Una riga per campo, con il percorso nel file: "a.b", "a[].b" per gli elenchi, "a.‹chiave›" per le chiavi variabili
function righeJson(nodo, percorso, radice, righe) {
    const n = risolvi(nodo, radice);
    const elemento = risolvi(n.items, radice);
    const contenitore = n.properties || (n.additionalProperties && typeof n.additionalProperties === 'object')
        || elemento.type === 'object';
    if (percorso && (n.description || !contenitore)) {
        let significato = n.description || '';
        const valori = n.enum || elemento.enum;
        if (valori) significato += ` Valori: ${valori.join('; ')}.`;
        righe.push({ campo: percorso, tipo: tipoJson(n, elemento), unita: n['x-unita'], significato: significato.trim() });
    }
    const prefisso = percorso ? `${percorso}.` : '';
    for (const [chiave, figlio] of Object.entries(n.properties || {})) righeJson(figlio, prefisso + chiave, radice, righe);
    if (n.additionalProperties && typeof n.additionalProperties === 'object') {
        righeJson(n.additionalProperties, `${prefisso}‹${n['x-chiave'] || 'chiave'}›`, radice, righe);
    }
    if (elemento.type === 'object') righeJson(n.items, `${percorso}[]`, radice, righe);
    return righe;
}

function righeTableSchema(schema) {
    return schema.fields.map(f => ({
        campo: f.name,
        tipo: f.type === 'datetime' && f.format ? 'data e ora AAAA-MM-GG hh:mm:ss' : (TIPI[f.type] || f.type),
        unita: f['x-unita'],
        significato: f.description || '',
    }));
}

function disegna(contenitore, titolo, righe) {
    const tabella = document.createElement('table');
    tabella.className = 'dictionary-table';
    tabella.createCaption().textContent = titolo;
    const testa = tabella.createTHead().insertRow();
    for (const t of ['Campo', 'Tipo e unità', 'Significato']) {
        const th = document.createElement('th');
        th.scope = 'col';
        th.textContent = t;
        testa.append(th);
    }
    const corpo = tabella.createTBody();
    for (const r of righe) {
        const tr = corpo.insertRow();
        const th = document.createElement('th');
        th.scope = 'row';
        const codice = document.createElement('code');
        // A capo solo dopo punti e parentesi del percorso, non a metà di un nome
        for (const pezzo of r.campo.split(/(?<=[.\]›])/)) codice.append(pezzo, document.createElement('wbr'));
        th.append(codice);
        tr.append(th);
        tr.insertCell().textContent = r.unita ? `${r.tipo}, ${r.unita}` : r.tipo;
        tr.insertCell().textContent = r.significato;
    }
    contenitore.replaceChildren(tabella);
}

for (const contenitore of document.querySelectorAll('[data-schema]')) {
    const url = contenitore.dataset.schema;
    leggi(url)
        .then(schema => disegna(contenitore, contenitore.dataset.titolo,
            schema.fields ? righeTableSchema(schema) : righeJson(schema, '', schema, [])))
        .catch(e => {
            console.error('Errore nel leggere lo schema:', e);
            const p = document.createElement('p');
            p.className = 'safety-muted';
            const a = document.createElement('a');
            a.href = url;
            a.textContent = url;
            p.append('Non sono riuscito a leggere lo schema. Puoi aprirlo qui: ', a);
            contenitore.replaceChildren(p);
        });
}

function scriviData(chiave, testo) {
    for (const el of document.querySelectorAll(`[data-aggiornamento="${chiave}"]`)) el.textContent = testo;
}

const aggiornamenti = {
    pagamenti: leggi('last_update.json').then(d => d.lastUpdate),
    cruscotto: leggi('data/cruscotto.json').then(d => {
        for (const el of document.querySelectorAll('[data-periodo="cruscotto"]')) {
            el.textContent = `dal ${giorno(d.periodo.da)} al ${giorno(d.periodo.a)}`;
        }
        return formatDate(d.generato);
    }),
    popolazione: leggi('data/popolazione.json').then(d => formatDate(d.generato)),
    sicurezza: leggi('data/sicurezza.json').then(d => formatDate(d.generato)),
};
for (const [chiave, promessa] of Object.entries(aggiornamenti)) {
    promessa
        .then(testo => scriviData(chiave, testo || 'non disponibile'))
        .catch(e => {
            console.error(`Errore nel leggere la data di ${chiave}:`, e);
            scriviData(chiave, 'non disponibile');
        });
}
