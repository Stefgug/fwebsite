#!/usr/bin/env python3
"""
Phase 3+4 — AI Test Failure Analysis + Auto-Fix PR
1. Reads Playwright JSON test results
2. For each failure: asks Claude to explain the error and propose a fix
3. Creates a Jira comment with the analysis
4. Applies the proposed code fix on a new git branch and opens a PR
"""
import json
import os
import re
import subprocess
import sys
import textwrap
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Stefgug/fwebsite")
COMMIT_SHA = os.environ.get("GIT_COMMIT_SHA", "")
RESULTS_FILE = os.environ.get("RESULTS_FILE", "frontend/test-results/results.json")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def extract_failures(results: dict) -> list[dict]:
    """Extract failed specs from Playwright JSON report."""
    failures = []

    def walk(suites: list, file_path: str = ""):
        for suite in suites:
            title = suite.get("title", "")
            fp = suite.get("file", file_path) or file_path
            nested = suite.get("suites", [])
            if nested:
                walk(nested, fp)
            for spec in suite.get("specs", []):
                for test in spec.get("tests", []):
                    if test.get("status") in ("failed", "timedOut"):
                        error_result = next(
                            (r for r in test.get("results", []) if r.get("status") in ("failed", "timedOut")),
                            {}
                        )
                        failures.append({
                            "file": fp,
                            "suite": title,
                            "title": spec.get("title", ""),
                            "error": error_result.get("error", {}).get("message", ""),
                            "stdout": "\n".join(
                                m.get("text", "") for m in error_result.get("stdout", [])
                            ),
                        })

    walk(results.get("suites", []))
    return failures


def read_source_file(test_file: str) -> str:
    """Try to read the test file for context."""
    # test_file is relative to the project, like 'frontend/tests/home.spec.ts'
    try:
        path = test_file if os.path.isabs(test_file) else os.path.join("frontend", test_file)
        if not os.path.exists(path):
            path = test_file
        with open(path) as f:
            return f.read()[:3000]
    except Exception:
        return "(test file not found)"


