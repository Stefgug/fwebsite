#!/usr/bin/env python3
"""Anticipatory regression-test analysis.

Runs the MOMENT the app changes (a push touching frontend/** or backend/**),
BEFORE any test is executed. It reads the code diff, understands what changed,
and asks Claude which existing regression tests are now likely outdated and
which new tests should be added — without running anything (some E2E runs are
slow). The output is a report on GitHub Pages whose proposal cards can, in one
click, either run the test on a branch or create a Jira ticket under the Epic.

Env:
  ANTHROPIC_API_KEY   - for the analysis (falls back to a deterministic stub)
  BASE_SHA / HEAD_SHA - commit range to diff (optional; git fallbacks apply)
  GITHUB_REF_NAME     - branch name (used to resolve the Epic + shown in report)
  GITHUB_SHA          - head commit
  GITHUB_RUN_ID       - run id
  JIRA_EPIC_KEY       - explicit Epic key (optional; otherwise resolved)
  JIRA_BASE_URL       - Jira base url
  PAGES_URL           - live GitHub Pages URL, to read current-epic.json (optional)
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import requests

import report_common as rc

try:
    import anthropic  # type: ignore
except Exception:
    anthropic = None

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "automation-reports"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BASE_SHA = os.environ.get("BASE_SHA", "")
HEAD_SHA = os.environ.get("HEAD_SHA", "") or os.environ.get("GITHUB_SHA", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "") or os.environ.get("GIT_BRANCH", "")
GITHUB_SHA = os.environ.get("GITHUB_SHA", "")
GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")
PAGES_URL = os.environ.get("PAGES_URL", "https://stefgug.github.io/fwebsite/")

SPEC_FILES = [
    "home.spec.ts", "navigation.spec.ts", "products.spec.ts",
    "cart.spec.ts", "auth.spec.ts", "about.spec.ts",
]
MAX_DIFF_CHARS = 16000


# --------- Git helpers ---------

def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True, timeout=60
        ).stdout
    except Exception as exc:
        print(f"  git {' '.join(args)} failed: {exc}")
        return ""


def _is_real_sha(s: str) -> bool:
    return bool(s) and set(s) != {"0"} and s != ""


def resolve_range() -> tuple[str, str]:
    """Return (base, head) commits to diff."""
    head = HEAD_SHA or "HEAD"
    base = BASE_SHA if _is_real_sha(BASE_SHA) else ""
    if not base:
        # New branch / forced push: diff against main's merge-base, else previous commit.
        mb = _git(["merge-base", "origin/main", head]).strip()
        base = mb or (_git(["rev-parse", f"{head}~1"]).strip() or head)
    return base, head


def collect_changes(base: str, head: str) -> tuple[list[dict[str, str]], str]:
    """Return (changed_files [{status,path}], unified diff text) for app code."""
    pathspec = ["--", "frontend", "backend",
                ":(exclude)frontend/node_modules", ":(exclude)backend/node_modules"]
    name_status = _git(["diff", "--name-status", f"{base}..{head}", *pathspec])
    files: list[dict[str, str]] = []
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append({"status": parts[0].strip(), "path": parts[-1].strip()})
    diff = _git(["diff", "--unified=3", f"{base}..{head}", *pathspec])
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n... [diff truncated] ..."
    return files, diff


# --------- Epic resolution ---------

def resolve_epic() -> tuple[str, str]:
    # 1) explicit env
    key = os.environ.get("JIRA_EPIC_KEY", "")
    if key and key != "UNKNOWN-EPIC":
        return key, os.environ.get("JIRA_EPIC_TITLE", "")
    # 2) branch name (e.g. feat/SCRUM-12-foo)
    m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", BRANCH or "")
    if m:
        return m.group(1), ""
    # 3) the last published current-epic.json
    try:
        r = requests.get(f"{PAGES_URL.rstrip('/')}/current-epic.json", timeout=10)
        if r.ok:
            data = r.json()
            if data.get("epic_key"):
                return data["epic_key"], data.get("epic_title", "")
    except Exception:
        pass
    return "UNKNOWN-EPIC", ""


# --------- Spec sources ---------

def read_specs() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in SPEC_FILES:
        p = ROOT / "frontend" / "tests" / name
        try:
            out[name] = p.read_text(encoding="utf-8")
        except Exception:
            out[name] = ""
    return out


def all_existing_test_names(specs: dict[str, str]) -> set[str]:
    names: set[str] = set()
    for src in specs.values():
        for m in re.findall(r"test\(['\"](.+?)['\"]", src):
            names.add(m.strip().lower())
    return names


# --------- AI analysis ---------

def analyze(files: list[dict[str, str]], diff: str, specs: dict[str, str]) -> dict[str, Any]:
    if not ANTHROPIC_API_KEY or anthropic is None or not diff.strip():
        return fallback_analysis(files)

    specs_blob = "\n\n".join(f"=== frontend/tests/{n} ===\n{s}" for n, s in specs.items() if s)
    files_blob = "\n".join(f"{f['status']}\t{f['path']}" for f in files) or "(no files)"

    prompt = f"""You are a senior QA automation engineer. The application code just changed on branch '{BRANCH}'. \
