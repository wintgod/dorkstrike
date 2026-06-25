"""HTML report generator for DorkStrike — grouped by dork."""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from datetime import datetime

from ..models import ScanConfig, SearchResult

logger = logging.getLogger("dorkstrike")


def generate_html_report(
    results: list[SearchResult],
    config: ScanConfig,
    output_dir: str,
) -> str:
    """Generate a self-contained dark-themed HTML report grouped by dork."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"dorkstrike_report_{timestamp}.html"
    filepath = os.path.join(output_dir, filename)

    # Stats
    engine_counts = Counter(r.engine for r in results)
    category_counts = Counter(r.category for r in results)
    total = len(results)
    unique_dorks = set(r.dork for r in results)
    engines_attempted = config.engines
    engines_successful = sorted(engine_counts.keys())

    # Group results by dork
    dork_groups: dict[str, list[SearchResult]] = defaultdict(list)
    for r in results:
        dork_groups[r.dork].append(r)

    # Build engine stat cards
    engine_cards = ""
    for eng in sorted(engine_counts.keys()):
        count = engine_counts[eng]
        pct = (count / total * 100) if total else 0
        engine_cards += f"""
            <div class="stat-card">
                <div class="stat-value">{count}</div>
                <div class="stat-label">{_esc(eng.upper())}</div>
                <div class="stat-bar"><div class="stat-bar-fill" style="width:{pct:.0f}%"></div></div>
            </div>"""

    # Build category rows
    category_rows = ""
    for cat in sorted(category_counts.keys()):
        count = category_counts[cat]
        category_rows += f"<tr><td>{_esc(cat)}</td><td class='num'>{count}</td></tr>\n"

    # Build grouped dork sections
    dork_sections = ""
    for i, (dork, items) in enumerate(sorted(dork_groups.items()), 1):
        engines_for_dork = sorted(set(r.engine for r in items))
        engine_badges = " ".join(
            f'<span class="badge badge-{e}">{e}</span>' for e in engines_for_dork
        )
        category = items[0].category if items else "Custom"

        url_rows = ""
        for j, r in enumerate(items, 1):
            url_rows += f"""
                <tr>
                    <td class="num">{j}</td>
                    <td><a href="{_esc(r.url)}" target="_blank" rel="noopener">{_esc(r.url)}</a></td>
                    <td>{_esc(r.title)}</td>
                    <td class="snippet">{_esc(r.snippet[:250])}</td>
                    <td><span class="badge badge-{r.engine}">{r.engine}</span></td>
                </tr>"""

        dork_sections += f"""
        <div class="dork-group">
            <div class="dork-header" onclick="toggleDork(this)">
                <div class="dork-info">
                    <span class="dork-number">#{i}</span>
                    <code class="dork-query" id="dork-{i}">{_esc(dork)}</code>
                    <button class="copy-btn" onclick="copyDork(event, 'dork-{i}')" title="Copy dork to clipboard">📋</button>
                    <span class="dork-meta">
                        <span class="category-tag">{_esc(category)}</span>
                        {engine_badges}
                        <span class="result-count">{len(items)} result{'s' if len(items) != 1 else ''}</span>
                    </span>
                </div>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="dork-body">
                <table>
                    <thead>
                        <tr>
                            <th style="width:40px">#</th>
                            <th>URL</th>
                            <th>Title</th>
                            <th>Snippet</th>
                            <th>Engine</th>
                        </tr>
                    </thead>
                    <tbody>{url_rows}</tbody>
                </table>
            </div>
        </div>"""

    # Dorks with no results section
    all_dork_queries = set(r.dork for r in results)

    # Engine status breakdown
    engine_status_rows = ""
    for eng in engines_attempted:
        count = engine_counts.get(eng, 0)
        status = "✓ Active" if count > 0 else "✗ No results"
        status_class = "status-active" if count > 0 else "status-inactive"
        engine_status_rows += f"""
            <tr>
                <td><span class="badge badge-{eng}">{eng}</span></td>
                <td class="{status_class}">{status}</td>
                <td class="num">{count}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DorkStrike Report — {_esc(config.site)}</title>
