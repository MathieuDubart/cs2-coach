"""Where the Ts go in, said the way players call it (06/10, the user during a bot match: "je veux juste avoir des
directions maintenant, des directions et depuis où": A via Palace, A via Ramp, Mid to A through Connector, and a key
for A, one for mid, one for B, one for rush, one for slow, one for map control).

Every hit of the base (the round's Ts got on a site), by the doorway each T stepped on the site through: grouped from
the steps themselves (the game's place names are not reliable there: on Mirage it calls A ramp "TRamp" and T ramp
"PalaceAlley"), named after the callout the Ts were in just before (A Ramp, Palace, Connector, Apps...), and "Mid ->"
when they came through mid. A round goes to the doorway most of its Ts took; two doorways with two Ts or more each is
a split. For each way: how often the round is won by the two buys and by tempo (a rush, a slow round, map control
first), by when the Ts got on the site (the curve the panel draws, at equal numbers like tside's plays), the walk the
players take (the most typical one), and the grenades the Ts threw before stepping on the site, grouped by the spot
they are thrown from (a stack: several grenades from one place, the smoke then the flash over it).
Also mid control: the rounds where two Ts or more held mid early, how they end, and the grenades of that control.
Cached in out/population/tdirs.json until the base grows by 15 % (like the other T tables).
Usage: python tdirs.py [map ...]"""
import json
import os
import re
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

import config
import nades
import tside

OUT = os.path.join(config.OUT, "population", "tdirs.json")
VERSION = 1   # bump when the output changes shape: the cache is rebuilt
RUSH, SLOW = 30.0, 60.0   # on the site in the first 30 s (1:25 on the clock): a rush; after 60 s (0:55): a slow round
CONTROL_T = (14.0, 26.0)  # Ts spread over two areas or more around 0:20 into the round, then a hit after 35 s: map control first
MIN_DIR = 25              # rounds for a way to be kept
GATE_EPS = 24             # radar pixels between two steps on the site for one doorway (about 120 units on most maps)
GATE_MIN = 0.06           # a doorway takes at least 6 % of the steps on its site
STAND_R, STAND_Z, LAND_R = 40.0, 24.0, 120.0   # one lineup: thrown from the same spot (units, same height), landing at the same place
STACK_R = 80.0            # lineups thrown from within 80 units: one stack
MAX_UTIL = 12
MID = re.compile(r"\bmid", re.I)
SKIP = {"TSpawn", "CTSpawn", "?", "†", ""}
# a doorway named after a place of the site itself where players call it by the way in (Mirage: the palace's exit is
# the game's "Scaffolding", the apartments' exit is "Truck" by the van): applied to doorway names only
GATE_FIX = {"de_mirage": {"Scaffolding": "Palace", "Van": "Apps"}}
_HUM = {}


def hum(z, mp):
    k = (z, mp)
    if k not in _HUM:
        _HUM[k] = tside.humanize(z, mp) if isinstance(z, str) and z else None
    return _HUM[k]


def _short(name, site):
    """A callout without its site's letter: "A Ramp" on A is the ramp."""
    if name and name.startswith(site + " ") and len(name) > 2:
        return name[2:]
    return name


def _map_rounds(mp, dirs):
    """The T table of every match of the map (tside.py), with the match id."""
    out = []
    for d in dirs:
        f = os.path.join(tside.OUT, os.path.basename(d) + ".parquet")
        if os.path.exists(f):
            x = pd.read_parquet(f)
            if len(x):
                out.append(x.assign(match=os.path.basename(d)))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _areas(zs):
    """Each zone of the map: the site it leads to (A or B, 70 % of the Ts who went through it then got in there), mid,
    or nothing."""
    out = {}
    for z, (a, b) in zs.items():
        pa = a / max(1, a + b)
        out[z] = "A" if pa >= 0.7 else "B" if pa <= 0.3 else None
    return out


