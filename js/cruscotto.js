// Cruscotto: legge i dati precalcolati da scripts/build_cruscotto.py (data/cruscotto.json)
document.addEventListener('DOMContentLoaded', () => {
    const PRIVATI = 'Privati';
    const ENTITY_CATEGORIES = ['Partecipate', 'Enti controllati e vigilati'];
    const RANKING_SIZE = 20;

    const periodSelect = document.getElementById('period-select');
    const privateOnly = document.getElementById('private-only');
    const coverageNotice = document.getElementById('coverage-notice');
    const categoriesBody = document.getElementById('categories-body');
    const rankingBody = document.getElementById('ranking-body');
    const rankingTitle = document.getElementById('ranking-title');
    const entitiesBody = document.getElementById('entities-body');

    const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
    const integer = new Intl.NumberFormat('it-IT');
    const percent = new Intl.NumberFormat('it-IT', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const formatDate = iso => iso.split('-').reverse().join('/');
    const escapeHtml = text => String(text).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    const exploreLink = name => `<a href="index.html?q=${encodeURIComponent(name)}">${escapeHtml(name)}</a>`;

    let data = null;

    function periodLabel(period) {
        if (period === 'tutti') return `Tutti gli anni (${data.anni[data.anni.length - 1]}–${data.anni[0]})`;
        // Anno parziale se l'ultimo mandato non è di dicembre (es. 2025: dati fino a settembre)
        const coverage = data.coperture[period];
        const partial = coverage && !coverage.a.startsWith(`${period}-12`);
        return partial ? `${period} (fino al ${formatDate(coverage.a)})` : period;
    }

    function render() {
        const period = periodSelect.value;
        const stats = data.periodi[period];
        const share = amount => stats.totale ? percent.format(amount / stats.totale) : '–';

        categoriesBody.innerHTML = data.categorie.map(cat => {
            const c = stats.categorie[cat];
            return `<tr><td>${escapeHtml(cat)}</td><td class="num">${euro.format(c.imp)}</td><td class="num">${share(c.imp)}</td><td class="num">${integer.format(c.n)}</td></tr>`;
        }).join('') + `<tr class="total-row"><td>Totale</td><td class="num">${euro.format(stats.totale)}</td><td class="num">100%</td><td class="num">${integer.format(stats.n)}</td></tr>`;

        const ranking = stats.beneficiari.filter(b => !privateOnly.checked || b.cat === PRIVATI).slice(0, RANKING_SIZE);
        rankingTitle.textContent = `Primi ${RANKING_SIZE} beneficiari${privateOnly.checked ? ' privati' : ''}`;
        rankingBody.closest('table').classList.toggle('private-only', privateOnly.checked); // colonna Categoria ridondante
        rankingBody.innerHTML = ranking.map((b, i) =>
            `<tr><td class="num">${i + 1}</td><td>${exploreLink(b.b)}</td><td><span class="category-tag">${escapeHtml(b.cat)}</span></td><td class="num">${euro.format(b.imp)}</td><td class="num">${share(b.imp)}</td><td class="num">${integer.format(b.n)}</td></tr>`
        ).join('');

        const entities = stats.beneficiari.filter(b => ENTITY_CATEGORIES.includes(b.cat));
        entitiesBody.innerHTML = entities.length ? entities.map(b =>
            `<tr><td>${exploreLink(b.b)}</td><td>${escapeHtml(b.cat)}</td><td class="num">${euro.format(b.imp)}</td><td class="num">${share(b.imp)}</td><td class="num">${integer.format(b.n)}</td><td>${b.nota ? escapeHtml(b.nota) : ''}</td></tr>`
        ).join('') : '<tr><td colspan="6">Nessun pagamento nel periodo.</td></tr>';
    }

    fetch('data/cruscotto.json')
        .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
        .then(json => {
            data = json;
            coverageNotice.innerHTML = `Dati per singolo mandato dal <strong>${formatDate(data.periodo.da)}</strong> al <strong>${formatDate(data.periodo.a)}</strong>. ` +
                'Dal IV trimestre 2025 il Comune pubblica solo dati aggregati (schema ANAC, delibera n. 495/2024), non inclusi.';
            periodSelect.innerHTML = ['tutti', ...data.anni].map(p => `<option value="${p}">${escapeHtml(periodLabel(p))}</option>`).join('');
            periodSelect.addEventListener('change', render);
            privateOnly.addEventListener('change', render);
            render();
        })
        .catch(error => {
            console.error('Errore caricamento cruscotto:', error);
            coverageNotice.textContent = `Errore nel caricamento dei dati del cruscotto (${error.message}).`;
        });
});
