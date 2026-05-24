#!/usr/bin/env python3
"""
Phase 3+4 — AI Test Failure Analysis + Auto-Fix PR
1. Reads Playwright JSON test results
2. For each failure: asks Claude (tool_use) to explain and propose a fix
3. Creates a Jira comment with the analysis
4. Commits a fix-notes file on a new branch and opens a GitHub PR
"""
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

ANALYSIS_TOOL = {
    "name": "analyze_test_failure",
    "description": "Analyse un échec de test Playwright et propose une correction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "analysis": {
                "type": "string",
                "description": "Explication claire de pourquoi le test a échoué (2-3 phrases, en français)."
            },
            "user_impact": {
                "type": "string",
                "description": "Impact côté utilisateur si ce bug existe en production (1 phrase, en français)."
            },
            "fix_suggestion": {
                "type": "string",
                "description": "Correction proposée: code ou explication technique précise (en français)."
            },
            "fix_file": {
                "type": "string",
                "description": "Chemin relatif du fichier source à corriger (ex: frontend/app/page.tsx). Vide si incertain."
            },
            "fix_code_hint": {
                "type": "string",
                "description": "Extrait de code de la correction proposée (peut être vide)."
            },
        },
        "required": ["analysis", "user_impact", "fix_suggestion", "fix_file", "fix_code_hint"],
    },
}


def load_results() -> list[dict]:
    """Parse Playwright JSON report and return list of failed tests."""
    import json
    with open(RESULTS_FILE) as f:
        data = json.load(f)

    failures = []

    def walk(suites: list, file_path: str = ""):
        for suite in suites:
            fp = suite.get("file", file_path) or file_path
            title = suite.get("title", "")
            if suite.get("suites"):
                walk(suite["suites"], fp)
            for spec in suite.get("specs", []):
                for test in spec.get("tests", []):
                    if test.get("status") in ("failed", "timedOut"):
                        result = next(
                            (r for r in test.get("results", [])
                             if r.get("status") in ("failed", "timedOut")), {}
                        )
                        failures.append({
                            "file": fp,
                            "suite": title,
                            "title": spec.get("title", ""),
                            "error": result.get("error", {}).get("message", "")[:2000],
                        })

    walk(data.get("suites", []))
    return failures


def read_file_safe(path: str, max_chars: int = 3000) -> str:
    for candidate in [path, os.path.join("frontend", path), os.path.join("frontend/tests", path)]:
        try:
            with open(candidate) as f:
                return f.read()[:max_chars]
        except OSError:
            continue
    return "(file not found)"


def analyze_with_claude(failure: dict, test_code: str) -> dict:
    prompt = (
        f"Analyse cet échec de test Playwright et propose une correction.\n\n"
        f"**Fichier :** `{failure['file']}`\n"
        f"**Suite :** {failure['suite']}\n"
        f"**Test :** {failure['title']}\n\n"
        f"**Erreur :**\n```\n{failure['error']}\n```\n\n"
        f"**Code du test :**\n```typescript\n{test_code}\n```"
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "analyze_test_failure"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    return tool_block.input


def jira_request(method: str, path: str, body: dict | None = None) -> requests.Response:
    return requests.request(
        method, f"{JIRA_BASE_URL}/rest/api/3{path}", json=body,
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=15,
    )


def build_adf(text: str) -> dict:
    return {"type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


def find_or_create_jira_ticket(failure: dict, analysis: dict) -> str:
    safe_title = failure["title"][:50].replace('"', "'")
    jql = f'project = {JIRA_PROJECT_KEY} AND summary ~ "Échec test" AND summary ~ "{safe_title}" ORDER BY created DESC'
    res = jira_request("GET", f'/search?jql={requests.utils.quote(jql)}&maxResults=1')
    if res.ok:
        issues = res.json().get("issues", [])
        if issues:
            return issues[0]["key"]

    body = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": "Tâche"},
            "summary": f"🔴 Échec test: {failure['title'][:70]}",
            "description": build_adf(
                f"Test automatisé en échec sur le commit {COMMIT_SHA[:8]}.\n\n"
                f"{analysis.get('analysis', '')}"
            ),
        }
    }
    res = jira_request("POST", "/issue", body)
    res.raise_for_status()
    return res.json()["key"]


