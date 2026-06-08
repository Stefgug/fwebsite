#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

try:
    import anthropic  # type: ignore
except Exception:
    anthropic = None

# --------- Paths ---------
ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "automation-reports"

PLAYWRIGHT_RESULTS_FILE = Path(
    os.environ.get("PLAYWRIGHT_RESULTS_FILE", str(ROOT / "frontend/test-results/results.json"))
)
COVERAGE_SUMMARY_FILE = Path(
    os.environ.get("COVERAGE_SUMMARY_FILE", str(ROOT / "frontend/coverage/coverage-summary.json"))
)

# --------- Environment ---------
JIRA_EPIC_KEY = os.environ.get("JIRA_EPIC_KEY", "UNKNOWN-EPIC")
JIRA_EPIC_TITLE = os.environ.get("JIRA_EPIC_TITLE", "No epic title provided")
JIRA_EPIC_DESCRIPTION = os.environ.get("JIRA_EPIC_DESCRIPTION", "")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")

UNIT_OUTCOME = os.environ.get("UNIT_OUTCOME", "unknown")
E2E_OUTCOME = os.environ.get("E2E_OUTCOME", "unknown")

GITHUB_SHA = os.environ.get("GITHUB_SHA", "")
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass
class PlaywrightFailure:
    file: str
    test: str
    error: str


# --------- Data loading ---------

