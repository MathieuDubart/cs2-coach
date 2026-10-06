"""The training session: one Play, the whole block in the time you chose, on the training server (replay.py).

Three blocks per map, in this order: aim on the map, stuff, situations.
- Aim: your real duel spots. You stand where you fought in your matches, and the bots appear one by one where your
  enemies were in those duels (they hold the spot and shoot back). The zones where you died most come first.
- Stuff: the lineups your plan recommends for the zones you play. A new one is guided (exact spot and aim, how to
  throw); once you landed it, only the spot and how; then only the spot.
- Situations: your replays (lost 1v1/1v2, opening deaths not traded…).
Everything comes back by Leitner boxes: a miss comes back at the next session, a success later and later; the rest of
each block is drawn at random among the important ones. Each drill scores points (streaks multiply them): XP, levels.

Maps: one map, a random one (weighted by what you play), or a mix of up to 3 (one changelevel per map)."""
import json
import math
import os
import random
import time
from collections import Counter

import numpy as np
import pandas as pd

import config
import replay

STATE_F = os.path.join(config.OUT, "train_progress.json")
SITES_F = os.path.join(config.OUT, "train_sites.json")
SESS = os.path.join(replay.COACH, "sessions")
# share of the time of each block: defending a site (CT), the push routes with their prefires (T), the stuff, the
# situations (04/10: "a CT training, then a T one: the push routes"); a warm-up (5 min) is the first two only
SPLIT = {"defend": 0.17, "push": 0.17, "aim": 0.34, "nade": 0.2, "situation": 0.46, "wallbang": 0.12}   # before 06/10 (kept for the old sessions' files)
# the warm-up (06/10, the user: "tout l'entraînement sur le même serveur comme avant, le bouton warmup pour tout lancer:
# de l'aim, de la défense de bomb site, du chemin de prefire, du stuff, du wallbang"): one session in that order, each
# part's share of the time by the session's length (5 min: the hands only)
ORDER = ["aim", "defend", "push", "nade", "wallbang", "situation"]


def splits(minutes):
    if minutes <= 5:
        return {"aim": 0.4, "defend": 0.3, "push": 0.3}
    if minutes <= 10:
        return {"aim": 0.2, "defend": 0.15, "push": 0.15, "nade": 0.2, "wallbang": 0.1, "situation": 0.2}
    if minutes <= 20:
        return {"aim": 0.15, "defend": 0.15, "push": 0.15, "nade": 0.15, "wallbang": 0.1, "situation": 0.3}
    return {"aim": 0.12, "defend": 0.15, "push": 0.15, "nade": 0.15, "wallbang": 0.12, "situation": 0.31}
WARMUP = {"defend": 0.5, "push": 0.5, "aim": 1.0}
WARMUP_MIN = 5
EST = {"defend": 110, "push": 75, "aim": 85, "nade": 40, "situation": 45, "wallbang": 60}   # seconds a drill takes, about (with a retry)
RIFLE = {2: "weapon_ak47", 3: "weapon_m4a1"}
PRIMARY = {"AK-47": "ak47", "M4A4": "m4a1", "M4A1-S": "m4a1_silencer", "AWP": "awp", "Galil AR": "galilar",
           "FAMAS": "famas", "SG 553": "sg556", "AUG": "aug", "SSG 08": "ssg08", "MP9": "mp9", "MAC-10": "mac10"}
NADE_ITEM = {"smoke": "weapon_smokegrenade", "flash": "weapon_flashbang", "he": "weapon_hegrenade",
             "molotov": {2: "weapon_molotov", 3: "weapon_incgrenade"}}


# ---------------------------------------------------------------- progress (XP, Leitner boxes)

def progress():
    try:
        p = json.load(open(STATE_F, encoding="utf-8"))
    except (OSError, ValueError):
        p = {}
    p.setdefault("xp", 0)
    p.setdefault("sessions", [])
    p.setdefault("items", {})
    p.setdefault("read", 0)
    return p


def _save(p):
    json.dump(p, open(STATE_F, "w", encoding="utf-8"), ensure_ascii=False)


def level(xp):
    """Level n needs 300 * n * (n - 1) / 2 XP: 300 to reach level 2, 900 to level 3, 1800 to level 4…"""
    n = int((1 + math.sqrt(1 + 8 * xp / 300)) / 2)
    lo, hi = 300 * n * (n - 1) // 2, 300 * (n + 1) * n // 2
    return {"level": n, "xp": xp, "from": lo, "to": hi}


def ingest():
    """The plugin's results since last time: points, boxes of the items, finished sessions."""
    p = progress()
    try:
        lines = open(os.path.join(replay.COACH, "results.jsonl"), encoding="utf-8").read().splitlines()
    except OSError:
        return p
    n = len(p["sessions"])
    for ln in lines[p["read"]:]:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not r.get("session"):
            continue
        if r.get("end"):
            s = next((x for x in p["sessions"] if x["id"] == r["session"]), None)
            if s is not None:
                s.update(done=True, points=r.get("points", 0), ok=r.get("ok", 0), drills=r.get("drills", 0))
            continue
        p["xp"] += int(r.get("points") or 0)
        it = p["items"].setdefault(r["drill"], {"box": 0, "next": 0, "n": 0, "ok": 0})
        it["n"] += 1
        if r.get("ok"):
            it["ok"] += 1
            it["box"] = min(3, it["box"] + 1)
            it["next"] = n - 1 + 2 ** it["box"]   # 2, 4, 8 sessions later (n: sessions so far, this one included)
        else:
            it["box"] = 0
            it["next"] = n   # the next session
        it["last"] = r.get("outcome")
    p["read"] = len(lines)
    _save(p)
    return p


def _pick(cands, n, items, nsess, key=lambda c: c["id"], weight=lambda c: 1.0):
    """Due items first (the ones missed come back), then new or not yet due ones at random, weighted by importance."""
    due = [c for c in cands if key(c) in items and items[key(c)]["next"] <= nsess]
    due.sort(key=lambda c: (items[key(c)]["box"], items[key(c)]["next"]))
    rest = [c for c in cands if c not in due]
    out = due[:n]
    if len(out) < n and rest:
        w = np.array([max(0.05, weight(c)) * (2.0 if key(c) not in items else 1.0) for c in rest], dtype=float)
        k = min(n - len(out), len(rest))
        idx = np.random.choice(len(rest), size=k, replace=False, p=w / w.sum())
        out += [rest[i] for i in idx]
    return out


# ---------------------------------------------------------------- the drills of a map

def _my_matches(sid, mp=None):
    md = os.path.join(config.player_dir(sid), "matches")
    out = []
    for mid in os.listdir(md) if os.path.isdir(md) else []:
        deep = os.path.join(config.OUT, "deep", mid)
        try:
            m = json.load(open(os.path.join(deep, "meta.json"), encoding="utf-8"))["map"]
        except (OSError, ValueError, KeyError):
            continue
        if os.path.exists(os.path.join(deep, "duels.parquet")) and (mp is None or m == mp):
            out.append((mid, m))
    return out


def maps(sid):
    """Your maps with their number of matches (with demo)."""
    c = {}
    for _, m in _my_matches(sid):
        c[m] = c.get(m, 0) + 1
    return dict(sorted(c.items(), key=lambda x: -x[1]))


def _angle(a, b):
    d = np.asarray(b, float) - np.asarray(a, float)
    yaw = math.degrees(math.atan2(d[1], d[0]))
    pitch = -math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return [round(pitch, 1), round(yaw, 1)]


def aim_drills(sid, mp):
    """Your duel spots on this map: you where you fought, the enemies where they were (one drill per zone and side)."""
    sid = str(sid)
    rows = []
    for mid, _ in _my_matches(sid, mp):
        deep = os.path.join(config.OUT, "deep", mid)
        D = pd.read_parquet(os.path.join(deep, "duels.parquet"))
        D["killer"], D["victim"] = D.killer.astype(str), D.victim.astype(str)
        L = pd.read_parquet(os.path.join(deep, "loadout.parquet"), columns=["round", "steamid", "primary"])
        L = L[L.steamid.astype(str) == sid].set_index("round").primary
        for _, d in D[(D.killer == sid) | (D.victim == sid)].iterrows():
            me = "killer" if d.killer == sid else "victim"
            en = "victim" if me == "killer" else "killer"
            if d[f"{me}_side"] == d[f"{en}_side"]:
                continue
            rows.append({"side": d[f"{me}_side"], "zone": d[f"{me}_zone"], "died": me == "victim", "weapon": L.get(d["round"]),
                         "me": (float(d[f"{me}_X"]), float(d[f"{me}_Y"]), float(d[f"{me}_Z"])),
                         "en": (float(d[f"{en}_X"]), float(d[f"{en}_Y"]), float(d[f"{en}_Z"])),
                         "en_zone": d[f"{en}_zone"]})
    if not rows:
        return []
    R = pd.DataFrame(rows)
    out = []
    for (side, zone), g in R.groupby(["side", "zone"]):
        if len(g) < 3 or not isinstance(zone, str) or zone in ("?", ""):
            continue
        # your most frequent spot in the zone, and only the duels you took from there: their enemies were in sight
        P = np.array(g.me.tolist())
        near = None
        for rad in (220, 350):
            d2 = np.sqrt(((P[:, None, :2] - P[None, :, :2]) ** 2).sum(-1))
            close = (d2 <= rad) & (np.abs(P[:, None, 2] - P[None, :, 2]) < 100)
            k = int(np.argmax(close.sum(1) * 10 + g.died.to_numpy()))
            near = g[close[k]]
            mine = P[k]
            enemies, seen = [], []
            E = list(zip(near.en, near.en_zone))
            random.shuffle(E)
            for e, ez in E:   # distinct spots (150 u apart), not too far, 5 at most
                if all(math.dist(e, s_) > 150 for s_ in seen) and 150 < math.dist(e, mine) < 1800:
                    seen.append(e)
                    enemies.append({"pos": [round(v, 1) for v in e], "zone": replay_zone(ez, mp)})
                if len(enemies) >= 5:
                    break
            if len(enemies) >= 2:
                break
        if len(enemies) < 2:
            continue
        team = 2 if side == "T" else 3
        w = g.weapon.dropna()
        wp = PRIMARY.get(w.mode().iloc[0]) if len(w) else None
        died = int(near.died.sum())
        out.append({"id": f"aim:{mp}:{side}:{zone}", "kind": "aim", "map": mp, "title": f"{replay_zone(zone, mp)} ({side})",
                    "tip": f"{len(enemies)} enemies, one by one, where they were when you fought here" + (f" · you died here {died}×" if died else ""),
                    "team": team, "me": {"pos": [round(float(v), 1) for v in mine], "ang": _angle(mine, enemies[0]["pos"])},
                    "weapons": ["weapon_knife", f"weapon_{wp}" if wp else RIFLE[team]],
                    "bot_weapons": ["weapon_knife", RIFLE[5 - team]],
                    "bots": [{"pos": e["pos"], "ang": _angle(e["pos"], mine), "zone": e["zone"]} for e in enemies],
                    "weight": 1 + 2 * died + len(near)})
    return out


