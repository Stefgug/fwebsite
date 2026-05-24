#!/usr/bin/env python3
"""
Phase 5 — AI Test Generation from Commit

1. Reads the diff of the current commit
2. Lists existing Playwright tests (so Claude knows what's already covered)
3. Asks Claude (tool_use) if new tests would be relevant
4. If yes: creates the test files on a tests/auto-* branch and opens a PR
"""
import glob
import os
import re
import subprocess
import sys
import requests
import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Stefgug/fwebsite")
COMMIT_SHA = os.environ.get("GIT_COMMIT_SHA", "")
COMMIT_MESSAGE = os.environ.get("GIT_COMMIT_MESSAGE", "")

TESTS_DIR = "frontend/tests"
FRONTEND_DIR = "frontend"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

TEST_GEN_TOOL = {
    "name": "decide_and_generate_tests",
    "description": "Décide si de nouveaux tests Playwright sont pertinents pour ce commit, puis les génère si oui.",
    "input_schema": {
        "type": "object",
        "properties": {
            "needs_tests": {
                "type": "boolean",
                "description": "True si le commit introduit des fonctionnalités testables (nouvelle page, nouveau composant interactif, nouvelle route) NON déjà couvertes par les tests existants. False pour : refactos, fixes de tests, changements CI/CD, documentation, modifs purement visuelles.",
            },
            "reasoning": {
                "type": "string",
                "description": "Explication courte (2-3 phrases en français) de la décision : ce qui est nouveau, ce qui est déjà couvert, pourquoi des tests sont (ou ne sont pas) pertinents.",
            },
            "tests_to_create": {
                "type": "array",
                "description": "Liste des nouveaux fichiers de tests à créer. Tableau vide si needs_tests=false. Suivre exactement le style des tests existants (même imports, même structure describe/test, mêmes patterns de locators).",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Chemin relatif depuis frontend/, format: tests/<nom>.spec.ts (ex: tests/wishlist.spec.ts)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Contenu COMPLET du fichier .spec.ts en TypeScript/Playwright, prêt à exécuter. Doit importer depuis '@playwright/test', utiliser test.describe/test, et tester uniquement des comportements observables côté utilisateur.",
                        },
                        "what_it_tests": {
                            "type": "string",
                            "description": "Description en français de ce que ce fichier teste (1 phrase).",
                        },
                    },
                    "required": ["file_path", "content", "what_it_tests"],
                },
            },
        },
        "required": ["needs_tests", "reasoning", "tests_to_create"],
    },
}


def get_commit_diff() -> str:
    """Get diff of the commit, limited to source files (excludes lockfiles, generated)."""
    res = subprocess.run(
        [
            "git", "diff", "HEAD~1", "HEAD",
            "--", "frontend/app", "frontend/components", "frontend/lib",
            "frontend/store", "frontend/types", "frontend/hooks",
        ],
        capture_output=True, text=True, check=False,
    )
    return res.stdout[:15_000]  # truncate very large diffs


def get_changed_source_files() -> list[str]:
    """List source files modified in the commit (for context)."""
    res = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD",
         "--", "frontend/app", "frontend/components"],
        capture_output=True, text=True, check=False,
    )
    return [f.strip() for f in res.stdout.splitlines() if f.strip()]


def list_existing_tests() -> list[dict]:
    """Return existing test files with a one-line description (extracted from first describe)."""
    files = sorted(glob.glob(f"{TESTS_DIR}/*.spec.ts"))
    out = []
    for f in files:
        try:
            with open(f) as fp:
                content = fp.read()
            describes = re.findall(r"test\.describe\(['\"]([^'\"]+)['\"]", content)
            out.append({
                "file": os.path.relpath(f, FRONTEND_DIR),
                "describes": describes,
            })
        except OSError:
            continue
    return out


def read_example_test() -> str:
    """Pick the longest existing test file as a style reference."""
    files = sorted(glob.glob(f"{TESTS_DIR}/*.spec.ts"))
    if not files:
        return ""
    largest = max(files, key=lambda f: os.path.getsize(f))
    with open(largest) as fp:
        return f"# Exemple de style (depuis {os.path.relpath(largest, FRONTEND_DIR)})\n```typescript\n{fp.read()}\n```"


