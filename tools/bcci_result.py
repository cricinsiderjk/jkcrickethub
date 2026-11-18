#!/usr/bin/env python3
"""Fill a finished J&K match in data.json from BCCI's match-centre data.

Usage:  python3 tools/bcci_result.py <match id in data.json> [--file scorecard.json] [--dry]
The match must have a "bcci" field (the BCCI match id). The script downloads
https://stats.bcci.tv/match/<bcci>/scorecard (or reads --file), and, if BCCI marks the
match complete, writes status, winner, result, XI and the J&K batting/bowling card.
Only J&K players are stored. It refuses to touch matches with ball-by-ball data.
Exit codes: 0 = written, 2 = not finished yet, 1 = error.
"""
import difflib, json, re, sys, urllib.request

ALIASES = {  # spellings BCCI uses -> existing player ids
    "ananaya sharma": "p-ananya-sharma", "mariya noorain": "p-maria-noorain", "aashutosh mahajan": "p-ashutosh-mahajan",
    "sp khajuria": "p-shubham-khajuria", "shubham singh pundir": "p-shubham-pundir",
    "sr kumar": "p-sunil-kumar", "lone nasir": "p-lone-nasir-muzaffar", "umar nazir mir": "p-umar-nazir",
    "yudhvir singh charak": "p-yudhvir-singh", "yawar hasan": "p-yawer-hassan", "kanhaiya wadhwan": "p-kanhaiya-wadhawan",
}
ROLE = {"batsman": "Batter", "batter": "Batter", "bowler": "Bowler", "allrounder": "All-rounder", "all-rounder": "All-rounder", "wicketkeeper": "Wicket-keeper"}

