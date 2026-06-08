import os, sys, time
import requests

JIRA_BASE_URL  = os.environ["JIRA_BASE_URL"]
JIRA_EMAIL     = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
PROJECT_KEY    = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")

auth    = (JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

def fetch_all_keys():
    keys, start = [], 0
    while True:
        r = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/search",
            auth=auth, headers=headers,
            json={"jql": f"project = {PROJECT_KEY} ORDER BY created ASC",
                  "maxResults": 100, "startAt": start,
                  "fields": ["summary"]},
            timeout=20,
        )
        if not r.ok:
            print(f"Search failed ({r.status_code}): {r.text[:300]}")
            sys.exit(1)
        data  = r.json()
        batch = data.get("issues", [])
        keys += [i["key"] for i in batch]
        start += len(batch)
        total  = data.get("total", 0)
        print(f"  Fetched {len(keys)}/{total}...")
        if start >= total or not batch:
            break
    return keys

def delete_all(keys):
    deleted, failed = 0, []
    for key in keys:
        r = requests.delete(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{key}",
            auth=auth, headers=headers, timeout=20,
        )
        if r.status_code in (204, 404):
            print(f"  Deleted {key}")
            deleted += 1
        else:
            print(f"  FAILED {key}: {r.status_code} {r.text[:120]}")
            failed.append(key)
        time.sleep(0.05)
    print(f"Done. Deleted {deleted}/{len(keys)}.")
    if failed:
        print(f"Failed: {chr(44).join(failed)}")
        sys.exit(1)

if __name__ == "__main__":
    print(f"Fetching all issues in {PROJECT_KEY}...")
    keys = fetch_all_keys()
    if not keys:
        print("Already empty.")
        sys.exit(0)
    print(f"Deleting {len(keys)} issues...")
    delete_all(keys)