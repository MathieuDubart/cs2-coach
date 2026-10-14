"""Lineups from the clips you send (07/10, the user: "Essaye de récupérer ces stuffs", four X posts: ZywOo's Anubis A
combo, kyxsan's Mirage connector + short, two Gold CS Nades lineups).

A clip shows a lineup, not its numbers: each one is looked at (the map, the spot, the aim, where it lands) and written
below as a probe; the base's demos (matchmaking and pro) then give the exact throw: the same grenade from the same spot
(40 u), the same aim (2.5 degrees) landing at the same place (150 u). Their median is the setpos / setang, their usual
technique the "how", their count how often the base and the pros throw it. Out: out/lineups/clips.json, read by the
In-game stuff tab and the training (each clip's grenades one after the other, in the clip's order).
Usage: python clips.py   (resolves the probes again: the base grows)"""
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd

import config
from i18n import N_

OUT = os.path.join(config.OUT, "lineups", "clips.json")
POS_R, POS_Z, ANG, LAND_R = 40.0, 40.0, 2.5, 150.0

# the clips: what each one shows, as probes (spot, aim, where it lands) the base's throws are matched with; "exact": the
# probe is a real throw of a pro demo (the clip's own player or another pro the same way), kept as it is
CLIPS = [
    {"id": "x2107287958634275182", "url": "https://x.com/NadesOutHere/status/2107287958634275182", "author": "Nades Out Here",
     "handle": "NadesOutHere", "date": "2026-10-06", "map": "de_anubis", "side": "T", "title": N_("ZywOo's A execute from Canal"),
     "text": N_("ZywOo's Anubis A-site utility combo: he smokes Heaven, molotovs Broken Wall, then follows it with the A-site flashes."),
     "seen": N_("ZywOo throws it from the same spot in two of the base's pro demos (Vitality); in the clip at 1:25, 1:20 and 1:18"),
     "throws": [
         {"type": "smoke", "label": "Heaven", "pos": [744.0, 626.0, -152.0], "ang": [-2.38, 79.32], "land": [1046, 2242, -38], "t": 30, "how": "standing still", "exact": True},
         {"type": "molotov", "label": "Broken Wall", "pos": [744.0, 626.0, -152.0], "ang": [-0.84, 73.47], "land": [798, 1500, -88], "t": 35, "how": "jumpthrow", "exact": True},
         {"type": "flash", "label": "A site", "pos": [744.0, 626.0, -152.0], "ang": [0.48, 54.68], "land": [1233, 1443, 150], "t": 37, "how": "jumpthrow", "exact": True},
     ]},
    {"id": "x2107093457420632194", "url": "https://x.com/NadesOutHere/status/2107093457420632194", "author": "Nades Out Here",
     "handle": "NadesOutHere", "date": "2026-10-05", "map": "de_mirage", "side": "T", "title": N_("kyxsan's Connector smoke + Short molotov"),
     "text": N_("kyxsan's Mirage Connector smoke + Short molotov combo, from Top of Mid."),
     "seen": N_("the same two grenades from the same spot, 2 s apart, in a pro demo (biguzera); in the clip at 1:41 and 1:39; the smoke is the base's usual one"),
     "throws": [
         {"type": "smoke", "label": "Connector", "pos": [503.0, -64.0, -160.0], "ang": [-13.92, -147.16], "land": [-667, -899, -246], "t": 14, "how": "standing still", "exact": True},
         {"type": "molotov", "label": "Short", "pos": [503.0, -64.0, -160.0], "ang": [-0.53, 176.49], "land": [-880, 17, -38], "t": 16, "how": "jumpthrow", "exact": True},
     ]},
    {"id": "x2106987750364741874", "url": "https://x.com/goldcsnades/status/2106987750364741874", "author": "Gold CS Nades",
     "handle": "goldcsnades", "date": "2026-10-05", "map": "de_mirage", "side": "T", "title": N_("Giant smoke: CT from T spawn"),
     "text": N_("New GIANT SMOKE lineup: from spawn, left click + jumpthrow, it flies over the roofs to the CT gate."),
     "seen": N_("matched by the clip's look (T spawn, the aim on a rooftop, the gate it lands at): the base's CT smoke from T spawn"),
     "check": N_("the clip shows no map: check the spot in game (Dust 2's mid doors smoke from T spawn looks alike)"),
     "throws": [
         {"type": "smoke", "label": "CT", "pos": [1258.0, -872.0, -138.0], "ang": [-21.4, -144.0], "land": [-849, -2422, -170], "t": 2, "how": "jumpthrow"},
     ]},
    {"id": "x2107184046346559830", "url": "https://x.com/goldcsnades/status/2107184046346559830", "author": "Gold CS Nades",
     "handle": "goldcsnades", "date": "2026-10-05", "map": "de_ancient", "side": "T", "title": N_("All A entry smokes from one spot"),
     "text": N_("All A site entry smokes from ONE position, each a left click + jumpthrow."),
     "seen": N_("the spot pros use outside A Main for the same smokes (each a jumpthrow), from the base's pro demos"),
     "check": N_("the clip's spot could also be the one 250 u further up the stairs (the base's matchmaking players' spot)"),
     "throws": [
         {"type": "smoke", "label": "Donut exit", "pos": [-2144.0, -1004.0, 0.0], "ang": [-37.9, 71.9], "land": [-1334, 354, 89], "how": "jumpthrow"},
         {"type": "smoke", "label": "A site", "pos": [-2144.0, -1004.0, 0.0], "ang": [-29.8, 66.1], "land": [-1192, 918, 54], "how": "jumpthrow"},
         {"type": "smoke", "label": "back of A site", "pos": [-2144.0, -1004.0, 0.0], "ang": [-28.7, 60.7], "land": [-1124, 1153, 55], "how": "jumpthrow"},
         {"type": "smoke", "label": "Donut", "pos": [-2144.0, -1004.0, 0.0], "ang": [-44.3, 42.7], "land": [-1324, 42, 105], "how": "jumpthrow"},
     ]},
]

