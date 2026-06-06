#!/usr/bin/env python3
"""
Crée un Epic Jira avec des tickets enfants pour la démo PoC,
puis déclenche le workflow de test automatisé.
"""
from __future__ import annotations

import json
import os
import sys
import time
import requests

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://stephaneguren.atlassian.net")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")

GH_TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", os.environ.get("GITHUB_REPO", "Stefgug/fwebsite"))

HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)


def jira(method: str, path: str, body: dict | None = None) -> dict:
    res = requests.request(
        method, f"{JIRA_BASE_URL}/rest/api/3{path}",
        json=body, auth=AUTH, headers=HEADERS, timeout=20,
    )
    if not res.ok:
        print(f"  ⚠️ {method} {path} → {res.status_code}: {res.text[:300]}")
        res.raise_for_status()
    return res.json() if res.text else {}


def get_issuetype_id(name: str) -> str:
    """Find the ID of an issue type by name (e.g. 'Epic', 'Tâche')."""
    data = jira("GET", "/issuetype")
    for it in data:
        if it.get("name", "").lower() == name.lower() or it.get("untranslatedName", "").lower() == name.lower():
            return it["id"]
    raise SystemExit(f"Issue type '{name}' not found. Available: {[i['name'] for i in data]}")


def get_epic_type_name() -> str:
    """In Jira Cloud, the Epic issue type may be localized.
    Returns the first match for 'Epic' (English) or 'Épopée' (French)."""
    data = jira("GET", "/issuetype")
    for it in data:
        if it.get("name") in ("Epic", "Épopée"):
            return it["name"]
    # fallback — try API by untranslated name
    for it in data:
        if it.get("untranslatedName") == "Epic":
            return it["name"]
    raise SystemExit(f"No Epic issue type found. Available: {[i['name'] for i in data]}")


def create_issue(summary: str, description: str, issuetype: str,
                 epic_key: str | None = None) -> str:
    fields: dict = {
        "project": {"key": JIRA_PROJECT_KEY},
        "issuetype": {"name": issuetype},
        "summary": summary,
        "description": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
        },
    }
    if epic_key:
        fields["parent"] = {"key": epic_key}

    data = jira("POST", "/issue", {"fields": fields})
    return data["key"]


def transition_issue(issue_key: str, target_status: str) -> None:
    """Transition an issue to a target status."""
    transitions = jira("GET", f"/issue/{issue_key}/transitions")
    tid = None
    for t in transitions.get("transitions", []):
        if t.get("name", "").lower() == target_status.lower() or t.get("to", {}).get("name", "").lower() == target_status.lower():
            tid = t["id"]
            break
    if not tid:
        print(f"  ℹ️  No transition to '{target_status}' found for {issue_key} — skipping")
        return
    jira("POST", f"/issue/{issue_key}/transitions", {"transition": {"id": tid}})


def trigger_test_workflow(epic_key: str, epic_title: str, epic_description: str) -> str | None:
    """Dispatch the epic test workflow via GitHub API (workflow_dispatch)."""
    if not GH_TOKEN:
        print("  ⚠️  GH_TOKEN not set — cannot trigger workflow")
        return None

    res = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/5-epic-automated-test-workflow.yml/dispatches",
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
        json={
            "ref": "main",
            "inputs": {
                "jira_epic_key": epic_key,
                "jira_epic_title": epic_title,
                "jira_epic_description": epic_description,
            },
        },
        timeout=20,
    )
    if res.status_code == 204:
        # Give GitHub a moment to register the run
        time.sleep(3)
        runs = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/5-epic-automated-test-workflow.yml/runs?per_page=1&event=workflow_dispatch",
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"},
            timeout=15,
        )
        if runs.ok:
            wf_runs = runs.json().get("workflow_runs", [])
            if wf_runs:
                return wf_runs[0].get("html_url")
        return "(run queued — check Actions tab)"
    else:
        print(f"  ⚠️  Dispatch failed ({res.status_code}): {res.text[:300]}")
        return None


