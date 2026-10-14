"""Momentum: moving on the real maps (rework_entrainement.md, section 9; the user: "Momentum: a dedicated movement
training mode built to improve your map mobility, pathing, and jump precision using real map assets"). A module of its
own (a focus block), four drills, all from the base's real rounds:
- route: a real way run against the clock, a T or CT spawn to a site or a CT rotation from one site to the other. Its
  checkpoints on the ground in order (the gold line too, until you ran it once), your time at each one against the
  base's pace, at the end against the base's runs of that way (their median), its fastest runs (their 10th percentile)
  and the pros';
- jump: a jump the base's players really make onto something (a box, a ledge, a window), from its takeoff to where they
  land; the training server checks you land on top;
- stop: counter-strafing (the level's first fundamental): run left and right, STOP comes at full speed; measured, the
  time from your speed's drop to an accurate stop, and whether you went the other way after;
- silent: the last stretch of a real way into a site, walked (Shift) in the time given: a footstep heard is a miss.
The movement useful in a match only: no bunny hop, no surf (the document's proposal, 14/10).

Built on the coach's PC from the base (shipped with it, like the entries and Crossfire): out/train_momentum/<map>.json
- routes: every player's run from his spawn to the first site he entered, each CT's from one site to the other, running
  all the way (150 u/s or more each half second but one), from the matches' samples (every 0.5 s); grouped by their
  start, their site and the first three places they cross; the two most run ways of each start and site, 8 runs at
  least. A way's line is its most typical run read again from its demo (every 2 ticks, on the ground);
- jumps: from the demos (the game's player_jump), the jumps whose player landed 32 to 72 u higher on solid ground (not on
  a teammate: that is a boost), grouped by their takeoff and their landing; 6 jumps of 4 matches at least, outside the
  spawns; the kills its jumpers made from up there in the next 15 s.

Usage: python -m wily.training.momentum [map ...] (every bomb map of the base by default)."""
import json
import math
import os
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

from wily.core import config
from wily.core import i18n
from wily.training import crossfire

MO_D = os.path.join(config.OUT, "train_momentum")
V = 1
MATCHES = 400   # the base's matches read per map for the ways (their samples)
DEMOS = 120   # demos parsed per map for the jumps
RUN = 75.0   # u in half a second: running (150 u/s; a knife 250, a rifle 215, a walk 130)
MIN_RUNS = 8   # runs of a way at least
CP_EVERY = 450.0   # u between two checkpoints
CP_R, END_R = 120.0, 140.0   # how near a checkpoint counts, the way's end (Momentum.cs: the same)
SILENT_LEN = 750.0   # the silent walk's stretch, before the site
CLIMB = (32.0, 72.0)   # a jump onto something: higher than a step (18 u), lower than a boost
SITE = {"BombsiteA": "A", "BombsiteB": "B"}
HOW = {"jump": i18n.N_("jump"), "run": i18n.N_("running jump"), "duck": i18n.N_("crouch-jump"), "run+duck": i18n.N_("running crouch-jump")}


def path(mp):
    return os.path.join(MO_D, f"{mp}.json")


def load(mp, build=True):
    """The map's momentum data (cached); {} where it can't be built (a player's copy without it, no demo)."""
    try:
        with open(path(mp), encoding="utf-8") as f:
            c = json.load(f)
        if c.get("v") == V:
            return c
    except (OSError, ValueError):
        pass
    if not build or config.role() == "client":
        return {}
    from wily.training import replay
    return replay.in_worker(_build, mp)


# ---------------------------------------------------------------- the ways