def post_jira_comment(issue_key: str, failure: dict, analysis: dict, pr_url: str | None) -> None:
    lines = [
        f"🔴 Échec Playwright — commit {COMMIT_SHA[:8]}",
        f"Fichier: {failure['file']}",
        f"Test: {failure['title']}",
        "",
        f"Analyse: {analysis.get('analysis', '-')}",
        f"Impact utilisateur: {analysis.get('user_impact', '-')}",
        "",
        f"Correction suggérée: {analysis.get('fix_suggestion', '-')}",
    ]
    if analysis.get("fix_file"):
        lines.append(f"Fichier à modifier: {analysis['fix_file']}")
    if pr_url:
        lines += ["", f"PR de correction automatique: {pr_url}"]

    res = jira_request("POST", f"/issue/{issue_key}/comment",
                       {"body": build_adf("\n".join(lines))})
    if not res.ok:
        print(f"  ⚠️  Jira comment failed ({res.status_code}): {res.text[:200]}")


def create_fix_pr(failure: dict, analysis: dict) -> str | None:
    if not GH_TOKEN:
        print("  ℹ️  GH_TOKEN not set — skipping PR")
        return None

    slug = re.sub(r'[^a-z0-9]+', '-', failure["title"].lower())[:35].strip('-')
    branch = f"fix/auto-{COMMIT_SHA[:8]}-{slug}"

    subprocess.run(["git", "config", "user.email", "ci-bot@shopgeneric.dev"], check=False)
    subprocess.run(["git", "config", "user.name", "ShopGeneric CI Bot"], check=False)

    result = subprocess.run(["git", "checkout", "-b", branch], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  Branch creation failed: {result.stderr[:200]}")
        return None

    os.makedirs("fix-notes", exist_ok=True)
    note_path = f"fix-notes/{COMMIT_SHA[:8]}-{slug}.md"
    fix_code = analysis.get("fix_code_hint", "")
    note = textwrap.dedent(f"""
        # Auto-fix suggestion — {failure['title']}

        **Test en échec :** `{failure['file']}` > `{failure['title']}`
        **Commit déclencheur :** `{COMMIT_SHA[:8]}`

        ## Analyse

        {analysis.get('analysis', '')}

        ## Impact utilisateur

        {analysis.get('user_impact', '')}

        ## Correction proposée

        {analysis.get('fix_suggestion', '')}

        {('### Code suggéré\n```\n' + fix_code + '\n```') if fix_code else ''}
        {('**Fichier à modifier :** `' + analysis['fix_file'] + '`') if analysis.get('fix_file') else ''}

        ---
        *Généré automatiquement par Claude Sonnet — vérifier avant de merger.*
    """).strip()

    with open(note_path, "w") as f:
        f.write(note)

    subprocess.run(["git", "add", note_path], check=False)
    cp = subprocess.run(
        ["git", "commit", "-m", f"fix(auto): analysis for failing test '{failure['title'][:60]}'"],
        capture_output=True, text=True,
    )
    if cp.returncode != 0:
        print(f"  ⚠️  Commit failed: {cp.stderr[:200]}")
        return None

    remote = f"https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPO}.git"
    push = subprocess.run(["git", "push", remote, branch], capture_output=True, text=True)
    if push.returncode != 0:
        print(f"  ⚠️  Push failed: {push.stderr[:300]}")
        return None

    pr_res = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/pulls",
        json={"title": f"🔧 Auto-fix: {failure['title'][:80]}",
              "body": note, "head": branch, "base": "main"},
        headers={"Authorization": f"Bearer {GH_TOKEN}",
                 "Accept": "application/vnd.github+json"},
        timeout=15,
    )
    if pr_res.ok:
        url = pr_res.json().get("html_url", "")
        print(f"  ✅ PR: {url}")
        return url
    print(f"  ⚠️  PR failed ({pr_res.status_code}): {pr_res.text[:300]}")
    return None


def main():
    if not os.path.exists(RESULTS_FILE):
        print(f"✅ No results file at {RESULTS_FILE} — all tests passed.")
        sys.exit(0)

    failures = load_results()
    if not failures:
        print("✅ All tests passed.")
        sys.exit(0)

    print(f"❌ {len(failures)} failing test(s).")
    for i, failure in enumerate(failures, 1):
        print(f"\n[{i}/{len(failures)}] {failure['title']}")
        test_code = read_file_safe(failure["file"])

        print("  🤖 Analyzing with Claude...")
        analysis = analyze_with_claude(failure, test_code)
        print(f"  → {analysis.get('analysis', '')[:100]}")

        print("  🔧 Creating fix branch + PR...")
        pr_url = create_fix_pr(failure, analysis)

        print("  📎 Posting to Jira...")
        try:
            key = find_or_create_jira_ticket(failure, analysis)
            post_jira_comment(key, failure, analysis, pr_url)
            print(f"  ✅ {JIRA_BASE_URL}/browse/{key}")
        except Exception as e:
            print(f"  ⚠️  Jira error: {e}")

    print("\n🏁 Done.")


if __name__ == "__main__":
    main()
