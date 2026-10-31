// In js/main.js
document.addEventListener('DOMContentLoaded', () => {
    // Elementi DOM principali
    const loadingStatusElement = document.getElementById('loading-status');
    const errorMessageElement = document.getElementById('error-message');
    const resultsBody = document.getElementById('results-body');
    const searchInput = document.getElementById('search-input');
    const searchButtonMain = document.getElementById('search-button-main'); 
    const applyFiltersButton = document.getElementById('apply-filters-button');
    const toggleFilterDropdownBtn = document.getElementById('toggle-filter-dropdown-btn');
    const filterOptionsDropdown = document.getElementById('filter-options-dropdown');
    const activeFiltersContainer = document.getElementById('active-filters-container');
    const resetAllFiltersButton = document.getElementById('reset-all-filters-button');
    
    // Usa l'ID del tuo spinner come definito in HTML
    const loadingSpinnerElement = document.getElementById('loading-spinner'); // Era 'tableLoader' nel mio esempio precedente

    // Elementi Info Risultati
    const currentRowsSpan = document.getElementById('current-rows');
    const totalRowsHeaderSpan = document.getElementById('total-rows-header'); 
    const totalRowsFooterSpan = document.getElementById('total-rows-footer'); 
    const currentPageSpan = document.getElementById('current-page');
    const totalPagesSpan = document.getElementById('total-pages'); 
    const paginationTotalPagesSpan = document.getElementById('pagination-total-pages');

    // Elementi Paginazione
    const firstPageButton = document.getElementById('first-page-button');
    const prevPageButton = document.getElementById('prev-page-button');
    const nextPageButton = document.getElementById('next-page-button');
    const lastPageButton = document.getElementById('last-page-button');
    const pageInput = document.getElementById('page-input');
    const rowsPerPageSelect = document.getElementById('rows-per-page');

    // Elemento per ordinamento
    const headerImporto = document.getElementById('header-importo');

    // Array per tenere traccia dei controlli interattivi da disabilitare/abilitare
    let interactiveControls = [
        searchButtonMain, applyFiltersButton, resetAllFiltersButton, toggleFilterDropdownBtn,
        searchInput, rowsPerPageSelect, pageInput, firstPageButton, prevPageButton,
        nextPageButton, lastPageButton, headerImporto
    ].filter(el => el != null); 

    const dbUrl = 'busto_pagamenti.db'; 
    let db = null; 
    let currentQueryState = { 
        searchTerm: '',
        activeFilters: {}, 
        currentPage: 1,
        rowsPerPage: parseInt(rowsPerPageSelect.value, 10), // Assicurati che rowsPerPageSelect esista al caricamento
        totalRows: 0,
        totalPages: 1,
        orderByField: 'DataMandato', 
        orderByDirection: 'DESC'     
    };

    // NOTA: Inizializza rowsPerPage se rowsPerPageSelect non è garantito
    if (rowsPerPageSelect) {
        currentQueryState.rowsPerPage = parseInt(rowsPerPageSelect.value, 10);
    } else {
        currentQueryState.rowsPerPage = 50; // Valore di default se il select non è trovato
        console.warn("Elemento 'rows-per-page' non trovato, usando default 50 righe per pagina.");
    }


    const COLUMNS_TO_SELECT = ['Anno', 'DataMandato', 'Beneficiario', 'ImportoEuro', 'DescrizioneMandato', 'NumeroMandato'];
    const COLUMNS_STRING = COLUMNS_TO_SELECT.join(', ');

    // --- GESTIONE STATO DI CARICAMENTO ---
    function setLoadingState(isLoading) {
        if (loadingSpinnerElement) { // Usa la variabile corretta per il tuo spinner
            loadingSpinnerElement.style.display = isLoading ? 'flex' : 'none'; // 'flex' per via del tuo HTML
        }
        
        if (loadingStatusElement) { // Nascondi il testo di caricamento se lo spinner è attivo
            loadingStatusElement.style.display = 'none'; 
        }

        interactiveControls.forEach(control => {
            if (control) control.disabled = isLoading;
        });
        
        if (activeFiltersContainer) {
            if (isLoading) {
                activeFiltersContainer.classList.add('controls-disabled');
            } else {
                activeFiltersContainer.classList.remove('controls-disabled');
            }
        }
        
        if (!isLoading && resultsBody) { // Aggiorna paginazione solo se resultsBody esiste
            updatePaginationInfo(resultsBody.rows.length);
        }
    }

    // --- FUNZIONE PER AGGIORNARE L'INTERFACCIA DELLE FRECCE DI ORDINAMENTO ---
    function updateSortArrows() { 
        document.querySelectorAll('.sortable-header').forEach(header => {
            header.classList.remove('sort-asc', 'sort-desc');
        });
        if (currentQueryState.orderByField === 'ImportoEuro' && headerImporto) {
            if (currentQueryState.orderByDirection === 'ASC') {
                headerImporto.classList.add('sort-asc');
            } else if (currentQueryState.orderByDirection === 'DESC') {
                headerImporto.classList.add('sort-desc');
            }
        }
    }
    
    // --- GESTIONE VISIBILITÀ PULSANTI FILTRO ---
    function updateActionButtonsVisibility() { 
        const hasActiveFiltersWithOptions = Object.values(currentQueryState.activeFilters).some(
            filter => filter.value !== null && (typeof filter.value === 'string' ? filter.value.trim() !== '' : true)
        );
        const hasGeneralSearchTerm = searchInput && searchInput.value.trim() !== ''; // Aggiunto controllo per searchInput

        if (applyFiltersButton) applyFiltersButton.style.display = hasActiveFiltersWithOptions ? 'inline-block' : 'none';
        if (resetAllFiltersButton) resetAllFiltersButton.style.display = (Object.keys(currentQueryState.activeFilters).length > 0 || hasGeneralSearchTerm) ? 'inline-block' : 'none';
    }

    function addFilter(filterType, filterLabel) {
        if (currentQueryState.activeFilters[filterType]) return;
        let operatorOptionsHtml = '', inputType = 'text', inputPlaceholder = 'Valore...', inputStep = ''; 
        if (filterType === 'year') { operatorOptionsHtml = `<option value="equals" selected>uguale a</option><option value="greater_than">maggiore di</option><option value="less_than">minore di</option>`; inputType = 'number'; inputPlaceholder = 'Es. 2023';}
        else if (filterType === 'beneficiary' || filterType === 'description') { operatorOptionsHtml = `<option value="contains" selected>contiene</option><option value="equals">uguale a</option><option value="starts_with">inizia con</option><option value="ends_with">finisce con</option>`; inputPlaceholder = 'Testo...';}
        else if (filterType === 'amount') { operatorOptionsHtml = `<option value="equals" selected>uguale a</option><option value="greater_than">maggiore di</option><option value="less_than">minore di</option><option value="not_equals">diverso da</option>`; inputType = 'number'; inputPlaceholder = 'Es. 123.45'; inputStep = '0.01';}
        const filterIdPrefix = `${filterType}-filter`;
        const filterHtml = `<div class="active-filter-item" data-filter-type="${filterType}"><button class="filter-name-tag" data-remove-filter="${filterType}" title="Rimuovi filtro ${filterLabel}"><span class="remove-icon">×</span> ${filterLabel}</button><select class="filter-operator-select" id="${filterIdPrefix}-operator">${operatorOptionsHtml}</select><input type="${inputType}" class="filter-value-input" id="${filterIdPrefix}-value" placeholder="${inputPlaceholder}" ${inputStep ? `step="${inputStep}"` : ''}></div>`;
        if(activeFiltersContainer) activeFiltersContainer.insertAdjacentHTML('beforeend', filterHtml); else console.warn("activeFiltersContainer non trovato");
        currentQueryState.activeFilters[filterType] = { value: null, operator: document.getElementById(`${filterIdPrefix}-operator`).value };
        const valueInput = document.getElementById(`${filterIdPrefix}-value`);
        const operatorSelect = document.getElementById(`${filterIdPrefix}-operator`);
        if (valueInput) interactiveControls.push(valueInput);
        if (operatorSelect) interactiveControls.push(operatorSelect);
        const handleFilterInputChange = () => { let val = valueInput.value.trim(); if (valueInput.type === 'number') { val = val ? parseFloat(val) : null; if (isNaN(val)) val = null; } currentQueryState.activeFilters[filterType].value = val; currentQueryState.activeFilters[filterType].operator = operatorSelect.value; updateActionButtonsVisibility(); };
        valueInput.addEventListener('input', handleFilterInputChange);
        operatorSelect.addEventListener('change', handleFilterInputChange);
        valueInput.addEventListener('keypress', e => { if (e.key === 'Enter') { e.preventDefault(); triggerSearchExecution(); }});
        valueInput.focus();
        const dropdownOption = filterOptionsDropdown.querySelector(`a[data-filter-type="${filterType}"]`);
        if (dropdownOption) dropdownOption.classList.add('disabled');
        if(filterOptionsDropdown) filterOptionsDropdown.style.display = 'none';
        updateActionButtonsVisibility();
    }

    function removeFilter(filterType) {
        const filterItem = activeFiltersContainer.querySelector(`.active-filter-item[data-filter-type="${filterType}"]`);
        if (filterItem) {
            const valueInput = filterItem.querySelector('.filter-value-input');
            const operatorSelect = filterItem.querySelector('.filter-operator-select');
            if (valueInput) interactiveControls = interactiveControls.filter(el => el && el.id !== valueInput.id); // Aggiunto controllo el
            if (operatorSelect) interactiveControls = interactiveControls.filter(el => el && el.id !== operatorSelect.id); // Aggiunto controllo el
            filterItem.remove();
        }
        delete currentQueryState.activeFilters[filterType];
        const dropdownOption = filterOptionsDropdown.querySelector(`a[data-filter-type="${filterType}"]`);
        if (dropdownOption) dropdownOption.classList.remove('disabled');
        updateActionButtonsVisibility();
    }

    function resetAllFilters() {
        if(searchInput) searchInput.value = ''; 
        currentQueryState.searchTerm = '';
        Object.keys(currentQueryState.activeFilters).forEach(filterType => {
            const filterItem = activeFiltersContainer.querySelector(`.active-filter-item[data-filter-type="${filterType}"]`);
            if (filterItem) {
                const valueInput = filterItem.querySelector('.filter-value-input');
                const operatorSelect = filterItem.querySelector('.filter-operator-select');
                if (valueInput) interactiveControls = interactiveControls.filter(el => el && el.id !== valueInput.id);
                if (operatorSelect) interactiveControls = interactiveControls.filter(el => el && el.id !== operatorSelect.id);
                filterItem.remove();
            }
            const dropdownOption = filterOptionsDropdown.querySelector(`a[data-filter-type="${filterType}"]`);
            if (dropdownOption) dropdownOption.classList.remove('disabled');
        });
        currentQueryState.activeFilters = {};
        updateActionButtonsVisibility();
        triggerSearchExecution(); 
    }
    
    function triggerSearchExecution() {
        setLoadingState(true); 
        currentQueryState.currentPage = 1;
        setTimeout(() => { fetchDataAndDisplay(); }, 50); 
    }

    // --- Event Listeners (con controlli null) ---
    if(toggleFilterDropdownBtn) toggleFilterDropdownBtn.addEventListener('click', () => { if(filterOptionsDropdown) filterOptionsDropdown.style.display = filterOptionsDropdown.style.display === 'none' ? 'block' : 'none'; });
    if(filterOptionsDropdown) filterOptionsDropdown.addEventListener('click', (event) => { event.preventDefault(); const target = event.target.closest('a[data-filter-type]'); if (target && !target.classList.contains('disabled')) { addFilter(target.dataset.filterType, target.dataset.filterLabel || target.textContent); }});
    if(activeFiltersContainer) activeFiltersContainer.addEventListener('click', (event) => { const target = event.target.closest('button[data-remove-filter]'); if (target) removeFilter(target.dataset.removeFilter); });
    if(resetAllFiltersButton) resetAllFiltersButton.addEventListener('click', resetAllFilters);
    if(applyFiltersButton) applyFiltersButton.addEventListener('click', triggerSearchExecution);
    if(searchButtonMain) searchButtonMain.addEventListener('click', triggerSearchExecution);
    if(searchInput) { searchInput.addEventListener('input', updateActionButtonsVisibility); searchInput.addEventListener('keypress', e => { if (e.key === 'Enter') { e.preventDefault(); triggerSearchExecution(); }}); }
    document.addEventListener('click', function(event) { if (toggleFilterDropdownBtn && filterOptionsDropdown && !toggleFilterDropdownBtn.contains(event.target) && !filterOptionsDropdown.contains(event.target) && filterOptionsDropdown.style.display === 'block') { filterOptionsDropdown.style.display = 'none'; }});

    // --- CARICAMENTO DB E LOGICA DATI ---
    async function loadAndInitializeDb() {
        setLoadingState(true);
        try {
            if(loadingStatusElement) loadingStatusElement.textContent = 'Caricamento libreria SQLite (sql.js)...'; else console.log('Caricamento libreria SQLite (sql.js)...');
            const SQL = await initSqlJs({ locateFile: file => `js/lib/${file}` });
            if(loadingStatusElement) loadingStatusElement.textContent = `Download database (${dbUrl})...`; else console.log(`Download database (${dbUrl})...`);
            const response = await fetch(dbUrl);
            if (!response.ok) throw new Error(`Errore HTTP ${response.status} nel download.`);
            const arrayBuffer = await response.arrayBuffer();
            if(loadingStatusElement) loadingStatusElement.textContent = 'Caricamento database in memoria...'; else console.log('Caricamento database in memoria...');
            db = new SQL.Database(new Uint8Array(arrayBuffer));
            if(loadingStatusElement) { loadingStatusElement.textContent = 'Database caricato!'; loadingStatusElement.style.display = 'none';} else console.log('Database caricato!');

            // Ricerca precompilata da link esterni (es. cruscotto.html → pagamenti.html?q=AGESP)
            const initialSearch = new URLSearchParams(window.location.search).get('q');
            if (initialSearch && searchInput) searchInput.value = initialSearch;

            await fetchDataAndDisplay();
            updateActionButtonsVisibility();
            updateSortArrows();

            if(headerImporto) { headerImporto.addEventListener('click', () => { if (currentQueryState.orderByField === 'ImportoEuro') { currentQueryState.orderByDirection = currentQueryState.orderByDirection === 'ASC' ? 'DESC' : 'ASC'; } else { currentQueryState.orderByField = 'ImportoEuro'; currentQueryState.orderByDirection = 'DESC'; } triggerSearchExecution(); }); }
            if(rowsPerPageSelect) rowsPerPageSelect.addEventListener('change', (event) => { currentQueryState.rowsPerPage = parseInt(event.target.value, 10); triggerSearchExecution(); });
            if(pageInput) { pageInput.addEventListener('change', () => { let newPage = parseInt(pageInput.value, 10); goToPage(newPage, true); }); pageInput.addEventListener('keypress', e => { if (e.key === 'Enter') pageInput.dispatchEvent(new Event('change'));}); }
            if(firstPageButton) firstPageButton.addEventListener('click', () => goToPage(1));
            if(prevPageButton) prevPageButton.addEventListener('click', () => goToPage(currentQueryState.currentPage - 1));
            if(nextPageButton) nextPageButton.addEventListener('click', () => goToPage(currentQueryState.currentPage + 1));
            if(lastPageButton) lastPageButton.addEventListener('click', () => goToPage(currentQueryState.totalPages));

        } catch (error) {
            console.error('Errore inizializzazione DB:', error);
            if (loadingStatusElement) loadingStatusElement.style.display = 'none';
            if (errorMessageElement) { errorMessageElement.textContent = `ERRORE CRITICO: ${error.message}. Controlla la console.`; errorMessageElement.style.display = 'block';}
            setLoadingState(false);
        }
    }
    
    function goToPage(pageNumber, fromInputChange = false) {
        let newPage = parseInt(pageNumber, 10);
        if (isNaN(newPage)) { if(pageInput) pageInput.value = currentQueryState.currentPage; return; }
        if (newPage < 1) newPage = 1;
        if (currentQueryState.totalPages > 0 && newPage > currentQueryState.totalPages) newPage = currentQueryState.totalPages;
        else if (currentQueryState.totalPages === 0 && newPage > 1) newPage = 1;
        if (newPage !== currentQueryState.currentPage || fromInputChange) {
            currentQueryState.currentPage = newPage;
            if(pageInput) pageInput.value = newPage; 
            setLoadingState(true); 
            setTimeout(() => { fetchDataAndDisplay(); }, 50);
        } else if (fromInputChange) {
             if(pageInput) pageInput.value = currentQueryState.currentPage;
        }
    }

    async function fetchDataAndDisplay() {
        if (!db) { setLoadingState(false); return; }
        if (loadingStatusElement) loadingStatusElement.style.display = 'none';
        if (errorMessageElement) errorMessageElement.style.display = 'none';

        try {
            // La logica per leggere i filtri, costruire le query, eseguire le query
            // e popolare la tabella è esattamente come nella tua ultima versione fornita.
            // Per mantenere questa risposta concisa, non la ripeterò qui, ma assicurati
            // che sia identica a quella che funzionava per te.
            // Il blocco inizia con: currentQueryState.searchTerm = searchInput.value.trim();
            // e finisce prima del blocco catch.

            // --- INIZIO BLOCCO LOGICA QUERY (Identica alla tua ultima versione) ---
            currentQueryState.searchTerm = searchInput ? searchInput.value.trim() : '';
            for (const filterType in currentQueryState.activeFilters) {
                const valueInput = document.getElementById(`${filterType}-filter-value`);
                const operatorSelect = document.getElementById(`${filterType}-filter-operator`);
                if (valueInput && operatorSelect) {
                    let val = valueInput.value.trim();
                    if (valueInput.type === 'number') { val = val ? parseFloat(val) : null; if (isNaN(val)) val = null; }
                    currentQueryState.activeFilters[filterType].value = val;
                    currentQueryState.activeFilters[filterType].operator = operatorSelect.value;
                }
            }
            let params = []; let whereClauses = [];
            if (currentQueryState.searchTerm) {
                whereClauses.push("(Beneficiario LIKE ? OR DescrizioneMandato LIKE ? OR Anno LIKE ? OR CAST(NumeroMandato AS TEXT) LIKE ?)");
                const searchTermLike = `%${currentQueryState.searchTerm}%`;
                params.push(searchTermLike, searchTermLike, searchTermLike, searchTermLike);
            }
            for (const filterType in currentQueryState.activeFilters) {
                const filter = currentQueryState.activeFilters[filterType];
                if (filter.value !== null && (typeof filter.value === 'string' ? filter.value !== '' : true) ) {
                    let fieldName = '', valueToUse = filter.value;
                    if (filterType === 'year') fieldName = 'Anno'; else if (filterType === 'beneficiary') fieldName = 'Beneficiario';
                    else if (filterType === 'description') fieldName = 'DescrizioneMandato'; else if (filterType === 'amount') fieldName = 'ImportoEuro';
                    if (fieldName) {
                        let operatorSql = '=';
                        switch (filter.operator) {
                            case 'equals': operatorSql = '='; break; case 'not_equals': operatorSql = '!='; break;
                            case 'greater_than': operatorSql = '>'; break; case 'less_than': operatorSql = '<'; break;
                            case 'contains': operatorSql = 'LIKE'; valueToUse = `%${filter.value}%`; break;
                            case 'starts_with': operatorSql = 'LIKE'; valueToUse = `${filter.value}%`; break;
                            case 'ends_with': operatorSql = 'LIKE'; valueToUse = `%${filter.value}`; break;
                        }
                        whereClauses.push(`${fieldName} ${operatorSql} ?`); params.push(valueToUse);
                    }
                }
            }
            let countQuery = "SELECT COUNT(*) as total FROM pagamenti";
            if (whereClauses.length > 0) countQuery += " WHERE " + whereClauses.join(" AND ");
            const countResult = db.exec(countQuery, params);
            currentQueryState.totalRows = (countResult.length > 0 && countResult[0].values.length > 0) ? countResult[0].values[0][0] : 0;
            currentQueryState.totalPages = Math.ceil(currentQueryState.totalRows / currentQueryState.rowsPerPage) || 1;
            if (currentQueryState.currentPage > currentQueryState.totalPages && currentQueryState.totalPages > 0) { currentQueryState.currentPage = currentQueryState.totalPages; }
            else if (currentQueryState.currentPage > 1 && currentQueryState.totalPages === 0) { currentQueryState.currentPage = 1; }
            if (currentQueryState.currentPage < 1) { currentQueryState.currentPage = 1; }
            let dataQuery = `SELECT ${COLUMNS_STRING} FROM pagamenti`;
            if (whereClauses.length > 0) dataQuery += " WHERE " + whereClauses.join(" AND ");
            dataQuery += ` ORDER BY ${currentQueryState.orderByField} ${currentQueryState.orderByDirection}`;
            if (currentQueryState.orderByField !== 'NumeroMandato') dataQuery += `, NumeroMandato DESC`; 
            const offset = (currentQueryState.currentPage - 1) * currentQueryState.rowsPerPage;
            dataQuery += ` LIMIT ? OFFSET ?;`;
            let dataParams = [...params]; dataParams.push(currentQueryState.rowsPerPage); dataParams.push(offset);
            if(resultsBody) resultsBody.innerHTML = ''; else console.error("resultsBody non trovato prima di innerHTML");
            let displayedRowCount = 0;
            const dataResults = db.exec(dataQuery, dataParams);
            if (dataResults.length > 0 && dataResults[0].values.length > 0) {
                const columnNames = dataResults[0].columns;
                dataResults[0].values.forEach(valueRow => {
                    const row = {}; columnNames.forEach((colName, index) => { row[colName] = valueRow[index]; });
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${row.Anno !== undefined && row.Anno !== null ? row.Anno : ''}</td>
                        <td>${row.DataMandato ? new Date(row.DataMandato).toLocaleDateString('it-IT') : ''}</td>
                        <td>${row.Beneficiario || ''}</td>
                        <td>${row.ImportoEuro !== undefined && row.ImportoEuro !== null ? parseFloat(row.ImportoEuro).toLocaleString('it-IT', { style: 'currency', currency: 'EUR' }) : ''}</td>
                        <td>${row.DescrizioneMandato || ''}</td>
                        <td>${row.NumeroMandato !== undefined && row.NumeroMandato !== null ? row.NumeroMandato : ''}</td>
                    `;
                   if(resultsBody) resultsBody.appendChild(tr);
                    displayedRowCount++;
                });
            }
            // --- FINE BLOCCO LOGICA QUERY ---
            updatePaginationInfo(displayedRowCount);
            updateActionButtonsVisibility();
            updateSortArrows();
        } catch (e) {
            console.error("Errore durante il recupero o la visualizzazione dei dati:", e);
            if(errorMessageElement) {errorMessageElement.textContent = `Errore: ${e.message}`; errorMessageElement.style.display = 'block';}
            if(resultsBody) resultsBody.innerHTML = `<tr><td colspan="${COLUMNS_TO_SELECT.length}" style="text-align:center; color:red;">Errore nel caricamento dei dati.</td></tr>`;
            currentQueryState.totalRows = 0; currentQueryState.totalPages = 1;
            updatePaginationInfo(0);
        } finally {
            setLoadingState(false);
        }
    }

    function updatePaginationInfo(displayedRows) {
        if(totalRowsHeaderSpan) totalRowsHeaderSpan.textContent = currentQueryState.totalRows.toLocaleString('it-IT');
        if(totalRowsFooterSpan) totalRowsFooterSpan.textContent = currentQueryState.totalRows.toLocaleString('it-IT');
        if(currentRowsSpan) currentRowsSpan.textContent = displayedRows.toLocaleString('it-IT');
        if(currentPageSpan) currentPageSpan.textContent = currentQueryState.currentPage.toLocaleString('it-IT');
        if(totalPagesSpan) totalPagesSpan.textContent = currentQueryState.totalPages.toLocaleString('it-IT');
        if(paginationTotalPagesSpan) paginationTotalPagesSpan.textContent = currentQueryState.totalPages.toLocaleString('it-IT');
        if(pageInput) { pageInput.value = currentQueryState.currentPage; pageInput.max = currentQueryState.totalPages > 0 ? currentQueryState.totalPages : 1; }
        const noResultsOrSinglePage = currentQueryState.totalPages <= 1;
        if(firstPageButton) firstPageButton.disabled = currentQueryState.currentPage === 1 || noResultsOrSinglePage;
        if(prevPageButton) prevPageButton.disabled = currentQueryState.currentPage === 1 || noResultsOrSinglePage;
        if(nextPageButton) nextPageButton.disabled = currentQueryState.currentPage === currentQueryState.totalPages || noResultsOrSinglePage;
        if(lastPageButton) lastPageButton.disabled = currentQueryState.currentPage === currentQueryState.totalPages || noResultsOrSinglePage;
        if(pageInput) pageInput.disabled = noResultsOrSinglePage;
    }

    loadAndInitializeDb();
});