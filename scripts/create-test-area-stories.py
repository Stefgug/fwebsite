#!/usr/bin/env python3
"""
create-test-area-stories.py

Creates one Jira Story per Playwright spec file as a child of the current Epic.
Run once per pipeline execution.
"""

import os
import re
import sys
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
JIRA_BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]
JIRA_EPIC_KEY = os.environ["JIRA_EPIC_KEY"]

AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

# Root of the repo = parent of the scripts/ directory (where this script lives)
ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Spec file definitions
# ---------------------------------------------------------------------------
SPEC_FILES = [
    {
        "path": "frontend/tests/home.spec.ts",
        "area": "Home Page",
        "coverage": "Covers the home page layout including the hero section, navigation CTAs, feature badges, category shortcuts, product and blog sections, and page metadata.",
    },
    {
        "path": "frontend/tests/navigation.spec.ts",
        "area": "Navigation",
        "coverage": "Covers site-wide navigation including the logo, navbar links, cart icon, login visibility, and the 404 not-found page.",
    },
    {
        "path": "frontend/tests/products.spec.ts",
        "area": "Products",
        "coverage": "Covers the product listing page including the category sidebar, product cards, category filtering, navigation to product detail pages, and the Add to Cart button.",
    },
    {
        "path": "frontend/tests/cart.spec.ts",
        "area": "Shopping Cart",
        "coverage": "Covers shopping cart behaviour including the empty cart state, adding products, cart item count badge, and the Checkout button.",
    },
    {
        "path": "frontend/tests/auth.spec.ts",
        "area": "Authentication",
        "coverage": "Covers the login and registration flows including form fields, validation errors, successful login redirect, and links between auth pages.",
    },
    {
        "path": "frontend/tests/about.spec.ts",
        "area": "About Page",
        "coverage": "Covers the About page including the hero section, stats, value cards, CTA heading, and internal navigation links.",
    },
]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_tests(source: str) -> list[str]:
    """
    Extract test names from a Playwright spec file.

    Handles:
      test('name', ...)
      test("name", ...)
      test.describe('name', ...) — used as prefix for nested tests
    """
    names: list[str] = []

    # Find all describe blocks and their content to associate describe labels
    # with their nested test() calls.
    # Strategy: walk through the file and track describe/test nesting.

    # Regex patterns
    describe_re = re.compile(
        r"""test\.describe\s*\(\s*(['"`])(.*?)\1""",
        re.DOTALL,
    )
    test_re = re.compile(
        r"""(?<!\w)test\s*\(\s*(['"`])(.*?)\1""",
        re.DOTALL,
    )

    # Simple line-based approach: collect (position, kind, name)
    events: list[tuple[int, str, str]] = []

    for m in describe_re.finditer(source):
        events.append((m.start(), "describe", m.group(2).strip()))

    for m in test_re.finditer(source):
        # Skip test.describe itself (already captured above)
        prefix_end = m.start()
        # Make sure this is not part of test.describe
        preceding = source[max(0, prefix_end - 1): prefix_end + 20]
        if ".describe" in source[max(0, prefix_end - 5): prefix_end + 5]:
            continue
        events.append((m.start(), "test", m.group(2).strip()))

    events.sort(key=lambda x: x[0])

    # Build names: find which describe block (if any) each test lives inside.
    # We find the nearest describe before each test.
    describe_positions = [e for e in events if e[1] == "describe"]

    for pos, kind, name in events:
        if kind != "test":
            continue
        # Find the last describe that started before this test
        enclosing = [d for d in describe_positions if d[0] < pos]
        if enclosing:
            describe_name = enclosing[-1][2]
            names.append(f"{describe_name} > {name}")
        else:
            names.append(name)

    return names


# ---------------------------------------------------------------------------
# ADF builder
# ---------------------------------------------------------------------------

def build_adf(coverage_sentence: str, test_names: list[str], github_url: str = "") -> dict:
    bullet_items = [
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": name}],
                }
            ],
        }
        for name in test_names
    ]

    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": coverage_sentence}],
            },
            {
                "type": "bulletList",
                "content": bullet_items,
            },
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Automated by Playwright — results visible in the QA report after each pipeline run.",
                    }
                ],
            },
            *(
                [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "📂 View test file on GitHub",
                                "marks": [{"type": "link", "attrs": {"href": github_url}}],
                            }
                        ],
                    }
                ]
                if github_url
                else []
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Jira API
# ---------------------------------------------------------------------------

def create_story(area: str, coverage: str, test_names: list[str], github_url: str = "") -> str | None:
    """
    POST a Jira Story.  Returns the issue key on success, None on failure.
    """
    summary = f"🧪 Test Area: {area}"
    description = build_adf(coverage, test_names, github_url=github_url)

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "issuetype": {"name": "Story"},
            "parent": {"key": JIRA_EPIC_KEY},
            "labels": ["automated-test"],
            "description": description,
        }
    }

    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    response = requests.post(url, json=payload, auth=AUTH, headers=HEADERS, timeout=30)

    if response.status_code in (200, 201):
        data = response.json()
        return data.get("key", "UNKNOWN")
    else:
        print(
            f"  ERROR creating '{summary}': "
            f"HTTP {response.status_code} — {response.text[:300]}"
        )
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    created = 0
    total = len(SPEC_FILES)

    for spec in SPEC_FILES:
        spec_path = ROOT / spec["path"]
        area = spec["area"]

        # Read spec file
        try:
            source = spec_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"  WARNING: spec file not found: {spec_path} — skipping")
            continue
        except OSError as exc:
            print(f"  WARNING: could not read {spec_path}: {exc} — skipping")
            continue

        # Parse test names
        test_names = parse_tests(source)
        if not test_names:
            print(f"  WARNING: no test names found in {spec['path']} — will create story with empty list")

        # Create story
        gh_url = f"https://github.com/Stefgug/fwebsite/blob/main/{spec['path']}"
        key = create_story(area, spec["coverage"], test_names, github_url=gh_url)
        if key:
            print(f"Created: {key} — Test Area: {area}")
            created += 1

    print(f"\nDone. Created {created}/{total} test area stories.")


if __name__ == "__main__":
    main()
