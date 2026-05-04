// ── Data loading, CSV parsing, and aggregation ────────────

Object.assign(DataVisualizationApp.prototype, {

    async loadData(filename) {
        if (!filename) {
            document.getElementById('columnSelection').innerHTML = '<p class="placeholder">Select a data source first</p>';
            document.getElementById('codeLevelSection').style.display = 'none';
            document.getElementById('codeFilterSection').style.display = 'none';
            document.getElementById('codeFilter').innerHTML = '<option value="">All</option>';
            this.currentData = null;
            this.updateChart();
            return;
        }

        try {
            const response = await fetch(`Data/processed/${filename}`);
            if (!response.ok) throw new Error(`File not found: ${filename}`);
            const csv = await response.text();
            this.currentData = this.parseCSV(csv);
            this.populateCodeLevel();
            this.populateCodeFilter();
            this.populateColumnSelection();
            this.updateChart();
        } catch (error) {
            console.error('Error loading data:', error);
            document.getElementById('columnSelection').innerHTML = '<p class="placeholder">Error: Unable to load file</p>';
        }
    },

    parseCSV(csv) {
        const lines   = csv.trim().split('\n');
        const headers = this.parseCSVLine(lines[0]);
        const rows    = [];
        for (let i = 1; i < lines.length; i++) {
            if (!lines[i].trim()) continue;
            const fields = this.parseCSVLine(lines[i]);
            const obj    = {};
            for (let j = 0; j < headers.length; j++) obj[headers[j]] = fields[j] || '';
            rows.push(obj);
        }
        return { headers, rows };
    },

    parseCSVLine(line) {
        const result = [];
        let current  = '';
        let inQuotes = false;
        for (let i = 0; i < line.length; i++) {
            const ch   = line[i];
            const next = line[i + 1];
            if (ch === '"') {
                if (inQuotes && next === '"') { current += '"'; i++; }
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
    },

    populateCodeLevel() {
        const codeCol = this.currentData.headers[0];
        const isSOC   = codeCol.toUpperCase() === 'SOC';
        const select  = document.getElementById('codeLevel');
        select.innerHTML = '';
        const levels = isSOC
            ? [
                { value: '2', label: '2-digit — Major Group' },
                { value: '3', label: '3-digit — Minor Group' },
                { value: '4', label: '4-digit — Broad Occupation' },
                { value: '6', label: '6-digit — Detailed Occupation' },
              ]
            : [
                { value: '2', label: '2-digit — Sector' },
                { value: '3', label: '3-digit — Subsector' },
                { value: '4', label: '4-digit — Industry Group' },
                { value: '5', label: '5-digit — Industry' },
                { value: '6', label: '6-digit — National Industry' },
              ];
        levels.forEach(({ value, label }, i) => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = label;
            if (i === levels.length - 1) opt.selected = true;
            select.appendChild(opt);
        });
        document.getElementById('codeLevelSection').style.display = 'block';
    },

    getCodePrefix(code, level, isSOC) {
        if (isSOC) {
            const [major, minor = ''] = code.split('-');
            if (level === '2') return major;
            if (level === '3') return `${major}-${minor.slice(0, 1)}`;
            if (level === '4') return `${major}-${minor.slice(0, 2)}`;
            return code;
        }
        return code.slice(0, parseInt(level));
    },

    aggregateRows(rows, level, isSOC) {
        const codeCol   = this.currentData.headers[0];
        const nameCol   = this.currentData.headers[1];
        const numCols   = this.currentData.headers.slice(2);
        const nameMap   = isSOC ? this.socMajorGroups : this.naicsSectors;
        const emplCol   = numCols.find(h => /^empl$/i.test(h));
        // Columns whose values represent rates/averages — sum would be meaningless
        const isRateCol = h => /avg|mean|lq|rate|%/i.test(h);
        const isTotalRow = r => {
            const c = (r[codeCol] || '').trim();
            return c === '' || c === '00-0000';
        };
        const grouped = new Map();

        rows.filter(r => !isTotalRow(r)).forEach(row => {
            const prefix = this.getCodePrefix(row[codeCol] || '', level, isSOC);
            if (!grouped.has(prefix)) {
                const name = level === '2'
                    ? (nameMap[prefix] || row[nameCol] || prefix)
                    : (row[nameCol] || prefix);
                grouped.set(prefix, { [codeCol]: prefix, [nameCol]: name });
            }
            const agg    = grouped.get(prefix);
            const weight = emplCol ? (parseFloat(row[emplCol]) || 0) : 1;
            numCols.forEach(h => {
                const val = parseFloat(row[h]);
                if (isNaN(val)) return;
                // Rate/avg columns: track weighted numerator + denominator separately
                if (isRateCol(h) || !emplCol) {
                    agg[`_ws_${h}`] = (agg[`_ws_${h}`] || 0) + val * weight;
                    agg[`_wd_${h}`] = (agg[`_wd_${h}`] || 0) + weight;
                } else {
                    agg[h] = (agg[h] || 0) + val;
                }
            });
        });

        return [...grouped.values()].map(agg => {
            numCols.forEach(h => {
                const den = agg[`_wd_${h}`];
                if (den > 0) agg[h] = agg[`_ws_${h}`] / den;
                delete agg[`_ws_${h}`];
                delete agg[`_wd_${h}`];
            });
            return agg;
        });
    },

    populateCodeFilter() {
        const codeCol = this.currentData.headers[0];
        const isSOC   = codeCol.toUpperCase() === 'SOC';
        const counts  = new Map();
        this.currentData.rows.forEach(row => {
            const code   = row[codeCol] || '';
            if (code === '' || code === '00-0000') return;
            const prefix = isSOC ? code.split('-')[0] : code.slice(0, 2);
            if (prefix) counts.set(prefix, (counts.get(prefix) || 0) + 1);
        });
        const select  = document.getElementById('codeFilter');
        const nameMap = isSOC ? this.socMajorGroups : this.naicsSectors;
        document.getElementById('codeFilterLabel').textContent = isSOC ? 'Major Group' : 'Sector';
        select.innerHTML = '<option value="">All</option>';
        [...counts.entries()].sort().forEach(([prefix, count]) => {
            const opt = document.createElement('option');
            opt.value = prefix;
            opt.textContent = `${prefix} · ${nameMap[prefix] || 'Unknown'} (${count})`;
            select.appendChild(opt);
        });
        document.getElementById('codeFilterSection').style.display = 'block';
    },

    populateColumnSelection() {
        const container = document.getElementById('columnSelection');
        container.innerHTML = '';
        this.currentData.headers.forEach((header, index) => {
            if (index <= 1) return;
            const div      = document.createElement('div');
            div.className  = 'column-item';
            const checkbox = document.createElement('input');
            checkbox.type  = 'checkbox';
            checkbox.id    = `col_${index}`;
            checkbox.dataset.column = header;
            checkbox.checked = index <= 3;
            checkbox.addEventListener('change', () => {
                if (this.colorMode === 'perSeries') this.updatePerSeriesColors();
                this.updateChart();
            });
            const label       = document.createElement('label');
            label.htmlFor     = `col_${index}`;
            label.textContent = header;
            label.style.marginBottom = '0';
            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        });
    },

    getSelectedColumns() {
        const selected = [];
        document.querySelectorAll('#columnSelection input[type="checkbox"]:checked').forEach(cb => {
            selected.push(cb.dataset.column);
        });
        return selected;
    },

});
