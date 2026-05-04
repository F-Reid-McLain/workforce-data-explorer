// ============================================
// Gallery — pre-built example charts
// ============================================

const NAICS_NAMES = {
    '11': 'Agriculture',        '21': 'Mining & Oil/Gas',
    '22': 'Utilities',          '23': 'Construction',
    '31': 'Manufacturing',      '32': 'Manufacturing',      '33': 'Manufacturing',
    '42': 'Wholesale Trade',
    '44': 'Retail Trade',       '45': 'Retail Trade',
    '48': 'Transportation',     '49': 'Transportation',
    '51': 'Information',        '52': 'Finance & Insurance',
    '53': 'Real Estate',        '54': 'Professional Services',
    '55': 'Management',         '56': 'Admin Services',
    '61': 'Education',          '62': 'Health Care',
    '71': 'Arts & Recreation',  '72': 'Hospitality',
    '81': 'Other Services',     '92': 'Public Admin',
};

// Sectors that share the same 2-digit canonical code
const NAICS_MERGE = { '32': '31', '33': '31', '45': '44', '49': '48' };

// ── CSV parsing ───────────────────────────────────────────

function parseCSV(text) {
    const lines = text.trim().split('\n');
    const headers = parseCSVLine(lines[0]);
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        if (!lines[i].trim()) continue;
        const fields = parseCSVLine(lines[i]);
        const obj = {};
        headers.forEach((h, j) => { obj[h] = (fields[j] || '').trim(); });
        rows.push(obj);
    }
    return { headers, rows };
}

function parseCSVLine(line) {
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') {
            if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
            else inQuotes = !inQuotes;
        } else if (ch === ',' && !inQuotes) {
            result.push(current.trim());
            current = '';
        } else {
            current += ch;
        }
    }
    result.push(current.trim());
    return result;
}

// ── Data helpers ──────────────────────────────────────────

function toNum(v) {
    if (!v || (typeof v === 'string' && v.toLowerCase() === 'n/a')) return null;
    const n = parseFloat(v);
    return isNaN(n) ? null : n;
}

function topN(arr, col, n, dir = 'desc') {
    return [...arr]
        .filter(r => r[col] != null && r[col] > 0)
        .sort((a, b) => dir === 'desc' ? b[col] - a[col] : a[col] - b[col])
        .slice(0, n);
}

function aggregateNAICS(rows) {
    const map = new Map();
    rows.forEach(row => {
        const raw = (row['NAICS'] || '').toString().slice(0, 2);
        if (!raw) return;
        const code = NAICS_MERGE[raw] || raw;
        const name = NAICS_NAMES[code] || code;
        if (!map.has(code)) map.set(code, { code, name, Empl: 0, wageNum: 0, wageDen: 0 });
        const e = map.get(code);
        const empl  = toNum(row['Empl'])          || 0;
        const wages = toNum(row['Avg Ann Wages'])  || 0;
        e.Empl    += empl;
        e.wageNum += wages * empl;   // weighted sum
        e.wageDen += empl;
    });
    const result = [];
    map.forEach(e => {
        e.AvgWages = e.wageDen > 0 ? e.wageNum / e.wageDen : 0;
        result.push(e);
    });
    return result;
}

// ── Formatters ────────────────────────────────────────────

function fmtNum(n) {
    if (n == null) return '';
    const abs = Math.abs(n);
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return Math.round(n).toLocaleString();
}

