#!/usr/bin/env python3
"""Create QA test coverage Stories from a Jira Epic using Claude AI.

Reads an Epic from Jira, uses Claude to generate 5-7 functional test coverage
Stories, and creates them as child issues under the Epic.

Required environment variables:
    JIRA_BASE_URL     - Jira instance URL (e.g. https://stephaneguren.atlassian.net)
    JIRA_EMAIL        - Atlassian account email
    JIRA_API_TOKEN    - Atlassian API token
    JIRA_PROJECT_KEY  - Jira project key (e.g. SCRUM)
    JIRA_EPIC_KEY     - Epic issue key (e.g. SCRUM-123)
    ANTHROPIC_API_KEY - Anthropic API key for Claude
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, cast

import requests
from anthropic import Anthropic

# --- Validate required env vars ---

REQUIRED_ENV = [
    "JIRA_BASE_URL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_PROJECT_KEY",
    "JIRA_EPIC_KEY",
    "ANTHROPIC_API_KEY",
]

missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)

JIRA_BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = cast(str, os.environ["JIRA_API_TOKEN"])
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]
JIRA_EPIC_KEY = os.environ["JIRA_EPIC_KEY"]
ANTHROPIC_API_KEY = cast(str, os.environ["ANTHROPIC_API_KEY"])

# --- ADF helpers ---

def adf_text_para(text: str) -> dict[str, Any]:
    """Build a single-paragraph ADF doc node."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": text}
                ],
            }
        ],
    }


def extract_plain_text(adf_node: Any) -> str:
    """Recursively extract all text nodes from an ADF description into a plain string."""
    if adf_node is None:
        return ""
    if isinstance(adf_node, str):
        return adf_node
    if isinstance(adf_node, dict):
        node_type = adf_node.get("type", "")
        if node_type == "text":
            return adf_node.get("text", "")
        content = adf_node.get("content", [])
        return " ".join(extract_plain_text(c) for c in content)
    if isinstance(adf_node, list):
        return " ".join(extract_plain_text(item) for item in adf_node)
    return ""


# --- Dedup helper ---

def existing_child_summaries(epic_key: str) -> set[str]:
    """Return the set of summaries of issues that are children of the Epic, so we can skip duplicates."""
    summaries: set[str] = set()
    next_token = None
    while True:
        body: dict[str, Any] = {"jql": f"parent = {epic_key}", "maxResults": 100, "fields": ["summary"]}
        if next_token:
            body["nextPageToken"] = next_token
        try:
            r = requests.post(
                f"{JIRA_BASE_URL}/rest/api/3/search/jql",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=body,
                timeout=20,
            )
        except Exception:
            break
        if not r.ok:
            print(f"  (dedup check skipped: HTTP {r.status_code})")
            break
        data = r.json()
        for it in data.get("issues", []):
            s = ((it.get("fields") or {}).get("summary") or "").strip()
            if s:
                summaries.add(s)
        next_token = data.get("nextPageToken")
        if not data.get("issues") or not next_token:
            break
    return summaries


# --- Main flow ---

def main() -> None:
    # 1. Fetch the Epic
    print(f"Fetching Epic {JIRA_EPIC_KEY}...")
    res = requests.get(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{JIRA_EPIC_KEY}",
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if not res.ok:
        print(f"ERROR: Failed to fetch Epic {JIRA_EPIC_KEY}: HTTP {res.status_code}")
        print(res.text[:500])
        sys.exit(1)

    issue_data = res.json()
    fields = issue_data.get("fields", {})
    epic_title = (fields.get("summary") or "").strip()
    epic_desc_raw = fields.get("description")
    epic_description = extract_plain_text(epic_desc_raw) if epic_desc_raw else "No description provided."

    print(f"Epic title: {epic_title}")
    print(f"Description: {epic_description[:200]}...")

    # 2. Call Claude to generate Stories
    print("\nGenerating test coverage Stories with Claude...")
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are a QA lead writing functional test coverage stories for a product Epic.

Epic Title: {epic_title}
Epic Description:
{epic_description}

Generate 5-7 functional test coverage Stories for this Epic. Each Story must be written as a user journey that a non-technical QA person understands — no code, no jargon.

Return ONLY a JSON array where each element has:
- "summary": max 100 characters, describing what to test from a user's perspective
- "description": 2-4 sentences describing what to verify from a user perspective

Do NOT include markdown fences, prose, or any text outside the JSON array."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text_parts = [c.text for c in msg.content if getattr(c, "type", "") == "text"]
    raw_response = "\n".join(text_parts).strip()

    # 3. Parse the JSON array
    try:
        # Strip markdown fences if present
        cleaned = raw_response
        if cleaned.startswith("```"):
            import re
            cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned)
            cleaned = re.sub(r"\n```\s*$", "", cleaned)
        stories = json.loads(cleaned)
        if not isinstance(stories, list):
            raise ValueError("Response is not a JSON array")
    except Exception as e:
        print(f"ERROR: Failed to parse Claude response as JSON array: {e}")
        print(f"Raw response:\n{raw_response}")
        sys.exit(1)

    print(f"Claude generated {len(stories)} stories.")

    # 4. Create Jira issues for each Story
    existing = existing_child_summaries(JIRA_EPIC_KEY)
    if existing:
        print(f"Found {len(existing)} existing child issue(s) under {JIRA_EPIC_KEY} — duplicates will be skipped.")

    created = 0
    for i, story in enumerate(stories, 1):
        summary = story.get("summary", f"Test Story {i}")
        description_text = story.get("description", "No description provided.")

        if summary.strip() in existing or summary[:100].strip() in existing:
            print(f"Skipping (already exists): {summary[:60]}")
            continue

        payload = {
            "fields": {
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": summary[:100],
                "description": adf_text_para(description_text),
                "issuetype": {"name": "Story"},
                "parent": {"key": JIRA_EPIC_KEY},
            }
        }

        res = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue",
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )

        if res.ok:
            issue_key = res.json().get("key", "UNKNOWN")
            print(f"Created: {issue_key}")
            created += 1
        else:
            print(f"ERROR creating story {i} ('{summary[:60]}...'): HTTP {res.status_code}")
            print(res.text[:300])

    print(f"\nDone. Created {created}/{len(stories)} stories under {JIRA_EPIC_KEY}.")


if __name__ == "__main__":
    main()
