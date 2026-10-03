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

import numpy as np
import pandas as pd

import config
import replay

STATE_F = os.path.join(config.OUT, "train_progress.json")
SITES_F = os.path.join(config.OUT, "train_sites.json")
SESS = os.path.join(replay.COACH, "sessions")
SPLIT = {"aim": 0.25, "nade": 0.25, "situation": 0.5}   # share of the time of each block
EST = {"aim": 85, "nade": 40, "situation": 45}   # seconds a drill takes, about (with a retry): how many to prepare
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
    their spots). Cached per map, rebuilt when the base grows."""
    try:
        cache = json.load(open(SITES_F, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    dirs = []
    for d in sorted(os.listdir(os.path.join(config.OUT, "deep"))):
        try:
            if json.load(open(os.path.join(config.OUT, "deep", d, "meta.json"), encoding="utf-8")).get("map") == mp:
                dirs.append(d)
        except (OSError, ValueError):
            continue
    if mp in cache and cache[mp].get("n") == len(dirs) and cache[mp].get("v") == 2:
        return cache[mp]
    rows = []
    for d in dirs:
        try:
            D = pd.read_parquet(os.path.join(config.OUT, "deep", d, "duels.parquet"))
        except Exception:
            continue
        for _, r in D[D.t <= 75].iterrows():
            if {r.killer_side, r.victim_side} != {"T", "CT"}:
                continue
            ct = "killer" if r.killer_side == "CT" else "victim"
            tt = "victim" if ct == "killer" else "killer"
            rows.append({"time": float(r.t), "ct": (r[f"{ct}_X"], r[f"{ct}_Y"], r[f"{ct}_Z"]), "ct_zone": r[f"{ct}_zone"],
                         "t": (r[f"{tt}_X"], r[f"{tt}_Y"], r[f"{tt}_Z"]), "t_zone": r[f"{tt}_zone"]})
    R = pd.DataFrame(rows)
    sites = {}
    if len(R):
        for z in sorted({z for z in R.ct_zone.dropna().unique() if "Bombsite" in str(z)}):
            S = R[R.ct_zone == z]
            if len(S) < 25:
                continue
            cen = np.median(np.array(S.ct.tolist(), float), axis=0)
            near = R[[math.dist(c, cen) < 1500 for c in R.ct]]
            ents = []
            for tz, g in near.groupby("t_zone"):   # where the Ts were when they fought the site's CTs
                if not isinstance(tz, str) or tz == z or len(g) < 12:
                    continue
                T = np.array(g.t.tolist(), float)
                dist = float(np.median([math.dist(p, cen) for p in T]))
                if dist < 500:
                    continue
                CP = np.array(g.ct.tolist(), float)
                holds = _spread(_cells(CP), 12)   # the CT spots facing that entrance
                tm = g.time.to_numpy()
                spawn = _spread(_cells(T), 3, gap=200, keep=lambda p: math.dist(p, cen) > 700)
                if len(holds) < 4 or not spawn:
                    continue
                tcen = np.median(T, axis=0)
                ents.append({"zone": tz, "n": int(len(g)), "dist": round(dist),
                             "start": [round(float(v), 1) for v in _spread(_cells(T), 1)[0][1]],
                             "holds": [{"pos": [round(float(v), 1) for v in p], "ang": _angle(p, tcen), "n": c, "t": _hold_t(CP, tm, p)}
                                       for c, p in holds],
                             "spawns": [[round(float(v), 1) for v in p] for _, p in spawn]})
            ents.sort(key=lambda e: -e["n"])
            spot = _spread(_cells(np.array(S.ct.tolist(), float)), 1)[0][1]   # the CTs' favourite spot on the site
            sites[z] = {"center": [round(float(v), 1) for v in cen], "defend": [round(float(v), 1) for v in spot], "entrances": ents[:4]}
    cache[mp] = {"n": len(dirs), "v": 2, "sites": sites}
    json.dump(cache, open(SITES_F, "w", encoding="utf-8"))
    return cache[mp]


def _timings(holds):
    """When each angle peeks, from the real timings (the earliest at once, the others after it, compressed by half,
    within 30 s): the bots show up like the players do, at recurring moments."""
    ts = [h.get("t") for h in holds]
    if not ts or any(t is None for t in ts):
        return [0.0] * len(holds)
    t0 = min(ts)
    return [round(min(30.0, (t - t0) * 0.5), 1) for t in ts]


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
        for e in pick[:2]:
            frm = replay_zone(e["zone"], mp)
            start = e["start"]
            first = min(e["holds"], key=lambda h: math.dist(h["pos"], start))
            out.append({"id": f"prefire:{mp}:{z}:{e['zone']}", "kind": "aim", "mode": "prefire", "map": mp,
                        "title": f"PREFIRE {site} from {frm}", "team": 2,
                        "tip": f"{len(e['holds'])} CTs on the angles they really hold, peeking at their real timings · they don't shoot · clear them all, fast",
                        "me": {"pos": start, "ang": _angle(start, first["pos"])},
                        "weapons": ["weapon_knife", RIFLE[2]], "bot_weapons": ["weapon_knife", RIFLE[3]],
                        "bots": [{"pos": h["pos"], "ang": h["ang"], "zone": site, "at": at} for h, at in zip(e["holds"], _timings(e["holds"]))],
                        "seconds": 75, "weight": 2 + min(1.0, e["n"] / 400)})
        spawns = [{"pos": p, "ang": _angle(p, S["defend"]), "zone": replay_zone(e["zone"], mp)} for e in S["entrances"] for p in e["spawns"]]
        if len(spawns) >= 2:
            froms = ", ".join(dict.fromkeys(replay_zone(e["zone"], mp) for e in S["entrances"]))
            out.append({"id": f"defend:{mp}:{z}", "kind": "aim", "mode": "defend", "map": mp, "title": f"DEFEND {site}",
                        "team": 3, "tip": f"90 s · they come from {froms} · frag as many as you can · you respawn",
                        "me": {"pos": S["defend"], "ang": _angle(S["defend"], spawns[0]["pos"])},
                        "weapons": ["weapon_knife", RIFLE[3]], "bot_weapons": ["weapon_knife", RIFLE[2], "weapon_c4"],
                        "bots": spawns, "seconds": 90, "alive": 3, "weight": 4})
    return out


def replay_zone(z, mp=None):
    import nades
    return nades.humanize(z, mp) or str(z)


def _world(mp, px, py):
    import mapdata
    r = mapdata.get(mp)
    f = r.get("px_factor", 1.0)
    return [round(px / f * r["scale"] + r["pos_x"], 1), round(r["pos_y"] - py / f * r["scale"], 1)]


def nade_drills(sid, mp):
    """The lineups your plan recommends on this map (the zones you play, both sides)."""
    try:
        a = json.load(open(os.path.join(config.player_dir(sid), "advice.json"), encoding="utf-8"))
        M = a["plan"]["nades"]["maps"][mp]
    except (OSError, ValueError, KeyError):
        return []
    out = []
    for side, S in M.items():
        if not isinstance(S, dict):
            continue
        team = 2 if side == "T" else 3
        for typ, T in (S.get("types") or {}).items():
            for x in (T.get("picks") or [])[:3]:
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
                out.append({"id": f"nade:{mp}:{side}:{typ}:{x['from_key']}>{x['to_key']}", "kind": "nade", "map": mp,
                            "title": f"{name} → {x['to']}", "tip": f"from {x['from']} · {x.get('timer') or ''}".strip(" ·"),
                            "team": team, "type": typ, "item": item, "how": x.get("how") or "standing still",
                            "click": {"right": "right click", "both": "left + right click"}.get(x.get("click"), "left click"),
                            "me": {"pos": pos, "ang": ang}, "target": _world(mp, *x["to_px"]),
                            "weight": 1 + 10 * float(x.get("score") or 0)})
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
    if where in mine:
        chosen = [where]
    elif where == "mix":
        k = 1 if minutes < 15 else 2 if minutes < 30 else 3
        w = np.array([mine[m] for m in names], float)
        chosen = list(np.random.choice(names, size=min(k, len(names)), replace=False, p=w / w.sum()))
    else:
        w = np.array([mine[m] for m in names], float)
        chosen = [str(np.random.choice(names, p=w / w.sum()))]
    per_map = minutes * 60 / len(chosen)
    all_sc = replay.scenarios(sid, n=40)
    blocks, todo = [], []
    for mp in chosen:
        aim = lambda s_, m_: practice_drills(s_, m_) or aim_drills(s_, m_)   # hostage maps: your duel spots
        for kind, fn in (("aim", aim), ("nade", nade_drills), ("situation", lambda s_, m_: situation_drills(s_, m_, all_sc))):
            secs = per_map * SPLIT[kind]
            cands = fn(sid, mp)
            if not cands:
                continue
            n = max(1, int(secs / EST[kind]) + 1)
            picked = _pick(cands, n, p["items"], nsess, weight=lambda c: c.get("weight", 1.0))
            if kind == "aim":   # a warm-up first: the prefires, then the defenses
                picked.sort(key=lambda c: {"prefire": 0, "defend": 1}.get(c.get("mode"), 2))
            drills = []
            for d in picked:
                if kind == "nade":   # guided, then the spot and how, then the spot only
                    d["level"] = min(2, (p["items"].get(d["id"]) or {}).get("box", 0))
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
            "level": level(p["xp"]), "blocks": blocks}
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
    p["sessions"].append({"id": sid_, "t": time.time(), "minutes": minutes, "maps": chosen, "done": False})
    _save(p)
    return sess


def _scenario(sid, d):
    try:
        replay.build(sid, d["mid"], d["round"], d["sk"], d.get("t"))
    except Exception as e:
        print("situation", d["id"], repr(e), flush=True)


def summary():
    """For the page: level, XP, last sessions, what comes back next time."""
    p = ingest()
    nsess = len(p["sessions"])
    due = [k for k, v in p["items"].items() if v["next"] <= nsess]
    kinds = {}
    for k in due:
        kinds[k.split(":")[0] if ":" in k else "situation"] = kinds.get(k.split(":")[0] if ":" in k else "situation", 0) + 1
    stars = {k: v["box"] for k, v in p["items"].items()}
    return {**level(p["xp"]), "sessions": p["sessions"][-5:], "due": kinds, "mastered": sum(1 for v in stars.values() if v >= 3),
            "items": len(stars)}


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
    closed game is started first, the connect waits for its menu; tried twice."""
    url = f"steam://connect/127.0.0.1:{replay.PORT}"
    if not _game_running():
        f = _console()
        start = os.path.getsize(f) if f else 0
        os.startfile("steam://run/730")
        for _ in range(180):
            time.sleep(1)
            if _menu_since(start):
                break
        time.sleep(8)   # the menu settles
    for _ in range(2):
        os.startfile(url)
        for _ in range(45):
            time.sleep(1)
            h = replay.heartbeat()
            if h and h.get("humans"):
                time.sleep(10)   # still there 10 s later: in game (a connect cut while loading drops you before)
                h = replay.heartbeat()
                if h and h.get("humans"):
                    return True
    return False


def play(sid, minutes=20, where="random", difficulty=2):
    """One Play: the session built, the server on its first map, the plugin told, and the game sent to the server
    (started first if it is closed). You only follow what the game shows."""
    import threading
    sess = build(sid, minutes, where, difficulty)
    replay.start(sess["blocks"][0]["map"])
    replay.rcon(f"css_session {sess['id']}")
    threading.Thread(target=_connect, daemon=True).start()
    return {"session": {k: sess[k] for k in ("id", "minutes", "maps")},
            "blocks": [{"map": b["map"], "kind": b["kind"], "seconds": b["seconds"], "n": len(b["drills"])} for b in sess["blocks"]],
            **replay.status()}