function fmtDollar(n) {
    if (n == null) return '';
    const abs = Math.abs(n);
    if (abs >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return '$' + Math.round(n / 1e3) + 'K';
    return '$' + Math.round(n).toLocaleString();
}

function truncate(str, len) {
    return str && str.length > len ? str.slice(0, len - 1) + '…' : str;
}

// ── Color helpers ─────────────────────────────────────────

function hexToRgb(hex) {
    return {
        r: parseInt(hex.slice(1, 3), 16),
        g: parseInt(hex.slice(3, 5), 16),
        b: parseInt(hex.slice(5, 7), 16)
    };
}

function gradientPalette(startHex, endHex, count) {
    if (count <= 1) return [startHex];
    const s = hexToRgb(startHex), e = hexToRgb(endHex);
    return Array.from({ length: count }, (_, i) => {
        const t = i / (count - 1);
        return `rgb(${Math.round(s.r + (e.r - s.r) * t)},${Math.round(s.g + (e.g - s.g) * t)},${Math.round(s.b + (e.b - s.b) * t)})`;
    });
}

// ── Shared chart config ───────────────────────────────────

const C = {
    bg:       '#ffffff',
    text:     '#374151',
    muted:    '#6b7280',
    grid:     '#e5e7eb',
    axis:     '#d1d5db',
    font:     "'Inter', system-ui, sans-serif",
};

Chart.defaults.color       = C.text;
Chart.defaults.font.family = C.font;
Chart.defaults.font.size   = 11;

const bgPlugin = {
    id: 'galleryBg',
    beforeDraw(chart) {
        const ctx = chart.canvas.getContext('2d');
        ctx.save();
        ctx.fillStyle = C.bg;
        ctx.fillRect(0, 0, chart.width, chart.height);
        ctx.restore();
    }
};

function hBarBase(labels, data, colors, fmtFn, rightPad = 56) {
    return {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors,
                borderWidth: 0,
                barPercentage: 0.75,
                categoryPercentage: 1.0,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { right: rightPad, top: 4, bottom: 4 } },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ' ' + fmtFn(ctx.raw)
                    }
                },
                datalabels: {
                    anchor: 'end',
                    align: 'right',
                    clamp: false,
                    clip: false,
                    color: C.muted,
                    font: { size: 10, weight: '500', family: C.font },
                    formatter: fmtFn
                }
            },
            scales: {
                y: {
                    grid:   { display: false },
                    border: { display: false },
                    ticks:  { color: C.text, font: { size: 11, family: C.font } }
                },
                x: {
                    display: false,
                    grid:    { display: false },
                }
            }
        },
        plugins: [bgPlugin, ChartDataLabels]
    };
}

// ── Deep-link helper ──────────────────────────────────────

// Base visual theme shared by all gallery charts
const GALLERY_BASE_THEME = {
    chartBg:         '#ffffff',
    textColor:       '#374151',
    wordTextColor:   '#374151',
    numberTextColor: '#374151',
    axisColor:       '#d1d5db',
    gridColor:       '#e5e7eb',
    titleFont:       'Inter, system-ui, sans-serif',
    legendFont:      'Inter, system-ui, sans-serif',
    chartFontSize:   '11',
    showXAxis:       false,
    showYAxis:       true,
    showGrid:        true,
    showCodes:       false,
    showNames:       true,
    barOpacity:      '100',
    barSpacing:      '75',
    showBarLabels:   true,
    titleAlign:      'start',
    titleSize:       '15',
};

function setCustomizeLink(canvasId, config, theme) {
    const card = document.getElementById(canvasId).closest('.chart-card');
    const btn  = card && card.querySelector('.customize-btn');
    if (!btn) return;
    const full = { ...config, theme: JSON.stringify({ ...GALLERY_BASE_THEME, ...theme }) };
    btn.href = 'index.html?' + new URLSearchParams(full).toString();
}

function setCardTotal(canvasId, text) {
    if (!text) return;
    const card  = document.getElementById(canvasId).closest('.chart-card');
    const title = card && card.querySelector('.card-title');
    if (!title) return;
    const span = document.createElement('span');
    span.className   = 'card-total';
    span.textContent = text;
    title.appendChild(span);
}

// ── Chart 1: Biggest Employing Industries ─────────────────

