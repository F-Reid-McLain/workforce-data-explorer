// ============================================
// Data Visualization Generator — App Shell
// Methods are added via Object.assign in:
//   js/data.js · js/colors.js · js/chart.js
//   js/presets.js · js/export.js
// ============================================

class DataVisualizationApp {
    constructor() {
        this.currentData  = null;
        this.currentChart = null;
        this.chartCanvas  = document.getElementById('myChart');
        this.chartCtx     = this.chartCanvas.getContext('2d');
        this.colorMode    = 'preset';
        this.perSeriesColors = {};

        this.colorSchemes = {
            default: ['#6366f1', '#22d3ee', '#f59e0b', '#34d399', '#f87171'],
            vibrant: ['#e879f9', '#38bdf8', '#fb923c', '#4ade80', '#fbbf24'],
            pastel:  ['#a5b4fc', '#93c5fd', '#86efac', '#fde68a', '#fca5a5'],
            muted:   ['#6b7280', '#8b8fa8', '#9ca3af', '#71717a', '#a1a1aa'],
        };

        this.naicsSectors = {
            '11': 'Agriculture, Forestry, Fishing & Hunting',
            '21': 'Mining, Quarrying & Oil and Gas Extraction',
            '22': 'Utilities',
            '23': 'Construction',
            '31': 'Manufacturing', '32': 'Manufacturing', '33': 'Manufacturing',
            '42': 'Wholesale Trade',
            '44': 'Retail Trade',  '45': 'Retail Trade',
            '48': 'Transportation & Warehousing', '49': 'Transportation & Warehousing',
            '51': 'Information',
            '52': 'Finance & Insurance',
            '53': 'Real Estate & Rental and Leasing',
            '54': 'Professional, Scientific & Technical Services',
            '55': 'Management of Companies & Enterprises',
            '56': 'Administrative & Support Services',
            '61': 'Educational Services',
            '62': 'Health Care & Social Assistance',
            '71': 'Arts, Entertainment & Recreation',
            '72': 'Accommodation & Food Services',
            '81': 'Other Services',
            '92': 'Public Administration',
        };

        this.socMajorGroups = {
            '11': 'Management',
            '13': 'Business & Financial Operations',
            '15': 'Computer & Mathematical',
            '17': 'Architecture & Engineering',
            '19': 'Life, Physical & Social Science',
            '21': 'Community & Social Service',
            '23': 'Legal',
            '25': 'Educational Instruction & Library',
            '27': 'Arts, Design, Entertainment & Media',
            '29': 'Healthcare Practitioners & Technical',
            '31': 'Healthcare Support',
            '33': 'Protective Service',
            '35': 'Food Preparation & Serving',
            '37': 'Building & Grounds Cleaning',
            '39': 'Personal Care & Service',
            '41': 'Sales & Related',
            '43': 'Office & Administrative Support',
            '45': 'Farming, Fishing & Forestry',
            '47': 'Construction & Extraction',
            '49': 'Installation, Maintenance & Repair',
            '51': 'Production',
            '53': 'Transportation & Material Moving',
            '55': 'Military Specific',
        };

        this.initEventListeners();
    }

