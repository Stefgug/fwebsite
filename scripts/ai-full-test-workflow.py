#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

try:
    import anthropic  # type: ignore
except Exception:
    anthropic = None

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "automation-reports"
FIX_NOTES_DIR = ROOT / "fix-notes"

PLAYWRIGHT_RESULTS_FILE = Path(
    os.environ.get("PLAYWRIGHT_RESULTS_FILE", str(ROOT / "frontend/test-results/results.json"))
)
COVERAGE_SUMMARY_FILE = Path(
    os.environ.get("COVERAGE_SUMMARY_FILE", str(ROOT / "frontend/coverage/coverage-summary.json"))
)

JIRA_EPIC_KEY = os.environ.get("JIRA_EPIC_KEY", "UNKNOWN-EPIC")
JIRA_EPIC_TITLE = os.environ.get("JIRA_EPIC_TITLE", "No epic title provided")
JIRA_EPIC_DESCRIPTION = os.environ.get("JIRA_EPIC_DESCRIPTION", "")

UNIT_OUTCOME = os.environ.get("UNIT_OUTCOME", "unknown")
E2E_OUTCOME = os.environ.get("E2E_OUTCOME", "unknown")

GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", os.environ.get("GITHUB_REPO", ""))
GITHUB_SHA = os.environ.get("GITHUB_SHA", "")
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
GH_TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


@dataclass
class PlaywrightFailure:
    file: str
    test: str
    error: str


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def fallback_triage(playwright: dict[str, Any], coverage: dict[str, Any]) -> str:
    fail_lines = [
        f"- `{f['file']}` / **{f['test']}**: {str(f['error']).splitlines()[0][:180]}"
        for f in playwright.get("failures", [])[:5]
    ]
    miss_lines = [
        f"- Add targeted unit tests for `{lf['file'].split('/frontend/')[-1]}` ({lf['lines_pct']:.2f}% lines)."
        for lf in coverage.get("low_files", [])[:8]
    ]

    return "\n".join(
        [
            "## AI triage (fallback mode)",
            "",
            "Anthropic API was unavailable; this triage is deterministic.",
            "",
            "### Root causes from failing tests",
            *(fail_lines or ["- No failing Playwright tests detected."]),
            "",
            "### Missing tests likely required",
            *(miss_lines or ["- No low-coverage files under 50% lines."]),
            "",
            "### Suggested correction strategy",
            "- Fix failing tests first (highest user impact).",
            "- Add unit tests for low-coverage modules next.",
            "- Keep Playwright for user journey validation and Vitest for logic branches.",
        ]
    )


def ai_triage(playwright: dict[str, Any], coverage: dict[str, Any]) -> str:
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
                    "You are a QA automation lead for an AI-driven testing PoC. "
                    "Return markdown with sections: Executive summary, Root causes, "
                    "Missing tests, Suggested code fixes, and Proposed PR checklist.\n\n"
                    f"INPUT JSON:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
                ),
            }
        ],
    )

    text_parts = [c.text for c in msg.content if getattr(c, "type", "") == "text"]
    text = "\n".join(text_parts).strip()
    return text or fallback_triage(playwright, coverage)


def status_badge(ok: bool, label: str) -> str:
    icon = "✅" if ok else "❌"
    klass = "ok" if ok else "ko"
    return f'<span class="badge {klass}">{icon} {html.escape(label)}</span>'


def render_bar(pct: float, color: str) -> str:
    p = max(0.0, min(100.0, float(pct)))
    return (
        '<div class="bar"><div class="fill" style="width:'
        f"{p:.2f}%; background:{color};\"></div></div><div class=\"pct\">{p:.2f}%</div>"
    )