function buildChart1(indRows) {
    const sectors  = aggregateNAICS(indRows);
    const top      = topN(sectors, 'Empl', 10);
    const colors   = gradientPalette('#6366f1', '#22d3ee', top.length);
    const totalRow = indRows.find(r => (r['NAICS'] || '').trim() === '');

    new Chart(
        document.getElementById('chart1'),
        hBarBase(
            top.map(r => r.name),
            top.map(r => r.Empl),
            colors,
            fmtNum
        )
    );

    if (totalRow) setCardTotal('chart1', fmtNum(toNum(totalRow['Empl'])) + ' total');

    setCustomizeLink('chart1', {
        source:  'Industry_Snapshot.csv',
        cols:    'Empl',
        type:    'horizontalBar',
        sort:    'desc',
        level:   '2',
        maxrows: '10',
        title:   'Biggest Employing Industries',
    }, {
        colorMode:    'gradient',
        gradientStart:'#6366f1',
        gradientEnd:  '#22d3ee',
        showLegend:   false,
        totalInTitle: true,
    });
}

// ── Chart 2: Most In-Demand Occupations ──────────────────

function buildChart2(occRows) {
    const totalRow = occRows.find(r => r['SOC'] === '00-0000');
    const rows     = occRows
        .filter(r => r['SOC'] !== '00-0000')
        .map(r => ({ name: truncate(r['Occupation'], 34), empl: toNum(r['Empl']) }))
        .filter(r => r.empl > 0)
        .sort((a, b) => b.empl - a.empl)
        .slice(0, 15);
    const colors = gradientPalette('#34d399', '#6366f1', rows.length);

    new Chart(
        document.getElementById('chart2'),
        hBarBase(
            rows.map(r => r.name),
            rows.map(r => r.empl),
            colors,
            fmtNum
        )
    );

    if (totalRow) setCardTotal('chart2', fmtNum(toNum(totalRow['Empl'])) + ' total');

    setCustomizeLink('chart2', {
        source:  'Occupation_Snapshot.csv',
        cols:    'Empl',
        type:    'horizontalBar',
        sort:    'desc',
        maxrows: '15',
        title:   'Most In-Demand Occupations',
    }, {
        colorMode:    'gradient',
        gradientStart:'#34d399',
        gradientEnd:  '#6366f1',
        showLegend:   false,
        totalInTitle: true,
    });
}

// ── Chart 3: Best-Paid Occupations ───────────────────────

function buildChart3(wageRows) {
    const totalRow = wageRows.find(r => r['SOC'] === '00-0000');
    const rows     = wageRows
        .filter(r => r['SOC'] !== '00-0000')
        .map(r => ({ name: truncate(r['Occupation'], 30), median: toNum(r['50% (Median)']) }))
        .filter(r => r.median > 0)
        .sort((a, b) => b.median - a.median)
        .slice(0, 12);
    const colors = gradientPalette('#f59e0b', '#ef4444', rows.length);

    new Chart(
        document.getElementById('chart3'),
        hBarBase(
            rows.map(r => r.name),
            rows.map(r => r.median),
            colors,
            fmtDollar,
            68
        )
    );

    if (totalRow) setCardTotal('chart3', fmtDollar(toNum(totalRow['50% (Median)'])) + ' overall median');

    setCustomizeLink('chart3', {
        source:  'Occupation_Wages.csv',
        cols:    '50% (Median)',
        type:    'horizontalBar',
        sort:    'desc',
        maxrows: '12',
        title:   'Best-Paid Occupations',
    }, {
        colorMode:    'gradient',
        gradientStart:'#f59e0b',
        gradientEnd:  '#ef4444',
        showLegend:   false,
        numberFormat: 'dollar',
        totalInTitle: true,
    });
}

// ── Chart 4: Wage Spread (10th vs 90th) ──────────────────

