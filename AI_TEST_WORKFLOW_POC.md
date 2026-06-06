# 🎬 Démo PoC — Mode d'emploi simplifié

## En 3 clics, tu déclenches tout

### 1. Lance le workflow démo

Dans GitHub :
- Va dans **Actions** → **PoC Demo — Create Jira Epic + Trigger Test Workflow**
- Clique **Run workflow** → **Run workflow** (vert)
- (pas besoin de remplir de paramètres)

Ça crée automatiquement dans Jira :
- 1 Epic avec un scénario cohérent
- 7 tickets enfants (tests unitaires, E2E, analyse)

### 2. Le workflow de test se lance tout seul

Le script enchaîne automatiquement sur le **Phase 7 — Jira Epic → Fully Automated Test Workflow**.

Dans GitHub Actions, tu verras **2 runs** qui s'enchaînent :
1. `PoC Demo — Create Jira Epic + Trigger Test Workflow` (~30s)
2. `Phase 7 — Jira Epic → Fully Automated Test Workflow` (~5 min)

### 3. Récupère les résultats visuels

Quand le run Phase 7 est terminé :
- Ouvre le run → section **Artifacts** (en bas)
- Télécharge **`ai-test-workflow-dashboard`**
- Ouvre `dashboard.html` dans ton navigateur

Tu verras :
- Badges ✅/❌ (unit tests, E2E, gate)
- Barres de couverture (lines, functions, branches)
- Tableau des tests en échec (s'il y en a)
- Fichiers sous-couverts (<50%)
- Recommandations IA

---

## Où voir les choses dans Jira

L'Epic créé apparaît dans ton projet **SCRUM** sur https://stephaneguren.atlassian.net.

Tu y trouveras :
- L'Epic avec la description du PoC
- 7 tickets enfants détaillant chaque type de test à couvrir

---

## Résumé des workflows disponibles

| # | Workflow | Trigger | Rôle |
|---|----------|---------|------|
| 1 | `1-ai-commit-to-jira.yml` | push main | Crée un ticket Jira depuis un commit |
| 2 | `2-playwright-and-ai.yml` | push/PR main | Playwright + analyse IA si échec |
| 3 | `3-ai-generate-tests.yml` | push main | Génération auto de tests |
| 4 | `4-unit-tests-coverage.yml` | push/PR main | Tests unitaires + seuil 50% |
| 5 | `5-epic-automated-test-workflow.yml` | dispatch / Jira branch | Workflow complet piloté par Epic |
| 6 | `6-demo-create-epic-and-trigger.yml` | dispatch | Crée l'Epic + lance le workflow 5 |
| 7 | `7-cleanup-scrum43.yml` | dispatch | Nettoie l'Epic dupliqué |

---

## Si tu veux rejouer la démo

1. GitHub → Actions → **PoC Demo — Create Jira Epic + Trigger Test Workflow** → Run workflow
2. Attends que les 2 runs finissent
3. Télécharge `ai-test-workflow-dashboard`
