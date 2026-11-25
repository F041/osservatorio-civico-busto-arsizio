// Pagina Popolazione: residenti stimati per gruppo di quartieri, da data/popolazione.json (scripts/build_popolazione.py)
const intero = new Intl.NumberFormat('it-IT');
const decimale = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const percento = new Intl.NumberFormat('it-IT', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nomeMese = new Intl.DateTimeFormat('it-IT', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const formatDate = s => s.slice(0, 10).split('-').reverse().join('/');
const fineMese = mese => nomeMese.format(new Date(`${mese}-01T00:00:00Z`));

function crea(tag, classe, testo) {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (testo !== undefined) el.textContent = testo;
    return el;
}

function link(href, testo) {
    const a = crea('a', '', testo);
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener';
    return a;
}

// Tabella con intestazione: `colonne` sono [titolo, numerica?]; ogni riga è una lista di celle (testo o nodo)
function tabella(el, didascalia, colonne, righe) {
    el.createCaption().textContent = didascalia;
    const testa = el.createTHead().insertRow();
    for (const [titolo, numerica] of colonne) {
        const th = crea('th', numerica ? 'num' : '', titolo);
        th.scope = 'col';
        testa.append(th);
    }
    const corpo = el.createTBody();
    for (const riga of righe) {
        const tr = corpo.insertRow();
        riga.forEach((valore, i) => {
            const cella = i === 0 ? crea('th') : tr.insertCell();
            if (i === 0) { cella.scope = 'row'; tr.append(cella); }
            if (colonne[i][1]) cella.className = 'num';
            cella.append(valore instanceof Node ? valore : String(valore));
        });
    }
}

function cifra(valore, etichetta, nota) {
    const box = crea('div', 'population-figure');
    box.append(crea('p', 'population-figure-value', valore), crea('p', 'population-figure-label', etichetta),
        crea('p', 'safety-muted', nota));
    return box;
}

// Numero con una barra proporzionale, per leggere a colpo d'occhio i gruppi più grandi
function conBarra(valore, massimo) {
    const contenitore = crea('span', 'population-bar-cell');
    const binario = crea('span', 'population-bar-track');
    binario.setAttribute('aria-hidden', 'true');
    const barra = crea('span', 'population-bar');
    barra.style.width = `${(valore / massimo) * 100}%`;
    binario.append(barra);
    contenitore.append(binario, crea('span', '', intero.format(valore)));
    return contenitore;
}

function mostra(d) {
    const r = d.residenti;
    const c = d.consultazione;
    const provvisorio = r.provvisorio ? ', dato provvisorio' : '';
    document.getElementById('population-figures').append(
        cifra(intero.format(r.valore), 'residenti a Busto', `ISTAT, fine ${fineMese(r.mese)}${provvisorio}`),
        cifra(intero.format(c.elettori), 'elettori', `${c.nome}`),
        cifra(decimale.format(d.k), 'residenti per elettore', 'il rapporto usato per la stima'),
    );

    const massimo = Math.max(...d.gruppi.map(g => g.residenti_stimati));
    tabella(document.getElementById('population-groups'),
        `A fine ${fineMese(r.mese)}, dagli elettori della consultazione di ${nomeMese.format(new Date(`${c.data.slice(0, 7)}-01T00:00:00Z`))}`,
        [['Gruppo di quartieri'], ['Sezioni', true], ['Elettori', true], ['Quota', true], ['Residenti stimati', true]],
        d.gruppi.map(g => [g.nome, g.sezioni, intero.format(g.elettori), percento.format(g.quota_elettori),
            conBarra(g.residenti_stimati, massimo)]));

    tabella(document.getElementById('population-schools'), 'Scuole e sedi dove si vota',
        [['Scuola o sede'], ['Sezioni'], ['Zona'], ['Gruppo'], ['Elettori', true], ['Perché']],
        d.plessi.map(p => {
            const perche = crea('span');
            perche.append(`${p.nota} `, link(p.fonte, 'Fonte'));
            const sezioni = p.sezioni[0] === p.sezioni[1] ? String(p.sezioni[0]) : `${p.sezioni[0]}–${p.sezioni[1]}`;
            return [p.nome, sezioni, p.zona, p.gruppo, intero.format(p.elettori), perche];
        }));

    document.getElementById('sezioni-titolo').textContent = `Elettori di tutte le ${d.sezioni.length} sezioni`;
    tabella(document.getElementById('population-sections'), `Elettori per sezione, ${c.nome}`,
        [['Sezione'], ['Scuola o sede'], ['Gruppo'], ['Uomini', true], ['Donne', true], ['Totale', true]],
        d.sezioni.map(s => [s.numero, s.scuola, s.gruppo, intero.format(s.elettori_m), intero.format(s.elettori_f),
            intero.format(s.elettori)]));

    const metodo = document.getElementById('population-method');
    const voce = (...parti) => { const li = crea('li'); li.append(...parti); metodo.append(li); };
    voce('Ogni sezione conta per il quartiere della scuola dove si vota, anche se una parte dei suoi elettori abita in ',
        'un quartiere vicino. Il Comune non pubblica i confini dei quartieri: i gruppi valgono solo per questa stima.');
    voce(`Residenti stimati di un gruppo = elettori del gruppo × ${decimale.format(d.k)}, cioè i residenti del Comune `,
        'divisi per gli elettori del Comune.');
    voce('Minorenni e stranieri non votano. Dove sono di più, i residenti veri sono più di quelli stimati, e altrove meno.');
    voce('Due attribuzioni non hanno una fonte nota: Sant’Anna e la scuola Marco Polo, contate nel gruppo ',
        'Redentore / Santi Apostoli. Le teniamo come nel foglio di calcolo da cui è partita la stima.');
    voce('Le sezioni dell’ospedale e dell’istituto La Provvidenza restano a parte.');
    voce('Elettori: ', link(c.link_sezioni, 'dettaglio per sezione'), ' e ', link(c.link_comune, 'totale del Comune'),
        `, dati ufficiosi dell’Ufficio elettorale, rilevazione del ${c.aggiornamento.slice(0, 10)}. Residenti: `,
        link(r.link, 'bilancio demografico mensile ISTAT'), `${provvisorio}, rivisto da ISTAT nel bilancio definitivo dell’anno.`);
    voce(`Aggiornato il ${formatDate(d.generato)}.`);
}

fetch('data/popolazione.json')
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(dati => {
        mostra(dati);
        document.getElementById('population-status').remove();
        document.getElementById('population-content').hidden = false;
    })
    .catch(errore => {
        console.error('Errore caricamento popolazione:', errore);
        document.getElementById('population-status').textContent = `Non riesco a caricare i dati (${errore.message}).`;
    });