function buildChart4(wageRows) {
    const rows = wageRows
        .filter(r => r['SOC'] !== '00-0000')
        .map(r => ({
            name:   truncate(r['Occupation'], 26),
            p10:    toNum(r['10%']),
            p90:    toNum(r['90%']),
            median: toNum(r['50% (Median)'])
        }))
        .filter(r => r.p10 > 0 && r.p90 > 0 && r.median > 0)
        .sort((a, b) => b.median - a.median)
        .slice(0, 8);

    new Chart(document.getElementById('chart4'), {
        type: 'bar',
        data: {
            labels: rows.map(r => r.name),
            datasets: [
                {
                    label: '10th Percentile',
                    data:  rows.map(r => r.p10),
                    backgroundColor: 'rgba(99,102,241,0.55)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    barPercentage: 0.7,
                    categoryPercentage: 0.82
                },
                {
                    label: '90th Percentile',
                    data:  rows.map(r => r.p90),
                    backgroundColor: 'rgba(34,211,238,0.55)',
                    borderColor: '#22d3ee',
                    borderWidth: 1,
                    barPercentage: 0.7,
                    categoryPercentage: 0.82
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 8 } },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    align: 'end',
                    labels: { color: C.text, font: { size: 11, family: C.font }, boxWidth: 12, padding: 12 }
                },
                tooltip: {
                    callbacks: { label: ctx => ` ${ctx.dataset.label}: ${fmtDollar(ctx.raw)}` }
                },
                datalabels: { display: false }
            },
            scales: {
                x: {
                    grid:   { display: false },
                    border: { color: C.axis },
                    ticks:  { color: C.text, font: { size: 9, family: C.font }, maxRotation: 28 }
                },
                y: {
                    grid:   { color: C.grid },
                    border: { display: false },
                    ticks:  {
                        color: C.text,
                        font:  { size: 10, family: C.font },
                        callback: v => fmtDollar(v)
                    }
                }
            }
        },
        plugins: [bgPlugin]
    });

    setCustomizeLink('chart4', {
        source:  'Occupation_Wages.csv',
        cols:    '10%,90%',
        type:    'bar',
        sort:    'desc',
        maxrows: '8',
        title:   'The Wage Spread',
    }, {
        colorMode:   'preset',
        colorScheme: 'default',
        showLegend:  true,
        showXAxis:   true,
        showYAxis:   true,
        showBarLabels: false,
        numberFormat: 'dollar',
    });
}

// ── Chart 5: Highest-Paying Industries ───────────────────

function buildChart5(indRows) {
    const totalRow = indRows.find(r => (r['NAICS'] || '').trim() === '');
    const sectors  = aggregateNAICS(indRows);
    const top      = topN(sectors, 'AvgWages', 10);
    const colors   = gradientPalette('#f43f5e', '#f97316', top.length);

    new Chart(document.getElementById('chart5'), {
        type: 'bar',
        data: {
            labels: top.map(r => r.name),
            datasets: [{
                data: top.map(r => r.AvgWages),
                backgroundColor: colors,
                borderWidth: 0,
                barPercentage: 0.7,
                categoryPercentage: 0.85,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: { padding: { top: 28, left: 8, right: 8 } },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ' ' + fmtDollar(ctx.raw) } },
                datalabels: {
                    anchor: 'end',
                    align: 'top',
                    clip: false,
                    color: C.muted,
                    font: { size: 10, weight: '500', family: C.font },
                    formatter: fmtDollar
                }
            },
            scales: {
                x: {
                    grid:   { display: false },
                    border: { color: C.axis },
                    ticks:  { color: C.text, font: { size: 10, family: C.font }, maxRotation: 30 }
                },
                y: {
                    grid:   { color: C.grid },
                    border: { display: false },
                    ticks:  {
                        color: C.text,
                        font:  { size: 10, family: C.font },
                        callback: v => fmtDollar(v)
                    }
                }
            }
        },
        plugins: [bgPlugin, ChartDataLabels]
    });

    if (totalRow) setCardTotal('chart5', fmtDollar(toNum(totalRow['Avg Ann Wages'])) + ' overall avg');

    setCustomizeLink('chart5', {
        source:  'Industry_Snapshot.csv',
        cols:    'Avg Ann Wages',
        type:    'bar',
        sort:    'desc',
        level:   '2',
        maxrows: '10',
        title:   'Highest-Paying Industries',
    }, {
        colorMode:    'gradient',
        gradientStart:'#f43f5e',
        gradientEnd:  '#f97316',
        showLegend:   false,
        showXAxis:    true,
        showYAxis:    true,
        showBarLabels: true,
        numberFormat: 'dollar',
        totalInTitle: true,
    });
}

