# AI-Augmented QA Pipeline — Live Demo Guide

## 1. Overview

This is a live demonstration of an **AI-augmented QA pipeline** built on top of a real e-commerce demo site (Next.js 15 + Strapi 5).

**What this pipeline does:**

> From a single Jira Epic, this pipeline automatically generates structured Jira tickets from acceptance criteria, runs E2E + unit tests, produces a visual report with plain-English failure explanations, surfaces blind spots in test coverage, and proposes new tests for human review — all with zero clicks after the Epic is created.

**Audience:** QA leads who are non-technical on code. Everything they see is **visual and functional** — no stack traces, no source code in the report.

- **Repo:** `Stefgug/fwebsite` (branch `main`)
- **Jira:** https://stephaneguren.atlassian.net — project **SCRUM** (team-managed)
- **Live report:** https://stefgug.github.io/fwebsite/

---

## 2. Architecture — the end-to-end chain

```
   [1] QA lead creates an EPIC in Jira (with clear acceptance criteria)
                          |
                          v
   [2] Jira Automation rule fires  -- repository_dispatch -->  GitHub
        (event_type: jira-epic-created, body uses .jsonEncode)
                          |
                          v
   [3] GitHub Actions: .github/workflows/epic-test-pipeline.yml
        a. create-tickets-from-epic.py    -> 5-7 functional Story tickets (deduped)
        b. create-test-area-stories.py    -> one "Test Area" Story per spec file (deduped)
        c. Vitest unit tests (+coverage) + Playwright E2E tests
        d. ai-full-test-workflow.py       -> AI QA report (dashboard + catalog)
             - auto-creates a Jira Bug per failing test
             - draws RED BOXES on failure screenshots (Claude vision + Pillow)
             - proposes high-value new/updated tests
        e. publish to GitHub Pages + upload artifacts
                          |
                          v
   [4] Report URL posted as a comment on the Jira Epic
                          |
                          v
   [On click] "Accept & run" a proposed test
        -> .github/workflows/run-proposed-test.yml runs ONLY that test
           in a throwaway checkout and comments PASS/FAIL back on the issue
           (nothing is committed automatically)
```

The whole flow is **zero-click after the Epic is created** — except the deliberate, human-in-the-loop step of accepting a proposed test.

---

## 3. One-time setup

These are configured once and are already in place in the repo. Verify before a demo.

### 3.1 GitHub secrets

Repository → **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude (model `claude-sonnet-4-6`) — used for story generation, AI triage, vision analysis, and test proposals. If missing, the pipeline falls back to deterministic triage so the demo never hard-fails. |
| `JIRA_EMAIL` | Atlassian account email for Jira API auth. |
| `JIRA_API_TOKEN` | Generate at https://id.atlassian.com → Security → API tokens. |
| `GITHUB_TOKEN` | Auto-provided by GitHub Actions — no manual setup. |

Jira base URL: `https://stephaneguren.atlassian.net` — project key **SCRUM**.

### 3.2 The Jira Automation rule

This is the bridge that triggers the GitHub pipeline when an Epic is created.

1. In the **SCRUM project**, go to **Project settings → Automation → Create rule**.
2. **Trigger:** Issue created. **Condition:** Issue Type = Epic.
3. **Action:** Send web request.
   - **Webhook URL:** `https://api.github.com/repos/Stefgug/fwebsite/dispatches`
   - **Method:** POST
   - **Headers:**
     - `Authorization: Bearer YOUR_GITHUB_PAT`
     - `Content-Type: application/json`
     - `Accept: application/vnd.github+json`
   - **HTTP body:**
     ```json
     {
       "event_type": "jira-epic-created",
       "client_payload": {
         "jira_epic_key": "{{issue.key}}",
         "jira_epic_title": "{{issue.summary.jsonEncode}}",
         "jira_epic_description": "{{issue.description.jsonEncode}}"
       }
     }
     ```
   - **CRITICAL:** the smart values **must** use `.jsonEncode`. A rich Epic description contains quotes and newlines that otherwise break the JSON and the request fails with **HTTP 400**. `.jsonEncode` escapes them safely.
