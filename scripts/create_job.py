"""Create a queued render job on the VPS for the local agent to claim + render.

Logs in (cookie), creates a research run, starts discovery, waits, approves the
first proposed candidate, and creates a render job. Prints the job id so you can
watch it on the dashboard /jobs/{id} as the local agent drives it to completion.
"""
import sys
import time

import httpx

API = "https://api.purapuraninja.my.id"
PW = "526a0886af726327e864f88756596d5ac919a23fed34cf88"

c = httpx.Client(timeout=30.0)

r = c.post(f"{API}/api/v1/auth/login", json={"username": "admin", "password": PW})
r.raise_for_status()
print("login ok")

r = c.post(
    f"{API}/api/v1/research-runs",
    json={"keyword": "banjir jakarta terkini", "language": "id-ID", "period_days": 7},
)
r.raise_for_status()
rid = r.json()["id"]
print("run", rid)

r = c.post(f"{API}/api/v1/research-runs/{rid}/start")
r.raise_for_status()
print("started")

st = None
for _ in range(40):
    st = c.get(f"{API}/api/v1/research-runs/{rid}").json()["status"]
    print("  status", st)
    if st in ("completed", "failed"):
        break
    time.sleep(2)

cs = c.get(f"{API}/api/v1/research-runs/{rid}/candidates").json()
cand = next((x for x in cs if x["status"] == "proposed"), None) or (cs[0] if cs else None)
if not cand:
    print("no candidates"); sys.exit(1)
print("approve", cand["id"], "->", cand["title"])

r = c.post(f"{API}/api/v1/candidates/{cand['id']}/approve")
r.raise_for_status()

r = c.post(
    f"{API}/api/v1/candidates/{cand['id']}/render-jobs",
    params={"profile_name": "TikTok ID 45s"},
)
r.raise_for_status()
job = r.json()
print("JOB", job["id"], job["status"])
print(f"watch: https://app.purapuraninja.my.id/jobs/{job['id']}")