def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_epic_key_from_text(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", text)
    return m.group(1) if m else None


def hydrate_epic_from_env_or_event() -> None:
    global JIRA_EPIC_KEY, JIRA_EPIC_TITLE, JIRA_EPIC_DESCRIPTION

    if JIRA_EPIC_KEY and JIRA_EPIC_KEY != "UNKNOWN-EPIC":
        return

    candidates = [
        os.environ.get("GIT_EVENT_REF", ""),
        os.environ.get("GITHUB_REF_NAME", ""),
        os.environ.get("GITHUB_HEAD_REF", ""),
        os.environ.get("GITHUB_REF", ""),
    ]

    for c in candidates:
        key = extract_epic_key_from_text(c)
        if key:
            JIRA_EPIC_KEY = key
            break

    if not JIRA_EPIC_KEY or JIRA_EPIC_KEY == "UNKNOWN-EPIC":
        return

    if (
        JIRA_EMAIL
        and JIRA_API_TOKEN
        and (not JIRA_EPIC_TITLE or JIRA_EPIC_TITLE == "No epic title provided")
    ):
        try:
            res = requests.get(
                f"{JIRA_BASE_URL}/rest/api/3/issue/{JIRA_EPIC_KEY}",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if res.ok:
                fields = (res.json() or {}).get("fields", {})
                summary = fields.get("summary")
                description = fields.get("description")
                if isinstance(summary, str) and summary.strip():
                    JIRA_EPIC_TITLE = summary
                if description:
                    JIRA_EPIC_DESCRIPTION = json.dumps(description, ensure_ascii=False)[:3000]
        except Exception:
            pass


# --------- Parsers ---------

def parse_playwright_results(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "failures": []}

    failures: list[PlaywrightFailure] = []
    total = passed = failed = skipped = 0

    def walk(suites: list[dict[str, Any]], inherited_file: str = "") -> None:
        nonlocal total, passed, failed, skipped
        for suite in suites:
            suite_file = suite.get("file") or inherited_file
            for child in suite.get("suites", []) or []:
                walk([child], suite_file)

            for spec in suite.get("specs", []) or []:
                title = spec.get("title", "(untitled)")
                for test in spec.get("tests", []) or []:
                    total += 1
                    status = test.get("status")
                    if status == "expected":
                        passed += 1
                    elif status == "skipped":
                        skipped += 1
                    else:
                        failed += 1
                        result = next(
                            (
                                r
                                for r in reversed(test.get("results", []) or [])
                                if r.get("status") in ("failed", "timedOut")
                            ),
                            {},
                        )
                        err_msg = (
                            (result.get("error") or {}).get("message")
                            or result.get("error")
                            or "No error message"
                        )
                        failures.append(
                            PlaywrightFailure(
                                file=suite_file or "unknown-file",
                                test=title,
                                error=str(err_msg)[:1200],
                            )
                        )

    walk(data.get("suites", []) or [])
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": [f.__dict__ for f in failures],
    }


def parse_coverage_summary(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data or "total" not in data:
        return {
            "lines_pct": 0.0,
            "functions_pct": 0.0,
            "branches_pct": 0.0,
            "statements_pct": 0.0,
            "low_files": [],
        }

    total = data["total"]
    out = {
        "lines_pct": float(total.get("lines", {}).get("pct", 0.0)),
        "functions_pct": float(total.get("functions", {}).get("pct", 0.0)),
        "branches_pct": float(total.get("branches", {}).get("pct", 0.0)),
        "statements_pct": float(total.get("statements", {}).get("pct", 0.0)),
        "low_files": [],
    }

    low_files = []
    for key, value in data.items():
        if key == "total" or not isinstance(value, dict):
            continue
        lp = float((value.get("lines") or {}).get("pct", 0.0))
        if lp < 50.0:
            low_files.append(
                {
                    "file": str(key).replace("\\", "/"),
                    "lines_pct": lp,
                    "functions_pct": float((value.get("functions") or {}).get("pct", 0.0)),
                    "branches_pct": float((value.get("branches") or {}).get("pct", 0.0)),
                }
            )
    low_files.sort(key=lambda x: x["lines_pct"])
    out["low_files"] = low_files
    return out


# --------- AI triage ---------

def fallback_triage(playwright: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    """Deterministic fallback when Anthropic API is unavailable."""
    failing_tests = []
    for f in playwright.get("failures", [])[:5]:
        failing_tests.append({
            "test_name": f["test"],
            "functional_impact": f"The test '{f['test']}' failed — users may experience a broken feature or degraded experience.",
            "qa_action": f"Manually verify the user journey for '{f['test']}' and check if the underlying feature still works.",
        })

    blind_spots = []
    for lf in coverage.get("low_files", [])[:8]:
        short = lf["file"].split("/frontend/")[-1]
        blind_spots.append(f"Manually verify functionality related to '{short}' (only {lf['lines_pct']:.0f}% line coverage).")

    if not blind_spots:
        blind_spots = [
            "Manually verify the complete purchase flow from product selection to checkout.",
            "Test the site on mobile and tablet viewports for responsive layout issues.",
            "Verify error handling by submitting forms with invalid data.",
            "Check accessibility with a screen reader for critical user journeys.",
            "Test performance under slow network conditions (throttled 3G).",
        ]

    all_pass = playwright.get("failed", 0) == 0

    return {
        "summary": (
            f"All {playwright.get('total', 0)} tests passed successfully. No issues detected."
            if all_pass
            else f"{playwright.get('failed', 0)} of {playwright.get('total', 0)} tests failed. "
            f"Unit coverage is at {coverage.get('lines_pct', 0):.1f}%. AI analysis was unavailable; triage is deterministic."
        ),
        "failing_tests": failing_tests,
        "blind_spots": blind_spots,
    }


def ai_triage(playwright: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    if not ANTHROPIC_API_KEY or anthropic is None:
        return fallback_triage(playwright, coverage)

    payload = {
        "epic": {
            "key": JIRA_EPIC_KEY,
            "title": JIRA_EPIC_TITLE,
            "description": JIRA_EPIC_DESCRIPTION[:3000],
        },
        "unit_outcome": UNIT_OUTCOME,
        "e2e_outcome": E2E_OUTCOME,
        "playwright": playwright,
        "coverage": {
            "lines_pct": coverage.get("lines_pct"),
            "functions_pct": coverage.get("functions_pct"),
            "branches_pct": coverage.get("branches_pct"),
            "low_files": coverage.get("low_files", [])[:10],
        },
    }

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1800,
        messages=[
            {
                "role": "user",
                "content": (
                    "You are a QA lead analysing test results for a non-technical audience.\n\n"
                    "Given the test run data below, produce a JSON object with exactly these keys:\n\n"
                    "- \"summary\": 2-3 plain-English sentences describing overall test health and what it means for the product.\n"
                    "- \"failing_tests\": an array of objects, one per failing test. Each object has:\n"
                    "    - \"test_name\": the name of the failing test\n"
                    "    - \"functional_impact\": one plain-English sentence describing the broken user experience (no code, no jargon)\n"
                    "    - \"qa_action\": one concrete non-code action a QA person should take (e.g. \"Manually verify the login flow works on Chrome\")\n"
                    "- \"blind_spots\": an array of 3-5 strings, each describing a functional user journey the test suite does NOT cover, "
                    "written as what a QA person should manually verify.\n\n"
                    "Return ONLY the JSON object — no markdown fences, no prose before or after.\n\n"
                    f"INPUT DATA:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
                ),
            }
        ],
    )

    text_parts = [c.text for c in msg.content if getattr(c, "type", "") == "text"]
    text = "\n".join(text_parts).strip()

    # Try to parse JSON from the response
    try:
        # Strip markdown fences if present
        cleaned = text
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned)
            cleaned = re.sub(r"\n```\s*$", "", cleaned)
        result = json.loads(cleaned)
        # Validate required keys
        if all(k in result for k in ("summary", "failing_tests", "blind_spots")):
            return result
    except Exception:
        pass

    # If parsing fails, print raw response and use fallback
    print(f"AI response could not be parsed as JSON. Raw response:\n{text}")
    fallback = fallback_triage(playwright, coverage)
    fallback["ai_raw_response"] = text[:2000]
    return fallback


# --------- HTML helpers ---------

def status_badge(ok: bool, label: str) -> str:
    icon = "✅" if ok else "❌"
    klass = "ok" if ok else "ko"
    return f'<span class="badge {klass}">{icon} {html.escape(label)}</span>'


def coverage_bar(pct: float) -> str:
    p = max(0.0, min(100.0, float(pct)))
    if p >= 80:
        color = "#2ecc71"
    elif p >= 50:
        color = "#f39c12"
    else:
        color = "#e74c3c"
    return (
        '<div class="bar"><div class="fill" style="width:'
        f'{p:.1f}%; background:{color};"></div></div>'
        f'<div class="pct">{p:.1f}%</div>'
    )


# --------- Dashboard HTML ---------

def dashboard_html(summary: dict[str, Any], triage: dict[str, Any]) -> str:
    cov = summary["coverage"]
    pw = summary["playwright"]

    all_pass = pw.get("failed", 0) == 0
    summary_color = "#2ecc71" if all_pass else "#e74c3c"
    summary_border = "4px solid #2ecc71" if all_pass else "4px solid #e74c3c"

    # Suite status cards
    unit_card = f"""<div class="card">
        <div class="card-title">Unit Tests (Vitest)</div>
        <div class="card-badge {'badge-pass' if UNIT_OUTCOME == 'success' else 'badge-fail'}">{'✅ PASS' if UNIT_OUTCOME == 'success' else '❌ FAIL'}</div>
        <div class="card-detail">{'Passed' if UNIT_OUTCOME == 'success' else 'Some tests failed'}</div>
        {coverage_bar(cov['lines_pct'])}
    </div>"""

    e2e_card = f"""<div class="card">
        <div class="card-title">E2E Tests (Playwright)</div>
        <div class="card-badge {'badge-pass' if E2E_OUTCOME == 'success' else 'badge-fail'}">{'✅ PASS' if E2E_OUTCOME == 'success' else '❌ FAIL'}</div>
        <div class="card-detail">{pw['passed']} / {pw['total']} passed</div>
    </div>"""

    # Failing tests table
    failing_tests = triage.get("failing_tests", [])
    if failing_tests:
        fail_rows = "\n".join(
            f"""<tr>
                <td>{html.escape(ft.get('test_name', 'Unknown'))}</td>
                <td>{html.escape(ft.get('functional_impact', 'No impact description'))}</td>
                <td>{html.escape(ft.get('qa_action', 'No action specified'))}</td>
            </tr>"""
            for ft in failing_tests
        )
        failing_section = f"""<h2>Failing Tests — Functional Impact</h2>
        <table>
            <thead><tr><th>Test Name</th><th>Functional Impact</th><th>QA Action</th></tr></thead>
            <tbody>{fail_rows}</tbody>
        </table>"""
    else:
        failing_section = ""

    # Blind spots
    blind_spots = triage.get("blind_spots", [])
    blind_items = "\n".join(f"<li>⚠️ {html.escape(bs)}</li>" for bs in blind_spots)
    blind_section = f"""<div class="blind-spots-card">
        <h2>Blind Spots — Areas Not Covered by Automated Tests</h2>
        <ul>{blind_items}</ul>
        <p class="blind-note"><em>These areas should be verified manually or a new automated test should be requested.</em></p>
    </div>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>QA Test Dashboard — {html.escape(JIRA_EPIC_KEY)}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #1a1a2e; }}
    .header {{ background: #1a1a2e; color: white; padding: 24px 32px; }}
    .header h1 {{ font-size: 24px; margin-bottom: 4px; }}
    .header .subtitle {{ font-size: 14px; color: #a0a0b8; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px; }}
    .summary-banner {{ background: white; border-left: {summary_border}; border-radius: 8px; padding: 20px 24px; margin-bottom: 24px; font-size: 15px; line-height: 1.6; color: #333; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
    .card-title {{ font-size: 13px; color: #64748b; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .card-badge {{ display: inline-block; font-size: 14px; font-weight: 700; padding: 6px 14px; border-radius: 6px; margin-bottom: 8px; }}
    .badge-pass {{ background: #d4edda; color: #155724; }}
    .badge-fail {{ background: #f8d7da; color: #721c24; }}
    .card-detail {{ font-size: 14px; color: #475569; margin-bottom: 12px; }}
    .bar {{ width: 100%; height: 10px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: 6px; }}
    .fill {{ height: 100%; border-radius: 999px; }}
    .pct {{ font-size: 12px; color: #475569; margin-top: 4px; }}
    h2 {{ font-size: 18px; color: #1a1a2e; margin: 24px 0 12px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
    th, td {{ text-align: left; padding: 12px 16px; font-size: 13px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
    th {{ background: #f8fafc; font-weight: 600; color: #475569; }}
    tr:nth-child(even) td {{ background: #fafbfc; }}
    .blind-spots-card {{ background: white; border-left: 6px solid #f39c12; border-radius: 8px; padding: 20px 24px; margin-top: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
    .blind-spots-card ul {{ padding-left: 20px; margin-top: 12px; }}
    .blind-spots-card li {{ margin-bottom: 8px; line-height: 1.5; font-size: 14px; }}
    .blind-note {{ margin-top: 16px; color: #64748b; font-size: 13px; }}
    .footer {{ text-align: center; padding: 24px; color: #94a3b8; font-size: 12px; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>QA Test Dashboard</h1>
    <div class="subtitle">Run: {html.escape(RUN_TIMESTAMP)} · Epic: {html.escape(JIRA_EPIC_KEY)}</div>
  </div>

  <div class="container">
    <div class="summary-banner">{html.escape(triage.get('summary', 'No summary available.'))}</div>

    <div class="grid">
      {unit_card}
      {e2e_card}
    </div>

    {failing_section}

    {blind_section}

    <div class="footer">Generated by AI Test Pipeline · Stefgug/fwebsite</div>
  </div>
</body>
</html>"""


# --------- Report writing ---------

def write_reports(summary: dict[str, Any], triage: dict[str, Any]) -> tuple[Path, Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = REPORTS_DIR / "workflow-summary.json"
    report_path = REPORTS_DIR / "ai-triage-report.md"
    dash_path = REPORTS_DIR / "dashboard.html"

    # Store full data including triage in summary
    full_summary = {**summary, "ai_triage": triage}
    summary_path.write_text(json.dumps(full_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # GitHub Pages requires index.html as entry point
    index_path = REPORTS_DIR / "index.html"
    index_path.write_text(dashboard_html(summary, triage), encoding="utf-8")

    # Build readable markdown report
    ai_summary = triage.get("summary", "No summary available.")
    failing = triage.get("failing_tests", [])
    blind = triage.get("blind_spots", [])

    report_lines = [
        f"# AI Test Workflow Report — {JIRA_EPIC_KEY}",
        "",
        f"**Epic:** {JIRA_EPIC_TITLE}",
        f"**Run:** {GITHUB_RUN_ID or 'local'}",
        f"**Commit:** {(GITHUB_SHA or '')[:8]}",
        "",
        "## Gate status",
        f"- Unit tests: {UNIT_OUTCOME}",
        f"- E2E tests: {E2E_OUTCOME}",
        f"- Coverage lines: {summary['coverage']['lines_pct']:.2f}%",
        f"- Workflow gate: {'PASS' if summary['workflow_ok'] else 'FAIL'}",
        "",
        "## AI Summary",
        ai_summary,
        "",
    ]

    if failing:
        report_lines.append("## Failing Tests — Functional Impact")
        report_lines.append("")
        for ft in failing:
            report_lines.append(f"- **{ft.get('test_name', 'Unknown')}**: {ft.get('functional_impact', 'N/A')}")
            report_lines.append(f"  → QA Action: {ft.get('qa_action', 'N/A')}")
        report_lines.append("")

    if blind:
        report_lines.append("## Blind Spots — Areas Not Covered")
        report_lines.append("")
        for bs in blind:
            report_lines.append(f"- ⚠️ {bs}")
        report_lines.append("")
        report_lines.append("*These areas should be verified manually or a new automated test should be requested.*")
        report_lines.append("")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    dash_path.write_text(dashboard_html(summary, triage), encoding="utf-8")
    return summary_path, report_path, dash_path



# --------- Jira comment ---------

def _adf_text(text: str, href: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": text}
    if href:
        node["marks"] = [{"type": "link", "attrs": {"href": href}}]
    return node


def post_jira_epic_comment(summary: dict[str, Any], pages_url: str) -> bool:
    if not (JIRA_EMAIL and JIRA_API_TOKEN):
        return False
    if not JIRA_EPIC_KEY or JIRA_EPIC_KEY == "UNKNOWN-EPIC":
        return False

    cov = summary["coverage"]
    pw = summary["playwright"]
    gate = "PASS ✅" if summary["workflow_ok"] else "FAIL ❌"

    body_content: list[dict[str, Any]] = [
        {"type": "paragraph", "content": [_adf_text(f"\U0001f916 AI test pipeline finished — gate: {gate}")]},
        {
            "type": "paragraph",
            "content": [
                _adf_text(
                    f"Unit: {UNIT_OUTCOME} · E2E: {E2E_OUTCOME} · "
                    f"Coverage (lines): {cov['lines_pct']:.2f}% · "
                    f"Playwright: {pw['passed']}/{pw['total']} passed, {pw['failed']} failed"
                )
            ],
        },
    ]
    if pages_url:
        body_content.append(
            {
                "type": "paragraph",
                "content": [_adf_text("\U0001f4ca Live QA report: "), _adf_text(pages_url, pages_url)],
            }
        )

    try:
        res = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{JIRA_EPIC_KEY}/comment",
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"body": {"type": "doc", "version": 1, "content": body_content}},
            timeout=20,
        )
        return res.ok
    except Exception:
        return False

# --------- Main ---------

def main() -> None:
    hydrate_epic_from_env_or_event()

    pw = parse_playwright_results(load_json(PLAYWRIGHT_RESULTS_FILE))
    cov = parse_coverage_summary(load_json(COVERAGE_SUMMARY_FILE))

    workflow_ok = UNIT_OUTCOME == "success" and E2E_OUTCOME == "success" and cov["lines_pct"] >= 50.0
    summary = {
        "epic": {"key": JIRA_EPIC_KEY, "title": JIRA_EPIC_TITLE, "description": JIRA_EPIC_DESCRIPTION},
        "git": {"sha": GITHUB_SHA, "run_id": GITHUB_RUN_ID},
        "unit_outcome": UNIT_OUTCOME,
        "e2e_outcome": E2E_OUTCOME,
        "playwright": pw,
        "coverage": cov,
        "workflow_ok": workflow_ok,
    }

    triage = ai_triage(pw, cov)
    summary_path, report_path, dash_path = write_reports(summary, triage)

    pages_url = "https://stefgug.github.io/fwebsite/"
    jira_commented = post_jira_epic_comment(summary, pages_url)

    gh_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_step_summary:
        with open(gh_step_summary, "a", encoding="utf-8") as f:
            f.write("## 🧪 AI Test Workflow Summary\n")
            f.write(f"- Epic: **{JIRA_EPIC_KEY}** — {JIRA_EPIC_TITLE}\n")
            f.write(f"- Unit tests: `{UNIT_OUTCOME}`\n")
            f.write(f"- E2E tests: `{E2E_OUTCOME}`\n")
            f.write(f"- Coverage lines: `{cov['lines_pct']:.2f}%`\n")
            f.write(f"- Workflow gate: **{'PASS ✅' if workflow_ok else 'FAIL ❌'}**\n")
            f.write("\nArtifacts:\n")
            f.write("- `automation-reports/dashboard.html`\n")
            f.write("- `automation-reports/ai-triage-report.md`\n")
            f.write("- `automation-reports/workflow-summary.json`\n")
            f.write(f"- Live report (GitHub Pages): {pages_url}\n")
            f.write(f"- Jira epic comment posted: {'yes' if jira_commented else 'no'}\n")

    print(f"summary={summary_path}")
    print(f"report={report_path}")
    print(f"dashboard={dash_path}")
    if jira_commented:
        print("jira_comment=posted")


if __name__ == "__main__":
    main()
