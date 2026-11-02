#!/usr/bin/env python3
"""
Outputs Module

Generates JSON, CSV, and HTML reports from correlated findings.
"""

import json
import csv
import io
import logging
import html as html_lib
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outputs")


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_json_report(data: Dict) -> str:
    """
    Generate formatted JSON report.

    Args:
        data: Complete report data from main pipeline

    Returns:
        Formatted JSON string
    """
    logger.info("Generating JSON report")

    report = {
        "report_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "data": data,
    }

    return json.dumps(report, indent=2, ensure_ascii=False)


def generate_csv_report(scored_findings: Dict) -> str:
    """
    Generate CSV report for spreadsheet analysis.

    Args:
        scored_findings: Output from score_confidence

    Returns:
        CSV string
    """
    logger.info("Generating CSV report")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "email", "confidence", "source_count", "sources", "risk_category"
    ])

    for finding in scored_findings.get("scored_findings", []):
        email = finding.get("email", "")
        confidence = finding.get("confidence", 0)
        sources_list = finding.get("sources", [])
        sources = ";".join(sources_list)

        if confidence >= 75:
            risk = "HIGH_CONFIDENCE"
        elif confidence >= 50:
            risk = "MEDIUM_CONFIDENCE"
        else:
            risk = "LOW_CONFIDENCE"

        writer.writerow([
            email, confidence, len(sources_list), sources, risk
        ])

    return output.getvalue()


def _esc(value) -> str:
    """HTML-escape any value for safe interpolation into the report."""
    return html_lib.escape(str(value), quote=True)


def generate_html_report(data: Dict) -> str:
    """
    Generate interactive HTML report.

    Args:
        data: Complete report data from main pipeline

    Returns:
        HTML string
    """
    logger.info("Generating HTML report")

    target = data.get("target", "N/A")
    timestamp = data.get("timestamp", utc_now_iso())
    enumeration = data.get("enumeration", {})
    pivots = data.get("pivots", {})
    consolidated = data.get("consolidated", {})

    profiles = enumeration.get("profiles", {})
    unique_emails = consolidated.get("unique_emails", [])
    highest_confidence = consolidated.get("highest_confidence", 0)

    parts: List[str] = []

    parts.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OSINT Report: {_esc(target)}</title>
