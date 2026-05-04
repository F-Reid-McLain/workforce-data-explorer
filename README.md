# Data Visualization Generator

A web-based tool for creating custom, downloadable charts from talent market data. Built with Chart.js for client-side rendering with transparent backgrounds.

## Features

✨ **Data Selection**
- Choose from multiple data sources (Industry Snapshot, Occupation Snapshot, Occupation Wages)
- Select specific columns to visualize
- Filter by row count

📊 **Chart Types**
- Bar Charts
- Line Charts
- Pie Charts
- Doughnut Charts
- Scatter Charts

🎨 **Customization**
- Predefined color schemes (Default, Vibrant, Pastel, Muted)
- Custom color picker for full control
- Chart titles and labels
- Toggle legend and grid display

💾 **Export Options**
- PNG format (transparent background)
- SVG format (vector, scalable)
- PDF format (print-ready)

## Project Structure

```
Data Visualization Generator/
├── index.html                 # Main application
├── app.js                     # JavaScript application logic
├── styles.css                 # Application styling
├── process_data.py            # Python data processing script
├── Data/
│   ├── Industry Snapshot.xlsx      # Source data
│   ├── Occupation Snapshot.xlsx    # Source data
│   ├── Occupation Wages.xlsx       # Source data
│   └── processed/             # Generated CSV files (auto-created)
│       ├── Industry_Snapshot.csv
│       ├── Occupation_Snapshot.csv
│       └── Occupation_Wages.csv
├── Resources/                 # Reference examples
│   └── Talent-Demand-Study-2024_Book-FINAL.pdf
└── README.md                  # This file
```

## Data Processing

### Running the Python Script (Quarterly Update)

The application loads data from CSV files in the `Data/processed/` folder. When you update the source Excel files, run the Python script to regenerate the CSVs.

**Requirements:**
- Python 3.7+
- openpyxl package

**Installation:**
```bash
pip install openpyxl
```

**Usage:**
```bash
python3 process_data.py
```

This script will:
1. Read the Excel files from `Data/` folder
2. Remove header rows (first 2 rows from Industry Snapshot, Occupation Snapshot, and Occupation Wages)
3. Save cleaned CSV files to `Data/processed/`

## Using the Application

### For Local Development

1. Open `index.html` in a web browser
2. Select a data source from the dropdown
3. Choose columns to display
4. Select a chart type
5. Customize colors, title, and options
6. Download in your preferred format

### For GitHub Pages Deployment

1. Create a GitHub repository (e.g., `data-viz-generator`)
2. Push all files to the repo:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/data-viz-generator.git
   git branch -M main
   git push -u origin main
   ```

3. Enable GitHub Pages in repository settings:
   - Go to Settings → Pages
   - Set Source to "main" branch
   - Root directory default
   - Click Save

4. Your tool will be live at: `https://YOUR_USERNAME.github.io/data-viz-generator/`

## Features Breakdown

### Data Sources

**Industry Snapshot**
- NAICS code and industry name
- Employment figures
- Average annual wages
- Location quotient (LQ)
- Employment change metrics
- Total demand and job transitions
- Forecasted employment growth

**Occupation Snapshot**
- SOC code and occupation name
- Similar employment metrics
- Industry-specific data

**Occupation Wages**
- Occupation details
- Wage statistics across different percentiles
- Wage change data

### Color Schemes

- **Default (Blue)**: Professional blues with complementary colors
- **Vibrant**: Bold, saturated colors for high impact
- **Pastel**: Soft, muted pastel tones
- **Muted**: Sophisticated, understated color palette
- **Custom**: Pick your own colors with RGB color picker

### Export Settings

- **PNG**: Best for quick sharing and presentations
- **SVG**: Best for scaling and further editing
- **PDF**: Best for printing and formal documents

## Customization Tips

### For Marketing Team

- **Chart Titles**: Add descriptive titles that explain the data being visualized
- **Column Selection**: Start with 2-3 key metrics for clarity; too many columns = cluttered chart
- **Row Limiting**: Use "Max Rows to Display" to focus on top performers or trends
- **Color Consistency**: Use the same color scheme across related charts for brand consistency

### For Developers

To modify the application:

1. **Chart Types**: Edit the `chart-type-options` in `index.html`
2. **Colors**: Add new schemes to the `colorSchemes` object in `app.js`
3. **Data Processing**: Modify `process_data.py` to handle additional sheets or transformations
4. **Styling**: Customize CSS variables in `styles.css` for branding

## Troubleshooting

### "Data not loading"
- Ensure CSV files exist in `Data/processed/` folder
- Check browser console (F12) for error messages
- Verify column names match between HTML and CSV

### "Chart not displaying"
- Select at least one column for visualization
- Verify data source is selected
- Check that selected columns contain numeric data

### "Export not working"
- Some browsers may block downloads; check browser settings
- Ensure the chart is visible before exporting
- Try a different export format

## Browser Compatibility

- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- Mobile browsers: Responsive layout, but touch controls recommended for desktop app

## Dependencies

All major libraries are loaded from CDNs:
- **Chart.js 4.4.1**: Chart rendering
- **html2canvas 1.4.1**: Canvas-to-image conversion
- **jsPDF 0.10.1**: PDF generation

No local package installation required for frontend use.

## Future Enhancements

Potential additions:
- Real-time data updates
- More chart variations (waterfall, heatmap, bubble)
- Data filtering and search
- Chart templates
- Collaborative sharing
- Database integration for live data

## Contact & Support

Questions about the tool? Contact the development team or check the main documentation.

---

**Version:** 1.0  
**Last Updated:** April 2026
