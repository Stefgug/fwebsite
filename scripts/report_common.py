#!/usr/bin/env python3
"""Shared helpers for the QA report pages published to GitHub Pages.

Used by both:
  - scripts/ai-full-test-workflow.py  (post-run test report + catalog)
  - scripts/analyze-code-changes.py   (anticipatory code-change analysis)

Provides a consistent visual language (BASE_CSS), the unified "proposal card"
renderer with its two action buttons (run-on-a-branch + create-Jira-ticket),
and the GitHub Pages hub (index.html) that links to every report.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

# --------- Constants ---------
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "Stefgug/fwebsite")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")

LABEL_RUN = "run-proposed-test"
LABEL_JIRA = "create-jira-ticket"


def now_utc() -> tuple[str, int]:
    """Return (human timestamp, unix seconds)."""
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC"), int(dt.timestamp())


# --------- Shared design language ---------
# A single, modern, professional palette shared by every generated page.
BASE_CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
      background: #f8fafc; color: #111827; font-size: 14px; line-height: 1.5;
    }
    a { color: #2563eb; }
    .header {
      background: #111827; padding: 20px 32px; display: flex;
      align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;
    }
    .header-left .breadcrumb { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
    .header-left .breadcrumb a { color: #9ca3af; text-decoration: none; }
    .header-left .breadcrumb a:hover { color: #d1d5db; }
    .header-left h1 { font-size: 20px; font-weight: 700; color: #f9fafb; }
    .header-left .meta { font-size: 12px; color: #6b7280; margin-top: 3px; }
    .header-left .meta a { color: #93c5fd; text-decoration: none; }
    .container { max-width: 1000px; margin: 0 auto; padding: 28px 20px 48px; }
    .section-title {
      font-size: 16px; font-weight: 700; color: #111827;
      margin: 32px 0 16px; padding-bottom: 12px; border-bottom: 1px solid #e5e7eb;
    }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px 22px; }
    .footer {
      text-align: center; padding: 24px; color: #9ca3af; font-size: 12px;
      border-top: 1px solid #e5e7eb; margin-top: 8px;
    }
"""


# --------- Proposal action URLs (GitHub issue prefills) ---------