BEFORE the (sometimes slow) regression suite runs, anticipate how the existing Playwright E2E tests should evolve.

This is an e-commerce app (Next.js frontend on http://localhost:3000, Strapi backend, mock data in CI). \
Known facts: product slug `macbook-pro-14` exists; login is test@example.com / password123; cart localStorage key is `fwebsite-cart`.

Analyse the diff and produce a JSON object with EXACTLY these keys:

- "summary": 2-3 plain-English sentences for a non-technical QA lead: what changed in the product and what it means for regression testing.
- "change_impacts": array (one per meaningful changed area) of objects:
    - "file": the changed file path
    - "change": one plain-English sentence describing the functional change (no code/jargon)
    - "risk": "low" | "medium" | "high" (regression risk if untested)
    - "tested": true if an existing E2E test already covers this behaviour, else false
- "proposals": array (max 4, highest value first) of test improvements:
    - "kind": "new_test" (cover a NEW/changed behaviour not yet tested) | "modify_test" (an existing test is now OUTDATED because the app legitimately changed)
    - "trigger": "code_change"
    - "title": short human title
    - "rationale": 1-2 plain-English sentences on the business value
    - "coverage_check": which existing tests you checked; why this is not a duplicate (or for modify, why the change is safe)
    - "target_file": one of {SPEC_FILES}
    - "test_name": exact test title used inside proposed_code
    - "existing_code": for modify_test, the EXACT verbatim current test block copied from the sources below; else ""
    - "proposed_code": for new_test, a COMPLETE self-contained `test.describe(...)` block (with the import line) appendable to the file; for modify_test, the full replacement `test(...)` block. Match the existing style: `import {{ test, expect }} from '@playwright/test';`.

CRITICAL: Only propose modify_test when the app legitimately changed and the test is now outdated — never to paper over a real bug. Never duplicate behaviour already covered. If nothing valuable is warranted, return "proposals": [].

Return ONLY the JSON object, no markdown fences.

CHANGED FILES:
{files_blob}

DIFF (app code only):
```diff
{diff}
```

EXISTING TEST SUITE (for dedup and exact-match anchors):
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
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n", "", text)
            text = re.sub(r"\n```\s*$", "", text)
        data = json.loads(text)
        if isinstance(data, dict) and "summary" in data:
            return data
    except Exception as exc:
        print(f"  WARN  analysis failed: {exc}")
    return fallback_analysis(files)


def fallback_analysis(files: list[dict[str, str]]) -> dict[str, Any]:
    impacts = [
        {"file": f["path"], "change": f"File {f['status']} — review whether behaviour changed.",
         "risk": "medium", "tested": False}
        for f in files[:8]
    ]
    return {
        "summary": (
            f"{len(files)} application file(s) changed on branch '{BRANCH}'. "
            "AI analysis was unavailable, so review the changed files manually to decide which "
            "regression tests need updating."
        ),
        "change_impacts": impacts,
        "proposals": [],
    }


# --------- Proposal cleanup (mirror of the post-run pipeline) ---------

def clean_proposals(raw: list[dict[str, Any]], specs: dict[str, str], epic_key: str) -> list[dict[str, Any]]:
    seen = all_existing_test_names(specs)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(raw or [], 1):
        if not isinstance(p, dict):
            continue
        kind = p.get("kind")
        tname = (p.get("test_name") or "").strip()
        code = (p.get("proposed_code") or "").strip()
        if kind not in ("new_test", "modify_test") or not code or not tname:
            continue
        base = (p.get("target_file") or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
        if base not in SPEC_FILES:
            print(f"  skip proposal with unknown target_file '{p.get('target_file')}'")
            continue
        p["target_file"] = f"frontend/tests/{base}"
        if kind == "new_test" and tname.lower() in seen:
            print(f"  skip duplicate new test '{tname}'")
            continue
        if kind == "modify_test" and not (p.get("existing_code") or "").strip():
            continue
        p["id"] = f"chg-{i}"
        p["jira_epic_key"] = epic_key
        p["source"] = "code-change"
        if kind == "new_test":
            seen.add(tname.lower())
        out.append(p)
    print(f"  {len(out)} proposal(s) after cleanup")
    return out


# --------- Report HTML ---------

def _risk_pill(risk: str) -> str:
    r = (risk or "").lower()
    if r == "high":
        return '<span style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;padding:2px 9px;border-radius:5px;font-size:12px;font-weight:600;">High risk</span>'
    if r == "medium":
        return '<span style="background:#fffbeb;color:#a16207;border:1px solid #fde68a;padding:2px 9px;border-radius:5px;font-size:12px;font-weight:600;">Medium risk</span>'
    return '<span style="background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;padding:2px 9px;border-radius:5px;font-size:12px;font-weight:600;">Low risk</span>'


def _tested_pill(tested: bool) -> str:
    if tested:
        return '<span style="color:#15803d;font-size:12px;font-weight:600;">✓ Covered</span>'
    return '<span style="color:#b91c1c;font-size:12px;font-weight:600;">✕ Not covered</span>'


def build_report_html(analysis: dict[str, Any], proposals: list[dict[str, Any]],
                      files: list[dict[str, str]], epic_key: str, epic_title: str,
                      generated_at: str) -> str:
    impacts = analysis.get("change_impacts", []) or []
    impact_rows = "".join(
        f"""<tr>
            <td style="padding:11px 14px;font-size:13px;white-space:nowrap;"><code style="font-size:12px;color:#374151;">{html.escape(imp.get('file',''))}</code></td>
            <td style="padding:11px 14px;font-size:13px;color:#374151;">{html.escape(imp.get('change',''))}</td>
            <td style="padding:11px 14px;white-space:nowrap;">{_risk_pill(imp.get('risk',''))}</td>
            <td style="padding:11px 14px;white-space:nowrap;">{_tested_pill(bool(imp.get('tested')))}</td>
        </tr>"""
        for imp in impacts
    )
    if impact_rows:
        impacts_section = f"""
        <div class="section-title">Code changes detected</div>
        <div class="card" style="padding:0;overflow:hidden;">
          <table style="width:100%;border-collapse:collapse;">
            <thead><tr style="background:#f9fafb;">
              <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">File</th>
              <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">Functional change</th>
              <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">Risk</th>
              <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">Coverage</th>
            </tr></thead>
            <tbody>{impact_rows}</tbody>
          </table>
        </div>"""
    else:
        names = "".join(f"<li><code>{html.escape(f['path'])}</code> <span style='color:#9ca3af;'>({html.escape(f['status'])})</span></li>" for f in files)
        impacts_section = f"""
        <div class="section-title">Code changes detected</div>
        <div class="card"><ul style="margin:0;padding-left:18px;line-height:1.7;font-size:13px;color:#374151;">{names or '<li>No application files changed.</li>'}</ul></div>"""

    if proposals:
        proposals_section = (
            '<div class="section-title">Proposed regression-test updates</div>'
            + rc.proposals_section_html(
                proposals,
                intro=("Anticipated from the code changes above — before the suite runs. "
                       "Use <strong>Run on a branch</strong> to validate a proposal now, or "
                       "<strong>Create Jira ticket</strong> to track it in the Epic if it's relevant."),
            )
        )
    else:
        proposals_section = """
        <div class="section-title">Proposed regression-test updates</div>
        <div class="card" style="border-color:#bbf7d0;background:#f0fdf4;">
          <strong style="color:#15803d;">No test changes needed.</strong>
          <span style="color:#374151;"> The existing regression suite already covers these changes adequately.</span>
        </div>"""

    commit_short = (GITHUB_SHA or "")[:8]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code Change Analysis — {html.escape(epic_key)}</title>
<style>{rc.BASE_CSS}
  .summary-banner {{
    background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px;
    padding:16px 20px; display:flex; gap:14px; align-items:flex-start; margin-bottom:8px;
  }}
  .summary-banner .icon {{
    width:28px;height:28px;flex-shrink:0;border-radius:50%;background:#2563eb;color:#fff;
    font-weight:700;display:flex;align-items:center;justify-content:center;
  }}
  .summary-banner p {{ font-size:14px;color:#374151;line-height:1.65; }}
</style>
</head>
<body>
  <header class="header">
    <div class="header-left">
      <div class="breadcrumb"><a href="index.html">← Hub</a> &nbsp;·&nbsp; <a href="catalog.html">Test Catalog</a></div>
      <h1>Code Change Analysis</h1>
      <div class="meta">
        Branch <code>{html.escape(BRANCH or '?')}</code> · Commit <code>{html.escape(commit_short)}</code>
        · Epic: <a href="{html.escape(JIRA_BASE_URL)}/browse/{html.escape(epic_key)}" target="_blank">{html.escape(epic_key)}</a>
        · {html.escape(generated_at)}
      </div>
    </div>
  </header>

  <main class="container">
    <div class="summary-banner">
      <div class="icon">🔮</div>
      <p>{html.escape(analysis.get('summary', 'No summary available.'))}</p>
    </div>

    {impacts_section}

    {proposals_section}
  </main>

  <footer class="footer">Anticipatory analysis · runs before the suite · {html.escape(rc.GITHUB_REPO)}</footer>
</body>
</html>"""


# --------- Main ---------

def main() -> None:
    base, head = resolve_range()
    print(f"Diff range: {base}..{head}")
    files, diff = collect_changes(base, head)
    print(f"Changed app files: {len(files)}")

    epic_key, epic_title = resolve_epic()
    print(f"Epic: {epic_key}")

    specs = read_specs()
    analysis = analyze(files, diff, specs)
    proposals = clean_proposals(analysis.get("proposals", []), specs, epic_key)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at, generated_ts = rc.now_utc()

    report_html = build_report_html(analysis, proposals, files, epic_key, epic_title, generated_at)
    (REPORTS_DIR / "code-analysis.html").write_text(report_html, encoding="utf-8")

    # The hub (kept identical across workflows) so both reports always coexist.
    (REPORTS_DIR / "index.html").write_text(rc.build_hub_html(), encoding="utf-8")

    rc.write_meta(REPORTS_DIR, "code-analysis.meta.json", {
        "type": "code-analysis",
        "title": "Code Change Analysis",
        "href": "code-analysis.html",
        "generated_at": generated_at,
        "generated_ts": generated_ts,
        "epic_key": epic_key,
        "branch": BRANCH,
        "commit": (GITHUB_SHA or "")[:8],
        "n_changes": len(files),
        "n_proposals": len(proposals),
    })

    # Persist machine-readable analysis for debugging / re-use.
    (REPORTS_DIR / "code-analysis.json").write_text(
        json.dumps({"branch": BRANCH, "commit": GITHUB_SHA, "epic_key": epic_key,
                    "files": files, "analysis": analysis, "proposals": proposals},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    gh_step = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_step:
        with open(gh_step, "a", encoding="utf-8") as f:
            f.write("## 🔮 Code Change Analysis\n")
            f.write(f"- Branch: `{BRANCH}` · Commit: `{(GITHUB_SHA or '')[:8]}`\n")
            f.write(f"- Epic: **{epic_key}**\n")
            f.write(f"- Changed app files: **{len(files)}**\n")
            f.write(f"- Proposed test updates: **{len(proposals)}**\n")

    print(f"code-analysis.html written ({len(report_html):,} bytes)")


if __name__ == "__main__":
    main()