def main():
    epic_type = get_epic_type_name()
    print(f"Epic issue type: '{epic_type}'")

    # ── Epic ──
    print("\n📌 Creating Epic...")
    epic_key = create_issue(
        summary="[PoC] Automatisation complète des tests - Site e-commerce ShopGeneric",
        description=(
            "Cet Epic pilote la démonstration de la boucle complète d'automatisation des tests :\n"
            "- déclenchement depuis Jira\n"
            "- exécution des tests unitaires avec couverture\n"
            "- exécution des tests E2E Playwright\n"
            "- analyse IA des échecs et des tests manquants\n"
            "- dashboard visuel HTML\n"
            "- PR automatique avec suggestions de correction"
        ),
        issuetype=epic_type,
    )
    print(f"  ✅ Epic: {epic_key}")

    # ── Child tickets ──
    children = [
        (
            "Test unitaire — couverture du store cartStore",
            "Ajouter des tests unitaires Vitest pour le Zustand store cartStore.\n"
            "Vérifier addItem, removeItem, updateQuantity, clearCart, totalItems, totalPrice.\n"
            "Seuil : >= 50% de couverture lignes.",
        ),
        (
            "Test unitaire — couverture du store wishlistStore",
            "Ajouter des tests unitaires Vitest pour le Zustand store wishlistStore.\n"
            "Vérifier addItem, removeItem, toggleItem, clearWishlist, hasItem, totalItems.\n"
            "Seuil : >= 50% de couverture lignes.",
        ),
        (
            "Test unitaire — fonctions utilitaires (utils.ts)",
            "Ajouter des tests unitaires Vitest pour formatPrice, cn, truncate dans lib/utils.ts.\n"
            "Edge cases : prix nul, classes vides, texte exact à la limite de longueur.",
        ),
        (
            "Test unitaire — helpers Strapi (strapi.ts)",
            "Ajouter des tests unitaires pour getProducts, strapiLogin, strapiRegister, getStrapiImageUrl.\n"
            "Mocker fetch pour simuler les réponses API Strapi.\n"
            "Vérifier la construction des query params et la gestion des erreurs.",
        ),
        (
            "Test E2E Playwright — page About",
            "Ajouter des tests E2E Playwright pour la page About :\n"
            "- titre, heading hero, description\n"
            "- stats affichées\n"
            "- section valeurs, CTA\n"
            "- liens Browse Products et Contact Us",
        ),
        (
            "Test E2E Playwright — flux de wishlist",
            "Ajouter des tests E2E Playwright pour la wishlist :\n"
            "- ajout d'un produit depuis la page détail\n"
            "- visualisation de la wishlist\n"
            "- suppression d'un produit\n"
            "- persistance localStorage",
        ),
        (
            "Analyser les résultats et générer le dashboard visuel",
            "Exécuter le workflow complet epic-test-orchestrator :\n"
            "- lancer les tests unitaires + coverage\n"
            "- lancer les tests E2E Playwright\n"
            "- générer le dashboard HTML + rapport IA\n"
            "- uploader les artifacts visuels\n"
            "- créer une PR automatique si le gate échoue",
        ),
    ]

    child_keys = []
    task_type = "Tâche"

    for i, (summary, desc) in enumerate(children, 1):
        print(f"\n📝 Creating child {i}/{len(children)}: {summary[:60]}...")
        key = create_issue(summary, desc, task_type, epic_key=epic_key)
        child_keys.append(key)
        print(f"  ✅ {key}")

    # ── Move Epic to "In Progress" if possible ──
    print(f"\n🔄 Transitioning Epic {epic_key}...")
    try:
        transition_issue(epic_key, "In Progress")
    except Exception:
        pass  # may not have that transition on the board

    # ── Trigger test workflow ──
    print(f"\n🚀 Triggering full test workflow for {epic_key}...")
    wf_url = trigger_test_workflow(
        epic_key,
        f"[PoC] Automatisation complète des tests - Site e-commerce ShopGeneric",
        json.dumps(children[6][1])[:500],
    )

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"🎯 Epic: {JIRA_BASE_URL}/browse/{epic_key}")
    print(f"   {len(child_keys)} child issues created:")
    for ck in child_keys:
        print(f"   - {ck}")
    if wf_url:
        print(f"\n🔗 Test workflow: {wf_url}")

    # GitHub Actions step summary
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a", encoding="utf-8") as f:
            f.write("## 🎯 Démo PoC — Epic & tickets créés\n")
            f.write(f"- **Epic:** [{epic_key}]({JIRA_BASE_URL}/browse/{epic_key})\n")
            f.write(f"- **Projet:** {JIRA_PROJECT_KEY}\n\n")
            f.write("### Tickets enfants\n")
            for ck in child_keys:
                f.write(f"- [{ck}]({JIRA_BASE_URL}/browse/{ck})\n")
            if wf_url:
                f.write(f"\n### 🧪 Workflow de test déclenché\n{wf_url}")
            else:
                f.write("\n⚠️ Workflow de test non déclenché (ref: main, vérifier le merge).")


if __name__ == "__main__":
    main()
