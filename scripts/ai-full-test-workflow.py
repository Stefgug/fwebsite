#!/usr/bin/env python3
from __future__ import annotations

import base64
import html
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import report_common as rc

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
    screenshot: str = ""


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
                        shot = ""
                        for att in (result.get("attachments") or []):
                            if (att.get("contentType") or "").startswith("image/") and att.get("path"):
                                shot = att["path"]
                                break
                        failures.append(
                            PlaywrightFailure(
                                file=suite_file or "unknown-file",
                                test=title,
                                error=str(err_msg)[:1200],
                                screenshot=shot,
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
    """Render a progress bar for a coverage percentage."""
    p = max(0.0, min(100.0, float(pct)))
    if p >= 80:
        track_color = "#bbf7d0"
        fill_color  = "#16a34a"
        label_color = "#15803d"
    elif p >= 50:
        track_color = "#fef9c3"
        fill_color  = "#ca8a04"
        label_color = "#a16207"
    else:
        track_color = "#fee2e2"
        fill_color  = "#dc2626"
        label_color = "#b91c1c"
    return (
        f'<div style="width:100%;height:6px;background:{track_color};border-radius:99px;overflow:hidden;margin-top:10px;">'
        f'<div style="width:{p:.1f}%;height:100%;background:{fill_color};border-radius:99px;transition:width .4s;"></div>'
        f'</div>'
        f'<div style="font-size:12px;color:{label_color};font-weight:600;margin-top:5px;">{p:.1f}% line coverage</div>'
    )


# --------- Visual evidence (screenshots + red-box annotation) ---------

def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", s)[:60] or "shot"


def _annotate_bbox(src: Path, dst: Path, bbox: dict | None, label: str) -> bool:
    """Draw a red box (and small label) on a copy of the screenshot. Falls back to a plain copy."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        try:
            shutil.copyfile(src, dst)
            return True
        except Exception:
            return False
    try:
        img = Image.open(src).convert("RGB")
        if bbox:
            W, H = img.size
            x = max(0, int(float(bbox.get("x", 0)) * W))
            y = max(0, int(float(bbox.get("y", 0)) * H))
            w = int(float(bbox.get("width", 0)) * W)
            h = int(float(bbox.get("height", 0)) * H)
            if w > 2 and h > 2:
                draw = ImageDraw.Draw(img)
                for off in range(5):
                    draw.rectangle([x - off, y - off, x + w + off, y + h + off], outline=(231, 76, 60))
                if label:
                    ty = max(0, y - 20)
                    draw.rectangle([x, ty, x + 8 + len(label) * 7, ty + 18], fill=(231, 76, 60))
                    draw.text((x + 4, ty + 4), label, fill=(255, 255, 255))
        img.save(dst)
        return True
    except Exception:
        try:
            shutil.copyfile(src, dst)
            return True
        except Exception:
            return False


def _vision_bbox(src: Path, test_name: str, impact: str) -> tuple[dict | None, str]:
    """Ask Claude vision for the bounding box of the problem area. Best-effort; returns (bbox, label)."""
    if not ANTHROPIC_API_KEY or anthropic is None:
        return None, ""
    try:
        import io
        from PIL import Image
        img = Image.open(src).convert("RGB")
        max_w = 1024
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        try:
            b64 = base64.b64encode(src.read_bytes()).decode()
        except Exception:
            return None, ""
    prompt = (
        f"This screenshot is from a FAILED end-to-end UI test named '{test_name}'. "
        f"The functional problem is: {impact}\n\n"
        "Identify the SINGLE rectangular region of the page most relevant to this failure "
        "(the broken, missing, or misplaced element - or the area where the expected element should be). "
        "Return ONLY a JSON object with fractions of the image dimensions (0.0-1.0): "
        '{"x":float,"y":float,"width":float,"height":float,"label":"3-5 word description"}. '
        "No prose, no code fences."
    )
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
        text = "\n".join(c.text for c in msg.content if getattr(c, "type", "") == "text").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n", "", text)
            text = re.sub(r"\n```\s*$", "", text)
        data = json.loads(text)
        label = str(data.get("label", ""))[:40]
        bbox = {k: float(data[k]) for k in ("x", "y", "width", "height") if k in data}
        if all(k in bbox for k in ("x", "y", "width", "height")):
            return bbox, label
    except Exception as exc:
        print(f"  vision annotation failed for '{test_name}': {exc}")
    return None, ""


def build_visual_evidence(failures: list[dict], triage: dict | None = None) -> dict[str, dict]:
    """Copy each failure screenshot into the report and draw a red box on the problem area."""
    evidence: dict[str, dict] = {}
    impact_by_test: dict[str, str] = {}
    if triage:
        for ft in triage.get("failing_tests", []):
            impact_by_test[ft.get("test_name", "")] = ft.get("functional_impact", "")
    shots_dir = REPORTS_DIR / "screenshots"
    for f in failures:
        shot = f.get("screenshot") or ""
        if not shot:
            continue
        src = Path(shot)
        if not src.exists():
            continue
        shots_dir.mkdir(parents=True, exist_ok=True)
        test_name = f.get("test", "test")
        impact = impact_by_test.get(test_name) or f.get("error", "")
        bbox, label = _vision_bbox(src, test_name, impact)
        dst = shots_dir / f"{_safe_name(test_name)}.png"
        if _annotate_bbox(src, dst, bbox, label):
            evidence[test_name] = {"image": f"screenshots/{dst.name}", "label": label}
            print(f"  visual evidence for '{test_name}'" + (f" (boxed: {label})" if bbox else " (plain)"))
    return evidence


# --------- Dashboard HTML ---------

def dashboard_html(summary: dict[str, Any], triage: dict[str, Any], visual_evidence: dict | None = None) -> str:
    cov = summary["coverage"]
    pw = summary["playwright"]

    all_pass = pw.get("failed", 0) == 0 and pw.get("total", 0) > 0
    e2e_total  = pw.get("total",  0)
    e2e_passed = pw.get("passed", 0)
    e2e_failed = pw.get("failed", 0)

    # ── Unit test card ──────────────────────────────────────────────────
    unit_ok = (UNIT_OUTCOME == "success")
    if unit_ok:
        unit_status_html = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;"><span style="width:8px;height:8px;border-radius:50%;background:#16a34a;flex-shrink:0;"></span><span style="font-size:14px;font-weight:600;color:#15803d;">All tests passed</span></div>'
    else:
        unit_status_html = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;"><span style="width:8px;height:8px;border-radius:50%;background:#dc2626;flex-shrink:0;"></span><span style="font-size:14px;font-weight:600;color:#b91c1c;">Tests failed</span></div>'

    unit_card = f"""<div class="card">
      <div class="card-label">Unit Tests <span class="runner-chip">Vitest</span></div>
      {unit_status_html}
      {coverage_bar(cov['lines_pct'])}
    </div>"""

    # ── E2E card — show numeric split ──────────────────────────────────
    if e2e_total == 0:
        e2e_inner = '<div style="color:#6b7280;font-size:14px;margin-top:8px;">No results recorded</div>'
    else:
        pass_pct = (e2e_passed / e2e_total * 100) if e2e_total else 0
        p_bg = "#f0fdf4"; p_num_col = "#15803d"; p_lbl_col = "#16a34a"
        f_bg = "#fff"     if e2e_failed == 0 else "#fef2f2"
        f_num_col = "#9ca3af" if e2e_failed == 0 else "#b91c1c"
        f_lbl_col = "#9ca3af" if e2e_failed == 0 else "#dc2626"
        e2e_inner = f"""
        <div style="display:flex;gap:12px;margin-top:12px;">
          <div style="flex:1;background:{p_bg};border-radius:8px;padding:12px 16px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:{p_num_col};line-height:1;">{e2e_passed}</div>
            <div style="font-size:12px;font-weight:500;color:{p_lbl_col};margin-top:4px;letter-spacing:.5px;">PASSED</div>
          </div>
          <div style="flex:1;background:{f_bg};border:1px solid {'#fecaca' if e2e_failed > 0 else '#e5e7eb'};border-radius:8px;padding:12px 16px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:{f_num_col};line-height:1;">{e2e_failed}</div>
            <div style="font-size:12px;font-weight:500;color:{f_lbl_col};margin-top:4px;letter-spacing:.5px;">FAILED</div>
          </div>
        </div>
        <div style="font-size:12px;color:#9ca3af;margin-top:10px;">{e2e_total} tests total · {pass_pct:.0f}% passing</div>"""
    e2e_card = f"""<div class="card">
      <div class="card-label">E2E Tests <span class="runner-chip">Playwright</span></div>
      {e2e_inner}
    </div>"""

    # ── Failing tests table ────────────────────────────────────────────
    failing_tests = triage.get("failing_tests", [])
    if failing_tests:
        fail_rows = "\n".join(
            f"""<tr>
                <td class="td-name">{html.escape(ft.get('test_name', 'Unknown'))}</td>
                <td>{html.escape(ft.get('functional_impact', 'No impact description'))}</td>
                <td>{html.escape(ft.get('qa_action', 'No action specified'))}</td>
            </tr>"""
            for ft in failing_tests
        )
        failing_section = f"""<div class="section-header"><h2>Failing Tests — Functional Impact</h2></div>
        <table>
            <thead><tr><th>Test</th><th>What broke for users</th><th>Suggested QA action</th></tr></thead>
            <tbody>{fail_rows}</tbody>
        </table>"""
    else:
        failing_section = ""

    # ── Blind spots ────────────────────────────────────────────────────
    blind_spots = triage.get("blind_spots", [])
    blind_items = "\n".join(
        f'<li><span style="color:#d97706;font-size:13px;margin-right:6px;">⚠</span>{html.escape(bs)}</li>'
        for bs in blind_spots
    )
    blind_section = f"""<div class="blind-card">
        <div class="blind-card-header">
          <span style="font-size:16px;">🔍</span>
          <h2 style="margin:0;">Coverage Gaps</h2>
          <span style="font-size:13px;color:#92400e;font-weight:500;">Areas not covered by automated tests</span>
        </div>
        <ul class="blind-list">{blind_items}</ul>
        <p class="blind-note">These journeys should be verified manually or a new test should be requested via the catalog.</p>
    </div>"""

    # ── Visual evidence ────────────────────────────────────────────────
    visual_evidence = visual_evidence or {}
    if visual_evidence:
        ev_cards = ""
        for _tname, _ev in visual_evidence.items():
            _label = html.escape(_ev.get("label", "") or "")
            _label_html = (
                f'<div style="display:inline-flex;align-items:center;gap:6px;background:#fef2f2;'
                f'border:1px solid #fecaca;border-radius:6px;padding:4px 10px;font-size:12px;'
                f'font-weight:600;color:#b91c1c;margin-bottom:10px;">🎯 {_label}</div>'
            ) if _label else ""
            _img_src = html.escape(_ev.get('image', ''))
            ev_cards += f"""<div class="ev-card">
                <div class="card-label" style="margin-bottom:8px;">{html.escape(_tname)}</div>
                {_label_html}
                <a href="{_img_src}" target="_blank" onclick="openLightbox(event, this.href)">
                  <img src="{_img_src}"
                       alt="Screenshot of {html.escape(_tname)}"
                       style="width:100%;border-radius:8px;border:1px solid #e5e7eb;cursor:zoom-in;display:block;" />
                </a>
                <div style="font-size:11px;color:#9ca3af;margin-top:6px;text-align:center;">Click to enlarge</div>
            </div>"""
        visual_section = f"""<div class="section-header"><h2>Visual Evidence</h2>
        <span style="font-size:13px;color:#6b7280;">Screenshots taken at the moment each test failed · red box marks the problem area</span></div>
        <div class="ev-grid">{ev_cards}</div>"""
    else:
        visual_section = ""

    # ── Gate summary banner ────────────────────────────────────────────
    if all_pass:
        banner_icon  = "✓"
        banner_bg    = "#f0fdf4"
        banner_border= "#86efac"
        banner_icon_col = "#16a34a"
    else:
        banner_icon  = "✕"
        banner_bg    = "#fff7f7"
        banner_border= "#fca5a5"
        banner_icon_col = "#dc2626"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QA Dashboard — {html.escape(JIRA_EPIC_KEY)}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
      background: #f8fafc;
      color: #111827;
      font-size: 14px;
      line-height: 1.5;
    }}
    /* ── Header ── */
    .header {{
      background: #111827;
      padding: 20px 32px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .header-left h1 {{ font-size: 20px; font-weight: 700; color: #f9fafb; }}
    .header-left .meta {{
      font-size: 12px; color: #6b7280; margin-top: 3px;
    }}
    .header-left .meta a {{ color: #93c5fd; text-decoration: none; }}
    .header-left .meta a:hover {{ text-decoration: underline; }}
    .header-nav a {{
      display: inline-flex; align-items: center; gap: 6px;
      background: #1f2937; color: #d1d5db;
      border: 1px solid #374151;
      padding: 7px 14px; border-radius: 6px;
      text-decoration: none; font-size: 13px; font-weight: 500;
      transition: background .15s;
    }}
    .header-nav a:hover {{ background: #374151; color: #f9fafb; }}
    /* ── Layout ── */
    .container {{ max-width: 1080px; margin: 0 auto; padding: 28px 20px 48px; }}
    /* ── Summary banner ── */
    .summary-banner {{
      background: {banner_bg};
      border: 1px solid {banner_border};
      border-radius: 10px;
      padding: 16px 20px;
      display: flex;
      gap: 14px;
      align-items: flex-start;
      margin-bottom: 24px;
    }}
    .banner-icon {{
      width: 28px; height: 28px; flex-shrink: 0;
      border-radius: 50%;
      background: {banner_icon_col};
      color: #fff; font-weight: 700; font-size: 14px;
      display: flex; align-items: center; justify-content: center;
    }}
    .summary-banner p {{ font-size: 14px; color: #374151; line-height: 1.65; }}
    /* ── Cards grid ── */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }}
    .card {{
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 20px 22px;
    }}
    .card-label {{
      font-size: 12px;
      font-weight: 600;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: .6px;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .runner-chip {{
      background: #f3f4f6;
      color: #374151;
      font-size: 11px;
      padding: 2px 7px;
      border-radius: 4px;
      font-weight: 500;
      letter-spacing: 0;
      text-transform: none;
    }}
    /* ── Section headers ── */
    .section-header {{
      display: flex;
      align-items: baseline;
      gap: 12px;
      margin: 32px 0 14px;
      flex-wrap: wrap;
    }}
    .section-header h2 {{
      font-size: 16px;
      font-weight: 700;
      color: #111827;
    }}
    /* ── Failing tests table ── */
    .table-wrap {{
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      overflow: hidden;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      text-align: left;
      padding: 11px 16px;
      font-size: 13px;
      border-bottom: 1px solid #f3f4f6;
      vertical-align: top;
    }}
    th {{ background: #f9fafb; font-weight: 600; color: #374151; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }}
    tr:last-child td {{ border-bottom: none; }}
    td.td-name {{ font-weight: 500; white-space: nowrap; }}
    /* ── Blind spots ── */
    .blind-card {{
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 20px 24px;
      margin-top: 24px;
    }}
    .blind-card-header {{
      display: flex; align-items: center; gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 14px;
      padding-bottom: 14px;
      border-bottom: 1px solid #f3f4f6;
    }}
    .blind-card-header h2 {{ font-size: 16px; font-weight: 700; color: #111827; }}
    .blind-list {{ list-style: none; padding: 0; }}
    .blind-list li {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 8px 0;
      font-size: 13px;
      color: #374151;
      line-height: 1.55;
      border-bottom: 1px solid #f9fafb;
    }}
    .blind-list li:last-child {{ border-bottom: none; }}
    .blind-note {{ margin-top: 14px; font-size: 12px; color: #9ca3af; font-style: italic; }}
    /* ── Visual evidence ── */
    .ev-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }}
    .ev-card {{
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 18px 20px;
    }}
    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 24px;
      color: #9ca3af;
      font-size: 12px;
      margin-top: 32px;
      border-top: 1px solid #e5e7eb;
    }}
    /* ── Catalog strip ── */
    .catalog-strip {{
      background: #1e3a5f;
      padding: 20px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 14px;
    }}
    .catalog-strip p {{
      color: #93c5fd;
      font-size: 14px;
      margin: 0;
    }}
    .catalog-strip a.cta {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #2563eb;
      color: #fff;
      padding: 10px 22px;
      border-radius: 8px;
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
      white-space: nowrap;
      transition: background .15s;
    }}
    .catalog-strip a.cta:hover {{ background: #1d4ed8; }}
    /* ── Lightbox ── */
    #lb-overlay {{
      display: none;
      position: fixed; inset: 0;
      background: rgba(0,0,0,.85);
      z-index: 9999;
      align-items: center;
      justify-content: center;
      cursor: zoom-out;
    }}
    #lb-overlay.open {{ display: flex; }}
    #lb-overlay img {{
      max-width: 92vw;
      max-height: 92vh;
      border-radius: 6px;
      box-shadow: 0 8px 40px rgba(0,0,0,.6);
    }}
    #lb-close {{
      position: fixed; top: 16px; right: 20px;
      color: #fff; font-size: 28px; cursor: pointer;
      line-height: 1; user-select: none;
    }}
  </style>
</head>
<body>
  <!-- Lightbox overlay -->
  <div id="lb-overlay" onclick="closeLightbox()">
    <span id="lb-close" onclick="closeLightbox()">×</span>
    <img id="lb-img" src="" alt="" />
  </div>
  <script>
    function openLightbox(e, src) {{
      e.preventDefault();
      document.getElementById('lb-img').src = src;
      document.getElementById('lb-overlay').classList.add('open');
      document.addEventListener('keydown', _lbKey);
    }}
    function closeLightbox() {{
      document.getElementById('lb-overlay').classList.remove('open');
      document.getElementById('lb-img').src = '';
      document.removeEventListener('keydown', _lbKey);
    }}
    function _lbKey(e) {{ if (e.key === 'Escape') closeLightbox(); }}
  </script>
  <header class="header">
    <div class="header-left">
      <div style="font-size:12px;color:#6b7280;margin-bottom:4px;"><a href="index.html" style="color:#9ca3af;text-decoration:none;">← Hub</a></div>
      <h1>Post-Run Test Report</h1>
      <div class="meta">
        Epic: <a href="{html.escape(JIRA_BASE_URL)}/browse/{html.escape(JIRA_EPIC_KEY)}" target="_blank">{html.escape(JIRA_EPIC_KEY)}</a>
        &nbsp;·&nbsp; {html.escape(RUN_TIMESTAMP)}
      </div>
    </div>
  </header>

  <div class="container">

    <div class="summary-banner">
      <div class="banner-icon">{banner_icon}</div>
      <p>{html.escape(triage.get('summary', 'No summary available.'))}</p>
    </div>

    <div class="cards-grid">
      {unit_card}
      {e2e_card}
    </div>

    {'<div class="table-wrap">' + failing_section + '</div>' if failing_section else ''}

    {visual_section}

    {blind_section}

    <div class="footer">Generated by AI Test Pipeline · Stefgug/fwebsite</div>
  </div>

  <div class="catalog-strip">
    <p>See all tests by area, AI-proposed improvements, and per-test flags.</p>
    <a href="catalog.html" class="cta">📋 View Test Catalog →</a>
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

    pw = summary["playwright"]
    visual_evidence = build_visual_evidence(pw.get("failures", []), triage)

    # The post-run dashboard now lives at test-report.html (index.html is the hub).
    report_html = dashboard_html(summary, triage, visual_evidence)
    (REPORTS_DIR / "test-report.html").write_text(report_html, encoding="utf-8")

    # index.html = the GitHub Pages hub linking to every report.
    (REPORTS_DIR / "index.html").write_text(rc.build_hub_html(), encoding="utf-8")

    # Metadata consumed by the hub (client-side) + the "current epic" marker
    # used by the anticipatory code-change analysis workflow.
    generated_at, generated_ts = rc.now_utc()
    e2e_total = pw.get("total", 0)
    rc.write_meta(REPORTS_DIR, "test-report.meta.json", {
        "type": "test-report",
        "title": "Post-Run Test Report",
        "href": "test-report.html",
        "generated_at": generated_at,
        "generated_ts": generated_ts,
        "epic_key": JIRA_EPIC_KEY,
        "epic_title": JIRA_EPIC_TITLE,
        "gate": "pass" if (pw.get("failed", 0) == 0 and e2e_total > 0 and UNIT_OUTCOME == "success") else "fail",
        "e2e": f"{pw.get('passed', 0)}/{e2e_total}" if e2e_total else "",
        "coverage": round(float(summary["coverage"].get("lines_pct", 0.0)), 1),
    })
    rc.write_meta(REPORTS_DIR, "current-epic.json", {
        "epic_key": JIRA_EPIC_KEY,
        "epic_title": JIRA_EPIC_TITLE,
        "updated_at": generated_at,
    })

    # Test catalog page
    (REPORTS_DIR / "proposed-tests.json").write_text(
        json.dumps(
            {"generated_at": RUN_TIMESTAMP, "epic_key": JIRA_EPIC_KEY,
             "run_id": GITHUB_RUN_ID, "proposals": proposals or []},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    catalog_html = generate_catalog_html(pw, triage, jira_bug_links, proposals)
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
    dash_path.write_text(report_html, encoding="utf-8")
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


def transition_epic(issue_key: str, target_category: str, fallback_names: list[str]) -> bool:
    """Transition an issue to the first transition whose destination status matches
    target_category (statusCategory.key, e.g. 'done' for Done), falling back to a name match.
    Best-effort & fail-safe."""
    if not (JIRA_EMAIL and JIRA_API_TOKEN and issue_key):
        return False
    try:
        r = requests.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Accept": "application/json"},
            timeout=20,
        )
        if not r.ok:
            print(f"  (transition skipped: HTTP {r.status_code})")
            return False
        transitions = r.json().get("transitions", [])
        names_lc = [n.lower() for n in fallback_names]
        chosen = None
        for t in transitions:
            cat = (((t.get("to") or {}).get("statusCategory") or {}).get("key") or "").lower()
            if cat == target_category:
                chosen = t
                break
        if not chosen:
            for t in transitions:
                to_name = ((t.get("to") or {}).get("name") or "").lower()
                tname = (t.get("name") or "").lower()
                if to_name in names_lc or tname in names_lc:
                    chosen = t
                    break
        if not chosen:
            print(f"  (no transition found for category '{target_category}')")
            return False
        pr = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"transition": {"id": chosen["id"]}},
            timeout=20,
        )
        if pr.ok:
            print(f"  -> {issue_key} transitioned to '{(chosen.get('to') or {}).get('name')}'")
            return True
        print(f"  (transition POST failed: HTTP {pr.status_code} {pr.text[:200]})")
        return False
    except Exception as exc:
        print(f"  (transition error: {exc})")
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

        # Split tests into failed vs passed
        failed_in_area  = [t for t in test_names if t in failed_tests]
        passed_in_area  = [t for t in test_names if t not in failed_tests]
        n_failed = len(failed_in_area)
        n_passed = len(passed_in_area)

        def _make_row(test_name: str, is_failed: bool) -> str:
            if is_failed:
                s_badge = ('<span style="display:inline-flex;align-items:center;gap:5px;'
                           'background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;'
                           'padding:3px 9px;border-radius:5px;font-size:12px;font-weight:600;">✕ Failed</span>')
            elif e2e_ran:
                s_badge = ('<span style="display:inline-flex;align-items:center;gap:5px;'
                           'background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;'
                           'padding:3px 9px;border-radius:5px;font-size:12px;font-weight:600;">✓ Passed</span>')
            else:
                s_badge = ('<span style="background:#f3f4f6;color:#6b7280;'
                           'padding:3px 9px;border-radius:5px;font-size:12px;">— Unknown</span>')

            display_name = test_name[0].upper() + test_name[1:] if test_name else test_name

            if is_failed and jira_bug_links and test_name in jira_bug_links:
                jira_info = jira_bug_links[test_name]
                action_cell = (
                    f'<a href="{jira_info["url"]}" target="_blank" '
                    f'style="display:inline-flex;align-items:center;gap:5px;'
                    f'background:#b91c1c;color:#fff;padding:4px 10px;border-radius:5px;'
                    f'font-size:12px;text-decoration:none;font-weight:600;">🐛 {jira_info["key"]}</a>'
                )
            else:
                encoded_name = quote_plus(test_name)
                if is_failed and test_name in triage_by_test:
                    ti = triage_by_test[test_name]
                    issue_body = (
                        f"**Area:** {area_name}\n"
                        f"**Test:** {test_name}\n\n"
                        f"**What broke:**\n{ti.get('functional_impact', '')}\n\n"
                        f"**Suggested QA action:**\n{ti.get('qa_action', '')}\n\n"
                        f"---\n*Auto-generated from the AI test pipeline report.*"
                    )
                else:
                    issue_body = f"Area: {area_name}\nTest: {test_name}\n\nDescribe the issue or improvement needed:"
                flag_url = (
                    f"https://github.com/Stefgug/fwebsite/issues/new"
                    f"?title=Test+flag:+{encoded_name}"
                    f"&body={quote_plus(issue_body)}"
                )
                if is_failed:
                    action_cell = (
                        f'<a href="{flag_url}" target="_blank" '
                        f'style="color:#dc2626;font-size:12px;text-decoration:none;font-weight:500;">🚩 Report issue</a>'
                    )
                else:
                    action_cell = (
                        f'<a href="{flag_url}" target="_blank" '
                        f'style="color:#d1d5db;font-size:12px;text-decoration:none;">🚩 Flag</a>'
                    )

            return (
                f'<tr>'
                f'<td style="padding:10px 14px;white-space:nowrap;">{s_badge}</td>'
                f'<td style="padding:10px 14px;color:#1f2937;font-size:13px;">{html.escape(display_name)}</td>'
                f'<td style="padding:10px 14px;white-space:nowrap;">{action_cell}</td>'
                f'</tr>'
            )

        # Failed rows always shown
        failed_rows_html = "".join(_make_row(t, True)  for t in failed_in_area)
        passed_rows_html = "".join(_make_row(t, False) for t in passed_in_area)

        if not test_names:
            table_body = '<tr><td colspan="3" style="padding:14px;color:#9ca3af;font-style:italic;">No tests parsed from spec file.</td></tr>'
            toggle_html = ""
        else:
            area_id = re.sub(r"[^a-z0-9]", "-", area_name.lower())

            # Failed rows + conditional passed-rows collapse
            passed_toggle_html = ""
            if passed_in_area:
                passed_toggle_html = (
                    f'<tr class="passed-toggle-row" data-area="{area_id}">'
                    f'<td colspan="3" style="padding:10px 14px;">'
                    f'<button onclick="togglePassed(\'{area_id}\')" '
                    f'style="background:none;border:none;cursor:pointer;color:#6b7280;font-size:12px;'
                    f'display:flex;align-items:center;gap:6px;padding:0;" id="btn-{area_id}">'
                    f'<span id="arrow-{area_id}" style="transition:transform .2s;">▶</span>'
                    f'Show {n_passed} passed test{"s" if n_passed != 1 else ""}'
                    f'</button>'
                    f'</td></tr>'
                    + "".join(
                        f'<tr class="passed-row-{area_id}" style="display:none;">'
                        f'<td style="padding:10px 14px;white-space:nowrap;">'
                        + (_make_row(t, False).split("<td style", 1)[1].split("</td>", 1)[0].replace("style=", "<td style=", 1) if False else "")
                        + f'</tr>'
                        for t in passed_in_area
                    )
                )
                # simpler: generate each passed row directly
                passed_toggle_html = (
                    f'<tr data-area="{area_id}">'
                    f'<td colspan="3" style="padding:10px 14px;background:#fafafa;border-top:1px solid #f3f4f6;">'
                    f'<button onclick="togglePassed(\'{area_id}\')" '
                    f'id="btn-{area_id}" '
                    f'style="background:none;border:none;cursor:pointer;color:#6b7280;font-size:12px;'
                    f'display:inline-flex;align-items:center;gap:6px;padding:0;">'
                    f'<span id="arrow-{area_id}" style="display:inline-block;transition:transform .2s;font-size:10px;">▶</span>'
                    f'&nbsp;Show {n_passed} passed test{"s" if n_passed != 1 else ""}'
                    f'</button>'
                    f'</td></tr>'
                )
                passed_rows_section = "".join(
                    f'<tr class="passed-row-{area_id}" style="display:none;">{_make_row(t, False)[4:]}'
                    for t in passed_in_area
                )
            else:
                passed_toggle_html = ""
                passed_rows_section = ""

            table_body = failed_rows_html + passed_toggle_html + passed_rows_section
            toggle_html = ""  # JS is in the page <script>

        # Area header meta
        area_pills = ""
        if n_failed:
            area_pills += (f'<span style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;'
                           f'padding:3px 9px;border-radius:5px;font-size:12px;font-weight:600;">'
                           f'{n_failed} failing</span> ')
        area_pills += (f'<span style="background:#f3f4f6;color:#374151;'
                       f'padding:3px 9px;border-radius:5px;font-size:12px;font-weight:500;">'
                       f'{len(test_names)} tests</span>')

        area_cards_html += f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:20px;overflow:hidden;">
            <div style="padding:18px 20px 12px;display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap;border-bottom:1px solid #f3f4f6;">
                <div style="flex:1;min-width:0;">
                    <h2 style="font-size:15px;font-weight:700;color:#111827;margin-bottom:4px;">{html.escape(area_name)}</h2>
                    <div style="font-size:13px;color:#6b7280;line-height:1.45;">{html.escape(description)}</div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;flex-shrink:0;">
                    {area_pills}
                    <a href="https://github.com/Stefgug/fwebsite/blob/main/frontend/tests/{spec_file}"
                       target="_blank"
                       style="font-size:12px;color:#9ca3af;text-decoration:none;white-space:nowrap;">↗ source</a>
                </div>
            </div>
            <div style="overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="background:#f9fafb;">
                            <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;width:105px;">Status</th>
                            <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;">Test</th>
                            <th style="padding:9px 14px;text-align:left;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;width:120px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>{table_body}</tbody>
                </table>
            </div>
        </div>"""

    for _p in (proposals or []):
        _p.setdefault("jira_epic_key", JIRA_EPIC_KEY)
        _p.setdefault("source", "post-run")
    proposals_html = rc.proposals_section_html(
        proposals or [],
        intro=("Claude analysed the failures and coverage gaps, then proposed the improvements below — "
               "each verified against the existing suite. Use <strong>Run on a branch</strong> to validate "
               "the test, or <strong>Create Jira ticket</strong> to track it in the Epic."),
    )

    catalog_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Catalog — {html.escape(JIRA_EPIC_KEY)}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
          background: #f8fafc;
          color: #111827;
          font-size: 14px;
          line-height: 1.5;
        }}
        a {{ color: #2563eb; }}
        .header {{
          background: #111827;
          padding: 18px 32px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 10px;
        }}
        .header-left .breadcrumb {{ font-size:12px;color:#6b7280;margin-bottom:4px; }}
        .header-left .breadcrumb a {{ color:#9ca3af;text-decoration:none; }}
        .header-left .breadcrumb a:hover {{ color:#d1d5db; }}
        .header-left h1 {{ font-size:19px;font-weight:700;color:#f9fafb; }}
        .header-left .meta {{ font-size:12px;color:#6b7280;margin-top:3px; }}
        .header-left .meta a {{ color:#93c5fd;text-decoration:none; }}
        .container {{ max-width:960px;margin:0 auto;padding:28px 20px 48px; }}
        .section-title {{
          font-size:16px;font-weight:700;color:#111827;
          margin:32px 0 16px;
          padding-bottom:12px;
          border-bottom:1px solid #e5e7eb;
        }}
        .footer {{
          text-align:center;padding:24px;color:#9ca3af;font-size:12px;
          border-top:1px solid #e5e7eb;margin-top:8px;
        }}
    </style>
    <script>
    function togglePassed(areaId) {{
        var rows = document.querySelectorAll('.passed-row-' + areaId);
        var arrow = document.getElementById('arrow-' + areaId);
        var btn   = document.getElementById('btn-' + areaId);
        var hidden = rows.length > 0 && rows[0].style.display === 'none';
        rows.forEach(function(r) {{ r.style.display = hidden ? '' : 'none'; }});
        if (arrow) arrow.style.transform = hidden ? 'rotate(90deg)' : '';
        if (btn) {{
          var count = rows.length;
          var label = hidden
            ? 'Hide ' + count + ' passed test' + (count !== 1 ? 's' : '')
            : 'Show ' + count + ' passed test' + (count !== 1 ? 's' : '');
          btn.innerHTML = '<span id="arrow-' + areaId + '" style="display:inline-block;transition:transform .2s;font-size:10px;transform:' + (hidden ? 'rotate(90deg)' : '') + '">▶</span>&nbsp;' + label;
        }}
    }}
    </script>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <div class="breadcrumb"><a href="index.html">← Hub</a> &nbsp;·&nbsp; <a href="test-report.html">Test Report</a></div>
            <h1>Test Catalog</h1>
            <div class="meta">
                Epic: <a href="{html.escape(JIRA_BASE_URL)}/browse/{html.escape(JIRA_EPIC_KEY)}" target="_blank">{html.escape(JIRA_EPIC_KEY)}</a>
                &nbsp;—&nbsp; {html.escape(JIRA_EPIC_TITLE)}
                &nbsp;·&nbsp; {html.escape(RUN_TIMESTAMP)}
            </div>
        </div>
    </header>

    <main class="container">
        <div class="section-title">Test coverage by area</div>
        {area_cards_html}

        {('<div class="section-title">AI-Proposed Test Improvements</div>' + proposals_html) if proposals_html else ''}
    </main>

    <footer class="footer">
        QA Test Catalog &nbsp;·&nbsp; Generated by AI Test Pipeline &nbsp;·&nbsp; Stefgug/fwebsite
    </footer>
</body>
</html>"""

    return catalog_html


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

    if JIRA_EPIC_KEY and JIRA_EPIC_KEY != "UNKNOWN-EPIC":
        transition_epic(JIRA_EPIC_KEY, "done", ["Terminé", "Terminé(e)", "Done", "Closed"])

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

