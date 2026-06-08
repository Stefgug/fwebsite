#!/usr/bin/env python3
"""Apply an AI-proposed Playwright test (new or modification), run it once, and
post the result back to the triggering GitHub issue. NOTHING is committed.

Env:
  ISSUE_BODY        - the GitHub issue body containing a ```json {proposal} ``` block
  ISSUE_NUMBER      - issue number to comment on
  GITHUB_REPOSITORY - owner/repo
  GITHUB_TOKEN      - token with issues:write
  CI=true
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def post_comment(body: str) -> None:
    if not (ISSUE_NUMBER and GITHUB_REPOSITORY and GITHUB_TOKEN):
        print("Cannot post comment - missing GitHub env. Comment body:\n" + body)
        return
    import requests

    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{ISSUE_NUMBER}/comments",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"body": body},
        timeout=20,
    )
    print(f"Comment post: HTTP {r.status_code}")


def extract_proposal(body: str) -> dict | None:
    # Capture the full fenced block (the JSON contains inner braces, so a
    # brace-bounded pattern would stop too early). Match up to the closing fence.
    m = re.search(r"```json\s*(.*?)\s*```", body, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1).strip())
    except Exception:
        return None


def _replace_test_by_name(content: str, name: str, replacement: str) -> str | None:
    if not name:
        return None
    idx = content.find(f"test('{name}'")
    if idx == -1:
        idx = content.find(f'test("{name}"')
    if idx == -1:
        return None
    paren_start = content.find("(", idx)
    depth = 0
    i = paren_start
    while i < len(content):
        c = content[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(content) and content[end] == ";":
                    end += 1
                return content[:idx] + replacement + content[end:]
        i += 1
    return None


def _normalize_target(target: str) -> str | None:
    """Accept 'auth.spec.ts', 'tests/auth.spec.ts' or 'frontend/tests/auth.spec.ts'
    and return the canonical repo path. Reject anything unsafe or non-spec."""
    t = (target or "").strip().replace("\\", "/")
    if not t or ".." in t:
        return None
    base = t.rsplit("/", 1)[-1]
    if not base.endswith(".spec.ts"):
        return None
    return f"frontend/tests/{base}"


def apply_proposal(p: dict) -> tuple[bool, str]:
    target = _normalize_target(p.get("target_file"))
    if not target:
        return False, f"Invalid target_file: {p.get('target_file')!r}"
    path = ROOT / target
    if not path.exists():
        return False, f"Target file not found: {target}"
    content = path.read_text(encoding="utf-8")
    kind = p.get("kind")
    proposed = (p.get("proposed_code") or "").strip()
    if not proposed:
        return False, "Empty proposed_code"

    if kind == "modify_test":
        existing = (p.get("existing_code") or "").strip()
        if existing and existing in content:
            content = content.replace(existing, proposed, 1)
        else:
            new_content = _replace_test_by_name(content, p.get("test_name", ""), proposed)
            if new_content is None:
                return False, "Could not locate the existing test to modify (anchor not found)."
            content = new_content
    else:  # new_test
        block = proposed
        if "from '@playwright/test'" in content:
            block = re.sub(
                r"^\s*import\s+\{[^}]*\}\s+from\s+['\"]@playwright/test['\"];?\s*\n",
                "",
                block,
                count=1,
            )
        content = content.rstrip() + "\n\n" + block.strip() + "\n"

    path.write_text(content, encoding="utf-8")
    return True, target


def run_test(target: str, test_name: str) -> tuple[bool, str]:
    pattern = re.escape(test_name)
    spec_rel = target[len("frontend/"):]  # tests/xxx.spec.ts
    cmd = ["npx", "playwright", "test", spec_rel, "-g", pattern]
    env = {**os.environ, "CI": "true", "NEXT_PUBLIC_STRAPI_URL": "http://localhost:1999"}
    try:
        proc = subprocess.run(
            cmd, cwd=str(FRONTEND), capture_output=True, text=True, env=env, timeout=600
        )
    except subprocess.TimeoutExpired:
        return False, "Test run timed out after 600s."
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, output[-4000:]


def main() -> None:
    proposal = extract_proposal(ISSUE_BODY)
    if not proposal:
        post_comment("Could not find a valid proposal JSON block in this issue. Nothing to run.")
        return

    test_name = proposal.get("test_name", "(unnamed test)")
    kind = proposal.get("kind", "?")

    ok_apply, info = apply_proposal(proposal)
    if not ok_apply:
        post_comment(f"**Could not apply the proposed change.**\n\n{info}")
        return

    # apply_proposal returns the canonical path in `info` on success
    passed, output = run_test(info, test_name)
    proposed_code = proposal.get("proposed_code", "")

    status = "PASSED" if passed else "FAILED"
    kind_label = "modification to" if kind == "modify_test" else "new test in"
    next_step = (
        "Since it passed, you can now open a pull request to add it to the suite permanently."
        if passed
        else "It did not pass, so review the proposal before adding it."
    )
    comment = f"""## Proposed test - validation run

**Result: {status}**

**Applied:** {kind_label} `{proposal.get('target_file')}`
**Test:** `{test_name}`

<details><summary>Test code that was run</summary>

```ts
{proposed_code}
```
</details>

<details><summary>Playwright output</summary>

```
{output.strip()}
```
</details>

---
This was a **one-time validation run** on a throwaway checkout - the change was **not committed**. {next_step}
"""
    post_comment(comment)
    print("Done.")


if __name__ == "__main__":
    main()
