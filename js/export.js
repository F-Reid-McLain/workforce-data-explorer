// ── Chart export (PNG / SVG / PDF) ────────────────────────

Object.assign(DataVisualizationApp.prototype, {

    async downloadChart(format) {
        if (!this.currentChart) { alert('Please generate a chart first'); return; }
        const title     = document.getElementById('chartTitle').value || 'chart';
        const timestamp = new Date().toISOString().slice(0, 10);
        const filename  = `${title.replace(/\s+/g, '_')}_${timestamp}`;
        try {
            if (format === 'png')      await this.downloadPNG(filename);
            else if (format === 'svg') this.downloadSVG(filename);
            else if (format === 'pdf') await this.downloadPDF(filename);
        } catch (err) {
            console.error('Download error:', err);
            alert('Error downloading chart. Please try again.');
        }
    },

    async downloadPNG(filename) {
        const link    = document.createElement('a');
        link.href     = this.chartCanvas.toDataURL('image/png');
        link.download = `${filename}.png`;
        link.click();
    },

    downloadSVG(filename) {
        const canvas  = this.chartCanvas;
        const svg     = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width',   canvas.width);
        svg.setAttribute('height',  canvas.height);
        svg.setAttribute('viewBox', `0 0 ${canvas.width} ${canvas.height}`);
        const image   = document.createElementNS('http://www.w3.org/2000/svg', 'image');
        image.setAttribute('width',  canvas.width);
        image.setAttribute('height', canvas.height);
        image.setAttribute('href',   canvas.toDataURL('image/png'));
        svg.appendChild(image);
        const blob    = new Blob([new XMLSerializer().serializeToString(svg)], { type: 'image/svg+xml' });
        const link    = document.createElement('a');
        link.href     = URL.createObjectURL(blob);
        link.download = `${filename}.svg`;
        link.click();
        URL.revokeObjectURL(link.href);
    },

    async downloadPDF(filename) {
        const canvas    = this.chartCanvas;
        const imgData   = canvas.toDataURL('image/png');
        const pdf       = new jspdf.jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
        const imgWidth  = 280;
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        pdf.addImage(imgData, 'PNG', 15, 15, imgWidth, imgHeight);
        pdf.save(`${filename}.pdf`);
    },

});
