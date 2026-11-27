// Cerca pagamenti: interroga nel browser il database SQLite (sql.js) con ricerca libera, filtri, ordinamento e pagine
document.addEventListener('DOMContentLoaded', () => {
    const $ = id => document.getElementById(id);
    const spinner = $('loading-spinner');
    const statoCaricamento = $('loading-status');
    const messaggioErrore = $('error-message');
    const corpoTabella = $('results-body');
    const ricerca = $('search-input');
    const applica = $('apply-filters-button');
    const apriFiltri = $('toggle-filter-dropdown-btn');
    const menuFiltri = $('filter-options-dropdown');
    const filtriAttivi = $('active-filters-container');
    const reimposta = $('reset-all-filters-button');
    const intestazioneImporto = $('header-importo');
    const inputPagina = $('page-input');
    const righePerPagina = $('rows-per-page');
    const pulsantiPagina = { prima: $('first-page-button'), prec: $('prev-page-button'), succ: $('next-page-button'), ultima: $('last-page-button') };

    const DB = 'busto_pagamenti.db';
    const COLONNE = ['Anno', 'DataMandato', 'Beneficiario', 'ImportoEuro', 'DescrizioneMandato', 'NumeroMandato'];
    const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' });
    const intero = new Intl.NumberFormat('it-IT');

    // Per ogni filtro: colonna, operatori possibili (il primo è quello proposto) e campo da compilare
    const UGUALE = ['equals', 'uguale a'];
    const MAGGIORE = ['greater_than', 'maggiore di'];
    const MINORE = ['less_than', 'minore di'];
    const TESTO = { operatori: [['contains', 'contiene'], UGUALE, ['starts_with', 'inizia con'], ['ends_with', 'finisce con']], tipo: 'text', esempio: 'Testo...' };
    const FILTRI = {
        year: { colonna: 'Anno', operatori: [UGUALE, MAGGIORE, MINORE], tipo: 'number', esempio: 'Es. 2023' },
        beneficiary: { colonna: 'Beneficiario', ...TESTO },
        description: { colonna: 'DescrizioneMandato', ...TESTO },
        amount: { colonna: 'ImportoEuro', operatori: [UGUALE, MAGGIORE, MINORE, ['not_equals', 'diverso da']], tipo: 'number', esempio: 'Es. 123.45', passo: '0.01' },
    };
    // Operatore SQL e forma del valore cercato
    const SQL = {
        equals: ['=', v => v], not_equals: ['!=', v => v], greater_than: ['>', v => v], less_than: ['<', v => v],
        contains: ['LIKE', v => `%${v}%`], starts_with: ['LIKE', v => `${v}%`], ends_with: ['LIKE', v => `%${v}`],
    };

    let db = null;
    let caricando = false;
    let focusPrima = null;
    const stato = { pagina: 1, perPagina: parseInt(righePerPagina.value, 10), totale: 0, pagine: 1, ordine: 'DataMandato', verso: 'DESC' };
    // Filtri aperti: tipo -> { operatore: <select>, valore: <input> }
    const filtri = new Map();

    const valoreFiltro = ({ valore }) => {
        const testo = valore.value.trim();
        if (valore.type !== 'number') return testo;
        const numero = parseFloat(testo);
        return Number.isNaN(numero) ? null : numero;
    };
    const compilato = f => { const v = valoreFiltro(f); return v !== null && v !== ''; };

    function caricamento(attivo) {
        caricando = attivo;
        spinner.hidden = !attivo;
        statoCaricamento.hidden = true;
        if (attivo && document.activeElement && document.activeElement !== document.body) focusPrima = document.activeElement;
        document.querySelectorAll('.page-controls-bar :is(button, input), #active-filters-area :is(button, input, select), .pagination :is(button, input, select)')
            .forEach(el => { el.disabled = attivo; });
        filtriAttivi.classList.toggle('controls-disabled', attivo);
        if (!attivo) {
            aggiornaPagine(corpoTabella.rows.length);
            // I controlli disattivati durante la query perdono il focus: torna dov'era o su un controllo vicino
            if (focusPrima && (!document.activeElement || document.activeElement === document.body)) {
                const vicini = focusPrima.closest('.pagination') ? [focusPrima, inputPagina, righePerPagina] : [focusPrima, ricerca];
                vicini.find(el => el.isConnected && !el.disabled && !el.hidden)?.focus();
            }
            focusPrima = null;
        }
    }

    function apriMenu(aperto) {
        menuFiltri.hidden = !aperto;
        apriFiltri.setAttribute('aria-expanded', aperto);
    }

    function aggiornaPulsanti() {
        applica.hidden = ![...filtri.values()].some(compilato);
        reimposta.hidden = !filtri.size && !ricerca.value.trim();
    }

    function aggiornaFreccia() {
        intestazioneImporto.classList.remove('sort-asc', 'sort-desc');
        if (stato.ordine === 'ImportoEuro') intestazioneImporto.classList.add(stato.verso === 'ASC' ? 'sort-asc' : 'sort-desc');
        // Per i lettori di schermo: quale colonna ordina la tabella e in che verso
        for (const th of intestazioneImporto.parentElement.children) th.removeAttribute('aria-sort');
        const colonna = intestazioneImporto.parentElement.children[COLONNE.indexOf(stato.ordine)];
        colonna?.setAttribute('aria-sort', stato.verso === 'ASC' ? 'ascending' : 'descending');
    }

    function aggiungiFiltro(tipo, nome) {
        if (filtri.has(tipo)) return;
        const def = FILTRI[tipo];
        const riquadro = document.createElement('div');
        riquadro.className = 'active-filter-item';
        riquadro.dataset.filterType = tipo;
        const togli = document.createElement('button');
        togli.className = 'filter-name-tag';
        togli.dataset.removeFilter = tipo;
        togli.title = `Rimuovi filtro ${nome}`;
        togli.setAttribute('aria-label', `Rimuovi filtro ${nome}`);
        const croce = document.createElement('span');
        croce.className = 'remove-icon';
        croce.textContent = '×';
        togli.append(croce, ` ${nome}`);
        const operatore = document.createElement('select');
        operatore.className = 'filter-operator-select';
        operatore.id = `${tipo}-filter-operator`;
        operatore.setAttribute('aria-label', `Condizione per ${nome}`);
        operatore.append(...def.operatori.map(([valore, testo]) => new Option(testo, valore)));
        const valore = document.createElement('input');
        valore.type = def.tipo;
        valore.className = 'filter-value-input';
        valore.id = `${tipo}-filter-value`;
        valore.placeholder = def.esempio;
        valore.setAttribute('aria-label', `Valore per ${nome}`);
        if (def.passo) valore.step = def.passo;
        riquadro.append(togli, operatore, valore);
        filtriAttivi.append(riquadro);
        filtri.set(tipo, { operatore, valore });

        valore.addEventListener('input', aggiornaPulsanti);
        operatore.addEventListener('change', aggiornaPulsanti);
        valore.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); cerca(); } });
        valore.focus();
        const voce = menuFiltri.querySelector(`a[data-filter-type="${tipo}"]`);
        voce?.classList.add('disabled');
        voce?.setAttribute('aria-disabled', 'true');
        apriMenu(false);
        aggiornaPulsanti();
    }

    function togliFiltro(tipo) {
        filtriAttivi.querySelector(`.active-filter-item[data-filter-type="${tipo}"]`)?.remove();
        filtri.delete(tipo);
        const voce = menuFiltri.querySelector(`a[data-filter-type="${tipo}"]`);
        voce?.classList.remove('disabled');
        voce?.removeAttribute('aria-disabled');
        aggiornaPulsanti();
    }

    function reimpostaTutto() {
        ricerca.value = '';
        [...filtri.keys()].forEach(togliFiltro);
        cerca();
    }

    // La pausa lascia al browser il tempo di mostrare l'attesa prima della query, che blocca la pagina
    function interroga() {
        caricamento(true);
        setTimeout(mostraRisultati, 50);
    }

    function cerca() {
        stato.pagina = 1;
        interroga();
    }

    function vaiAPagina(numero, daCampo = false) {
        let pagina = parseInt(numero, 10);
        if (Number.isNaN(pagina)) { inputPagina.value = stato.pagina; return; }
        pagina = Math.min(Math.max(pagina, 1), stato.pagine);
        if (pagina !== stato.pagina || daCampo) {
            stato.pagina = pagina;
            inputPagina.value = pagina;
            interroga();
        }
    }

    function condizioni() {
        const dove = [];
        const parametri = [];
        const testo = ricerca.value.trim();
        if (testo) {
            dove.push('(Beneficiario LIKE ? OR DescrizioneMandato LIKE ? OR Anno LIKE ? OR CAST(NumeroMandato AS TEXT) LIKE ?)');
            parametri.push(...Array(4).fill(`%${testo}%`));
        }
        for (const [tipo, f] of filtri) {
            if (!compilato(f)) continue;
            const [operatore, forma] = SQL[f.operatore.value];
            dove.push(`${FILTRI[tipo].colonna} ${operatore} ?`);
            parametri.push(forma(valoreFiltro(f)));
        }
        return { where: dove.length ? ` WHERE ${dove.join(' AND ')}` : '', parametri };
    }

    // Testo, mai HTML: beneficiari e descrizioni vengono dal Comune e possono contenere < e &
    function cella(riga, testo) {
        riga.insertCell().textContent = testo ?? '';
    }

    function mostraRisultati() {
        if (!db) { caricamento(false); return; }
        messaggioErrore.hidden = true;
        try {
            const { where, parametri } = condizioni();
            stato.totale = db.exec(`SELECT COUNT(*) FROM pagamenti${where}`, parametri)[0]?.values[0][0] ?? 0;
            stato.pagine = Math.ceil(stato.totale / stato.perPagina) || 1;
            stato.pagina = Math.min(Math.max(stato.pagina, 1), stato.pagine);
            // A parità di importo o di data, il mandato più recente prima
            const ordine = stato.ordine === 'NumeroMandato' ? '' : ', NumeroMandato DESC';
            const risultato = db.exec(
                `SELECT ${COLONNE.join(', ')} FROM pagamenti${where} ORDER BY ${stato.ordine} ${stato.verso}${ordine} LIMIT ? OFFSET ?`,
                [...parametri, stato.perPagina, (stato.pagina - 1) * stato.perPagina])[0];

            corpoTabella.replaceChildren();
            for (const valori of risultato?.values ?? []) {
                const r = Object.fromEntries(risultato.columns.map((c, i) => [c, valori[i]]));
                const riga = corpoTabella.insertRow();
                cella(riga, r.Anno);
                cella(riga, r.DataMandato && new Date(r.DataMandato).toLocaleDateString('it-IT'));
                cella(riga, r.Beneficiario);
                cella(riga, r.ImportoEuro != null ? euro.format(parseFloat(r.ImportoEuro)) : '');
                cella(riga, r.DescrizioneMandato);
                cella(riga, r.NumeroMandato);
            }
            aggiornaPagine(corpoTabella.rows.length);
            aggiornaPulsanti();
            aggiornaFreccia();
        } catch (e) {
            console.error('Errore nella ricerca dei pagamenti:', e);
            messaggioErrore.textContent = `Errore: ${e.message}`;
            messaggioErrore.hidden = false;
            corpoTabella.replaceChildren();
            const avviso = corpoTabella.insertRow().insertCell();
            avviso.colSpan = COLONNE.length;
            avviso.className = 'table-error';
            avviso.textContent = 'Errore nel caricamento dei dati.';
            stato.totale = 0;
            stato.pagine = 1;
            aggiornaPagine(0);
        } finally {
            caricamento(false);
        }
    }

    function aggiornaPagine(mostrate) {
        const testi = { 'total-rows-header': stato.totale, 'total-rows-footer': stato.totale, 'current-rows': mostrate,
            'current-page': stato.pagina, 'total-pages': stato.pagine, 'pagination-total-pages': stato.pagine };
        for (const [id, n] of Object.entries(testi)) $(id).textContent = intero.format(n);
        inputPagina.value = stato.pagina;
        inputPagina.max = stato.pagine;
        const unaSola = stato.pagine <= 1;
        pulsantiPagina.prima.disabled = pulsantiPagina.prec.disabled = unaSola || stato.pagina === 1;
        pulsantiPagina.succ.disabled = pulsantiPagina.ultima.disabled = unaSola || stato.pagina === stato.pagine;
        inputPagina.disabled = unaSola;
    }

    apriFiltri.addEventListener('click', () => apriMenu(menuFiltri.hidden));
    menuFiltri.addEventListener('click', e => {
        e.preventDefault();
        const voce = e.target.closest('a[data-filter-type]');
        if (voce && !voce.classList.contains('disabled')) aggiungiFiltro(voce.dataset.filterType, voce.dataset.filterLabel || voce.textContent);
    });
    document.addEventListener('click', e => {
        if (!apriFiltri.contains(e.target) && !menuFiltri.contains(e.target)) apriMenu(false);
    });
    // Esc chiude il menu dei filtri e riporta il focus sul pulsante che l'ha aperto
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !menuFiltri.hidden) {
            const dentro = menuFiltri.contains(document.activeElement);
            apriMenu(false);
            if (dentro || document.activeElement === apriFiltri) apriFiltri.focus();
        }
    });
    filtriAttivi.addEventListener('click', e => {
        const togli = e.target.closest('button[data-remove-filter]');
        if (!togli) return;
        togliFiltro(togli.dataset.removeFilter);
        // Il pulsante premuto sparisce: il focus va su "Aggiungi Filtro" invece di perdersi
        apriFiltri.focus();
    });
    reimposta.addEventListener('click', reimpostaTutto);
    applica.addEventListener('click', cerca);
    $('search-button-main').addEventListener('click', cerca);
    ricerca.addEventListener('input', aggiornaPulsanti);
    ricerca.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); cerca(); } });
    intestazioneImporto.addEventListener('click', () => {
        if (caricando) return;
        stato.verso = stato.ordine === 'ImportoEuro' && stato.verso === 'DESC' ? 'ASC' : 'DESC';
        stato.ordine = 'ImportoEuro';
        cerca();
    });
    righePerPagina.addEventListener('change', () => { stato.perPagina = parseInt(righePerPagina.value, 10); cerca(); });
    inputPagina.addEventListener('change', () => vaiAPagina(inputPagina.value, true));
    pulsantiPagina.prima.addEventListener('click', () => vaiAPagina(1));
    pulsantiPagina.prec.addEventListener('click', () => vaiAPagina(stato.pagina - 1));
    pulsantiPagina.succ.addEventListener('click', () => vaiAPagina(stato.pagina + 1));
    pulsantiPagina.ultima.addEventListener('click', () => vaiAPagina(stato.pagine));

    async function avvia() {
        caricamento(true);
        try {
            const SQLite = await initSqlJs({ locateFile: file => `js/lib/${file}` });
            const risposta = await fetch(DB);
            if (!risposta.ok) throw new Error(`Errore HTTP ${risposta.status} nel download.`);
            db = new SQLite.Database(new Uint8Array(await risposta.arrayBuffer()));
            // Ricerca precompilata dai link del cruscotto (pagamenti.html?q=AGESP)
            ricerca.value = new URLSearchParams(location.search).get('q') ?? '';
            mostraRisultati();
            aggiornaPulsanti();
        } catch (e) {
            console.error('Errore nel caricamento del database:', e);
            messaggioErrore.textContent = `Non riesco a caricare il database dei pagamenti (${e.message}). Riprova più tardi.`;
            messaggioErrore.hidden = false;
            caricamento(false);
        }
    }

    avvia();
});