def ask_claude(diff: str, changed_files: list[str], existing_tests: list[dict], example: str) -> dict:
    existing_summary = "\n".join(
        f"- `{t['file']}` : {', '.join(t['describes']) or '(pas de describes)'}"
        for t in existing_tests
    )
    files_list = "\n".join(f"- `{f}`" for f in changed_files) or "(aucun fichier source frontend modifié)"

    prompt = (
        f"Tu es un agent qui décide si un commit mérite de nouveaux tests Playwright e2e, et qui les écrit si oui.\n\n"
        f"**Commit :** `{COMMIT_SHA[:8]}` — {COMMIT_MESSAGE[:200]}\n\n"
        f"**Fichiers source frontend modifiés :**\n{files_list}\n\n"
        f"**Tests Playwright déjà existants :**\n{existing_summary}\n\n"
        f"**Diff du commit (tronqué si nécessaire) :**\n```diff\n{diff}\n```\n\n"
        f"{example}\n\n"
        f"**Règles :**\n"
        f"- Si le commit ajoute UNE page (ex: `app/wishlist/page.tsx`), un composant interactif visible, ou une route, génère UN fichier .spec.ts pour cette page/feature.\n"
        f"- Si le commit est un refactor, un fix de test, du CSS, du CI/CD, de la doc → needs_tests=false.\n"
        f"- Si une feature similaire est déjà couverte → needs_tests=false.\n"
        f"- Les nouveaux tests DOIVENT suivre EXACTEMENT le style de l'exemple : imports, baseURL implicite, locators robustes (getByRole, getByText), pas de sleep/waitForTimeout arbitraires.\n"
        f"- Le mock Strapi tourne sur localhost:1999 et expose les produits mock (slug 'macbook-pro-14' notamment).\n"
        f"- Pour les features purement client (ex: Wishlist persistée dans localStorage), pré-remplir localStorage via addInitScript comme dans cart.spec.ts."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[TEST_GEN_TOOL],
        tool_choice={"type": "tool", "name": "decide_and_generate_tests"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    return tool_block.input


def create_tests_pr(tests: list[dict], reasoning: str) -> str | None:
    if not GH_TOKEN:
        print("  ℹ️  GH_TOKEN not set — skipping PR")
        return None

    slug_seed = tests[0]["file_path"].replace("tests/", "").replace(".spec.ts", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug_seed.lower()).strip("-")[:35]
    branch = f"tests/auto-{COMMIT_SHA[:8]}-{slug}"

    subprocess.run(["git", "config", "user.email", "ci-bot@shopgeneric.dev"], check=False)
    subprocess.run(["git", "config", "user.name", "ShopGeneric CI Bot"], check=False)

    res = subprocess.run(["git", "checkout", "-b", branch], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ⚠️  Branch creation failed: {res.stderr[:200]}")
        return None

    created_paths = []
    for t in tests:
        full_path = os.path.join(FRONTEND_DIR, t["file_path"])
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(t["content"])
        created_paths.append(full_path)
        subprocess.run(["git", "add", full_path], check=False)

    file_summary = "\n".join(f"- `{t['file_path']}` — {t['what_it_tests']}" for t in tests)
    cp = subprocess.run(
        ["git", "commit", "-m",
         f"test(auto): generated tests for commit {COMMIT_SHA[:8]}\n\n{reasoning}\n\nFiles:\n{file_summary}"],
        capture_output=True, text=True,
    )
    if cp.returncode != 0:
        print(f"  ⚠️  Commit failed: {cp.stderr[:200] or cp.stdout[:200]}")
        return None

    remote = f"https://x-access-token:{GH_TOKEN}@github.com/{GITHUB_REPO}.git"
    push = subprocess.run(["git", "push", remote, branch], capture_output=True, text=True)
    if push.returncode != 0:
        print(f"  ⚠️  Push failed: {push.stderr[:300]}")
        return None

    pr_body = (
        f"## 🧪 Tests générés automatiquement par Claude\n\n"
        f"**Commit déclencheur :** `{COMMIT_SHA[:8]}` — {COMMIT_MESSAGE[:200]}\n\n"
        f"### Analyse\n\n{reasoning}\n\n"
        f"### Fichiers créés\n\n{file_summary}\n\n"
        f"---\n*Généré automatiquement — relire les assertions avant de merger.*"
    )

    pr_res = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/pulls",
        json={
            "title": f"🧪 Auto-tests: {tests[0]['file_path'].replace('tests/', '').replace('.spec.ts', '')}",
            "body": pr_body, "head": branch, "base": "main",
        },
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
    diff = get_commit_diff()
    if not diff.strip():
        print("ℹ️  Pas de changement dans les fichiers source frontend — rien à analyser.")
        sys.exit(0)

    changed_files = get_changed_source_files()
    existing = list_existing_tests()
    example = read_example_test()

    print(f"📝 Commit: {COMMIT_SHA[:8]} — {COMMIT_MESSAGE[:80]}")
    print(f"📂 {len(changed_files)} fichier(s) source modifié(s), {len(existing)} test(s) existant(s)")
    print("🤖 Demande à Claude si des tests sont pertinents…")

    decision = ask_claude(diff, changed_files, existing, example)

    print(f"\n→ Décision : needs_tests={decision['needs_tests']}")
    print(f"→ Raison : {decision['reasoning']}")

    if not decision["needs_tests"] or not decision["tests_to_create"]:
        print("\n✅ Aucun nouveau test nécessaire.")
        sys.exit(0)

    print(f"\n🧪 {len(decision['tests_to_create'])} fichier(s) de test à créer :")
    for t in decision["tests_to_create"]:
        print(f"  - {t['file_path']} : {t['what_it_tests']}")

    print("\n🔧 Création de la branche + PR…")
    pr_url = create_tests_pr(decision["tests_to_create"], decision["reasoning"])
    if pr_url:
        print(f"\n🎉 Done : {pr_url}")
    else:
        print("\n⚠️  PR non créée — voir les erreurs ci-dessus.")


if __name__ == "__main__":
    main()