def _bearing(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def _route(zones, mp, limit=3):
    """The places a run crosses, in order, flickers dropped (A B A -> A): its way's name."""
    from wily.insights import nades
    out = []
    for z in zones:
        n = nades.humanize(z, mp) if isinstance(z, str) and z else None
        if not n or n == "?" or (out and out[-1] == n):
            continue
        if len(out) >= 2 and out[-2] == n:
            out.pop()
            continue
        out.append(n)
    return out[:limit]


def _runs(S, mp=None):
    """A match's running ways (its samples, every 0.5 s: tick, steamid, side, round, t, X, Y, Z, zone): each player's
    run from his spawn to the first site he entered, each CT's from one site to the other with no stop in between.
    t: the time to the way's end as the training server counts it (its last 140 u: the end's ring)."""
    out = []
    if S is None or not len(S):
        return out
    S = S.sort_values(["round", "steamid", "t"])
    for (rnd, sid), g in S.groupby(["round", "steamid"], sort=False):
        side = g.side.iloc[0]
        if len(g) < 5 or side not in ("T", "CT"):
            continue
        t = g.t.to_numpy(float)
        P = g[["X", "Y", "Z"]].to_numpy(float)
        tk = g.tick.to_numpy(np.int64)
        zones = g.zone.to_numpy(object)
        site = [SITE.get(z) if isinstance(z, str) else None for z in zones]
        step = np.r_[0.0, np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))]
        gap = np.r_[False, np.diff(t) > 0.75]   # a sample missing: dead, or not read

        def running(a, b):
            s = step[a + 1:b + 1]
            return len(s) >= 4 and not gap[a + 1:b + 1].any() and int((s < RUN).sum()) <= 1

        def run(kind, frm, a, b):
            dt = float(t[b] - t[a])
            v = float(step[a + 1:b + 1].sum()) / max(0.5, dt)
            return {"kind": kind, "side": side, "from": frm, "to": site[b], "t": round(dt - min(0.5, END_R / max(1.0, v)), 2),
                    "zones": _route([z for z in zones[a + 1:b] if z != zones[a]], mp), "P": P[a:b + 1], "tick0": int(tk[a]), "tick1": int(tk[b]), "sid": str(sid), "round": int(rnd)}
        if t[0] <= 0.6:   # there at the round's start: his spawn
            k = next((i for i in range(len(t)) if site[i]), None)
            if k is not None and k >= 4 and t[k] - t[0] <= 45 and running(0, k):
                out.append(run("spawn", side, 0, k))
        if side != "CT":
            continue
        i = 0
        while i < len(t) - 1:   # a CT's rotation: his last sample on a site, then the other site, running all the way
            if site[i] and site[i + 1] != site[i]:
                j = next((q for q in range(i + 1, len(t)) if site[q]), None)
                if j is None:
                    break
                if site[j] != site[i] and j - i >= 4 and t[j] - t[i] <= 40 and running(i, j):
                    out.append(run("rotate", site[i], i, j))
                i = j
                continue
            i += 1
    return out


def _resample(P, k=32):
    P = np.asarray(P, float)
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(P[:, :2], axis=0).T))]
    if d[-1] <= 0:
        return None
    u = np.linspace(0, d[-1], k)
    return np.c_[np.interp(u, d, P[:, 0]), np.interp(u, d, P[:, 1])]


def _length(Q):
    Q = np.asarray(Q, float)
    return float(np.hypot(*np.diff(Q[:, :2], axis=0).T).sum()) if len(Q) > 1 else 0.0


def _at(Q, L):
    """The point of a line at L u along it (on the ground: its height between its points)."""
    Q = np.asarray(Q, float)
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(Q[:, :2], axis=0).T))]
    i = int(np.clip(np.searchsorted(d, L) - 1, 0, len(Q) - 2))
    a = 0.0 if d[i + 1] <= d[i] else (L - d[i]) / (d[i + 1] - d[i])
    return Q[i] + (Q[i + 1] - Q[i]) * min(1.0, max(0.0, a))


