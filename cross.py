"""Cross-match analysis for one player: zones/spots to play or avoid, others' best spots, lineups, duel contexts.

Usage: python cross.py > out/cross.json   (reads out/deep/<match_id>/)
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

from map_analysis import humanize

ME = None  # set by run()
HERE = os.path.dirname(os.path.abspath(__file__))
DEEP = os.path.join(HERE, "out", "deep")
CELL = 28  # radar px (~110-160 game units depending on map)


def wr(k, d):
    n = k + d
    return round(100 * k / n) if n else None


def load(match_ids=None):
    """Deep data per map: the player's matches, plus every other analyzed demo of the same map
    (reference pool for zone baselines, best spots and lineups) when the map uses game callouts."""
    per_map = defaultdict(lambda: {"duels": [], "nades": [], "samples": [], "meta": None, "matches": 0, "pool": 0})
    metas, mine = {}, set()
    for mid in sorted(os.listdir(DEEP)):
        f = os.path.join(DEEP, mid)
        if not os.path.exists(os.path.join(f, "meta.json")):
            continue
        metas[mid] = json.load(open(os.path.join(f, "meta.json"), encoding="utf-8"))
        if match_ids is None or mid in match_ids:
            smp = pd.read_parquet(os.path.join(f, "samples.parquet"), columns=["steamid"])
            if ME in set(smp.steamid):
                mine.add(mid)
    my_maps = {metas[m]["map"] for m in mine}
    for mid, meta in metas.items():
        if meta["map"] not in my_maps:
            continue
        if mid not in mine and meta.get("zone_mode") != "callouts":
            continue  # hand-made / automatic sectors are not comparable across demos
        f = os.path.join(DEEP, mid)
        m = per_map[meta["map"]]
        for name, key in (("duels", "duels"), ("grenades", "nades"), ("samples", "samples")):
            df = pd.read_parquet(os.path.join(f, f"{name}.parquet"))
            df["match"] = mid
            m[key].append(df)
        m["pool"] += 1
        if mid in mine:
            m["matches"] += 1
        if m["meta"] is None or len(meta["zones"]) > len(m["meta"]["zones"]):
            m["meta"] = meta
    for m in per_map.values():
        for key in ("duels", "nades", "samples"):
            m[key] = pd.concat(m[key], ignore_index=True) if m[key] else pd.DataFrame()
    return per_map


def zone_name(meta, key):
    for z in meta["zones"]:
        if z["key"] == key:
            return z["name"]
    return humanize(key, meta.get("map")) if isinstance(key, str) else str(key)


def my_duels(d):
    """One row per duel I was in, from my point of view."""
    a = d[d.killer == ME].copy()
    a["won"] = True
    b = d[d.victim == ME].copy()
    b["won"] = False
    rows = []
    for won, df, me, op in ((True, a, "killer", "victim"), (False, b, "victim", "killer")):
        for _, r in df.iterrows():
            rows.append({"match": r.match, "round": r["round"], "tick": r.tick, "t": r.t, "won": won,
                         "side": r[f"{me}_side"], "zone": r[f"{me}_zone"], "opp_zone": r[f"{op}_zone"],
                         "px": r[f"{me}_px"], "py": r[f"{me}_py"], "level": r[f"{me}_level"],
                         "opp_px": r[f"{op}_px"], "opp_py": r[f"{op}_py"],
                         "X": r[f"{me}_X"], "Y": r[f"{me}_Y"],
                         "speed": r.get(f"{me}_speed"), "opp_speed": r.get(f"{op}_speed"),
                         "hp": r.get(f"{me}_hp"), "crouch": r.get(f"{me}_crouch"),
                         "mate_dist": r.get(f"{me}_mate_dist"), "mates_alive": r.get(f"{me}_mates_alive"),
                         "opp_mates_alive": r.get(f"{op}_mates_alive"),
                         "me_flashed": r.killer_flashed if me == "killer" else r.victim_flashed,
                         "opp_flashed": r.victim_flashed if me == "killer" else r.killer_flashed,
                         "distance": r.distance, "weapon": r.weapon, "opening": r.opening})
    return pd.DataFrame(rows).sort_values(["match", "tick"]) if rows else pd.DataFrame()


def all_duels_pov(d, exclude_me=True):
    """Every duel from both players' point of view (for 'others' baselines)."""
    rows = []
    for me, op, won in (("killer", "victim", True), ("victim", "killer", False)):
        df = pd.DataFrame({
            "player": d[me], "won": won, "side": d[f"{me}_side"], "zone": d[f"{me}_zone"],
            "px": d[f"{me}_px"], "py": d[f"{me}_py"], "level": d[f"{me}_level"], "t": d.t,
            "speed": d.get(f"{me}_speed"), "opp_speed": d.get(f"{op}_speed"), "crouch": d.get(f"{me}_crouch"),
            "hp": d.get(f"{me}_hp"), "mate_dist": d.get(f"{me}_mate_dist"),
            "mates_alive": d.get(f"{me}_mates_alive"), "opp_mates_alive": d.get(f"{op}_mates_alive"),
            "opp_flashed": d.victim_flashed if me == "killer" else d.killer_flashed,
            "me_flashed": d.killer_flashed if me == "killer" else d.victim_flashed,
            "distance": d.distance, "scoped": d.get(f"{me}_scoped"), "weapon": d.weapon})
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    return out[out.player != ME] if exclude_me else out


