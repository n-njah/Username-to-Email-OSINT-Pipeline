#!/usr/bin/env python3
"""
Outputs Module

Generates JSON, CSV, and HTML reports from correlated findings.
"""

import json
import csv
import io
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outputs")


def generate_json_report(data: Dict) -> str:
    """
    Generate formatted JSON report.
    
    Args:
        data: Complete report data from main pipeline
    
    Returns:
        Formatted JSON string
    """
    logger.info("Generating JSON report")
    
    # Add metadata
    report = {
        "report_version": "1.0.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data": data
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
    
    # Header
    writer.writerow([
        "email", "confidence", "source_count", "sources", "risk_category"
    ])
    
    # Data rows
    for finding in scored_findings.get("scored_findings", []):
        email = finding["email"]
        confidence = finding["confidence"]
        sources = ";".join(finding.get("sources", []))
        
        # Risk categorization
        if confidence >= 75:
            risk = "HIGH_CONFIDENCE"
        elif confidence >= 50:
            risk = "MEDIUM_CONFIDENCE"
        else:
            risk = "LOW_CONFIDENCE"
        
        writer.writerow([
            email, confidence, len(sources.split(";")), sources, risk
        ])
    
    return output.getvalue()


def generate_html_report(data: Dict) -> str:
    """
    Generate interactive HTML report.
    
    Args:
        data: Complete report data from main pipeline
    
    Returns:
        HTML string
    """
    logger.info("Generating HTML report")
    
    # Extract key data
    target = data.get("target", "N/A")
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())
    enumeration = data.get("enumeration", {})
    pivots = data.get("pivots", {})
    consolidated = data.get("consolidated", {})
    
    profiles = enumeration.get("profiles", {})
    unique_emails = consolidated.get("unique_emails", [])
    highest_confidence = consolidated.get("highest_confidence", 0)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OSINT Report: {target}</title>
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
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: var(--surface);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            color: var(--primary);
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        
        .meta {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}
        
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
        
        .kpi-value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--primary);
        }}
        
        .kpi-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }}
        
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
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: var(--bg);
            font-weight: 600;
        }}
        
        tr:hover {{
            background: var(--bg);
        }}
        
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        
        .badge-high {{
            background: #e8f5e9;
            color: var(--success);
        }}
        
        .badge-medium {{
            background: #fff3e0;
            color: var(--warning);
        }}
        
        .badge-low {{
            background: #ffebee;
            color: var(--danger);
        }}
        
        .profile-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        
        .profile-item {{
            background: var(--bg);
            border-radius: 4px;
            padding: 1rem;
        }}
        
        .profile-platform {{
            font-weight: 600;
            color: var(--primary);
        }}
        
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
        }}
        
        .conf-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--danger), var(--warning), var(--success));
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>OSINT Investigation Report</h1>
            <p class="meta">Target: <strong>{target}</strong></p>
            <p class="meta">Generated: {timestamp}</p>
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
        
        <section>
            <h2>Discovered Profiles</h2>
            <div class="profile-grid">
                '''
    
    # Add profiles
    for platform, url in profiles.items():
        html += f'''
                <div class="profile-item">
                    <div class="profile-platform">{platform.title()}</div>
                    <div class="profile-url"><a href="{url}" target="_blank">{url}</a></div>
                </div>
                '''
    
    html += '''
            </div>
        </section>
        
        <section>
            <h2>Email Findings</h2>
            <table>
                <thead>
                    <tr>
                        <th>Email</th>
                        <th>Confidence</th>
                        <th>Sources</th>
                        <th>Risk</th>
                    </tr>
                </thead>
                <tbody>
                '''
    
    # Add email findings
    raw_findings = data.get("raw_scored_findings", {}).get("scored_findings", [])
    for finding in raw_findings:
        email = finding.get("email", "N/A")
        confidence = finding.get("confidence", 0)
        sources = "; ".join(finding.get("sources", []))
        
        if confidence >= 75:
            badge_class = "badge-high"
            risk_label = "High"
        elif confidence >= 50:
            badge_class = "badge-medium"
            risk_label = "Medium"
        else:
            badge_class = "badge-low"
            risk_label = "Low"
        
        html += f'''
                    <tr>
                        <td><code>{email}</code></td>
                        <td>
                            {confidence}%
                            <div class="conf-meter">
                                <div class="conf-fill" style="width: {confidence}%"></div>
                            </div>
                        </td>
                        <td>{sources}</td>
                        <td><span class="badge {badge_class}">{risk_label}</span></td>
                    </tr>
                '''
    
    html += '''
                </tbody>
            </table>
        </section>
        
        <section>
            <h2>Pivot Results Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Pivot Module</th>
                        <th>Emails Found</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                '''
    
    # Add pivot summaries
    for pivot_name, pivot_data in pivots.items():
        emails = pivot_data.get("emails_found", [])
        details = ", ".join(f"{k}: {v}" for k, v in pivot_data.items() if k not in ["emails_found"])
        
        html += f'''
                    <tr>
                        <td>{pivot_name.title()}</td>
                        <td>{len(emails)}</td>
                        <td><small>{details}</small></td>
                    </tr>
                '''
    
    html += '''
                </tbody>
            </table>
        </section>
        
        <footer>
            <p>Generated by Username-to-Email OSINT Pipeline v1.0.0</p>
            <p>This report is for authorized security research purposes only.</p>
        </footer>
    </div>
</body>
</html>'''
    
    return html


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


# Export functions for direct import
__all__ = [
    "generate_json_report",
    "generate_csv_report", 
    "generate_html_report",
    "write_to_file"
]