def marks(line):
    """A way's checkpoints: one every 450 u along its line, and its end: [x, y, z, its share of the way]."""
    total = _length(line)
    out = []
    L = CP_EVERY
    while total > 0 and L < total - CP_EVERY / 2:
        p = _at(line, L)
        out.append([round(float(p[0]), 1), round(float(p[1]), 1), round(float(p[2]), 1), round(L / total, 3)])
        L += CP_EVERY
    e = np.asarray(line[-1], float)
    out.append([round(float(e[0]), 1), round(float(e[1]), 1), round(float(e[2]), 1), 1.0])
    return out


def _simple_line(P):
    """A way from half-second samples: its turns kept within 16 u (the 2-tick line's smoothing would flatten them)."""
    from wily.training import train
    Q = np.asarray(P, float)[:, :3]
    keep = train._rdp(Q, 16.0) if len(Q) > 2 else list(range(len(Q)))
    return [[round(float(v), 1) for v in Q[i]] for i in keep]


def _ways(runs, pro, mp):
    """The ways: runs grouped by their kind, side, start, site and first three places; for each start and site the two
    most run (8 runs at least), the base's median time, its fastest runs' (10th percentile), the pros'. "_cands": the
    runs nearest to its most typical one (one of them is read again from its demo for the line)."""
    groups = {}
    for r in runs:
        groups.setdefault((r["kind"], r["side"], r["from"], r["to"], tuple(r["zones"])), []).append(r)
    pros = {}
    for r in pro or []:
        pros.setdefault((r["kind"], r["side"], r["from"], r["to"], tuple(r["zones"])), []).append(r["t"])
    best = {}
    for key, g in groups.items():
        if len(g) >= MIN_RUNS:
            best.setdefault(key[:4], []).append((len(g), key))
    out = []
    for head, ks in sorted(best.items()):
        for n, key in sorted(ks, reverse=True)[:2]:
            g = groups[key]
            A = [x for x in (_resample(r["P"]) for r in g)]
            ok = [i for i, a in enumerate(A) if a is not None]
            if len(ok) < MIN_RUNS:
                continue
            M = np.array([A[i] for i in ok])
            dist = np.array([np.mean(np.hypot(*(M - m).transpose(2, 0, 1))) for m in M])
            order = [ok[i] for i in np.argsort(dist)]
            ts = np.array([r["t"] for r in g], float)
            pt = pros.get(key) or []
            kind, side, frm, to = head
            out.append({"id": f"{kind}:{side}:{frm}>{to}:{'>'.join(key[4])}", "kind": kind, "side": side, "from": frm, "to": to,
                        "via": list(key[4]), "n": len(g), "base": round(float(np.median(ts)), 2),
                        "best": round(float(np.percentile(ts, 10)), 2), "pro": round(float(np.median(pt)), 2) if len(pt) >= 3 else None,
                        "pro_n": len(pt), "_cands": [g[i] for i in order[:6]]})
    return out


def _finish(w, P, mp, fine=True):
    """A way's line on the ground, its checkpoints, its start and the way it faces, from its run's positions (fine: read
    from its demo every 2 ticks, else its half-second samples)."""
    from wily.training import train
    P = np.asarray(P, float)
    line = train._ground_line(P, mp) if fine else _simple_line(P)
    start = [round(float(v), 1) for v in P[0]]
    line[0] = start
    total = _length(line)
    ahead = _at(line, min(150.0, total))
    w.update(start=start, yaw=round(_bearing(start, ahead), 1), len=round(total), line=line, marks=marks(line))
    return w


# ---------------------------------------------------------------- the jumps