def _steps(mp, d, R, areas):
    """One match: every T who stepped on the hit site, where (the step before the site), the callout just before,
    mid or not, the walk from the spawn; and per round the areas the Ts were in around 0:20 (map control)."""
    S = pd.read_parquet(os.path.join(d, "samples.parquet"), columns=["steamid", "side", "round", "t", "px", "py", "level", "zone", "health"])
    S = S[(S.side == "T") & S.px.notna() & S["round"].isin(list(R))]
    steps, spread = [], {}
    for rnd, x in S.groupby("round", sort=False):
        r = R[rnd]
        cut = x[(x.t >= CONTROL_T[0]) & (x.t <= CONTROL_T[1]) & (x.health.fillna(1) > 0)]
        ar = set()
        for z in cut.zone.dropna().unique():
            h = hum(z, mp) or ""
            ar.add("mid" if MID.search(h) else areas.get(z))
        ar.discard(None)
        spread[rnd] = sorted(ar)
        if r["site"] not in ("A", "B"):
            continue
        target = "Bombsite" + r["site"]
        for sid, y in x.groupby("steamid", sort=False):
            y = y[y.health.fillna(1) > 0].sort_values("t")
            z = y.zone.to_numpy(object)
            t = y.t.to_numpy(float)
            idx = np.flatnonzero(z == target)
            if not len(idx):
                continue
            i = int(idx[0])
            if t[i] > r["hit_t"] + 20 or i == 0:
                continue   # on the site long after the hit, or already there at the first step: not a way in
            j = i - 1 if t[i] - t[i - 1] <= 2.0 else i
            came = None   # the last callout before the step on the site (3 s at most): the doorway's own name
            for k in range(i - 1, -1, -1):
                if t[i] - t[k] > 3.0:
                    break
                v = z[k]
                if isinstance(v, str) and v not in SKIP and not v.startswith("Bombsite") and hum(v, mp):
                    came = hum(v, mp)
                    break
            way = (t >= t[i] - 8) & (t < t[i] - 1.5)   # the callouts of the way in (not the last step: the van, the ramp's foot): what names the doorway
            names = sorted({hum(v, mp) for v in z[way] if isinstance(v, str) and v not in SKIP and not v.startswith("Bombsite") and hum(v, mp)})
            back = (t >= t[i] - 14) & (t < t[i])
            via_mid = any(MID.search(hum(v, mp) or "") for v in z[back] if isinstance(v, str) and v not in SKIP)
            walk = [(float(a), float(b), l) for a, b, l in zip(y.px.iloc[:i + 1], y.py.iloc[:i + 1], y.level.iloc[:i + 1])]
            steps.append({"match": os.path.basename(d), "round": int(rnd), "sid": int(sid), "site": r["site"], "t_in": float(t[i]),
                          "px": float(y.px.iloc[j]), "py": float(y.py.iloc[j]), "level": y.level.iloc[j], "came": came,
                          "mid": via_mid, "names": names, "walk": walk})
    return steps, spread


