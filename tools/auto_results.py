#!/usr/bin/env python3
"""Run by GitHub Actions every 15 min: fills in finished J&K matches from BCCI.
For each 'upcoming' match with a bcci id whose start has passed, runs bcci_result.py.
Prints a one-line summary per match written; exit 0 always (errors are retried next run)."""
import json, subprocess, sys, datetime as dt, os
here = os.path.dirname(os.path.abspath(__file__))
f = os.path.join(here, "..", "data.json")
d = json.load(open(f))
now = dt.datetime.now(dt.timezone.utc)
todo = []
for mid, m in d["matches"].items():
    if m.get("status") != "upcoming" or not m.get("bcci"): continue
    s = m.get("start") or (m.get("date", "") + "T04:00:00Z")
    try: t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError: continue
    if t + dt.timedelta(hours=2) <= now: todo.append(mid)
done = []
for mid in todo:
    r = subprocess.run([sys.executable, os.path.join(here, "bcci_result.py"), mid], capture_output=True, text=True)
    print(mid, r.returncode, (r.stdout or r.stderr).strip()[-300:])
    if r.returncode == 0: done.append(mid)
# fallback squads from BCCI for tournaments with no squad on the site yet (official JKCA squads always win)
sq = subprocess.run([sys.executable, os.path.join(here, "bcci_squad.py")], capture_output=True, text=True, cwd=os.path.join(here, ".."))
print("squads:", (sq.stdout or sq.stderr).strip()[-400:])
try: sq_added = json.loads(sq.stdout.strip().splitlines()[-1]).get("added", [])
except Exception: sq_added = []
if done or sq_added:
    d = json.load(open(f))
    d["updated"] = (now + dt.timedelta(hours=5, minutes=30)).date().isoformat()
    json.dump(d, open(f, "w"), ensure_ascii=False, separators=(",", ":"))
    parts = [d["matches"][m].get("result", m) for m in done] + ["squad " + x.split(":")[0] for x in sq_added]
    open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a").write("msg=Stats (auto): " + ", ".join(parts) + "\n")
