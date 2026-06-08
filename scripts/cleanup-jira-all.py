#!/usr/bin/env python3
import os, requests, sys

JIRA_BASE_URL  = "https://stephaneguren.atlassian.net"
JIRA_EMAIL     = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]

auth    = (JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json"}

KEYS = [
    "SCRUM-2","SCRUM-3","SCRUM-4","SCRUM-5","SCRUM-6","SCRUM-7","SCRUM-8",
    "SCRUM-9","SCRUM-10","SCRUM-11","SCRUM-12","SCRUM-13","SCRUM-14","SCRUM-15",
    "SCRUM-16","SCRUM-17","SCRUM-18","SCRUM-19","SCRUM-20","SCRUM-21","SCRUM-22",
    "SCRUM-23","SCRUM-24","SCRUM-25","SCRUM-26","SCRUM-27","SCRUM-28","SCRUM-29",
    "SCRUM-30","SCRUM-31","SCRUM-32","SCRUM-33","SCRUM-34","SCRUM-35","SCRUM-36",
    "SCRUM-37","SCRUM-38","SCRUM-39","SCRUM-40","SCRUM-41","SCRUM-42","SCRUM-44",
    "SCRUM-45","SCRUM-46","SCRUM-47","SCRUM-48","SCRUM-49","SCRUM-50","SCRUM-51",
    "SCRUM-52","SCRUM-53","SCRUM-54","SCRUM-55","SCRUM-56","SCRUM-57","SCRUM-58",
    "SCRUM-59","SCRUM-60","SCRUM-61","SCRUM-62","SCRUM-63","SCRUM-64","SCRUM-65",
    "SCRUM-66","SCRUM-67","SCRUM-68","SCRUM-69",
]

print(f"Deleting {len(KEYS)} issues...")
deleted, failed = 0, []

for key in KEYS:
    res = requests.delete(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{key}",
        auth=auth, headers=headers, timeout=20
    )
    if res.status_code == 204:
        print(f"  Deleted {key}")
        deleted += 1
    elif res.status_code == 404:
        print(f"  Already gone: {key}")
        deleted += 1
    else:
        print(f"  FAILED {key}: {res.status_code} {res.text[:200]}")
        failed.append(key)

print(f"\nDone. Deleted {deleted}/{len(KEYS)}.")
if failed:
    print(f"Failed: {', '.join(failed)}")
    sys.exit(1)