def _gates(E, mp=None):
    """The doorways of each site: the steps on the site grouped by the last callout before them (A Ramp, Palace,
    Connector...); two callouts whose steps land at the same place (within GATE_EPS on the radar) are one doorway, named
    after the most common. A step with no callout, or a rare one, joins the nearest doorway (twice GATE_EPS at most)."""
    E = E.copy()
    E["gate"] = None
    gates = []
    for (site, lv), x in E.groupby(["site", "level"]):
        if len(x) < 30:
            continue
        named = x[x.came.notna()]
        groups = []   # [names Counter, index list, median px]
        for name, m in sorted(named.groupby("came"), key=lambda kv: -len(kv[1])):
            if len(m) < 0.03 * len(x):
                continue
            c = np.array([m.px.median(), m.py.median()])
            for gr in groups:
                if np.hypot(*(gr[2] - c)) < GATE_EPS:
                    gr[0][name] += len(m)
                    gr[1].extend(m.index)
                    break
            else:
                groups.append([Counter({name: len(m)}), list(m.index), c])
        if not groups:
            continue
        C = np.array([gr[2] for gr in groups])
        rest = x.index.difference(pd.Index([i for gr in groups for i in gr[1]]))
        for i in rest:
            d = np.hypot(C[:, 0] - x.at[i, "px"], C[:, 1] - x.at[i, "py"])
            k = int(np.argmin(d))
            if d[k] < 2 * GATE_EPS:
                groups[k][1].append(i)
        tot = sum(len(gr[1]) for gr in groups)
        groups = [gr for gr in groups if len(gr[1]) >= GATE_MIN * tot]
        # each doorway's name: the callout of its way in that the other doorways of the site don't share (A Ramp for the
        # ramp, though the game calls the ramp's foot "PalaceInterior" like the palace itself)
        def prof(ix):
            c = Counter(n for ns in E.loc[ix, "names"] for n in ns)
            return {n: k / len(ix) for n, k in c.items()}

        def cos(a, b):
            d = sum(v * b.get(n, 0) for n, v in a.items())
            return d / (np.sqrt(sum(v * v for v in a.values())) * np.sqrt(sum(v * v for v in b.values())) or 1)
        # two doorways the Ts reach by the same way (Mirage: the apartments' two exits, by the balcony and by the van)
        # are one: merged while their ways' callouts are alike (cosine 0.85; the ramp and the palace stay apart)
        P = [prof(gr[1]) for gr in groups]
        while True:
            pair = max(((cos(P[i], P[j]), i, j) for i in range(len(groups)) for j in range(i + 1, len(groups))), default=None)
            if not pair or pair[0] < 0.85:
                break
            _, i, j = pair
            groups[i][0].update(groups[j][0])
            groups[i][1].extend(groups[j][1])
            del groups[j]
            P = [prof(gr[1]) for gr in groups]
        fix = GATE_FIX.get(mp, {})
        named = {}
        for gi, gr in enumerate(groups):
            spec = {n: p - max([o.get(n, 0) for oi, o in enumerate(P) if oi != gi] or [0]) for n, p in P[gi].items() if p >= 0.25}
            name = max(spec, key=spec.get) if spec else gr[0].most_common(1)[0][0]
            m = E.loc[gr[1]]
            mid = bool(m.mid.mean() >= 0.5)
            if mid and MID.search(name or ""):   # "Mid -> A (Mid)" says nothing: the last callout before the site (Connector)
                last = [n for n, _ in gr[0].most_common() if not MID.search(n or "")]
                name = last[0] if last else name
            name = _short(fix.get(name, name), site) or "?"
            key = (name, mid)
            named.setdefault(key, []).extend(gr[1])
        for (name, mid), ix in named.items():
            m = E.loc[ix]
            gid = f"{site}{len(gates)}"
            E.loc[ix, "gate"] = gid
            gates.append({"id": gid, "site": site, "level": lv, "name": name, "mid": mid,
                          "px": [round(float(m.px.median())), round(float(m.py.median()))], "steps": int(len(m))})
    tot = Counter(g["site"] for g in gates for _ in range(g["steps"]))
    for g in gates:
        g["share"] = round(100 * g["steps"] / max(1, tot[g["site"]]))
    return E, gates


def _label(g):
    return f"Mid → {g['site']} ({g['name']})" if g["mid"] else f"{g['site']} via {g['name']}"


def _round_dirs(E, gates):
    """Each hit round: its way (the doorway most of its Ts stepped through), a split when two doorways had two Ts or
    more. -> {(match, round): key}, {key: label}"""
    G = {g["id"]: g for g in gates}
    keys, labels, pairs = {}, {}, {}
    for (mid, rnd), x in E[E.gate.notna()].groupby(["match", "round"]):
        c = Counter(x.gate)
        top = sorted(c.items(), key=lambda kv: (-kv[1], x[x.gate == kv[0]].t_in.min()))
        site = G[top[0][0]]["site"]
        if len(top) >= 2 and top[1][1] >= 2:
            k = f"{site}:split"
            pairs.setdefault(k, Counter())[" + ".join(sorted(G[g]["name"] for g, _ in top[:2]))] += 1
        else:
            k = top[0][0]
            labels[k] = _label(G[k])
        keys[(mid, int(rnd))] = k
    for k, c in pairs.items():
        labels[k] = f"{k[0]} split: {c.most_common(1)[0][0]}"
    return keys, labels


