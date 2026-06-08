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
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")

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

    <div style="text-align:center;margin-top:24px;">
      <a href="catalog.html" style="display:inline-block;padding:10px 22px;background:#3b82f6;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">📋 View Test Catalog</a>
    </div>

    <div class="footer">Generated by AI Test Pipeline · Stefgug/fwebsite</div>
  </div>
</body>
</html>"""


# --------- Report writing ---------

def write_reports(summary: dict[str, Any], triage: dict[str, Any], jira_bug_links: dict | None = None, proposals: list | None = None) -> tuple[Path, Path, Path]:
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

    # Test catalog page
    (REPORTS_DIR / "proposed-tests.json").write_text(
        json.dumps(
            {"generated_at": RUN_TIMESTAMP, "epic_key": JIRA_EPIC_KEY,
             "run_id": GITHUB_RUN_ID, "proposals": proposals or []},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    catalog_html = generate_catalog_html(summary["playwright"], triage, jira_bug_links, proposals)
    catalog_path = REPORTS_DIR / "catalog.html"
    catalog_path.write_text(catalog_html, encoding="utf-8")
    print(f"  ✅ catalog.html written ({len(catalog_html):,} bytes)")

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

# --------- Auto-create Jira Bugs for failing tests ---------

def create_jira_bugs_for_failing_tests(triage: dict, epic_key: str) -> dict[str, dict]:
    """Auto-create a Jira Bug for each failing test. Returns {test_name: {key, url}}."""
    if not (JIRA_EMAIL and JIRA_API_TOKEN):
        print("  ⚠️  Skipping Jira bug creation — JIRA_EMAIL or JIRA_API_TOKEN not set")
        return {}
    if not epic_key or epic_key == "UNKNOWN-EPIC":
        print("  ⚠️  Skipping Jira bug creation — no valid Epic key")
        return {}

    failing_tests = triage.get("failing_tests", [])
    if not failing_tests:
        return {}

    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    jira_links: dict[str, dict] = {}

    for ft in failing_tests:
        test_name = ft.get("test_name", "Unknown test")
        functional_impact = ft.get("functional_impact", "No impact description available.")
        qa_action = ft.get("qa_action", "No action specified.")

        description_content: list[dict[str, Any]] = [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "🤖 Auto-generated by the AI Test Pipeline", "marks": [{"type": "strong"}]}
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Failing test: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": test_name},
                ],
            },
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Functional Impact"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": functional_impact}]},
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Suggested QA Action"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": qa_action}]},
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "References"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "📊 QA Report: "},
                    {
                        "type": "text",
                        "text": "https://stefgug.github.io/fwebsite/",
                        "marks": [{"type": "link", "attrs": {"href": "https://stefgug.github.io/fwebsite/"}}],
                    },
                ],
            },
        ]

        payload: dict[str, Any] = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "issuetype": {"name": "Bug"},
                "summary": f"[QA] Failing test: {test_name}",
                "description": {"type": "doc", "version": 1, "content": description_content},
                "parent": {"key": epic_key},
                "labels": ["automated-bug", "playwright"],
            }
        }

        def _try_create(p: dict[str, Any]) -> dict[str, Any] | None:
            try:
                r = requests.post(
                    f"{JIRA_BASE_URL}/rest/api/3/issue",
                    auth=auth,
                    headers=headers,
                    json=p,
                    timeout=20,
                )
                if r.ok:
                    return r.json()
                print(f"    HTTP {r.status_code}: {r.text[:300]}")
            except Exception as exc:
                print(f"    Exception: {exc}")
            return None

        result = _try_create(payload)

        # Fallback: if Bug issue type not found, retry with Task
        if result is None:
            print(f"  ⚠️  'Bug' type failed for '{test_name}' — retrying with 'Task'")
            payload["fields"]["issuetype"] = {"name": "Task"}
            result = _try_create(payload)

        if result:
            issue_key = result.get("key", "")
            issue_url = f"{JIRA_BASE_URL}/browse/{issue_key}"
            jira_links[test_name] = {"key": issue_key, "url": issue_url}
            print(f"  ✅ Created Jira issue {issue_key} for failing test: '{test_name}'")
        else:
            print(f"  ❌ Could not create Jira issue for '{test_name}'")

    return jira_links


# --------- Test Catalog ---------

def generate_catalog_html(pw_results: dict, triage: dict | None = None, jira_bug_links: dict | None = None, proposals: list | None = None) -> str:
    """Parse spec files and cross-reference with Playwright results to build catalog HTML."""
    import re
    from urllib.parse import quote_plus
    from pathlib import Path

    ROOT = Path(__file__).parent.parent

    SPEC_AREAS = {
        "home.spec.ts": ("Homepage", "Tests the homepage hero, CTAs, categories, featured products and blog sections."),
        "navigation.spec.ts": ("Navigation", "Tests navbar links, cart icon, login link visibility and 404 handling."),
        "products.spec.ts": ("Product Catalog", "Tests product listing, category filtering, product cards and detail page access."),
        "cart.spec.ts": ("Shopping Cart", "Tests empty cart state, adding products, cart badge counter and checkout button."),
        "auth.spec.ts": ("Authentication", "Tests the login and registration forms, validation and successful auth flow."),
        "about.spec.ts": ("About Page", "Tests all content sections, statistics, values cards and CTA navigation."),
    }

    # Build failed test name set
    failed_tests = set()
    for f in pw_results.get("failures", []):
        failed_tests.add(f.get("test", ""))

    # Build triage lookup: test_name -> {functional_impact, qa_action}
    triage_by_test: dict = {}
    if triage:
        for ft in triage.get("failing_tests", []):
            triage_by_test[ft.get("test_name", "")] = ft

    e2e_ran = pw_results.get("total", 0) > 0

    proposals_html = proposals_section_html(proposals or [])

    # Build area cards HTML
    area_cards_html = ""
    total_tests = 0

    for spec_file, (area_name, description) in SPEC_AREAS.items():
        spec_path = ROOT / "frontend" / "tests" / spec_file
        test_names = []
        try:
            content = spec_path.read_text(encoding="utf-8")
            test_names = re.findall(r"test\(['\"](.+?)['\"]", content)
        except Exception:
            test_names = []

        total_tests += len(test_names)

        rows_html = ""
        for test_name in test_names:
            if test_name in failed_tests:
                status_badge = '<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">❌ Fail</span>'
            elif e2e_ran:
                status_badge = '<span style="background:#2ecc71;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">✅ Pass</span>'
            else:
                status_badge = '<span style="background:#888;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">⚪ Unknown</span>'

            display_name = test_name[0].upper() + test_name[1:] if test_name else test_name

            # Action button: Jira bug link for failed tests (if created), else GitHub fallback
            if test_name in failed_tests and jira_bug_links and test_name in jira_bug_links:
                jira_info = jira_bug_links[test_name]
                action_cell = (
                    f'<a href="{jira_info["url"]}" target="_blank" '
                    f'style="background:#e74c3c;color:#fff;padding:3px 10px;border-radius:4px;'
                    f'font-size:12px;text-decoration:none;font-weight:600;">🐛 {jira_info["key"]}</a>'
                )
            else:
                encoded_name = quote_plus(test_name)
                encoded_area = quote_plus(area_name)
                if test_name in failed_tests and test_name in triage_by_test:
                    ti = triage_by_test[test_name]
                    issue_body = (
                        f"**Area:** {area_name}\n"
                        f"**Test:** {test_name}\n\n"
                        f"**What broke:**\n{ti.get('functional_impact', '')}\n\n"
                        f"**Suggested QA action:**\n{ti.get('qa_action', '')}\n\n"
                        f"---\n*Auto-generated from the AI test pipeline report.*"
                    )
                else:
                    issue_body = (
                        f"Area: {area_name}\nTest: {test_name}\n\nDescribe the issue or improvement needed:"
                    )
                flag_url = (
                    f"https://github.com/Stefgug/fwebsite/issues/new"
                    f"?title=Test+flag:+{encoded_name}"
                    f"&body={quote_plus(issue_body)}"
                )
                link_style = (
                    "color:#e67e22;font-size:12px;text-decoration:none;"
                    if test_name in failed_tests
                    else "color:#94a3b8;font-size:12px;text-decoration:none;"
                )
                link_label = "🚩 Report issue" if test_name in failed_tests else "🚩 Flag"
                action_cell = f'<a href="{flag_url}" target="_blank" style="{link_style}">{link_label}</a>'

            rows_html += f"""
                <tr style="border-bottom:1px solid #e0e0e0;">
                    <td style="padding:10px 12px;white-space:nowrap;">{status_badge}</td>
                    <td style="padding:10px 12px;color:#2d3748;">{display_name}</td>
                    <td style="padding:10px 12px;white-space:nowrap;">{action_cell}</td>
                </tr>"""

        if not test_names:
            rows_html = '<tr><td colspan="3" style="padding:12px;color:#888;font-style:italic;">No tests parsed from spec file.</td></tr>'

        count_badge = f'<span style="background:#3b82f6;color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">{len(test_names)} tests</span>'

        area_cards_html += f"""
        <div style="background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:28px;overflow:hidden;border-left:5px solid #3b82f6;">
            <div style="padding:18px 22px 10px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
                <h2 style="margin:0;font-size:20px;color:#1a1a2e;flex:1;">{area_name}</h2>
                {count_badge}
                <a href="https://github.com/Stefgug/fwebsite/blob/main/frontend/tests/{spec_file}" target="_blank" style="font-size:12px;color:#6b7280;text-decoration:none;white-space:nowrap;">📂 View on GitHub</a>
            </div>
            <div style="padding:0 22px 12px 22px;color:#718096;font-size:14px;">{description}</div>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;font-size:14px;">
                    <thead>
                        <tr style="background:#f7f8fa;border-bottom:2px solid #e0e0e0;">
                            <th style="padding:10px 12px;text-align:left;color:#4a5568;font-weight:600;width:110px;">Status</th>
                            <th style="padding:10px 12px;text-align:left;color:#4a5568;font-weight:600;">Test Name</th>
                            <th style="padding:10px 12px;text-align:left;color:#4a5568;font-weight:600;width:120px;">Flag</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}
                    </tbody>
                </table>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Catalog — {JIRA_EPIC_KEY}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #2d3748; }}
        a {{ color: #3b82f6; }}
    </style>
</head>
<body>
    <header style="background:#1a1a2e;color:#fff;padding:28px 32px 24px 32px;">
        <div style="max-width:960px;margin:0 auto;">
            <div style="font-size:13px;color:#a0aec0;margin-bottom:6px;">
                <a href="index.html" style="color:#a0aec0;text-decoration:none;">← Back to Dashboard</a>
            </div>
            <h1 style="font-size:28px;font-weight:700;margin-bottom:6px;">📋 Test Catalog</h1>
            <div style="color:#a0aec0;font-size:14px;">
                Epic: <strong style="color:#e2e8f0;">{JIRA_EPIC_KEY} — {JIRA_EPIC_TITLE}</strong>
                &nbsp;·&nbsp; Run: <code style="color:#e2e8f0;">{GITHUB_RUN_ID}</code>
                &nbsp;·&nbsp; {RUN_TIMESTAMP}
            </div>
        </div>
    </header>

    <main style="max-width:960px;margin:32px auto;padding:0 20px;">
        <p style="background:#fff;border-radius:8px;padding:16px 20px;color:#4a5568;font-size:15px;box-shadow:0 1px 4px rgba(0,0,0,0.06);margin-bottom:28px;line-height:1.6;">
            This catalog lists all automated Playwright tests. QA testers can use this page to understand test coverage and flag tests that need attention.
        </p>

        {proposals_html}

        {area_cards_html}
    </main>

    <footer style="text-align:center;padding:24px;color:#a0aec0;font-size:13px;border-top:1px solid #e2e8f0;margin-top:16px;">
        QA Test Catalog &nbsp;·&nbsp; Generated by AI Test Pipeline &nbsp;·&nbsp; Stefgug/fwebsite
    </footer>
</body>
</html>"""

    return html


# --------- Test Proposal Generation (Phase 1) ---------

SPEC_FILES = [
    "home.spec.ts", "navigation.spec.ts", "products.spec.ts",
    "cart.spec.ts", "auth.spec.ts", "about.spec.ts",
]


def read_all_spec_files() -> dict[str, str]:
    """Return {spec_filename: full_source} for all known spec files."""
    specs: dict[str, str] = {}
    for name in SPEC_FILES:
        p = ROOT / "frontend" / "tests" / name
        try:
            specs[name] = p.read_text(encoding="utf-8")
        except Exception:
            specs[name] = ""
    return specs


def _all_existing_test_names(specs: dict[str, str]) -> set[str]:
    names: set[str] = set()
    for src in specs.values():
        for m in re.findall(r"test\(['\"](.+?)['\"]", src):
            names.add(m.strip())
    return names


def generate_test_proposals(triage: dict[str, Any], playwright: dict[str, Any]) -> list[dict[str, Any]]:
    """Ask Claude to propose NEW tests (for blind spots) and MODIFICATIONS (for failing
    tests that are genuinely outdated), ensuring no proposal duplicates existing coverage."""
    if not ANTHROPIC_API_KEY or anthropic is None:
        return []

    failing = triage.get("failing_tests", [])
    blind_spots = triage.get("blind_spots", [])
    if not failing and not blind_spots:
        return []

    specs = read_all_spec_files()
    existing_names = _all_existing_test_names(specs)
    specs_blob = "\n\n".join(
        f"=== frontend/tests/{name} ===\n{src}" for name, src in specs.items() if src
    )
    failing_blob = json.dumps(failing, ensure_ascii=False, indent=2)
    blind_blob = json.dumps(blind_spots, ensure_ascii=False, indent=2)

    prompt = f"""You are a senior QA automation engineer working on a Playwright E2E suite for an e-commerce site (Next.js, baseURL http://localhost:3000, backed by mock data).

Your job: propose HIGH-VALUE end-to-end / business-level test improvements - NEVER trivial micro-tests. Two kinds:
1. "new_test" - for a genuine COVERAGE GAP (blind spot) not already tested anywhere.
2. "modify_test" - ONLY when an existing test FAILED because the application legitimately changed and the test is now outdated. If a test failed because it caught a REAL BUG (the app is broken / behaving wrongly), DO NOT propose modifying the test to make it pass - that would hide the bug. Skip it instead.

CRITICAL DEDUP RULE: Before proposing any new_test, verify the behaviour is not ALREADY covered by ANY existing test across ALL files below. If it is already covered, DO NOT propose it. For every proposal, fill "coverage_check" naming the existing tests you checked and why a gap remains.

Write tests in the SAME style as the existing files: `import {{ test, expect }} from '@playwright/test';` and `test.describe('...', () => {{ test('...', async ({{ page }}) => {{ ... }}) }})`. Known facts: product slug `macbook-pro-14` exists; login credentials are test@example.com / password123; cart localStorage key is `fwebsite-cart`.

For "new_test": "proposed_code" MUST be a COMPLETE, self-contained `test.describe(...)` block (including the import line) that can be APPENDED to the end of the target file and run as-is. Leave "existing_code" as "".
For "modify_test": "existing_code" MUST be the EXACT verbatim block of the current failing test copied from the file below (so it can be string-matched), and "proposed_code" the full replacement `test(...)` block.

Return ONLY a JSON object: {{"proposals": [ ... ]}}. Max 4 proposals, highest value first. Each proposal object has keys:
- "kind": "new_test" | "modify_test"
- "trigger": "blind_spot" | "failing_test"
- "title": short human title
- "rationale": 1-2 plain-English sentences on the business value (for a non-technical QA lead)
- "coverage_check": which existing tests you checked; why this is not a duplicate (or for modify, why the change is safe and not hiding a bug)
- "target_file": one of {SPEC_FILES}
- "test_name": the exact test title string used inside proposed_code
- "existing_code": verbatim current block (modify_test only; else "")
- "proposed_code": the test code as described above

If there is nothing genuinely valuable and non-duplicate to add, return {{"proposals": []}}.

FAILING TESTS:
{failing_blob}

BLIND SPOTS:
{blind_blob}

EXISTING TEST SUITE (full source - use for dedup and exact-match anchors):
{specs_blob}
"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "\n".join(c.text for c in msg.content if getattr(c, "type", "") == "text").strip()
        cleaned = text
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned)
            cleaned = re.sub(r"\n```\s*$", "", cleaned)
        data = json.loads(cleaned)
        proposals = data.get("proposals", []) if isinstance(data, dict) else []
    except Exception as exc:
        print(f"  WARN  Proposal generation failed: {exc}")
        return []

    clean: list[dict[str, Any]] = []
    seen_names = {n.lower() for n in existing_names}
    for i, p in enumerate(proposals, 1):
        if not isinstance(p, dict):
            continue
        kind = p.get("kind")
        tname = (p.get("test_name") or "").strip()
        code = (p.get("proposed_code") or "").strip()
        if kind not in ("new_test", "modify_test") or not code or not tname:
            continue
        # Normalize target_file to the canonical repo path and drop proposals
        # that point at a spec file which does not actually exist.
        base = (p.get("target_file") or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
        if base not in SPEC_FILES:
            print(f"  skip proposal with unknown target_file '{p.get('target_file')}'")
            continue
        p["target_file"] = f"frontend/tests/{base}"
        if kind == "new_test" and tname.lower() in seen_names:
            print(f"  skip duplicate new test '{tname}' (already covered)")
            continue
        if kind == "modify_test" and not (p.get("existing_code") or "").strip():
            continue
        p["id"] = f"prop-{i}"
        if kind == "new_test":
            seen_names.add(tname.lower())
        clean.append(p)
    print(f"  generated {len(clean)} test proposal(s)")
    return clean


def _proposal_issue_url(p: dict[str, Any]) -> str:
    from urllib.parse import quote_plus
    payload = {
        "id": p.get("id"),
        "kind": p.get("kind"),
        "target_file": p.get("target_file"),
        "test_name": p.get("test_name"),
        "existing_code": p.get("existing_code", ""),
        "proposed_code": p.get("proposed_code", ""),
    }
    body = (
        f"**AI-proposed test {'modification' if p.get('kind') == 'modify_test' else '(new)'}**\n\n"
        f"**Rationale:** {p.get('rationale', '')}\n\n"
        f"**Coverage check:** {p.get('coverage_check', '')}\n\n"
        "Approving this issue (it already carries the `run-proposed-test` label) will apply the change "
        "and run the test once. Nothing is committed automatically.\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```\n"
    )
    title = f"[QA Proposal] {p.get('title', 'test improvement')}"
    return (
        "https://github.com/Stefgug/fwebsite/issues/new"
        f"?title={quote_plus(title)}"
        f"&labels={quote_plus('run-proposed-test')}"
        f"&body={quote_plus(body)}"
    )


def proposals_section_html(proposals: list[dict[str, Any]]) -> str:
    if not proposals:
        return ""
    cards = ""
    for p in proposals:
        kind = p.get("kind")
        if kind == "modify_test":
            badge = '<span style="background:#8b5cf6;color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600;">EDIT Modify existing test</span>'
            border = "#8b5cf6"
        else:
            badge = '<span style="background:#10b981;color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600;">NEW test</span>'
            border = "#10b981"
        url = _proposal_issue_url(p)
        existing = html.escape(p.get("existing_code", "") or "")
        proposed = html.escape(p.get("proposed_code", "") or "")
        if kind == "modify_test" and existing:
            diff_block = f"""
            <details style="margin-top:10px;">
              <summary style="cursor:pointer;color:#6b7280;font-size:13px;">View change</summary>
              <div style="font-size:12px;color:#991b1b;font-weight:600;margin-top:8px;">- Current</div>
              <pre style="background:#fef2f2;border-radius:6px;padding:12px;overflow-x:auto;font-size:12px;line-height:1.5;"><code>{existing}</code></pre>
              <div style="font-size:12px;color:#166534;font-weight:600;">+ Proposed</div>
              <pre style="background:#f0fdf4;border-radius:6px;padding:12px;overflow-x:auto;font-size:12px;line-height:1.5;"><code>{proposed}</code></pre>
            </details>"""
        else:
            diff_block = f"""
            <details style="margin-top:10px;">
              <summary style="cursor:pointer;color:#6b7280;font-size:13px;">View proposed test code</summary>
              <pre style="background:#f0fdf4;border-radius:6px;padding:12px;overflow-x:auto;font-size:12px;line-height:1.5;"><code>{proposed}</code></pre>
            </details>"""
        cards += f"""
        <div style="background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:18px;padding:18px 22px;border-left:5px solid {border};">
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px;">
                {badge}
                <h3 style="margin:0;font-size:17px;color:#1a1a2e;flex:1;">{html.escape(p.get('title', ''))}</h3>
                <code style="font-size:12px;color:#6b7280;">{html.escape(p.get('target_file', ''))}</code>
            </div>
            <p style="color:#4a5568;font-size:14px;margin:6px 0;line-height:1.55;">{html.escape(p.get('rationale', ''))}</p>
            <p style="color:#718096;font-size:13px;margin:6px 0;line-height:1.5;"><strong>Coverage check:</strong> {html.escape(p.get('coverage_check', ''))}</p>
            {diff_block}
            <div style="margin-top:14px;">
                <a href="{url}" target="_blank" style="display:inline-block;background:#1a1a2e;color:#fff;padding:9px 18px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px;">Accept &amp; run this test</a>
            </div>
        </div>"""

    return f"""
        <section style="margin-bottom:32px;">
            <h2 style="font-size:22px;color:#1a1a2e;margin-bottom:6px;">AI-Proposed Test Improvements</h2>
            <p style="color:#718096;font-size:14px;margin-bottom:18px;line-height:1.55;">
                Claude analysed the failures and coverage gaps, then proposed the high-value tests below - each checked against the existing suite to avoid duplication.
                Click <strong>Accept &amp; run</strong> to apply the change and validate it in a one-off run (no code is committed automatically).
            </p>
            {cards}
        </section>"""


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
    jira_bug_links = create_jira_bugs_for_failing_tests(triage, JIRA_EPIC_KEY)
    proposals = generate_test_proposals(triage, pw)
    summary_path, report_path, dash_path = write_reports(summary, triage, jira_bug_links, proposals)

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

