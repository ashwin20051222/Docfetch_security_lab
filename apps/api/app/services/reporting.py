"""Real report generation from stored tests and findings.

No report is produced unless at least one security test has actually
finished execution.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Finding, LabTarget, SecurityReport, SecurityTest

settings = get_settings()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_report_data(db: Session, target: LabTarget) -> dict:
    tests = list(
        db.scalars(
            select(SecurityTest)
            .where(SecurityTest.target_id == target.id)
            .order_by(SecurityTest.started_at)
        )
    )
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.target_id == target.id)
            .order_by(Finding.created_at)
        )
    )
    executed = [t for t in tests if t.status in ("passed", "failed")]
    finding_rows = [
        {
            "id": f.id,
            "severity": f.severity,
            "status": f.status,
            "title": f.title,
            "description": f.description,
            "expected_behavior": f.expected_behavior,
            "observed_behavior": f.observed_behavior,
            "recommendation": f.recommendation,
            "evidence": f.evidence,
            "created_at": f.created_at.isoformat(),
        }
        for f in findings
    ]
    data = {
        "report_id": "",
        "generated_at": _now(),
        "scope": (
            "Authorized security lab review of the named lab target. All testing was "
            "performed against infrastructure explicitly registered as an authorized "
            "lab target. No external or third-party systems were contacted."
        ),
        "target": {
            "id": target.id,
            "name": target.name,
            "base_url": target.base_url,
            "environment": target.environment_type,
            "authorization_status": target.auth_status,
        },
        "tests_executed": [
            {
                "id": t.id,
                "profile": t.profile,
                "title": t.title,
                "status": t.status,
                "started_at": t.started_at.isoformat(),
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                "request_summary": t.request_summary,
                "response_summary": t.response_summary,
                "error": t.error_message,
            }
            for t in executed
        ],
        "findings": finding_rows,
        "evidence": [
            {
                "test_id": t.id,
                "profile": t.profile,
                "evidence": t.evidence,
            }
            for t in executed
            if t.evidence
        ],
        "risk": (
            "Risk is limited to the registered lab target and derived entirely from "
            "observed response behavior captured during this review."
        ),
        "remediation": [f["recommendation"] for f in finding_rows],
        "limitations": [
            "Tests execute against authorized lab targets only.",
            "Findings reflect observed HTTP responses and do not constitute an exhaustive audit.",
            "No persistence of credentials, tokens, cookies, or document contents occurs.",
        ],
    }
    return data


def count_executed(db: Session, target_id: str) -> int:
    return len(
        list(
            db.scalars(
                select(SecurityTest).where(
                    SecurityTest.target_id == target_id,
                    SecurityTest.status.in_(["passed", "failed"]),
                )
            )
        )
    )


def generate_report(db: Session, target: LabTarget, fmt: str = "json") -> SecurityReport:
    executed = count_executed(db, target.id)
    if executed == 0:
        raise ValueError("No report available yet: no security test has executed.")

    data = build_report_data(db, target)
    findings = list(
        db.scalars(select(Finding).where(Finding.target_id == target.id))
    )

    rid = "%s-%s" % (target.name.lower().replace(" ", "-"), int(datetime.now().timestamp()))
    data["report_id"] = rid
    if fmt == "json":
        path = settings.reports_dir / f"{rid}.json"
        path.write_text(json.dumps(data, indent=2, default=str))
    elif fmt == "html":
        path = settings.reports_dir / f"{rid}.html"
        path.write_text(_render_html(data))
    else:
        raise ValueError(f"Unsupported report format: {fmt}")

    record = SecurityReport(
        target_id=target.id,
        format=fmt,
        path=str(path),
        finding_count=len(findings),
        summary={
            "executed_tests": executed,
            "findings": len(findings),
            "open_findings": sum(1 for f in findings if f.status == "open"),
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    from app.core.audit import record_audit

    record_audit(
        db,
        "report_generated",
        entity_type="security_report",
        entity_id=record.id,
        detail={"target_id": target.id, "format": fmt},
    )
    return record


def _render_html(data: dict) -> str:
    t = data["target"]
    rows = []
    for f in data["findings"]:
        rows.append(
            "<tr>"
            f"<td><span class='sev sev-{html.escape(f['severity'])}'>{html.escape(f['severity'].upper())}</span></td>"
            f"<td>{html.escape(f['title'])}</td>"
            f"<td>{html.escape(f['observed_behavior'])}</td>"
            f"<td>{html.escape(f['recommendation'])}</td>"
            + "</tr>"
        )
    test_rows = "".join(
        f"<tr><td>{html.escape(x['title'])}</td><td>{html.escape(x['status'])}</td>"
        f"<td>{x.get('started_at','')}</td></tr>"
        for x in data["tests_executed"]
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>DocFetch Security Lab — Report</title>
<style>
 body{{font-family:Inter,Arial,sans-serif;color:#0f172a;background:#f6f9f8;margin:2rem}}
 h1,h2{{font-family:'Space Grotesk','Inter',sans-serif}}
 .card{{background:#fff;border:1px solid #d1ded9;border-radius:12px;padding:1.25rem;margin:1rem 0}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{border-bottom:1px solid #edf3f1;text-align:left;padding:8px;font-size:13px;vertical-align:top}}
 th{{background:#f6f9f8;text-transform:uppercase;font-size:11px;letter-spacing:.03em;font-family:'JetBrains Mono',monospace;color:#334155}}
 .sev{{font-family:'JetBrains Mono',monospace;font-size:11px;padding:2px 6px;border-radius:4px;border:1px solid}}
 .sev-critical{{color:#b91c1c;background:#fef2f2;border-color:#fca5a5}}
 .sev-high{{color:#c2410c;background:#fff7ed;border-color:#fed7aa}}
 .sev-medium{{color:#b45309;background:#fffbeb;border-color:#fde68a}}
 .sev-low{{color:#475569;background:#f1f5f9;border-color:#cbd5e1}}
 .sev-informational{{color:#0f766e;background:#f0fdfa;border-color:#99f6e4}}
 pre{{background:#edf3f1;padding:.75rem;border-radius:8px;overflow:auto;font:12px 'JetBrains Mono',monospace}}
 .muted{{color:#64748b}}
</style></head><body>
<h1>DocFetch Security Lab — Security Report</h1>
<p class="muted">Generated {html.escape(data['generated_at'])}</p>
<div class="card"><h2>Scope</h2><p>{html.escape(data['scope'])}</p></div>
<div class="card"><h2>Target</h2>
<table><tbody>
<tr><th>Name</th><td>{html.escape(t['name'])}</td></tr>
<tr><th>Base URL</th><td><code>{html.escape(t['base_url'])}</code></td></tr>
<tr><th>Environment</th><td>{html.escape(t['environment'])}</td></tr>
<tr><th>Authorization status</th><td>{html.escape(t['authorization_status'])}</td></tr>
</tbody></table></div>
<div class="card"><h2>Tests executed</h2>
<table><thead><tr><th>Test</th><th>Result</th><th>Started</th></tr></thead><tbody>{test_rows}</tbody></table></div>
<div class="card"><h2>Findings ({len(data['findings'])})</h2>
<table><thead><tr><th>Severity</th><th>Title</th><th>Observed</th><th>Remediation</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class="card"><h2>Risk</h2><p>{html.escape(data['risk'])}</p></div>
<div class="card"><h2>Remediation</h2><ul>{"".join(f"<li>{html.escape(r)}</li>" for r in data['remediation'])}</ul></div>
<div class="card"><h2>Limitations</h2><ul>{"".join(f"<li>{html.escape(l)}</li>" for l in data['limitations'])}</ul></div>
</body></html>"""