// ── Theme preset save / load / clear ─────────────────────

Object.assign(DataVisualizationApp.prototype, {

    collectThemeSettings() {
        const g = (id) => document.getElementById(id);
        return {
            colorMode:        this.colorMode,
            colorScheme:      g('colorScheme').value,
            primaryColor:     g('primaryColor').value,
            secondaryColor:   g('secondaryColor').value,
            accentColor:      g('accentColor').value,
            gradientStart:    g('gradientStart').value,
            gradientEnd:      g('gradientEnd').value,
            perSeriesColors:  { ...this.perSeriesColors },
            chartTitle:       g('chartTitle').value,
            showTitle:        g('showTitle').checked,
            titleFont:        g('titleFont').value,
            titleAlign:       g('titleAlign').value,
            titleSize:        g('titleSize').value,
            legendFont:       g('legendFont').value,
            legendPosition:   g('legendPosition').value,
            chartFontSize:    g('chartFontSize').value,
            textColor:        g('textColor').value,
            chartBg:          g('chartBg').value,
            aspectRatio:      g('aspectRatio').value,
            wordTextColor:    g('wordTextColor').value,
            numberTextColor:  g('numberTextColor').value,
            axisColor:        g('axisColor').value,
            showXAxis:        g('showXAxis').checked,
            showYAxis:        g('showYAxis').checked,
            axisLineWidth:    g('axisLineWidth').value,
            showBarBorder:    g('showBarBorder').checked,
            xAxisTitle:       g('xAxisTitle').value,
            yAxisTitle:       g('yAxisTitle').value,
            gridStyle:        g('gridStyle').value,
            gridColor:        g('gridColor').value,
            showLegend:       g('showLegend').checked,
            showGrid:         g('showGrid').checked,
            showCodes:        g('showCodes').checked,
            showNames:        g('showNames').checked,
            sortOrder:        g('sortOrder').value,
            numberFormat:     g('numberFormat').value,
            isStacked:        g('isStacked').checked,
            totalInTitle:     g('totalInTitle').checked,
            barSpacing:       g('barSpacing').value,
            barOpacity:       g('barOpacity').value,
            showBarLabels:    g('showBarLabels').checked,
            overlayBarLabels: g('overlayBarLabels').checked,
            lineThickness:    g('lineThickness').value,
            pointStyle:       g('pointStyle').value,
            pointSize:        g('pointSize').value,
            refLineEnabled:   g('refLineEnabled').checked,
            refLineValue:     g('refLineValue').value,
            refLineLabel:     g('refLineLabel').value,
            refLineColor:     g('refLineColor').value,
        };
    },

    applyThemeSettings(s, { noRender = false } = {}) {
        const set   = (id, v) => { const el = document.getElementById(id); if (el) el.value   = v; };
        const check = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };

        // Color mode
        const mode = s.colorMode || 'preset';
        document.querySelectorAll('.color-mode-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.color-panel').forEach(p => p.style.display = 'none');
        const modeBtn   = document.querySelector(`.color-mode-btn[data-mode="${mode}"]`);
        if (modeBtn) modeBtn.classList.add('active');
        this.colorMode  = mode;
        const modePanel = document.getElementById(`colorPanel-${mode}`);
        if (modePanel) modePanel.style.display = '';

        set('colorScheme',    s.colorScheme   || 'default');
        set('primaryColor',   s.primaryColor  || '#3498db');
        set('secondaryColor', s.secondaryColor || '#e74c3c');
        set('accentColor',    s.accentColor   || '#2ecc71');
        set('gradientStart',  s.gradientStart || '#6366f1');
        set('gradientEnd',    s.gradientEnd   || '#22d3ee');
        this.perSeriesColors = s.perSeriesColors || {};
        document.getElementById('customColorPanel').style.display =
            s.colorScheme === 'custom' ? '' : 'none';
        if (mode === 'perSeries') this.updatePerSeriesColors();

        set('chartTitle',     s.chartTitle    || '');
        check('showTitle',    s.showTitle     !== false);
        set('titleFont',      s.titleFont     || 'Inter, system-ui, sans-serif');
        set('titleAlign',     s.titleAlign    || 'center');
        set('titleSize',      s.titleSize     || '16');
        set('legendFont',     s.legendFont    || 'Inter, system-ui, sans-serif');
        set('legendPosition', s.legendPosition || 'top');
        set('chartFontSize',  s.chartFontSize || '12');
        set('textColor',      s.textColor     || '#374151');

        set('chartBg',        s.chartBg       || '#f7f6f3');
        set('aspectRatio',    s.aspectRatio   || '2');

        set('wordTextColor',   s.wordTextColor   || '#374151');
        set('numberTextColor', s.numberTextColor || '#374151');
        set('axisColor',       s.axisColor       || '#d1d5db');
        check('showXAxis',     s.showXAxis !== false);
        check('showYAxis',     s.showYAxis !== false);
        set('axisLineWidth',   s.axisLineWidth   || '1');
        check('showBarBorder', !!s.showBarBorder);
        set('xAxisTitle',      s.xAxisTitle      || '');
        set('yAxisTitle',      s.yAxisTitle      || '');

        set('gridStyle',      s.gridStyle      || 'solid');
        set('gridColor',      s.gridColor      || '#e4e4e7');
        check('showLegend',   s.showLegend !== false);
        check('showGrid',     s.showGrid   !== false);
        check('showCodes',    s.showCodes  !== false);
        check('showNames',    s.showNames  !== false);

        set('sortOrder',      s.sortOrder      || 'none');
        set('numberFormat',   s.numberFormat   || 'auto');
        check('isStacked',    !!s.isStacked);
        check('totalInTitle', !!s.totalInTitle);

        set('barSpacing',  s.barSpacing  || '80');
        document.getElementById('barSpacingValue').textContent = `${s.barSpacing || 80}%`;
        set('barOpacity',  s.barOpacity  || '100');
        document.getElementById('barOpacityValue').textContent = `${s.barOpacity || 100}%`;
        check('showBarLabels',    !!s.showBarLabels);
        check('overlayBarLabels', !!s.overlayBarLabels);

        set('lineThickness', s.lineThickness || '2');
        set('pointStyle',    s.pointStyle    || 'circle');
        set('pointSize',     s.pointSize     || '3');

        check('refLineEnabled', !!s.refLineEnabled);
        set('refLineValue',  s.refLineValue  || '0');
        set('refLineLabel',  s.refLineLabel  || '');
        set('refLineColor',  s.refLineColor  || '#ef4444');

        this.updateGradientPreview();
        if (!noRender) this.updateChart();
    },

    savePreset(slot) {
        const nameInput = document.getElementById(`preset-name-${slot}`);
        const name      = nameInput.value.trim() || `Preset ${slot + 1}`;
        nameInput.value = name;
        const data      = { name, settings: this.collectThemeSettings() };
        localStorage.setItem(`dvg_preset_${slot}`, JSON.stringify(data));
        this.updatePresetSlot(slot, data);
    },

    loadPreset(slot) {
        const raw = localStorage.getItem(`dvg_preset_${slot}`);
        if (!raw) return;
        const { settings } = JSON.parse(raw);
        this.applyThemeSettings(settings);
    },

    clearPreset(slot) {
        localStorage.removeItem(`dvg_preset_${slot}`);
        document.getElementById(`preset-name-${slot}`).value = '';
        this.updatePresetSlot(slot, null);
    },

    updatePresetSlot(slot, data) {
        const slotEl   = document.getElementById(`preset-slot-${slot}`);
        const loadBtn  = slotEl.querySelector('.preset-load-btn');
        const clearBtn = slotEl.querySelector('.preset-clear-btn');
        if (data) {
            slotEl.classList.add('has-data');
            loadBtn.style.display  = '';
            clearBtn.style.display = '';
        } else {
            slotEl.classList.remove('has-data');
            loadBtn.style.display  = 'none';
            clearBtn.style.display = 'none';
        }
    },

    initPresets() {
        for (let i = 0; i < 5; i++) {
            const raw = localStorage.getItem(`dvg_preset_${i}`);
            if (raw) {
                const data = JSON.parse(raw);
                document.getElementById(`preset-name-${i}`).value = data.name || `Preset ${i + 1}`;
                this.updatePresetSlot(i, data);
            }
        }
        document.querySelectorAll('.preset-save-btn').forEach(btn =>
            btn.addEventListener('click', () => this.savePreset(parseInt(btn.dataset.slot)))
        );
        document.querySelectorAll('.preset-load-btn').forEach(btn =>
            btn.addEventListener('click', () => this.loadPreset(parseInt(btn.dataset.slot)))
        );
        document.querySelectorAll('.preset-clear-btn').forEach(btn =>
            btn.addEventListener('click', () => this.clearPreset(parseInt(btn.dataset.slot)))
        );
    },

});
