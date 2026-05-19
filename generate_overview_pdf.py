#!/usr/bin/env python3
"""
Generate the Macon-Bibb County Economic Overview PDF.

Usage:
  python3 generate_overview_pdf.py

Output: reports/pdf/macon-overview.pdf

Setup (one-time):
  pip install playwright
  playwright install chromium
"""

import asyncio
import base64
import csv
import json
import sys
import tempfile
from pathlib import Path

# ── Short industry names ───────────────────────────────────────────────────

INDUSTRIES = {
    '11': {'name': 'Agriculture & Forestry',            'prefixes': ['11'],           'color': '#86efac'},
    '21': {'name': 'Mining & Oil/Gas',                  'prefixes': ['21'],           'color': '#fcd34d'},
    '22': {'name': 'Utilities',                         'prefixes': ['22'],           'color': '#67e8f9'},
    '23': {'name': 'Construction',                      'prefixes': ['23'],           'color': '#fdba74'},
    '31': {'name': 'Manufacturing',                     'prefixes': ['31','32','33'], 'color': '#93c5fd'},
    '42': {'name': 'Wholesale Trade',                   'prefixes': ['42'],           'color': '#5eead4'},
    '44': {'name': 'Retail Trade',                      'prefixes': ['44','45'],      'color': '#f9a8d4'},
    '48': {'name': 'Transportation & Warehousing',      'prefixes': ['48','49'],      'color': '#fca5a5'},
    '51': {'name': 'Information',                       'prefixes': ['51'],           'color': '#c4b5fd'},
    '52': {'name': 'Finance & Insurance',               'prefixes': ['52'],           'color': '#7dd3fc'},
    '53': {'name': 'Real Estate',                       'prefixes': ['53'],           'color': '#6ee7b7'},
    '54': {'name': 'Professional & Tech Services',      'prefixes': ['54'],           'color': '#a5b4fc'},
    '55': {'name': 'Management of Companies',           'prefixes': ['55'],           'color': '#94a3b8'},
    '56': {'name': 'Administrative & Support',          'prefixes': ['56'],           'color': '#fde68a'},
    '61': {'name': 'Educational Services',              'prefixes': ['61'],           'color': '#bef264'},
    '62': {'name': 'Health Care & Social Assistance',   'prefixes': ['62'],           'color': '#34d399'},
    '71': {'name': 'Arts & Entertainment',              'prefixes': ['71'],           'color': '#f9a8d4'},
    '72': {'name': 'Accommodation & Food Services',     'prefixes': ['72'],           'color': '#fb923c'},
    '81': {'name': 'Other Services',                    'prefixes': ['81'],           'color': '#a1a1aa'},
    '92': {'name': 'Public Administration',             'prefixes': ['92'],           'color': '#818cf8'},
}

# ── Helpers ────────────────────────────────────────────────────────────────