# ---------------------------------------------------------------- the aim block on the game's aim map (06/10)

AIM_MAP = "aim_map"


def _my_guns(sid):
    """The guns you play (your demos): your T rifle, your CT rifle, your pistol (the default one unless you play another
    one a lot)."""
    t, ct, pist = Counter(), Counter(), Counter()
    for mid, _ in _my_matches(str(sid)):
        try:
            L = pd.read_parquet(os.path.join(config.OUT, "deep", mid, "loadout.parquet"), columns=["steamid", "side", "primary", "pistol"])
        except Exception:
            continue
        L = L[L.steamid.astype(str) == str(sid)]
        t.update(L[L.side == "T"].primary.dropna())
        ct.update(L[L.side == "CT"].primary.dropna())
        pist.update(L.pistol.dropna())
    rifle = lambda c, names, dflt: next((n for n, _ in c.most_common() if n in names and replay._item(n)), dflt)
    tr = rifle(t, ("AK-47", "Galil AR", "SG 553"), "AK-47")
    cr = rifle(ct, ("M4A1-S", "M4A4", "FAMAS", "AUG"), "M4A1-S")
    n = sum(pist.values()) or 1
    pi = next((p for p, k in pist.most_common() if p not in ("Glock-18", "USP-S", "P2000") and k >= 0.15 * n and replay._item(p)), "USP-S")
    return tr, cr, pi


def aim_range_drills(sid, secs):
    """The aim block (06/10, the user: "fais le travail d'aim sur une map d'aim, une map d'entraînement d'aim, et
    ensuite lance les maps que j'ai choisies"; the duel spots on the maps spawned in front of him or behind him and
    prefired him): on the game's aim_map, targets across the map in front of you: still ones to flick to, strafing
    ones, then duels that shoot back only after a player's reaction time; your guns. As many as the block's time holds."""
    tr, cr, pi = _my_guns(sid)
    w = lambda n: replay._item(n) or "weapon_ak47"
    menu = [
        {"variant": "flick", "gun": tr, "secs": 60, "count": 3, "goal": 25,
         "tip": "still targets across the map: flick to the head, one bullet · they don't shoot"},
        {"variant": "strafe", "gun": cr, "secs": 50, "count": 2, "goal": 14,
         "tip": "strafing targets: stop, then shoot (counter-strafe) · they don't shoot"},
        {"variant": "duel", "gun": tr, "secs": 60, "count": 2, "goal": 12,
         "tip": "duels: they shoot back once they've seen you a player's reaction time · you respawn"},
        {"variant": "flick", "gun": pi, "secs": 45, "count": 3, "goal": 15,
         "tip": "pistol: still targets, head only · they don't shoot"},
    ]
    out, used, k = [], 0, 0
    while used < secs - 20 and k < 8:
        m = menu[k % len(menu)]
        k += 1
        name = {"flick": "FLICKS", "strafe": "STRAFE", "duel": "DUELS"}[m["variant"]]
        out.append({"id": f"range:{m['variant']}:{m['gun']}", "kind": "aim", "mode": "range", "variant": m["variant"], "map": AIM_MAP,
                    "title": f"{name} · {m['gun']}", "tip": m["tip"], "team": 2,
                    "weapons": ["weapon_knife", w(m["gun"])] if m["gun"] == pi else ["weapon_knife", "weapon_glock", w(m["gun"])],
                    "bot_weapons": ["weapon_knife", RIFLE[3]], "seconds": m["secs"], "count": m["count"], "goal": m["goal"],
                    "clock": m["secs"]})
        used += m["secs"] + 12
    return out


# a prefire's angles by the bots' level (06/10, the user: "en expert les bots vraiment partout, en normal le maximum
# mais un peu moins, en simple vraiment beaucoup moins: les positions les plus fortes, les plus jouées")
PREFIRE_N = {0: 4, 1: 7, 2: 9, 3: 10}


def _by_level(d, difficulty):
    b = d["bots"][:PREFIRE_N.get(int(difficulty), 9)]   # the most played first
    m = min((x.get("at", 0) for x in b), default=0)
    d["bots"] = [dict(x, at=round(x.get("at", 0) - m, 1)) for x in b]
    return d


# ---------------------------------------------------------------- aim like on practice servers