COLS = ["t", "type", "side", "X", "Y", "Z", "pitch", "yaw", "jump", "speed", "crouch", "walk", "click", "zone",
        "land_X", "land_Y", "land_Z", "land_zone"]


def _throws(mp):
    """Every throw of the map in the base and the pro demos, with the pro's name for the pro ones."""
    out = []
    for base, pro in ((config.DEEP, False), (os.path.join(config.OUT, "deep_pro"), True)):
        for d in glob.glob(os.path.join(base, "*")):
            try:
                with open(os.path.join(d, "meta.json"), encoding="utf-8") as fh:
                    if json.load(fh).get("map") != mp:
                        continue
                g = pd.read_parquet(os.path.join(d, "grenades.parquet"))
            except (OSError, ValueError):
                continue
            if "side" not in g.columns:
                continue
            g = g[[c for c in COLS + ["thrower_name"] if c in g.columns]].assign(pro=pro)
            if not pro and "thrower_name" in g.columns:
                g = g.drop(columns=["thrower_name"])
            out.append(g)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS + ["pro"])


def _resolve(G, side, mp, pr):
    """A probe's throws in the base: the exact spot, aim and technique, where they land, how often."""
    import nades
    p, a, l = pr["pos"], pr["ang"], pr["land"]
    m = (G.type == pr["type"]) & (G.side == side) & (np.hypot(G.X - p[0], G.Y - p[1]) <= POS_R) \
        & ((G.pitch - a[0]).abs() <= ANG) & (((G.yaw - a[1] + 180) % 360 - 180).abs() <= ANG) \
        & (np.hypot(G.land_X - l[0], G.land_Y - l[1]) <= LAND_R)
    if p[2]:
        m &= (G.Z - p[2]).abs() <= POS_Z
    g = G[m]
    # t: seconds after the freeze time, the clip's own moment (its clock) or else the base's usual one
    rec = {"type": pr["type"], "uses": int(len(g)), "pro_uses": int(g.pro.sum()) if len(g) else 0,
           "t": pr.get("t", round(float(g.t.median())) if len(g) and "t" in g and g.t.notna().any() else None)}
    if len(g) and not pr.get("exact"):
        # the lineup is one exact spot and aim (a corner, a pixel): the most common one, not a median that would blend
        # two near ones (a median of 35 Heaven smokes gave a spot 15 u off ZywOo's)
        key = list(zip(g.X.round(0), g.Y.round(0), g.pitch.round(1), g.yaw.round(1)))
        top = pd.Series(key).value_counts().index[0]
        e = g[[k == top for k in key]]
        b = e.median(numeric_only=True)
        still = e[~e.jump.astype(bool)]
        z = float(still.Z.median()) if len(still) else float(e.Z.min())   # a jumpthrow's lowest release: at the ground or just above
        how = pr.get("how") or nades._how(pd.Series({"jump": bool(e.jump.mode().iloc[0]), "speed": float(b.speed),
                                                     "walk": bool(e.walk.mode().iloc[0]), "crouch": bool(e.crouch.mode().iloc[0])}))
        pos, ang = [round(float(b.X), 1), round(float(b.Y), 1), round(z, 1)], [round(float(b.pitch), 2), round(float(b.yaw), 2)]
        land = [round(float(v), 1) for v in e[["land_X", "land_Y", "land_Z"]].dropna().median().tolist()] or l
        rec.update(how=how, pos=pos, ang=ang, land=land)
    else:   # a pro demo's own throw, or not in the base (yet): the probe as it is
        rec.update(how=pr.get("how") or "standing still", pos=[float(v) for v in p], ang=[float(v) for v in a], land=[float(v) for v in l])
    if len(g):
        rec.update(from_zone=nades.humanize(g.zone.mode().iloc[0], mp) if g.zone.notna().any() else None,
                   to_zone=nades.humanize(g.land_zone.mode().iloc[0], mp) if g.land_zone.notna().any() else None,
                   pros=sorted({str(n) for n in g.get("thrower_name", pd.Series(dtype=str)).dropna()})[:6])
    else:
        rec.update(from_zone=None, to_zone=None, pros=[])
    try:   # on the radar (the Maps tab draws it like the pro catalog's cards)
        import mapdata
        cfg = mapdata.get(mp)
        f = cfg.get("px_factor", 1.0)
        px = lambda x, y: [round((x - cfg["pos_x"]) / cfg["scale"] * f, 1), round((cfg["pos_y"] - y) / cfg["scale"] * f, 1)]
        rec.update(px=px(*rec["pos"][:2]), land_px=px(*rec["land"][:2]), level=mapdata.level_of(cfg, rec["pos"][2]),
                   land_level=mapdata.level_of(cfg, rec["land"][2]) if len(rec["land"]) > 2 else None)
    except Exception as e:
        print("clips radar:", e)
    rec["to"] = pr.get("label") or rec.get("to_zone") or "?"
    rec["click"] = "left click"
    rec["setpos"] = f"setpos {rec['pos'][0]} {rec['pos'][1]} {rec['pos'][2]}; setang {rec['ang'][0]} {rec['ang'][1]} 0"
    return rec


def refresh(log=print):
    out = {"t": time.time(), "clips": []}
    cache = {}
    for c in CLIPS:
        mp = c["map"]
        if mp not in cache:
            cache[mp] = _throws(mp)
        G = cache[mp]
        throws = [_resolve(G, c["side"], mp, pr) for pr in c["throws"]]
        out["clips"].append({k: v for k, v in c.items() if k != "throws"} | {"throws": throws})
        log(f"{c['title']} ({mp}): " + ", ".join(f"{x['type']} → {x['to']} {x['how']} ({x['uses']} in the base, {x['pro_uses']} by pros)" for x in throws))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    config.write_json(OUT, out)
    return out


def load(mp=None):
    try:
        with open(OUT, encoding="utf-8") as fh:
            C = json.load(fh).get("clips") or []
    except (OSError, ValueError):
        return []
    return [c for c in C if mp is None or c["map"] == mp]


def by_map():
    out = {}
    for c in load():
        out.setdefault(c["map"], []).append(c)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    refresh()