// ── Chart 6: Employment Share by Sector ──────────────────

function buildChart6(indRows) {
    const totalRow = indRows.find(r => (r['NAICS'] || '').trim() === '');
    const sectors  = aggregateNAICS(indRows);
    const top      = topN(sectors, 'Empl', 10);
    const total    = top.reduce((s, r) => s + r.Empl, 0);

    const palette = [
        '#6366f1','#22d3ee','#f59e0b','#34d399','#f87171',
        '#e879f9','#38bdf8','#fb923c','#4ade80','#a78bfa'
    ];

    new Chart(document.getElementById('chart6'), {
        type: 'doughnut',
        data: {
            labels: top.map(r => r.name),
            datasets: [{
                data: top.map(r => r.Empl),
                backgroundColor: palette,
                borderColor: '#ffffff',
                borderWidth: 3,
                hoverBorderWidth: 3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '55%',
            layout: { padding: 8 },
            plugins: {
                legend: {
                    display: true,
                    position: 'right',
                    labels: {
                        color: C.text,
                        font: { size: 10.5, family: C.font },
                        boxWidth: 11,
                        padding: 10,
                        generateLabels(chart) {
                            const data = chart.data;
                            return data.labels.map((label, i) => {
                                const val = data.datasets[0].data[i];
                                const pct = ((val / total) * 100).toFixed(1);
                                return {
                                    text: `${label}  ${pct}%`,
                                    fillStyle: palette[i],
                                    strokeStyle: palette[i],
                                    lineWidth: 0,
                                    hidden: false,
                                    index: i
                                };
                            });
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const pct = ((ctx.raw / total) * 100).toFixed(1);
                            return `  ${fmtNum(ctx.raw)} jobs  (${pct}%)`;
                        }
                    }
                },
                datalabels: {
                    display: ctx => {
                        const pct = ctx.dataset.data[ctx.dataIndex] / total * 100;
                        return pct >= 6;
                    },
                    formatter: (v) => ((v / total) * 100).toFixed(0) + '%',
                    color: '#fff',
                    font: { size: 11, weight: '700', family: C.font }
                }
            }
        },
        plugins: [bgPlugin, ChartDataLabels]
    });

    if (totalRow) setCardTotal('chart6', fmtNum(toNum(totalRow['Empl'])) + ' total');

    setCustomizeLink('chart6', {
        source:  'Industry_Snapshot.csv',
        cols:    'Empl',
        type:    'doughnut',
        level:   '2',
        maxrows: '10',
        title:   'Employment Share by Sector',
    }, {
        colorMode:   'preset',
        colorScheme: 'vibrant',
        showLegend:  true,
        legendPosition: 'right',
        showBarLabels: false,
        totalInTitle:  true,
    });
}

// ── Init ──────────────────────────────────────────────────

async function init() {
    try {
        const [indText, occText, wageText] = await Promise.all([
            fetch('Data/processed/Industry_Snapshot.csv').then(r => { if (!r.ok) throw new Error(r.status); return r.text(); }),
            fetch('Data/processed/Occupation_Snapshot.csv').then(r => { if (!r.ok) throw new Error(r.status); return r.text(); }),
            fetch('Data/processed/Occupation_Wages.csv').then(r => { if (!r.ok) throw new Error(r.status); return r.text(); }),
        ]);

        const ind   = parseCSV(indText);
        const occ   = parseCSV(occText);
        const wages = parseCSV(wageText);

        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('gallery').style.display = '';

        buildChart1(ind.rows);
        buildChart2(occ.rows);
        buildChart3(wages.rows);
        buildChart4(wages.rows);
        buildChart5(ind.rows);
        buildChart6(ind.rows);

    } catch (err) {
        const el = document.getElementById('loadingState');
        el.querySelector('.spinner').style.display = 'none';
        el.querySelector('span').textContent =
            'Could not load data. Open via a local server: python3 -m http.server 8080';
        console.error(err);
    }
}

document.addEventListener('DOMContentLoaded', init);