def analyze_failure_with_claude(failure: dict, test_code: str) -> dict:
    """Ask Claude to explain the failure and propose a fix."""
    prompt = f"""Tu es un expert en tests Playwright et Next.js. Analyse cet échec de test.

Fichier de test: {failure['file']}
Suite: {failure['suite']}
Test: {failure['title']}

Erreur:
{failure['error'][:2000]}

Code du test:
```typescript
{test_code}
```

Réponds en JSON avec:
- "analysis": explication claire de pourquoi le test a échoué (2-3 phrases, en français)
- "user_impact": impact côté utilisateur si ce bug existe en production (1 phrase)
- "fix_suggestion": correction proposée (code ou explication technique, en français)
- "fix_file": chemin relatif du fichier à corriger (ex: "frontend/app/page.tsx"), ou null si incertain
- "fix_code_hint": extrait de code de la correction (optionnel, peut être vide string)

Réponds UNIQUEMENT avec le JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"analysis": raw, "user_impact": "", "fix_suggestion": "", "fix_file": None, "fix_code_hint": ""}


def jira_request(method: str, path: str, body: dict | None = None) -> requests.Response:
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    auth = (JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    return requests.request(method, url, json=body, auth=auth, headers=headers, timeout=15)


def find_or_create_jira_ticket(failure: dict, analysis: dict) -> str:
    """Find an existing ticket matching the test name, or create a new one."""
    # Search for existing ticket
    jql = f'project = {JIRA_PROJECT_KEY} AND summary ~ "Échec test: {failure["title"][:40]}" ORDER BY created DESC'
    res = jira_request("GET", f"/search?jql={requests.utils.quote(jql)}&maxResults=1")
    if res.ok:
        issues = res.json().get("issues", [])
        if issues:
            return issues[0]["key"]

    # Create new ticket
    summary = f"🔴 Échec test: {failure['title'][:70]}"
    body = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": "Tâche"},
            "summary": summary,
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": f"Test automatisé en échec sur le commit {COMMIT_SHA[:8]}.\n\n{analysis.get('analysis', '')}"}
                ]}]
            }
        }
    }
    res = jira_request("POST", "/issue", body)
    res.raise_for_status()
    return res.json()["key"]


def add_jira_comment(issue_key: str, failure: dict, analysis: dict, pr_url: str | None) -> None:
    lines = [
        f"🔴 **Échec de test Playwright** — commit `{COMMIT_SHA[:8]}`",
        f"**Fichier:** `{failure['file']}`",
        f"**Test:** {failure['title']}",
        "",
        f"**Analyse IA:** {analysis.get('analysis', '-')}",
        f"**Impact utilisateur :** {analysis.get('user_impact', '-')}",
        "",
        f"**Correction suggérée :** {analysis.get('fix_suggestion', '-')}",
    ]
    if pr_url:
        lines += ["", f"🔧 **PR de correction automatique :** {pr_url}"]

    content_text = "\n".join(lines)
    body = {
        "body": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": content_text}]}]
        }
    }
    res = jira_request("POST", f"/issue/{issue_key}/comment", body)
    if not res.ok:
        print(f"  ⚠️  Jira comment failed: {res.text[:200]}")


def create_fix_pr(failure: dict, analysis: dict) -> str | None:
    """Create a git branch with a fix note and open a GitHub PR."""
    if not GH_TOKEN:
        print("  ℹ️  GH_TOKEN not set — skipping PR creation")
        return None

    fix_file = analysis.get("fix_file")
    fix_code = analysis.get("fix_code_hint", "")
    branch = f"fix/auto-test-{COMMIT_SHA[:8]}-{re.sub(r'[^a-z0-9]', '-', failure['title'].lower())[:30]}"

    # Configure git
    subprocess.run(["git", "config", "user.email", "ci-bot@shopgeneric.dev"], check=False)
    subprocess.run(["git", "config", "user.name", "ShopGeneric CI Bot"], check=False)
    subprocess.run(["git", "checkout", "-b", branch], check=False)

    # Write a fix notes file so the PR is not empty
    fix_notes_path = f"fix-notes/{COMMIT_SHA[:8]}.md"
    os.makedirs("fix-notes", exist_ok=True)
    fix_note_content = textwrap.dedent(f"""
        # Auto-fix suggestion — {failure['title']}

        **Failing test:** `{failure['file']}` > `{failure['title']}`
        **Triggered by commit:** `{COMMIT_SHA[:8]}`

        ## Analyse

        {analysis.get('analysis', '')}

        ## Impact utilisateur

        {analysis.get('user_impact', '')}

        ## Correction proposée

        {analysis.get('fix_suggestion', '')}

        {'### Code suggéré' if fix_code else ''}
        {'```' + chr(10) + fix_code + chr(10) + '```' if fix_code else ''}

        {'**Fichier à modifier :** `' + fix_file + '`' if fix_file else ''}

        ---
        *Généré automatiquement par Claude Sonnet — vérifier avant de merger.*
    """).strip()

    with open(fix_notes_path, "w") as f:
        f.write(fix_note_content)

    subprocess.run(["git", "add", fix_notes_path], check=False)
    subprocess.run(
        ["git", "commit", "-m", f"fix(auto): test failure analysis for {COMMIT_SHA[:8]}"],
        check=False
    )

    # Push branch
    remote = f"https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPO}.git"
    result = subprocess.run(["git", "push", remote, branch], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  Push failed: {result.stderr[:300]}")
        return None

    # Create PR via GitHub API
    pr_body = {
        "title": f"🔧 Auto-fix: {failure['title'][:80]}",
        "body": fix_note_content,
        "head": branch,
        "base": "main",
    }
    api_res = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/pulls",
        json=pr_body,
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
        timeout=15,
    )
    if api_res.ok:
        pr_url = api_res.json().get("html_url", "")
        print(f"  ✅ PR créée : {pr_url}")
        return pr_url
    else:
        print(f"  ⚠️  PR creation failed: {api_res.text[:300]}")
        return None


def main():
    if not os.path.exists(RESULTS_FILE):
        print(f"✅ No test results file found at {RESULTS_FILE} — no failures to process.")
        sys.exit(0)

    with open(RESULTS_FILE) as f:
        results = json.load(f)

    failures = extract_failures(results)
    if not failures:
        print("✅ All tests passed — nothing to do.")
        sys.exit(0)

    print(f"❌ Found {len(failures)} failing test(s).")

    for i, failure in enumerate(failures, 1):
        print(f"\n[{i}/{len(failures)}] Analyzing: {failure['title']}")
        test_code = read_source_file(failure["file"])

        print("  🤖 Calling Claude...")
        analysis = analyze_failure_with_claude(failure, test_code)
        print(f"  📋 Analysis: {analysis.get('analysis', '')[:100]}...")

        print("  🔧 Creating fix PR...")
        pr_url = create_fix_pr(failure, analysis)

        print("  📎 Posting to Jira...")
        try:
            issue_key = find_or_create_jira_ticket(failure, analysis)
            add_jira_comment(issue_key, failure, analysis, pr_url)
            print(f"  ✅ Jira updated: {JIRA_BASE_URL}/browse/{issue_key}")
        except Exception as e:
            print(f"  ⚠️  Jira failed: {e}")

    print("\n🏁 Done.")


if __name__ == "__main__":
    main()