def _cells(P, cell=110):
    """Positions grouped by cells of 110 u (and height): (count, median position) the busiest first."""
    if not len(P):
        return []
    P = np.asarray(P, float)
    key = np.stack([np.floor(P[:, 0] / cell), np.floor(P[:, 1] / cell), np.floor(P[:, 2] / 90)], 1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    out = [(int(cnt[k]), np.median(P[inv.ravel() == k], axis=0)) for k in range(len(cnt))]
    return sorted(out, key=lambda x: -x[0])


def _spread(cands, n, gap=160, keep=lambda p: True):
    out = []
    for c, p in cands:
        if keep(p) and all(math.dist(p, q) > gap for _, q in out):
            out.append((c, p))
        if len(out) >= n:
            break
    return out


def _hold_t(CP, tm, p):
    """When the CTs fight from that spot (median time in the round): the peek timing."""
    near = np.hypot(CP[:, 0] - p[0], CP[:, 1] - p[1]) < 110
    return round(float(np.median(tm[near] if near.any() else tm)), 1)


def site_data(mp):
    """From every demo of the map (the whole base, not only yours): for each bomb site, the spots CTs hold it from (the
    duels of the first 75 s of a round, CT within 1500 u of the site) and where the Ts come from (entrance zones, with
    their spots). Each spot keeps where the Ts it fought stood ("seen", 40 at most: the two saw each other, so a way
    that passes there is in its sight, 06/10) and how often its CTs fought crouched. Cached per map, rebuilt when the
    base grows."""
    try:
        cache = json.load(open(SITES_F, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    dirs = _map_dirs(mp)
    # computed again when the map has a quarter more matches (the base grows by itself: not at every Play)
    if mp in cache and cache[mp].get("v") == 5 and cache[mp].get("n", 0) >= 0.8 * len(dirs):
        return cache[mp]
    cols = ["t", "killer_side", "victim_side", "killer_zone", "victim_zone", "killer_crouch", "victim_crouch",
            "killer_X", "killer_Y", "killer_Z", "victim_X", "victim_Y", "victim_Z"]
    parts = []
    for d in dirs:
        try:
            D = pd.read_parquet(os.path.join(config.OUT, "deep", d, "duels.parquet"), columns=cols)
        except Exception:
            continue
        D = D[(D.t <= 75) & (((D.killer_side == "CT") & (D.victim_side == "T")) | ((D.killer_side == "T") & (D.victim_side == "CT")))]
        if not len(D):
            continue
        ck = (D.killer_side == "CT").to_numpy()
        col = lambda a, ct: np.where(ck == ct, D[f"killer_{a}"].to_numpy(), D[f"victim_{a}"].to_numpy())
        parts.append(pd.DataFrame({"time": D.t.to_numpy(float),
                                   "ctx": col("X", True), "cty": col("Y", True), "ctz": col("Z", True), "ct_zone": col("zone", True),
                                   "ct_crouch": col("crouch", True), "tx": col("X", False), "ty": col("Y", False), "tz": col("Z", False),
                                   "t_zone": col("zone", False)}))
    R = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    sites = {}
    if len(R):
        R = R.dropna(subset=["ctx", "cty", "ctz", "tx", "ty", "tz"])
        CA = R[["ctx", "cty", "ctz"]].to_numpy(float)
        rng = np.random.default_rng(0)
        for z in sorted({z for z in R.ct_zone.dropna().unique() if "Bombsite" in str(z)}):
            S = R[R.ct_zone == z]
            if len(S) < 25:
                continue
            cen = np.median(S[["ctx", "cty", "ctz"]].to_numpy(float), axis=0)
            near = R[(np.linalg.norm(CA - cen, axis=1) < 1500) & (np.abs(CA[:, 2] - cen[2]) < 300)]   # its own floor (Nuke: A is above B)
            ents = []
            for tz, g in near.groupby("t_zone"):   # where the Ts were when they fought the site's CTs
                if not isinstance(tz, str) or tz == z or len(g) < 12:
                    continue
                T = g[["tx", "ty", "tz"]].to_numpy(float)
                dist = float(np.median(np.linalg.norm(T - cen, axis=1)))
                if dist < 500:
                    continue
                CP = g[["ctx", "cty", "ctz"]].to_numpy(float)
                holds = _spread(_cells(CP), 12)   # the CT spots facing that entrance
                tm = g.time.to_numpy()
                spawn = _spread(_cells(T), 3, gap=200, keep=lambda p: math.dist(p, cen) > 700)
                if len(holds) < 4 or not spawn:
                    continue
                tcen = np.median(T, axis=0)
                cr = g.ct_crouch.fillna(False).astype(bool).to_numpy()
                hs = []
                for c, p in holds:
                    m = (np.hypot(CP[:, 0] - p[0], CP[:, 1] - p[1]) < 110) & (np.abs(CP[:, 2] - p[2]) < 90)
                    Tm = T[m]
                    if len(Tm) > 40:
                        Tm = Tm[rng.choice(len(Tm), 40, replace=False)]
                    hs.append({"pos": [round(float(v), 1) for v in p], "ang": _angle(p, tcen), "n": c, "t": _hold_t(CP, tm, p),
                               "zone": _hold_zone(CP, g.ct_zone.to_numpy(), p, mp), "seen": [[round(float(v)) for v in q] for q in Tm],
                               "crouch": round(float(cr[m].mean()), 2) if m.any() else 0.0})
                ents.append({"zone": tz, "n": int(len(g)), "dist": round(dist),
                             "start": [round(float(v), 1) for v in _spread(_cells(T), 1)[0][1]], "holds": hs,
                             "spawns": [[round(float(v), 1) for v in p] for _, p in spawn]})
            ents.sort(key=lambda e: -e["n"])
            spot = _spread(_cells(S[["ctx", "cty", "ctz"]].to_numpy(float)), 1)[0][1]   # the CTs' favourite spot on the site
            sites[z] = {"center": [round(float(v), 1) for v in cen], "defend": [round(float(v), 1) for v in spot], "entrances": ents[:4]}
    cache[mp] = {"n": len(dirs), "v": 5, "sites": sites}
    json.dump(cache, open(SITES_F, "w", encoding="utf-8"))
    return cache[mp]


def _site_holds(S):
    """A site's CT spots from all its entrances, the ones 160 u apart merged (their counts and their foes summed), the
    most held first."""
    out = []
    for h in sorted((h for e in S["entrances"] for h in e["holds"]), key=lambda h: -h["n"]):
        same = next((q for q in out if math.dist(h["pos"], q["pos"]) <= 160), None)
        if same:
            same["n"] += h["n"]
            same["seen"] = same["seen"] + list(h.get("seen") or [])
            continue
        out.append(dict(h, seen=list(h.get("seen") or [])))
    return out


def _sees(h, P, r=160.0, dz=110.0):
    """How many of a CT spot's foes stood on that way (its points within r, same floor): the duels prove the two saw
    each other, so the way passes in the spot's sight. 0: never seen fighting from there."""
    Q = np.array(h.get("seen") or [], float).reshape(-1, 3)
    W = np.asarray(P, float)[:, :3]
    if not len(Q) or not len(W):
        return 0
    W = W[::3] if len(W) > 90 else W
    m = (np.hypot(Q[:, None, 0] - W[None, :, 0], Q[:, None, 1] - W[None, :, 1]) < r) & (np.abs(Q[:, None, 2] - W[None, :, 2]) < dz)
    return int(m.any(1).sum())


def _first_seen(h, P, r=160.0, dz=110.0):
    """The first frame of a way in a CT spot's sight (one of its foes' spots), -1: never."""
    Q = np.array(h.get("seen") or [], float).reshape(-1, 3)
    W = np.asarray(P, float)[:, :3]
    if not len(Q) or not len(W):
        return -1
    m = ((np.hypot(W[:, None, 0] - Q[None, :, 0], W[:, None, 1] - Q[None, :, 1]) < r) & (np.abs(W[:, None, 2] - Q[None, :, 2]) < dz)).any(1)
    return int(np.argmax(m)) if m.any() else -1


def _hold_zone(CP, zones, p, mp):
    """A hold's place name: the most common zone of the CTs who fought from there (Backsite, Heaven…)."""
    near = np.hypot(CP[:, 0] - p[0], CP[:, 1] - p[1]) < 110
    z = pd.Series(zones[near] if near.any() else zones).dropna()
    return replay_zone(z.mode().iloc[0], mp) if len(z) else None


ZONES_F = os.path.join(config.OUT, "train_zones.json")


def zone_outline(mp, name, near, cell=32.0, max_matches=60, R=1600.0, ZR=170.0, hold=650.0):
    """The ground outline of the place a defense's post is in (06/10, the user: "une zone plus grande que juste un cercle,
    adapte-toi à la morphologie de la map: si c'est Garage, prends tout le Garage"): where the base's players stood in
    that place (same name, same floor), 650 u around the post at most (Nuke's Outside is the whole yard), the piece
    around the post with its small holes filled, its border walked around and simplified (20 u). Cached per post."""
    if not name or not near:
        return []
    key = f"{mp}|{name}|{round(near[0])}|{round(near[1])}|{round(near[2])}"
    try:
        cache = json.load(open(ZONES_F, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if key in cache:
        return cache[key]
    from collections import deque
    pts = []
    for d in _map_dirs(mp)[-max_matches:]:
        try:
            S = pd.read_parquet(os.path.join(config.OUT, "deep", d, "samples.parquet"), columns=["X", "Y", "Z", "zone", "health"])
        except Exception:
            continue
        S = S[(S.health > 0) & S.zone.notna()]
        S = S[(np.hypot(S.X - near[0], S.Y - near[1]) < R) & ((S.Z - near[2]).abs() < ZR)]
        if len(S):
            zs = {z: replay_zone(z, mp) for z in S.zone.unique()}
            S = S[S.zone.map(zs) == name]
            pts.append(S[["X", "Y", "Z"]].to_numpy(float))
    P = np.concatenate(pts) if pts else np.zeros((0, 3))
    out = []
    if len(P) >= 30:
        cnt = Counter(zip(np.floor(P[:, 0] / cell).astype(int), np.floor(P[:, 1] / cell).astype(int)))
        occ = {c for c, n in cnt.items() if n >= 2 and math.hypot((c[0] + .5) * cell - near[0], (c[1] + .5) * cell - near[1]) < hold}
        if occ:
            start = min(occ, key=lambda c: ((c[0] + .5) * cell - near[0]) ** 2 + ((c[1] + .5) * cell - near[1]) ** 2)
            comp, q = {start}, deque([start])
            while q:
                x, y = q.popleft()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + dx, y + dy)
                    if n in occ and n not in comp:
                        comp.add(n)
                        q.append(n)
            for _ in range(2):   # a box in the middle: its cells filled
                xs, ys = [c[0] for c in comp], [c[1] for c in comp]
                comp |= {(x, y) for x in range(min(xs) - 1, max(xs) + 2) for y in range(min(ys) - 1, max(ys) + 2)
                         if (x, y) not in comp and sum((x + dx, y + dy) in comp for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) >= 3}
            edges = {}
            for (x, y) in comp:
                for (dx, dy), (a, b) in (((0, -1), ((x, y), (x + 1, y))), ((1, 0), ((x + 1, y), (x + 1, y + 1))),
                                          ((0, 1), ((x + 1, y + 1), (x, y + 1))), ((-1, 0), ((x, y + 1), (x, y)))):
                    if (x + dx, y + dy) not in comp:
                        edges.setdefault(a, []).append(b)
            loops = []
            while edges:
                a = next(iter(edges))
                loop = [a]
                while a in edges:
                    nx = edges[a].pop()
                    if not edges[a]:
                        del edges[a]
                    if nx == loop[0]:
                        break
                    loop.append(nx)
                    a = nx
                loops.append(loop)
            L = np.array(max(loops, key=len), float) * cell
            L = L[_rdp(np.c_[L, np.zeros(len(L))], 20.0)]
            for x, y in L:
                d = np.hypot(P[:, 0] - x, P[:, 1] - y)
                out.append([round(float(x), 1), round(float(y), 1), round(float(np.median(P[np.argsort(d)[:25], 2])), 1)])
    cache[key] = out
    config.write_json(ZONES_F, cache)
    return out


def _timings(holds):
    """When each angle peeks, from the real timings (the earliest at once, the others after it, compressed by half,
    within 30 s): the bots show up like the players do, at recurring moments."""
    ts = [h.get("t") for h in holds]
    if not ts or any(t is None for t in ts):
        return [0.0] * len(holds)
    t0 = min(ts)
    return [round(min(30.0, (t - t0) * 0.5), 1) for t in ts]


ENTRY_D = os.path.join(config.OUT, "train_entries")


def _hit_nades(p, ticks):
    """The grenades thrown in the windows of a demo's hits: (tick, thrower, the plugin's nade: type, first position and
    speed), like replay._nades (a thrower dead in the replay throws nothing)."""
    try:
        g = p.parse_grenades()
    except Exception:
        return []
    lo, hi = min(ticks), max(ticks)
    g = g[g.grenade_type.isin(list(replay.NADES)) & g.x.notna() & (g.tick >= lo) & (g.tick <= hi)].sort_values("tick")
    out = []
    for (_, sid_, typ), e in g.groupby(["grenade_entity_id", "steamid", "grenade_type"]):
        t = e.tick.to_numpy()
        cuts = [0] + [i for i in range(1, len(t)) if t[i] - t[i - 1] > 2] + [len(t)]
        for a, b in zip(cuts, cuts[1:]):
            r = e.iloc[a:b]
            if len(r) < 2:
                continue
            dt = (int(r.tick.iloc[1]) - int(r.tick.iloc[0])) / 64
            v = [(float(r[c].iloc[1]) - float(r[c].iloc[0])) / dt for c in ("x", "y", "z")]
            v[2] += 0.5 * 320 * dt
            out.append((int(r.tick.iloc[0]), str(sid_), {"type": replay.NADES[typ], "inc": False, "life": int(r.tick.iloc[-1]) - int(r.tick.iloc[0]),
                                                          "p": [round(float(r[c].iloc[0]), 1) for c in ("x", "y", "z")], "v": [round(x, 1) for x in v]}))
    return out


def entries(mp, demos=24):
    """Real hits on each site, from the base's demos: for every plant, the planter and the Ts entering with him, their
    path in the 14 s before the plant (positions every 2 ticks), the ones that came from outside (700 u away or more)
    and ended on the site; with the moment a CT first saw each one (spot: its frame, -1: never) and the grenades it
    threw on the way (f: their frame). The attackers of a defense walk them, throw them, then fight on their own once
    they see you. Cached per map."""
    from demoparser2 import DemoParser
    import nades
    os.makedirs(ENTRY_D, exist_ok=True)
    cf = os.path.join(ENTRY_D, f"{mp}.json")
    try:
        c = json.load(open(cf, encoding="utf-8"))
        if c.get("v") == 5:
            return c
    except (OSError, ValueError):
        pass
    dirs = []
    for d in sorted(os.listdir(os.path.join(config.OUT, "deep")), reverse=True):
        try:
            if json.load(open(os.path.join(config.OUT, "deep", d, "meta.json"), encoding="utf-8")).get("map") == mp                     and os.path.exists(os.path.join(config.CACHE, f"{d}.dem")):
                dirs.append(d)
        except (OSError, ValueError):
            continue
    out = {"v": 5, "A": [], "B": []}
    for d in dirs[:demos]:
        try:
            R = pd.read_parquet(os.path.join(config.OUT, "deep", d, "rounds.parquet"))
            R = R[R.plant_site.isin(["A", "B"]) & R.plant_tick.notna()]
            if not len(R):
                continue
            want = sorted({t for pt in R.plant_tick for t in range(int(pt) - 14 * 64, int(pt) + 1, 2)})
            dp = DemoParser(os.path.join(config.CACHE, f"{d}.dem"))
            T = dp.parse_ticks(["X", "Y", "Z", "yaw", "pitch", "is_alive", "team_num", "last_place_name", "spotted"], ticks=want)
            thrown = _hit_nades(dp, want)
        except Exception as e:
            print("entries", d, e, flush=True)
            continue
        for _, r in R.iterrows():
            pt, site = int(r.plant_tick), r.plant_site
            w = T[(T.tick >= pt - 14 * 64) & (T.tick <= pt) & (T.team_num == 2)]
            pl = w[w.steamid == r.planter].sort_values("tick")
            pz = float(pl.Z.iloc[-1]) if len(pl) else None   # the floor of the plant (Nuke: a T on A when B is planted is not on B)
            for sid_, g in w.groupby("steamid"):
                g = g.sort_values("tick")
                if len(g) < 200 or not bool(g.is_alive.iloc[-1]):
                    continue
                P = g[["X", "Y", "Z"]].to_numpy(float)
                dist = np.hypot(P[:, 0] - r.plant_X, P[:, 1] - r.plant_Y)
                if dist[-1] > 450 or dist[0] < 700 or (pz is not None and abs(P[-1, 2] - pz) > 200):
                    continue
                k0 = int(np.argmax(dist <= 1500)) if (dist <= 1500).any() else 0   # from where it gets close
                if len(g) - k0 < 40:
                    continue
                path, zones = [], []
                for x, y, z, yw, pi in zip(g.X, g.Y, g.Z, g.yaw, g.pitch):
                    path += [round(float(x), 1), round(float(y), 1), round(float(z), 1), round(float(yw), 1), round(float(pi), 1)]
                for pl in g.last_place_name.fillna(""):   # the places it crosses, in order
                    nm = nades.humanize(pl, mp) if pl else None
                    if nm and (not zones or zones[-1] != nm):
                        zones.append(nm)
                pl = g.last_place_name.fillna("").iloc[k0]
                seen = g.spotted.astype(object).eq(True).to_numpy() if "spotted" in g else np.zeros(len(g), bool)
                t0_ = int(g.tick.iloc[0])
                own = [{"f": (tk - t0_) // 2, **nd} for tk, by, nd in thrown if by == str(sid_) and t0_ <= tk <= int(g.tick.iloc[-1])]
                out[site].append({"zone": nades.humanize(pl, mp) or "?", "path": path, "k0": k0, "zones": zones,
                                  "from": round(float(dist[0])), "spot": int(np.argmax(seen)) if seen.any() else -1, "nades": own})
    json.dump(out, open(cf, "w", encoding="utf-8"), separators=(",", ":"))
    return out


def _opening(z, w=13):
    """The height without the jumps: a morphological opening over ±w samples (positions every 2 ticks: ±0.4 s). A
    jump's arc, shorter than the window, goes; a ramp or a box you stay on keeps its height."""
    from numpy.lib.stride_tricks import sliding_window_view
    e = sliding_window_view(np.pad(z, w, mode="edge"), 2 * w + 1).min(axis=1)
    return sliding_window_view(np.pad(e, w, mode="edge"), 2 * w + 1).max(axis=1)


def _jumps(z):
    """How many jumps a way has (its height 25 u over the ground, again and again)."""
    up = (np.asarray(z, float) - _opening(np.asarray(z, float))) > 25
    return int(np.sum(up[1:] & ~up[:-1]) + (1 if len(up) and up[0] else 0))


def _rdp(Q, eps):
    """The points that keep the way's shape within eps (Ramer-Douglas-Peucker)."""
    keep, stack = {0, len(Q) - 1}, [(0, len(Q) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg, pts = Q[b] - Q[a], Q[a + 1:b] - Q[a]
        n = float(np.linalg.norm(seg))
        d = np.linalg.norm(np.cross(pts, seg / n), axis=1) if n > 1e-6 else np.linalg.norm(pts, axis=1)
        k = int(np.argmax(d))
        if d[k] > eps:
            keep.add(a + 1 + k)
            stack += [(a, a + 1 + k), (a + 1 + k, b)]
    return sorted(keep)


# the maps' water: (x min, x max, y min, y max, -, the height the line goes up to there): Anubis's canals, where the
# players' feet are at -189 and the walkways at -152
WATER = {"de_anubis": [(-420, 1270, 20, 890, -200, -158)]}


def _ground_line(P, mp=None):
    """The way drawn on the ground: the jumps flattened, the strafes straightened, 60 segments at most (03/10: the
    line hung in the air and zigzagged where the real player jumped on the boxes)."""
    Q = np.array(P[:, :3], float)
    Q[:, 2] = _opening(Q[:, 2])
    if len(Q) > 20:   # the strafes and quick peeks smoothed out (±0.25 s): the way, not the steps (04/10: "the zigzag is bad")
        k = 8
        pad = np.pad(Q[:, :2], ((k, k), (0, 0)), mode="edge")
        sm = np.stack([np.convolve(pad[:, j], np.ones(2 * k + 1) / (2 * k + 1), mode="valid") for j in range(2)], 1)
        sm[0], sm[-1] = Q[0, :2], Q[-1, :2]
        Q[:, :2] = sm
    for x0, x1, y0, y1, zmin, surf in WATER.get(mp, ()):   # in the water: on its surface, not under it (06/10, Anubis)
        w = (Q[:, 0] > x0) & (Q[:, 0] < x1) & (Q[:, 1] > y0) & (Q[:, 1] < y1) & (Q[:, 2] < surf)
        Q[w, 2] = surf
    eps, keep = 24.0, _rdp(Q, 24.0)   # 06/10: closer to the way walked (48 u cut the corners)
    while len(keep) > 81:
        eps *= 1.5
        keep = _rdp(Q, eps)
    return [[round(float(v), 1) for v in Q[i]] for i in keep]


def practice_drills(sid, mp):
    """Prefire (you T from an entrance, bots on every angle the CTs really hold, they don't shoot: clear them fast) and
    defense (you CT on the site, attackers keep coming from the real entrances for 90 s: as many frags as you can)."""
    out = []
    for z, S in (site_data(mp).get("sites") or {}).items():
        site = replay_zone(z, mp)
        pick = []
        for e in S["entrances"]:   # the entrances right on the site, not two next to each other
            if e["dist"] < 1700 and all(math.dist(e["start"], p["start"]) > 900 for p in pick):
                pick.append(e)
        letter = z.replace("Bombsite", "")[:1]
        hits = [t for t in (entries(mp).get(letter) or []) if t.get("from", 0) >= 1300 and len(t.get("zones") or []) >= 2
                and not any("CT" in zn for zn in t["zones"])   # an attack, not a late rotation through the CTs' side
                and replay_zone("Bombsite" + ("B" if letter == "A" else "A"), mp) not in t["zones"]]   # nor a drop from the other site (Nuke)
        for e in pick[:3]:   # the push routes: one per entrance on the site
            frm = replay_zone(e["zone"], mp)
            # a real hit through that entrance, from far: its way is the route (start, places, the line drawn in the game)
            way = sorted([t for t in hits if frm in (t.get("zones") or [])], key=lambda t: -t.get("from", 0))[:6]
            if way:   # one of the ones from furthest, with the fewest jumps (boxes: a line hard to follow)
                jumps = {id(t): _jumps(np.array(t["path"], float).reshape(-1, 5)[:, 2]) for t in way}
                way = [t for t in way if jumps[id(t)] == min(jumps.values())]
            hit = random.choice(way) if way else None
            if not hit:
                continue
            P = np.array(hit["path"], float).reshape(-1, 5)[:, :3] if hit else None
            start = [round(float(v), 1) for v in P[0]] if hit else e["start"]
            # the CT angles seen from that very way (06/10, the user: "le dernier, je le croise jamais... je veux juste
            # qu'il soit visible depuis le chemin que je prends"): the base's duels put Ts on this way fighting a CT on
            # that spot (they saw each other); the most fought from it first (the strongest, the most played: the
            # session keeps more or fewer by its level), none right at your start, 10 at most (a team holds 10 bots)
            keep = []
            for h in _site_holds(S):
                h["vis"] = _sees(h, P)
                if h["vis"] >= 2 and math.dist(h["pos"][:2], start[:2]) > 600:
                    keep.append(h)
            keep = sorted(keep, key=lambda h: (-h["vis"], -h["n"]))[:10]
            if len(keep) < 4:
                continue
            for h in keep:   # each one turned to where it saw the Ts of this way
                Q = np.array(h["seen"], float).reshape(-1, 3)
                near = Q[np.hypot(Q[:, 0, None] - P[None, ::3, 0], Q[:, 1, None] - P[None, ::3, 1]).min(1) < 160]
                if len(near):
                    eye = 46 if h.get("crouch", 0) >= 0.35 else 64
                    h["ang"] = _angle([h["pos"][0], h["pos"][1], h["pos"][2] + eye], np.median(near, axis=0) + [0, 0, 56])
            route = hit["zones"] if hit else [frm, site]
            first = min(keep, key=lambda h: math.dist(h["pos"], start))
            line = _ground_line(P, mp) if hit else []   # the way drawn on the ground
            out.append({"id": f"prefire:{mp}:{z}:{e['zone']}", "kind": "aim", "mode": "prefire", "map": mp,
                        "title": f"PREFIRE {site} via {frm}", "team": 2, "route": route, "line": line,
                        "tip": f"follow the gold line: {' → '.join(route)} · the angles CTs hold there, at their real timings · they don't move, they don't shoot",
                        "me": {"pos": start, "ang": _angle(start, line[1] if len(line) > 1 else first["pos"])},
                        "weapons": ["weapon_knife", RIFLE[2]], "bot_weapons": ["weapon_knife", RIFLE[3]],
                        "bots": [{"pos": h["pos"], "ang": h["ang"], "zone": h.get("zone") or site, "at": at, "duck": h.get("crouch", 0) >= 0.35}
                                 for h, at in zip(keep, _timings(keep))],
                        # the round's clock as when these angles get fought (06/10: "le vrai temps in-game, pas 58 minutes")
                        "clock": round(max(15.0, 115 - max(0.0, min(h["t"] for h in keep) - 8)), 1),
                        "seconds": 90, "weight": 2 + min(1.0, e["n"] / 400)})
        spawns = [{"pos": p, "ang": _angle(p, S["defend"]), "zone": replay_zone(e["zone"], mp)} for e in S["entrances"] for p in e["spawns"]]
        letter = z.replace("Bombsite", "")[:1]
        hits = (entries(mp).get(letter) or []) if letter in ("A", "B") else []
        other = replay_zone("Bombsite" + ("B" if letter == "A" else "A"), mp)
        hits = [t for t in hits if not any("CT" in zn for zn in t.get("zones") or []) and other not in (t.get("zones") or [])]   # attacks
        # the spots to hold, one after the other, before playing free (04/10: "a specific work on positions: backsite,
        # then that one, then free"): the most held of the site, each its own place, and only one the real hits come
        # into sight of (06/10: "les bots n'attaquent pas le mid, je peux rester à rien faire"); each post gets its own
        # attackers, real hits that walk into its sight from out of it
        posts, tracks = [], []
        for h in _site_holds(S):
            if not h.get("zone") or any(h["zone"] == q["zone"] or math.dist(h["pos"], q["pos"]) <= 300 for q in posts):
                continue
            mine = [t for t in hits if _sees(h, np.array(t["path"], float).reshape(-1, 5), r=180) >= 2]
            tr = _defense_tracks(mine, h["pos"], n=10, foes=h) if len(mine) >= 3 else []
            if len(tr) < 3:   # too few walk into its sight from out of it
                continue
            k = len(posts)
            Q = np.array(h["seen"], float).reshape(-1, 3)   # turned to where its foes stood
            ang = _angle([h["pos"][0], h["pos"][1], h["pos"][2] + 64], np.median(Q, axis=0) + [0, 0, 56]) if len(Q) else h["ang"]
            posts.append({"pos": h["pos"], "ang": ang, "zone": _post_name(mp, h), "poly": zone_outline(mp, h["zone"], h["pos"]), "t": h.get("t")})
            tracks += [dict(t, post=k) for t in tr]
            if len(posts) >= 2:
                break
        tracks += [dict(t, post=-1) for t in _defense_tracks(hits, S["defend"], n=12)]   # then free: any of them
        if len(spawns) < 2 and not tracks:
            continue
        ways = Counter(t["zone"] for t in tracks)
        froms = ", ".join(f"{w} {round(100 * n / len(tracks))}%" for w, n in ways.most_common(4)) if tracks else \
            ", ".join(dict.fromkeys(replay_zone(e["zone"], mp) for e in S["entrances"]))
        hold_t = [p["t"] for p in posts if p.get("t") is not None]
        for kit in _defense_kits(sid):
            out.append({"id": f"defend:{mp}:{z}:{kit['cls']}", "kind": "aim", "mode": "defend", "map": mp,
                        "title": f"DEFEND {site} · {kit['name']}", "team": 3,
                        "tip": f"{kit['seconds']} s · {kit['alive']} at a time, the ways real hits come: {froms} · {kit['goal']} frags · you respawn",
                        "me": {"pos": S["defend"], "ang": _angle(S["defend"], spawns[0]["pos"] if spawns else tracks[0]["path"][:3])},
                        "weapons": kit["weapons"], "bot_weapons": kit["bot_weapons"], "armor": 100, "helmet": kit["helmet"],
                        "bots": spawns, "tracks": tracks, "seconds": kit["seconds"], "alive": kit["alive"], "goal": kit["goal"],
                        "posts": posts, "weight": kit["weight"],
                        "clock": round(max(20.0, 115 - max(0.0, min(hold_t) - 6)), 1) if hold_t else 0})
    return out


# a post's name as players call it where the game's places say otherwise (06/10, the user on Overpass: "cette zone elle
# s'appelle Toilettes, pas Lower Park"): (map, x, y, radius, callout)
POST_NAMES = [("de_overpass", -2238.6, -603.1, 260, "Toilets")]


def _post_name(mp, h):
    for m, x, y, r, nm in POST_NAMES:
        if m == mp and math.hypot(h["pos"][0] - x, h["pos"][1] - y) < r:
            return nm
    return h["zone"]


def _defense_tracks(hits, spot, n=24, foes=None):
    """A defense's attackers: real hits on the site in their real proportions (the ways attackers really take: few by
    mid when few go by mid, 04/10), each one from 2 s before a CT first saw it in its match, so it walks in out of sight
    instead of appearing in front of you ("the spawn kill problem"), never closer than 700 u; with its grenades. For a
    post (foes: its CT spot): from 3 s before it comes into that spot's sight, 900 u away at least (06/10: "ils sont trop
    proches de moi")."""
    cut = []
    for t in hits:
        P = np.array(t["path"], float).reshape(-1, 5)
        d = np.hypot(P[:, 0] - spot[0], P[:, 1] - spot[1])
        sp = _first_seen(foes, P, r=180) if foes else t.get("spot", -1)
        far = 900 if foes else 700
        if 0 <= sp < 32 and d[0] < 1200:   # seen from its very first second, close: it would appear in your sight
            continue
        k = max(0, sp - (96 if foes else 64)) if sp >= 0 else 0
        while k > 0 and d[k] < far:
            k -= 1
        if d[k] < far or len(P) - k < 40:
            continue
        cut.append({"zone": t["zone"], "path": t["path"][5 * k:], "nades": [dict(nd, f=nd["f"] - k) for nd in t.get("nades") or [] if nd["f"] >= k]})
    by = {}
    for t in cut:
        by.setdefault(t["zone"], []).append(t)
    pick = []
    for w, ts in by.items():   # each way its share of the n
        pick += random.sample(ts, min(len(ts), max(1, round(n * len(ts) / len(cut)))))
    random.shuffle(pick)
    return pick[:n]


KIT_CLASS = {"rifle": ("M4A4", "M4A1-S", "AK-47", "FAMAS", "Galil AR", "AUG", "SG 553"),
             "close": ("MAG-7", "XM1014", "Nova", "Sawed-Off", "MP9", "MAC-10", "MP7", "MP5-SD", "UMP-45", "P90", "PP-Bizon"),
             "awp": ("AWP", "SSG 08")}


def _defense_kits(sid):
    """The weapons of your site defenses: the ones you play as CT (your demos), one defense each: your rifle, your
    close-range weapon and the AWP when you play them, your pistol (04/10: "other weapons than the M4, ones I do play:
    the pistol, closer range, the sniper"). Longer with the rifle, and more at a time; fewer for the AWP and the pistol."""
    prim, pist, n = Counter(), Counter(), 0
    for mid, _ in _my_matches(str(sid)):
        try:
            L = pd.read_parquet(os.path.join(config.OUT, "deep", mid, "loadout.parquet"), columns=["steamid", "side", "primary", "pistol"])
        except Exception:
            continue
        L = L[(L.steamid.astype(str) == str(sid)) & (L.side == "CT")]
        n += len(L)
        prim.update(L.primary.dropna())
        pist.update(L.pistol.dropna())
    pistol = next((p for p, _ in pist.most_common() if replay._item(p)), "USP-S")
    side_arm = replay._item(pistol) or "weapon_usp_silencer"
    kits = []
    for cls, names in KIT_CLASS.items():
        best = max((x for x in names if prim[x] and replay._item(x)), key=lambda x: prim[x], default=None)
        if cls == "rifle" and not best:
            best = "M4A4"
        if not best or (cls != "rifle" and sum(prim[x] for x in names) < max(5, 0.05 * n)):
            continue
        kits.append({"cls": cls, "name": best, "weapons": ["weapon_knife", side_arm, replay._item(best)], "helmet": True,
                     "bot_weapons": ["weapon_knife", "weapon_glock", RIFLE[2]], "seconds": {"rifle": 120}.get(cls, 100),
                     "alive": 4 if cls == "rifle" else 3, "goal": {"rifle": 10, "close": 8, "awp": 7}[cls], "weight": 4 if cls == "rifle" else 3})
    kits.append({"cls": "pistol", "name": pistol, "weapons": ["weapon_knife", side_arm], "helmet": False,
                 "bot_weapons": ["weapon_knife", "weapon_glock"], "seconds": 90, "alive": 3, "goal": 6, "weight": 3})
    return kits


def replay_zone(z, mp=None):
    import nades
    return nades.humanize(z, mp) or str(z)


def _world(mp, px, py):
    import mapdata
    r = mapdata.get(mp)
    f = r.get("px_factor", 1.0)
    return [round(px / f * r["scale"] + r["pos_x"], 1), round(r["pos_y"] - py / f * r["scale"], 1)]


_LANDS = {}


def _land(mp, typ, pos):
    """Where that very throw landed (the one whose spot and aim the drill gives), not the middle of its group: a
    bouncing molotov of the group can land 300 u from it (03/10). With its height when the demo it comes from is here
    (its detonation point): x, y, z; else x, y."""
    if mp not in _LANDS:
        f = os.path.join(config.OUT, "population", "nades.parquet")
        cols = ["map", "match", "round", "type", "X", "Y", "land_px", "land_py"]
        try:
            try:   # a player's copy: each throw's landing came with the base, its demo stays on the coach's PC (05/10)
                N = pd.read_parquet(f, columns=cols + ["land_X", "land_Y", "land_Z"])
            except Exception:
                N = pd.read_parquet(f, columns=cols)
            _LANDS[mp] = N[N["map"] == mp]
        except Exception:
            _LANDS[mp] = None
    N = _LANDS[mp]
    if N is None or not len(N):
        return None
    m = N[(N.type == typ) & ((N.X - pos[0]).abs() < 1) & ((N.Y - pos[1]).abs() < 1)]
    if not len(m):
        return None
    if "land_X" in m and m.land_X.notna().any():
        q = m[m.land_X.notna() & m.land_Z.notna()][["land_X", "land_Y", "land_Z"]].to_numpy(float)[:5]
        if len(q):
            return [round(float(v), 1) for v in np.median(q, axis=0)]
    pts = []
    for mid, rnd in zip(m["match"].astype(str), m["round"]):   # the same throw in its demo: x, y and z
        try:
            G = pd.read_parquet(os.path.join(config.OUT, "deep", mid, "grenades.parquet"),
                                columns=["round", "type", "X", "Y", "land_X", "land_Y", "land_Z"])
        except Exception:
            continue
        g = G[(G["round"] == rnd) & (G.type == typ) & ((G.X - pos[0]).abs() < 1) & ((G.Y - pos[1]).abs() < 1)].dropna()
        pts += g[["land_X", "land_Y", "land_Z"]].values.tolist()
        if len(pts) >= 5:
            break
    if pts:
        return [round(float(v), 1) for v in np.median(np.array(pts, float), axis=0)]
    return _world(mp, float(m.land_px.median()), float(m.land_py.median()))


SPOTS_F = os.path.join(config.OUT, "train_spots.json")


_MAPDIRS = {}


def _map_dirs(mp):
    """The base's matches on a map. Kept 10 min in memory (06/10: a map's stuff drills asked 19 times, reading the
    2,900 matches' meta.json each time: 54,000 files, 14 s before the warm-up could start)."""
    hit = _MAPDIRS.get(mp)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    dirs = []
    for d in sorted(os.listdir(os.path.join(config.OUT, "deep"))):
        try:
            with open(os.path.join(config.OUT, "deep", d, "meta.json"), encoding="utf-8") as fh:
                if json.load(fh).get("map") == mp:
                    dirs.append(d)
        except (OSError, ValueError):
            continue
    _MAPDIRS[mp] = (time.time(), dirs)
    return dirs


_SPOTS_MEM = {"mt": None, "c": {}}


def _spots(mp):
    """Where each side really stands on the map: the duels of every demo (killers and victims), 64 u cells with their
    mean position and how often. Cached per map, computed again after a quarter more matches."""
    try:   # the file read again only when it changed (19 reads of 1 MB per map's stuff before)
        mt = os.path.getmtime(SPOTS_F)
        if _SPOTS_MEM["mt"] != mt:
            with open(SPOTS_F, encoding="utf-8") as fh:
                _SPOTS_MEM.update(mt=mt, c=json.load(fh))
        cache = _SPOTS_MEM["c"]
    except (OSError, ValueError):
        cache = {}
    dirs = _map_dirs(mp)
    c = cache.get(mp)
    if c and c.get("n", 0) >= 0.8 * len(dirs):
        return c
    cells = {}
    for d in dirs:
        try:
            D = pd.read_parquet(os.path.join(config.OUT, "deep", d, "duels.parquet"),
                                columns=["killer_side", "victim_side", "killer_X", "killer_Y", "killer_Z", "victim_X", "victim_Y", "victim_Z"])
        except Exception:
            continue
        for who in ("killer", "victim"):
            for sd, x, y, z in zip(D[f"{who}_side"], D[f"{who}_X"], D[f"{who}_Y"], D[f"{who}_Z"]):
                if sd in ("T", "CT") and x == x and y == y and z == z:
                    k = (sd, int(x // 64), int(y // 64), int(z // 64))
                    a = cells.setdefault(k, [0, 0.0, 0.0, 0.0])
                    a[0] += 1
                    a[1] += x
                    a[2] += y
                    a[3] += z
    out = {"n": len(dirs), "T": [], "CT": []}
    for (sd, *_), (n, sx, sy, sz) in sorted(cells.items(), key=lambda kv: -kv[1][0]):
        if len(out[sd]) < 4000:
            out[sd].append([round(sx / n, 1), round(sy / n, 1), round(sz / n, 1), n])
    cache[mp] = out
    with open(SPOTS_F, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, separators=(",", ":"))
    return out


def _victims(mp, team, typ, land, me, side=None, t_med=None):
    """The enemies a grenade is for, where the base's players really were when the same lineup landed (06/10, the user:
    "la personne qui subit le stuff doit être là où quelqu'un a pris des dégâts avec cette grenade": a Squeaky flash is
    for the Ts in Squeaky, not for a CT outside): the throws from that spot onto that place in the demos, the enemies in
    its reach at that moment (an HE 350 u, a molotov 220 u, a flash 650 u, a smoke 900 u, same floor), their most
    frequent spots, turned to it. Without such throws: the most held enemy spots in its reach (a smoke or a flash: the
    ones beyond it from where you throw); a molotov: in its fire, turned to where it came from."""
    if not land or len(land) < 3:
        return []
    lx, ly, lz = land[:3]
    reach = {"he": 350, "molotov": 220, "flash": 650, "smoke": 900}.get(typ, 500)
    foe = "CT" if team == 2 else "T"
    _land(mp, typ, me)   # the base's throws of the map, loaded
    N, hits = _LANDS.get(mp), []
    if N is not None and len(N):
        m = N[(N.type == typ) & ((N.X - me[0]).abs() < 24) & ((N.Y - me[1]).abs() < 24)]
        for mid, rnd in list(dict.fromkeys(zip(m["match"].astype(str), m["round"])))[:10]:
            try:
                G = pd.read_parquet(os.path.join(config.OUT, "deep", mid, "grenades.parquet"),
                                    columns=["round", "type", "X", "Y", "t", "flight_s", "land_X", "land_Y", "land_Z", "enemies_blind", "damage"])
                Sm = pd.read_parquet(os.path.join(config.OUT, "deep", mid, "samples.parquet"), columns=["round", "t", "side", "X", "Y", "Z", "health"])
            except Exception:
                continue
            g = G[(G["round"] == rnd) & (G.type == typ) & ((G.X - me[0]).abs() < 24) & ((G.Y - me[1]).abs() < 24)
                  & (np.hypot(G.land_X - lx, G.land_Y - ly) < 160)]
            lo, hi = {"flash": (-260, 60), "he": (-150, 90), "molotov": (-90, 90)}.get(typ, (-160, 160))   # its floor (Nuke: A over B)
            for r in g.itertuples():
                if typ == "flash" and not (r.enemies_blind == r.enemies_blind and r.enemies_blind > 0):
                    continue   # that time it blinded nobody
                if typ in ("he", "molotov") and not (r.damage == r.damage and r.damage > 0):
                    continue   # that time it hurt nobody
                tl = float(r.t) + (float(r.flight_s) if r.flight_s == r.flight_s else 1.5)
                q = Sm[(Sm["round"] == rnd) & ((Sm.t - tl).abs() <= 0.5) & (Sm.side == foe) & (Sm.health > 0)]
                near = sorted((math.hypot(x - lx, y - ly) + 2 * abs(z - lz), (x, y, z)) for x, y, z in zip(q.X, q.Y, q.Z)
                              if math.hypot(x - lx, y - ly) <= reach and lo <= z - lz <= hi)
                hits += [p for _, p in near[:2]]   # the closest: the ones it was for
    look = [lx, ly, lz + (0 if typ == "flash" else 40)]
    out = []
    if len(hits) >= 2:
        for n, p in _cells(np.array(hits, float), cell=64):
            if all(math.dist(p, o["pos"]) > 200 for o in out):
                pp = [round(float(v), 1) for v in p]
                out.append({"pos": pp, "ang": _angle([pp[0], pp[1], pp[2] + 64], look)})
            if len(out) >= 2:
                break
        return out
    if typ == "molotov":
        dx, dy = me[0] - lx, me[1] - ly
        d = math.hypot(dx, dy) or 1.0
        p = [round(lx + 40 * dx / d, 1), round(ly + 40 * dy / d, 1), round(lz, 1)]
        return [{"pos": p, "ang": _angle([p[0], p[1], p[2] + 64], [me[0], me[1], me[2] + 64])}]
    lo_z, hi_z = (-450, 100) if typ == "flash" else (-200, 200)   # a flash pops in the air: the ones under it
    ax, ay = lx - me[0], ly - me[1]
    an = math.hypot(ax, ay) or 1.0
    cone = {"smoke": 0.5, "flash": 0.0}.get(typ)

    def beyond(x, y):
        if cone is None:
            return True
        bx, by = x - lx, y - ly
        return (ax * bx + ay * by) / (an * (math.hypot(bx, by) or 1.0)) >= cone
    for x, y, z, n in _spots(mp)["CT" if team == 2 else "T"]:   # the most held first
        if math.hypot(x - lx, y - ly) <= reach and lo_z < z - lz < hi_z and beyond(x, y) and all(math.dist([x, y, z], o["pos"]) > 250 for o in out):
            out.append({"pos": [x, y, z], "ang": _angle([x, y, z + 64], look)})
            if len(out) >= 2:
                break
    return out


def _my_setup(sid, mp):
    """Where you stand on each side of this map 15 to 30 s into your rounds (your demos: the spot you play, not where the
    round takes you: on Fachwerk you hold Apps, you end up on A), and the zones your enemies come from when you fight
    from those spots. -> ({side: Counter(zone)}, {side: Counter(enemy zone)})."""
    setup, faced = {"CT": Counter(), "T": Counter()}, {"CT": Counter(), "T": Counter()}
    duels = []
    for mid, _ in _my_matches(str(sid), mp):
        deep = os.path.join(config.OUT, "deep", mid)
        try:
            S = pd.read_parquet(os.path.join(deep, "samples.parquet"), columns=["steamid", "side", "round", "t", "zone"])
            D = pd.read_parquet(os.path.join(deep, "duels.parquet"), columns=["killer", "victim", "killer_side", "victim_side", "killer_zone", "victim_zone"])
        except Exception:
            continue
        S = S[(S.steamid.astype(str) == str(sid)) & (S.t >= 15) & (S.t <= 30)]
        for (_, side), g in S.groupby(["round", "side"]):
            z = g.zone.dropna().mode()
            if side in setup and len(z):
                setup[side][z.iloc[0]] += 1
        for who, en in (("killer", "victim"), ("victim", "killer")):
            d = D[D[who].astype(str) == str(sid)]
            duels += list(zip(d[f"{who}_side"], d[f"{who}_zone"], d[f"{en}_zone"]))
    for side, mz, ez in duels:
        if side in faced and mz in dict(setup[side].most_common(3)) and isinstance(ez, str):
            faced[side][ez] += 1
    return setup, faced


REPEATABLE = ("standing still", "jumpthrow", "crouching", "jumpthrow + crouching")


def nade_drills(sid, mp):
    """The lineups for where you play: thrown from the spots you hold 15-30 s into your rounds, or landing where your
    enemies come from when you hold them (04/10: "I'm an Apps player, I don't play long: this smoke changes nothing for
    me"). Only throws you can repeat from a spot: standing, crouching or a jumpthrow (04/10: "you say running jump: it
    goes way too far": a running throw starts somewhere the demos don't tell)."""
    import nades
    S = (nades.summary().get("maps") or {}).get(mp) or {}
    setup, faced = _my_setup(sid, mp)
    out = []
    for side, M in S.items():
        if not isinstance(M, dict) or not setup.get(side):
            continue
        team = 2 if side == "T" else 3
        su, fa = setup[side], faced[side]
        top, n_su = dict(su.most_common(3)), sum(su.values())
        hot, n_fa = dict(fa.most_common(5)), sum(fa.values()) or 1
        cands = []
        for typ, T in (M.get("types") or {}).items():
            for x in T.get("groups") or []:
                if (x.get("how") or "standing still") not in REPEATABLE or (typ == "flash" and (x.get("blind") or 0) < 20):
                    continue
                rel = top.get(x["from_key"], 0) / n_su + 0.5 * hot.get(x["to_key"], 0) / n_fa
                if rel > 0:
                    cands.append((rel * (0.5 + float(x.get("score") or 0)), rel, typ, x))
        for w, rel, typ, x in sorted(cands, key=lambda c: -c[0])[:12]:
            sp = (x.get("setpos") or "").replace(";", " ").split()
            try:
                pos = [float(v) for v in sp[1:4]]
                ang = [float(sp[5]), float(sp[6])]
            except (IndexError, ValueError):
                continue
            item = NADE_ITEM[typ][team] if typ == "molotov" else NADE_ITEM.get(typ)
            if not item or not x.get("to_px"):
                continue
            name = {"smoke": "Smoke", "flash": "Flash", "he": "HE", "molotov": "Molotov"}[typ]
            land = _land(mp, typ, pos) or _world(mp, *x["to_px"])
            mine = x["from_key"] in top
            why = f"from {x['from']}, your spot" if mine else f"onto {x['to']}, where they come at you from your spot"
            out.append({"id": f"nade:{mp}:{side}:{typ}:{x['from_key']}>{x['to_key']}", "kind": "nade", "map": mp,
                        "title": f"{name} → {x['to']}", "tip": f"{why} · {x.get('timer') or ''}".strip(" ·"),
                        "team": team, "type": typ, "item": item, "how": x.get("how") or "standing still",
                        "click": {"right": "right click", "both": "left + right click"}.get(x.get("click"), "left click"),
                        "me": {"pos": pos, "ang": ang}, "target": land, "victims": [], "_vic": [side, x.get("t_med")],
                        "clock": round(max(10.0, 115 - float(x.get("t_med") or 0) + 3), 1) if x.get("t_med") else 0,
                        "weight": 1 + 10 * w})
    return out


# ---------------------------------------------------------------- where you struggle lately (06/10)

KIND_EN = {"exec": "executes", "rush": "rushes", "hit": "hits"}
_STRUG = {"t": 0, "sid": None, "v": []}


def struggles(sid, n=20):
    """Where you lose rounds lately (06/10, the user: "la game d'Overpass entre le 4 et le 5 où on s'est pris des execs B
    en CT: si tu vois des situations comme ça où je galère, priorise-les en entraînement"): your last matches' rounds by
    map, side, site and how the Ts came (an execute: three Ts or more on the site after 0:30; a rush: before), the
    recent ones weighing more (a week old: half). A situation counts when you lost most of its rounds, twice at least.
    -> [{map, side, site, kind, lost, n, score, rounds: [[mid, round], ...], last}] the worst first"""
    import tside
    sid = str(sid)
    if _STRUG["sid"] == sid and time.time() - _STRUG["t"] < 600:
        return _STRUG["v"]
    try:
        reg = json.load(open(os.path.join(config.CACHE, "matches.json"), encoding="utf-8"))
    except (OSError, ValueError):
        reg = {}
    acc = {}
    for mid, mp in replay._own_matches(sid, n):
        f = os.path.join(tside.OUT, mid + ".parquet")
        lf = os.path.join(config.OUT, "deep", mid, "loadout.parquet")
        if not mp or not os.path.exists(f) or not os.path.exists(lf):
            continue
        try:
            R = pd.read_parquet(f, columns=["round", "site", "hit_t", "n_exec", "T_won"])
            L = pd.read_parquet(lf, columns=["round", "steamid", "side"])
        except Exception:
            continue
        me = L[L.steamid.astype(str) == sid].set_index("round").side
        when = (reg.get(mid) or {}).get("time")
        try:
            t = time.mktime(time.strptime(when[:16], "%Y-%m-%dT%H:%M")) if when else None
        except ValueError:
            t = None
        w = 0.5 ** (max(0.0, time.time() - t) / 86400 / 7) if t else 0.5
        for r in R.itertuples():
            side = me.get(r.round)
            if side not in ("T", "CT") or r.site not in ("A", "B") or r.hit_t != r.hit_t:
                continue
            kind = "rush" if r.hit_t < 30 else "exec" if (r.n_exec or 0) >= 3 else "hit"
            lost = bool(r.T_won) if side == "CT" else not bool(r.T_won)
            e = acc.setdefault((mp, side, r.site, kind), {"lost": 0, "n": 0, "w": 0.0, "rounds": [], "last": 0})
            e["n"] += 1
            if lost:
                e["lost"] += 1
                e["w"] += w
                e["rounds"].append([mid, int(r.round)])
                e["last"] = max(e["last"], t or 0)
    out = []
    for (mp, side, site, kind), e in acc.items():
        if e["lost"] >= 2 and e["lost"] / e["n"] >= 0.55:
            out.append({"map": mp, "side": side, "site": site, "kind": kind, "lost": e["lost"], "n": e["n"],
                        "score": round(e["w"] * e["lost"] / e["n"], 3), "rounds": e["rounds"],
                        "last": time.strftime("%d/%m", time.localtime(e["last"])) if e["last"] else None,
                        "text": f"{side} on {site}: {e['lost']} of {e['n']} rounds lost to {KIND_EN[kind]}" if side == "CT"
                                else f"T on {site}: {e['lost']} of {e['n']} {KIND_EN[kind]} lost"})
    out.sort(key=lambda x: -x["score"])
    _STRUG.update(t=time.time(), sid=sid, v=out)
    return out


def _boost(S, mp, side, site):
    """How much a drill on that map, side and site is pushed (1: not at all, up to 4): your recent struggles there."""
    top = max((x["score"] for x in S), default=0) or 1
    sc = sum(x["score"] for x in S if x["map"] == mp and x["side"] == side and x["site"] == site)
    return 1 + 3 * min(1.0, sc / top)


# ---------------------------------------------------------------- wallbangs (06/10: "practice des lineups de wallbang" in long sessions)

WB_WEAPON = {"ak47": "weapon_ak47", "m4a1_silencer": "weapon_m4a1_silencer", "m4a1": "weapon_m4a1", "awp": "weapon_awp", "ssg08": "weapon_ssg08",
             "deagle": "weapon_deagle", "galilar": "weapon_galilar", "famas": "weapon_famas", "aug": "weapon_aug", "sg556": "weapon_sg556"}


def wallbang_drills(sid, mp):
    """The map's wallbangs (wallbangs.py: the base's kills through walls from one spot onto one place): you on the
    spot, the bots where the victims stood behind the wall, the weapon most of those kills were made with."""
    import wallbangs
    out = []
    for w in wallbangs.load(mp)[:10]:
        team = 2 if w["side"] == "T" else 3
        wp = next((WB_WEAPON[k] for k in (w.get("weapons") or {}) if k in WB_WEAPON), RIFLE[team])
        name = {v: k for k, v in WB_WEAPON.items()}.get(wp, "rifle").replace("_silencer", "-S").upper()
        vic = [v for v in w.get("victims") or []][:3]
        if not vic:
            continue
        out.append({"id": f"wallbang:{mp}:{w['side']}:{w.get('from_key')}>{w.get('to_key')}", "kind": "aim", "map": mp,
                    "title": f"WALLBANG {w['from']} → {w['to']} ({w['side']})",
                    "tip": f"through the wall with the {name}: {w['n']} kills from here in my base · shoot where they stand, a few bullets",
                    "team": team, "me": {"pos": w["pos"], "ang": _angle(w["pos"], vic[0])}, "weapons": ["weapon_knife", wp],
                    "bot_weapons": ["weapon_knife", RIFLE[5 - team]],
                    "bots": [{"pos": v, "ang": _angle(v, w["pos"]), "zone": replay_zone(w.get("to_key") or "", mp)} for v in vic],
                    "weight": 1 + w["n"] / 5})
    return out


def situation_drills(sid, mp, all_sc=None):
    return [{"id": s["id"], "kind": "situation", "map": s["map"], "title": f"R{s['round']} · " + (
                f"1v{s['vs']} clutch" if s["kind"] == "clutch" else "death") + (f" · {replay_zone(s['zone'], mp)}" if s.get("zone") else ""),
             "tip": (f"you died to {s['by']} ({s.get('weapon')})" if s.get("by") else "you lost it") +
                    ("" if s["kind"] == "clutch" else (" · first death" if s.get("opening") else "") + ("" if s.get("traded") else " · not traded")),
             "mid": s["mid"], "round": s["round"], "sk": s["kind"], "t": s["t"], "weight": s["score"]}
            for s in (all_sc if all_sc is not None else replay.scenarios(sid, n=40)) if s["map"] == mp]


# ---------------------------------------------------------------- the session

def build(sid, minutes=20, where="random", difficulty=2):
    """The plan of a session: blocks of each map, drills picked (due first, then at random by importance), the
    situations' scenario files built. Written to the server's coach/sessions folder."""
    sid = str(sid)
    p = ingest()
    nsess = len(p["sessions"])
    mine = maps(sid)
    if not mine:
        raise ValueError("no match with a demo yet")
    names = list(mine)
    try:
        S = struggles(sid)
    except Exception as e:
        print("struggles:", e, flush=True)
        S = []
    top = max((x["score"] for x in S), default=0) or 1
    hard = {m: min(1.0, sum(x["score"] for x in S if x["map"] == m) / top) for m in names}   # your struggles: their maps come up more
    picked_maps = [m for m in str(where).split(",") if m in mine]   # Prepare's maps (one to three)
    if picked_maps:
        chosen = picked_maps[:3]
    elif where == "mix":
        k = 1 if minutes < 15 else 2 if minutes < 30 else 3
        w = np.array([mine[m] * (1 + 2 * hard[m]) for m in names], float)
        chosen = list(np.random.choice(names, size=min(k, len(names)), replace=False, p=w / w.sum()))
    else:
        w = np.array([mine[m] * (1 + 2 * hard[m]) for m in names], float)
        chosen = [str(np.random.choice(names, p=w / w.sum()))]
    per_map = minutes * 60 / len(chosen)
    warm = minutes <= WARMUP_MIN   # a quick warm-up before a game: the hands only (aim, defense, prefire), no stuff, no situation
    split = splits(minutes)
    all_sc = [] if warm else replay.scenarios(sid, n=40)
    blocks, todo = [], []
    if split.get("aim"):   # the aim first, on the aim map, for all the maps' share (06/10)
        secs = minutes * 60 * split["aim"]
        blocks.append({"map": AIM_MAP, "kind": "aim", "seconds": int(secs), "drills": aim_range_drills(sid, secs)})
    for mp in chosen:
        pr = practice_drills(sid, mp)
        fns = {"defend": lambda s_, m_: [d for d in pr if d.get("mode") == "defend"],
               "push": lambda s_, m_: [d for d in pr if d.get("mode") == "prefire"], "nade": nade_drills,
               "wallbang": wallbang_drills, "situation": lambda s_, m_: situation_drills(s_, m_, all_sc)}
        share = {k: v for k, v in split.items() if k != "aim"}
        if not pr:   # a hostage map: no site to defend or push, the situations take their time
            share["situation"] = share.get("situation", 0) + share.pop("defend", 0) + share.pop("push", 0)
        kinds = [(k, fns[k]) for k in ORDER if share.get(k)]
        bad = {(m_, r_) for x in S if x["map"] == mp for m_, r_ in x["rounds"]}   # the rounds you struggled in
        spare = 0.0   # a part with nothing to train on this map gives its time to the next ones
        for kind, fn in kinds:
            secs = per_map * share[kind] + spare
            cands = fn(sid, mp)
            if not cands:
                spare = secs
                continue
            spare = 0.0
            for c in cands:   # your struggles first: the defense of that site, its pushes, the rounds you lost there
                site = None
                if c.get("mode") in ("defend", "prefire"):
                    site = next((s_ for s_ in ("A", "B") if f"Bombsite{s_}" in c["id"] or f":{s_} " in c.get("title", "") or c.get("title", "").endswith(f" {s_}")), None)
                    if site is None:
                        site = next((s_ for s_ in ("A", "B") if f"DEFEND {s_}" in c.get("title", "") or f"PUSH {s_}" in c.get("title", "")), None)
                if site:
                    b = _boost(S, mp, "CT" if c.get("mode") == "defend" else "T", site)
                    if b > 1.05:
                        c["weight"] = c.get("weight", 1.0) * b
                        why = next((x for x in S if x["map"] == mp and x["site"] == site and x["side"] == ("CT" if c.get("mode") == "defend" else "T")), None)
                        if why:
                            c["tip"] = f"{c.get('tip', '')} · priority: {why['text']} lately".strip(" ·")
                if kind == "situation" and (str(c.get("mid")), int(c.get("round") or 0)) in bad:
                    c["weight"] = c.get("weight", 1.0) * 3
            n = max(1, int(secs / EST[kind]) + 1)
            picked = _pick(cands, n, p["items"], nsess, weight=lambda c: c.get("weight", 1.0))
            drills = []
            for d in picked:
                if kind == "nade":   # guided, then the spot and how, then the spot only
                    d["level"] = min(2, (p["items"].get(d["id"]) or {}).get("box", 0))
                    side_, t_med = d.pop("_vic", [None, None])
                    try:
                        d["victims"] = _victims(mp, d["team"], d["type"], d.get("target"), d["me"]["pos"], side_, t_med)
                    except Exception as e:
                        print("victims", d["id"], e, flush=True)
                if kind == "push":
                    _by_level(d, difficulty)
                if kind == "situation":   # its file is built below (the plugin waits for it if it comes to it first)
                    d["scenario"] = d["id"]
                    todo.append(d)
                d.pop("weight", None)
                drills.append(d)
            if drills:
                blocks.append({"map": mp, "kind": kind, "seconds": int(secs), "drills": drills})
    if not blocks:
        raise ValueError("nothing to train on these maps yet")
    sid_ = time.strftime("s%Y%m%d_%H%M%S")
    sess = {"id": sid_, "minutes": minutes, "where": where, "maps": chosen, "difficulty": int(difficulty),
            "level": level(p["xp"]), "warmup": warm, "blocks": blocks}
    os.makedirs(SESS, exist_ok=True)
    first = [d for d in blocks[0]["drills"] if blocks[0]["kind"] == "situation"][:1]
    for d in first:   # a session that starts with a situation: that one now
        _scenario(sid, d)
    json.dump(sess, open(os.path.join(SESS, f"{sid_}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    rest = [d for d in todo if d not in first]
    if rest:   # the others while you play the first blocks (demo parsing: about 2 s each)
        import threading
        from concurrent.futures import ThreadPoolExecutor
        threading.Thread(target=lambda: list(ThreadPoolExecutor(3).map(lambda d: _scenario(sid, d), rest)), daemon=True).start()
    p["sessions"].append({"id": sid_, "t": time.time(), "minutes": minutes, "maps": chosen, "done": False, "difficulty": int(difficulty)})
    _save(p)
    return sess


def preview(sid, minutes=20, where="random"):
    """What a warm-up will be, before it's built (Prepare shows it under its button): each part's minutes, map by map;
    a part without data on a map (no wallbang found there yet) gives its time to the next one."""
    import wallbangs
    sid = str(sid)
    mine = maps(sid) if sid.isdigit() else {}
    chosen = [m for m in str(where).split(",") if m in mine][:3] or [where if where in mine else "random"]
    split, out = splits(minutes), []
    per_map = minutes * 60 / len(chosen)
    if split.get("aim"):   # the aim first, on the aim map (06/10)
        out.append({"map": AIM_MAP, "kind": "aim", "seconds": int(minutes * 60 * split["aim"])})
    for mp in chosen:
        share = {k: v for k, v in split.items() if k != "aim"}
        if mp.startswith("cs_"):
            share["situation"] = share.get("situation", 0) + share.pop("defend", 0) + share.pop("push", 0)
        spare = 0.0
        for k in ORDER:
            if not share.get(k):
                continue
            secs = per_map * share[k] + spare
            if k == "wallbang" and mp != "random" and not wallbangs.load(mp):
                spare = secs
                continue
            spare = 0.0
            out.append({"map": mp, "kind": k, "seconds": int(secs)})
    return out


def _scenario(sid, d):
    try:
        replay.build(sid, d["mid"], d["round"], d["sk"], d.get("t"))
    except Exception as e:
        print("situation", d["id"], repr(e), flush=True)


def suggest(sid, p=None):
    """What the page preselects (04/10: "the bots' level from my level in training", "a 5 min warm-up when I know my
    stuff or I just played"): the bots' level from your last two sessions (85 % of the drills or more: one up; half or
    less: one down; else the same), the warm-up when your last match ended under two hours ago or you master most of
    your lineups."""
    p = p or progress()
    done = [x for x in p["sessions"] if x.get("done") and x.get("drills")][-2:]
    last = next((x for x in reversed(p["sessions"]) if x.get("difficulty") is not None), None)
    d = int(last["difficulty"]) if last else None
    if d is None and done:   # sessions before 04/10: the level is in their file
        try:
            with open(os.path.join(SESS, f"{done[-1]['id']}.json"), encoding="utf-8") as fh:
                d = int(json.load(fh).get("difficulty", 2))
        except (OSError, ValueError):
            d = None
    rate = sum(x.get("ok", 0) for x in done) / max(1, sum(x.get("drills", 0) for x in done)) if done else None
    diff, why = (2 if d is None else d), "your last level"
    if d is not None and rate is not None and rate >= 0.85 and d < 3:
        diff, why = d + 1, f"{round(100 * rate)} % of your last drills ✔: one level up"
    elif d is not None and rate is not None and rate <= 0.5 and d > 0:
        diff, why = d - 1, f"{round(100 * rate)} % of your last drills ✔: one level down"
    warm, wwhy = False, ""
    try:   # your last match: the match list (start + length), you among its players
        acc = int(sid) - 76561197960265728
        with open(os.path.join(config.CACHE, "matches.json"), encoding="utf-8") as fh:
            reg = json.load(fh)
        ends = [time.mktime(time.strptime(m["time"][:16], "%Y-%m-%dT%H:%M")) + (m.get("duration_s") or 2400)
                for m in reg.values() if acc in (m.get("accounts") or []) and m.get("time")]
        if ends and time.time() - max(ends) < 2 * 3600:
            warm, wwhy = True, "you played a match less than two hours ago"
    except (OSError, ValueError, TypeError, KeyError):
        pass
    nade = [v for k, v in p["items"].items() if k.startswith("nade:")]
    if not warm and len(nade) >= 8 and sum(v["box"] >= 2 for v in nade) >= 0.7 * len(nade):
        warm, wwhy = True, "you master most of your lineups"
    return {"diff": diff, "why": why, "warmup": warm, "warm_why": wwhy}


def summary(sid=None):
    """For the page: level, XP, last sessions, what comes back next time, what to preselect."""
    p = ingest()
    nsess = len(p["sessions"])
    due = [k for k, v in p["items"].items() if v["next"] <= nsess]
    kinds = {}
    for k in due:
        kinds[k.split(":")[0] if ":" in k else "situation"] = kinds.get(k.split(":")[0] if ":" in k else "situation", 0) + 1
    stars = {k: v["box"] for k, v in p["items"].items()}
    return {**level(p["xp"]), "sessions": p["sessions"][-5:], "due": kinds, "mastered": sum(1 for v in stars.values() if v >= 3),
            "items": len(stars), "suggest": suggest(sid, p) if sid and str(sid).isdigit() else None}


def _game_running():
    """The game runs (the training server is a cs2.exe too: the one started with -dedicated)."""
    import subprocess
    ps = "Get-CimInstance Win32_Process -Filter \"name='cs2.exe'\" | ForEach-Object { $_.CommandLine }"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=replay.NO_WINDOW)
    return any(ln.strip() and "-dedicated" not in ln for ln in r.stdout.splitlines())


def _console():
    import chatcalls
    f = chatcalls.console_file()
    return f if f and os.path.exists(f) else None


def _menu_since(start_size):
    """The game's main menu is up since the launch, its background map loaded (its console log is written again at
    each launch): a connect given before that is cut while the map loads (LOOPSHUTDOWN, seen on 03/10)."""
    f = _console()
    if not f:
        return False
    size = os.path.getsize(f)
    with open(f, "rb") as fh:
        fh.seek(0 if size < start_size else start_size)
        t = fh.read()
    return b"-> CSGO_GAME_UI_STATE_MAINMENU" in t and b"Connected to 'loopback" in t


def _connect():
    """The game sent to the server. A connect given while CS2 starts is lost (it runs before the menu is ready): a
    closed game is started first, the connect waits for its menu. First the game's own connect (Steam passes it to the
    running game), then Steam's: Steam's opens its "game info" window, whose check of the local server fails ("the app
    ID given by the server is invalid", 06/10) while its "Join" button works."""
    urls = [f"steam://rungame/730/76561202255233023/+connect%20127.0.0.1:{replay.PORT}", f"steam://connect/127.0.0.1:{replay.PORT}"]
    if not _game_running():
        f = _console()
        start = os.path.getsize(f) if f else 0
        os.startfile("steam://run/730")
        for _ in range(180):
            time.sleep(1)
            if _menu_since(start):
                break
        time.sleep(8)   # the menu settles
    for url in urls:
        os.startfile(url)
        for _ in range(30 if url.startswith("steam://rungame") else 60):
            time.sleep(1)
            h = replay.heartbeat()
            if h and h.get("humans"):
                time.sleep(10)   # still there 10 s later: in game (a connect cut while loading drops you before)
                h = replay.heartbeat()
                if h and h.get("humans"):
                    return True
    return False


def _quiet_start(mp):
    try:
        replay.start(mp)
    except Exception as e:   # play() starts it again and says why
        print("training server early start:", e, flush=True)


def play(sid, minutes=20, where="random", difficulty=2):
    """One Play: the session built, the server on its first map, the plugin told, and the game sent to the server
    (started first if it is closed). You only follow what the game shows."""
    import threading
    first = AIM_MAP if splits(minutes).get("aim") else next((m for m in str(where).split(",") if m in maps(sid)), None)
    pre = threading.Thread(target=lambda: _quiet_start(first), daemon=True) if first else None
    if pre:   # the server starts while the session is built (06/10: a minute and a half before anything happened)
        pre.start()
    sess = build(sid, minutes, where, difficulty)
    if pre:
        pre.join(timeout=150)   # never an RCON before its map runs: the server would then refuse 127.0.0.1
    replay.start(sess["blocks"][0]["map"])
    replay.rcon(f"css_session {sess['id']}")
    threading.Thread(target=_connect, daemon=True).start()
    return {"session": {k: sess[k] for k in ("id", "minutes", "maps")},
            "blocks": [{"map": b["map"], "kind": b["kind"], "seconds": b["seconds"], "n": len(b["drills"])} for b in sess["blocks"]],
            **replay.status()}
