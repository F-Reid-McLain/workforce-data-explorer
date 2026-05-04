// ── Color utilities, gradient, and per-series color UI ────

Object.assign(DataVisualizationApp.prototype, {

    hexToRgb(hex) {
        return {
            r: parseInt(hex.slice(1, 3), 16),
            g: parseInt(hex.slice(3, 5), 16),
            b: parseInt(hex.slice(5, 7), 16),
        };
    },

    hexToRgba(hex, alpha) {
        const { r, g, b } = this.hexToRgb(hex);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    },

    interpolateColors(startHex, endHex, count) {
        if (count <= 1) return [startHex];
        const s = this.hexToRgb(startHex);
        const e = this.hexToRgb(endHex);
        return Array.from({ length: count }, (_, i) => {
            const t = i / (count - 1);
            const r = Math.round(s.r + (e.r - s.r) * t);
            const g = Math.round(s.g + (e.g - s.g) * t);
            const b = Math.round(s.b + (e.b - s.b) * t);
            return `rgb(${r},${g},${b})`;
        });
    },

    applyOpacity(color, alpha) {
        if (alpha >= 1 || typeof color !== 'string') return color;
        if (color.startsWith('#')) {
            const { r, g, b } = this.hexToRgb(color);
            return `rgba(${r},${g},${b},${alpha})`;
        }
        if (color.startsWith('rgba(')) return color.replace(/,\s*[\d.]+\s*\)$/, `,${alpha})`);
        if (color.startsWith('rgb('))  return color.replace('rgb(', 'rgba(').replace(')', `,${alpha})`);
        return color;
    },

    getChartColors() {
        const scheme = document.getElementById('colorScheme').value;
        if (scheme === 'custom') {
            return [
                document.getElementById('primaryColor').value,
                document.getElementById('secondaryColor').value,
                document.getElementById('accentColor').value,
            ];
        }
        return this.colorSchemes[scheme] || this.colorSchemes.default;
    },

    updateGradientPreview() {
        const start = document.getElementById('gradientStart').value;
        const end   = document.getElementById('gradientEnd').value;
        document.getElementById('gradientPreview').style.background =
            `linear-gradient(to right, ${start}, ${end})`;
    },

    updatePerSeriesColors() {
        const container = document.getElementById('perSeriesColors');
        const selected  = this.getSelectedColumns();
        if (selected.length === 0) {
            container.innerHTML = '<span class="color-placeholder">Select columns to assign colors</span>';
            return;
        }
        container.innerHTML = '';
        const palette = this.colorSchemes.default;
        selected.forEach((col, i) => {
            if (!this.perSeriesColors[col]) this.perSeriesColors[col] = palette[i % palette.length];
            const item   = document.createElement('div');
            item.className = 'series-color-item';
            const swatch = document.createElement('input');
            swatch.type  = 'color';
            swatch.value = this.perSeriesColors[col];
            swatch.addEventListener('input', (e) => { this.perSeriesColors[col] = e.target.value; this.updateChart(); });
            const lbl    = document.createElement('span');
            lbl.textContent = col;
            item.appendChild(swatch);
            item.appendChild(lbl);
            container.appendChild(item);
        });
    },

});
