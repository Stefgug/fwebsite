import os, sys, time
import requests

JIRA_BASE_URL  = os.environ["JIRA_BASE_URL"]
JIRA_EMAIL     = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
PROJECT_KEY    = os.environ.get("JIRA_PROJECT_KEY", "SCRUM")

auth    = (JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}


def fetch_all_keys():
    """Paginate through all issues using nextPageToken (new Jira Cloud cursor API)."""
    keys = []
    next_page_token = None

    while True:
        body = {
            "jql": f"project = {PROJECT_KEY} ORDER BY created ASC",
            "maxResults": 100,
            "fields": ["summary"],
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token

        r = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            auth=auth, headers=headers,
            json=body, timeout=20,
        )
        if not r.ok:
            print(f"Search failed ({r.status_code}): {r.text[:300]}")
            sys.exit(1)

        data   = r.json()
        batch  = data.get("issues", [])
        keys  += [i["key"] for i in batch]
        next_page_token = data.get("nextPageToken")
        print(f"  Fetched {len(keys)} so far...")

        if not batch or not next_page_token:
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