def _lineups(N, rounds, min_n=None):
    """The grenades of a way's rounds, grouped: thrown from the same spot and landing at the same place. Each: how many
    of the way's rounds use it, won when used, the usual moment, and the exact throw (the most common aim of the
    throws you can repeat from a spot: standing, crouching or a jumpthrow without running)."""
    if not len(N):
        return []
    N = N.sort_values("t")
    cl = []   # [type, X, Y, Z, lX, lY, [row indexes]]
    for i, b in zip(N.index, N.itertuples()):
        for c in cl:
            if c[0] == b.type and abs(c[1] - b.X) < STAND_R and abs(c[2] - b.Y) < STAND_R and abs(c[3] - b.Z) < STAND_Z \
                    and np.hypot(c[4] - b.land_X, c[5] - b.land_Y) < LAND_R:
                c[6].append(i)
                n = len(c[6])
                c[1] += (b.X - c[1]) / n
                c[2] += (b.Y - c[2]) / n
                c[4] += (b.land_X - c[4]) / n
                c[5] += (b.land_Y - c[5]) / n
                break
        else:
            cl.append([b.type, b.X, b.Y, b.Z, b.land_X, b.land_Y, [i]])
    out = []
    nr = max(1, len(rounds))
    for c in cl:
        x = N.loc[c[6]]
        rr = x.drop_duplicates(["match", "round"])
        if len(rr) < (min_n if min_n is not None else max(4, 0.02 * nr)):
            continue
        rep = x[x.speed < 20] if (x.speed < 20).any() else x
        # the most common aim: the throw with the most others within 1.5 degrees
        P, Y = rep.pitch.to_numpy(float), rep.yaw.to_numpy(float)
        dy = np.abs(((Y[:, None] - Y[None, :]) + 180) % 360 - 180)
        close = ((np.abs(P[:, None] - P[None, :]) < 1.5) & (dy < 1.5)).sum(1)
        b = rep.iloc[int(np.argmax(close))]
        won = rr.won.mean()
        out.append({"type": c[0], "from": b.zone_h, "to": b.land_zone_h, "from_px": [round(float(rep.px.median())), round(float(rep.py.median()))],
                    "to_px": [round(float(x.land_px.median())), round(float(x.land_py.median()))], "level": b.level, "land_level": b.land_level,
                    "X": round(float(b.X), 1), "Y": round(float(b.Y), 1), "Z": round(float(b.Z), 1),
                    "n": int(len(rr)), "share": round(100 * len(rr) / nr), "win": round(100 * float(won)),
                    "t_med": round(float(x.t.median()), 1), "how": nades._how(b), "click": b.click if isinstance(b.click, str) else None,
                    "setpos": f"setpos {b.X:.1f} {b.Y:.1f} {b.Z:.1f}; setang {b.pitch:.2f} {b.yaw:.2f} 0"})
    out.sort(key=lambda u: -u["n"])
    seen = []
    for u in out:   # the same lineup thrown from a few units apart (standing, walking...): one, the most used, counted together
        for v in seen:
            if v["type"] == u["type"] and v["from"] == u["from"] and v["to"] == u["to"] and np.hypot(v["X"] - u["X"], v["Y"] - u["Y"]) < 160:
                v["n"] += u["n"]
                v["share"] = round(100 * v["n"] / nr)
                break
        else:
            seen.append(u)
    out = sorted(seen, key=lambda u: -u["n"])[:MAX_UTIL]
    # stacks: lineups thrown from within 80 units of each other, same height (the smoke, then the flash over it)
    sid = 0
    for i, u in enumerate(out):
        if "stack" in u:
            continue
        u["stack"] = sid
        for v in out[i + 1:]:
            if "stack" not in v and np.hypot(u["X"] - v["X"], u["Y"] - v["Y"]) < STACK_R and abs(u["Z"] - v["Z"]) < 2 * STAND_Z:
                v["stack"] = sid
        sid += 1
    for u in out:
        for k in ("X", "Y", "Z"):
            u.pop(k)
    return out


def _stats(rows):
    n = len(rows)
    return [int(n), int(rows.T_won.sum())] if n else [0, 0]