    initEventListeners() {
        document.getElementById('dataSourceSelect').addEventListener('change', (e) => {
            this.loadData(e.target.value);
        });

        document.querySelectorAll('input[name="chartType"]').forEach(radio => {
            radio.addEventListener('change', () => this.updateChart());
        });

        // Footer tabs
        document.querySelectorAll('.footer-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.footer-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.footer-panel').forEach(p => p.style.display = 'none');
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).style.display = '';
            });
        });

        // Color mode buttons
        document.querySelectorAll('.color-mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.color-mode-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.color-panel').forEach(p => p.style.display = 'none');
                btn.classList.add('active');
                this.colorMode = btn.dataset.mode;
                document.getElementById(`colorPanel-${this.colorMode}`).style.display = '';
                if (this.colorMode === 'perSeries') this.updatePerSeriesColors();
                this.updateChart();
            });
        });

        // Preset color scheme
        document.getElementById('colorScheme').addEventListener('change', (e) => {
            document.getElementById('customColorPanel').style.display =
                e.target.value === 'custom' ? '' : 'none';
            this.updateChart();
        });
        document.getElementById('primaryColor').addEventListener('input',   () => this.updateChart());
        document.getElementById('secondaryColor').addEventListener('input', () => this.updateChart());
        document.getElementById('accentColor').addEventListener('input',    () => this.updateChart());

        // Gradient
        document.getElementById('gradientStart').addEventListener('input', () => {
            this.updateGradientPreview(); this.updateChart();
        });
        document.getElementById('gradientEnd').addEventListener('input', () => {
            this.updateGradientPreview(); this.updateChart();
        });

        // Typography
        document.getElementById('chartTitle').addEventListener('input',       () => this.updateChart());
        document.getElementById('showTitle').addEventListener('change',       () => this.updateChart());
        document.getElementById('titleFont').addEventListener('change',       () => this.updateChart());
        document.getElementById('titleAlign').addEventListener('change',      () => this.updateChart());
        document.getElementById('titleSize').addEventListener('change',       () => this.updateChart());
        document.getElementById('legendFont').addEventListener('change',      () => this.updateChart());
        document.getElementById('legendPosition').addEventListener('change',  () => this.updateChart());
        document.getElementById('chartFontSize').addEventListener('change',   () => this.updateChart());
        document.getElementById('textColor').addEventListener('input',        () => this.updateChart());

        // Canvas
        document.getElementById('chartBg').addEventListener('input',         () => this.updateChart());
        document.getElementById('aspectRatio').addEventListener('change',     () => this.updateChart());

        // Axes & Grid
        document.getElementById('wordTextColor').addEventListener('input',   () => this.updateChart());
        document.getElementById('numberTextColor').addEventListener('input', () => this.updateChart());
        document.getElementById('axisColor').addEventListener('input',       () => this.updateChart());
        document.getElementById('showXAxis').addEventListener('change',      () => this.updateChart());
        document.getElementById('showYAxis').addEventListener('change',      () => this.updateChart());
        document.getElementById('axisLineWidth').addEventListener('change',  () => this.updateChart());
        document.getElementById('showBarBorder').addEventListener('change',  () => this.updateChart());
        document.getElementById('xAxisTitle').addEventListener('input',      () => this.updateChart());
        document.getElementById('yAxisTitle').addEventListener('input',      () => this.updateChart());
        document.getElementById('gridStyle').addEventListener('change',      () => this.updateChart());
        document.getElementById('gridColor').addEventListener('input',       () => this.updateChart());
        document.getElementById('showLegend').addEventListener('change',     () => this.updateChart());
        document.getElementById('showGrid').addEventListener('change',       () => this.updateChart());
        document.getElementById('showCodes').addEventListener('change',      () => this.updateChart());
        document.getElementById('showNames').addEventListener('change',      () => this.updateChart());

        // Data
        document.getElementById('maxRows').addEventListener('change',        () => this.updateChart());
        document.getElementById('sortOrder').addEventListener('change',      () => this.updateChart());
        document.getElementById('numberFormat').addEventListener('change',   () => this.updateChart());
        document.getElementById('isStacked').addEventListener('change',      () => this.updateChart());
        document.getElementById('totalInTitle').addEventListener('change',   () => this.updateChart());

        // Bar style
        document.getElementById('barSpacing').addEventListener('input', (e) => {
            document.getElementById('barSpacingValue').textContent = `${e.target.value}%`;
            this.updateChart();
        });
        document.getElementById('barOpacity').addEventListener('input', (e) => {
            document.getElementById('barOpacityValue').textContent = `${e.target.value}%`;
            this.updateChart();
        });
        document.getElementById('showBarLabels').addEventListener('change',    () => this.updateChart());
        document.getElementById('overlayBarLabels').addEventListener('change', () => this.updateChart());

        // Line & scatter
        document.getElementById('lineThickness').addEventListener('change', () => this.updateChart());
        document.getElementById('pointStyle').addEventListener('change',    () => this.updateChart());
        document.getElementById('pointSize').addEventListener('change',     () => this.updateChart());

        // Reference line
        document.getElementById('refLineEnabled').addEventListener('change', () => this.updateChart());
        document.getElementById('refLineValue').addEventListener('change',   () => this.updateChart());
        document.getElementById('refLineLabel').addEventListener('input',    () => this.updateChart());
        document.getElementById('refLineColor').addEventListener('input',    () => this.updateChart());

        // Sidebar filters
        document.getElementById('codeFilter').addEventListener('change', () => this.updateChart());
        document.getElementById('codeLevel').addEventListener('change',  () => this.updateChart());

        // Export
        document.getElementById('downloadPNG').addEventListener('click', () => this.downloadChart('png'));
        document.getElementById('downloadSVG').addEventListener('click', () => this.downloadChart('svg'));
        document.getElementById('downloadPDF').addEventListener('click', () => this.downloadChart('pdf'));

        this.initPresets();
    }

    applyURLParams(params) {
        // Apply visual theme first so data params can override any conflicting defaults
        const themeStr = params.get('theme');
        if (themeStr) {
            try { this.applyThemeSettings(JSON.parse(themeStr), { noRender: true }); }
            catch (e) { console.warn('Bad theme param', e); }
        }

        const type = params.get('type');
        if (type) {
            const radio = document.querySelector(`input[name="chartType"][value="${type}"]`);
            if (radio) radio.checked = true;
        }

        const level = params.get('level');
        if (level) { const el = document.getElementById('codeLevel');  if (el) el.value = level; }

        const filter = params.get('filter');
        if (filter) { const el = document.getElementById('codeFilter'); if (el) el.value = filter; }

        const maxrows = params.get('maxrows');
        if (maxrows) document.getElementById('maxRows').value = maxrows;

        const sort = params.get('sort');
        if (sort) document.getElementById('sortOrder').value = sort;

        const numfmt = params.get('numfmt');
        if (numfmt) document.getElementById('numberFormat').value = numfmt;

        const title = params.get('title');
        if (title) {
            document.getElementById('chartTitle').value = title;
            document.getElementById('showTitle').checked = true;
        }

        const cols = params.get('cols');
        if (cols) {
            const wanted = cols.split(',');
            document.querySelectorAll('#columnSelection input[type="checkbox"]').forEach(cb => {
                cb.checked = wanted.includes(cb.dataset.column);
            });
        }

        window.history.replaceState({}, '', window.location.pathname);
        this.updateChart();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// ── Bootstrap ─────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    Chart.defaults.color       = '#52525b';
    Chart.defaults.borderColor = '#e4e4e7';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

    const app = new DataVisualizationApp();
    app.updateGradientPreview();

    const params = new URLSearchParams(window.location.search);
    const source = params.get('source');
    if (source) {
        const sel = document.getElementById('dataSourceSelect');
        if (sel) sel.value = source;
        app.loadData(source).then(() => app.applyURLParams(params));
    }
});
