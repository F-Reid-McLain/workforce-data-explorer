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

# BLS-based NAICS sector → SOC major group prefixes
NAICS_SOC_GROUPS = {
    '11': ['45','19','11'],
    '21': ['47','17','51'],
    '22': ['17','49','51'],
    '23': ['47','49','17'],
    '31': ['51','17','49','13'],
    '32': ['51','17','49','13'],
    '33': ['51','17','49','13'],
    '42': ['41','43','53','13'],
    '44': ['41','43','35','11'],
    '45': ['41','43','35','11'],
    '48': ['53','49','43'],
    '49': ['53','49','43'],
    '51': ['15','27','43','13'],
    '52': ['13','43','11','15'],
    '53': ['41','13','43'],
    '54': ['13','17','15','19','23'],
    '55': ['11','13','43'],
    '56': ['43','33','37','39'],
    '61': ['25','43','11'],
    '62': ['29','31'],
    '71': ['27','39','43'],
    '72': ['35','39','41','43'],
    '81': ['49','39','37','43'],
    '92': ['33','25','11','43'],
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

# ── Occupation helpers ─────────────────────────────────────────────────────

def process_occupations(industry_id, soc_rows, occ_wage_rows):
    if not soc_rows:
        return [], {}
    sector     = NAICS_MERGE.get(industry_id, industry_id)
    soc_groups = NAICS_SOC_GROUPS.get(sector, [])
    wage_lookup = {(r.get('SOC') or '').strip(): r for r in (occ_wage_rows or [])}
    relevant = [r for r in soc_rows
                if (r.get('SOC') or '').strip()[:2] in soc_groups
                and to_num(r.get('Empl', 0)) > 0]
    relevant.sort(key=lambda r: -to_num(r.get('Empl', 0)))
    return relevant[:10], wage_lookup


def build_occ_table(occ_rows, wage_lookup):
    if not occ_rows:
        return '<p style="font-size:8pt;color:#6b7280;padding:12pt;">No occupation data available for this industry.</p>'

    th_style = 'padding:5pt 9pt;text-align:left;font-size:6.5pt;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#6b7280;white-space:nowrap;'
    head = (
        '<table style="width:100%;border-collapse:collapse;font-size:8.5pt;">'
        '<thead><tr style="border-bottom:1pt solid #e5e7eb;">'
        f'<th style="{th_style}">Occupation</th>'
        f'<th style="{th_style}">SOC</th>'
        f'<th style="{th_style}">Employment</th>'
        f'<th style="{th_style}">Mean Wage</th>'
        f'<th style="{th_style}">Entry → Experienced</th>'
        f'<th style="{th_style}">Openings/yr</th>'
        f'<th style="{th_style}">Macon vs. National</th>'
        '</tr></thead><tbody>'
    )

    rows_html = ''
    for i, r in enumerate(occ_rows):
        soc   = (r.get('SOC') or '').strip()
        w     = wage_lookup.get(soc, {})
        lq    = to_num(r.get('LQ', 0))
        entry = to_num(w.get('Entry Level', 0))
        exp   = to_num(w.get('Experienced', 0))

        if lq >= 1.2:
            lq_style = 'background:#d1fae5;color:#065f46'
        elif lq >= 0.8:
            lq_style = 'background:#fef3c7;color:#92400e'
        else:
            lq_style = 'background:#f3f4f6;color:#6b7280'

        wage_range = f'{fmt_dollar(int(entry))} → {fmt_dollar(int(exp))}' if entry > 0 and exp > 0 else '—'
        bg = '#f9fafb' if i % 2 == 0 else '#fff'
        td = f'padding:4pt 9pt;border-bottom:.5pt solid #e5e7eb;'

        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td style="{td}color:#111827;">{(r.get("Occupation") or "").strip()}</td>'
            f'<td style="{td}color:#6b7280;font-size:7.5pt;font-variant-numeric:tabular-nums;">{soc}</td>'
            f'<td style="{td}color:#374151;">{fmt_num(to_num(r.get("Empl", 0)))}</td>'
            f'<td style="{td}color:#374151;">{fmt_dollar(to_num(r.get("Mean Ann Wages2", 0)))}</td>'
            f'<td style="{td}color:#6b7280;font-size:7.5pt;white-space:nowrap;">{wage_range}</td>'
            f'<td style="{td}color:#374151;">{fmt_num(to_num(r.get("Total Demand", 0)))}</td>'
            f'<td style="{td}"><span style="display:inline-block;padding:2pt 7pt;border-radius:10pt;font-size:7.5pt;font-weight:600;{lq_style}">'
            f'{"N/A" if lq <= 0 else f"{lq:.1f}×"}</span></td>'
            '</tr>'
        )

    return head + rows_html + '</tbody></table>'

