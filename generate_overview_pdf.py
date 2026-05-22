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

def load_logo_png(path):
    """Convert webp to PNG, crop transparent padding, return data URI."""
    try:
        from PIL import Image
        import io, numpy as np
        img = Image.open(path).convert('RGBA')
        arr = np.array(img)
        alpha = arr[:, :, 3]
        rows = np.where(alpha.max(axis=1) > 0)[0]
        cols = np.where(alpha.max(axis=0) > 0)[0]
        img = img.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        data = base64.b64encode(buf.getvalue()).decode('ascii')
        return f'data:image/png;base64,{data}'
    except Exception:
        return None

def wrap_label(s, max_per_line=20):
    """Split label at word boundaries into ≤2 lines. Returns str or [str, str]."""
    if len(s) <= max_per_line:
        return s
    words = s.split()
    line1 = []
    for i, w in enumerate(words):
        if len(' '.join(line1 + [w])) <= max_per_line:
            line1.append(w)
        else:
            line2 = ' '.join(words[i:])
            if len(line2) > max_per_line:
                line2 = line2[:max_per_line - 1] + '…'
            return [' '.join(line1), line2] if line1 else s
    return ' '.join(line1)

def build_soc_groups(snap_rows, metric, min_empl=50):
    base = [r for r in snap_rows if not r.get('SOC', '').endswith('00')]
    groups = {}
    for r in base:
        code = r['SOC'][:6]
        empl = to_num(r.get('Empl', 0))
        if code not in groups:
            groups[code] = {'empl': 0.0, 'wsum': 0.0, 'first_name': r.get('Occupation', code)}
        groups[code]['empl'] += empl
        groups[code]['wsum'] += empl * to_num(r.get(metric, 0))
    return [
        {'label': g['first_name'], 'v': g['wsum'] / g['empl'] if g['empl'] else 0.0}
        for g in groups.values() if g['empl'] >= min_empl
    ]

# ── Data processing ────────────────────────────────────────────────────────

