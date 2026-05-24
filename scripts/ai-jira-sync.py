#!/usr/bin/env python3
"""
Phase 1 — AI Commit → Jira
Analyzes a git commit diff with Claude (tool_use for guaranteed JSON)
and creates or updates a Jira ticket.
"""
import os
import re
import subprocess
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")
COMMIT_MESSAGE = os.environ.get("GIT_COMMIT_MESSAGE", "")
COMMIT_SHA = os.environ.get("GIT_COMMIT_SHA", "")
COMMIT_AUTHOR = os.environ.get("GIT_AUTHOR", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

# Tool schema forces Claude to return well-typed, valid JSON — no escaping issues.
JIRA_TOOL = {
    "name": "create_jira_ticket",
    "description": "Crée un ticket Jira à partir d'un commit Git.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Titre court du ticket (max 80 caractères), en français."
            },
            "description": {
                "type": "string",
                "description": (
                    "Description structurée en markdown (en français): "
                    "ce qui a changé, pourquoi, et l'impact potentiel. "
                    "Ne pas inclure de code ou de diff brut."
                )
            },
        },
        "required": ["summary", "description"],
    },
}


def get_git_diff() -> str:
    try:
        # --stat gives a compact summary; --unified=2 adds limited context lines
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--stat", "--unified=2"],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout[:6000] or "(empty diff — first commit or squash)"
    except Exception as e:
        return f"(could not get diff: {e})"


def detect_existing_jira_key(message: str) -> str | None:
    match = re.search(r'\b(SCRUM-\d+)\b', message, re.IGNORECASE)
    return match.group(1).upper() if match else None


def analyze_with_claude(diff: str, commit_message: str, author: str) -> dict:
    """Use tool_use to guarantee structured, valid JSON output from Claude."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        f"Analyse ce commit Git et remplis le ticket Jira correspondant.\n\n"
        f"**Auteur :** {author}\n"
        f"**Message :** {commit_message}\n"
        f"**SHA :** {COMMIT_SHA[:8] or 'unknown'}\n"
        f"**Dépôt :** {GITHUB_REPO}\n\n"
        f"**Diff (résumé) :**\n```\n{diff}\n```"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=[JIRA_TOOL],
        tool_choice={"type": "tool", "name": "create_jira_ticket"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    return tool_block.input  # Already a Python dict — no JSON parsing needed


def jira_request(method: str, path: str, body: dict | None = None) -> requests.Response:
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    return requests.request(
        method, url, json=body,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=15,
    )


def build_adf(paragraphs: list[str]) -> dict:
    """Build a minimal Atlassian Document Format body from plain text paragraphs."""
    return {
        "type": "doc", "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]}
            for p in paragraphs if p
        ],
    }


def create_jira_ticket(summary: str, description: str) -> str:
    body = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": "Tâche"},
            "summary": summary[:255],
            "description": build_adf([
                description,
                f"🤖 Auto-créé — commit {COMMIT_SHA[:8]} par {COMMIT_AUTHOR}",
            ]),
        }
    }
    res = jira_request("POST", "/issue", body)
    res.raise_for_status()
    return res.json()["key"]


def add_jira_comment(issue_key: str, description: str) -> None:
    comment = (
        f"Commit lié : {COMMIT_SHA[:8]} par {COMMIT_AUTHOR}\n\n{description}"
    )
    body = {"body": build_adf([comment])}
    res = jira_request("POST", f"/issue/{issue_key}/comment", body)
    res.raise_for_status()


def main():
    print("🔍 Getting git diff...")
    diff = get_git_diff()
    print(f"   Diff: {len(diff)} chars")

    print("🤖 Analyzing with Claude (tool_use)...")
    ticket = analyze_with_claude(diff, COMMIT_MESSAGE, COMMIT_AUTHOR)
    summary = ticket["summary"]
    description = ticket["description"]
    print(f"   → {summary}")

    existing_key = detect_existing_jira_key(COMMIT_MESSAGE)
    if existing_key:
        print(f"📎 References {existing_key} — adding comment...")
        add_jira_comment(existing_key, description)
        print(f"✅ {JIRA_BASE_URL}/browse/{existing_key}")
    else:
        print("📝 Creating new ticket...")
        key = create_jira_ticket(summary, description)
        print(f"✅ {JIRA_BASE_URL}/browse/{key}")


if __name__ == "__main__":
    main()
