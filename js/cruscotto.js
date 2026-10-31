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
    const categoriesTitle = document.getElementById('categories-title');
    const entitiesTitle = document.getElementById('entities-title');
    const entitiesBody = document.getElementById('entities-body');
    const yearChart = document.getElementById('year-chart');
    const yearTooltip = document.getElementById('year-tooltip');
    const yearLegend = document.getElementById('year-legend');
    const yearChartNote = document.getElementById('year-chart-note');
    const yearTableHead = document.getElementById('year-table-head');
    const yearTableBody = document.getElementById('year-table-body');

    // Colori fissi per categoria (stesso ordine di data.categorie), validati per daltonismo
    const CATEGORY_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
    const SVG_NS = 'http://www.w3.org/2000/svg';

    const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
    const integer = new Intl.NumberFormat('it-IT');
    const percent = new Intl.NumberFormat('it-IT', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const millions = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    const formatMillions = amount => `${millions.format(amount / 1e6)} mln €`;
    const formatDate = iso => iso.split('-').reverse().join('/');
    const escapeHtml = text => String(text).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    const exploreLink = name => `<a href="pagamenti.html?q=${encodeURIComponent(name)}">${escapeHtml(name)}</a>`;

    let data = null;

    function periodLabel(period) {
        if (period === 'tutti') return `Tutti gli anni (${data.anni[data.anni.length - 1]}–${data.anni[0]})`;
        // Anno parziale se l'ultimo mandato non è di dicembre (es. 2025: dati fino a settembre)
        return isPartialYear(period) ? `${period} (fino al ${formatDate(data.coperture[period].a)})` : period;
    }

    function isPartialYear(year) {
        const coverage = data.coperture[year];
        return Boolean(coverage) && !coverage.a.startsWith(`${year}-12`);
    }

    function svgElement(tag, attributes) {
        const element = document.createElementNS(SVG_NS, tag);
        for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
        return element;
    }

    // Rettangolo con i soli angoli superiori arrotondati (estremità del dato)
    function topRoundedBar(x, yTop, width, height, radius) {
        const r = Math.min(radius, height, width / 2);
        const yBottom = yTop + height;
        return `M${x},${yBottom}V${yTop + r}A${r},${r} 0 0 1 ${x + r},${yTop}H${x + width - r}A${r},${r} 0 0 1 ${x + width},${yTop + r}V${yBottom}Z`;
    }

    function niceStep(rawStep) {
        const magnitude = 10 ** Math.floor(Math.log10(rawStep));
        return [1, 2, 2.5, 5, 10].map(m => m * magnitude).find(step => step >= rawStep);
    }

    function renderYearLegendAndTable() {
        yearLegend.innerHTML = data.categorie.map((cat, i) =>
            `<li><span class="chart-swatch" style="background:${CATEGORY_COLORS[i]}"></span>${escapeHtml(cat)}</li>`
        ).join('');
        const partialYears = data.anni.filter(isPartialYear);
        if (partialYears.length) {
            yearChartNote.textContent = partialYears.map(y => `* ${y}: anno parziale, dati fino al ${formatDate(data.coperture[y].a)}.`).join(' ') +
                ' Clic su un anno per selezionarlo nel cruscotto.';
        }
        yearTableHead.innerHTML = `<tr><th>Anno</th>${data.categorie.map(cat => `<th class="num">${escapeHtml(cat)}</th>`).join('')}<th class="num">Totale</th></tr>`;
        yearTableBody.innerHTML = data.anni.map(year => {
            const stats = data.periodi[year];
            return `<tr><td>${escapeHtml(periodLabel(year))}</td>${data.categorie.map(cat => `<td class="num">${euro.format(stats.categorie[cat].imp)}</td>`).join('')}<td class="num">${euro.format(stats.totale)}</td></tr>`;
        }).join('');
    }

    function showYearTooltip(year, column) {
        const stats = data.periodi[year];
        yearTooltip.replaceChildren();
        const title = document.createElement('div');
        title.className = 'tt-title';
        title.textContent = periodLabel(year);
        yearTooltip.append(title);
        // Dall'alto in basso, come la pila del grafico
        [...data.categorie].reverse().forEach(cat => {
            const amount = stats.categorie[cat].imp;
            const row = document.createElement('div');
            row.className = 'tt-row';
            const swatch = document.createElement('span');
            swatch.className = 'chart-swatch';
            swatch.style.background = CATEGORY_COLORS[data.categorie.indexOf(cat)];
            const value = document.createElement('span');
            value.className = 'tt-value';
            value.textContent = formatMillions(amount);
            const label = document.createElement('span');
            label.textContent = `${cat} (${stats.totale ? percent.format(amount / stats.totale) : '–'})`;
            row.append(swatch, value, label);
            yearTooltip.append(row);
        });
        const total = document.createElement('div');
        total.className = 'tt-row tt-total';
        const totalValue = document.createElement('span');
        totalValue.className = 'tt-value';
        totalValue.textContent = formatMillions(stats.totale);
        const totalLabel = document.createElement('span');
        totalLabel.textContent = `Totale, ${integer.format(stats.n)} pagamenti`;
        total.append(totalValue, totalLabel);
        yearTooltip.append(total);

        yearTooltip.hidden = false;
        const chartWidth = yearChart.clientWidth;
        const columnBox = column.getBBox();
        const tooltipWidth = yearTooltip.offsetWidth;
        // A destra della colonna, o a sinistra se non c'è spazio
        let left = columnBox.x + columnBox.width + 4;
        if (left + tooltipWidth > chartWidth) left = columnBox.x - tooltipWidth - 4;
        yearTooltip.style.left = `${Math.max(0, left)}px`;
        yearTooltip.style.top = '8px';
    }

    function renderYearChart() {
        const years = [...data.anni].reverse();
        const width = yearChart.clientWidth;
        const height = 280;
        const margin = { top: 10, right: 4, bottom: 28, left: 62 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        const maxTotal = Math.max(...years.map(year => data.periodi[year].totale));
        const step = niceStep(maxTotal / 5);
        const yMax = Math.ceil(maxTotal / step) * step;
        const yScale = amount => margin.top + plotHeight - (amount / yMax) * plotHeight;
        const band = plotWidth / years.length;
        const barWidth = Math.min(24, band * 0.6);
        const selected = periodSelect.value;

        const svg = svgElement('svg', { width, height, role: 'img',
            'aria-label': `Spesa per anno e categoria, ${years[0]}–${years[years.length - 1]}. I valori sono nella tabella sotto il grafico.` });

        for (let tick = 0; tick <= yMax + step / 2; tick += step) {
            const y = Math.round(yScale(tick)) + 0.5;
            svg.append(svgElement('line', { x1: margin.left, x2: width - margin.right, y1: y, y2: y,
                stroke: tick === 0 ? '#c3c2b7' : '#e1e0d9', 'stroke-width': 1 }));
            const label = svgElement('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', fill: '#52514e', 'font-size': 12 });
            label.textContent = `${integer.format(tick / 1e6)} mln €`;
            svg.append(label);
        }

        years.forEach((year, i) => {
            const stats = data.periodi[year];
            const center = margin.left + band * (i + 0.5);
            const x = center - barWidth / 2;
            const dimmed = selected !== 'tutti' && selected !== year;
            const column = svgElement('g', { class: 'chart-col', tabindex: 0,
                'aria-label': `${periodLabel(year)}: ${formatMillions(stats.totale)}` });
            column.append(svgElement('rect', { class: 'chart-hit', x: center - band / 2 + 1, y: margin.top, width: band - 2, height: plotHeight, rx: 4 }));

            // Pila dal basso; 2px di spazio tra i segmenti, angoli arrotondati solo in cima
            const segments = data.categorie.map((cat, c) => ({ amount: stats.categorie[cat].imp, color: CATEGORY_COLORS[c] }));
            const topIndex = segments.map(s => s.amount > 0).lastIndexOf(true);
            const bars = svgElement('g', { opacity: dimmed ? 0.35 : 1 });
            let base = 0;
            segments.forEach((segment, c) => {
                if (segment.amount <= 0) return;
                const yTop = yScale(base + segment.amount);
                const yBottom = yScale(base) - (base > 0 ? 2 : 0);
                base += segment.amount;
                const segmentHeight = yBottom - yTop;
                if (segmentHeight < 0.5) return; // invisibile a questa scala: resta nel tooltip e in tabella
                bars.append(c === topIndex
                    ? svgElement('path', { d: topRoundedBar(x, yTop, barWidth, segmentHeight, 4), fill: segment.color })
                    : svgElement('rect', { x, y: yTop, width: barWidth, height: segmentHeight, fill: segment.color }));
            });

            column.append(bars);
            const label = svgElement('text', { x: center, y: height - 8, 'text-anchor': 'middle', fill: '#52514e', 'font-size': 12,
                'font-weight': selected === year ? 700 : 400 });
            label.textContent = isPartialYear(year) ? `${year}*` : year;
            column.append(label);

            column.addEventListener('mouseenter', () => showYearTooltip(year, column));
            column.addEventListener('focus', () => showYearTooltip(year, column));
            column.addEventListener('mouseleave', () => { yearTooltip.hidden = true; });
            column.addEventListener('blur', () => { yearTooltip.hidden = true; });
            const selectYear = () => {
                periodSelect.value = periodSelect.value === year ? 'tutti' : year;
                render();
            };
            column.addEventListener('click', selectYear);
            column.addEventListener('keydown', event => {
                if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectYear(); }
            });
            svg.append(column);
        });

        yearChart.querySelector('svg')?.remove();
        yearChart.prepend(svg);
    }

    function render() {
        const period = periodSelect.value;
        renderYearChart();
        const stats = data.periodi[period];
        const share = amount => stats.totale ? percent.format(amount / stats.totale) : '–';

        categoriesBody.innerHTML = data.categorie.map(cat => {
            const c = stats.categorie[cat];
            return `<tr><td>${escapeHtml(cat)}</td><td class="num">${euro.format(c.imp)}</td><td class="num">${share(c.imp)}</td><td class="num">${integer.format(c.n)}</td></tr>`;
        }).join('') + `<tr class="total-row"><td>Totale</td><td class="num">${euro.format(stats.totale)}</td><td class="num">100%</td><td class="num">${integer.format(stats.n)}</td></tr>`;

        const ranking = stats.beneficiari.filter(b => !privateOnly.checked || b.cat === PRIVATI).slice(0, RANKING_SIZE);
        // Il periodo nel titolo: le tabelle cambiano con il menu Periodo e con il clic sul grafico
        const periodSuffix = ` · ${periodLabel(period)}`;
        categoriesTitle.textContent = `Ripartizione per categoria${periodSuffix}`;
        rankingTitle.textContent = `Primi ${RANKING_SIZE} beneficiari${privateOnly.checked ? ' privati' : ''}${periodSuffix}`;
        entitiesTitle.textContent = `Società partecipate ed enti controllati${periodSuffix}`;
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
            coverageNotice.innerHTML = `Dati per singolo pagamento dal <strong>${formatDate(data.periodo.da)}</strong> al <strong>${formatDate(data.periodo.a)}</strong>. ` +
                'Dal IV trimestre 2025 il Comune pubblica solo dati aggregati (schema ANAC, delibera n. 495/2024), non inclusi.';
            periodSelect.innerHTML = ['tutti', ...data.anni].map(p => `<option value="${p}">${escapeHtml(periodLabel(p))}</option>`).join('');
            periodSelect.addEventListener('change', render);
            privateOnly.addEventListener('change', render);
            renderYearLegendAndTable();
            render();
            let resizeFrame = null;
            window.addEventListener('resize', () => {
                cancelAnimationFrame(resizeFrame);
                resizeFrame = requestAnimationFrame(renderYearChart);
            });
        })
        .catch(error => {
            console.error('Errore caricamento cruscotto:', error);
            coverageNotice.textContent = `Errore nel caricamento dei dati del cruscotto (${error.message}).`;
        });
});