def pid(n): return "p-" + re.sub(r"[^a-z]+", "-", n.lower()).strip("-")

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(1)
    mid = a[0]; dry = "--dry" in a
    d = json.load(open("data.json")); M, T = d["matches"], d["teams"]
    m = M.get(mid)
    if not m or not m.get("bcci"): print("match not found or has no bcci id"); sys.exit(1)
    if any(i.get("balls") for i in m.get("innings", [])): print("has ball-by-ball data; not touching"); sys.exit(1)
    if "--file" in a: j = json.load(open(a[a.index("--file") + 1]))
    else:
        req = urllib.request.Request(f"https://stats.bcci.tv/match/{m['bcci']}/scorecard", headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bcci.tv/"})
        import time
        for t in range(6):  # BCCI's server sometimes drops connections: retry
            try:
                raw = urllib.request.urlopen(req, timeout=30).read()
                if raw[:2] == b"\x1f\x8b": raw = __import__("gzip").decompress(raw)  # BCCI sometimes sends gzip
                j = json.loads(raw); break
            except Exception as e:
                if t == 5: print("BCCI unreachable after 6 tries:", e); sys.exit(1)
                time.sleep(10 * (t + 1))
    mt = j["match"]
    if mt.get("match_status") != "complete": print("not finished:", mt.get("match_status"), mt.get("live_status_name")); sys.exit(2)
    jkids = [t for t in (m["teamA"], m["teamB"]) if t.startswith("t-jk")]
    jk = jkids[0]; opp = m["teamB"] if m["teamA"] == jk else m["teamA"]
    bt_team = next(t for t in j["team"] if "Jammu" in t["name"])
    ot_team = next(t for t in j["team"] if t is not bt_team)
    tid = {bt_team["team_id"]: jk, ot_team["team_id"]: opp}
    names = {p["player_id"]: (p.get("known_as") or p["name"]) for t in j["team"] for p in t["player"]}
    team = T[jk]; byname = {p["name"].lower(): p["id"] for p in team["players"]}; have = {p["id"] for p in team["players"]}
    allids = {p["id"]: p for t in T.values() for p in t.get("players", [])}
    added = []
    def squash(x): return re.sub(r"(.)\1+", r"\1", re.sub(r"[^a-z ]", "", x.lower())).split()
    def near(n):  # same team, same person spelt slightly differently (Arfat/Arfaat, Partap/Pratap, name with/without surname)
        a = squash(n); hits = set()
        for p in team["players"]:
            b = squash(p["name"])
            if len(a) >= 2 and len(b) >= 2 and (a == b[:len(a)] or b == a[:len(b)]): hits.add(p["id"]); continue
            if len(a) == len(b) and difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio() >= 0.88: hits.add(p["id"])
        return hits.pop() if len(hits) == 1 else None
    def gid(bp):
        n = names[bp]; k = n.lower()
        if k in byname: return byname[k]
        i = ALIASES.get(k) or near(n) or pid(n)
        if i not in have:
            src = next((p for p in j["team"] for p in p["player"] if p["player_id"] == bp), {})
            role = ROLE.get((src.get("player_role") or "").lower(), "Wicket-keeper" if src.get("is_keeper") == "1" else "Player")
            team["players"].append({"id": i, "name": allids[i]["name"] if i in allids else n, "role": allids[i].get("role", role) if i in allids else role})
            have.add(i); added.append(n)
        byname[k] = i; return i
    xi = [gid(p["player_id"]) for p in bt_team["player"]]
    inns = []
    for n_i, i in enumerate(j["innings"]):
        if n_i >= 2 and (m.get("overs") or 0) and str(i.get("ball_limit") or "") in ("6", "12"):
            continue  # super over: not part of the scorecard or player stats
        jb = tid.get(i["batting_team_id"]) == jk
        ed = ", ".join(f"{k} {v}" for k, v in (("b", i.get("byes")), ("lb", i.get("legbyes")), ("w", i.get("wides")), ("nb", i.get("noballs")), ("pen", i.get("penalties"))) if v and int(v))
        card = {"total": int(i["runs"]), "wkts": int(i["wickets"]), "balls": int(i.get("balls_bowled") or i.get("total_balls_bowled") or 0) or None,
                "extras": int(i.get("extras") or 0), "extrasDetail": ed, "partial": False}
        if (i.get("closure_name") or "").lower().startswith("declar"): card["dec"] = True
        if jb:
            card["bt"] = [{"p": gid(b["player_id"]), "r": int(b["runs"]), "b": int(b["balls_faced"]), "f": int(b["fours"]), "s": int(b["sixes"]),
                           "out": b.get("dismissal_str") if b.get("is_out") == "1" else None} for b in i["batting"] if b.get("batted") == "yes"]
            if sum(x["r"] for x in card["bt"]) + card["extras"] != card["total"]: card["partial"] = True; card["note"] = "Batting figures do not add up to the total in BCCI's data."
        else:
            card["bw"] = [{"p": gid(b["player_id"]), "balls": int(b["balls"]), "m": int(b["maidens"]), "r": int(b["conceded"]), "w": int(b["wickets"])} for b in i["bowling"]]
            if card["balls"] and sum(x["balls"] for x in card["bw"]) != card["balls"]: card["partial"] = True; card["note"] = "Bowling figures do not add up in BCCI's data."
        inns.append({"bat": jk if jb else opp, "bowl": opp if jb else jk, "balls": [], "closed": True, "card": card})
    res = mt.get("result_string") or ""
    for t in j["team"]: res = res.replace(t["name"], T[tid[t["team_id"]]]["name"])
    res = re.sub(r"\bwin by\b", "won by", res).replace("win the super over", "won the super over")
    w = tid.get(mt.get("winner_team_id"))
    m.update({"status": "done", "winner": w, "result": res, "innings": inns, "xi": {jk: xi, opp: []},
              "src": f"https://www.bcci.tv/matches/{m['bcci']}/match", "srcName": "BCCI match centre"})
    if (mt.get("result_name") or "").lower().startswith("draw"): m["draw"] = True; m["winner"] = None
    if mt.get("ground_name") and (not m.get("venue") or m["venue"] in ("TBA", "Venue to be confirmed")): m["venue"] = mt["ground_name"]
    print(json.dumps({"match": mid, "result": res, "added_players": added,
                      "jk_innings": [f'{x["card"]["total"]}/{x["card"]["wkts"]}' for x in inns if x["bat"] == jk],
                      "partial": [x["card"].get("note") for x in inns if x["card"]["partial"]]}, ensure_ascii=False))
    if not dry: json.dump(d, open("data.json", "w"), ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__": main()