def _jumps(T, J, K, rounds, mid, mp=None):
    """A demo's jumps onto something. T: its players' ticks around the jumps (every 2 ticks: steamid, tick, X, Y, Z,
    is_airborne, ducking, last_place_name, team_num, g: the ground entity, pawn), J: its player_jump events (tick,
    user_steamid), K: its kills (tick, attacker_steamid, attacker_X/Y/Z), rounds: [(freeze end, end)]. Each jump:
    its takeoff, its landing (the first tick on the ground after it), its run-up's start (back while he ran, 0.6 s at
    most, same floor), crouched in the air or not, its speed, and the kills its jumper made from up there."""
    from wily.insights import nades
    out = []
    if T is None or not len(T) or J is None or not len(J):
        return out
    T = T.copy()
    T["steamid"] = T.steamid.astype(str)
    pawns = set(T.pawn.dropna().astype("int64")) if "pawn" in T else set()
    T = T.set_index(["steamid", "tick"]).sort_index()
    if K is not None and len(K):
        K = K.copy()
        K["attacker_steamid"] = K.attacker_steamid.astype(str)
    for k, sid in zip(J.tick.astype(int), J.user_steamid.astype(str)):
        rs = [a for a, b in rounds if a <= k <= b]
        if not rs:   # the freeze time, the warm-up, between two rounds
            continue
        try:
            g = T.loc[sid].loc[k - 40:k + 80]
        except KeyError:
            continue
        if len(g) < 20:
            continue
        ticks = g.index.to_numpy()
        i0 = int(np.searchsorted(ticks, k))
        if i0 >= len(g) - 4:
            continue
        air = g.is_airborne.astype(object).eq(True).to_numpy()
        land = next((i for i in range(i0 + 3, len(g)) if not air[i]), None)
        if land is None:
            continue
        P = g[["X", "Y", "Z"]].to_numpy(float)
        climb = float(P[land, 2] - P[i0, 2])
        if not CLIMB[0] <= climb <= CLIMB[1]:
            continue
        if "g" in g:
            gr = g.g.iloc[land]
            if gr == gr and gr is not None and int(gr) in pawns:   # on a teammate: a boost (boosts.py)
                continue
        duck = bool(g.ducking.iloc[i0:land + 1].astype(object).eq(True).any()) if "ducking" in g else False
        i8 = max(0, i0 - 4)
        speed = float(np.hypot(*(P[i0, :2] - P[i8, :2]))) / max(1e-3, (ticks[i0] - ticks[i8]) / 64)
        a = i0
        while a > 0 and ticks[i0] - ticks[a - 1] <= 40 and abs(P[a - 1, 2] - P[i0, 2]) < 24:
            dt = (ticks[a] - ticks[a - 1]) / 64
            if dt <= 0 or dt > 4 / 64 or np.hypot(*(P[a, :2] - P[a - 1, :2])) / dt < 100:
                break
            a -= 1
        kills = 0
        if K is not None and len(K):
            q = K[(K.attacker_steamid == sid) & (K.tick > ticks[land]) & (K.tick <= ticks[land] + 15 * 64)]
            if len(q):
                kills = int(((np.hypot(q.attacker_X.to_numpy(float) - P[land, 0], q.attacker_Y.to_numpy(float) - P[land, 1]) < 150)
                             & (np.abs(q.attacker_Z.to_numpy(float) - P[land, 2]) < 40)).sum())
        pl = g.last_place_name.astype(object).to_numpy() if "last_place_name" in g else [None] * len(g)
        tm = g.team_num.iloc[i0] if "team_num" in g else None
        out.append({"mid": str(mid), "from": [round(float(v), 1) for v in P[i0]], "to": [round(float(v), 1) for v in P[land]],
                    "start": [round(float(v), 1) for v in P[a]], "climb": round(climb, 1), "duck": duck, "speed": round(speed),
                    "t": round((k - rs[0]) / 64, 1), "side": {2: "T", 3: "CT"}.get(int(tm) if tm == tm and tm is not None else 0),
                    "kills": kills, "zone": nades.humanize(pl[land], mp) if isinstance(pl[land], str) and pl[land] else None,
                    "from_zone": nades.humanize(pl[i0], mp) if isinstance(pl[i0], str) and pl[i0] else None})
    return out


