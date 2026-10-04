"""The pro grenade catalog of Daily CS Nades made usable (04/10, the user: "fiabilise les stuffs").

Its 7,310 lineups thrown in pro matches (out/lineups/<map>_dailycsnades.json, fetched by tools/fetch_dailycsnades.py)
give where the thrower stood and where the grenade landed, but not the aim: on their own nobody can throw them. Each
one is matched here with the real throws of the base (matchmaking and pro demos) from the same spot (40 units, same
height) landing at the same place (120 units): their largest group of aims gives the exact setpos/setang and the
technique (jump, running, crouching, the click). Kept: the lineups found at least twice, with how often the base and
the pros throw them. Writes out/site/nadecat/<map>.json for the Maps tab; skipped while the base has not grown by a
quarter since (like the other caches).
Usage: python nades_catalog.py [map ...]"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

import config
import nades

CAT = os.path.join(config.OUT, "lineups")
OUT = os.path.join(config.OUT, "site", "nadecat")
DEEP_PRO = os.path.join(config.OUT, "deep_pro")
TYPE = {"smoke": "smoke", "flash": "flash", "he": "he", "molotov": "molotov", "incendiary": "molotov"}
POS_R, POS_Z, LAND_R = 40, 24, 120   # same spot (units), same height, same landing
MIN_THROWS = 2
COLS = ["type", "side", "X", "Y", "Z", "pitch", "yaw", "jump", "speed", "crouch", "walk", "click", "px", "py", "level", "zone",
        "land_X", "land_Y", "land_Z", "land_px", "land_py", "land_level", "land_zone"]


def maps():
    return sorted(os.path.basename(f)[:-len("_dailycsnades.json")] for f in glob.glob(os.path.join(CAT, "*_dailycsnades.json")))


def _throws(mp):
    """Every throw of the base and of the pro demos on that map, with the pro flag."""
    out = []
    for base, pro in ((config.DEEP, False), (DEEP_PRO, True)):
        for d in glob.glob(os.path.join(base, "*")):
            try:
                if json.load(open(os.path.join(d, "meta.json"), encoding="utf-8")).get("map") != mp:
                    continue
                g = pd.read_parquet(os.path.join(d, "grenades.parquet"))
            except (OSError, ValueError):
                continue
            out.append(g[[c for c in COLS if c in g.columns]].assign(pro=pro))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS + ["pro"])


def build(mp):
    cat = json.load(open(os.path.join(CAT, f"{mp}_dailycsnades.json"), encoding="utf-8")).get("lineups", [])
    G = _throws(mp)
    if not len(G) or not cat:
        return None
    P, L = G[["X", "Y", "Z"]].to_numpy(float), G[["land_X", "land_Y"]].to_numpy(float)
    ty, sd = G.type.to_numpy(), G.side.to_numpy()
    found = {}
    for c in cat:
        t = TYPE.get(str(c.get("type") or "").lower())
        p, l = c.get("position"), c.get("landing")
        if not t or not p or not l or len(p) < 3:
            continue
        m = (ty == t) & (np.hypot(P[:, 0] - p[0], P[:, 1] - p[1]) <= POS_R) & (np.abs(P[:, 2] - p[2]) <= POS_Z) \
            & (np.hypot(L[:, 0] - l[0], L[:, 1] - l[1]) <= LAND_R)
        if c.get("side") in ("T", "CT"):
            m &= sd == c["side"]
        g = G[m]
        if len(g) < MIN_THROWS:
            continue
        key = list(zip(g.pitch.round(0), g.yaw.round(0), g.jump.astype(bool), g.crouch.astype(bool)))
        top = pd.Series(key).value_counts()
        best = g[[k == top.index[0] for k in key]]
        if len(best) < MIN_THROWS:
            continue
        b = best.median(numeric_only=True)
        one = best.iloc[0]
        rec = {"type": t, "side": str(one.side), "uses": int(len(best)), "pro_uses": int(best.pro.sum()),
               "from_zone": nades.humanize(best.zone.mode().iloc[0], mp) if best.zone.notna().any() else None,
               "to_zone": nades.humanize(best.land_zone.mode().iloc[0], mp) if best.land_zone.notna().any() else None,
               "title": c.get("title"), "how": nades._how(pd.Series({"jump": bool(best.jump.mode().iloc[0]), "speed": float(b.speed),
                                                                      "walk": bool(best.walk.mode().iloc[0]), "crouch": bool(best.crouch.mode().iloc[0])})),
               "click": str(best.click.mode().iloc[0]) if "click" in best and best.click.notna().any() else None,
               "level": str(best.level.mode().iloc[0]) if best.level.notna().any() else None,
               "land_level": str(best.land_level.mode().iloc[0]) if best.land_level.notna().any() else None,
               "px": [round(float(b.px), 1), round(float(b.py), 1)], "land_px": [round(float(b.land_px), 1), round(float(b.land_py), 1)],
               "setpos": f"setpos {b.X:.1f} {b.Y:.1f} {b.Z:.1f}; setang {b.pitch:.2f} {b.yaw:.2f} 0"}
        k = (t, round(b.X / 16), round(b.Y / 16), round(b.pitch), round(b.yaw))   # the same lineup listed by several pros
        cur = found.get(k)
        pro = c.get("player")
        if cur:
            if pro and pro not in cur["pros"]:
                cur["pros"].append(pro)
            continue
        found[k] = {**rec, "pros": [pro] if pro else []}
    res = sorted(found.values(), key=lambda x: (-x["uses"], x["type"]))
    return {"map": mp, "n_catalog": len(cat), "n_throws": int(len(G)), "found": len(res),
            "source": {"label": "Daily CS Nades, pro grenade dataset", "url": "https://dailycsnades.com"}, "lineups": res}


def run_all(only=None, log=print):
    os.makedirs(OUT, exist_ok=True)
    n_demos = len(glob.glob(os.path.join(config.DEEP, "*", "grenades.parquet")))
    for mp in only or maps():
        f = os.path.join(OUT, f"{mp}.json")
        try:
            cur = json.load(open(f, encoding="utf-8"))
            if not only and cur.get("_demos", 0) >= 0.8 * n_demos:
                continue
        except (OSError, ValueError):
            pass
        r = build(mp)
        if r:
            r["_demos"] = n_demos
            config.write_json(f, r)
            log(f"{mp}: {r['found']} of the {r['n_catalog']} catalog lineups found in {r['n_throws']} real throws")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run_all(sys.argv[1:] or None)