def proposal_issue_url(p: dict[str, Any], action: str) -> str:
    """Build a prefilled GitHub "new issue" URL for one of the two actions.

    action == "run"  -> label run-proposed-test  (validate the test on a throwaway run)
    action == "jira" -> label create-jira-ticket (create a Jira ticket under the Epic)
    """
    payload = {
        "id": p.get("id"),
        "kind": p.get("kind"),
        "target_file": p.get("target_file"),
        "test_name": p.get("test_name"),
        "title": p.get("title", ""),
        "rationale": p.get("rationale", ""),
        "coverage_check": p.get("coverage_check", ""),
        "existing_code": p.get("existing_code", ""),
        "proposed_code": p.get("proposed_code", ""),
        "jira_epic_key": p.get("jira_epic_key", ""),
        "source": p.get("source", ""),
    }
    json_block = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```\n"

    if action == "jira":
        label = LABEL_JIRA
        title = f"[QA] Create Jira ticket: {p.get('title', 'proposed test')}"
        body = (
            f"**Create a Jira ticket in Epic `{p.get('jira_epic_key', '')}` for this proposed test.**\n\n"
            f"**Rationale:** {p.get('rationale', '')}\n\n"
            f"**Coverage check:** {p.get('coverage_check', '')}\n\n"
            "Opening this issue (it already carries the `create-jira-ticket` label) will create a "
            "Jira ticket under the Epic describing this work. No code is committed.\n\n"
            f"{json_block}"
        )
    else:  # run
        label = LABEL_RUN
        title = f"[QA] Run proposed test: {p.get('title', 'proposed test')}"
        body = (
            f"**AI-proposed test {'modification' if p.get('kind') == 'modify_test' else '(new)'}**\n\n"
            f"**Rationale:** {p.get('rationale', '')}\n\n"
            f"**Coverage check:** {p.get('coverage_check', '')}\n\n"
            "Opening this issue (it already carries the `run-proposed-test` label) will apply the change "
            "and run the test once on a throwaway checkout. Nothing is committed automatically.\n\n"
            f"{json_block}"
        )
    return (
        f"https://github.com/{GITHUB_REPO}/issues/new"
        f"?title={quote_plus(title)}"
        f"&labels={quote_plus(label)}"
        f"&body={quote_plus(body)}"
    )


# --------- Unified proposal card + section ---------

def proposal_card_html(p: dict[str, Any]) -> str:
    kind = p.get("kind")
    if kind == "modify_test":
        badge = ('<span style="background:#ede9fe;color:#6d28d9;border:1px solid #c4b5fd;'
                 'padding:3px 10px;border-radius:5px;font-size:12px;font-weight:600;">Modify existing test</span>')
    else:
        badge = ('<span style="background:#d1fae5;color:#065f46;border:1px solid #6ee7b7;'
                 'padding:3px 10px;border-radius:5px;font-size:12px;font-weight:600;">New test</span>')

    existing = html.escape(p.get("existing_code", "") or "")
    proposed = html.escape(p.get("proposed_code", "") or "")
    if kind == "modify_test" and existing:
        diff_block = f"""
        <details style="margin-top:12px;">
          <summary style="cursor:pointer;color:#6b7280;font-size:13px;font-weight:500;user-select:none;">View change ↕</summary>
          <div style="margin-top:10px;">
            <div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Current</div>
            <pre style="background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:12px;overflow-x:auto;font-size:12px;line-height:1.55;"><code>{existing}</code></pre>
            <div style="font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin:8px 0 4px;">Proposed</div>
            <pre style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:12px;overflow-x:auto;font-size:12px;line-height:1.55;"><code>{proposed}</code></pre>
          </div>
        </details>"""
    else:
        diff_block = f"""
        <details style="margin-top:12px;">
          <summary style="cursor:pointer;color:#6b7280;font-size:13px;font-weight:500;user-select:none;">View proposed test code ↕</summary>
          <pre style="margin-top:10px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:6px;padding:12px;overflow-x:auto;font-size:12px;line-height:1.55;"><code>{proposed}</code></pre>
        </details>"""

    run_url = proposal_issue_url(p, "run")
    jira_url = proposal_issue_url(p, "jira")
    epic_key = html.escape(p.get("jira_epic_key", "") or "")
    jira_label = f"Create Jira ticket in {epic_key}" if epic_key else "Create Jira ticket"

    return f"""
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:14px;padding:18px 22px;">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px;">
            {badge}
            <h3 style="margin:0;font-size:15px;font-weight:700;color:#111827;flex:1;">{html.escape(p.get('title', ''))}</h3>
            <code style="font-size:12px;color:#9ca3af;background:#f3f4f6;padding:2px 7px;border-radius:4px;">{html.escape(p.get('target_file', ''))}</code>
        </div>
        <p style="color:#374151;font-size:13px;line-height:1.6;margin-bottom:6px;">{html.escape(p.get('rationale', ''))}</p>
        <p style="color:#9ca3af;font-size:12px;line-height:1.5;">
            <strong style="color:#6b7280;">Coverage check:</strong> {html.escape(p.get('coverage_check', ''))}
        </p>
        {diff_block}
        <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;">
            <a href="{run_url}" target="_blank"
               style="display:inline-flex;align-items:center;gap:6px;background:#111827;color:#f9fafb;
                      padding:8px 16px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px;">
                ▶ Run on a branch
            </a>
            <a href="{jira_url}" target="_blank"
               style="display:inline-flex;align-items:center;gap:6px;background:#fff;color:#1d4ed8;
                      border:1px solid #bfdbfe;padding:8px 16px;border-radius:6px;text-decoration:none;
                      font-weight:600;font-size:13px;">
                🎫 {jira_label}
            </a>
        </div>
    </div>"""


def proposals_section_html(proposals: list[dict[str, Any]], intro: str | None = None) -> str:
    """Render the list of proposal cards (no section title — caller adds it)."""
    if not proposals:
        return ""
    intro_html = ""
    if intro:
        intro_html = (
            f'<div style="color:#6b7280;font-size:13px;margin-bottom:16px;line-height:1.55;">{intro}</div>'
        )
    cards = "".join(proposal_card_html(p) for p in proposals)
    return intro_html + cards


# --------- Meta files + hub ---------

def write_meta(reports_dir: Path, name: str, data: dict[str, Any]) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_hub_html() -> str:
    """A static landing page that links to every report. It reads the per-report
    *.meta.json files client-side so it never goes stale and both report types
    coexist regardless of which workflow ran last."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QA Automation Hub — {html.escape(GITHUB_REPO)}</title>
<style>{BASE_CSS}
  .hub-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; margin-top:8px; }}
  .hub-card {{
    background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:24px;
    text-decoration:none; color:inherit; display:block; transition:border-color .15s, box-shadow .15s;
  }}
  .hub-card:hover {{ border-color:#93c5fd; box-shadow:0 4px 16px rgba(0,0,0,.06); }}
  .hub-card.disabled {{ opacity:.55; pointer-events:none; }}
  .hub-icon {{ font-size:26px; }}
  .hub-card h2 {{ font-size:17px; font-weight:700; margin:12px 0 4px; color:#111827; }}
  .hub-card p {{ font-size:13px; color:#6b7280; line-height:1.55; }}
  .hub-meta {{ margin-top:14px; font-size:12px; color:#9ca3af; }}
  .latest-badge {{
    display:inline-block; background:#dcfce7; color:#166534; border:1px solid #86efac;
    font-size:11px; font-weight:700; padding:2px 8px; border-radius:99px; margin-left:8px;
  }}
  .pill {{ display:inline-block; font-size:12px; font-weight:600; padding:2px 9px; border-radius:5px; }}
  .pill-pass {{ background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; }}
  .pill-fail {{ background:#fef2f2; color:#b91c1c; border:1px solid #fecaca; }}
  .catalog-link {{
    display:inline-flex; align-items:center; gap:8px; margin-top:28px;
    background:#2563eb; color:#fff; padding:11px 22px; border-radius:8px;
    text-decoration:none; font-weight:600; font-size:14px;
  }}
  .catalog-link:hover {{ background:#1d4ed8; }}
  .intro {{ font-size:14px; color:#374151; line-height:1.65; margin-bottom:24px; max-width:680px; }}
</style>
</head>
<body>
  <header class="header">
    <div class="header-left">
      <h1>QA Automation Hub</h1>
      <div class="meta">{html.escape(GITHUB_REPO)} · AI-assisted regression testing</div>
    </div>
  </header>

  <main class="container">
    <p class="intro">
      Two complementary views of test health. <strong>Code Change Analysis</strong> runs the moment
      the app changes — before any test is executed — and proposes which regression tests to update or add.
      The <strong>Post-Run Test Report</strong> shows the outcome once the suite has actually run.
      The most recently generated one is marked <span class="latest-badge" style="margin:0;">Latest</span>.
    </p>

    <div class="hub-grid">
      <a id="card-code" class="hub-card disabled" href="code-analysis.html">
        <div class="hub-icon">🔮</div>
        <h2>Code Change Analysis <span id="latest-code"></span></h2>
        <p>Anticipates regression-test gaps from the latest code changes, before running the suite.</p>
        <div class="hub-meta" id="meta-code">Not generated yet.</div>
      </a>

      <a id="card-test" class="hub-card disabled" href="test-report.html">
        <div class="hub-icon">📊</div>
        <h2>Post-Run Test Report <span id="latest-test"></span></h2>
        <p>Unit + E2E results, functional impact of failures, visual evidence and coverage gaps.</p>
        <div class="hub-meta" id="meta-test">Not generated yet.</div>
      </a>
    </div>

    <a class="catalog-link" href="catalog.html">📋 Open the Test Catalog →</a>
  </main>

  <footer class="footer">Generated by AI Test Pipeline · {html.escape(GITHUB_REPO)}</footer>

  <script>
    async function loadMeta(file) {{
      try {{
        const r = await fetch(file, {{ cache: 'no-store' }});
        if (!r.ok) return null;
        return await r.json();
      }} catch (e) {{ return null; }}
    }}
    function esc(s) {{ return (s == null ? '' : String(s)).replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c])); }}

    (async () => {{
      const [code, test] = await Promise.all([
        loadMeta('code-analysis.meta.json'),
        loadMeta('test-report.meta.json'),
      ]);

      if (code) {{
        document.getElementById('card-code').classList.remove('disabled');
        const parts = [];
        if (code.branch) parts.push('Branch <code>' + esc(code.branch) + '</code>');
        if (code.commit) parts.push('Commit <code>' + esc(code.commit) + '</code>');
        parts.push(esc(code.n_changes || 0) + ' file(s) changed');
        parts.push('<strong>' + esc(code.n_proposals || 0) + ' test proposal(s)</strong>');
        parts.push(esc(code.generated_at || ''));
        document.getElementById('meta-code').innerHTML = parts.join(' · ');
      }}

      if (test) {{
        document.getElementById('card-test').classList.remove('disabled');
        const gate = (test.gate === 'pass')
          ? '<span class="pill pill-pass">Gate: PASS</span>'
          : '<span class="pill pill-fail">Gate: FAIL</span>';
        const parts = [gate];
        if (test.e2e) parts.push('E2E ' + esc(test.e2e));
        if (test.coverage != null) parts.push(esc(test.coverage) + '% coverage');
        if (test.epic_key) parts.push('Epic ' + esc(test.epic_key));
        parts.push(esc(test.generated_at || ''));
        document.getElementById('meta-test').innerHTML = parts.join(' · ');
      }}

      // "Latest" badge on whichever was generated most recently
      const ct = code && code.generated_ts ? code.generated_ts : 0;
      const tt = test && test.generated_ts ? test.generated_ts : 0;
      if (ct || tt) {{
        const badge = '<span class="latest-badge">Latest</span>';
        if (ct >= tt && code) document.getElementById('latest-code').innerHTML = badge;
        else if (test) document.getElementById('latest-test').innerHTML = badge;
      }}
    }})();
  </script>
</body>
</html>"""