<style>
:root {{
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-orange: #d29922;
    --accent-red: #f85149;
    --accent-purple: #bc8cff;
    --accent-cyan: #39d2c0;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}}

.container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}

/* Banner */
.banner {{
    background: linear-gradient(135deg, #1a1e2e 0%, #0d1117 50%, #1a1224 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}}
.banner::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent-red), var(--accent-orange), var(--accent-cyan), var(--accent-blue), var(--accent-purple));
}}
.banner h1 {{
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
}}
.banner .meta {{ color: var(--text-secondary); font-size: 0.9rem; }}
.banner .meta span {{ margin-right: 1.5rem; }}
.banner .meta .label {{ color: var(--text-secondary); }}
.banner .meta .value {{ color: var(--accent-blue); font-weight: 500; }}

/* Stats */
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}}
.stat-card {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s;
}}
.stat-card:hover {{ transform: translateY(-2px); border-color: var(--accent-blue); }}
.stat-value {{ font-size: 2rem; font-weight: 700; color: var(--accent-cyan); }}
.stat-label {{ font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em; }}
.stat-bar {{ height: 4px; background: var(--bg-tertiary); border-radius: 2px; margin-top: 0.75rem; overflow: hidden; }}
.stat-bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue)); border-radius: 2px; }}

