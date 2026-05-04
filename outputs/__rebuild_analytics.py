"""원본 analytics-dashboard.html을 git에서 가져와 CSS만 새 토큰으로 교체."""
import pathlib, re

orig = pathlib.Path("/tmp/analytics-dashboard.orig.html").read_text(encoding="utf-8")

NEW_STYLE = """    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

        :root {
            --bg:        #FAFAF7;
            --bg-elev:   #FFFFFF;
            --bg-soft:   #F1F2F4;
            --fg:        #1F2328;
            --fg-strong: #0B1221;
            --fg-muted:  #57606A;
            --fg-subtle: #6E7781;
            --border:    #D0D7DE;
            --border-subtle: #E5E7EB;
            --accent:    #0969DA;
            --accent-bg: rgba(9,105,218,0.08);
            --bar:       #4C8DD3;
            --bar-strong:#0969DA;
            --trend:     #2DA44E;
            --trend-strong:#1A7F37;
            --header-bg: #1F2328;
            --header-fg: #F0F6FC;
            --header-link:#9DA7B3;
            --shadow-sm: 0 1px 2px rgba(31,35,40,0.05);
            --shadow:    0 1px 3px rgba(31,35,40,0.08), 0 4px 10px rgba(31,35,40,0.04);
            --tooltip-bg:#1F2328;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg:        #0D1117;
                --bg-elev:   #161B22;
                --bg-soft:   #1C2128;
                --fg:        #E6EDF3;
                --fg-strong: #F0F6FC;
                --fg-muted:  #8B949E;
                --fg-subtle: #6E7681;
                --border:    #30363D;
                --border-subtle: #21262D;
                --accent:    #58A6FF;
                --accent-bg: rgba(88,166,255,0.12);
                --bar:       #4C8DD3;
                --bar-strong:#79B8FF;
                --trend:     #3FB950;
                --trend-strong:#56D364;
                --header-bg: #161B22;
                --header-fg: #E6EDF3;
                --header-link:#8B949E;
                --shadow-sm: 0 1px 2px rgba(0,0,0,0.20);
                --shadow:    0 1px 3px rgba(0,0,0,0.25), 0 4px 10px rgba(0,0,0,0.18);
                --tooltip-bg:#21262D;
            }
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Pretendard','Noto Sans KR',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,system-ui,sans-serif;
            background: var(--bg);
            color: var(--fg);
            line-height: 1.65;
            font-size: 15px;
            -webkit-font-smoothing: antialiased;
        }
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 8px; border: 2px solid var(--bg); }
        * { scrollbar-width: thin; scrollbar-color: var(--border) transparent; }

        .header {
            background: var(--header-bg);
            color: var(--header-fg);
            padding: 14px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-subtle);
        }
        .header h1 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; }
        .header a {
            color: var(--header-link);
            text-decoration: none;
            font-size: 13px;
            padding: 4px 10px;
            border-radius: 6px;
            transition: background-color 0.15s, color 0.15s;
        }
        .header a:hover { background: rgba(255,255,255,0.08); color: var(--header-fg); }
        .header-links { display: flex; align-items: center; gap: 6px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: var(--bg-elev);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 18px;
            box-shadow: var(--shadow-sm);
            text-align: left;
        }
        .metric-card .label {
            font-size: 12px;
            font-weight: 500;
            color: var(--fg-muted);
            margin-bottom: 6px;
            letter-spacing: 0.2px;
            text-transform: uppercase;
        }
        .metric-card .value {
            font-size: 28px;
            font-weight: 700;
            color: var(--fg-strong);
            line-height: 1.2;
            font-variant-numeric: tabular-nums;
        }

        .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 768px) {
            .two-col { grid-template-columns: 1fr; }
            .header { flex-direction: column; gap: 8px; padding: 14px; }
            .container { padding: 14px; }
        }

        .panel {
            background: var(--bg-elev);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 20px;
            box-shadow: var(--shadow-sm);
            margin-bottom: 20px;
        }
        .panel h2 {
            font-size: 15px;
            font-weight: 600;
            margin-bottom: 14px;
            color: var(--fg-strong);
            letter-spacing: -0.1px;
        }

        .bar-chart .bar-row { display: flex; align-items: center; margin-bottom: 8px; }
        .bar-row .bar-label {
            width: 130px; font-size: 13px; text-align: right;
            padding-right: 12px; flex-shrink: 0; color: var(--fg-muted);
        }
        .bar-row .bar-track {
            flex: 1; background: var(--bg-soft); border-radius: 5px;
            height: 22px; overflow: hidden;
        }
        .bar-row .bar-fill {
            height: 100%; background: var(--bar); border-radius: 5px;
            transition: width 0.6s ease; min-width: 2px;
        }
        .bar-row:hover .bar-fill { background: var(--bar-strong); }
        .bar-row .bar-count {
            width: 60px; font-size: 13px; padding-left: 8px;
            color: var(--fg); font-variant-numeric: tabular-nums; font-weight: 500;
        }

        .sparkline-container {
            display: flex; align-items: flex-end; gap: 3px;
            height: 110px; margin-top: 6px; padding: 0 4px;
        }
        .spark-bar {
            flex: 1; background: var(--trend);
            border-radius: 2px 2px 0 0; min-height: 2px;
            transition: height 0.4s ease, background-color 0.15s; position: relative;
        }
        .spark-bar:hover { background: var(--trend-strong); }
        .spark-bar:hover::after {
            content: attr(data-tip); position: absolute; bottom: 100%;
            left: 50%; transform: translateX(-50%); background: var(--tooltip-bg);
            color: #fff; padding: 3px 8px; border-radius: 4px;
            font-size: 11px; white-space: nowrap; z-index: 10; box-shadow: var(--shadow-sm);
        }
        .spark-labels {
            display: flex; gap: 3px; font-size: 11px;
            color: var(--fg-subtle); margin-top: 6px; padding: 0 4px;
            font-variant-numeric: tabular-nums;
        }
        .spark-labels span { flex: 1; text-align: center; }

        .table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
        th {
            background: var(--bg-soft); text-align: left;
            padding: 10px 12px; border-bottom: 1px solid var(--border);
            color: var(--fg-muted); white-space: nowrap;
            font-weight: 600; font-size: 12px;
            text-transform: uppercase; letter-spacing: 0.3px;
            position: sticky; top: 0;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-subtle);
            color: var(--fg);
        }
        tr:nth-child(even) td { background: var(--bg-soft); }
        tr:hover td { background: var(--accent-bg); }

        .heatmap-grid {
            display: grid; grid-template-columns: 60px repeat(24, 1fr);
            gap: 3px; font-size: 11px; font-variant-numeric: tabular-nums;
        }
        .heatmap-header {
            text-align: center; color: var(--fg-subtle);
            font-weight: 600; padding: 4px 0;
        }
        .heatmap-row-label {
            text-align: right; padding-right: 8px;
            color: var(--fg-muted); font-size: 12px; font-weight: 500;
            display: flex; align-items: center; justify-content: flex-end;
        }
        .heatmap-cell {
            aspect-ratio: 1; border-radius: 3px;
            min-height: 20px; position: relative; cursor: default;
        }
        .heatmap-cell:hover { outline: 2px solid var(--accent); outline-offset: 1px; z-index: 5; }
        .heatmap-cell:hover::after {
            content: attr(data-tip); position: absolute; bottom: 100%;
            left: 50%; transform: translateX(-50%); background: var(--tooltip-bg);
            color: #fff; padding: 3px 8px; border-radius: 4px;
            font-size: 11px; white-space: nowrap; z-index: 10; box-shadow: var(--shadow-sm);
        }

        .loading { text-align: center; padding: 2rem; color: var(--fg-subtle); font-size: 13px; }
        *:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
    </style>"""