<style>
    :root {{
        --primary: #6d4aff;
        --bg: #fafafa;
        --surface: #ffffff;
        --border: #e0e0e0;
        --text: #333333;
        --text-secondary: #666666;
        --success: #4caf50;
        --warning: #ff9800;
        --danger: #f44336;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.6;
        padding: 2rem;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
        background: var(--surface);
        border-radius: 8px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    h1 {{ color: var(--primary); font-size: 2rem; margin-bottom: 0.5rem; }}
    .meta {{ color: var(--text-secondary); font-size: 0.9rem; }}
    .kpi-strip {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }}
    .kpi-card {{
        background: var(--surface);
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }}
    .kpi-value {{ font-size: 2rem; font-weight: bold; color: var(--primary); }}
    .kpi-label {{ color: var(--text-secondary); font-size: 0.9rem; margin-top: 0.5rem; }}
    section {{
        background: var(--surface);
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    h2 {{
        color: var(--text);
        font-size: 1.25rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid var(--border);
        padding-bottom: 0.5rem;
    }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: var(--bg); font-weight: 600; }}
    tr:hover {{ background: var(--bg); }}
    .badge {{
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 500;
    }}
    .badge-high {{ background: #e8f5e9; color: var(--success); }}
    .badge-medium {{ background: #fff3e0; color: var(--warning); }}
    .badge-low {{ background: #ffebee; color: var(--danger); }}
    .profile-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 1rem;
        margin-top: 1rem;
    }}
    .profile-item {{ background: var(--bg); border-radius: 4px; padding: 1rem; }}
    .profile-platform {{ font-weight: 600; color: var(--primary); }}
    .profile-url {{
        font-size: 0.85rem;
        color: var(--text-secondary);
        word-break: break-all;
        margin-top: 0.25rem;
    }}
    footer {{
        text-align: center;
        color: var(--text-secondary);
        font-size: 0.85rem;
        margin-top: 3rem;
        padding: 1rem;
    }}
    .conf-meter {{
        height: 8px;
        background: var(--border);
        border-radius: 4px;
        overflow: hidden;
        margin-top: 4px;
    }}
    .conf-fill {{ height: 100%; background: var(--primary); }}
    .empty {{ color: var(--text-secondary); font-style: italic; }}
</style>
</head>
<body>
<div class="container">
<header>
    <h1>OSINT Investigation Report</h1>
    <p class="meta">Target: <strong>{_esc(target)}</strong></p>
    <p class="meta">Generated: {_esc(timestamp)}</p>
</header>

<div class="kpi-strip">
    <div class="kpi-card">
        <div class="kpi-value">{len(profiles)}</div>
        <div class="kpi-label">Profiles Discovered</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{len(unique_emails)}</div>
        <div class="kpi-label">Unique Emails</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-value">{highest_confidence}%</div>
        <div class="kpi-label">Highest Confidence</div>
    </div>
</div>
''')

    # Profiles section
    parts.append('<section>\n<h2>Discovered Profiles</h2>\n')
    if profiles:
        parts.append('<div class="profile-grid">\n')
        for platform, url in profiles.items():
            safe_url = _esc(url)
            parts.append(
                f'<div class="profile-item">'
                f'<div class="profile-platform">{_esc(platform.title())}</div>'
                f'<div class="profile-url"><a href="{safe_url}" rel="noopener noreferrer">'
                f'{safe_url}</a></div></div>\n'
            )
        parts.append('</div>\n')
    else:
        parts.append('<p class="empty">No profiles discovered.</p>\n')
    parts.append('</section>\n')

    # Email findings section
    parts.append('''<section>
<h2>Email Findings</h2>
<table>
<thead>
<tr><th>Email</th><th>Confidence</th><th>Sources</th><th>Risk</th></tr>
</thead>
<tbody>
''')

    raw_findings = data.get("raw_scored_findings", {}).get("scored_findings", [])
    if raw_findings:
        for finding in raw_findings:
            email = finding.get("email", "N/A")
            confidence = finding.get("confidence", 0)
            sources = "; ".join(finding.get("sources", []))

            if confidence >= 75:
                badge_class, risk_label = "badge-high", "High"
            elif confidence >= 50:
                badge_class, risk_label = "badge-medium", "Medium"
            else:
                badge_class, risk_label = "badge-low", "Low"

            parts.append(
                f'<tr>'
                f'<td><code>{_esc(email)}</code></td>'
                f'<td>{confidence}%'
                f'<div class="conf-meter"><div class="conf-fill" '
                f'style="width: {confidence}%"></div></div></td>'
                f'<td>{_esc(sources)}</td>'
                f'<td><span class="badge {badge_class}">{risk_label}</span></td>'
                f'</tr>\n'
            )
    else:
        parts.append('<tr><td colspan="4" class="empty">No emails discovered.</td></tr>\n')

    parts.append('</tbody>\n</table>\n</section>\n')

    # Pivot summary section
    parts.append('''<section>
<h2>Pivot Results Summary</h2>
<table>
<thead>
<tr><th>Pivot Module</th><th>Emails Found</th><th>Details</th></tr>
</thead>
<tbody>
''')

    if pivots:
        for pivot_name, pivot_data in pivots.items():
            emails = pivot_data.get("emails_found", [])
            details = ", ".join(
                f"{k}: {v}" for k, v in pivot_data.items()
                if k not in ("emails_found", "contacts_extracted")
            )
            parts.append(
                f'<tr><td>{_esc(pivot_name.title())}</td>'
                f'<td>{len(emails)}</td>'
                f'<td><small>{_esc(details)}</small></td></tr>\n'
            )
    else:
        parts.append('<tr><td colspan="3" class="empty">No pivots executed.</td></tr>\n')

    parts.append('''</tbody>
</table>
</section>

<footer>
<p>Generated by Username-to-Email OSINT Pipeline v1.0.0</p>
<p>This report is for authorized security research purposes only.</p>
</footer>
</div>
</body>
</html>''')

    return "".join(parts)


def write_to_file(content: str, filepath: Path) -> None:
    """
    Write content to file with proper encoding.

    Args:
        content: String content to write
        filepath: Destination path
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Report written to: {filepath}")


__all__ = [
    "generate_json_report",
    "generate_csv_report",
    "generate_html_report",
    "write_to_file",
    "utc_now_iso",
]