def contexts(mine, others):
    """Win rate of duels under different conditions, me vs the other players."""
    def split(df, name, masks):
        res = []
        for label, fn in masks:
            s = df[fn(df)]
            res.append({"label": label, "n": int(len(s)), "win": round(100 * s.won.mean()) if len(s) else None})
        return {"name": name, "rows": res}

    specs = [
        ("Teammate support", [("teammate within 600 u", lambda x: x.mate_dist < 600),
                                     ("alone (teammate beyond 1,200 u or none)", lambda x: (x.mate_dist > 1200) | x.mate_dist.isna())]),
        ("Movement at the start of the duel", [("still, you hold the angle (< 40 u/s)", lambda x: x.speed < 40),
                                        ("moving, you peek (> 110 u/s)", lambda x: x.speed > 110)]),
        ("Enemy movement", [("the enemy peeks at you (> 110 u/s)", lambda x: x.opp_speed > 110),
                                       ("the enemy is still (< 40 u/s)", lambda x: x.opp_speed < 40)]),
        ("Flashes", [("enemy flashed by your team", lambda x: x.opp_flashed == True),
                    ("you flashed", lambda x: x.me_flashed == True),
                    ("nobody flashed", lambda x: (x.opp_flashed == False) & (x.me_flashed == False))]),
        ("Balance of power", [("with a man advantage", lambda x: x.mates_alive > x.opp_mates_alive),
                              ("even", lambda x: x.mates_alive == x.opp_mates_alive),
                              ("outnumbered", lambda x: x.mates_alive < x.opp_mates_alive)]),
        ("Moment of the round", [("0-20 s", lambda x: x.t <= 20), ("20-45 s", lambda x: (x.t > 20) & (x.t <= 45)),
                             ("after 45 s", lambda x: x.t > 45)]),
        ("Distance", [("short (< 10 m)", lambda x: x.distance < 10), ("medium (10-20 m)", lambda x: (x.distance >= 10) & (x.distance < 20)),
                      ("long (> 20 m)", lambda x: x.distance >= 20)]),
        ("Health at the start of the duel", [("more than 80 HP", lambda x: x.hp > 80), ("less than 50 HP", lambda x: x.hp < 50)]),
        ("Stance", [("crouched", lambda x: x.crouch == True), ("standing", lambda x: x.crouch == False)]),
    ]
    out = []
    for name, masks in specs:
        a, b = split(mine, name, masks), split(others, name, masks)
        for ra, rb in zip(a["rows"], b["rows"]):
            ra["others_win"], ra["others_n"] = rb["win"], rb["n"]
        out.append(a)
    return out


def repeek(mine):
    """After one of my kills, what happens in my next duel within 8 s depending on whether I moved."""
    res = {"stayed": [0, 0], "moved": [0, 0]}
    for _, g in mine.groupby(["match", "round"]):
        g = g.sort_values("tick").reset_index(drop=True)
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if not a.won or b.tick - a.tick > 8 * 64:
                continue
            moved = np.hypot(b.X - a.X, b.Y - a.Y)
            key = "stayed" if moved < 150 else "moved"
            res[key][0 if b.won else 1] += 1
    return {k: {"won": v[0], "lost": v[1], "win": wr(*v)} for k, v in res.items()}


