"""The boosts of each map and what they bring (06/10, the user: "une vraie passe pour trouver des boosts sur toutes les
maps si ça existe, avec l'efficacité: savoir s'il y a eu des kills avec").

From scan.py's pass over the base's demos: every time a player stood on a teammate's head (the game's own ground
entity, so never a ladder, a vent or players crowding a spawn). An episode is a boost when the two stand still (the
one below moves less than 48 u, the one on top less than 64 u) for a second at least: not a player riding a running
teammate. Episodes 80 u apart at most (same height) make a boost spot. Its use: how often, in how many matches, by which
side, when in the round, where the boosted player looks. Its effect: the kills the boosted player made from up there
(during the boost, or within the second after it: the drop after the shot), his deaths up there, and the share of
boosts that got a kill.

Kept in out/population/boosts.json. Usage: python -m wily.insights.boosts [map ...] (all the scanned maps by default)."""
import json
import math
import os
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

from wily.core import config
from wily.demos import scan

OUT = os.path.join(config.OUT, "population", "boosts.json")
MIN_S, BASE_MOVE, TOP_MOVE = 1.0, 48.0, 64.0
SIDE = {2: "T", 3: "CT"}


def _round_starts(mid):
    try:
        R = pd.read_parquet(os.path.join(config.OUT, "deep", mid, "rounds.parquet"), columns=["round", "start_tick"])
        return dict(zip(R["round"].astype(int), R.start_tick.astype(float)))
    except Exception:
        return {}


def episodes(mp, log=print):
    """The boosts of the map's scanned demos, each with its kills and deaths up there."""
    out, nd = [], 0
    for mid in scan.demos(mp, 100000):
        d = scan.load(mid)
        if not d:
            continue
        nd += 1
        B = d.get("boosts") or []
        if not B:
            continue
        K = pd.DataFrame(d["kills"], columns=d["kcols"]) if d.get("kills") else pd.DataFrame(columns=d["kcols"])
        starts = _round_starts(mid)
        for b in B:
            dur = (b["t1"] - b["t0"]) / 64
            if dur < MIN_S or b["move"] > BASE_MOVE or b["tmove"] > TOP_MOVE:
                continue
            st = starts.get(b["round"])
            t = round((b["t0"] - st) / 64, 1) if st is not None and st == st else None
            if t is not None and t < 0:
                continue   # the freeze time: nobody boosts for real there
            up = K[(K.attacker == b["top"]) & (K.tick >= b["t0"] - 8) & (K.tick <= b["t1"] + 64)]
            up = up[(up.az.isna()) | (up.az >= b["pos"][2] - 40)]   # still up there (or right at the drop)
            down = K[(K.victim == b["top"]) & (K.tick >= b["t0"]) & (K.tick <= b["t1"] + 16)]
            out.append(dict(b, match=mid, dur=round(dur, 1), t=t,
                            kills=[{"w": r.weapon, "hs": bool(r.headshot), "v": [r.vx, r.vy, r.vz], "vplace": r.vplace} for r in up.itertuples()],
                            died=bool(len(down))))
    return out, nd


def _cluster(E, r=80.0, dz=40.0):
    """Spots: the episodes 80 u apart at most (and at the same height), the busiest first."""
    cl = []
    for e in sorted(E, key=lambda e: (e["team"], e["pos"][0], e["pos"][1])):
        for c in cl:
            if c["team"] == e["team"] and math.hypot(c["x"] - e["pos"][0], c["y"] - e["pos"][1]) <= r and abs(c["z"] - e["pos"][2]) <= dz:
                c["E"].append(e)
                n = len(c["E"])
                c["x"] += (e["pos"][0] - c["x"]) / n
                c["y"] += (e["pos"][1] - c["y"]) / n
                c["z"] += (e["pos"][2] - c["z"]) / n
                break
        else:
            cl.append({"team": e["team"], "x": e["pos"][0], "y": e["pos"][1], "z": e["pos"][2], "E": [e]})
    return cl


def analyze_map(mp, log=print):
    from wily.demos.map_analysis import humanize
    t0 = time.time()
    E, nd = episodes(mp, log)
    spots = []
    for c in _cluster(E):
        es = c["E"]
        matches = {e["match"] for e in es}
        if len(es) < 3 or len(matches) < 2:
            continue
        P = np.array([e["pos"] for e in es], float)
        Bp = np.array([e["bpos"] for e in es], float)
        yw = np.radians([e["yaw"] for e in es])
        kills = [k for e in es for k in e["kills"]]
        n_kill = sum(1 for e in es if e["kills"])
        deaths = sum(1 for e in es if e["died"])
        ts = [e["t"] for e in es if e["t"] is not None]
        place = Counter(e["place"] for e in es if e["place"]).most_common(1)
        vic, seen = [], []
        for k in kills:
            v = k["v"]
            if v[0] is None:
                continue
            if all(math.hypot(v[0] - a, v[1] - b) > 90 for a, b, _ in seen):
                seen.append(v)
            if len(seen) >= 4:
                break
        spots.append({
            "side": SIDE.get(c["team"], "?"), "place": humanize(place[0][0], mp) if place else "?", "place_key": place[0][0] if place else None,
            "pos": [round(float(v), 1) for v in np.median(P, axis=0)], "base": [round(float(v), 1) for v in np.median(Bp, axis=0)],
            "dz": round(float(np.median([e["dz"] for e in es])), 1), "base_crouch": round(float(np.mean([e["bduck"] for e in es])), 2),
            "n": len(es), "matches": len(matches), "secs": round(float(np.median([e["dur"] for e in es])), 1),
            "t_med": round(float(np.median(ts)), 1) if ts else None,
            "yaw": round(float(np.degrees(np.arctan2(np.sin(yw).mean(), np.cos(yw).mean()))), 1),
            "pitch": round(float(np.median([e["pitch"] for e in es])), 1),
            "kills": len(kills), "hs": sum(1 for k in kills if k["hs"]), "deaths": deaths,
            "kill_share": round(100 * n_kill / len(es)), "kd": round(len(kills) / max(1, deaths), 2),
            "weapons": dict(Counter(k["w"] for k in kills).most_common(3)),
            "victims": [[round(float(x), 1) for x in v] for v in seen],
            "victim_places": [humanize(p, mp) for p, _ in Counter(k["vplace"] for k in kills if k["vplace"]).most_common(3)],
        })
    spots.sort(key=lambda s: (-s["kills"], -s["n"]))
    log(f"{mp}: {len(E)} boosts in {nd} scanned demos -> {len(spots)} spots, {sum(s['kills'] for s in spots)} kills from them ({time.time() - t0:.0f} s)")
    return {"demos": nd, "episodes": len(E), "spots": spots}


def run(maps=None, log=print):
    from wily.insights import tside
    try:
        cur = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    todo = maps or sorted(m for m, ds in tside._map_dirs().items() if len(ds) >= 10)
    res = {"time": time.strftime("%Y-%m-%d %H:%M"), "maps": dict(cur.get("maps") or {})}
    for mp in todo:
        try:
            r = analyze_map(mp, log)
        except Exception as e:
            log(f"{mp}: boosts unavailable ({e})")
            continue
        if r["demos"]:
            res["maps"][mp] = r
            config.write_json(OUT, res)
    return res


def load(mp=None):
    try:
        d = json.load(open(OUT, encoding="utf-8")).get("maps") or {}
    except (OSError, ValueError):
        d = {}
    return (d.get(mp) or {}).get("spots") or [] if mp else d


if __name__ == "__main__":
    run(sys.argv[1:] or None)
