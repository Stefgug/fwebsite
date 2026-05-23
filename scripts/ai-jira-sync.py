#!/usr/bin/env python3
"""
Phase 1 — AI Commit → Jira
Analyzes a git commit diff with Claude and creates or updates a Jira ticket.
Run from the root of the repository in GitHub Actions.
"""
import json
import os
import re
import subprocess
import sys
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


def get_git_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--stat", "--unified=3"],
            capture_output=True, text=True, timeout=30
        )
        diff = result.stdout[:8000]  # Cap at 8k chars to avoid token overflow
        return diff or "(empty diff — first commit or squash)"
    except Exception as e:
        return f"(could not get diff: {e})"


def detect_existing_jira_key(message: str) -> str | None:
    """If commit message already references a Jira ticket, return its key."""
    match = re.search(r'\b(SCRUM-\d+)\b', message, re.IGNORECASE)
    return match.group(1).upper() if match else None


def analyze_with_claude(diff: str, commit_message: str, author: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Tu es un assistant de gestion de projet Agile. Analyse ce commit Git et génère un ticket Jira clair et structuré.

Auteur: {author}
Message de commit: {commit_message}
SHA: {COMMIT_SHA[:8] if COMMIT_SHA else 'unknown'}
Dépôt: {GITHUB_REPO}

Diff Git:
{diff}

Génère un ticket Jira en JSON avec ces champs:
- "summary": titre court et clair (max 80 caractères), en français
- "description": description structurée en markdown, incluant: ce qui a changé, pourquoi, et l'impact potentiel
- "issue_type": "Tâche" (use this always, it's the only available type for regular tasks)

Réponds UNIQUEMENT avec le JSON, sans markdown ni texte autour."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    # Strip possible markdown code fences
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


def jira_request(method: str, path: str, body: dict | None = None) -> requests.Response:
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    return requests.request(method, url, json=body, auth=auth, headers=headers, timeout=15)


def create_jira_ticket(summary: str, description: str) -> str:
    """Create a new Jira task and return its key."""
    body = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": "Tâche"},
            "summary": summary,
            "description": {
                "type": "doc", "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description}]},
                    {"type": "paragraph", "content": [
                        {"type": "text", "text": f"\n\n🤖 Auto-créé depuis le commit "},
                        {"type": "text", "text": COMMIT_SHA[:8] or "unknown",
                         "marks": [{"type": "code"}]},
                        {"type": "text", "text": f" par {COMMIT_AUTHOR}"},
                    ]},
                ]
            }
        }
    }
    res = jira_request("POST", "/issue", body)
    res.raise_for_status()
    data = res.json()
    return data["key"]


def add_jira_comment(issue_key: str, comment: str) -> None:
    """Add a comment to an existing Jira ticket."""
    body = {
        "body": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]
        }
    }
    res = jira_request("POST", f"/issue/{issue_key}/comment", body)
    res.raise_for_status()


def main():
    print("🔍 Getting git diff...")
    diff = get_git_diff()
    print(f"   Diff length: {len(diff)} chars")

    print("🤖 Analyzing commit with Claude...")
    ticket = analyze_with_claude(diff, COMMIT_MESSAGE, COMMIT_AUTHOR)
    summary = ticket.get("summary", f"Commit: {COMMIT_MESSAGE[:60]}")
    description = ticket.get("description", COMMIT_MESSAGE)
    print(f"   Summary: {summary}")

    existing_key = detect_existing_jira_key(COMMIT_MESSAGE)

    if existing_key:
        print(f"📎 Commit references existing ticket {existing_key} — adding comment...")
        comment = (
            f"**Commit lié :** `{COMMIT_SHA[:8]}`\n"
            f"**Auteur :** {COMMIT_AUTHOR}\n\n"
            f"{description}"
        )
        add_jira_comment(existing_key, comment)
        print(f"✅ Commentaire ajouté sur {existing_key}")
        print(f"   → {JIRA_BASE_URL}/browse/{existing_key}")
    else:
        print("📝 Creating new Jira ticket...")
        key = create_jira_ticket(summary, description)
        print(f"✅ Ticket créé : {key}")
        print(f"   → {JIRA_BASE_URL}/browse/{key}")


if __name__ == "__main__":
    main()