def cells(df, xcol="px", ycol="py"):
    return list(zip((df[xcol] // CELL).astype(int), (df[ycol] // CELL).astype(int), df["level"]))


def lineups(nades, side, zones_of_interest, meta, top=4):
    """Best grenades of each type that land in / are thrown from the zones this player uses."""
    out = []
    g = nades[(nades.side == side) & nades.land_px.notna()].copy()
    if not len(g):
        return out
    g["lcell"] = list(zip((g.land_px // 36).astype(int), (g.land_py // 36).astype(int), g.land_level))
    for typ in ("smoke", "flash", "molotov", "he"):
        t = g[g.type == typ]
        groups = []
        for cell, c in t.groupby("lcell"):
            rel = c.zone.isin(zones_of_interest).any() or c.land_zone.isin(zones_of_interest).any()
            if typ == "flash":
                c = c.assign(score=c.enemies_blind.fillna(0) * 2 + c.kills_after.fillna(0) * 3 - c.mates_blind.fillna(0) * 2)
                eff = c[c.score > 0]
                if not len(eff):
                    continue
                best = eff.sort_values("score", ascending=False).iloc[0]
                metric = {"uses": int(len(c)), "enemies_blind_avg": round(float(c.enemies_blind.mean()), 1),
                          "mates_blind_avg": round(float(c.mates_blind.mean()), 1), "kills_after": int(c.kills_after.sum())}
                value = float(c.score.mean()) + 0.3 * len(c)
            elif typ in ("he", "molotov"):
                if c.damage.fillna(0).sum() <= 0 and len(c) < 3:
                    continue
                c = c.assign(repro=(c.speed < 20) | c.jump)
                best = c.sort_values(["damage", "repro"], ascending=False).iloc[0]
                metric = {"uses": int(len(c)), "damage_avg": round(float(c.damage.fillna(0).mean())),
                          "damage_best": int(best.damage or 0)}
                value = float(c.damage.fillna(0).mean()) / 20 + len(c)
            else:  # smoke: popular landing spot = standard smoke; pick the most common throw spot
                if len(c) < 2:
                    continue
                tc = c.assign(tcell=list(zip((c.px // 20).astype(int), (c.py // 20).astype(int))),
                              repro=(c.speed < 20) | c.jump)
                pool = tc[tc.repro] if tc.repro.any() else tc
                top_throw = pool.tcell.value_counts().index[0]
                best = pool[pool.tcell == top_throw].iloc[0]
                metric = {"uses": int(len(c)), "players": int(c.thrower.nunique())}
                value = len(c) + c.thrower.nunique()
            groups.append((value + (5 if rel else 0), rel, best, metric))
        groups.sort(key=lambda x: -x[0])
        for value, rel, b, metric in groups[:top]:
            how = []
            if b.jump:
                how.append("jumpthrow")
            if b.speed > 150:
                how.append("running")
            elif b.walk or 20 < b.speed <= 150:
                how.append("walking")
            if b.crouch:
                how.append("crouching")
            out.append({
                "type": typ, "side": side, "relevant": bool(rel), **metric,
                "from_zone": zone_name(meta, b.zone), "to_zone": zone_name(meta, b.land_zone) if b.land_zone else None,
                "from_px": [round(b.px), round(b.py)], "to_px": [round(b.land_px), round(b.land_py)],
                "level": b.level, "land_level": b.land_level,
                "t": b.t, "click": b.click, "how": " + ".join(how) or "standing still", "by": b.thrower_name,
                "setpos": f"setpos {b.X:.1f} {b.Y:.1f} {b.Z:.1f}; setang {b.pitch:.2f} {b.yaw:.2f} 0",
                "flight_s": b.get("flight_s"),
            })
    return out


def per_map(name, m):
    d, n, s, meta = m["duels"], m["nades"], m["samples"], m["meta"]
    mine = my_duels(d)
    others = all_duels_pov(d)
    res = {"map": name, "matches": m["matches"], "pool": m["pool"], "levels": meta["levels"], "zone_mode": meta["zone_mode"],
           "zones_meta": meta["zones"], "sides": {}}
    ms = s[s.steamid == ME]
    for side in ("T", "CT"):
        my_s = ms[ms.side == side]
        if not len(my_s):
            continue
        md = mine[mine.side == side] if len(mine) else mine
        od = others[others.side == side]
        pres = my_s.zone.value_counts(normalize=True)
        first_contact = {}
        for z, g in od.groupby("zone"):
            first_contact[z] = round(float(g.t.quantile(0.25)), 1)
        zones = []
        for z in set(pres.index) | set(md.zone if len(md) else []):
            if z in ("?", None):
                continue
            mz = md[md.zone == z] if len(md) else md
            k, dd = (int(mz.won.sum()), int((~mz.won).sum())) if len(mz) else (0, 0)
            oz = od[od.zone == z]
            ok, odd = int(oz.won.sum()), int((~oz.won).sum())
            p = float(pres.get(z, 0) * 100)
            me_wr, oth_wr = wr(k, dd), wr(ok, odd)
            verdict = None
            if k + dd >= 4 and me_wr >= 60 and (oth_wr is None or me_wr >= oth_wr + 5):
                verdict = "exploit"
            elif k + dd >= 4 and (me_wr <= 35 or (oth_wr is not None and me_wr <= oth_wr - 20)):
                verdict = "avoid"
            elif k + dd >= 3 and k == 0:
                verdict = "avoid"
            if p < 3 and k + dd < 3:
                continue
            killers = mine[(mine.side == side) & (mine.zone == z) & (~mine.won)].opp_zone.value_counts().head(2) if len(mine) else pd.Series(dtype=int)
            zones.append({"key": z, "name": zone_name(meta, z), "presence": round(p, 1), "k": k, "d": dd, "win": me_wr,
                          "others_k": ok, "others_d": odd, "others_win": oth_wr, "verdict": verdict,
                          "early_contact_s": first_contact.get(z),
                          "killed_from": [{"zone": zone_name(meta, kz), "n": int(c)} for kz, c in killers.items()],
                          "my_speed_med": round(float(mz.speed.median())) if len(mz) and mz.speed.notna().any() else None,
                          "others_speed_med": round(float(oz.speed.median())) if len(oz) and oz.speed.notna().any() else None})
        zones.sort(key=lambda z: -z["presence"])
        # whole-pool view of the side: which zones pay off for everybody, and how much time players spend there
        side_s = s[(s.side == side) & (s.steamid != ME)]
        side_pres = side_s.zone.value_counts(normalize=True) if len(side_s) else pd.Series(dtype=float)
        pool_zones = []
        for z, g in od.groupby("zone"):
            if z in ("?", None):
                continue
            k, dd = int(g.won.sum()), int((~g.won).sum())
            if k + dd < 8:
                continue
            pool_zones.append({"key": z, "name": zone_name(meta, z), "k": k, "d": dd, "win": wr(k, dd),
                               "others_presence": round(float(side_pres.get(z, 0) * 100), 1),
                               "my_presence": round(float(pres.get(z, 0) * 100), 1),
                               "hold_pct": round(100 * float((g.speed < 40).mean())) if g.speed.notna().any() else None,
                               "t_med": round(float(g.t.median()))})
        pool_zones.sort(key=lambda z: -(z["win"] or 0))
        # my micro spots
        spots = []
        if len(md):
            md = md.assign(cell=cells(md))
            for c, g in md.groupby("cell"):
                if len(g) < 2:
                    continue
                spots.append({"px": [round(float(g.px.mean())), round(float(g.py.mean()))], "level": c[2],
                              "k": int(g.won.sum()), "d": int((~g.won).sum()), "zone": zone_name(meta, g.zone.mode()[0])})
        # others' best spots, in zones I use
        my_zones = {z["key"] for z in zones if z["presence"] >= 4}
        od2 = od[od.zone.isin(my_zones)].assign(cell=lambda x: cells(x))
        best = []
        for c, g in od2.groupby("cell"):
            k, dd = int(g.won.sum()), int((~g.won).sum())
            if k + dd >= 5 and k / (k + dd) >= 0.65:
                best.append({"px": [round(float(g.px.mean())), round(float(g.py.mean()))], "level": c[2], "k": k, "d": dd,
                             "win": wr(k, dd), "zone": zone_name(meta, g.zone.mode()[0]),
                             "hold_pct": round(100 * float((g.speed < 40).mean())), "crouch_pct": round(100 * float((g.crouch == True).mean())),
                             "scoped_pct": round(100 * float((g.scoped == True).mean())), "t_med": round(float(g.t.median())),
                             "players": int(g.player.nunique())})
        best.sort(key=lambda b: (-(b["k"] - b["d"]), -b["win"]))
        # my deaths spots with killers (for the radar)
        deaths = [{"px": [round(r.px), round(r.py)], "opp_px": [round(r.opp_px), round(r.opp_py)], "level": r.level, "won": bool(r.won),
                   "zone": zone_name(meta, r.zone)} for _, r in (md.dropna(subset=["px", "py", "opp_px", "opp_py"]).iterrows() if len(md) else [])]
        interest = my_zones | {z["key"] for z in zones if z["verdict"] == "avoid"}
        res["sides"][side] = {"zones": zones, "pool_zones": pool_zones, "spots": spots, "best_spots": best[:8], "duels": deaths,
                              "lineups": lineups(n, side, interest, meta) if len(n) else []}
    return res


def run(me, match_ids=None):
    global ME
    ME = int(me)
    pm = load(match_ids)
    out = {"maps": [], "contexts": None, "repeek": None}
    all_mine, all_others = [], []
    for name, m in sorted(pm.items(), key=lambda x: -x[1]["matches"]):
        out["maps"].append(per_map(name, m))
        all_mine.append(my_duels(m["duels"]))
        all_others.append(all_duels_pov(m["duels"]))
    mine = pd.concat(all_mine, ignore_index=True)
    others = pd.concat(all_others, ignore_index=True)
    out["contexts"] = contexts(mine, others)
    out["repeek"] = repeek(mine)
    out["totals"] = {"my_duels": int(len(mine)), "my_win": round(100 * float(mine.won.mean())), "others_duels": int(len(others)),
                     "others_win": round(100 * float(others.won.mean()))}
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import config
    res = run(int(sys.argv[1]) if len(sys.argv) > 1 else config.logged_in_account()[0])
    print(json.dumps(res, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
