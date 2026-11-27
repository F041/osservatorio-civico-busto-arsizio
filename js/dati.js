// Scarica dati: il CSV si genera nel browser dal database SQLite con sql.js, la stessa libreria di Cerca pagamenti
const DB = 'busto_pagamenti.db';
const pulsante = document.getElementById('download-csv');
const avviso = document.getElementById('csv-status');
const TESTO_PULSANTE = pulsante.textContent;

// Come un foglio di calcolo se lo aspetta: virgolette solo dove servono, raddoppiate dentro il campo
const campo = v => {
    if (v == null) return '';
    const s = String(v);
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

async function generaCsv() {
    pulsante.disabled = true;
    pulsante.textContent = 'Preparazione…';
    try {
        avviso.textContent = 'Scarico il database…';
        const [SQLite, risposta] = await Promise.all([initSqlJs({ locateFile: file => `js/lib/${file}` }), fetch(DB)]);
        if (!risposta.ok) throw new Error(`HTTP ${risposta.status}`);
        const db = new SQLite.Database(new Uint8Array(await risposta.arrayBuffer()));
        avviso.textContent = 'Preparo il file CSV…';
        const [{ columns, values }] = db.exec('SELECT * FROM pagamenti');
        db.close();
        const righe = [columns, ...values].map(r => r.map(campo).join(','));
        // Il BOM iniziale fa leggere a Excel gli accenti in UTF-8
        const file = new Blob(['﻿', righe.join('\r\n'), '\r\n'], { type: 'text/csv;charset=utf-8' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(file);
        link.download = 'pagamenti_busto_arsizio.csv';
        link.click();
        URL.revokeObjectURL(link.href);
        avviso.textContent = `File pronto: ${values.length.toLocaleString('it-IT')} pagamenti.`;
    } catch (e) {
        console.error('Errore nella generazione del CSV:', e);
        avviso.textContent = `Non sono riuscito a generare il CSV (${e.message}). Riprova più tardi.`;
    } finally {
        pulsante.disabled = false;
        pulsante.textContent = TESTO_PULSANTE;
    }
}

pulsante.addEventListener('click', generaCsv);

const dataAggiornamento = document.getElementById('db-last-update-date');
fetch('last_update.json')
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(d => { dataAggiornamento.textContent = d.lastUpdate || 'non disponibile'; })
    .catch(e => {
        console.error('Errore nel leggere la data di aggiornamento:', e);
        dataAggiornamento.textContent = 'non disponibile';
    });
