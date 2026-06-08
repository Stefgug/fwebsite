#!/usr/bin/env python3
import os, requests, sys

JIRA_BASE_URL = "https://stephaneguren.atlassian.net"
JIRA_EMAIL    = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]

auth    = (JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json"}

# Fetch ALL issues in SCRUM project (paginate to be safe)
keys = []
start = 0
while True:
    r = requests.get(
        f"{JIRA_BASE_URL}/rest/api/3/search",
        auth=auth, headers=headers,
        params={"jql": "project = SCRUM ORDER BY created ASC", "maxResults": 100, "startAt": start, "fields": "summary"},
        timeout=20
    )
    r.raise_for_status()
    data = r.json()
    batch = data.get("issues", [])
    keys += [i["key"] for i in batch]
    start += len(batch)
    if start >= data.get("total", 0):
        break

print(f"Found {len(keys)} issues to delete: {', '.join(keys)}")

deleted = 0
failed  = []
for key in keys:
    res = requests.delete(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{key}",
        auth=auth, headers=headers, timeout=20
    )
    if res.status_code == 204:
        print(f"  Deleted {key}")
        deleted += 1
    else:
        print(f"  FAILED {key}: {res.status_code} {res.text[:120]}")
        failed.append(key)

print(f"\nDone. Deleted {deleted}/{len(keys)}.")
if failed:
    print(f"Failed: {', '.join(failed)}")
    sys.exit(1)