def analyze_map(mp, dirs, log=print):
    t0 = time.time()
    g = _map_rounds(mp, dirs)
    if len(g) < 200:
        return None
    hits = g[g.entered.fillna(False).astype(bool) & g.site.isin(["A", "B"]) & g.hit_t.notna()]
    zs = tside.zone_sites(g.assign(entered=g.entered.fillna(False).astype(bool))).get(mp, {})
    areas = _areas(zs)
    by_match = {m: {int(r["round"]): r for r in x.to_dict("records")} for m, x in g.groupby("match")}
    steps, spread = [], {}
    for d in dirs:
        mid = os.path.basename(d)
        R = by_match.get(mid)
        if not R or not os.path.exists(os.path.join(d, "samples.parquet")):
            continue
        try:
            s, sp = _steps(mp, d, R, areas)
        except Exception as e:
            log(f"{mp} {mid}: steps unreadable ({e})")
            continue
        steps += s
        spread.update({(mid, k): v for k, v in sp.items()})
    if not steps:
        return None
    E = pd.DataFrame(steps)
    E, gates = _gates(E, mp)
    keys, labels = _round_dirs(E, gates)
    h = hits.assign(key=[keys.get((m, int(r))) for m, r in zip(hits.match, hits["round"])])
    h = h[h.key.notna()].copy()
    h["spread"] = [spread.get((m, int(r)), []) for m, r in zip(h.match, h["round"])]
    h["control"] = [len(a) >= 2 and t >= 35 for a, t in zip(h.spread, h.hit_t)]
    h["play"] = h.key
    timing = tside._play_timing(h) or {}
    # the grenades: the Ts' of the hit rounds before the step on the site (2 s after the hit at the latest); the CTs' of
    # the first 45 s of every round (what they throw onto each site's ways in); the CTs' kills in the Ts' rushes
    want = {(m, int(r)): (t, w) for m, r, t, w in zip(h.match, h["round"], h.hit_t, h.T_won)}
    won_of = {(m, int(r)): bool(w) for m, r, w in zip(g.match, g["round"], g.T_won)}
    rush_r = {(m, int(r)): (float(t), st) for m, r, t, st, ne in zip(hits.match, hits["round"], hits.hit_t, hits.site, hits.n_exec)
              if t < RUSH and (ne or 0) >= 3}
    ct_buy = {(m, int(r)): b for m, r, b in zip(g.match, g["round"], g.CT_buy)}
    NN, CC, KK = [], [], []
    for d in dirs:
        mid = os.path.basename(d)
        f = os.path.join(d, "grenades.parquet")
        if mid not in by_match or not os.path.exists(f):
            continue
        try:
            n = pd.read_parquet(f, columns=["round", "t", "type", "side", "X", "Y", "Z", "pitch", "yaw", "px", "py", "level", "zone", "jump", "speed",
                                            "crouch", "walk", "click", "land_X", "land_Y", "land_px", "land_py", "land_level", "land_zone"])
        except Exception:
            continue
        n = n[n.land_X.notna()]
        nt = n[n.side == "T"]
        if len(nt):
            hit = [want.get((mid, int(r))) for r in nt["round"]]
            nt = nt[[w is not None and tt <= w[0] + 2 for w, tt in zip(hit, nt.t)]]
            if len(nt):
                NN.append(nt.assign(match=mid, won=[want[(mid, int(r))][1] for r in nt["round"]]))
        nc = n[(n.side == "CT") & (n.t <= 45)]
        if len(nc):
            CC.append(nc.assign(match=mid, won=[not won_of.get((mid, int(r)), True) for r in nc["round"]]))
        fd = os.path.join(d, "duels.parquet")
        rr = {r for (m, r) in rush_r if m == mid}
        if rr and os.path.exists(fd):
            try:
                k = pd.read_parquet(fd, columns=["round", "t", "killer_side", "victim_side", "weapon", "killer_px", "killer_py", "killer_level", "killer_zone"])
            except Exception:
                k = pd.DataFrame()
            if len(k):
                k = k[(k.killer_side == "CT") & (k.victim_side == "T") & k["round"].isin(list(rr))]
                k = k[[tt <= rush_r[(mid, int(r))][0] + 12 for r, tt in zip(k["round"], k.t)]]
                if len(k):
                    KK.append(k.assign(match=mid, site=[rush_r[(mid, int(r))][1] for r in k["round"]],
                                       won=[not won_of.get((mid, int(r)), True) for r in k["round"]]))

    def nades_frame(L):
        x = pd.concat(L, ignore_index=True) if L else pd.DataFrame()
        if len(x):
            x["type"] = x["type"].replace({"incendiary": "molotov"})
            x = x[x["type"].isin(["smoke", "flash", "molotov", "he"])].copy()
            x["zone_h"] = [hum(z, mp) for z in x.zone]
            x["land_zone_h"] = [hum(z, mp) for z in x.land_zone]
        return x
    N, C = nades_frame(NN), nades_frame(CC)
    if len(N):
        N["key"] = [keys.get((m, int(r))) for m, r in zip(N.match, N["round"])]
    G = {x["id"]: x for x in gates}
    out_dirs = []
    for k, x in h.groupby("key"):
        if len(x) < MIN_DIR:
            continue
        site = k[0]
        econ = {f"{a}|{b}": _stats(y) for (a, b), y in x.groupby(["T_buy", "CT_buy"]) if len(y) >= 3}
        tempo = {"rush": _stats(x[x.hit_t < RUSH]), "slow": _stats(x[x.hit_t >= SLOW]), "control": _stats(x[x.control])}
        main = [k] if k in G else []
        if not main:   # a split: the walks of its two most common doorways
            ks = Counter(E[E.gate.notna() & E.set_index(["match", "round"]).index.isin(list(zip(x.match, x["round"])))].gate)
            main = [gk for gk, _ in ks.most_common(2)]
        routes = []
        for gk in main:
            W = E[(E.gate == gk) & E.set_index(["match", "round"]).index.isin(list(zip(x.match, x["round"])))]
            pts = tside._walk_medoid(list(W.walk.head(80)))
            if pts:
                routes.append({"gate": gk, "pts": pts})
        util = _lineups(N[N.key == k], x) if len(N) else []
        out_dirs.append({"k": k, "site": site, "label": labels.get(k, k), "mid": bool(G[k]["mid"]) if k in G else False,
                         "split": k not in G, "gates": main, "n": int(len(x)), "win": round(100 * float(x.T_won.mean())),
                         "hit_med": round(float(x.hit_t.median()), 1), "econ": econ, "tempo": tempo, "timing": timing.get(k),
                         "routes": routes, "util": util})
    out_dirs.sort(key=lambda o: -o["n"])
    # mid control: two Ts or more in mid around 0:20, whatever happens next
    res = {"n": int(len(h)), "gates": gates, "dirs": out_dirs}
    ctl = g.assign(spread=[spread.get((m, int(r)), []) for m, r in zip(g.match, g["round"])])
    mc = ctl[["mid" in a for a in ctl.spread]]
    if len(mc) >= MIN_DIR:
        then = Counter(keys.get((m, int(r)), "none") for m, r in zip(mc.match, mc["round"]))
        res["mid"] = {"n": int(len(mc)), "win": round(100 * float(mc.T_won.mean())),
                      "then": {k: v for k, v in then.most_common(6)}}
    # CT side (06/10, "Wily contre rush B 5 stack", "Wily fake défense A"): against the Ts' rushes of each site (three
    # Ts or more on it in the first 30 s), how often the CTs hold, the grenades they throw before the hit, the spots
    # they kill from and with what; and the CTs' grenades onto each site's ways in (to show a site you don't hold)
    K = pd.concat(KK, ignore_index=True) if KK else pd.DataFrame()
    res["defense"], res["ct_util"] = {}, {}
    for site in ("A", "B"):
        R = [(m, r) for (m, r), (t, st) in rush_r.items() if st == site]
        if len(R) >= 20:
            rr = pd.DataFrame(R, columns=["match", "round"])
            rr["won"] = [not won_of.get(x, True) for x in R]
            Rs = set(R)
            gs = [x for x in gates if x["site"] == site]
            Cs = C[[(m, int(r)) in Rs and tt <= rush_r[(m, int(r))][0] + 3 for m, r, tt in zip(C.match, C["round"], C.t)]] if len(C) else C
            if len(Cs) and gs:   # onto the rushed site's ways in only
                near = np.zeros(len(Cs), dtype=bool)
                for x in gs:
                    near |= np.hypot(Cs.land_px.to_numpy(float) - x["px"][0], Cs.land_py.to_numpy(float) - x["px"][1]) < 70
                Cs = Cs[near]
            base = float(rr.won.mean())
            util = _lineups(Cs, rr, min_n=4) if len(Cs) else []
            for u in util:   # what holds the rush: rounds held when it's thrown, pulled toward the usual when few
                u["edge"] = round((u["win"] / 100 * u["n"] + 10 * base) / (u["n"] + 10) * 100 - 100 * base)
            util.sort(key=lambda u: -(u["edge"] + 0.02 * u["n"]))
            spots, weapons = [], []
            Ks = K[K.site == site] if len(K) else K
            if len(Ks):   # the pistol rounds apart: their weapons say nothing of a bought round
                Ks = Ks[[ct_buy.get((m, int(r))) != "pistol" for m, r in zip(Ks.match, Ks["round"])]]
            if len(Ks):
                cell = Ks.assign(cx=(Ks.killer_px // 26).astype(int), cy=(Ks.killer_py // 26).astype(int))
                for (cx, cy, lv), x in cell.groupby(["cx", "cy", "killer_level"]):
                    if len(x) >= 4:
                        spots.append({"px": [round(float(x.killer_px.median())), round(float(x.killer_py.median()))], "level": lv,
                                      "kills": int(len(x)),
                                      "zone": hum(Counter(x.killer_zone.dropna()).most_common(1)[0][0], mp) if x.killer_zone.notna().any() else None,
                                      "weapon": Counter(x.weapon.dropna()).most_common(1)[0][0] if x.weapon.notna().any() else None})
                spots = sorted(spots, key=lambda q: -q["kills"])[:6]
                wc = Counter(Ks.weapon.dropna())
                tot = sum(wc.values())
                weapons = [{"w": w, "share": round(100 * c / tot)} for w, c in wc.most_common(6)] if tot else []
            res["defense"][site] = {"n": len(R), "ct_win": round(100 * float(rr.won.mean())), "util": util, "spots": spots, "weapons": weapons}
        gs = [x for x in gates if x["site"] == site]
        if len(C) and gs:
            near = np.zeros(len(C), dtype=bool)
            for x in gs:
                near |= np.hypot(C.land_px.to_numpy(float) - x["px"][0], C.land_py.to_numpy(float) - x["px"][1]) < 70
            Cw = C[near]
            if len(Cw):
                res["ct_util"][site] = _lineups(Cw, Cw.drop_duplicates(["match", "round"]), min_n=6)
    log(f"{mp}: {len(out_dirs)} ways in, {len(gates)} doorways, {len(h)} hits ({time.time() - t0:.0f} s)")
    return res


def run(maps=None, log=print, force=False):
    """Every map of the base (or the ones given), kept until the base grows by 15 %."""
    stamp = tside._stamp().replace(f"v{tside.VERSION}-", f"v{VERSION}-")
    try:
        cur = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    if not force and not maps and nades.fresh(cur.get("_stamp"), stamp):
        return cur
    dirs = tside._map_dirs()
    todo = maps or sorted(m for m, ds in dirs.items() if len(ds) >= 20 and m.startswith("de_"))
    res = {"_stamp": stamp, "maps": dict(cur.get("maps") or {}) if maps else {}}
    for mp in todo:
        try:
            r = analyze_map(mp, dirs.get(mp, []), log)
        except Exception as e:
            log(f"{mp}: ways in unavailable ({e})")
            r = None
        if r:
            res["maps"][mp] = r
    tmp = OUT + f".{os.getpid()}.tmp"
    json.dump(res, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    return res


def load():
    """What the plan needs: the cached table as it is (built by refresh / grow, never during a plan build)."""
    try:
        return json.load(open(OUT, encoding="utf-8")).get("maps") or {}
    except (OSError, ValueError):
        return {}


_MEM = {"mtime": None, "maps": {}}


def load_map(mp):
    """One map's ways for the page, read again only when the table changed on disk."""
    try:
        mt = os.path.getmtime(OUT)
    except OSError:
        return None
    if _MEM["mtime"] != mt:
        _MEM.update(mtime=mt, maps=load())
    return _MEM["maps"].get(mp)


if __name__ == "__main__":
    run(sys.argv[1:] or None, force=True)