def _jump_spots(rows, mp=None, keep=20):
    """The jumps of the base grouped by their takeoff (72 u) and their landing (56 u, same heights): the spots 6 jumps
    of 4 matches at least made, outside the spawns, the most used first (matches, and the kills from up there twice)."""
    groups = []
    for x in sorted(rows, key=lambda x: (round(x["to"][0]), round(x["to"][1]), round(x["to"][2]))):
        for g in groups:
            c = g[0]
            if math.dist(c["to"][:2], x["to"][:2]) < 56 and abs(c["to"][2] - x["to"][2]) < 20 \
                    and math.dist(c["from"][:2], x["from"][:2]) < 72 and abs(c["from"][2] - x["from"][2]) < 24:
                g.append(x)
                break
        else:
            groups.append([x])
    out = []
    for g in groups:
        ms = {x["mid"] for x in g}
        if len(g) < 6 or len(ms) < 4:
            continue
        zone = Counter(x["zone"] for x in g if x["zone"]).most_common(1)
        zone = zone[0][0] if zone else "?"
        if "spawn" in zone.lower():
            continue
        To = np.array([x["to"] for x in g], float)
        med = np.median(To, axis=0)
        to = g[int(np.argmin(np.hypot(To[:, 0] - med[0], To[:, 1] - med[1]) + np.abs(To[:, 2] - med[2])))]["to"]
        frm = np.median(np.array([x["from"] for x in g], float), axis=0)
        run = float(np.mean([x["speed"] >= 150 for x in g]))
        duck = float(np.mean([bool(x["duck"]) for x in g]))
        start = frm
        ups = [x for x in g if x["speed"] >= 150 and math.dist(x["start"][:2], x["from"][:2]) > 40]
        if run >= 0.5 and ups:   # a run-up: the most typical one (its way in, and its takeoff near the spot's)
            b = np.radians([_bearing(x["start"], x["from"]) for x in ups])
            mb = math.degrees(math.atan2(np.sin(b).mean(), np.cos(b).mean()))
            pick = min(ups, key=lambda x: abs((_bearing(x["start"], x["from"]) - mb + 180) % 360 - 180) + math.dist(x["from"][:2], frm[:2]) / 10)
            start = np.asarray(pick["start"], float)
        how = ("run+" if run >= 0.5 else "") + ("duck" if duck >= 0.6 else "")
        how = {"run+": "run", "": "jump"}.get(how, how)
        sides = Counter(x["side"] for x in g if x["side"])
        out.append({"id": f"{round(to[0])}:{round(to[1])}:{round(to[2])}", "from": [round(float(v), 1) for v in frm], "to": to,
                    "start": [round(float(v), 1) for v in start], "yaw": round(_bearing(start if math.dist(start[:2], to[:2]) > 16 else frm, to), 1),
                    "climb": round(float(np.median([x["climb"] for x in g])), 1), "duck": round(duck, 2), "run": round(run, 2), "how": how,
                    "n": len(g), "matches": len(ms), "kills": int(sum(x["kills"] for x in g)), "zone": zone,
                    "from_zone": (Counter(x["from_zone"] for x in g if x["from_zone"]).most_common(1) or [("?", 0)])[0][0],
                    "side": sides.most_common(1)[0][0] if sides else "T", "t_med": round(float(np.median([x["t"] for x in g])), 1)})
    out.sort(key=lambda s: -(s["matches"] + 2 * s["kills"]))
    return out[:keep]


# ---------------------------------------------------------------- the build (the coach's PC)

def _deep_dirs(base, mp):
    out = []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return out
    for d in names:
        try:
            with open(os.path.join(base, d, "meta.json"), encoding="utf-8") as f:
                if json.load(f).get("map") == mp:
                    out.append(d)
        except (OSError, ValueError):
            continue
    return out


SAMPLE_COLS = ["tick", "steamid", "side", "round", "t", "X", "Y", "Z", "zone"]


def _match_runs(base, d, mp):
    try:
        S = pd.read_parquet(os.path.join(base, d, "samples.parquet"), columns=SAMPLE_COLS)
    except Exception:
        return []
    rs = _runs(S, mp)
    for r in rs:
        r["mid"] = d
    return rs


