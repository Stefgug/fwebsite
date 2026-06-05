# AI Test Workflow PoC (Epic-driven + visual)

This PoC implements a full automated test flow from a Jira epic context, with visual outputs.

## What is implemented

- Unit tests + coverage gate in CI (`>=50%` lines)
- Playwright end-to-end tests
- AI triage that summarizes:
  - failing tests + root causes
  - missing test areas (low coverage)
  - suggested code fixes / PR plan
- **Visual dashboard** artifact (`dashboard.html`) for easy review (not only logs)
- Optional auto-PR with AI triage markdown when gate fails

## Workflows

### 1) Unit coverage workflow
- `.github/workflows/4-unit-tests-coverage.yml`

### 2) Epic automated workflow (main PoC)
- `.github/workflows/5-epic-automated-test-workflow.yml`

Triggers:
- `workflow_dispatch` (manual)
- `repository_dispatch` with event type: `jira-epic-test-workflow`

## Visual outputs in GitHub Actions

Artifacts produced by workflow 5:

1. `ai-test-workflow-dashboard`
   - `automation-reports/dashboard.html` (**main visual output**)
   - `automation-reports/ai-triage-report.md`
   - `automation-reports/workflow-summary.json`
2. `playwright-report`
   - native Playwright HTML report
3. `unit-coverage`
   - HTML coverage details

## GitHub secrets required

- `ANTHROPIC_API_KEY` (optional: richer AI narrative)
  - if missing, deterministic fallback triage is used.

No extra GitHub token setup is required inside workflow runs (uses built-in `secrets.GITHUB_TOKEN`).

---

## Step-by-step: trigger from Jira and visualize full workflow

## A) One-time setup in Jira

1. Go to **Jira Project Settings → Automation**
2. Click **Create rule**
3. Choose trigger (recommended):
   - **Issue transitioned** (e.g. Epic moved to "Ready for QA"), or
   - **Manual trigger** (for controlled PoC demo)
4. Add condition:
   - `Issue Type = Epic`
5. Add action: **Send web request**

Use this request:

- **Method**: `POST`
- **URL**: `https://api.github.com/repos/Stefgug/fwebsite/dispatches`
- **Headers**:
  - `Accept: application/vnd.github+json`
  - `Authorization: Bearer <YOUR_GITHUB_PAT>`
  - `Content-Type: application/json`
- **Body**:

```json
{
  "event_type": "jira-epic-test-workflow",
  "client_payload": {
    "jira_epic_key": "{{issue.key}}",
    "jira_epic_title": "{{issue.summary}}",
    "jira_epic_description": "{{issue.description}}"
  }
}
```

Notes:
- The PAT used in Jira must have repo access to `Stefgug/fwebsite`.
- For PoC simplicity, use a classic PAT with `repo` scope.

## B) Trigger manually from GitHub (optional fallback)

If you want to demo without Jira first:

1. GitHub repo → **Actions**
2. Open workflow: **Phase 7 — Jira Epic → Fully Automated Test Workflow**
3. Click **Run workflow**
4. Fill:
   - `jira_epic_key`
   - `jira_epic_title`
   - `jira_epic_description`
5. Run

## C) Visualize results (what to show in demo)

After run completion:

1. Open workflow run in GitHub Actions
2. Go to **Artifacts**
3. Download `ai-test-workflow-dashboard`
4. Open `dashboard.html` locally in browser

What to highlight in the dashboard:
- top status badges (unit/e2e/gate)
- coverage bars
- failing tests table (if any)
- low-coverage files table
- AI triage recommendations

Then show:
- `playwright-report` artifact for UI-level timeline/traces/screenshots
- `ai-triage-report.md` for detailed suggested corrections

## D) Optional Jira visibility loopback (next increment)

For tighter Jira visibility, add a final workflow step to post back into Jira:
- workflow URL
- gate status
- link/text summary from `ai-triage-report.md`

(Kept out of this PoC to minimize required Jira credentials in GitHub.)

---

## Gate logic

Workflow is PASS when all are true:
- unit tests pass
- e2e tests pass
- coverage lines >= 50%

If any fail, visual artifacts are still uploaded, and workflow ends as failed.