def process(ind_rows, occ_rows, pop_rows, comm_rows):
    data_rows = [r for r in ind_rows if (r.get('NAICS') or '').strip()]

    # Total employment and wage from the summary row
    total_row = next((r for r in ind_rows if not (r.get('NAICS') or '').strip()), {})
    total_jobs = round(to_num(total_row.get('Empl', 0)))
    avg_wage   = round(to_num(total_row.get('Avg Ann Wages', 0)))

    # Industry employment totals + 5-year changes + wage sums
    industry_totals   = {}
    industry_changes  = {}
    industry_wage_num = {}
    for r in data_rows:
        naics  = (r.get('NAICS') or '').strip()
        empl   = to_num(r.get('Empl', 0))
        change = to_num(r.get('Empl Change', 0))
        wage   = to_num(r.get('Avg Ann Wages', 0))
        for iid, cfg in INDUSTRIES.items():
            if any(naics.startswith(p) for p in cfg['prefixes']):
                industry_totals[iid]   = industry_totals.get(iid, 0)   + empl
                industry_changes[iid]  = industry_changes.get(iid, 0)  + change
                industry_wage_num[iid] = industry_wage_num.get(iid, 0) + empl * wage
                break

    def _sector(iid):
        empl   = industry_totals.get(iid, 0)
        change = industry_changes.get(iid, 0)
        prior  = empl - change
        return {
            'empl':       round(empl),
            'jobs_added': round(change),
            'growth_pct': round((change / prior) * 100, 1) if prior > 0 else 0,
            'avg_wage':   round(industry_wage_num.get(iid, 0) / empl) if empl else 0,
        }

    industries_sorted = sorted(
        [{'id': iid, 'name': INDUSTRIES[iid]['name'], 'empl': round(v), 'color': INDUSTRIES[iid]['color']}
         for iid, v in industry_totals.items() if v > 0],
        key=lambda x: -x['empl']
    )

    # Top industry name + 5-year growth
    top_industry = industries_sorted[0]['name'] if industries_sorted else '—'
    top_industry_growth_pct  = None
    top_industry_jobs_added  = None
    if industries_sorted:
        iid   = industries_sorted[0]['id']
        curr  = industry_totals.get(iid, 0)
        chg   = industry_changes.get(iid, 0)
        prior = curr - chg
        if prior > 0 and chg != 0:
            top_industry_growth_pct = round((chg / prior) * 100, 1)
            top_industry_jobs_added = round(chg)

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

    # Top occupations (exclude summary/total rows)
    top_occ = sorted(
        [r for r in occ_rows
         if to_num(r.get('Empl', 0)) > 0
         and not r.get('SOC', '').endswith('00')
         and 'total' not in r.get('Occupation', '').lower()],
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

    # Page 4 — Occupation Intelligence charts
    soc_growth_groups = build_soc_groups(occ_rows, 'Ann % Growth', min_empl=50)
    p4_growth = [{'label': wrap_label(g['label'], 25), 'v': round(g['v'], 4)}
                 for g in sorted([g for g in soc_growth_groups if g['v'] > 0], key=lambda x: -x['v'])[:8]]

    p4_wages = [{'label': wrap_label(g['label'], 25), 'v': round(g['v'])}
                for g in sorted(
                    [{'label': r.get('Occupation', ''), 'v': to_num(r.get('Mean Ann Wages2', 0))}
                     for r in occ_rows
                     if to_num(r.get('Mean Ann Wages2', 0)) > 0 and not r.get('SOC', '').endswith('00')],
                    key=lambda x: -x['v'])[:8]]

    base_no_total = [r for r in occ_rows
                     if not r.get('SOC', '').endswith('00')
                     and 'total' not in r.get('Occupation', '').lower()]
    p4_exits = [{'label': wrap_label(r.get('Occupation', ''), 18), 'v': round(to_num(r.get('Exits', 0)))}
                for r in sorted(base_no_total, key=lambda r: -to_num(r.get('Exits', 0)))[:5]
                if to_num(r.get('Exits', 0)) > 0]
    p4_transfers = [{'label': wrap_label(r.get('Occupation', ''), 18), 'v': round(to_num(r.get('Transfers', 0)))}
                    for r in sorted(base_no_total, key=lambda r: -to_num(r.get('Transfers', 0)))[:5]
                    if to_num(r.get('Transfers', 0)) > 0]
    p4_net = [{'label': wrap_label(r.get('Occupation', ''), 18), 'v': round(to_num(r.get('Empl Growth', 0)))}
              for r in sorted(base_no_total, key=lambda r: -to_num(r.get('Empl Growth', 0)))[:5]
              if to_num(r.get('Empl Growth', 0)) > 0]

    return {
        'total_jobs':         total_jobs,
        'avg_wage':           avg_wage,
        'population':         round(bibb_pop),
        'net_commuters':      round(bibb_comm),
        'top_industry':       top_industry,
        'industries_sorted':  industries_sorted,
        'surrounding':        surrounding,
        'top_occ':            top_occ,
        'comm_map_data':           comm_map_data,
        'pop_map_data':            pop_map_data,
        'top_industry_growth_pct': top_industry_growth_pct,
        'top_industry_jobs_added': top_industry_jobs_added,
        'healthcare':              _sector('62'),
        'manufacturing':           _sector('31'),
        'p4_growth':          p4_growth,
        'p4_wages':           p4_wages,
        'p4_exits':           p4_exits,
        'p4_transfers':       p4_transfers,
        'p4_net':             p4_net,
    }

# ── Occupation table HTML ──────────────────────────────────────────────────

def build_occ_table(occ_rows):
    th  = 'padding:4pt 7pt;text-align:left;font-size:7pt;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;white-space:nowrap;border-bottom:1pt solid #e5e7eb;'
    td  = 'padding:4pt 7pt;font-size:7.5pt;border-bottom:0.5pt solid #f3f4f6;'
    header = (f'<tr>'
              f'<th style="{th}">#</th>'
              f'<th style="{th}">Occupation</th>'
              f'<th style="{th};text-align:right">Employment</th>'
              f'<th style="{th};text-align:right">Avg Annual Wage</th>'
              f'<th style="{th};text-align:right">5-Yr Growth</th>'
              f'</tr>')
    rows_html = ''
    for i, r in enumerate(occ_rows):
        wage  = to_num(r.get('Mean Ann Wages2', 0))
        ann   = to_num(r.get('Ann %', 0)) * 100
        g_str = f'{ann:+.1f}%'
        g_col = '#059669' if ann > 0 else ('#dc2626' if ann < 0 else '#9ca3af')
        rows_html += (f'<tr>'
                      f'<td style="{td}color:#9ca3af">{i+1}</td>'
                      f'<td style="{td}font-weight:500">{r.get("Occupation","")}</td>'
                      f'<td style="{td}text-align:right">{fmt_num(to_num(r.get("Empl",0)))}</td>'
                      f'<td style="{td}text-align:right">{fmt_dollar(wage) if wage > 0 else "—"}</td>'
                      f'<td style="{td}text-align:right;font-weight:600;color:{g_col}">{g_str}</td>'
                      f'</tr>')
    return f'<table style="width:100%;border-collapse:collapse;"><thead>{header}</thead><tbody>{rows_html}</tbody></table>'

# ── HTML template ──────────────────────────────────────────────────────────

def build_html(d, geo_json_str, logo_uri=None):
    ind_labels  = json.dumps([x['name']  for x in d['industries_sorted']])
    ind_empls   = json.dumps([x['empl']  for x in d['industries_sorted']])
    ind_colors  = json.dumps([x['color'] for x in d['industries_sorted']])
    comm_map_json = json.dumps(d['comm_map_data'])
    pop_map_json  = json.dumps(d['pop_map_data'])
    occ_table   = build_occ_table(d['top_occ'][:10])

    # Demographics hardcoded from 2024 ACS
    age_labels  = json.dumps(['Under 18','18–24','25–34','35–44','45–54','55–64','65–74','75+'])
    age_vals    = json.dumps([24.4, 9.5, 14.1, 12.1, 11.3, 12.3, 9.9, 6.6])
    race_labels = json.dumps(['Black / African Am.','White','Hispanic / Latino','Two+ Races','Asian','Other'])
    race_vals   = json.dumps([54.9, 35.3, 4.7, 4.6, 2.3, 2.9])
    edu_labels  = json.dumps(['Postgraduate',"Bachelor's","Associate's",'Some College','High School','No Diploma'])
    edu_vals    = json.dumps([13.3, 13.9, 9.0, 22.2, 30.4, 11.2])

    demo_h = 155
    p4_growth_json    = json.dumps(d.get('p4_growth', []))
    p4_wages_json     = json.dumps(d.get('p4_wages', []))
    p4_exits_json     = json.dumps(d.get('p4_exits', []))
    p4_transfers_json = json.dumps(d.get('p4_transfers', []))
    p4_net_json       = json.dumps(d.get('p4_net', []))

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
  .content {{ padding: 0.42in 0.32in; }}

  /* Page 1 header */
  .pg1-header {{
    border-bottom: 1.5pt solid #e5e7eb; padding-bottom: 14pt; margin-bottom: 16pt;
    font-size: 0;
  }}
  .pg1-header-text {{
    display: inline-block; vertical-align: top;
    width: calc(100% - 160pt); font-size: initial;
  }}
  .pg1-header-logo {{
    display: inline-block; vertical-align: top;
    width: 150pt; text-align: right; font-size: initial;
  }}
  .pg1-eyebrow {{
    font-size: 6.5pt; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; color: #059669; margin-bottom: 4pt;
  }}
  .pg1-title {{
    font-size: 26pt; font-weight: 700; letter-spacing: -0.03em;
    color: #111827; line-height: 1.0; margin-bottom: 5pt;
  }}
  .pg1-sub {{
    font-size: 8.5pt; color: #6b7280; max-width: 4.2in; line-height: 1.6;
  }}
  .pg1-date {{
    font-size: 7.5pt; color: #9ca3af; text-align: right; white-space: nowrap;
    padding-top: 4pt;
  }}

  /* Fast facts */
  .ff-grid {{
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 9pt; margin-bottom: 16pt;
  }}
  .ff-card {{
    background: #f9fafb; border: 1pt solid #e5e7eb;
    border-radius: 6pt; padding: 11pt 12pt;
  }}
  .ff-val {{
    font-size: 16pt; font-weight: 700; letter-spacing: -0.03em;
    color: #111827; line-height: 1; margin-bottom: 4pt;
  }}
  .ff-label {{
    font-size: 5.5pt; font-weight: 600; letter-spacing: 0.09em;
    text-transform: uppercase; color: #9ca3af; margin-bottom: 3pt;
  }}
  .ff-note {{
    font-size: 5pt; color: #6b7280; line-height: 1.4;
  }}

  /* Shared section elements */
  .stag {{
    display: inline-block; font-size: 6.5pt; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: #4f46e5; border: 1pt solid #e0e7ff;
    background: #eef2ff; border-radius: 3pt; padding: 1pt 5pt;
    margin-bottom: 5pt;
  }}
  .stag.teal {{ color: #059669; border-color: #d1fae5; background: #ecfdf5; }}
  .stag.orange {{ color: #d97706; border-color: #fde68a; background: #fffbeb; }}
  .section-title {{
    font-size: 14pt; font-weight: 700; letter-spacing: -0.02em;
    color: #111827; margin-bottom: 3pt; line-height: 1.2;
  }}
  .section-sub {{
    font-size: 7.5pt; color: #6b7280; margin-bottom: 12pt; line-height: 1.6;
  }}
  .sdiv {{
    font-size: 7pt; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #9ca3af;
    border-top: 1pt solid #e5e7eb; padding-top: 7pt; margin: 14pt 0 9pt;
  }}
  .cbox {{ background: #f9fafb; border: 1pt solid #e5e7eb; border-radius: 6pt; padding: 10pt; }}

  /* Page 2 stat cards */
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 9pt; margin-bottom: 14pt; }}
  .stat-card {{ background: #f9fafb; border: 1pt solid #e5e7eb; border-radius: 6pt; padding: 11pt; }}
  .stat-val {{ font-size: 15pt; font-weight: 700; color: #111827; letter-spacing: -0.02em; }}
  .stat-key {{ font-size: 6.5pt; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 3pt; }}

  /* Demographics */
  .demo-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 10pt; }}
  .demo-card {{ background: #f9fafb; border: 1pt solid #e5e7eb; border-radius: 6pt; padding: 10pt; }}
  .demo-title {{ font-size: 7pt; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #9ca3af; margin-bottom: 8pt; border-bottom: 1pt solid #e5e7eb; padding-bottom: 5pt; }}
</style>
</head>
<body>

<!-- ══ PAGE 1: Overview + Map ══════════════════════════════ -->
<div class="page content">

  <!-- Header -->
  <div class="pg1-header">
    <div class="pg1-header-text">
      <div class="pg1-eyebrow">Economic Overview · Macon-Bibb County, Georgia</div>
      <div class="pg1-title">Macon-Bibb County</div>
      <p class="pg1-sub" style="margin:0;">Central Georgia's regional economic hub — a diverse workforce at the intersection of major transportation corridors, anchored by healthcare, public services, and growing industry.</p>
    </div><div class="pg1-header-logo">{'<img src="' + logo_uri + '" style="height:34pt;width:auto;" />' if logo_uri else ''}</div>
  </div>

  <!-- Fast facts -->
  <div class="ff-grid">
    <div class="ff-card">
      <div class="ff-val">{fmt_num(d['total_jobs'])}</div>
      <div class="ff-label">Total Jobs</div>
      <div class="ff-note">Payroll positions (QCEW) — counts jobs, not unique workers</div>
    </div>
    <div class="ff-card">
      <div class="ff-val">{fmt_dollar(d['avg_wage'])}</div>
      <div class="ff-label">Avg Annual Wage</div>
      <div class="ff-note">Mean payroll wage per job · not household income</div>
    </div>
    <div class="ff-card">
      <div class="ff-val">{fmt_num(d['population'])}</div>
      <div class="ff-label">Population</div>
      <div class="ff-note">ACS 2024 estimate · residents, not workforce</div>
    </div>
    <div class="ff-card">
      <div class="ff-val">+{d['net_commuters']:,}</div>
      <div class="ff-label">Net In-Commuters</div>
      <div class="ff-note">Workers entering Bibb minus residents leaving daily</div>
    </div>
    <div class="ff-card">
      <div class="ff-val" style="font-size:10pt;line-height:1.3;">{d['top_industry']}</div>
      <div class="ff-label">Largest Sector</div>
      {f'<div class="ff-note" style="color:#059669;font-weight:600;">+{d["top_industry_growth_pct"]}% job growth over 5 years</div>' if d.get('top_industry_growth_pct') and d['top_industry_growth_pct'] > 0 else ''}
    </div>
  </div>

  <!-- Regional map (full width) -->
  <div id="map-wrap" style="background:#f8fafc;border-radius:6pt;overflow:hidden;border:1pt solid #e5e7eb;">
    <svg id="map-svg" style="display:block;"></svg>
  </div>
  <p style="font-size:6.5pt;color:#9ca3af;margin-top:6pt;">Source: JobsEQ net commuting data · Macon-Bibb County, GA · U.S. Census Bureau Population Estimates</p>

</div>

<!-- ══ PAGE 2: Economic Picture + Who Lives Here ═══════════ -->
<div class="page content">

  <!-- Adjusted metrics -->
  <div class="stag teal">The Real Economic Picture</div>
  <div class="section-title">Workplace-Adjusted Metrics</div>
  <p class="section-sub">About 40% of workers employed in Macon-Bibb live outside it. Standard Census metrics follow the worker home — understating the county's income and overstating its neighbors'. The figures below are adjusted for where the work actually happens. This pattern exists because Macon-Bibb is the region's economic hub: the hospitals, professional offices, and major employers that surrounding rural counties rely on are here, so the workers come here too. Note also that the $55K average annual wage on page 1 reflects payroll jobs located here; the $50,747 household median below reflects where residents live — different populations, different measures.</p>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:9pt;margin-bottom:10pt;">
    <div class="stat-card">
      <div style="font-size:6.5pt;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#9ca3af;margin-bottom:7pt;border-bottom:1pt solid #e5e7eb;padding-bottom:4pt;">Median Earnings — Job Site vs. Residence</div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5pt;">
        <span style="font-size:6.5pt;color:#6b7280;">Adjusted (job-site)</span>
        <span style="font-size:14pt;font-weight:700;color:#059669;letter-spacing:-.02em;">$68,900</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-size:6.5pt;color:#6b7280;">Official household median</span>
        <span style="font-size:10pt;font-weight:600;color:#9ca3af;">$50,747</span>
      </div>
    </div>
    <div class="stat-card">
      <div style="font-size:6.5pt;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#9ca3af;margin-bottom:7pt;border-bottom:1pt solid #e5e7eb;padding-bottom:4pt;">Per-Capita GDP — Macon-Bibb vs. Houston Co.</div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5pt;">
        <span style="font-size:6.5pt;color:#6b7280;">Macon-Bibb (workplace)</span>
        <span style="font-size:14pt;font-weight:700;color:#059669;letter-spacing:-.02em;">$67,292</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-size:6.5pt;color:#6b7280;">Houston Co. (adjusted)</span>
        <span style="font-size:10pt;font-weight:600;color:#9ca3af;">$54,547</span>
      </div>
    </div>
    <div class="stat-card">
      <div style="font-size:6.5pt;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:#9ca3af;margin-bottom:7pt;border-bottom:1pt solid #e5e7eb;padding-bottom:4pt;">Unemployment — Workplace-Weighted vs. Official</div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5pt;">
        <span style="font-size:6.5pt;color:#6b7280;">Adjusted Unemployment</span>
        <span style="font-size:14pt;font-weight:700;color:#059669;letter-spacing:-.02em;">3.2%</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-size:6.5pt;color:#6b7280;">Official residence-based</span>
        <span style="font-size:10pt;font-weight:600;color:#9ca3af;">4.3%</span>
      </div>
    </div>
  </div>

  <div style="margin-bottom:10pt;">
    <div class="stat-card" style="border-left:3pt solid #059669;">
      <div style="font-size:18pt;font-weight:700;color:#059669;letter-spacing:-.03em;line-height:1;margin-bottom:3pt;">60–70%</div>
      <div style="font-size:7pt;color:#6b7280;line-height:1.5;">of retail spending in Macon-Bibb originates from <strong style="color:#374151;">non-residents</strong> — commuters and regional visitors whose wages are earned here but counted elsewhere in Census data.</div>
    </div>
  </div>
  <div style="font-size:6.5pt;color:#9ca3af;border-top:1pt solid #e5e7eb;padding-top:8pt;margin-bottom:16pt;">
    Source: George, A. (2025). <em>Reclassifying Municipal Realities</em> (commissioned research). U.S. Census, BLS, LEHD/LODES, BEA.
  </div>

  <!-- Demographics -->
  <div class="stag orange">Workforce Demographics</div>
  <div class="section-title">Who Lives Here</div>
  <p class="section-sub">ACS 2024 estimates for Macon-Bibb County residents.</p>

  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-val">{d['population']:,}</div>
      <div class="stat-key">Population</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">77.0%</div>
      <div class="stat-key">Prime-Age Participation · Ages 25–54</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">35 yrs</div>
      <div class="stat-key">Median Age</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">9.5%</div>
      <div class="stat-key">Work From Home</div>
    </div>
  </div>

  <div class="demo-grid">
    <div class="demo-card">
      <div class="demo-title">Age Distribution</div>
      <canvas id="cage" width="185" height="{demo_h}"></canvas>
    </div>
    <div class="demo-card">
      <div class="demo-title">Race &amp; Ethnicity</div>
      <canvas id="crace" width="185" height="{demo_h}"></canvas>
    </div>
    <div class="demo-card">
      <div class="demo-title">Education (Age 25–64)</div>
      <canvas id="cedu" width="185" height="{demo_h}"></canvas>
    </div>
  </div>

</div>

<!-- ══ PAGE 3: Where Macon Works ═══════════════════════════ -->
<div class="page content">

  <div class="stag">Industry Landscape</div>
  <div class="section-title" style="margin-bottom:4pt;">Where Macon Works</div>
  <p class="section-sub" style="margin-bottom:10pt;">Macon-Bibb's economy is anchored by high-value service and production sectors. Healthcare and Manufacturing alone account for nearly {fmt_num(d['healthcare']['empl'] + d['manufacturing']['empl'])} jobs — and together have added more than {fmt_num(d['healthcare']['jobs_added'] + d['manufacturing']['jobs_added'])} positions over the past five years.</p>

  <!-- Healthcare fast facts row -->
  <div style="font-size:6.5pt;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#059669;margin-bottom:5pt;">Healthcare &amp; Social Assistance</div>
  <div class="ff-grid" style="margin-bottom:8pt;">
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;">{fmt_num(d['healthcare']['empl'])}</div>
      <div class="ff-label">Total Jobs</div>
      <div class="ff-note">Largest sector</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;color:#059669;">+{d['healthcare']['growth_pct']}%</div>
      <div class="ff-label">5-Yr Employment Growth</div>
      <div class="ff-note">5-yr cumulative · JobsEQ</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;">+{fmt_num(d['healthcare']['jobs_added'])}</div>
      <div class="ff-label">Jobs Added · 5 Yrs</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;">{fmt_dollar(d['healthcare']['avg_wage'])}</div>
      <div class="ff-label">Avg Annual Wage</div>
      <div class="ff-note">QCEW · weighted</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:9pt;line-height:1.3;">Largest Sector</div>
      <div class="ff-label">Regional Rank</div>
      <div class="ff-note">Hub anchor</div>
    </div>
  </div>

  <!-- Manufacturing fast facts row -->
  <div style="font-size:6.5pt;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#3b82f6;margin-bottom:5pt;">Manufacturing</div>
  <div class="ff-grid" style="margin-bottom:10pt;">
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;">{fmt_num(d['manufacturing']['empl'])}</div>
      <div class="ff-label">Total Jobs</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;color:#059669;">+{d['manufacturing']['growth_pct']}%</div>
      <div class="ff-label">5-Yr Employment Growth</div>
      <div class="ff-note">Fastest-growing</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;">+{fmt_num(d['manufacturing']['jobs_added'])}</div>
      <div class="ff-label">Jobs Added · 5 Yrs</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:13pt;">{fmt_dollar(d['manufacturing']['avg_wage'])}</div>
      <div class="ff-label">Avg Annual Wage</div>
      <div class="ff-note">QCEW · weighted</div>
    </div>
    <div class="ff-card" style="padding:8pt 10pt;">
      <div class="ff-val" style="font-size:9pt;line-height:1.3;">High-Value Growth</div>
      <div class="ff-label">Sector Profile</div>
      <div class="ff-note">High wage · rising</div>
    </div>
  </div>

  <!-- Donut full-width -->
  <div class="cbox" style="padding:12pt;">
    <canvas id="cind" width="560" height="348" style="display:block;"></canvas>
    <div id="cind-legend" style="margin-top:8pt;"></div>
  </div>

</div>


<!-- ══ PAGE 4: Workforce Outlook ══════════════════════════ -->
<div class="page content">

  <div class="stag teal">Workforce Outlook</div>
  <div class="section-title" style="margin-bottom:4pt;">Occupation Intelligence</div>
  <p class="section-sub" style="margin-bottom:8pt;">High-wage healthcare and professional roles are growing while routine, lower-wage work contracts — a split consistent with automation and structural shifts that together pull the workplace-adjusted median to $68,900.</p>

  <!-- Top Growing + Top Paying charts -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10pt;margin-bottom:8pt;">
    <div class="cbox">
      <div style="font-size:6.5pt;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9ca3af;margin-bottom:4pt;">Top Growing Occupations</div>
      <div style="font-size:6pt;color:#9ca3af;margin-bottom:6pt;">1-year forecast growth rate · min. 50 employees · JobsEQ 2025 Q3</div>
      <canvas id="cp4-growth" width="270" height="207"></canvas>
    </div>
    <div class="cbox">
      <div style="font-size:6.5pt;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9ca3af;margin-bottom:4pt;">Top Paying Jobs</div>
      <div style="font-size:6pt;color:#9ca3af;margin-bottom:6pt;">Mean annual wage · OES estimates</div>
      <canvas id="cp4-wages" width="270" height="207"></canvas>
    </div>
  </div>

  <!-- In-Demand Roles table -->
  <div class="stag teal">Top Occupations</div>
  <div class="section-title" style="margin-bottom:4pt;">In-Demand Roles</div>
  <p class="section-sub" style="margin-bottom:6pt;">Top 10 by employment · Occupational Employment Statistics (OES) · Macon-Bibb County.</p>
  <div class="cbox" style="padding:0;overflow:hidden;">
    {occ_table}
  </div>

  <!-- Closing forward-looking statement -->
  <div style="margin-top:8pt;padding:7pt 12pt;background:#f0fdf4;border-left:3pt solid #059669;border-radius:4pt;page-break-inside:avoid;">
    <div style="font-size:7.5pt;font-weight:700;color:#059669;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4pt;">Outlook</div>
    <p style="font-size:7pt;color:#1e293b;line-height:1.6;margin:0;">Macon-Bibb's workforce is shifting toward higher-value employment — healthcare and professional roles are growing, manufacturing wages are rising, and automation is compressing low-wage routine roles while expanding demand for higher-skill work. A young median age and a growing anchor-employer base position the county for wage growth if training pipelines keep pace with employer demand.</p>
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

  // Industry doughnut
  var indEl = document.getElementById('cind');
  if (indEl) {{
    var allLabels = {ind_labels};
    var allEmpls  = {ind_empls};
    var allColors = {ind_colors};
    var indTotal  = allEmpls.reduce(function(s, v) {{ return s + v; }}, 0);

    // Show any sector >= 3% of total; merge the rest into "Other"
    var dLabels = [], dEmpls = [], dColors = [], otherEmpl = 0;
    for (var i = 0; i < allLabels.length; i++) {{
      if ((allEmpls[i] / indTotal) * 100 >= 3) {{
        dLabels.push(allLabels[i]); dEmpls.push(allEmpls[i]); dColors.push(allColors[i]);
      }} else {{
        otherEmpl += allEmpls[i];
      }}
    }}
    if (otherEmpl > 0) {{
      dLabels.push('Other'); dEmpls.push(otherEmpl); dColors.push('#94a3b8');
    }}

    // Legend — 3-column grid below chart
    var legEl = document.getElementById('cind-legend');
    if (legEl) {{
      legEl.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:3pt 10pt;">'
        + dLabels.map(function(lbl, i) {{
            var pct = ((dEmpls[i] / indTotal) * 100).toFixed(1);
            return '<div style="display:flex;align-items:center;gap:5pt;">'
              + '<span style="display:inline-block;width:8pt;height:8pt;border-radius:2pt;flex-shrink:0;background:' + dColors[i] + '"></span>'
              + '<span style="flex:1;font-size:6.5pt;color:#374151;">' + lbl + '</span>'
              + '<span style="font-size:6.5pt;color:#9ca3af;min-width:30pt;text-align:right;">' + fmtNum(dEmpls[i]) + '</span>'
              + '<span style="font-size:6.5pt;color:#6b7280;min-width:22pt;text-align:right;">' + pct + '%</span>'
              + '</div>';
          }}).join('')
        + '</div>';
    }}

    // Short names for slice labels
    function shortName(s) {{
      return s.replace('Health Care & Social Assistance','Healthcare')
              .replace('Accommodation & Food Services','Accom. & Food')
              .replace('Transportation & Warehousing','Transport & Whsg')
              .replace('Educational Services','Education')
              .replace('Public Administration','Public Admin')
              .replace('Professional & Tech Services','Prof & Tech Services')
              .replace('Administrative & Support','Admin & Support')
              .replace('Management of Companies','Management');
    }}

    new Chart(indEl, {{
      type: 'doughnut',
      data: {{
        labels: dLabels,
        datasets: [{{ data: dEmpls, backgroundColor: dColors, borderColor: '#ffffff', borderWidth: 2 }}],
      }},
      options: {{
        animation: false, responsive: false, maintainAspectRatio: false, cutout: '58%',
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ enabled: false }},
          datalabels: {{
            display: function(ctx) {{
              return (dEmpls[ctx.dataIndex] / indTotal) * 100 >= 4;
            }},
            formatter: function(v, ctx) {{
              var pct = ((v / indTotal) * 100).toFixed(0) + '%';
              return (v / indTotal) * 100 >= 8
                ? shortName(dLabels[ctx.dataIndex]) + '\\n' + pct
                : pct;
            }},
            color: '#1e293b',
            font: {{ size: 7.5, weight: '600' }},
            textAlign: 'center',
          }},
        }},
      }},
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
    var FONT = '-apple-system, Arial, sans-serif';
    var BG   = '#f8fafc';

    var wrap = document.getElementById('map-wrap');
    if (!wrap || typeof d3 === 'undefined') return;

    // W is the internal drawing canvas; SVG is set to width:100% via viewBox
    // so it always fills the container regardless of clientWidth measurement
    var W = 645;
    var H = 460;

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
      if (f === BIBB) return '#2d5a27';
      var comm = commLookup[f]||0;
      if (comm > 0) {{
        var t = comm / (maxPos||1);
        return d3.interpolateRgb('#f0fdf4','#bbf7d0')(t);
      }}
      var t = -comm / (maxNeg||1);
      return d3.interpolateRgb('#fff7ed','#c2410c')(0.15 + t*0.75);
    }}

    var proj = d3.geoAlbers().fitExtent([[28,52],[W-28,H-20]], GEO);
    var path = d3.geoPath().projection(proj);

    var svg = d3.select('#map-svg')
      .attr('viewBox', '0 0 ' + W + ' ' + H)
      .attr('width', '100%')
      .attr('height', H)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    // Background
    svg.append('rect').attr('width',W).attr('height',H).attr('fill',BG);

    // Title bar
    svg.append('rect').attr('width',W).attr('height',48).attr('fill','#fff');
    svg.append('line').attr('x1',0).attr('y1',48).attr('x2',W).attr('y2',48)
      .attr('stroke','#e5e7eb').attr('stroke-width',1);
    svg.append('text').text('Where Central Georgia Works')
      .attr('x',14).attr('y',20).attr('font-size',13).attr('font-weight',700)
      .attr('font-family',FONT).attr('fill','#111827').attr('letter-spacing','-0.02em');
    svg.append('text').text('Net in-commuter flow by county  ·  1-hour drive radius')
      .attr('x',14).attr('y',37).attr('font-size',9)
      .attr('font-family',FONT).attr('fill','#9ca3af');

    // County fills — uniform light border so shared edges stay clean
    svg.append('g').selectAll('path')
      .data(GEO.features).join('path')
      .attr('d', path)
      .attr('fill', function(d) {{ return countyFill(String(d.id).padStart(5,'0')); }})
      .attr('stroke','#e2e8f0').attr('stroke-width',1);

    // Bibb border on top — no bleed into neighbors
    var bibbFeat = GEO.features.find(function(d) {{ return String(d.id).padStart(5,'0') === BIBB; }});
    if (bibbFeat) {{
      svg.append('path').datum(bibbFeat)
        .attr('d', path).attr('fill','none')
        .attr('stroke','#1a3818').attr('stroke-width',2);
    }}

    // County labels
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
          .attr('font-size',12).attr('font-weight',700).attr('fill','#ffffff').attr('font-family',FONT);
        g.append('text').text(popStr).attr('text-anchor','middle').attr('dy','4')
          .attr('font-size',10).attr('fill','#bbf7d0').attr('font-family',FONT);
        g.append('text').text(commStr).attr('text-anchor','middle').attr('dy','18')
          .attr('font-size',9).attr('fill','#86efac').attr('font-family',FONT);
      }} else if (minDim >= 26) {{
        var fs = Math.max(7, Math.min(9, minDim/6));
        g.append('text').text(name).attr('text-anchor','middle').attr('dy', minDim<40?'-2':'-5')
          .attr('font-size',fs).attr('font-weight',600).attr('fill','#1e293b').attr('font-family',FONT);
        g.append('text').text(popStr).attr('text-anchor','middle').attr('dy', minDim<40?'7':'8')
          .attr('font-size',fs-1).attr('fill','#475569').attr('font-family',FONT);
        if (minDim >= 40) {{
          var commColor = comm > 0 ? '#15803d' : '#7c2d12';
          g.append('text').text(commStr).attr('text-anchor','middle').attr('dy','20')
            .attr('font-size',fs-1).attr('fill',commColor).attr('font-family',FONT);
        }}
      }}
    }});

    // SVG stats panel (bottom-left — renders in PDF)
    var totalPop = Object.values(popLookup).reduce(function(s,v){{ return s+v; }}, 0);
    var bibbPop  = popLookup[BIBB] || 0;
    function fmtPop(n) {{ return n>=1000000 ? (n/1000000).toFixed(2)+'M' : Math.round(n/1000)+'K'; }}
    var sW=148, sH=80, sX=12, sY=H-sH-12;
    var sG = svg.append('g').attr('transform','translate('+sX+','+sY+')');
    sG.append('rect').attr('width',sW).attr('height',sH).attr('rx',6)
      .attr('fill','#ffffff').attr('fill-opacity',0.95).attr('stroke','#e5e7eb').attr('stroke-width',1);
    sG.append('text').text(fmtPop(totalPop)).attr('x',12).attr('y',26)
      .attr('font-size',18).attr('font-weight',700).attr('font-family',FONT)
      .attr('fill','#111827').attr('letter-spacing','-0.03em');
    sG.append('text').text('TOTAL REGIONAL POPULATION').attr('x',12).attr('y',38)
      .attr('font-size',7).attr('font-weight',600).attr('font-family',FONT)
      .attr('fill','#9ca3af').attr('letter-spacing','0.05em');
    sG.append('line').attr('x1',12).attr('y1',46).attr('x2',sW-12).attr('y2',46)
      .attr('stroke','#f3f4f6').attr('stroke-width',1);
    sG.append('text').text(fmtPop(bibbPop)).attr('x',12).attr('y',63)
      .attr('font-size',18).attr('font-weight',700).attr('font-family',FONT)
      .attr('fill','#2d5a27').attr('letter-spacing','-0.03em');
    sG.append('text').text('MACON-BIBB POPULATION').attr('x',12).attr('y',75)
      .attr('font-size',7).attr('font-weight',600).attr('font-family',FONT)
      .attr('fill','#9ca3af').attr('letter-spacing','0.05em');

    // SVG legend (bottom-right — renders in PDF)
    var LEG = [
      {{color:'#2d5a27', stroke:'#1a3818', label:'Macon-Bibb County'}},
      {{color:'#c2410c', label:'Negative net commuting'}},
      {{color:'#bbf7d0', label:'Positive net commuting'}},
    ];
    var lW=158, lH=14+LEG.length*18+8, lX=W-lW-12, lY=H-lH-12;
    var lG = svg.append('g').attr('transform','translate('+lX+','+lY+')');
    lG.append('rect').attr('width',lW).attr('height',lH).attr('rx',6)
      .attr('fill','#ffffff').attr('fill-opacity',0.95).attr('stroke','#e5e7eb').attr('stroke-width',1);
    lG.append('text').text('MAP KEY').attr('x',10).attr('y',14)
      .attr('font-size',8).attr('font-weight',700).attr('font-family',FONT)
      .attr('fill','#111827').attr('letter-spacing','0.06em');
    LEG.forEach(function(item,i) {{
      var iy = 22 + i*18;
      lG.append('rect').attr('x',10).attr('y',iy).attr('width',11).attr('height',11).attr('rx',2)
        .attr('fill',item.color)
        .attr('stroke',item.stroke||'none').attr('stroke-width',item.stroke?1:0);
      lG.append('text').text(item.label).attr('x',26).attr('y',iy+8.5)
        .attr('font-size',9.5).attr('font-family',FONT).attr('fill','#6b7280');
    }});
  }})();

  // ── Page 4: Occupation Intelligence ──────────────────────
  var P4_GROWTH    = {p4_growth_json};
  var P4_WAGES     = {p4_wages_json};
  var P4_EXITS     = {p4_exits_json};
  var P4_TRANSFERS = {p4_transfers_json};
  var P4_NET       = {p4_net_json};

  function fmtPct(v) {{ return (v * 100).toFixed(2) + '%'; }}
  function fmtDollar(v) {{ return '$' + (v >= 1000 ? Math.round(v / 1000) + 'K' : Math.round(v).toLocaleString()); }}

  function mkP4Chart(elId, items, fmtFn, color, padRight) {{
    var el = document.getElementById(elId);
    if (!el || !items.length) return;
    new Chart(el, {{
      type: 'bar',
      data: {{
        labels: items.map(function(x) {{ return x.label; }}),
        datasets: [{{ data: items.map(function(x) {{ return x.v; }}), backgroundColor: color, borderWidth: 0, barPercentage: 0.75, categoryPercentage: 1 }}],
      }},
      options: {{
        indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false,
        layout: {{ padding: {{ right: padRight, top: 2, bottom: 2 }} }},
        plugins: {{
          legend: {{ display: false }}, tooltip: {{ enabled: false }},
          datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 7, weight: '500' }}, formatter: fmtFn }},
        }},
        scales: {{
          y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 7 }}, maxRotation: 0 }} }},
          x: {{ display: false }},
        }},
      }},
      plugins: [ChartDataLabels],
    }});
  }}

  mkP4Chart('cp4-growth', P4_GROWTH, fmtPct,    '#2dd4bf', 52);
  mkP4Chart('cp4-wages',  P4_WAGES,  fmtDollar, '#f59e0b', 52);

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
            context = await browser.new_context(device_scale_factor=2)
            page    = await context.new_page()
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
                    <span>Source: JobsEQ 2025 Q3 &nbsp;·&nbsp; QCEW &nbsp;·&nbsp; OES (BLS) &nbsp;·&nbsp; ACS 2024 &nbsp;·&nbsp; Macon-Bibb County, GA</span>
                    <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
                </div>''',
                margin={'top': '0.55in', 'bottom': '0.6in', 'left': '0.55in', 'right': '0.55in'},
            )
            await context.close()
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

    logo_path = script_dir / 'Resources' / '32_greatermacon_531X354.webp'
    logo_uri  = load_logo_png(logo_path) if logo_path.exists() else None

    output_dir = script_dir / 'reports' / 'pdf'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'macon-overview.pdf'

    print('Building Macon Overview PDF...')
    html = build_html(d, geo_json_str, logo_uri)
    await render_pdf(html, output_path)
    print(f'Saved → {output_path}')


if __name__ == '__main__':
    asyncio.run(main())