def _rounds(d):
    try:
        R = pd.read_parquet(os.path.join(config.DEEP, d, "rounds.parquet"), columns=["start_tick", "end_tick"])
        return [(int(a), int(b)) for a, b in zip(R.start_tick, R.end_tick) if a == a and b == b]
    except Exception:
        return []


def _demo_jumps(d, mp):
    """One demo of the base: its jumps onto something."""
    from demoparser2 import DemoParser
    dp = DemoParser(os.path.join(config.CACHE, f"{d}.dem"))
    try:
        J = dp.parse_event("player_jump")
    except Exception:
        J = None
    if not isinstance(J, pd.DataFrame) or not len(J) or "user_steamid" not in J:
        return []
    rounds = _rounds(d)
    J = J[[any(a <= int(k) <= b for a, b in rounds) for k in J.tick]]
    if not len(J):
        return []
    want = sorted({t for k in J.tick.astype(int) for t in range(k - 40, k + 81, 2)})
    T = dp.parse_ticks(["X", "Y", "Z", "is_airborne", "ducking", "last_place_name", "team_num",
                        "CCSPlayerPawn.m_hGroundEntity", "CCSPlayerController.m_hPlayerPawn"], ticks=want)
    T = T.rename(columns={"CCSPlayerPawn.m_hGroundEntity": "g", "CCSPlayerController.m_hPlayerPawn": "pawn"})
    try:
        K = dp.parse_event("player_death", player=["X", "Y", "Z"])
    except Exception:
        K = None
    if isinstance(K, pd.DataFrame) and not {"attacker_steamid", "attacker_X", "attacker_Y", "attacker_Z"} <= set(K.columns):
        K = None
    return _jumps(T, J, K, rounds, d, mp)


def _demo_way(r):
    """A way's run read again from its demo, every 2 ticks (None without its demo)."""
    f = os.path.join(config.CACHE, f"{r['mid']}.dem")
    if not os.path.exists(f):
        return None
    from demoparser2 import DemoParser
    T = DemoParser(f).parse_ticks(["X", "Y", "Z"], ticks=list(range(r["tick0"], r["tick1"] + 1, 2)))
    T = T[T.steamid.astype(str) == r["sid"]].sort_values("tick")
    return T[["X", "Y", "Z"]].to_numpy(float) if len(T) >= 10 else None


def _build(mp, matches=MATCHES, demos=DEMOS, log=print):
    os.makedirs(MO_D, exist_ok=True)
    t0 = time.time()
    dirs = _deep_dirs(config.DEEP, mp)
    runs = []
    for d in dirs[-matches:]:
        runs += _match_runs(config.DEEP, d, mp)
    pro = []
    pdir = os.path.join(config.OUT, "deep_pro")
    for d in _deep_dirs(pdir, mp):
        pro += _match_runs(pdir, d, mp)
    ways = _ways(runs, pro, mp)
    with_dem = [d for d in reversed(dirs) if os.path.exists(os.path.join(config.CACHE, f"{d}.dem"))][:demos]
    jrows = []
    for d in with_dem:
        config.wait_for_match_end(what="momentum")   # your match first
        try:
            jrows += _demo_jumps(d, mp)
        except Exception as e:
            log("momentum", d, e)
    out = {"v": V, "routes": [], "jumps": _jump_spots(jrows, mp)}
    for w in ways:
        cands = w.pop("_cands")
        P = None
        for r in cands:   # the most typical run whose demo is here, every 2 ticks (else its samples)
            try:
                P = _demo_way(r)
            except Exception as e:
                log("momentum way", r["mid"], e)
            if P is not None:
                break
        out["routes"].append(_finish(w, P, mp) if P is not None else _finish(w, cands[0]["P"], mp, fine=False))
    with open(path(mp), "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    log(f"momentum {mp}: {len(out['routes'])} ways ({len(runs)} runs, {len(pro)} of pros), {len(out['jumps'])} jumps "
        f"({len(jrows)} from {len(with_dem)} demos) in {time.time() - t0:.0f} s")
    return out