def dashboard_html(summary: dict[str, Any], triage_md: str) -> str:
    cov = summary["coverage"]
    pw = summary["playwright"]

    fail_rows = "\n".join(
        [
            "<tr>"
            f"<td>{html.escape(f['file'])}</td>"
            f"<td>{html.escape(f['test'])}</td>"
            f"<td><code>{html.escape(str(f['error']).splitlines()[0][:180])}</code></td>"
            "</tr>"
            for f in pw.get("failures", [])[:20]
        ]
    )
    if not fail_rows:
        fail_rows = '<tr><td colspan="3">No failing tests 🎉</td></tr>'

    low_rows = "\n".join(
        [
            "<tr>"
            f"<td>{html.escape(lf['file'])}</td>"
            f"<td>{lf['lines_pct']:.2f}%</td>"
            f"<td>{lf['functions_pct']:.2f}%</td>"
            f"<td>{lf['branches_pct']:.2f}%</td>"
            "</tr>"
            for lf in cov.get("low_files", [])[:20]
        ]
    )
    if not low_rows:
        low_rows = '<tr><td colspan="4">No files under 50% lines coverage.</td></tr>'

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <title>AI Test Workflow Dashboard — {html.escape(JIRA_EPIC_KEY)}</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 24px; color: #0f172a; background: #f8fafc; }}
    h1, h2 {{ margin: 0 0 12px 0; }}
    .sub {{ color: #475569; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; margin-bottom: 16px; }}
    .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.03); }}
    .k {{ font-size: 12px; color:#64748b; }}
    .v {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
    .badge {{ display:inline-block; font-size: 12px; padding: 4px 8px; border-radius: 999px; margin-right:8px; }}
    .ok {{ background:#dcfce7; color:#166534; }} .ko {{ background:#fee2e2; color:#991b1b; }}
    .bar {{ width: 100%; height: 12px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: 6px; }}
    .fill {{ height: 100%; }} .pct {{ font-size: 12px; color:#334155; margin-top: 6px; }}
    table {{ width:100%; border-collapse: collapse; background:white; border:1px solid #e2e8f0; border-radius: 12px; overflow:hidden; }}
    th, td {{ text-align:left; border-bottom:1px solid #e2e8f0; padding: 10px; font-size: 13px; vertical-align: top; }}
    th {{ background:#f1f5f9; }}
    pre {{ white-space: pre-wrap; background:#0b1020; color:#e2e8f0; border-radius:10px; padding:12px; font-size:12px; }}
  </style>
</head>
<body>
  <h1>🧪 AI Test Workflow Dashboard</h1>
  <div class='sub'>Epic <b>{html.escape(JIRA_EPIC_KEY)}</b> — {html.escape(JIRA_EPIC_TITLE)}<br/>Run: {html.escape(GITHUB_RUN_ID or 'local')} · Commit: {html.escape((GITHUB_SHA or '')[:8])}</div>

  <p>
    {status_badge(UNIT_OUTCOME == 'success', f'Unit tests: {UNIT_OUTCOME}')}
    {status_badge(E2E_OUTCOME == 'success', f'E2E tests: {E2E_OUTCOME}')}
    {status_badge(summary['workflow_ok'], 'Workflow gate')}
  </p>

  <div class='grid'>
    <div class='card'><div class='k'>Playwright total</div><div class='v'>{pw['total']}</div></div>
    <div class='card'><div class='k'>Playwright passed</div><div class='v'>{pw['passed']}</div></div>
    <div class='card'><div class='k'>Playwright failed</div><div class='v'>{pw['failed']}</div></div>
  </div>

  <div class='card' style='margin-bottom:16px;'>
    <h2>Coverage snapshot</h2>
    <div class='k'>Lines</div>{render_bar(cov['lines_pct'], '#2563eb')}
    <div class='k'>Functions</div>{render_bar(cov['functions_pct'], '#7c3aed')}
    <div class='k'>Branches</div>{render_bar(cov['branches_pct'], '#16a34a')}
    <div class='k'>Statements</div>{render_bar(cov['statements_pct'], '#ea580c')}
  </div>

  <h2>Failing tests</h2>
  <table>
    <thead><tr><th>File</th><th>Test</th><th>Error (first line)</th></tr></thead>
    <tbody>{fail_rows}</tbody>
  </table>

  <h2 style='margin-top:18px;'>Low-coverage files (&lt;50% lines)</h2>
  <table>
    <thead><tr><th>File</th><th>Lines</th><th>Functions</th><th>Branches</th></tr></thead>
    <tbody>{low_rows}</tbody>
  </table>

  <h2 style='margin-top:18px;'>AI triage output</h2>
  <pre>{html.escape(triage_md)}</pre>
</body>
</html>
"""


def write_reports(summary: dict[str, Any], triage_md: str) -> tuple[Path, Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = REPORTS_DIR / "workflow-summary.json"
    report_path = REPORTS_DIR / "ai-triage-report.md"
    dash_path = REPORTS_DIR / "dashboard.html"

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
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
            triage_md.strip(),
            "",
        ]
    )
    report_path.write_text(report, encoding="utf-8")
    dash_path.write_text(dashboard_html(summary, triage_md), encoding="utf-8")
    return summary_path, report_path, dash_path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)


def maybe_create_pr(report_path: Path, summary: dict[str, Any]) -> str | None:
    if not GH_TOKEN or not GITHUB_REPO:
        return None

    needs_pr = summary["playwright"]["failed"] > 0 or float(summary["coverage"]["lines_pct"]) < 50.0
    if not needs_pr:
        return None

    FIX_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    sha8 = (GITHUB_SHA or "local")[:8]
    safe_epic = re.sub(r"[^a-zA-Z0-9-]+", "-", JIRA_EPIC_KEY).lower().strip("-")
    branch = f"poc/ai-test-triage-{safe_epic}-{sha8}"

    run(["git", "config", "user.email", "ci-bot@shopgeneric.dev"])
    run(["git", "config", "user.name", "ShopGeneric CI Bot"])
    if run(["git", "checkout", "-b", branch]).returncode != 0:
        return None

    note_path = FIX_NOTES_DIR / f"{safe_epic}-{sha8}-ai-test-triage.md"
    note_path.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")

    run(["git", "add", str(note_path)])
    if run(["git", "commit", "-m", f"test(auto): AI triage for {JIRA_EPIC_KEY} ({sha8})"]).returncode != 0:
        return None

    remote = f"https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPO}.git"
    if run(["git", "push", remote, branch]).returncode != 0:
        return None

    res = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/pulls",
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
        json={
            "title": f"🧪 AI test triage for {JIRA_EPIC_KEY}",
            "head": branch,
            "base": "main",
            "body": (
                f"Automated AI triage for epic **{JIRA_EPIC_KEY}**.\n\n"
                f"- Unit outcome: `{UNIT_OUTCOME}`\n"
                f"- E2E outcome: `{E2E_OUTCOME}`\n"
                f"- Coverage lines: `{summary['coverage']['lines_pct']:.2f}%`\n\n"
                f"See `{note_path.as_posix()}` for details."
            ),
        },
        timeout=20,
    )
    if not res.ok:
        return None
    return res.json().get("html_url")


def main() -> None:
    pw = parse_playwright_results(load_json(PLAYWRIGHT_RESULTS_FILE))
    cov = parse_coverage_summary(load_json(COVERAGE_SUMMARY_FILE))

    workflow_ok = UNIT_OUTCOME == "success" and E2E_OUTCOME == "success" and cov["lines_pct"] >= 50.0
    summary = {
        "epic": {"key": JIRA_EPIC_KEY, "title": JIRA_EPIC_TITLE, "description": JIRA_EPIC_DESCRIPTION},
        "git": {"repo": GITHUB_REPO, "sha": GITHUB_SHA, "run_id": GITHUB_RUN_ID},
        "unit_outcome": UNIT_OUTCOME,
        "e2e_outcome": E2E_OUTCOME,
        "playwright": pw,
        "coverage": cov,
        "workflow_ok": workflow_ok,
    }

    triage = ai_triage(pw, cov)
    summary_path, report_path, dash_path = write_reports(summary, triage)

    pr_url = maybe_create_pr(report_path, summary)
    if pr_url:
        summary["auto_pr_url"] = pr_url
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    gh_step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_step_summary:
        with open(gh_step_summary, "a", encoding="utf-8") as f:
            f.write("## 🧪 AI Test Workflow Summary\n")
            f.write(f"- Epic: **{JIRA_EPIC_KEY}** — {JIRA_EPIC_TITLE}\n")
            f.write(f"- Unit tests: `{UNIT_OUTCOME}`\n")
            f.write(f"- E2E tests: `{E2E_OUTCOME}`\n")
            f.write(f"- Coverage lines: `{cov['lines_pct']:.2f}%`\n")
            f.write(f"- Workflow gate: **{'PASS ✅' if workflow_ok else 'FAIL ❌'}**\n")
            if pr_url:
                f.write(f"- Auto PR: {pr_url}\n")
            f.write("\nArtifacts:\n")
            f.write("- `automation-reports/dashboard.html`\n")
            f.write("- `automation-reports/ai-triage-report.md`\n")
            f.write("- `automation-reports/workflow-summary.json`\n")

    print(f"summary={summary_path}")
    print(f"report={report_path}")
    print(f"dashboard={dash_path}")
    if pr_url:
        print(f"auto_pr={pr_url}")


if __name__ == "__main__":
    main()