/* Section */
.section {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 1.5rem;
    overflow: hidden;
}}
.section-header {{
    padding: 1rem 1.5rem;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.section-header:hover {{ background: #282e36; }}
.section-body {{ padding: 0; }}
.section-body.collapsed {{ display: none; }}

/* Dork Groups */
.dork-group {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 1rem;
    overflow: hidden;
}}
.dork-header {{
    padding: 1rem 1.5rem;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    transition: background 0.2s;
}}
.dork-header:hover {{ background: #282e36; }}
.dork-info {{ display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; flex: 1; }}
.dork-number {{
    background: var(--accent-cyan);
    color: var(--bg-primary);
    font-weight: 700;
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    min-width: 28px;
    text-align: center;
}}
.dork-query {{
    background: rgba(57, 210, 192, 0.1);
    border: 1px solid rgba(57, 210, 192, 0.2);
    color: var(--accent-cyan);
    padding: 0.3rem 0.7rem;
    border-radius: 6px;
    font-family: var(--font-mono);
    font-size: 0.82rem;
    word-break: break-all;
}}
.dork-meta {{ display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
.category-tag {{
    background: rgba(188, 140, 255, 0.12);
    color: var(--accent-purple);
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 500;
}}
.result-count {{
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
}}
.toggle-icon {{ color: var(--text-secondary); font-size: 0.8rem; flex-shrink: 0; }}
.dork-body {{ padding: 0; }}
.dork-body.collapsed {{ display: none; }}

/* Table */
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
th {{ background: var(--bg-tertiary); padding: 0.65rem 1rem; text-align: left; font-weight: 600;
      color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.72rem;
      white-space: nowrap; }}
td {{ padding: 0.6rem 1rem; border-bottom: 1px solid var(--border); vertical-align: top; }}
tr:hover td {{ background: rgba(88, 166, 255, 0.04); }}
td.num {{ text-align: center; color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.8rem; }}
td a {{ color: var(--accent-blue); text-decoration: none; word-break: break-all; }}
td a:hover {{ text-decoration: underline; }}
td.snippet {{ color: var(--text-secondary); font-size: 0.8rem; max-width: 350px; }}

/* Engine status */
.status-active {{ color: var(--accent-green); font-weight: 500; }}
.status-inactive {{ color: var(--text-secondary); }}

/* Badges */
.badge {{
    display: inline-block; padding: 0.2rem 0.55rem; border-radius: 9999px;
    font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
}}
.badge-bing {{ background: rgba(57, 210, 192, 0.15); color: #39d2c0; }}
.badge-brave {{ background: rgba(248, 81, 73, 0.15); color: #f85149; }}
.badge-duckduckgo {{ background: rgba(63, 185, 80, 0.15); color: var(--accent-green); }}
.badge-yahoo {{ background: rgba(210, 153, 34, 0.15); color: var(--accent-orange); }}
.badge-yandex {{ background: rgba(188, 140, 255, 0.15); color: var(--accent-purple); }}

/* Copy button */
.copy-btn {{
    background: rgba(88, 166, 255, 0.1);
    border: 1px solid rgba(88, 166, 255, 0.25);
    color: var(--text-secondary);
    cursor: pointer;
    padding: 0.2rem 0.45rem;
    border-radius: 6px;
    font-size: 0.75rem;
    transition: all 0.2s;
    flex-shrink: 0;
}}
.copy-btn:hover {{
    background: rgba(88, 166, 255, 0.25);
    color: var(--accent-blue);
    border-color: var(--accent-blue);
}}
.copy-btn.copied {{
    background: rgba(63, 185, 80, 0.2);
    border-color: var(--accent-green);
    color: var(--accent-green);
}}

/* Footer */
.footer {{
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.8rem;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
}}
.footer .author {{ color: var(--accent-cyan); font-weight: 600; }}

/* Scrollbar */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: var(--bg-primary); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-secondary); }}

/* No results message */
.no-results {{
    padding: 3rem;
    text-align: center;
    color: var(--text-secondary);
    font-size: 1.1rem;
}}
</style>
</head>
<body>
<div class="container">

<!-- Banner -->
<div class="banner">
    <h1>⚡ DorkStrike Report</h1>
    <div class="meta">
        <span><span class="label">Target: </span><span class="value">{_esc(config.site)}</span></span>
        <span><span class="label">Generated: </span><span class="value">{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</span></span>
        <span><span class="label">Engines: </span><span class="value">{', '.join(engines_attempted)}</span></span>
        <span><span class="label">Results: </span><span class="value">{total}</span></span>
    </div>
</div>

<!-- Stats -->
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-value">{total}</div>
        <div class="stat-label">Total Results</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{len(unique_dorks)}</div>
        <div class="stat-label">Dorks With Hits</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{len(engines_successful)} / {len(engines_attempted)}</div>
        <div class="stat-label">Engines Active</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{len(category_counts)}</div>
        <div class="stat-label">Categories</div>
    </div>
    {engine_cards}
</div>

<!-- Engine Status -->
<div class="section">
    <div class="section-header" onclick="toggleSection(this)">
        🔌 Engine Status ({len(engines_successful)} active / {len(engines_attempted)} attempted) <span class="toggle-icon">▼</span>
    </div>
    <div class="section-body">
        <table>
            <thead><tr><th>Engine</th><th>Status</th><th style="width:100px">Results</th></tr></thead>
            <tbody>{engine_status_rows}</tbody>
        </table>
    </div>
</div>

<!-- Category Breakdown -->
<div class="section">
    <div class="section-header" onclick="toggleSection(this)">
        📊 Category Breakdown <span class="toggle-icon">▼</span>
    </div>
    <div class="section-body">
        <table>
            <thead><tr><th>Category</th><th style="width:100px">Count</th></tr></thead>
            <tbody>{category_rows}</tbody>
        </table>
    </div>
</div>

<!-- Dork Results (grouped) -->
<h2 style="color: var(--text-primary); margin: 1.5rem 0 1rem; font-size: 1.2rem;">
    🔍 Findings by Dork ({len(dork_groups)} dork{'s' if len(dork_groups) != 1 else ''} with results)
</h2>

{dork_sections if dork_sections else '<div class="no-results">No results found for any dork. Try different dorks or check your target domain.</div>'}

<!-- Footer -->
<div class="footer">
    Generated by <strong>DorkStrike v1.0.0</strong> — Dorking Reconnaissance Tool<br>
    Created by <span class="author">W1N7G0D</span>
</div>

</div>

<script>
function toggleSection(header) {{
    const body = header.nextElementSibling;
    const icon = header.querySelector('.toggle-icon');
    body.classList.toggle('collapsed');
    icon.textContent = body.classList.contains('collapsed') ? '▶' : '▼';
}}

function toggleDork(header) {{
    const body = header.nextElementSibling;
    const icon = header.querySelector('.toggle-icon');
    body.classList.toggle('collapsed');
    icon.textContent = body.classList.contains('collapsed') ? '▶' : '▼';
}}

function copyDork(event, elementId) {{
    event.stopPropagation();
    const codeEl = document.getElementById(elementId);
    if (!codeEl) return;
    const text = codeEl.textContent;
    navigator.clipboard.writeText(text).then(() => {{
        const btn = event.currentTarget;
        const orig = btn.textContent;
        btn.textContent = '✓';
        btn.classList.add('copied');
        setTimeout(() => {{
            btn.textContent = orig;
            btn.classList.remove('copied');
        }}, 1500);
    }}).catch(() => {{
        // Fallback for older browsers
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        const btn = event.currentTarget;
        const orig = btn.textContent;
        btn.textContent = '✓';
        btn.classList.add('copied');
        setTimeout(() => {{
            btn.textContent = orig;
            btn.classList.remove('copied');
        }}, 1500);
    }});
}}
</script>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(html)

    logger.info("HTML report saved: %s", filepath)
    return filepath


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