# Replace the original style block
m = re.search(r'    <style>.*?</style>', orig, re.S)
assert m, "no <style> block found"
print(f"Original style block: {m.start()}..{m.end()} ({m.end()-m.start()} chars)")
new_src = orig[:m.start()] + NEW_STYLE + orig[m.end():]

# Patch the heatmap RGB interpolation
old_heat = """        let html = '<div class="heatmap-grid">';
        // Header row
        html += '<div class="heatmap-header"></div>';
        hours.forEach(h => { html += `<div class="heatmap-header">${h}</div>`; });

        // Data rows
        days.forEach((day, di) => {
            html += `<div class="heatmap-row-label">${escapeHtml(String(day))}</div>`;
            hours.forEach((h, hi) => {
                const val = (data[di] && data[di][hi]) || 0;
                const intensity = val / maxVal;
                const r = Math.round(52 + (232 - 52) * (1 - intensity));
                const g = Math.round(152 + (236 - 152) * (1 - intensity));
                const b = Math.round(219 + (239 - 219) * (1 - intensity));
                html += `<div class="heatmap-cell" style="background:rgb(${r},${g},${b})" data-tip="${day} ${h}시: ${val}건"></div>`;
            });
        });
        html += '</div>';"""

new_heat = """        const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const colorLo = isDark ? [22, 27, 34]   : [235, 241, 247];
        const colorHi = isDark ? [88, 166, 255] : [9, 105, 218];

        let html = '<div class="heatmap-grid">';
        html += '<div class="heatmap-header"></div>';
        hours.forEach(h => { html += `<div class="heatmap-header">${h}</div>`; });

        days.forEach((day, di) => {
            html += `<div class="heatmap-row-label">${escapeHtml(String(day))}</div>`;
            hours.forEach((h, hi) => {
                const val = (data[di] && data[di][hi]) || 0;
                const t = val / maxVal;
                const r = Math.round(colorLo[0] + (colorHi[0] - colorLo[0]) * t);
                const g = Math.round(colorLo[1] + (colorHi[1] - colorLo[1]) * t);
                const b = Math.round(colorLo[2] + (colorHi[2] - colorLo[2]) * t);
                html += `<div class="heatmap-cell" style="background:rgb(${r},${g},${b})" data-tip="${day} ${h}시: ${val}건"></div>`;
            });
        });
        html += '</div>';"""

# Normalize CRLF to LF for matching
new_src_lf = new_src.replace("\r\n", "\n")
assert old_heat in new_src_lf, "heatmap pattern not found"
new_src_lf = new_src_lf.replace(old_heat, new_heat)

# Also tweak inline currentUser color
old_user = '<span id="currentUser" style="font-size:0.85rem;color:#a8d0f0;"></span>'
new_user = '<span id="currentUser" style="font-size:13px;color:var(--header-link);font-weight:500"></span>'
new_src_lf = new_src_lf.replace(old_user, new_user)

# Write back as LF
out = pathlib.Path("/sessions/blissful-vibrant-clarke/mnt/bonded-exhibition-chatbot-data/web/analytics-dashboard.html")
out.write_text(new_src_lf, encoding="utf-8")
print(f"wrote {out} ({len(new_src_lf)} chars, {new_src_lf.count(chr(10))+1} lines)")
print("tail:", repr(new_src_lf[-60:]))