# ---------------------------------------------------------------- the drills

# what each level works on (rework_entrainement.md, section 4: the bases for all, the ways and the jumps from
# Intermediate; nothing locked until the training level is done)
VARIANTS = {"debut": ["stop", "silent", "route"], "inter": ["stop", "route", "jump", "silent"], None: ["route", "jump", "stop", "route", "jump"]}
SECS = {"route": 75, "jump": 70, "stop": 60, "silent": 50}
REPS = {"route": 3, "jump": 5, "stop": 8, "silent": 2}
JUMP_GOAL = 3   # landings of a jump drill
WALK = 100.0   # u/s: the silent walk's time allowed (a rifle walks at 112 u/s, a knife at 130)


def _id(mp, v, key):
    return f"momentum:{mp}:{v}:{key}"


def _spawn_name(side):
    return i18n.tr("T spawn") if side == "T" else i18n.tr("CT spawn")


def _silent(w):
    """The last 750 u of a way into a site: its line, its start, its length."""
    line = np.asarray(w["line"], float)
    total = _length(line)
    if total < 300:
        return None
    L0 = max(0.0, total - SILENT_LEN)
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(line[:, :2], axis=0).T))]
    p = _at(line, L0)
    rest = [[round(float(v), 1) for v in p]] + [list(map(float, q)) for q, dd in zip(line, d) if dd > L0 + 1]
    n = _length(rest)
    ahead = _at(rest, min(150.0, n))
    return {"line": rest, "start": [round(float(p[0]), 1), round(float(p[1]), 1), round(float(p[2]) + 2, 1)],
            "yaw": round(_bearing(p, ahead), 1), "len": n}


def _cands(data):
    """Each variant's exercises on the map: (key, its data)."""
    routes, jumps = data.get("routes") or [], data.get("jumps") or []
    spawns = [w for w in routes if w["kind"] == "spawn"]
    stops = {}
    for w in sorted(spawns, key=lambda w: -w["n"]):   # one per side: its spawn, open ground to run left and right
        stops.setdefault(w["side"], w)
    silent = [w for w in sorted(spawns, key=lambda w: (w["side"] != "T", -w["n"])) if _length(w["line"]) >= 300]
    return {"route": [(w["id"], w) for w in routes], "jump": [(s["id"], s) for s in jumps],
            "stop": [(side, w) for side, w in stops.items()], "silent": [(w["id"], w) for w in silent]}


def count(mp):
    """How many momentum exercises the map has (Prepare's focus tile)."""
    c = _cands(load(mp, build=False) or {})
    return sum(len(v) for v in c.values()) if c["route"] or c["jump"] else 0


def has(mp):
    d = load(mp, build=False) or {}
    return bool(d.get("routes") or d.get("jumps"))