4. **YOUR_GITHUB_PAT** is a GitHub Personal Access Token with `repo` + `actions:write` scopes (https://github.com/settings/tokens).
5. Save and enable the rule.

**Verify:** create a test Epic — a run should appear in GitHub Actions within ~30 seconds.

### 3.3 The `run-proposed-test` label

The "Accept & run" feature opens a GitHub Issue carrying the label **`run-proposed-test`**, which triggers `run-proposed-test.yml`. **This label already exists in the repo** — no action needed, but if proposals never trigger, confirm the label is present.

---

## 4. Writing a good Epic (this drives test quality)

The richer and clearer the **acceptance criteria** in the Epic description, the sharper and more business-relevant the generated tests. Vague stories produce vague tests; explicit, bulleted acceptance criteria produce high-value E2E tests tied to real user journeys.

Write the Epic description with a short business goal followed by **bulleted acceptance criteria**.

**Example Epic — "Secure User Authentication & Checkout Access"**

> **Goal:** Customers must be able to register, sign in, and only reach checkout when authenticated, so that orders are always tied to a real account.
>
> **Acceptance criteria:**
> - A visitor can create an account with email + password and is signed in afterward.
> - A registered user can sign in with valid credentials and is greeted by name.
> - Invalid credentials show a clear error and do **not** sign the user in.
> - An unauthenticated user who tries to reach `/checkout` is redirected to sign-in.
> - After signing in, the user is returned to checkout and can complete the order.
> - Signing out clears the session and protected pages are no longer reachable.
> - The cart contents persist across sign-in (cart is not lost on login).

Notice each bullet is a **user journey with a verifiable outcome** — that is exactly what produces high-value E2E tests instead of micro-tests.

---

## 5. The live demo script

### Pre-demo prep (before the call)
- Run a **Demo reset** (section 7) so Jira is clean.
- Confirm the **deliberate regression** is in place (section 5, Step 6 note).
- Open tabs: Jira SCRUM backlog · GitHub Actions (filter `Epic Test Pipeline`) · the live report https://stefgug.github.io/fwebsite/.

### Step 1 — Create the Epic live
In Jira SCRUM, click **Create → Epic**. Title it **"Secure User Authentication & Checkout Access"** and paste the acceptance-criteria description from section 4. Click **Create**.

> "The quality of what comes out is driven by clear acceptance criteria — the tests map directly to the acceptance criteria you wrote, giving you business-level coverage tied to real user journeys."

### Step 2 — Tickets appear in Jira
Within ~30s the pipeline starts. Refresh the Epic — child **Story** tickets appear:
- 5–7 functional **coverage Stories** generated by Claude from the Epic.
- One **"🧪 Test Area: …"** Story per Playwright spec file (Homepage, Navigation, Product Catalog, Shopping Cart, Authentication, About), each listing its test names and a **"📂 View test file on GitHub"** link.

Both creators are **deduped** — re-triggering the same Epic won't create duplicates.

> "Every test maps to a named business area and a real file — full traceability from Epic acceptance criteria all the way to the test code."

### Step 3 — Pipeline runs
In GitHub Actions, open the running **Epic Test Pipeline**. Narrate the steps: create tickets → create test-area stories → unit tests (Vitest + coverage) → Playwright E2E → AI triage + report → publish to Pages.

### Step 4 — Open the Dashboard
Open https://stefgug.github.io/fwebsite/ and walk through:
- **Header** — the Epic key is **hyperlinked straight to Jira**.
- **AI summary banner** — overall test health in plain English.
- **Unit + E2E status cards** — the **E2E badge reflects real pass/fail counts**, not just the CI step outcome.
- **"Failing Tests — Functional Impact"** table — for each failure: the test name, a **plain-English functional impact**, and a **recommended QA action**. No stack traces, no code.

> "This tells you **what the customer can't do** and **what you should do about it** — in plain English, without needing to read a stack trace."

### Step 5 — Visual Evidence (the standout feature)
Scroll to **"Visual Evidence."** For each failing test, Playwright captured a screenshot at the moment of failure. Claude **vision** analyzes the screenshot plus the functional impact, returns the coordinates of the problem area, and the pipeline draws a **RED BOX with a short label** on the page image (using Pillow).

> "The QA lead literally **sees the broken page with the problem circled.**"

**Caveat to mention honestly:** for a *missing* element, the box marks **where it should be** — without a visual baseline it indicates the area, not a pixel-diff. If vision or Pillow is unavailable, the plain screenshot still shows.

### Step 6 — The auto-created Jira Bug
For each failing test the pipeline **automatically creates a Jira Bug** (child of the Epic), pre-filled with Claude's functional impact + suggested QA action, labeled `automated-bug` / `playwright`. (If the project has no "Bug" type, it falls back to "Task.")

In the **Test Catalog** (next step) the failing test shows a red **"🐛 SCRUM-XX"** link going straight to that Bug.

> "The failure doesn't just sit in a report — it's already a triaged ticket in your backlog, ready to be picked up."

**The deliberate regression behind this:** `frontend/app/cart/page.tsx` has the checkout link pointing to `/order/checkout` instead of `/checkout`. This breaks the Playwright test *"cart has a Checkout button when not empty"* **and** genuinely 404s a real user clicking "Proceed to Checkout." So the suite is catching a **real, business-relevant regression** — not a trivial one. *(Presenter: revert this after the demo.)*

### Step 7 — The Test Catalog
Click the **Test Catalog** button. Show all ~49 Playwright tests grouped into the **6 areas**, each with pass/fail badges, a **"📂 View on GitHub"** link to the spec, and an action per test.

### Step 8 — AI Test Proposals
Scroll to **"AI-Proposed Test Improvements."** After analyzing failures and blind spots, Claude proposes **high-value** improvements (never micro-tests), of two kinds:
- **🆕 New test** — fills a real coverage gap identified from a blind spot.
- **✏️ Modify existing test** — only when a failing test is genuinely **outdated**. It will **not** propose changing a test just to hide a real bug.

Every proposal is **dedup-checked** against the whole suite: Claude is given all 6 spec files and must justify the gap in a **"coverage check"** note, and a second programmatic guard drops any new test whose name already exists. Each card shows the rationale, the coverage-check note, a code preview, and an **"Accept & run this test"** button.

> "The pipeline surfaces blind spots and proposes targeted improvements — and a human stays in control of what gets added to the suite."

### Step 9 — Accept & run a proposal
Click **"Accept & run this test."** It opens a **pre-filled GitHub Issue** (already carrying the `run-proposed-test` label) whose body embeds the proposal as JSON. The `run-proposed-test.yml` workflow triggers on that label, applies the change to a **throwaway checkout**, runs **only that test**, and comments the **PASS/FAIL** result back on the issue — including the test code and Playwright output. **Nothing is committed automatically;** if it passes, the tester opens a PR to keep it.

> **Timing note:** this run does a full Next.js build first (~2–3 minutes). **Trigger it a few minutes before** you want to show the result, then cut back to it.

### Step 10 — The Epic comment
Back in Jira, the Epic now has a **comment with the report URL** — the permanent home of the report on GitHub Pages.

---

## 6. Artifacts cheat-sheet

| Artifact | Where | What it shows |
|---|---|---|
| Functional coverage Stories | Jira, under the Epic | 5–7 Claude-generated business test areas |
| "🧪 Test Area" Stories | Jira, under the Epic | one per spec file; test names + GitHub link |
| Dashboard | https://stefgug.github.io/fwebsite/ (`index.html` / `dashboard.html`) | AI summary, Unit + real E2E status, failing-test functional impact, Visual Evidence (red boxes), Blind Spots |
| Test Catalog | `catalog.html` (button on dashboard) | all ~49 tests in 6 areas, pass/fail, GitHub links, AI-Proposed Improvements |
| Auto-created Jira Bugs | Jira, under the Epic | one Bug per failing test, labeled `automated-bug`/`playwright`; linked from the catalog |
| Proposal run result | GitHub Issue comment | PASS/FAIL of the accepted test + code + Playwright output |
| Workflow artifacts | GitHub Actions run | report files + Playwright output (retained) |
| Epic comment | Jira Epic | link to the published report |

---

## 7. Demo reset (wipe Jira between runs)

To run the demo repeatedly, clear the SCRUM project:

1. GitHub → **Actions → "Jira Reset"** workflow → **Run workflow** (`workflow_dispatch`).
2. Type **`DELETE`** in the confirmation field to confirm.
3. It runs `scripts/jira-reset.py` and deletes all issues in the SCRUM project.

Also re-check the deliberate regression in `frontend/app/cart/page.tsx` (section 5, Step 6) before the next run.

---

## 8. Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Jira rule fails with **HTTP 400** | Smart values not JSON-escaped; quotes/newlines in the description break the body | Use **`.jsonEncode`** on `{{issue.summary}}` and `{{issue.description}}` (see section 3.2). |
| Workflow doesn't trigger after Epic creation | Automation rule disabled or PAT expired | Verify the rule in Jira → Project settings → Automation; regenerate the GitHub PAT (`repo` + `actions:write`). |
| Playwright reports **0 tests** | Dev server / mock backend not ready, or wrong base URL | Confirm the app started before tests; check `NEXT_PUBLIC_STRAPI_URL` and the Playwright `webServer` config. |
| Report URL shows **404** | Pages deploy not finished or cached | Wait 1–2 min for the deploy-pages job; hard-refresh (Ctrl+Shift+R). |
| No Jira **Bug** created | Project has no "Bug" issue type | Expected — the pipeline **falls back to "Task"** automatically. |
| AI sections look generic / no proposals | `ANTHROPIC_API_KEY` missing or rate-limited | Verify the secret. Triage falls back to deterministic mode so the demo still works; proposals/vision need the key. |
| **"Accept & run" didn't trigger** | Issue missing the `run-proposed-test` label | Confirm the label exists in the repo and is applied to the issue (section 3.3). |
| Proposal result slow to appear | The run does a full Next.js build (~2–3 min) | Trigger it a few minutes ahead and return to it (section 5, Step 9). |
| Stories created but no parent link | Hierarchy issue in the project | Ensure tickets are created as children of the Epic; re-check the Epic key passed in the dispatch payload. |