def build_radar_metrics_html(radar_data, acc):
    dims = ['Employment Scale', 'Wage Level', 'Economic Impact', 'Job Growth', 'Hiring Activity']
    html = ''
    for label, v in zip(dims, radar_data):
        color = acc if v >= 66 else ('#f59e0b' if v >= 33 else '#9ca3af')
        html += (
            f'<div style="margin-bottom:8pt;">'
            f'<div style="font-size:5.5pt;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:#6b7280;margin-bottom:3pt;">{label}</div>'
            f'<div style="display:flex;align-items:center;gap:6pt;">'
            f'<div style="flex:1;height:2.5pt;background:#e5e7eb;border-radius:2pt;overflow:hidden;">'
            f'<div style="width:{v}%;height:100%;background:{color};"></div></div>'
            f'<div style="font-size:8pt;font-weight:700;color:{color};white-space:nowrap;">{v}'
            f'<span style="font-size:5.5pt;color:#9ca3af;">th</span></div>'
            f'</div></div>'
        )
    return html


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

    # Doughnut — merge sectors below 2.9% threshold into "Other"
    sector_total = sum(v for _, v in sectors_sorted_full)
    threshold    = sector_total * 0.029
    main_sectors = [(c, v) for c, v in sectors_sorted_full if v >= threshold or c == canonical_id]
    other_total  = sum(v for c, v in sectors_sorted_full if v < threshold and c != canonical_id)
    sectors_sorted = main_sectors + ([('other', other_total)] if other_total > 0 else [])

    d_colors = [config['color'] if c == canonical_id else 'hsl(220,8%,74%)'
                for c, _ in sectors_sorted]

    # Employment chart
    empl_rows = sorted([r for r in ind_rows if to_num(r['Empl']) > 0],
                       key=lambda r: -to_num(r['Empl']))[:10]

    # Wage chart
    with_wages = sorted([r for r in ind_rows
                         if to_num(r['Avg Ann Wages']) > 0 and to_num(r['Empl']) > 0],
                        key=lambda r: -to_num(r['Avg Ann Wages']))
    half      = min(10, max(3, len(with_wages) // 2))
    wage_top  = with_wages[:half]
    wage_bot  = list(reversed(with_wages))[:half][::-1]
    top_naics = {r['NAICS'] for r in wage_top}
    wage_rows = wage_top + [r for r in wage_bot if r['NAICS'] not in top_naics]

    # Demand chart
    demand_rows = sorted([r for r in ind_rows if to_num(r['Total Demand']) > 0],
                         key=lambda r: -to_num(r['Total Demand']))[:12]

    # Growth chart (top 5 by net new jobs)
    growth_rows = sorted([r for r in ind_rows if r.get('Empl Growth', '').strip()],
                         key=lambda r: -to_num(r.get('Empl Growth', 0)))[:5]

    # LQ chart (top 8 by location quotient)
    lq_rows = sorted([r for r in ind_rows if to_num(r.get('LQ', 0)) > 0],
                     key=lambda r: -to_num(r.get('LQ', 0)))[:8]

    # Opening sources chart (top 5 by demand — decomposed into exits/transfers/growth)
    sources_rows = sorted([r for r in ind_rows if to_num(r.get('Total Demand', 0)) > 0],
                          key=lambda r: -to_num(r.get('Total Demand', 0)))[:5]

    # Opening rate chart (top 8 by demand/employment ratio)
    rate_rows = sorted(
        [r for r in ind_rows if to_num(r.get('Empl', 0)) > 0 and to_num(r.get('Total Demand', 0)) > 0],
        key=lambda r: -(to_num(r.get('Total Demand', 0)) / to_num(r.get('Empl', 0)))
    )[:8]

    # Radar — percentile rank across all industries for 5 dimensions
    # First pass: regional avg wage for EII normalization (wage premium per job)
    total_wage_bill = 0
    total_all_empl  = 0
    for iid, icfg in INDUSTRIES.items():
        ir = [r for r in rows if r['NAICS'].strip()
              and any(r['NAICS'].strip().startswith(p) for p in icfg['prefixes'])]
        total_wage_bill += sum(to_num(r['Avg Ann Wages']) * to_num(r['Empl']) for r in ir)
        total_all_empl  += sum(to_num(r['Empl']) for r in ir)
    regional_avg_wage_radar = total_wage_bill / total_all_empl if total_all_empl > 0 else 1

    all_metrics = {}
    for iid, icfg in INDUSTRIES.items():
        ir = [r for r in rows if r['NAICS'].strip()
              and any(r['NAICS'].strip().startswith(p) for p in icfg['prefixes'])]
        if not ir:
            continue
        e  = sum(to_num(r['Empl']) for r in ir)
        wn = sum(to_num(r['Avg Ann Wages']) * to_num(r['Empl']) for r in ir)
        wd = sum(to_num(r['Empl']) for r in ir)
        gv = [to_num(r['Ann % Growth']) for r in ir]
        dm = sum(to_num(r['Total Demand']) for r in ir)
        avg_g = sum(gv) / len(gv) if gv else 0
        avg_w = wn / wd if wd > 0 else 0
        # EII = wage premium vs regional baseline × growth multiplier
        eii = (avg_w / regional_avg_wage_radar) * (1 + max(avg_g, -0.5))
        all_metrics[iid] = {
            'share':  e / total_empl * 100 if total_empl > 0 else 0,
            'wage':   avg_w,
            'growth': avg_g,
            'rate':   dm / e * 100 if e > 0 else 0,
            'eii':    eii,
        }

    def pct_rank(key):
        vals = sorted(v[key] for v in all_metrics.values())
        my   = all_metrics.get(industry_id, {}).get(key, 0)
        rank = sum(1 for v in vals if v < my)
        return round(rank / (len(vals) - 1) * 100) if len(vals) > 1 else 50

    radar_data = [
        pct_rank('share'), pct_rank('wage'), pct_rank('eii'),
        pct_rank('growth'), pct_rank('rate'),
    ]

    # EII display value for KPI card
    reg_wage_num = sum(to_num(r['Avg Ann Wages']) * to_num(r['Empl']) for r in rows if r['NAICS'].strip())
    reg_wage_den = sum(to_num(r['Empl']) for r in rows if r['NAICS'].strip())
    regional_avg_wage = reg_wage_num / reg_wage_den if reg_wage_den > 0 else 1
    ind_avg_growth = sum(to_num(r['Ann % Growth']) for r in ind_rows) / len(ind_rows) if ind_rows else 0
    eii_display = (avg_wage / regional_avg_wage) * (1 + max(ind_avg_growth, -0.5))

    return dict(
        config=config,
        ind_empl=ind_empl, ind_demand=ind_demand,
        avg_wage=avg_wage, share=share, rank=rank,
        short_name=short_name,
        sectors_sorted=sectors_sorted, canonical_id=canonical_id,
        sector_total=sector_total, d_colors=d_colors,
        empl_rows=empl_rows, wage_rows=wage_rows,
        wage_top_len=len(wage_top), demand_rows=demand_rows,
        growth_rows=growth_rows, lq_rows=lq_rows,
        sources_rows=sources_rows, rate_rows=rate_rows,
        radar_data=radar_data, eii_display=eii_display,
    )

# ── HTML builder ───────────────────────────────────────────────────────────

def build_html(industry_id, rows, soc_rows=None, occ_wage_rows=None):
    d      = process(industry_id, rows)
    config = d['config']
    acc    = config['color']
    r, g, b = hex_to_rgb(acc)

    empl_h   = max(160, len(d['empl_rows'])   * 22 + 36)
    wage_h   = max(130, len(d['wage_rows'])   * 22 + 44)
    demand_h = max(160, len(d['demand_rows']) * 22 + 36)
    growth_h = max(110, len(d['growth_rows']) * 24 + 30)
    lq_h     = max(110, len(d['lq_rows'])     * 24 + 30)
    sources_h= max(110, len(d['sources_rows'])* 24 + 30)
    rate_h   = max(110, len(d['rate_rows'])   * 24 + 30)

    # Occupation data
    occ_rows, wage_lookup = process_occupations(industry_id, soc_rows or [], occ_wage_rows or [])
    occ_h       = max(120, min(6, len(occ_rows)) * 22 + 32)
    occ_table   = build_occ_table(occ_rows, wage_lookup)

    # Radar
    radar_metrics_html = build_radar_metrics_html(d['radar_data'], acc)

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

    def subsector_section():
        has_any = any([d['growth_rows'], d['lq_rows'], d['sources_rows'], d['rate_rows']])
        if not has_any:
            return ''

        def mini(canvas_id, title, sub, h):
            return (
                f'<div class="section">'
                f'<div class="stitle">{title}</div>'
                f'<p class="ssub">{sub}</p>'
                f'<div class="cbox"><canvas id="{canvas_id}" width="295" height="{h}"></canvas></div>'
                f'</div>'
            )

        g = mini('cg',  'Growth Trends',            'Projected net new jobs per year — top sub-sectors', growth_h)
        l = mini('clq', 'Regional Concentration',   'Location quotient — LQ &gt; 1 means above national average', lq_h)
        s = mini('cs',  'Opening Sources',           'How demand is composed — exits, transfers, and growth', sources_h)
        rt= mini('cr',  'Opening Rate',              'Annual openings as % of employment — hiring intensity', rate_h)

        return (
            f'<div class="sdiv">Sub-Sector Intelligence</div>'
            f'<div class="grid2">{g}{l}{s}{rt}</div>'
        )

    def occ_section():
        top6 = occ_rows[:6]
        if not top6:
            return ''

        wage_chart_items = [
            {'occ': trunc(r.get('Occupation',''), 38),
             'entry': to_num(wage_lookup.get((r.get('SOC') or '').strip(), {}).get('Entry Level', 0)),
             'exp':   to_num(wage_lookup.get((r.get('SOC') or '').strip(), {}).get('Experienced', 0))}
            for r in top6
        ]
        wage_chart_items = [x for x in wage_chart_items if x['entry'] > 0 and x['exp'] > 0]

        charts = (
            f'<div class="section">'
            f'<div class="stitle">Top Occupations by Employment</div>'
            f'<p class="ssub">Occupations most commonly found in this industry sector.</p>'
            f'<div class="cbox"><canvas id="coe" width="295" height="{occ_h}"></canvas></div>'
            f'</div>'
        )
        if wage_chart_items:
            charts += (
                f'<div class="section">'
                f'<div class="stitle">Wage Range by Occupation</div>'
                f'<p class="ssub">Entry-level to experienced wage spread for top occupations.</p>'
                f'<div class="cbox"><canvas id="cow" width="295" height="{occ_h}"></canvas></div>'
                f'</div>'
            )

        return (
            f'<div class="sdiv" style="page-break-before:always;">In-Demand Occupations <span class="stag">SOC</span></div>'
            f'<div class="grid2">{charts}</div>'
            f'<div class="section" style="page-break-inside:avoid;">'
            f'<div class="stitle">Occupation Detail</div>'
            f'<p class="ssub">Key workforce metrics. LQ &gt; 1 indicates above-average regional concentration.</p>'
            f'<div class="cbox" style="padding:0;overflow:hidden;">{occ_table}</div>'
            f'</div>'
        )

    # JSON payload
    top8_occ = occ_rows[:6]
    occ_empl_data = [{'Occupation': trunc(r.get('Occupation',''), 38), 'Empl': r.get('Empl','0')} for r in top8_occ]
    occ_wage_data = [
        {'occ': trunc(r.get('Occupation',''), 38),
         'entry': to_num(wage_lookup.get((r.get('SOC') or '').strip(), {}).get('Entry Level', 0)),
         'exp':   to_num(wage_lookup.get((r.get('SOC') or '').strip(), {}).get('Experienced', 0))}
        for r in top8_occ
        if to_num(wage_lookup.get((r.get('SOC') or '').strip(), {}).get('Entry Level', 0)) > 0
    ]

    payload = json.dumps({
        'acc': acc, 'r': r, 'g': g, 'b': b,
        'sector_total': d['sector_total'],
        'sectors_sorted': d['sectors_sorted'],
        'canonical_id': d['canonical_id'],
        'd_colors': d['d_colors'],
        'naics_names': {**NAICS_NAMES, 'other': 'Other'},
        'empl_rows':   [{'Industry': x['Industry'], 'Empl': x['Empl']}              for x in d['empl_rows']],
        'wage_rows':   [{'Industry': x['Industry'], 'Avg Ann Wages': x['Avg Ann Wages']} for x in d['wage_rows']],
        'wage_top_len': d['wage_top_len'],
        'demand_rows': [{'Industry': x['Industry'], 'Total Demand': x['Total Demand']} for x in d['demand_rows']],
        'growth_rows': [{'Industry': x['Industry'], 'Empl_Growth': x.get('Empl Growth',0)} for x in d['growth_rows']],
        'lq_rows':     [{'Industry': x['Industry'], 'LQ': x.get('LQ',0)}             for x in d['lq_rows']],
        'sources_rows':[{'Industry': x['Industry'],
                         'Exits':    x.get('Exits',0),
                         'Transfers':x.get('Transfers',0),
                         'Growth':   x.get('Empl Growth',0)}                         for x in d['sources_rows']],
        'rate_rows':   [{'Industry': x['Industry'],
                         'rate': round(to_num(x.get('Total Demand',0)) / max(1, to_num(x.get('Empl',1))) * 100, 1)}
                        for x in d['rate_rows']],
        'occ_empl': occ_empl_data,
        'occ_wages': occ_wage_data,
        'radar_data': d['radar_data'],
    }, ensure_ascii=False).replace('</', '<\\/')

    logo_uri = logo_data_uri()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{config['name']} — Workforce Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
@page {{ size: letter portrait; margin: 0.45in 0.55in; }}
* {{ margin:0; padding:0; box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
body {{ font-family:-apple-system,'Helvetica Neue',Arial,sans-serif; font-size:9.5pt; color:#1f2937; background:#fff; line-height:1.45; }}
.cover {{ display:flex; justify-content:space-between; align-items:flex-start; padding-bottom:10pt; border-bottom:1.5pt solid #e5e7eb; margin-bottom:12pt; }}
.cover-text {{ flex:1; }}
.cover-logo img {{ height:48pt; width:auto; display:block; }}
.clabel {{ font-size:6.5pt; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:{acc}; margin-bottom:6pt; display:flex; align-items:center; gap:6pt; }}
.clabel::before {{ content:''; display:inline-block; width:12pt; height:1.5pt; background:{acc}; border-radius:1pt; }}
.cover h1 {{ font-size:21pt; font-weight:700; color:#111827; letter-spacing:-.03em; line-height:1.1; margin-bottom:3pt; }}
.cover .sub {{ font-size:8.5pt; color:#6b7280; }}
.narrative {{ font-size:9pt; color:#374151; margin-bottom:10pt; line-height:1.55; }}
.narrative strong, .narrative .stat {{ color:#111827; font-weight:600; }}
.krow {{ display:grid; grid-template-columns:repeat(5,1fr); gap:6pt; margin-bottom:14pt; page-break-inside:avoid; }}
.kcard {{ background:#f9fafb; border:.5pt solid #e5e7eb; border-radius:4pt; padding:7pt 9pt; }}
.klbl {{ font-size:5.5pt; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:#6b7280; margin-bottom:5pt; }}
.kval {{ font-size:16pt; font-weight:700; letter-spacing:-.03em; color:#111827; line-height:1; }}
.kval.ind {{ color:{acc}; }}
.ksub {{ font-size:6pt; color:#9ca3af; margin-top:3pt; }}
.section {{ margin-bottom:12pt; page-break-inside:avoid; }}
.stitle {{ font-size:10pt; font-weight:700; color:#111827; margin-bottom:2pt; }}
.ssub {{ font-size:7.5pt; color:#6b7280; margin-bottom:6pt; line-height:1.4; }}
.cbox {{ background:#f9fafb; border:.5pt solid #e5e7eb; border-radius:4pt; padding:8pt; overflow:hidden; }}
.dw {{ display:flex; gap:14pt; align-items:flex-start; }}
.dc {{ flex-shrink:0; }}
.dl {{ flex:1; display:flex; flex-direction:column; gap:3pt; align-content:start; padding-top:6pt; }}
.li {{ display:flex; align-items:center; gap:5pt; }}
.li.hl .ln {{ color:#111827; font-weight:600; }}
.dot {{ width:8pt; height:8pt; border-radius:50%; flex-shrink:0; }}
.ln {{ font-size:8pt; color:#6b7280; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.lp {{ font-size:8pt; font-weight:600; white-space:nowrap; }}
.sdiv {{ font-size:6pt; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:#9ca3af; border-top:1pt solid #e5e7eb; padding-top:6pt; margin:16pt 0 8pt; }}
.stag {{ display:inline-block; background:#ede9fe; color:#6d28d9; font-size:5pt; font-weight:700; letter-spacing:.1em; padding:1pt 5pt; border-radius:3pt; margin-left:8pt; vertical-align:middle; text-transform:uppercase; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:10pt; margin-bottom:4pt; page-break-inside:avoid; }}
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
  <div class="kcard">
    <div class="klbl">Economic Impact Score</div>
    <div class="kval">{d['eii_display']:.2f}×</div>
    <div class="ksub">wage &amp; growth vs. regional baseline</div>
  </div>
</div>

<div class="section">
  <div class="stitle">Industry Profile</div>
  <p class="ssub">Percentile rankings across key workforce dimensions relative to all other local industry sectors.</p>
  <div class="cbox" style="display:flex;gap:18pt;align-items:center;padding:10pt 12pt;">
    <div style="min-width:120pt;">{radar_metrics_html}</div>
    <div><canvas id="crad" width="220" height="220"></canvas></div>
  </div>
</div>

<div class="section">
  <div class="stitle">Share of the Local Economy</div>
  <p class="ssub">Employment distribution across all major sectors. {d['short_name']} is highlighted.</p>
  <div class="cbox">
    <div class="dw">
      <div class="dc"><canvas id="cd" width="340" height="340"></canvas></div>
      <div class="dl">{legend_html}</div>
    </div>
  </div>
</div>

{empl_section()}{wage_section()}{demand_section()}
{subsector_section()}
{occ_section()}

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
        display: true, clamp: false, clip: false,
        formatter: function(v, ctx) {{
          var share = (v / st) * 100;
          var pct   = share.toFixed(1) + '%';
          var clr   = ctx.chart.data.datasets[0].backgroundColor[ctx.dataIndex];
          var lbl   = ctx.chart.data.labels[ctx.dataIndex];
          var name  = D.naics_names[lbl] || lbl;
          if (clr === acc) return name + '\\n' + pct;
          if (share >= 5)  return name + '\\n' + pct;
          if (share >= 2)  return pct;
          return '';
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
    data: {{ labels: D.empl_rows.map(function(x) {{ return trunc(x.Industry, 44); }}), datasets: [{{ data: D.empl_rows.map(function(x) {{ return toNum(x.Empl); }}), backgroundColor: ec, borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}] }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 54, top: 2, bottom: 2 }} }}, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: fmtNum }} }}, scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Wage
var cwEl = document.getElementById('cw');
if (cwEl) {{
  var wc = D.wage_rows.map(function(_, i) {{ return i < D.wage_top_len ? fade(acc, 0.8) : fade('#f59e0b', 0.8); }});
  new Chart(cwEl, {{
    type: 'bar',
    data: {{ labels: D.wage_rows.map(function(x) {{ return trunc(x.Industry, 44); }}), datasets: [{{ data: D.wage_rows.map(function(x) {{ return toNum(x['Avg Ann Wages']); }}), backgroundColor: wc, borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}] }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 62, top: 2, bottom: 2 }} }}, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: function(ctx) {{ return ctx.dataIndex < D.wage_top_len ? acc : '#f59e0b'; }}, font: {{ size: 9, weight: '600' }}, formatter: fmtDollar }} }}, scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Demand
var cd2El = document.getElementById('cd2');
if (cd2El) {{
  var dc = D.demand_rows.map(function(_, i) {{ return 'rgba('+r+','+g+','+b+','+(0.75-(i/D.demand_rows.length)*0.35)+')'; }});
  new Chart(cd2El, {{
    type: 'bar',
    data: {{ labels: D.demand_rows.map(function(x) {{ return trunc(x.Industry, 44); }}), datasets: [{{ data: D.demand_rows.map(function(x) {{ return toNum(x['Total Demand']); }}), backgroundColor: dc, borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}] }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 44, top: 2, bottom: 2 }} }}, plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: fmtNum }} }}, scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Growth Trends
var cgEl = document.getElementById('cg');
if (cgEl && D.growth_rows.length) {{
  new Chart(cgEl, {{
    type: 'bar',
    data: {{
      labels: D.growth_rows.map(function(x) {{ return trunc(x.Industry, 38); }}),
      datasets: [{{ data: D.growth_rows.map(function(x) {{ return toNum(x.Empl_Growth); }}),
        backgroundColor: D.growth_rows.map(function(x) {{ return toNum(x.Empl_Growth) >= 0 ? fade(acc, 0.8) : 'rgba(239,68,68,0.7)'; }}),
        borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}]
    }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 50, top: 2, bottom: 2 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: function(v) {{ return (v >= 0 ? '+' : '') + fmtNum(v); }} }} }},
      scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Regional Concentration (LQ)
var clqEl = document.getElementById('clq');
if (clqEl && D.lq_rows.length) {{
  var lqColors = D.lq_rows.map(function(x) {{ return toNum(x.LQ) >= 1 ? fade(acc, 0.8) : 'rgba(156,163,175,0.6)'; }});
  new Chart(clqEl, {{
    type: 'bar',
    data: {{
      labels: D.lq_rows.map(function(x) {{ return trunc(x.Industry, 38); }}),
      datasets: [{{ data: D.lq_rows.map(function(x) {{ return toNum(x.LQ); }}), backgroundColor: lqColors, borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}]
    }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 46, top: 2, bottom: 2 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }},
        datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: function(v) {{ return toNum(v).toFixed(2); }} }} }},
      scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false, min: 0 }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Opening Sources (stacked)
var csEl = document.getElementById('cs');
if (csEl && D.sources_rows.length) {{
  new Chart(csEl, {{
    type: 'bar',
    data: {{
      labels: D.sources_rows.map(function(x) {{ return trunc(x.Industry, 38); }}),
      datasets: [
        {{ label: 'Exits',     data: D.sources_rows.map(function(x) {{ return Math.max(0, toNum(x.Exits)); }}),     backgroundColor: 'rgba(239,68,68,0.7)',  borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }},
        {{ label: 'Transfers', data: D.sources_rows.map(function(x) {{ return Math.max(0, toNum(x.Transfers)); }}), backgroundColor: fade(acc, 0.65),         borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }},
        {{ label: 'Growth',    data: D.sources_rows.map(function(x) {{ return Math.max(0, toNum(x.Growth)); }}),    backgroundColor: 'rgba(34,197,94,0.7)',   borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}
      ]
    }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 4, top: 2, bottom: 2 }} }},
      plugins: {{ legend: {{ display: true, position: 'bottom', labels: {{ font: {{ size: 8 }}, padding: 8, boxWidth: 10 }} }}, tooltip: {{ enabled: false }}, datalabels: {{ display: false }} }},
      scales: {{ y: {{ stacked: true, grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ stacked: true, display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Opening Rate
var crEl = document.getElementById('cr');
if (crEl && D.rate_rows.length) {{
  new Chart(crEl, {{
    type: 'bar',
    data: {{
      labels: D.rate_rows.map(function(x) {{ return trunc(x.Industry, 38); }}),
      datasets: [{{ data: D.rate_rows.map(function(x) {{ return toNum(x.rate); }}),
        backgroundColor: D.rate_rows.map(function(_, i) {{ return 'rgba('+r+','+g+','+b+','+(0.85-(i/D.rate_rows.length)*0.4)+')'; }}),
        borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}]
    }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 48, top: 2, bottom: 2 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }},
        datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: function(v) {{ return toNum(v).toFixed(1) + '%'; }} }} }},
      scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false, min: 0 }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Industry Profile Radar
var cradEl = document.getElementById('crad');
if (cradEl) {{
  new Chart(cradEl, {{
    type: 'radar',
    data: {{
      labels: ['Employment\\nScale', 'Wage\\nLevel', 'Economic\\nImpact', 'Job\\nGrowth', 'Hiring\\nActivity'],
      datasets: [{{ data: D.radar_data,
        backgroundColor: fade(acc, 0.15),
        borderColor: acc, borderWidth: 2,
        pointBackgroundColor: acc, pointBorderColor: 'transparent', pointRadius: 4
      }}]
    }},
    options: {{
      animation: false, responsive: false, maintainAspectRatio: true,
      scales: {{ r: {{ min: 0, max: 100,
        ticks: {{ display: false }},
        grid: {{ color: '#e5e7eb' }}, angleLines: {{ color: '#e5e7eb' }},
        pointLabels: {{ color: '#374151', font: {{ size: 8.5, weight: '500' }} }}
      }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }}, datalabels: {{ display: false }} }}
    }},
    plugins: [ChartDataLabels]
  }});
}}

// Occupation Employment
var coeEl = document.getElementById('coe');
if (coeEl && D.occ_empl.length) {{
  new Chart(coeEl, {{
    type: 'bar',
    data: {{
      labels: D.occ_empl.map(function(x) {{ return trunc(x.Occupation, 38); }}),
      datasets: [{{ data: D.occ_empl.map(function(x) {{ return toNum(x.Empl); }}),
        backgroundColor: D.occ_empl.map(function(_, i) {{ return 'rgba(99,102,241,'+(0.9-(i/D.occ_empl.length)*0.45)+')'; }}),
        borderWidth: 0, barPercentage: 0.82, categoryPercentage: 1 }}]
    }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 52, top: 2, bottom: 2 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }},
        datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: fmtNum }} }},
      scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

// Occupation Wage Range (floating bar)
var cowEl = document.getElementById('cow');
if (cowEl && D.occ_wages.length) {{
  new Chart(cowEl, {{
    type: 'bar',
    data: {{
      labels: D.occ_wages.map(function(x) {{ return trunc(x.occ, 38); }}),
      datasets: [{{ data: D.occ_wages.map(function(x) {{ return [x.entry, x.exp]; }}),
        backgroundColor: D.occ_wages.map(function(_, i) {{ return 'rgba(99,102,241,'+(0.85-(i/D.occ_wages.length)*0.4)+')'; }}),
        borderWidth: 0, barPercentage: 0.6, categoryPercentage: 1 }}]
    }},
    options: {{ indexAxis: 'y', animation: false, responsive: false, maintainAspectRatio: false, layout: {{ padding: {{ right: 58, top: 2, bottom: 2 }} }},
      plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }},
        datalabels: {{ anchor: 'end', align: 'right', clamp: false, clip: false, color: '#9ca3af', font: {{ size: 9, weight: '500' }}, formatter: function(v) {{ return fmtDollar(v[1]); }} }} }},
      scales: {{ y: {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ color: '#374151', font: {{ size: 9 }} }} }}, x: {{ display: false }} }} }},
    plugins: [ChartDataLabels]
  }});
}}

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
    ind_path   = script_dir / 'Data' / 'processed' / 'Industry_Snapshot.csv'
    soc_path   = script_dir / 'Data' / 'processed' / 'Occupation_Snapshot.csv'
    wage_path  = script_dir / 'Data' / 'processed' / 'Occupation_Wages.csv'

    if not ind_path.exists():
        print(f'Error: data file not found at {ind_path}')
        sys.exit(1)

    rows      = load_csv(ind_path)
    soc_rows  = load_csv(soc_path)  if soc_path.exists()  else []
    wage_rows = load_csv(wage_path) if wage_path.exists() else []

    output_dir = script_dir / 'reports' / 'pdf'
    output_dir.mkdir(parents=True, exist_ok=True)

    for ind_id in industry_ids:
        if ind_id not in INDUSTRIES:
            print(f'Unknown industry ID: {ind_id}  (valid: {", ".join(INDUSTRIES)})')
            continue
        name = INDUSTRIES[ind_id]['name']
        print(f'  {ind_id}  {name}...', end=' ', flush=True)
        try:
            html = build_html(ind_id, rows, soc_rows, wage_rows)
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
