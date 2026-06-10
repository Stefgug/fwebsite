#!/usr/bin/env python3
"""Create a Jira ticket (under the Epic) from an AI test proposal.

Triggered by a GitHub issue carrying the `create-jira-ticket` label. The issue
body holds a ```json {proposal} ``` block (the same payload used by the
"Run on a branch" flow), which additionally carries `jira_epic_key`.

Creates a Story (fallback Task) parented to the Epic, with an ADF description
that captures the rationale, coverage check, target file and the proposed test
code. Comments the created Jira key/url back on the GitHub issue and closes it.

Env:
  ISSUE_BODY        - GitHub issue body containing the proposal JSON
  ISSUE_NUMBER      - GitHub issue number (to comment + close)
  GITHUB_REPOSITORY - owner/repo
  GITHUB_TOKEN      - token with issues:write
  JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")


# --------- GitHub helpers ---------

def gh_comment(body: str) -> None:
    if not (ISSUE_NUMBER and GITHUB_REPOSITORY and GITHUB_TOKEN):
        print("Cannot comment — missing GitHub env. Body:\n" + body)
        return
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{ISSUE_NUMBER}/comments",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=20,
    )
    print(f"GitHub comment: HTTP {r.status_code}")


def gh_close() -> None:
    if not (ISSUE_NUMBER and GITHUB_REPOSITORY and GITHUB_TOKEN):
        return
    r = requests.patch(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{ISSUE_NUMBER}",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"state": "closed"},
        timeout=20,
    )
    print(f"GitHub close: HTTP {r.status_code}")


# --------- Proposal extraction ---------

def extract_proposal(body: str) -> dict[str, Any] | None:
    m = re.search(r"```json\s*(.*?)\s*```", body, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except Exception:
        return None


# --------- ADF builder ---------

def _h(text: str, level: int = 3) -> dict[str, Any]:
    return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": text}]}


def _p(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def build_description(p: dict[str, Any]) -> dict[str, Any]:
    kind = p.get("kind")
    kind_label = "Modify an existing test" if kind == "modify_test" else "Add a new test"
    content: list[dict[str, Any]] = [
        {"type": "paragraph", "content": [
            {"type": "text", "text": "🤖 AI-proposed regression test", "marks": [{"type": "strong"}]}]},
        _p(f"Action: {kind_label}"),
        _p(f"Target file: {p.get('target_file', '')}"),
        _p(f"Test name: {p.get('test_name', '')}"),
        _h("Rationale"),
        _p(p.get("rationale", "") or "—"),
        _h("Coverage check"),
        _p(p.get("coverage_check", "") or "—"),
    ]
    proposed = (p.get("proposed_code") or "").strip()
    if proposed:
        content.append(_h("Proposed test code"))
        content.append({
            "type": "codeBlock",
            "attrs": {"language": "typescript"},
            "content": [{"type": "text", "text": proposed[:4000]}],
        })
    src = p.get("source", "")
    if src:
        content.append(_p(f"Source: {'code-change analysis' if src == 'code-change' else 'post-run analysis'}"))
    return {"type": "doc", "version": 1, "content": content}


# --------- Jira create ---------

def create_jira(p: dict[str, Any], epic_key: str | None) -> tuple[str, str] | None:
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    summary = f"[Test] {p.get('title', 'AI-proposed test')}"[:100]
    description = build_description(p)

    def _try(issuetype: str) -> tuple[str, str] | None:
        fields: dict[str, Any] = {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issuetype},
            "labels": ["ai-proposed-test"],
        }
        if epic_key:
            fields["parent"] = {"key": epic_key}
        payload = {"fields": fields}
        r = requests.post(f"{JIRA_BASE_URL}/rest/api/3/issue", auth=auth, headers=headers, json=payload, timeout=20)
        if r.ok:
            key = r.json().get("key", "")
            return key, f"{JIRA_BASE_URL}/browse/{key}"
        print(f"  '{issuetype}' create failed: HTTP {r.status_code} {r.text[:300]}")
        return None

    return _try("Story") or _try("Task")


def main() -> None:
    if not (JIRA_EMAIL and JIRA_API_TOKEN):
        gh_comment("❌ Jira credentials are not configured, so no ticket was created.")
        return

    p = extract_proposal(ISSUE_BODY)
    if not p:
        gh_comment("Could not find a valid proposal JSON block in this issue. No Jira ticket created.")
        return

    raw_epic = (p.get("jira_epic_key") or "").strip()
    epic_key: str | None = raw_epic if (raw_epic and raw_epic != "UNKNOWN-EPIC") else None

    result = create_jira(p, epic_key)
    if not result:
        target = f"under `{epic_key}`" if epic_key else "without an Epic"
        gh_comment(f"❌ Could not create a Jira ticket {target}. Check the workflow logs.")
        return

    key, url = result
    print(f"Created Jira issue {key}")
    if epic_key:
        context = f"under Epic `{epic_key}`"
    else:
        context = "without an Epic (no Epic was specified — you can link it manually in Jira)"
    gh_comment(
        f"✅ Created Jira ticket **[{key}]({url})** {context}.\n\n"
        f"It captures the proposed test (`{p.get('test_name', '')}` in `{p.get('target_file', '')}`), "
        "its rationale and the proposed code. Closing this issue."
    )
    gh_close()


if __name__ == "__main__":
    main()
