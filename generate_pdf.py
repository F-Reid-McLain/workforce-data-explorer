#!/usr/bin/env python3
"""
Generate PDF reports for Macon-Bibb workforce industry data.

Usage:
  python3 generate_pdf.py 31           # Single industry (Manufacturing)
  python3 generate_pdf.py all          # All 20 industries
  python3 generate_pdf.py 31 62 72     # Multiple specific industries

Output: reports/pdf/{id}.pdf

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

# ── Industry config ────────────────────────────────────────────────────────

INDUSTRIES = {
    '11': {'name': 'Agriculture, Forestry, Fishing & Hunting',     'naicsLabel': 'NAICS 11',    'prefixes': ['11'],           'color': '#86efac'},
    '21': {'name': 'Mining, Quarrying & Oil and Gas Extraction',    'naicsLabel': 'NAICS 21',    'prefixes': ['21'],           'color': '#fcd34d'},
    '22': {'name': 'Utilities',                                     'naicsLabel': 'NAICS 22',    'prefixes': ['22'],           'color': '#67e8f9'},
    '23': {'name': 'Construction',                                  'naicsLabel': 'NAICS 23',    'prefixes': ['23'],           'color': '#fdba74'},
    '31': {'name': 'Manufacturing',                                 'naicsLabel': 'NAICS 31–33', 'prefixes': ['31','32','33'], 'color': '#93c5fd'},
    '42': {'name': 'Wholesale Trade',                               'naicsLabel': 'NAICS 42',    'prefixes': ['42'],           'color': '#5eead4'},
    '44': {'name': 'Retail Trade',                                  'naicsLabel': 'NAICS 44–45', 'prefixes': ['44','45'],      'color': '#f9a8d4'},
    '48': {'name': 'Transportation & Warehousing',                  'naicsLabel': 'NAICS 48–49', 'prefixes': ['48','49'],      'color': '#fca5a5'},
    '51': {'name': 'Information',                                   'naicsLabel': 'NAICS 51',    'prefixes': ['51'],           'color': '#c4b5fd'},
    '52': {'name': 'Finance & Insurance',                           'naicsLabel': 'NAICS 52',    'prefixes': ['52'],           'color': '#7dd3fc'},
    '53': {'name': 'Real Estate & Rental and Leasing',              'naicsLabel': 'NAICS 53',    'prefixes': ['53'],           'color': '#6ee7b7'},
    '54': {'name': 'Professional, Scientific & Technical Services', 'naicsLabel': 'NAICS 54',    'prefixes': ['54'],           'color': '#a5b4fc'},
    '55': {'name': 'Management of Companies & Enterprises',         'naicsLabel': 'NAICS 55',    'prefixes': ['55'],           'color': '#94a3b8'},
    '56': {'name': 'Administrative & Support Services',             'naicsLabel': 'NAICS 56',    'prefixes': ['56'],           'color': '#fde68a'},
    '61': {'name': 'Educational Services',                          'naicsLabel': 'NAICS 61',    'prefixes': ['61'],           'color': '#bef264'},
    '62': {'name': 'Health Care & Social Assistance',               'naicsLabel': 'NAICS 62',    'prefixes': ['62'],           'color': '#34d399'},
    '71': {'name': 'Arts, Entertainment & Recreation',              'naicsLabel': 'NAICS 71',    'prefixes': ['71'],           'color': '#f9a8d4'},
    '72': {'name': 'Accommodation & Food Services',                 'naicsLabel': 'NAICS 72',    'prefixes': ['72'],           'color': '#fb923c'},
    '81': {'name': 'Other Services',                                'naicsLabel': 'NAICS 81',    'prefixes': ['81'],           'color': '#a1a1aa'},
    '92': {'name': 'Public Administration',                         'naicsLabel': 'NAICS 92',    'prefixes': ['92'],           'color': '#818cf8'},
}

NAICS_MERGE = {'32': '31', '33': '31', '45': '44', '49': '48'}

SECTOR_MUTED_COLORS = {
    '11': 'hsl(125,28%,62%)',  # sage          — Agriculture
    '21': 'hsl(42,30%,62%)',   # wheat         — Mining
    '22': 'hsl(188,28%,60%)',  # teal          — Utilities
    '23': 'hsl(28,32%,62%)',   # tan           — Construction
    '31': 'hsl(215,28%,62%)',  # steel blue    — Manufacturing
    '42': 'hsl(72,26%,60%)',   # olive         — Wholesale
    '44': 'hsl(345,26%,66%)',  # dusty rose    — Retail
    '48': 'hsl(18,28%,62%)',   # sienna        — Transportation
    '51': 'hsl(268,26%,64%)',  # soft purple   — Information
    '52': 'hsl(202,30%,62%)',  # sky blue      — Finance
    '53': 'hsl(155,26%,62%)',  # seafoam       — Real Estate
    '54': 'hsl(248,26%,65%)',  # lavender      — Professional
    '55': 'hsl(218,18%,62%)',  # slate         — Management
    '56': 'hsl(48,28%,62%)',   # muted gold    — Admin Services
    '61': 'hsl(92,26%,62%)',   # lime          — Education
    '71': 'hsl(298,20%,64%)',  # mauve         — Arts
    '72': 'hsl(22,30%,64%)',   # coral         — Hospitality
    '81': 'hsl(205,18%,64%)',  # blue-grey     — Other Services
    '92': 'hsl(235,26%,64%)',  # periwinkle    — Public Admin
}

NAICS_NAMES = {
    '11': 'Agriculture',       '21': 'Mining & Oil/Gas',
    '22': 'Utilities',         '23': 'Construction',
    '31': 'Manufacturing',     '42': 'Wholesale Trade',
    '44': 'Retail Trade',      '48': 'Transportation',
    '51': 'Information',       '52': 'Finance & Insurance',
    '53': 'Real Estate',       '54': 'Professional Services',
    '55': 'Management',        '56': 'Admin Services',
    '61': 'Education',         '62': 'Health Care',
    '71': 'Arts & Recreation', '72': 'Hospitality',
    '81': 'Other Services',    '92': 'Public Admin',
}

# ── Helpers ────────────────────────────────────────────────────────────────

def to_num(v):
    if not v:
        return 0.0
    try:
        return float(str(v).replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def fmt_num(n):
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n/1_000:.1f}K'
    return f'{round(n):,}'

def fmt_dollar(n):
    if n >= 1_000_000:
        return f'${n/1_000_000:.1f}M'
    if n >= 1_000:
        return f'${round(n/1_000)}K'
    return f'${round(n):,}'

def ordinal(n):
    if 11 <= n % 100 <= 13:
        return f'{n}th'
    return f'{n}{["th","st","nd","rd","th"][min(n % 10, 4)]}'

def trunc(s, length=44):
    s = s or ''
    return s[:length - 1] + '…' if len(s) > length else s

def hex_to_rgb(h):
    h = h.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def load_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def logo_data_uri():
    logo_path = Path(__file__).parent / 'Resources' / '32_greatermacon_531X354.webp'
    data = base64.b64encode(logo_path.read_bytes()).decode('ascii')
    return f'data:image/webp;base64,{data}'

# ── Data processing ────────────────────────────────────────────────────────

def process(industry_id, rows):
    config = INDUSTRIES[industry_id]

    total_row  = next((r for r in rows if r['NAICS'].strip() == ''), None)
    total_empl = to_num(total_row['Empl']) if total_row else 0

    ind_rows = [r for r in rows
                if r['NAICS'].strip()
                and any(r['NAICS'].strip().startswith(p) for p in config['prefixes'])]

    ind_empl   = sum(to_num(r['Empl'])         for r in ind_rows)
    ind_demand = sum(to_num(r['Total Demand'])  for r in ind_rows)
    wage_num   = sum(to_num(r['Avg Ann Wages']) * to_num(r['Empl']) for r in ind_rows)
    wage_den   = sum(to_num(r['Empl'])          for r in ind_rows)
    avg_wage   = wage_num / wage_den if wage_den > 0 else 0
    share      = (ind_empl / total_empl * 100)  if total_empl > 0 else 0

    sector_map = {}
    for r in rows:
        code = r['NAICS'].strip()
        if not code:
            continue
        raw    = code[:2]
        merged = NAICS_MERGE.get(raw, raw)
        sector_map[merged] = sector_map.get(merged, 0) + to_num(r['Empl'])
    sectors_sorted_full = sorted(sector_map.items(), key=lambda x: -x[1])

    canonical_id = NAICS_MERGE.get(industry_id, industry_id)
    rank         = next((i + 1 for i, (c, _) in enumerate(sectors_sorted_full) if c == canonical_id), 0)
    short_name   = config['name'].split(',')[0].split('&')[0].strip()

    # Chart data ── employment
    empl_rows = sorted([r for r in ind_rows if to_num(r['Empl']) > 0],
                       key=lambda r: -to_num(r['Empl']))[:20]

    # Chart data ── wage (top N + bottom N, deduplicated)
    with_wages = sorted([r for r in ind_rows
                         if to_num(r['Avg Ann Wages']) > 0 and to_num(r['Empl']) > 0],
                        key=lambda r: -to_num(r['Avg Ann Wages']))
    half      = min(10, max(3, len(with_wages) // 2))
    wage_top  = with_wages[:half]
    wage_bot  = list(reversed(with_wages))[:half][::-1]
    top_naics = {r['NAICS'] for r in wage_top}
    wage_rows = wage_top + [r for r in wage_bot if r['NAICS'] not in top_naics]

    # Chart data ── demand
    demand_rows = sorted([r for r in ind_rows if to_num(r['Total Demand']) > 0],
                         key=lambda r: -to_num(r['Total Demand']))[:15]

    # Doughnut — merge sectors < 2% of total into "Other" (never merge the highlighted sector)
    sector_total = sum(v for _, v in sectors_sorted_full)
    threshold    = sector_total * 0.02
    main_sectors = [(c, v) for c, v in sectors_sorted_full if v >= threshold or c == canonical_id]
    other_total  = sum(v for c, v in sectors_sorted_full if v < threshold and c != canonical_id)
    sectors_sorted = main_sectors + ([('other', other_total)] if other_total > 0 else [])

    d_colors = []
    for i, (c, _) in enumerate(sectors_sorted):
        if c == canonical_id:
            d_colors.append(config['color'])
        else:
            d_colors.append('hsl(220,8%,74%)')

    return dict(
        config=config,
        ind_empl=ind_empl, ind_demand=ind_demand,
        avg_wage=avg_wage, share=share, rank=rank,
        short_name=short_name,
        sectors_sorted=sectors_sorted, canonical_id=canonical_id,
        sector_total=sector_total, d_colors=d_colors,
        empl_rows=empl_rows, wage_rows=wage_rows,
        wage_top_len=len(wage_top), demand_rows=demand_rows,
    )

# ── HTML builder ───────────────────────────────────────────────────────────

def build_html(industry_id, rows):
    d      = process(industry_id, rows)
    config = d['config']
    acc    = config['color']
    r, g, b = hex_to_rgb(acc)

    empl_h   = max(240, len(d['empl_rows'])   * 30 + 60)
    wage_h   = max(180, len(d['wage_rows'])   * 30 + 80)
    demand_h = max(200, len(d['demand_rows']) * 30 + 60)

    # Narrative
    narrative = (
        f'<strong>{config["name"]}</strong> accounts for about '
        f'<span class="stat">{d["share"]:.1f}%</span> of Macon-Bibb\'s job market, '
        f'making it the <span class="stat">{ordinal(d["rank"])} largest industry</span> in the region. '
        f'Approximately <span class="stat">{fmt_num(d["ind_empl"])} people</span> work in this sector, '
        f'with an average annual wage of '
        f'<span class="stat">{fmt_dollar(round(d["avg_wage"]))}</span> across all sub-sectors.'
    )

    # Doughnut legend
    legend_html = ''.join(
        f'<div class="li{"  hl" if c == d["canonical_id"] else ""}">'
        f'<span class="dot" style="background:{d["d_colors"][i]}"></span>'
        f'<span class="ln">{"Other" if c == "other" else NAICS_NAMES.get(c, c)}</span>'
        f'<span class="lp" style="color:{acc if c == d["canonical_id"] else "#9ca3af"}">'
        f'{v / d["sector_total"] * 100:.1f}%</span></div>'
        for i, (c, v) in enumerate(d['sectors_sorted'])
    )

    # Optional chart sections
    def empl_section():
        if not d['empl_rows']:
            return ''
        return (
            f'<div class="section"><div class="stitle">Breakdown by Employer Type</div>'
            f'<p class="ssub">Top sub-sectors by total employment within {config["name"]}.</p>'
            f'<div class="cbox"><canvas id="ce" width="640" height="{empl_h}"></canvas></div></div>'
        )

    def wage_section():
        if not d['wage_rows']:
            return ''
        return (
            f'<div class="section"><div class="stitle">Highest &amp; Lowest Paying Sub-Sectors</div>'
            f'<p class="ssub">Average annual wage comparison across sub-sectors within {config["name"]}.</p>'
            f'<div class="cbox"><canvas id="cw" width="640" height="{wage_h}"></canvas></div></div>'
        )

    def demand_section():
        if not d['demand_rows']:
            return ''
        return (
            f'<div class="section"><div class="stitle">Sub-Sectors with the Highest Labor Demand</div>'
            f'<p class="ssub">Projected annual job openings for {config["name"]}.</p>'
            f'<div class="cbox"><canvas id="cd2" width="640" height="{demand_h}"></canvas></div></div>'
        )

    # JSON payload — escape </ so it can't terminate a script tag
    payload = json.dumps({
        'acc': acc, 'r': r, 'g': g, 'b': b,
        'sector_total': d['sector_total'],
        'sectors_sorted': d['sectors_sorted'],
        'canonical_id': d['canonical_id'],
        'd_colors': d['d_colors'],
        'naics_names': {**NAICS_NAMES, 'other': 'Other'},
        'empl_rows':   [{'Industry': x['Industry'], 'Empl': x['Empl']}
                        for x in d['empl_rows']],
        'wage_rows':   [{'Industry': x['Industry'], 'Avg Ann Wages': x['Avg Ann Wages']}
                        for x in d['wage_rows']],
        'wage_top_len': d['wage_top_len'],
        'demand_rows': [{'Industry': x['Industry'], 'Total Demand': x['Total Demand']}
                        for x in d['demand_rows']],
    }, ensure_ascii=False).replace('</', '<\\/')

    logo_uri = logo_data_uri()

    # Build the complete HTML document
    # Note: curly braces that belong to CSS/JS are doubled ({{ }}) because this is an f-string
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{config['name']} — Workforce Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
@page {{ size: letter portrait; margin: 0.65in 0.7in; }}
* {{ margin:0; padding:0; box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
body {{ font-family:-apple-system,'Helvetica Neue',Arial,sans-serif; font-size:10pt; color:#1f2937; background:#fff; line-height:1.5; }}
.cover {{ display:flex; justify-content:space-between; align-items:flex-start; padding-bottom:16pt; border-bottom:1.5pt solid #e5e7eb; margin-bottom:18pt; }}
.cover-text {{ flex:1; }}
.cover-logo img {{ height:56pt; width:auto; display:block; }}
.clabel {{ font-size:7pt; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:{acc}; margin-bottom:8pt; display:flex; align-items:center; gap:6pt; }}
.clabel::before {{ content:''; display:inline-block; width:14pt; height:1.5pt; background:{acc}; border-radius:1pt; }}
.cover h1 {{ font-size:24pt; font-weight:700; color:#111827; letter-spacing:-.03em; line-height:1.1; margin-bottom:4pt; }}
.cover .sub {{ font-size:9pt; color:#6b7280; }}
.narrative {{ font-size:9.5pt; color:#374151; margin-bottom:18pt; line-height:1.65; }}
.narrative strong, .narrative .stat {{ color:#111827; font-weight:600; }}
.krow {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8pt; margin-bottom:22pt; page-break-inside:avoid; }}
.kcard {{ background:#f9fafb; border:.5pt solid #e5e7eb; border-radius:5pt; padding:10pt 12pt; }}
.klbl {{ font-size:6pt; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:#6b7280; margin-bottom:6pt; }}
.kval {{ font-size:18pt; font-weight:700; letter-spacing:-.03em; color:#111827; line-height:1; }}
.kval.ind {{ color:{acc}; }}
.ksub {{ font-size:6.5pt; color:#9ca3af; margin-top:4pt; }}
.section {{ margin-bottom:20pt; page-break-inside:avoid; }}
.stitle {{ font-size:11pt; font-weight:700; color:#111827; margin-bottom:3pt; }}
.ssub {{ font-size:8pt; color:#6b7280; margin-bottom:8pt; line-height:1.5; }}
.cbox {{ background:#f9fafb; border:.5pt solid #e5e7eb; border-radius:5pt; padding:12pt; overflow:hidden; }}
.dw {{ display:flex; gap:18pt; align-items:flex-start; }}
.dc {{ flex-shrink:0; }}
.dl {{ flex:1; display:flex; flex-direction:column; gap:4pt; align-content:start; padding-top:8pt; }}
.li {{ display:flex; align-items:center; gap:6pt; }}
.li.hl .ln {{ color:#111827; font-weight:600; }}
.dot {{ width:9pt; height:9pt; border-radius:50%; flex-shrink:0; }}
.ln {{ font-size:9pt; color:#6b7280; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.lp {{ font-size:9pt; font-weight:600; white-space:nowrap; }}
canvas {{ display:block; }}
</style>
</head>
<body>

<div class="cover">
  <div class="cover-text">
    <div class="clabel">{config['naicsLabel']} · Industry Report</div>
    <h1>{config['name']}</h1>
    <p class="sub">Macon-Bibb County Workforce Analysis</p>
  </div>
  <div class="cover-logo"><img src="{logo_uri}" alt="Greater Macon Chamber of Commerce"></div>
</div>

<p class="narrative">{narrative}</p>

<div class="krow">
  <div class="kcard">
    <div class="klbl">Total Employed</div>
    <div class="kval ind">{fmt_num(d['ind_empl'])}</div>
    <div class="ksub">workers in this sector</div>
  </div>
  <div class="kcard">
    <div class="klbl">Share of Job Market</div>
    <div class="kval ind">{d['share']:.1f}%</div>
    <div class="ksub">of all local employment</div>
  </div>
  <div class="kcard">
    <div class="klbl">Average Annual Wage</div>
    <div class="kval">{fmt_dollar(round(d['avg_wage']))}</div>
    <div class="ksub">across all sub-sectors</div>
  </div>
  <div class="kcard">
    <div class="klbl">Projected Annual Openings</div>
    <div class="kval">{fmt_num(d['ind_demand'])}</div>
    <div class="ksub">total demand openings</div>
  </div>
</div>

<div class="section">
  <div class="stitle">Share of the Local Economy</div>
  <p class="ssub">Employment distribution across all major sectors. {d['short_name']} is highlighted.</p>
  <div class="cbox">
    <div class="dw">
      <div class="dc"><canvas id="cd" width="420" height="420"></canvas></div>
      <div class="dl">{legend_html}</div>
    </div>
  </div>
</div>

{empl_section()}{wage_section()}{demand_section()}

<script>
(function() {{
var D = {payload};

function toNum(v) {{ var n = parseFloat(v); return isNaN(n) ? 0 : n; }}
function fmtNum(n) {{ if (n>=1e6) return (n/1e6).toFixed(1)+'M'; if (n>=1e3) return (n/1e3).toFixed(1)+'K'; return Math.round(n).toLocaleString(); }}
function fmtDollar(n) {{ if (n>=1e6) return '$'+(n/1e6).toFixed(1)+'M'; if (n>=1e3) return '$'+Math.round(n/1e3)+'K'; return '$'+Math.round(n).toLocaleString(); }}
function trunc(s, l) {{ return s && s.length > l ? s.slice(0, l-1) + '…' : s; }}
function fade(hex, a) {{ var rv=parseInt(hex.slice(1,3),16), gv=parseInt(hex.slice(3,5),16), bv=parseInt(hex.slice(5,7),16); return 'rgba('+rv+','+gv+','+bv+','+a+')'; }}

    Chart.defaults.color = '#6b7280';
    Chart.defaults.font.size = 10;
    var acc = D.acc, r = D.r, g = D.g, b = D.b, st = D.sector_total;

    // Doughnut
    new Chart(document.getElementById('cd'), {{
      type: 'doughnut',
      data: {{
        labels: D.sectors_sorted.map(function(x) {{ return x[0]; }}),
        datasets: [{{ data: D.sectors_sorted.map(function(x) {{ return x[1]; }}), backgroundColor: D.d_colors, borderColor: '#fff', borderWidth: 2 }}]
      }},
      options: {{
        animation: false, responsive: false, maintainAspectRatio: true, cutout: '60%',
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ enabled: false }},
          datalabels: {{
            display: true,
            clamp: false,
            clip: false,
            formatter: function(v, ctx) {{
              var share = (v / st) * 100;
              var pct   = share.toFixed(1) + '%';
              var clr   = ctx.chart.data.datasets[0].backgroundColor[ctx.dataIndex];
              var lbl   = ctx.chart.data.labels[ctx.dataIndex];
              var name  = D.naics_names[lbl] || lbl;
              if (clr === acc) return name + '\\n' + pct;
              if (share >= 5)  return name + '\\n' + pct;
              return pct;
            }},
            color: function(ctx) {{
              return ctx.chart.data.datasets[0].backgroundColor[ctx.dataIndex] === acc ? '#fff' : '#1f2937';
            }},
            font: function(ctx) {{
              var share = ctx.dataset.data[ctx.dataIndex] / st * 100;
              return {{ size: share >= 5 ? 10 : 8.5, weight: '600' }};
            }},
            textAlign: 'center'
          }}
        }}
      }},
      plugins: [ChartDataLabels]
    }});

    // Employment
    var ceEl = document.getElementById('ce');
    if (ceEl) {{
      var ec = D.empl_rows.map(function(_, i) {{ return 'rgba('+r+','+g+','+b+','+(0.85-(i/D.empl_rows.length)*0.45)+')'; }});
      new Chart(ceEl, {{
        type: 'bar',
        data: {{ labels: D.empl_rows.map(function(x) {{ return trunc(x.Industry, 44); }}), datasets: [{{ data: D.empl_rows.map(function(x) {{ return toNum(x.Empl); }}), backgroundColor: ec, borderWidth: 0, barPercentage: 0.72, categoryPercentage: 1 }}] }},
        options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 58, top: 4, bottom: 4 }} }}, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: fmtNum }} }}, scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
        plugins: [ChartDataLabels]
      }});
    }}

    // Wage
    var cwEl = document.getElementById('cw');
    if (cwEl) {{
      var wc = D.wage_rows.map(function(_, i) {{ return i < D.wage_top_len ? fade(acc, 0.8) : fade('#f59e0b', 0.8); }});
      new Chart(cwEl, {{
        type: 'bar',
        data: {{ labels: D.wage_rows.map(function(x) {{ return trunc(x.Industry, 44); }}), datasets: [{{ data: D.wage_rows.map(function(x) {{ return toNum(x['Avg Ann Wages']); }}), backgroundColor: wc, borderWidth: 0, barPercentage: 0.72, categoryPercentage: 1 }}] }},
        options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 68, top: 4, bottom: 4 }} }}, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: function(ctx) {{ return ctx.dataIndex < D.wage_top_len ? acc : '#f59e0b'; }}, font: {{ size: 9, weight: '600' }}, formatter: fmtDollar }} }}, scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
        plugins: [ChartDataLabels]
      }});
    }}

    // Demand
    var cd2El = document.getElementById('cd2');
    if (cd2El) {{
      var dc = D.demand_rows.map(function(_, i) {{ return 'rgba('+r+','+g+','+b+','+(0.75-(i/D.demand_rows.length)*0.35)+')'; }});
      new Chart(cd2El, {{
        type: 'bar',
        data: {{ labels: D.demand_rows.map(function(x) {{ return trunc(x.Industry, 44); }}), datasets: [{{ data: D.demand_rows.map(function(x) {{ return toNum(x['Total Demand']); }}), backgroundColor: dc, borderWidth: 0, barPercentage: 0.72, categoryPercentage: 1 }}] }},
        options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 48, top: 4, bottom: 4 }} }}, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: fmtNum }} }}, scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
        plugins: [ChartDataLabels]
      }});
    }}

    // Signal to Playwright that all charts are built
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
                footer_template='''<div style="width:100%;font-size:7pt;color:#9ca3af;font-family:-apple-system,Arial,sans-serif;
                    display:flex;justify-content:space-between;align-items:center;
                    border-top:0.5pt solid #e5e7eb;padding-top:3pt;margin:0 0.7in;box-sizing:border-box;">
                    <span>Source: JobsEQ, Q3 2025 &nbsp;·&nbsp; Macon-Bibb County, GA</span>
                    <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
                </div>''',
                margin={'top': '0.65in', 'bottom': '0.65in', 'left': '0.7in', 'right': '0.7in'},
            )
            await browser.close()
    finally:
        tmp_path.unlink(missing_ok=True)


async def generate(industry_ids):
    script_dir = Path(__file__).parent
    csv_path   = script_dir / 'Data' / 'processed' / 'Industry_Snapshot.csv'

    if not csv_path.exists():
        print(f'Error: data file not found at {csv_path}')
        sys.exit(1)

    rows       = load_csv(csv_path)
    output_dir = script_dir / 'reports' / 'pdf'
    output_dir.mkdir(parents=True, exist_ok=True)

    for ind_id in industry_ids:
        if ind_id not in INDUSTRIES:
            print(f'Unknown industry ID: {ind_id}  (valid: {", ".join(INDUSTRIES)})')
            continue
        name = INDUSTRIES[ind_id]['name']
        print(f'  {ind_id}  {name}...', end=' ', flush=True)
        try:
            html = build_html(ind_id, rows)
            out  = output_dir / f'{ind_id}.pdf'
            await render_pdf(html, out)
            print(f'→ {out.relative_to(script_dir)}')
        except Exception as e:
            print(f'ERROR: {e}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ids = list(INDUSTRIES.keys()) if sys.argv[1] == 'all' else sys.argv[1:]
    print(f'Generating {len(ids)} report(s)...')
    asyncio.run(generate(ids))
