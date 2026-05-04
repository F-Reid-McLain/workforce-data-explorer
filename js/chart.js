// ── Chart data preparation and rendering ──────────────────

Object.assign(DataVisualizationApp.prototype, {

    formatNumber(value, format) {
        if (value === null || value === undefined || value === '') return '';
        const num = typeof value === 'string' ? parseFloat(value) : value;
        if (isNaN(num)) return '';
        if (num === 0)  return '0';
        switch (format) {
            case 'raw':     return num.toLocaleString();
            case 'K':       return (num / 1000).toFixed(1) + 'K';
            case 'M':       return (num / 1000000).toFixed(1) + 'M';
            case 'percent': return num.toFixed(1) + '%';
            case 'dollar':  return '$' + num.toLocaleString();
            default: {
                const abs = Math.abs(num);
                if (abs >= 1000000) return (num / 1000000).toFixed(1) + 'M';
                if (abs >= 1000)    return (num / 1000).toFixed(1) + 'K';
                return Number.isInteger(num) ? num.toLocaleString() : num.toFixed(2);
            }
        }
    },

    getChartData() {
        if (!this.currentData) return null;
        const selectedColumns = this.getSelectedColumns();
        if (selectedColumns.length === 0) return null;

        const maxRows      = parseInt(document.getElementById('maxRows').value);
        const filterPrefix = document.getElementById('codeFilter').value;
        const levelSelect  = document.getElementById('codeLevel');
        const level        = levelSelect ? levelSelect.value : '6';
        const codeCol      = this.currentData.headers[0];
        const isSOC        = codeCol.toUpperCase() === 'SOC';

        // Detect the total row in raw data before aggregation
        const isTotalCode = (code) => code === '' || code === '00-0000';
        const totalRowRaw = this.currentData.rows.find(r => isTotalCode((r[codeCol] || '').trim()));

        let dataRows = this.aggregateRows(this.currentData.rows, level, isSOC);

        if (filterPrefix) {
            dataRows = dataRows.filter(row => {
                const code = row[codeCol] || '';
                return isSOC ? code.split('-')[0] === filterPrefix : code.startsWith(filterPrefix);
            });
        }

        const sortOrder = document.getElementById('sortOrder').value;
        if (sortOrder !== 'none' && selectedColumns.length > 0) {
            const sortCol = selectedColumns[0];
            dataRows.sort((a, b) => {
                const av = parseFloat(a[sortCol]) || 0;
                const bv = parseFloat(b[sortCol]) || 0;
                return sortOrder === 'asc' ? av - bv : bv - av;
            });
        }

        dataRows = dataRows.slice(0, maxRows);

        const showCodes = document.getElementById('showCodes').checked;
        const showNames = document.getElementById('showNames').checked;
        const labels    = dataRows.map(row => {
            const code = row[this.currentData.headers[0]];
            const name = row[this.currentData.headers[1]];
            if (showCodes && showNames) return name ? `${code} — ${name}` : code;
            if (showCodes) return code;
            if (showNames) return name || code;
            return code;
        });

        const gradStart  = document.getElementById('gradientStart').value;
        const gradEnd    = document.getElementById('gradientEnd').value;
        const gradColors = this.interpolateColors(gradStart, gradEnd, dataRows.length);

        const datasets = selectedColumns.map((column, index) => {
            let bg, border;
            if (this.colorMode === 'gradient') {
                bg = gradColors; border = gradColors;
            } else if (this.colorMode === 'perSeries') {
                const fallback = this.colorSchemes.default[index % this.colorSchemes.default.length];
                const c = this.perSeriesColors[column] || fallback;
                bg = c; border = c;
            } else {
                const palette = this.getChartColors();
                const c = palette[index % palette.length];
                bg = c; border = c;
            }
            return {
                label:           column,
                data:            dataRows.map(row => {
                    const raw = row[column];
                    if (raw === undefined || raw === null || raw === '') return 0;
                    if (typeof raw === 'string' && raw.toLowerCase() === 'n/a') return 0;
                    const val = parseFloat(raw);
                    return isNaN(val) ? 0 : val;
                }),
                backgroundColor: bg,
                borderColor:     border,
                borderWidth:     2,
                fill:            false,
                tension:         0.3,
            };
        });

        return { labels, datasets, totalRow: totalRowRaw || null };
    },

    updateChart() {
        const chartData      = this.getChartData();
        const noDataMsg      = document.getElementById('noDataMessage');
        const chartContainer = document.getElementById('chartContainer');

        if (!chartData || chartData.datasets.length === 0) {
            noDataMsg.classList.remove('hidden');
            chartContainer.classList.remove('active');
            return;
        }

        noDataMsg.classList.add('hidden');
        chartContainer.classList.add('active');

        // ── Read all display settings ──────────────────────────

        const chartTypeValue   = document.querySelector('input[name="chartType"]:checked').value;
        const title            = document.getElementById('chartTitle').value;
        const showTitle        = document.getElementById('showTitle').checked;
        const titleFont        = document.getElementById('titleFont').value;
        const titleAlign       = document.getElementById('titleAlign').value;
        const titleSize        = parseInt(document.getElementById('titleSize').value) || 16;
        const legendFont       = document.getElementById('legendFont').value;
        const legendPosition   = document.getElementById('legendPosition').value;
        const showLegend       = document.getElementById('showLegend').checked;
        const showGrid         = document.getElementById('showGrid').checked;
        const showBarLabels    = document.getElementById('showBarLabels').checked;
        const overlayBarLabels = document.getElementById('overlayBarLabels').checked;
        const chartFontSize    = parseInt(document.getElementById('chartFontSize').value) || 12;
        const textColor        = document.getElementById('textColor').value;
        const wordTextColor    = document.getElementById('wordTextColor').value;
        const numberTextColor  = document.getElementById('numberTextColor').value;
        const axisColor        = document.getElementById('axisColor').value;
        const showXAxis        = document.getElementById('showXAxis').checked;
        const showYAxis        = document.getElementById('showYAxis').checked;
        const axisLineWidth    = parseInt(document.getElementById('axisLineWidth').value) || 1;
        const barOpacity       = parseInt(document.getElementById('barOpacity').value) / 100;
        const showBarBorder    = document.getElementById('showBarBorder').checked;
        const barPercentage    = parseInt(document.getElementById('barSpacing').value) / 100;
        const chartBg          = document.getElementById('chartBg').value;
        const aspectRatioVal   = parseFloat(document.getElementById('aspectRatio').value) || 2;
        const xAxisTitle       = document.getElementById('xAxisTitle').value;
        const yAxisTitle       = document.getElementById('yAxisTitle').value;
        const gridStyle        = document.getElementById('gridStyle').value;
        const gridColor        = document.getElementById('gridColor').value;
        const isStacked        = document.getElementById('isStacked').checked;
        const numberFormat     = document.getElementById('numberFormat').value;
        const lineThickness    = parseInt(document.getElementById('lineThickness').value) || 2;
        const pointStyleVal    = document.getElementById('pointStyle').value;
        const pointSize        = parseInt(document.getElementById('pointSize').value) || 3;
        const refLineEnabled   = document.getElementById('refLineEnabled').checked;
        const refLineValue     = parseFloat(document.getElementById('refLineValue').value) || 0;
        const refLineLabel     = document.getElementById('refLineLabel').value;
        const refLineColor     = document.getElementById('refLineColor').value;
        const totalInTitle     = document.getElementById('totalInTitle').checked;

        // ── Build display title (may append total) ─────────────

        let displayTitle = title;
        if (totalInTitle && chartData.totalRow) {
            const selectedColumns = this.getSelectedColumns();
            const col = selectedColumns[0];
            const raw = col && chartData.totalRow[col];
            const num = parseFloat(raw);
            if (!isNaN(num)) {
                const formatted = this.formatNumber(num, numberFormat);
                displayTitle = displayTitle
                    ? `${displayTitle} — ${formatted} total`
                    : `${formatted} total`;
            }
        }

        // ── Resolve chart type ─────────────────────────────────

        let chartType    = chartTypeValue;
        let isHorizontal = false;
        if (chartTypeValue === 'horizontalBar') { chartType = 'bar'; isHorizontal = true; }

        // ── Apply dataset-level settings (chart-type-aware) ────

        if (chartType === 'bar') {
            chartData.datasets.forEach(d => {
                d.barPercentage      = barPercentage;
                d.categoryPercentage = 1.0;
                d.borderWidth        = showBarBorder ? axisLineWidth : 0;
                if (showBarBorder) d.borderColor = axisColor;
                if (barOpacity < 1) {
                    d.backgroundColor = Array.isArray(d.backgroundColor)
                        ? d.backgroundColor.map(c => this.applyOpacity(c, barOpacity))
                        : this.applyOpacity(d.backgroundColor, barOpacity);
                }
            });
        } else if (chartType === 'line' || chartType === 'scatter') {
            chartData.datasets.forEach(d => {
                d.borderWidth      = lineThickness;
                d.pointStyle       = pointStyleVal === 'false' ? false : pointStyleVal;
                d.pointRadius      = pointSize;
                d.pointHoverRadius = pointSize + 2;
            });
        } else if (chartType === 'pie' || chartType === 'doughnut') {
            chartData.datasets.forEach(d => {
                if (this.colorMode === 'gradient') {
                    const s = document.getElementById('gradientStart').value;
                    const e = document.getElementById('gradientEnd').value;
                    d.backgroundColor = this.interpolateColors(s, e, d.data.length);
                } else {
                    d.backgroundColor = this.getChartColors();
                }
                d.borderColor = '#ffffff';
                d.borderWidth = 2;
            });
        }

        // ── Chart area background ──────────────────────────────

        document.querySelector('.chart-area').style.background = chartBg;

        if (this.currentChart) this.currentChart.destroy();

        // ── Helpers ────────────────────────────────────────────

        const gridDash       = gridStyle === 'dashed' ? [6, 4] : gridStyle === 'dotted' ? [2, 4] : [];
        const numFmt         = (v) => this.formatNumber(v, numberFormat);
        const isBarChart     = chartType === 'bar';
        const useValueLabels = isBarChart && showBarLabels;
        const useOverlay     = isBarChart && isHorizontal && overlayBarLabels;
        const useDataLabels  = useValueLabels || useOverlay;

        Chart.defaults.color       = textColor;
        Chart.defaults.font.family = legendFont;
        Chart.defaults.font.size   = chartFontSize;

        // ── Background plugin ──────────────────────────────────

        const bgPlugin = {
            id: 'customBg',
            beforeDraw(chart) {
                const ctx = chart.canvas.getContext('2d');
                ctx.save();
                ctx.fillStyle = chartBg;
                ctx.fillRect(0, 0, chart.width, chart.height);
                ctx.restore();
            }
        };

        // ── Build config ───────────────────────────────────────

        const config = {
            type: chartType,
            data: chartData,
            options: {
                responsive:          true,
                maintainAspectRatio: true,
                aspectRatio:         aspectRatioVal,
                plugins: {
                    title: {
                        display: showTitle && !!displayTitle,
                        text:    displayTitle,
                        color:   textColor,
                        align:   titleAlign,
                        font:    { size: titleSize, weight: 'bold', family: titleFont }
                    },
                    legend: {
                        display:  showLegend,
                        position: legendPosition,
                        labels:   { color: textColor, font: { family: legendFont } }
                    },
                    datalabels: {
                        clip: false,
                        labels: {
                            value: {
                                display:   useValueLabels,
                                anchor:    'end',
                                align:     isHorizontal ? 'right' : 'top',
                                color:     textColor,
                                font:      { family: legendFont, size: 11, weight: '500' },
                                formatter: (v) => numFmt(v)
                            },
                            name: {
                                display:   useOverlay,
                                anchor:    'start',
                                align:     'right',
                                padding:   { left: 6 },
                                color:     'rgba(255,255,255,0.92)',
                                font:      { family: legendFont, size: 11, weight: '500' },
                                formatter: (_, ctx) => ctx.chart.data.labels[ctx.dataIndex]
                            }
                        }
                    }
                }
            }
        };

        // ── Reference line annotation ──────────────────────────

        if (refLineEnabled) {
            const annotCfg = {
                type:        'line',
                borderColor: refLineColor,
                borderWidth: 2,
                borderDash:  [6, 3],
                label: {
                    display:         !!refLineLabel,
                    content:         refLineLabel,
                    position:        'start',
                    backgroundColor: 'rgba(0,0,0,0.7)',
                    color:           '#ffffff',
                    font:            { family: legendFont, size: 11 }
                }
            };
            if (isHorizontal) { annotCfg.xMin = refLineValue; annotCfg.xMax = refLineValue; }
            else               { annotCfg.yMin = refLineValue; annotCfg.yMax = refLineValue; }
            config.options.plugins.annotation = { annotations: { refLine: annotCfg } };
        }

        // ── Scales (bar and line only) ─────────────────────────

        if (['bar', 'line'].includes(chartType)) {
            config.options.indexAxis = isHorizontal ? 'y' : 'x';
            config.options.scales = {
                y: {
                    beginAtZero: true,
                    display:     showYAxis,
                    stacked:     isStacked,
                    grid: {
                        display:    showGrid && !isHorizontal,
                        color:      gridColor,
                        borderDash: gridDash
                    },
                    border: { display: showYAxis, color: axisColor, width: axisLineWidth },
                    ticks: {
                        display: !useOverlay,
                        color:   isHorizontal ? wordTextColor : numberTextColor,
                        font:    { size: chartFontSize },
                        ...(isHorizontal ? {} : { callback: (v) => numFmt(v) })
                    }
                },
                x: {
                    display: showXAxis,
                    stacked: isStacked,
                    grid: {
                        display:    showGrid && isHorizontal,
                        color:      gridColor,
                        borderDash: gridDash
                    },
                    border: { display: showXAxis, color: axisColor, width: axisLineWidth },
                    ticks: {
                        color: isHorizontal ? numberTextColor : wordTextColor,
                        font:  { size: chartFontSize },
                        ...(isHorizontal ? { callback: (v) => numFmt(v) } : {})
                    }
                }
            };

            if (xAxisTitle) config.options.scales.x.title = {
                display: true, text: xAxisTitle,
                color: textColor, font: { family: legendFont, size: chartFontSize }
            };
            if (yAxisTitle) config.options.scales.y.title = {
                display: true, text: yAxisTitle,
                color: textColor, font: { family: legendFont, size: chartFontSize }
            };
        }

        // ── Render ─────────────────────────────────────────────

        const chartPlugins    = [bgPlugin, ...(useDataLabels ? [ChartDataLabels] : [])];
        this.currentChart     = new Chart(this.chartCtx, { ...config, plugins: chartPlugins });
    },

});
