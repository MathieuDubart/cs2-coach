"""What the In game page showed during your matches, checked against what happened in them (from the match's demo).

During a match the page sends, a few times per round, what it shows: the CT read of the site (A / B / no hit) and of a
rush, the T side's path 1, the buy it advises, the site it finds after the plant. They are kept in out/live/ (one file
per day). Once the match's demo is analyzed, every round is compared with what the demo says: where the Ts went, if
they rushed, which play they ran, what your team bought, where the bomb went down. Per match and per map: how often
the read was right, and the rounds won when the team followed path 1 or not."""
import datetime as dt
import json
import math
import os
import re
import threading
import time

import config

LIVE = os.path.join(config.OUT, "live")
_LOCK = threading.Lock()
KEYS = {"map", "round", "side", "bucket", "elapsed", "money", "score", "read", "paths", "buy", "key", "site", "p_site", "nades"}


def log(body):
    """One snapshot of the page (sent by the page itself): kept as one line of the day's file."""
    if not isinstance(body, dict) or not re.fullmatch(r"[a-z0-9_]{3,40}", str(body.get("map") or "")):
        return False
    rec = {k: body[k] for k in KEYS if k in body}
    if len(json.dumps(rec)) > 6000:
        return False
    rec["ts"] = round(time.time(), 1)
    os.makedirs(LIVE, exist_ok=True)
    with _LOCK, open(os.path.join(LIVE, dt.date.today().strftime("%Y%m%d") + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


def _logs():
    out = []
    if os.path.isdir(LIVE):
        for fn in sorted(os.listdir(LIVE)):
            if fn.endswith(".jsonl"):
                for line in open(os.path.join(LIVE, fn), encoding="utf-8"):
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    return out


def _truth(mid, sid):
    """The match's rounds as the demo tells them: site, tempo, play, plant site, both buys, who won, your side."""
    import pandas as pd
    import tside
    df = tside.load()
    g = df[df.match.astype(str) == str(mid)]
    if not len(g):
        return None
    side = {}
    f = os.path.join(config.DEEP, str(mid), "loadout.parquet")
    if os.path.exists(f):
        L = pd.read_parquet(f, columns=["round", "steamid", "side"])
        mine = L[L.steamid.astype(str) == str(sid)]
        side = {int(r): s for r, s in zip(mine["round"], mine.side)}
    rows = {}
    for r in g.itertuples():
        rows[int(r.round)] = {"site": r.site, "dyn": r.dyn, "play": r.play if isinstance(r.play, str) else None,
                              "plant": r.plant_site if isinstance(r.plant_site, str) else None, "T_won": bool(r.T_won),
                              "T_buy": r.T_buy, "CT_buy": r.CT_buy, "side": side.get(int(r.round))}
    return rows


def _site_of_play(p):
    return None if not p or p == "none" else (p[-1] if p.startswith(("rush", "split")) else p[0])


def check_match(sid, m, logs):
    """One match: its snapshots (same map, during the match) against its rounds."""
    try:
        start = dt.datetime.fromisoformat(m["time"]).timestamp()
    except (KeyError, ValueError, TypeError):
        return None
    span = 60 * (5 + 2.5 * (m.get("rounds") or 24))
    snaps = [x for x in logs if x.get("map") == m.get("map") and start - 600 <= x.get("ts", 0) <= start + span]
    if not snaps:
        return None
    truth = _truth(m["id"], sid)
    if not truth:
        return None
    by = {}
    for x in snaps:   # the last snapshot of each moment wins (the page may send it again after a reload)
        by[(int(x.get("round") or 0), x.get("bucket"))] = x
    ct = {"n": 0, "right": 0, "logloss": 0.0, "rush_n": 0, "rush_right": 0}
    t = {"n": 0, "followed": 0, "won_f": 0, "won_nf": 0, "n_nf": 0, "site_same": 0}
    buy = {"n": 0, "same": 0}
    plant = {"n": 0, "right": 0}
    rounds = []
    for rnd, tr in sorted(truth.items()):
        my = tr["side"]
        if my not in ("T", "CT"):
            continue
        rec = {"round": rnd, "side": my}
        snap = by.get((rnd, "t20")) or by.get((rnd, "fz"))
        if my == "CT" and snap and isinstance(snap.get("read"), dict):
            rd = snap["read"]
            real = tr["site"] if tr["site"] in ("A", "B") else "none"
            p = max(0.01, min(0.99, (rd.get(real) if real != "none" else rd.get("none", 0)) / 100))
            guess = max(("A", "B", "none"), key=lambda k: rd.get(k, 0))
            ct["n"] += 1
            ct["right"] += guess == real
            ct["logloss"] += -math.log(p)
            rec.update(read=guess, real=real, p=round(100 * p))
            fz = by.get((rnd, "fz")) or snap
            if isinstance((fz or {}).get("read"), dict) and fz["read"].get("rush") is not None:
                said, did = fz["read"]["rush"] >= 40, tr["dyn"] == "rush"
                ct["rush_n"] += 1
                ct["rush_right"] += said == did
                rec.update(rush_said=fz["read"]["rush"], rush=did)
        fz = by.get((rnd, "fz"))
        if my == "T" and fz and fz.get("paths"):
            p1 = fz["paths"][0].get("k")
            won = tr["T_won"]
            follow = tr["play"] == p1
            t["n"] += 1
            t["followed"] += follow
            t["site_same"] += _site_of_play(tr["play"]) == _site_of_play(p1)
            if follow:
                t["won_f"] += won
            else:
                t["n_nf"] += 1
                t["won_nf"] += won
            rec.update(p1=p1, play=tr["play"], won=won)
        if fz and fz.get("buy"):
            team = tr["T_buy"] if my == "T" else tr["CT_buy"]
            adv = {"half": "eco"}.get(fz["buy"], fz["buy"])
            if team in ("eco", "force", "full"):
                buy["n"] += 1
                buy["same"] += adv == team
                rec.update(buy=fz["buy"], team_buy=team)
        pl = by.get((rnd, "plant"))
        if pl and pl.get("site") and tr["plant"] in ("A", "B"):
            plant["n"] += 1
            plant["right"] += pl["site"] == tr["plant"]
            rec.update(site_said=pl["site"], plant=tr["plant"])
        if len(rec) > 2:
            rounds.append(rec)
    if not rounds:
        return None
    return {"mid": m["id"], "map": m["map"], "time": m["time"], "snapshots": len(snaps),
            "ct": ct, "t": t, "buy": buy, "plant": plant, "rounds": rounds}


def summary(res):
    """Per map, every checked match together: the numbers the page shows."""
    maps = {}
    for r in res.values():
        a = maps.setdefault(r["map"], {"matches": 0, "ct_n": 0, "ct_right": 0, "ct_ll": 0.0, "rush_n": 0, "rush_right": 0,
                                       "t_n": 0, "followed": 0, "won_f": 0, "won_nf": 0, "n_nf": 0, "buy_n": 0, "buy_same": 0, "plant_n": 0, "plant_right": 0})
        a["matches"] += 1
        a["ct_n"] += r["ct"]["n"]
        a["ct_right"] += r["ct"]["right"]
        a["ct_ll"] += r["ct"]["logloss"]
        a["rush_n"] += r["ct"]["rush_n"]
        a["rush_right"] += r["ct"]["rush_right"]
        for k in ("followed", "won_f", "won_nf", "n_nf"):
            a[k] += r["t"][k]
        a["t_n"] += r["t"]["n"]
        a["buy_n"] += r["buy"]["n"]
        a["buy_same"] += r["buy"]["same"]
        a["plant_n"] += r["plant"]["n"]
        a["plant_right"] += r["plant"]["right"]
    pct = lambda x, n: round(100 * x / n) if n else None
    return {m: {"matches": a["matches"], "site_right": pct(a["ct_right"], a["ct_n"]), "site_n": a["ct_n"],
                "site_logloss": round(a["ct_ll"] / a["ct_n"], 3) if a["ct_n"] else None,
                "rush_right": pct(a["rush_right"], a["rush_n"]), "rush_n": a["rush_n"],
                "followed": pct(a["followed"], a["t_n"]), "t_n": a["t_n"], "win_followed": pct(a["won_f"], a["followed"]),
                "win_other": pct(a["won_nf"], a["n_nf"]), "buy_same": pct(a["buy_same"], a["buy_n"]), "buy_n": a["buy_n"],
                "plant_right": pct(a["plant_right"], a["plant_n"]), "plant_n": a["plant_n"]} for m, a in maps.items()}


def run(sid):
    """Every match of the player with snapshots: checked (again when its demo got analyzed since), saved with the
    player, and the per-map numbers returned for the plan."""
    path = os.path.join(config.player_dir(sid), "livecheck.json")
    old = config.read_json(path, {}) or {}
    logs = _logs()
    if not logs:
        return {"maps": summary(old.get("matches", {})), "matches": []}
    site = os.path.join(config.OUT, "site", "players", f"{sid}.json")
    try:
        matches = json.load(open(site, encoding="utf-8")).get("matches") or []
    except (OSError, ValueError):
        matches = []
    res = dict(old.get("matches", {}))
    for m in matches:
        try:
            r = check_match(sid, m, logs)
        except Exception as e:   # one match that can't be read doesn't stop the others
            print(f"live check {m.get('id')}: {e}", flush=True)
            r = None
        if r:
            res[str(m["id"])] = r
    config.write_json(path, {"matches": res, "updated": dt.datetime.now().isoformat(timespec="minutes")})
    last = sorted(res.values(), key=lambda r: r["time"], reverse=True)[:5]
    return {"maps": summary(res), "matches": [{k: v for k, v in r.items() if k != "rounds"} | {"rounds": r["rounds"][:30]} for r in last]}
