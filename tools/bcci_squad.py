#!/usr/bin/env python3
"""Fallback squads from BCCI: for every J&K tournament this season that has NO squad on the site yet,
add the players J&K registered with BCCI for that tournament (stats.bcci.tv/comp/<id>/squads).
Official JKCA squads always win: a tournament that already has any squad is skipped.
Usage: python3 tools/bcci_squad.py [--dry]      (run from the repository folder)
Stores names, captain/wicket-keeper flags and BCCI roles only (no birth dates or other personal data)."""
import json, re, sys, gzip, time, difflib, datetime as dt, urllib.request, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bcci_result import ROLE, ALIASES

SH = {"Ranji Trophy": "ranji", "Syed Mushtaq Ali Trophy": "smat", "Vijay Hazare Trophy": "vht", "Irani Cup": "irani",
      "CK Nayudu Trophy": "ckn", "Men's U23 State A Trophy": "u23a", "Men's U23 State A T20 Trophy": "u23t20", "Cooch Behar Trophy": "cb", "Vinoo Mankad Trophy": "vm",
      "Vijay Merchant Trophy": "vmt", "Senior Women's T20 Trophy": "swt20", "Senior Women's One Day Trophy": "swod",
      "Women's U23 T20 Trophy": "wu23t20", "Women's U23 One Day Trophy": "wu23od", "Women's U19 T20 Trophy": "wu19t20", "Women's U19 One Day Trophy": "wu19od"}
CAT = {"t-jk": "Senior Men", "t-jk-u23": "Under-23 Men", "t-jk-u19": "Under-19 Men", "t-jk-u16": "Under-16 Men", "t-jkw": "Women", "t-jkw-u23": "Women", "t-jkw-u19": "Women"}

def get(u):
    for t in range(4):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bcci.tv/"}), timeout=30).read()
            if raw[:2] == b"\x1f\x8b": raw = gzip.decompress(raw)
            return json.loads(raw)
        except Exception as e:
            if t == 3: raise
            time.sleep(8 * (t + 1))

def season_of(date):
    y, m = int(date[:4]), int(date[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def main():
    dry = "--dry" in sys.argv
    d = json.load(open("data.json")); T = d["teams"]
    today = dt.date.today().isoformat(); cur = season_of(today)
    have = {(q["tournament"], q["season"], q.get("team")) for q in d["squads"]}
    todo = {}
    for mid, m in d["matches"].items():
        if not m.get("bcci") or not m.get("date") or season_of(m["date"]) != cur: continue
        # only tournaments with a J&K match from 3 days ago to 14 days ahead (keeps requests to BCCI low)
        if not (str(dt.date.today() - dt.timedelta(days=3)) <= m["date"] <= str(dt.date.today() + dt.timedelta(days=14))): continue
        jk = next((t for t in (m["teamA"], m["teamB"]) if t.startswith("t-jk")), None)
        if not jk or (m["tournament"], cur, jk) in have: continue
        todo.setdefault((m["tournament"], jk), m)
    allids = {p["id"]: p for t in T.values() for p in t.get("players", [])}
    out = []
    for (tour, jk), m in todo.items():
        try:
            comp = get(f"https://stats.bcci.tv/match/{m['bcci']}/scorecard")["match"]["comp_id"]
            data = get(f"https://stats.bcci.tv/comp/{comp}/squads")
        except Exception as e:
            print(f"{tour}: BCCI unreachable ({e})"); continue
        sq = next((s for s in data.get("squads", []) if "jammu" in (s.get("team_name") or "").lower()), None)
        if not sq or not sq.get("players"): print(f"{tour}: no J&K squad on BCCI yet"); continue
        team = T[jk]; tp = team["players"]
        def squash(x): return re.sub(r"(.)\1+", r"\1", re.sub(r"[^a-z ]", "", x.lower())).split()
        def find(n):
            k = n.lower()
            for p in tp:
                if p["name"].lower() == k: return p["id"]
            if ALIASES.get(k): return ALIASES[k]
            a = squash(n); hits = set()
            for p in tp:
                b = squash(p["name"])
                if len(a) >= 2 and len(b) >= 2 and (a == b[:len(a)] or b == a[:len(b)]): hits.add(p["id"]); continue
                if len(a) == len(b) and difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio() >= 0.88: hits.add(p["id"])
            return hits.pop() if len(hits) == 1 else None
        ids, cap, wk, new = [], None, [], []
        for bp in sq["players"]:
            n = (bp.get("known_as") or bp.get("name") or "").strip()
            if not n: continue
            i = find(n)
            if not i:
                i = "p-" + re.sub(r"[^a-z]+", "-", n.lower()).strip("-")
                tag = (bp.get("player_role") or "").lower().replace(" ", "")
                role = "Wicket-keeper" if "keeper" in tag else ROLE.get(tag, "Player")
                if i not in {p["id"] for p in tp}:
                    tp.append({"id": i, "name": allids[i]["name"] if i in allids else n, "role": allids[i].get("role", role) if i in allids else role}); new.append(n)
            if i in ids: continue
            ids.append(i)
            if str(bp.get("is_captain")) == "1": cap = i
            if str(bp.get("is_wicketkeeper")).lower() in ("yes", "1", "true"): wk.append(i)
        q = {"id": f"sq-{SH.get(tour, 'x')}-{cur.replace('-', '')}-bcci", "category": CAT.get(jk, "Senior Men"), "team": jk, "tournament": tour, "season": cur,
             "label": "BCCI registered squad", "kind": "bcci", "announced": today, "players": ids, "wk": wk,
             "note": f"Players J&K registered with BCCI for this tournament ({len(ids)}). JKCA's final squad wasn't found yet; it will replace this list when published.",
             "src": f"https://www.bcci.tv/matches/{m['bcci']}/match/squads", "srcName": "BCCI.tv squads"}
        if cap: q["captain"] = cap
        d["squads"].append(q); out.append(f"{tour} ({team['name'] if 'name' in team else jk}): {len(ids)} players, {len(new)} new")
    if out and not dry: json.dump(d, open("data.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(json.dumps({"added": out}, ensure_ascii=False))

if __name__ == "__main__": main()