def drills(sid, mp, secs, guns, rifle, items=None, nsess=0):
    """The Momentum block: as many drills as its time holds, in the order of the player's level, each variant's in a row
    (Crossfire's way, 14/10); in each variant the ones missed and due first (the training's boxes), then the ones never
    played, the most used first, then the others. guns: (T rifle, CT rifle, pistol) as train._my_guns gives them."""
    from wily.training import replay
    data = load(mp, build=False) or {}
    C = _cands(data)
    if not (C["route"] or C["jump"]):
        return []
    items = items or {}
    order = [v for v in VARIANTS.get(crossfire.level_of(sid), VARIANTS[None]) if C[v]]
    if not order:
        return []
    tr_, cr_, _ = guns

    def rank(v):
        def r(x):
            it = items.get(_id(mp, v, x[0]))
            n = x[1].get("matches") or x[1].get("n") or 0
            return (1, -n) if it is None else (0, it["box"]) if it["next"] <= nsess else (2, it["next"])
        return sorted(C[v], key=r)
    ranked = {v: rank(v) for v in order}
    used = Counter()
    out, total, k = [], 0, 0
    while total < secs - 20 and k < max(12, secs // 25):
        v = order[k % len(order)]
        k += 1
        key, x = ranked[v][used[v] % len(ranked[v])]
        used[v] += 1
        did = _id(mp, v, key)
        box = (items.get(did) or {}).get("box", 0)
        side = x.get("side") or "T"
        team = 2 if side == "T" else 3
        gun = replay._item(tr_ if team == 2 else cr_) or rifle[team]
        pistol = "weapon_glock" if team == 2 else "weapon_usp_silencer"
        d = {"id": did, "kind": "momentum", "mode": "momentum", "variant": v, "map": mp, "team": team, "seconds": SECS[v],
             "count": REPS[v], "level": min(1, box), "armor": 100, "helmet": True}
        if v == "route":
            frm = _spawn_name(side) if x["kind"] == "spawn" else x["from"]
            title = (i18n.tr("RUN · {a} → {b}", a=frm, b=x["to"]) if x["kind"] == "spawn" else i18n.tr("ROTATE · {a} → {b}", a=frm, b=x["to"]))
            tip = (i18n.tr("via {via}", via=" → ".join(x["via"])) + " · " if x["via"] else "") \
                + i18n.tr("knife out, through every ring: the base runs it in {base} s, its fastest in {best} s", base=x["base"], best=x["best"]) \
                + (" · " + i18n.tr("the pros: {pro} s", pro=x["pro"]) if x.get("pro") else "")
            d.update(title=title, tip=tip, weapons=["weapon_knife"], me={"pos": x["start"], "ang": [0, x["yaw"]]},
                     line=x["line"], marks=x["marks"], par=x["base"], best=x["best"], pro=x.get("pro") or 0)
        elif v == "jump":
            how = i18n.tr(HOW.get(x["how"], HOW["jump"]))
            d.update(title=i18n.tr("JUMP · {zone}", zone=x["zone"]),
                     tip=f"{how} · " + i18n.tr("from the green ring, land in the blue one") + " · "
                         + i18n.trn(x["matches"], "the base jumps it in {n} match", "the base jumps it in {n} matches")
                         + (" · " + i18n.trn(x["kills"], "{n} kill from up there", "{n} kills from up there") if x.get("kills") else ""),
                     weapons=[gun, "weapon_knife"], me={"pos": x["start"], "ang": [0, x["yaw"]]}, target=x["to"],
                     **{"from": x["from"]}, how=x["how"], goal=JUMP_GOAL)
        elif v == "stop":
            d.update(title=i18n.tr("STOP DEAD · {zone}", zone=_spawn_name(side)),
                     tip=i18n.tr("run left and right (A, D) at full speed; on STOP, stop dead: tap the other key (counter-strafe)"),
                     weapons=["weapon_knife", pistol, gun], me={"pos": x["start"], "ang": [0, x["yaw"]]})
        else:
            s = _silent(x)
            if s is None:
                continue
            limit = round(s["len"] / WALK + 3, 1)
            d.update(title=i18n.tr("SILENT · into {site}", site=x["to"]),
                     tip=i18n.tr("walk in (Shift), not one footstep heard: {s} s at most", s=limit),
                     weapons=["weapon_knife", pistol, gun], me={"pos": s["start"], "ang": [0, s["yaw"]]},
                     line=s["line"], marks=marks(s["line"]), par=limit)
        out.append(d)
        total += SECS[v]
    out.sort(key=lambda d: order.index(d["variant"]))
    return out


if __name__ == "__main__":
    # python -m wily.training.momentum [map ...]: the maps' data built again (every bomb map of the base by default)
    sys.stdout.reconfigure(encoding="utf-8")
    from wily.training import train
    config.low_priority()
    for m in sys.argv[1:] or list(train.base_maps()):
        _build(m)