def to_num(v):
    try:
        return float(str(v or '').replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0

def fmt_num(n):
    if n >= 1_000_000: return f'{n/1_000_000:.1f}M'
    if n >= 1_000:     return f'{n/1_000:.1f}K'
    return f'{round(n):,}'

def fmt_dollar(n):
    if n >= 1_000: return f'${round(n/1_000)}K'
    return f'${round(n):,}'

def load_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def image_data_uri(path, mime='image/webp'):
    data = base64.b64encode(Path(path).read_bytes()).decode('ascii')
    return f'data:{mime};base64,{data}'

# ── Data processing ────────────────────────────────────────────────────────

def process(ind_rows, occ_rows, pop_rows, comm_rows):
    data_rows = [r for r in ind_rows if (r.get('NAICS') or '').strip()]

    # Total employment and wage from the summary row
    total_row = next((r for r in ind_rows if not (r.get('NAICS') or '').strip()), {})
    total_jobs = round(to_num(total_row.get('Empl', 0)))
    avg_wage   = round(to_num(total_row.get('Avg Ann Wages', 0)))

    # Industry employment totals
    industry_totals = {}
    for r in data_rows:
        naics = (r.get('NAICS') or '').strip()
        empl  = to_num(r.get('Empl', 0))
        for iid, cfg in INDUSTRIES.items():
            if any(naics.startswith(p) for p in cfg['prefixes']):
                industry_totals[iid] = industry_totals.get(iid, 0) + empl
                break

    industries_sorted = sorted(
        [{'id': iid, 'name': INDUSTRIES[iid]['name'], 'empl': round(v), 'color': INDUSTRIES[iid]['color']}
         for iid, v in industry_totals.items() if v > 0],
        key=lambda x: -x['empl']
    )

    # Top industry name
    top_industry = industries_sorted[0]['name'] if industries_sorted else '—'

    # Population and commuting (Bibb = FIPS 13021)
    bibb_pop  = next((to_num(r.get('Population', 0)) for r in pop_rows
                      if str(r.get('FIPS','')).zfill(5) == '13021'), 0)
    bibb_comm = next((to_num(r.get('NetCommuting', 0)) for r in comm_rows
                      if str(r.get('FIPS','')).zfill(5) == '13021'), 0)

    # Surrounding counties sorted by workers sent to Macon
    surrounding = sorted(
        [{'name': r['Region'].replace(', Georgia',''), 'pop': round(to_num(r.get('Population',0))),
          'comm': abs(round(to_num(r.get('NetCommuting',0))))}
         for r in comm_rows
         if str(r.get('FIPS','')).zfill(5) != '13021' and to_num(r.get('NetCommuting',0)) != 0],
        key=lambda x: -x['comm']
    )

    # Top occupations
    top_occ = sorted(
        [r for r in occ_rows if to_num(r.get('Empl', 0)) > 0],
        key=lambda r: -to_num(r.get('Empl', 0))
    )[:15]

    # Per-county data for map embed
    comm_map_data = [
        {'fips': str(r.get('FIPS','')).zfill(5),
         'name': r.get('Region','').replace(', Georgia','').replace(' County',''),
         'comm': round(to_num(r.get('NetCommuting',0)))}
        for r in comm_rows
    ]
    pop_map_data = [
        {'fips': str(r.get('FIPS','')).zfill(5),
         'pop': round(to_num(r.get('Population',0)))}
        for r in pop_rows
    ]

    return {
        'total_jobs':         total_jobs,
        'avg_wage':           avg_wage,
        'population':         round(bibb_pop),
        'net_commuters':      round(bibb_comm),
        'top_industry':       top_industry,
        'industries_sorted':  industries_sorted,
        'surrounding':        surrounding,
        'top_occ':            top_occ,
        'comm_map_data':      comm_map_data,
        'pop_map_data':       pop_map_data,
    }

# ── Occupation table HTML ──────────────────────────────────────────────────

def build_occ_table(occ_rows):
    th = 'padding:5pt 8pt;text-align:left;font-size:6.5pt;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;white-space:nowrap;border-bottom:1pt solid #e5e7eb;'
    td = 'padding:5pt 8pt;font-size:8pt;border-bottom:0.5pt solid #f3f4f6;'
    header = (f'<tr>'
              f'<th style="{th}">#</th>'
              f'<th style="{th}">Occupation</th>'
              f'<th style="{th};text-align:right">Employment</th>'
              f'<th style="{th};text-align:right">Avg Annual Wage</th>'
              f'<th style="{th};text-align:right">LQ</th>'
              f'</tr>')
    rows_html = ''
    for i, r in enumerate(occ_rows):
        lq  = to_num(r.get('LQ', 0))
        lq_color = '#059669' if lq >= 1.2 else '#d97706' if lq >= 0.8 else '#9ca3af'
        wage = to_num(r.get('Mean Ann Wages2', 0))
        rows_html += (f'<tr>'
                      f'<td style="{td}color:#9ca3af">{i+1}</td>'
                      f'<td style="{td}font-weight:500">{r.get("Occupation","")}</td>'
                      f'<td style="{td}text-align:right">{fmt_num(to_num(r.get("Empl",0)))}</td>'
                      f'<td style="{td}text-align:right">{fmt_dollar(wage) if wage > 0 else "—"}</td>'
                      f'<td style="{td}text-align:right;color:{lq_color};font-weight:600">'
                      f'{"—" if lq <= 0 else f"{lq:.2f}×"}</td>'
                      f'</tr>')
    return f'<table style="width:100%;border-collapse:collapse;"><thead>{header}</thead><tbody>{rows_html}</tbody></table>'

# ── HTML template ──────────────────────────────────────────────────────────

def build_html(d, geo_json_str):
    ind_labels  = json.dumps([x['name']  for x in d['industries_sorted']])
    ind_empls   = json.dumps([x['empl']  for x in d['industries_sorted']])
    ind_colors  = json.dumps([x['color'] for x in d['industries_sorted']])
    comm_map_json = json.dumps(d['comm_map_data'])
    pop_map_json  = json.dumps(d['pop_map_data'])
    occ_table   = build_occ_table(d['top_occ'])

    # Demographics hardcoded from 2024 ACS
    age_labels  = json.dumps(['Under 18','18–24','25–34','35–44','45–54','55–64','65–74','75+'])
    age_vals    = json.dumps([24.4, 9.5, 14.1, 12.1, 11.3, 12.3, 9.9, 6.6])
    race_labels = json.dumps(['Black / African Am.','White','Hispanic / Latino','Two+ Races','Asian','Other'])
    race_vals   = json.dumps([54.9, 35.3, 4.7, 4.6, 2.3, 2.9])
    edu_labels  = json.dumps(['Postgraduate',"Bachelor's","Associate's",'Some College','High School','No Diploma'])
    edu_vals    = json.dumps([13.3, 13.9, 9.0, 22.2, 30.4, 11.2])

    comm_rows_html = ''.join(
        f'<tr>'
        f'<td style="padding:5pt 8pt;font-size:8pt;border-bottom:0.5pt solid #f3f4f6;font-weight:500">{r["name"]}</td>'
        f'<td style="padding:5pt 8pt;font-size:8pt;border-bottom:0.5pt solid #f3f4f6;text-align:right">{r["pop"]:,}</td>'
        f'<td style="padding:5pt 8pt;font-size:8pt;border-bottom:0.5pt solid #f3f4f6;text-align:right;color:#4f46e5;font-weight:600">{r["comm"]:,}</td>'
        f'</tr>'
        for r in d['surrounding']
    )

    industry_chart_h = max(200, len(d['industries_sorted']) * 22)
    demo_h = 180

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Macon-Bibb County — Economic Overview</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'Inter', -apple-system, Arial, sans-serif;
    background: #fff; color: #111827;
    font-size: 9pt; line-height: 1.5;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .page {{ page-break-after: always; }}
  .page:last-child {{ page-break-after: auto; }}

  /* Cover */
  .cover {{
    min-height: 9in;
    display: flex; flex-direction: column; justify-content: center;
    background: #0f172a;
    padding: 1in 0.7in;
    position: relative;
  }}
  .cover::before {{
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0; width: 5pt;
    background: #059669;
  }}
  .cover-label {{
    font-size: 7pt; font-weight: 600;
    letter-spacing: 0.14em; text-transform: uppercase;
    color: #34d399; margin-bottom: 12pt;
  }}
  .cover h1 {{
    font-size: 40pt; font-weight: 700;
    letter-spacing: -0.03em; color: #fff;
    line-height: 1.0; margin-bottom: 10pt;
  }}
  .cover-sub {{
    font-size: 10pt; color: #94a3b8;
    max-width: 5in; line-height: 1.7; margin-bottom: 36pt;
  }}
  .kpi-row {{
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 10pt; margin-top: 0;
  }}
  .kpi-block {{
    background: rgba(255,255,255,0.05);
    border: 1pt solid rgba(255,255,255,0.1);
    border-radius: 6pt;
    padding: 14pt 14pt;
  }}
  .kpi-val {{ font-size: 18pt; font-weight: 700; color: #fff; letter-spacing: -0.03em; line-height: 1; }}
  .kpi-lbl {{ font-size: 6pt; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #64748b; margin-top: 5pt; }}

  /* Sections */
  .content {{ padding: 0.55in 0.7in; }}
  .stag {{
    display: inline-block; font-size: 6pt; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #4f46e5; border: 1pt solid #e0e7ff;
    background: #eef2ff; border-radius: 3pt; padding: 1pt 5pt;
    margin-bottom: 6pt;
  }}
  .stag.teal {{ color: #059669; border-color: #d1fae5; background: #ecfdf5; }}
  .stag.orange {{ color: #d97706; border-color: #fde68a; background: #fffbeb; }}
  .section-title {{
    font-size: 16pt; font-weight: 700; letter-spacing: -0.02em;
    color: #111827; margin-bottom: 4pt; line-height: 1.2;
  }}
  .section-sub {{
    font-size: 8.5pt; color: #6b7280; margin-bottom: 16pt; line-height: 1.6;
  }}
  .sdiv {{
    font-size: 7pt; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #9ca3af;
    border-top: 1pt solid #e5e7eb; padding-top: 8pt; margin: 20pt 0 10pt;
  }}
  .cbox {{ background: #f9fafb; border: 1pt solid #e5e7eb; border-radius: 6pt; padding: 12pt; }}

  /* Stat grid */
  .stat-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 10pt; margin-bottom: 20pt;
  }}
  .stat-card {{
    background: #f9fafb; border: 1pt solid #e5e7eb;
    border-radius: 6pt; padding: 12pt;
  }}
  .stat-val {{ font-size: 16pt; font-weight: 700; color: #111827; letter-spacing: -0.02em; }}
  .stat-key {{ font-size: 6.5pt; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 3pt; }}

  /* Demo grid */
  .demo-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 12pt; }}
  .demo-card {{ background: #f9fafb; border: 1pt solid #e5e7eb; border-radius: 6pt; padding: 12pt; }}
  .demo-title {{ font-size: 6.5pt; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #9ca3af; margin-bottom: 10pt; border-bottom: 1pt solid #e5e7eb; padding-bottom: 6pt; }}

  /* Commute table */
  .comm-table {{ width: 100%; border-collapse: collapse; }}
  .comm-th {{ padding: 5pt 8pt; text-align: left; font-size: 6.5pt; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #6b7280; border-bottom: 1pt solid #e5e7eb; white-space: nowrap; }}
</style>
</head>
<body>

<!-- ── Cover ────────────────────────────────────────────── -->
<div class="page cover">
  <div class="cover-label">Economic Overview · Macon-Bibb County, Georgia</div>
  <h1>Macon-Bibb<br>County</h1>
  <p class="cover-sub">Central Georgia's regional economic hub — a diverse workforce at the intersection of major transportation corridors, anchored by healthcare, public services, and growing industry.</p>
  <div class="kpi-row">
    <div class="kpi-block">
      <div class="kpi-val">{d['total_jobs']:,}</div>
      <div class="kpi-lbl">Total Jobs</div>
    </div>
    <div class="kpi-block">
      <div class="kpi-val">${d['avg_wage']:,}</div>
      <div class="kpi-lbl">Avg Annual Wage</div>
    </div>
    <div class="kpi-block">
      <div class="kpi-val">{d['population']:,}</div>
      <div class="kpi-lbl">Population</div>
    </div>
    <div class="kpi-block">
      <div class="kpi-val">+{d['net_commuters']:,}</div>
      <div class="kpi-lbl">Net In-Commuters</div>
    </div>
    <div class="kpi-block">
      <div class="kpi-val" style="font-size:11pt;line-height:1.2">{d['top_industry']}</div>
      <div class="kpi-lbl">Largest Sector</div>
    </div>
  </div>
</div>

<!-- ── Industry Breakdown ─────────────────────────────── -->
<div class="page content">
  <div class="stag">Industry Landscape</div>
  <div class="section-title">Where Macon Works</div>
  <p class="section-sub">Total employment by industry sector, sourced from JobsEQ covered employment data for Macon-Bibb County.</p>
  <div class="cbox">
    <canvas id="cind" width="640" height="{industry_chart_h}"></canvas>
  </div>
</div>

<!-- ── Regional Map ──────────────────────────────────── -->
<div class="page content" style="page-break-before:always;">
  <div class="stag">Regional Context</div>
  <p class="section-sub">All 16 surrounding counties have negative net commuting balances, reflecting a regional workforce that flows toward Macon-Bibb for employment. Net commuting = a county's total in-commuters minus its out-commuters.</p>
  <div id="map-wrap" style="background:#0d0d0f;border-radius:6pt;overflow:hidden;margin-bottom:18pt;">
    <svg id="map-svg" style="display:block;"></svg>
  </div>
  <div class="cbox" style="padding:0;overflow:hidden;">
    <table class="comm-table">
      <thead><tr>
        <th class="comm-th">County</th>
        <th class="comm-th" style="text-align:right">Population</th>
        <th class="comm-th" style="text-align:right">Net Commuting Balance</th>
      </tr></thead>
      <tbody>{comm_rows_html}</tbody>
    </table>
  </div>
  <p style="font-size:7pt;color:#9ca3af;margin-top:8pt;">Source: JobsEQ net commuting data · Macon-Bibb County, GA</p>
</div>

<!-- ── Demographics ──────────────────────────────────── -->
<div class="page content" style="page-break-before:always;">
  <div class="stag orange">Workforce Demographics</div>
  <div class="section-title">Who Lives Here</div>
  <p class="section-sub">American Community Survey 2024 estimates for Macon-Bibb County.</p>

  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-val">{d['population']:,}</div>
      <div class="stat-key">Population</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">56.6%</div>
      <div class="stat-key">Labor Force Participation</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">24.7%</div>
      <div class="stat-key">Poverty Rate</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">9.5%</div>
      <div class="stat-key">Work From Home</div>
    </div>
  </div>

  <div class="demo-grid">
    <div class="demo-card">
      <div class="demo-title">Age Distribution</div>
      <canvas id="cage" width="200" height="{demo_h}"></canvas>
    </div>
    <div class="demo-card">
      <div class="demo-title">Race &amp; Ethnicity</div>
      <canvas id="crace" width="200" height="{demo_h}"></canvas>
    </div>
    <div class="demo-card">
      <div class="demo-title">Educational Attainment (Age 25–64)</div>
      <canvas id="cedu" width="200" height="{demo_h}"></canvas>
    </div>
  </div>
</div>

<!-- ── Occupations ────────────────────────────────────── -->
<div class="page content" style="page-break-before:always;">
  <div class="stag teal">Top Occupations</div>
  <div class="section-title">In-Demand Roles</div>
  <p class="section-sub">Top 15 occupations by employment in Macon-Bibb County. LQ &gt; 1.0 indicates above-average regional concentration vs. the national average.</p>
  <div class="cbox" style="padding:0;overflow:hidden;">
    {occ_table}
  </div>
</div>


<script>
(function() {{
  Chart.register(ChartDataLabels);

  function trunc(s, n) {{ return s.length > n ? s.slice(0,n-1)+'…' : s; }}
  function fmtNum(v) {{
    if (v >= 1000) return (v/1000).toFixed(1)+'K';
    return Math.round(v).toString();
  }}

  var BAR_OPTS = function(padRight) {{
    return {{
      indexAxis: 'y', animation: false,
      responsive: false, maintainAspectRatio: false,
      layout: {{ padding: {{ right: padRight, top: 2, bottom: 2 }} }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ enabled: false }},
        datalabels: {{
          anchor: 'end', align: 'right', clamp: false, clip: false,
          color: '#9ca3af', font: {{ size: 8, weight: '500' }},
          formatter: fmtNum,
        }},
      }},
      scales: {{
        y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 8 }} }} }},
        x: {{ display: false }},
      }},
    }};
  }};

  // Industry chart
  var indEl = document.getElementById('cind');
  if (indEl) {{
    var indLabels = {ind_labels};
    var indEmpls  = {ind_empls};
    var indColors = {ind_colors};
    new Chart(indEl, {{
      type: 'bar',
      data: {{
        labels: indLabels,
        datasets: [{{ data: indEmpls, backgroundColor: indColors, borderWidth: 0, barPercentage: 0.8, categoryPercentage: 1 }}],
      }},
      options: BAR_OPTS(56),
      plugins: [ChartDataLabels],
    }});
  }}

  // Age
  var ageEl = document.getElementById('cage');
  if (ageEl) {{
    var ageLabels = {age_labels};
    var ageVals   = {age_vals};
    new Chart(ageEl, {{
      type: 'bar',
      data: {{
        labels: ageLabels,
        datasets: [{{ data: ageVals, backgroundColor: 'rgba(251,146,60,0.75)', borderWidth: 0, barPercentage: 0.75, categoryPercentage: 1 }}],
      }},
      options: {{
        indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false,
        layout: {{ padding: {{ right: 36, top: 2, bottom: 2 }} }},
        plugins: {{
          legend: {{ display: false }}, tooltip: {{ enabled: false }},
          datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 7.5, weight: '500' }}, formatter: function(v) {{ return v.toFixed(1)+'%'; }} }},
        }},
        scales: {{
          y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 7.5 }} }} }},
          x: {{ display: false }},
        }},
      }},
      plugins: [ChartDataLabels],
    }});
  }}

  // Race
  var raceEl = document.getElementById('crace');
  if (raceEl) {{
    var raceLabels = {race_labels};
    var raceVals   = {race_vals};
    new Chart(raceEl, {{
      type: 'bar',
      data: {{
        labels: raceLabels,
        datasets: [{{ data: raceVals, backgroundColor: 'rgba(129,140,248,0.75)', borderWidth: 0, barPercentage: 0.75, categoryPercentage: 1 }}],
      }},
      options: {{
        indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false,
        layout: {{ padding: {{ right: 36, top: 2, bottom: 2 }} }},
        plugins: {{
          legend: {{ display: false }}, tooltip: {{ enabled: false }},
          datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 7.5, weight: '500' }}, formatter: function(v) {{ return v.toFixed(1)+'%'; }} }},
        }},
        scales: {{
          y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 7.5 }} }} }},
          x: {{ display: false }},
        }},
      }},
      plugins: [ChartDataLabels],
    }});
  }}

  // Education
  var eduEl = document.getElementById('cedu');
  if (eduEl) {{
    var eduLabels = {edu_labels};
    var eduVals   = {edu_vals};
    new Chart(eduEl, {{
      type: 'bar',
      data: {{
        labels: eduLabels,
        datasets: [{{ data: eduVals, backgroundColor: 'rgba(52,211,153,0.75)', borderWidth: 0, barPercentage: 0.75, categoryPercentage: 1 }}],
      }},
      options: {{
        indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false,
        layout: {{ padding: {{ right: 36, top: 2, bottom: 2 }} }},
        plugins: {{
          legend: {{ display: false }}, tooltip: {{ enabled: false }},
          datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 7.5, weight: '500' }}, formatter: function(v) {{ return v.toFixed(1)+'%'; }} }},
        }},
        scales: {{
          y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 7.5 }} }} }},
          x: {{ display: false }},
        }},
      }},
      plugins: [ChartDataLabels],
    }});
  }}

  // ── D3 Choropleth Map ─────────────────────────────────────
  (function() {{
    var GEO  = {geo_json_str};
    var COMM = {comm_map_json};
    var POP  = {pop_map_json};
    var BIBB = '13021';

    var wrap = document.getElementById('map-wrap');
    if (!wrap || typeof d3 === 'undefined') return;

    var W = wrap.getBoundingClientRect().width || 682;
    var H = 400;

    var commLookup = {{}}, popLookup = {{}}, nameLookup = {{}};
    COMM.forEach(function(r) {{
      var f = String(r.fips).padStart(5,'0');
      commLookup[f] = r.comm; nameLookup[f] = r.name;
    }});
    POP.forEach(function(r) {{
      var f = String(r.fips).padStart(5,'0');
      popLookup[f] = r.pop;
    }});

    var nonBibb = Object.entries(commLookup).filter(function(e){{ return e[0] !== BIBB; }});
    var maxPos  = Math.max.apply(null, [0].concat(nonBibb.filter(function(e){{ return e[1] >  0; }}).map(function(e){{ return  e[1]; }})));
    var maxNeg  = Math.max.apply(null, [0].concat(nonBibb.filter(function(e){{ return e[1] <= 0; }}).map(function(e){{ return -e[1]; }})));

    function countyFill(f) {{
      if (f === BIBB) return '#166534';
      var comm = commLookup[f]||0;
      if (comm > 0) {{
        var t = comm / (maxPos||1);
        return d3.interpolateRgb('#dcfce7','#4ade80')(0.15 + t*0.45);
      }}
      var t = -comm / (maxNeg||1);
      return d3.interpolateRgb('#fff7ed','#c2410c')(0.15 + t*0.75);
    }}

    var proj = d3.geoAlbers().fitExtent([[24,52],[W-24,H-20]], GEO);
    var path = d3.geoPath().projection(proj);

    var svg = d3.select('#map-svg').attr('width', W).attr('height', H);

    svg.append('text').text('Macon and Surrounding Counties')
      .attr('x',14).attr('y',22)
      .attr('font-size',13).attr('font-weight',700)
      .attr('letter-spacing','-0.02em').attr('fill','#f4f4f5');
    svg.append('text').text('< 1-hour drive radius · net commuting balance by county')
      .attr('x',14).attr('y',38)
      .attr('font-size',8).attr('fill','#71717a');

    svg.append('g').selectAll('path')
      .data(GEO.features).join('path')
      .attr('d', path)
      .attr('fill', function(d) {{ return countyFill(String(d.id).padStart(5,'0')); }})
      .attr('stroke', function(d) {{
        return String(d.id).padStart(5,'0') === BIBB ? '#34d399' : '#4b5563';
      }})
      .attr('stroke-width', function(d) {{
        return String(d.id).padStart(5,'0') === BIBB ? 2 : 0.6;
      }});

    GEO.features.forEach(function(d) {{
      var f = String(d.id).padStart(5,'0');
      var isBibb = f === BIBB;
      var c = path.centroid(d);
      if (isNaN(c[0])) return;
      var name = (nameLookup[f]||'');
      var pop  = popLookup[f]||0;
      var comm = commLookup[f]||0;
      var popStr  = pop>=1000 ? (pop/1000).toFixed(pop<10000?1:0)+'K' : String(pop);
      var commStr = isBibb ? '+{d['net_commuters']:,} net' : 'net: '+Math.round(comm).toLocaleString();
      var bounds  = path.bounds(d);
      var minDim  = Math.min(bounds[1][0]-bounds[0][0], bounds[1][1]-bounds[0][1]);
      var g = svg.append('g').attr('transform','translate('+c[0]+','+c[1]+')');
      if (isBibb) {{
        g.append('text').text('Macon-Bibb').attr('text-anchor','middle').attr('dy','-10')
          .attr('font-size',12).attr('font-weight',700).attr('fill','#ffffff');
        g.append('text').text(popStr).attr('text-anchor','middle').attr('dy','4')
          .attr('font-size',10).attr('fill','#bbf7d0');
        g.append('text').text(commStr).attr('text-anchor','middle').attr('dy','18')
          .attr('font-size',9).attr('fill','#86efac');
      }} else if (minDim >= 26) {{
        var fs = Math.max(7, Math.min(9, minDim/6));
        g.append('text').text(name).attr('text-anchor','middle').attr('dy', minDim<40?'-2':'-5')
          .attr('font-size',fs).attr('font-weight',600).attr('fill','#d1d5db');
        g.append('text').text(popStr).attr('text-anchor','middle').attr('dy', minDim<40?'7':'8')
          .attr('font-size',fs-1).attr('fill','#9ca3af');
        if (minDim >= 40) {{
          var commColor = comm > 0 ? '#86efac' : '#fdba74';
          g.append('text').text(commStr).attr('text-anchor','middle').attr('dy','20')
            .attr('font-size',fs-1).attr('fill',commColor);
        }}
      }}
    }});

    // Population stat overlay (bottom-left of map)
    var totalPop = Object.values(popLookup).reduce(function(s,v){{ return s+v; }}, 0);
    var bibbPop  = popLookup[BIBB] || 0;
    function fmtPop(n) {{
      return n >= 1000000 ? (n/1000000).toFixed(2)+'M' : Math.round(n/1000)+'K';
    }}
    var statsEl = document.createElement('div');
    statsEl.style.cssText = 'position:absolute;bottom:12px;left:12px;background:rgba(13,13,15,0.88);border:1px solid #27272a;border-radius:5px;padding:9px 12px;';
    statsEl.innerHTML = (
      '<div style="margin-bottom:8px;">' +
        '<div style="font-size:16pt;font-weight:700;letter-spacing:-0.03em;color:#d4d4d8;line-height:1;">' + fmtPop(totalPop) + '</div>' +
        '<div style="font-size:6.5pt;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#52525b;margin-top:2px;">Total Regional Population</div>' +
      '</div>' +
      '<div>' +
        '<div style="font-size:16pt;font-weight:700;letter-spacing:-0.03em;color:#34d399;line-height:1;">' + fmtPop(bibbPop) + '</div>' +
        '<div style="font-size:6.5pt;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#52525b;margin-top:2px;">Macon-Bibb Population</div>' +
      '</div>'
    );
    wrap.appendChild(statsEl);
  }})();

  window.__chartsReady = true;
}})();
</script>
</body>
</html>"""


# ── PDF rendering ──────────────────────────────────────────────────────────

async def render_pdf(html, output_path):
    from playwright.async_api import async_playwright
    with tempfile.NamedTemporaryFile(suffix='.html', mode='w', encoding='utf-8', delete=False) as f:
        f.write(html)
        tmp_path = Path(f.name)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page    = await browser.new_page()
            errors  = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            await page.goto(tmp_path.as_uri(), wait_until='networkidle')
            try:
                await page.wait_for_function('window.__chartsReady === true', timeout=15_000)
            except Exception:
                if errors:
                    raise RuntimeError('JS errors: ' + '; '.join(errors))
                raise
            await page.pdf(
                path=str(output_path),
                format='Letter',
                print_background=True,
                display_header_footer=True,
                header_template='<span></span>',
                footer_template='''<div style="width:100%;font-size:7pt;color:#9ca3af;
                    font-family:-apple-system,Arial,sans-serif;
                    display:flex;justify-content:space-between;align-items:center;
                    border-top:0.5pt solid #e5e7eb;padding-top:3pt;
                    margin:0 0.7in;box-sizing:border-box;">
                    <span>Source: JobsEQ · ACS 2024 &nbsp;·&nbsp; Macon-Bibb County, GA</span>
                    <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
                </div>''',
                margin={'top': '0.65in', 'bottom': '0.65in', 'left': '0.7in', 'right': '0.7in'},
            )
            await browser.close()
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Main ───────────────────────────────────────────────────────────────────

async def main():
    script_dir = Path(__file__).parent

    paths = {
        'ind':  script_dir / 'Data' / 'processed' / 'Industry_Snapshot.csv',
        'occ':  script_dir / 'Data' / 'processed' / 'Occupation_Snapshot.csv',
        'pop':  script_dir / 'Data' / 'processed' / 'Population_By_County.csv',
        'comm': script_dir / 'Data' / 'processed' / 'Net_Commuting.csv',
        'geo':  script_dir / 'Data' / 'processed' / 'counties.geojson',
    }

    for key, p in paths.items():
        if not p.exists():
            print(f'Error: missing file: {p}')
            sys.exit(1)

    ind_rows  = load_csv(paths['ind'])
    occ_rows  = load_csv(paths['occ'])
    pop_rows  = load_csv(paths['pop'])
    comm_rows = load_csv(paths['comm'])
    geo_json_str = paths['geo'].read_text(encoding='utf-8')

    d = process(ind_rows, occ_rows, pop_rows, comm_rows)

    output_dir = script_dir / 'reports' / 'pdf'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'macon-overview.pdf'

    print('Building Macon Overview PDF...')
    html = build_html(d, geo_json_str)
    await render_pdf(html, output_path)
    print(f'Saved → {output_path}')


if __name__ == '__main__':
    asyncio.run(main())
