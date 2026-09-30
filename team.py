"""Team plan: you + 1 to 4 teammates. Crosses every member's data (roles, zones, lineups, weapons, mid-round habits,
matches played together) with the base and the pros to build a game plan:
roles (T, CT, AWP, IGL), map pool, CT setup (who plays where), T executes (who throws what), rotations, calls,
economy, synergies, collective goals and each member's individual work.

Saved in out/teams/<id>.json and copied to the site. Usage: python team.py <steamid> <steamid> [...]
"""
import datetime as dt
import hashlib
import itertools
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd

import config
import knowledge as K
from map_analysis import humanize

TEAMS = os.path.join(config.OUT, "teams")
META = os.path.join(config.OUT, "population", "map_meta.json")
PREMIER = ["de_ancient", "de_anubis", "de_cache", "de_dust2", "de_inferno", "de_mirage", "de_nuke"]
ROLE_FR = {"entry": "Entry", "trader": "Second / trade", "support": "Support", "lurker": "Lurker", "awper": "AWPer",
           "flex": "Rifler flex", "anchor": "Anchor", "closer": "Closer"}
T_ROLE_DO = {
    "entry": "First onto the site, behind the support's flash. Your job: take space and call what you see, even if you die.",
    "trader": "Stick to the entry within trade distance (1 to 2 s behind, not on the same line) and avenge them right away.",
    "support": "Throw the execute's smokes and flashes, then go in third. Keep a grenade for the post-plant.",
    "lurker": "Opposite side of the execute: walk, listen to the rotations and cut them when the team goes in.",
    "awper": "Take the first pick on the long angle, then cover the entry or the flank. Never re-peek the same angle.",
    "flex": "Backup for the execute or a second lurker depending on the info. Play the end of the round: clutch, post-plant.",
}
CT_SLOT_DO = {
    "anchor": "Hold the site: survive 10 s, call how many they are and their grenades, fall back rather than die first.",
    "support": "Backup for the most attacked site: delaying utility, then trade the anchor.",
    "mid": "Mid control: info early in the round, then a fast rotation to the attacked site.",
    "awp": "The long angle that hurts the Ts. One shot, then change position.",
}


# ---------- population references per map ----------
def _n_demos():
    return sum(1 for m in os.listdir(config.DEEP) if os.path.exists(os.path.join(config.DEEP, m, "rounds.parquet")))


def map_meta(rebuild=False):
    """Per map: region (A / B / mid) of every zone, and where the Ts plant (share, T win rate, plant time)."""
    if os.path.exists(META) and not rebuild:
        cur = json.load(open(META, encoding="utf-8"))
        if cur.get("_n") == _n_demos():
            return cur
    import midround
    sites = midround.site_centers()
    out = {"_n": _n_demos()}
    by_map = defaultdict(list)
    for mid in os.listdir(config.DEEP):
        d = os.path.join(config.DEEP, mid)
        try:
            mp = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))["map"]
        except Exception:
            continue
        by_map[mp].append(d)
    for mp, dirs in by_map.items():
        entry = {"regions": {}, "plants": {}}
        if mp in sites:
            S = pd.concat([pd.read_parquet(os.path.join(d, "samples.parquet"), columns=["X", "Y", "Z", "zone"]) for d in dirs[:10]], ignore_index=True)
            cen = S.groupby("zone")[["X", "Y", "Z"]].median()
            cA, cB = sites[mp]["A"]["c"], sites[mp]["B"]["c"]
            for z, r in cen.iterrows():
                dA = midround._dist(r.X, r.Y, r.Z, cA)
                dB = midround._dist(r.X, r.Y, r.Z, cB)
                ratio = dA / max(dA + dB, 1)
                entry["regions"][z] = "A" if ratio < 0.4 else "B" if ratio > 0.6 else "mid"
            from map_analysis import ZoneMap
            zm = ZoneMap(mp)
            for L in ("A", "B"):
                x, y = zm.px([sites[mp][L]["c"][0]], [sites[mp][L]["c"][1]])
                entry.setdefault("site_px", {})[L] = [float(x[0]), float(y[0])]
        R = [pd.read_parquet(os.path.join(d, "rounds.parquet")) for d in dirs if os.path.exists(os.path.join(d, "rounds.parquet"))]
        R = pd.concat([r for r in R if len(r)], ignore_index=True) if R else pd.DataFrame()
        if len(R) and "plant_site" in R:
            pl = R[R.plant_site.isin(["A", "B"])]
            for L, g in pl.groupby("plant_site"):
                entry["plants"][L] = {"share": round(100 * len(g) / max(len(pl), 1)), "t_win": round(100 * (g.winner == "T").mean()),
                                      "plant_t": round(float(g.plant_t.median()), 1), "n": int(len(g))}
            entry["rounds"] = int(len(R))
            entry["plant_rate"] = round(100 * len(pl) / len(R))
        out[mp] = entry
    os.makedirs(os.path.dirname(META), exist_ok=True)
    json.dump(out, open(META, "w", encoding="utf-8"), ensure_ascii=False)
    return out


# ---------- members ----------
def _load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def member(sid):
    pdir = config.player_dir(sid)
    adv = _load(os.path.join(pdir, "advice.json"))
    if not adv:
        return None
    cross = _load(os.path.join(pdir, "cross.json")) or {}
    arch = adv.get("archetype") or {}
    scores = {s["role"]: s["score"] for s in arch.get("scores", [])}
    plan = adv.get("plan") or {}
    names = config.settings().get("players", {})
    name = (names.get(str(sid)) or {}).get("name") or (adv.get("leetify") or {}).get("name") or str(sid)
    mdir = os.path.join(pdir, "matches")
    for mid in sorted(os.listdir(mdir)) if os.path.exists(mdir) else []:
        st = _load(os.path.join(mdir, mid, "stats.json"))
        if st and not st.get("error"):
            name = st["player"]["name"]
    return {"steamid": str(sid), "name": name, "adv": adv, "cross": cross, "plan": plan, "arch": arch,
            "scores": {r: scores.get(r, 50) for r in ("entry", "trader", "support", "lurker", "awper", "anchor", "closer")},
            "has_scores": bool(scores), "light": bool(adv.get("light")),
            "maps": {m["map"]: m for m in cross.get("maps", [])}}


def _pct(m, key, where="bench"):
    """Percentile of a metric (advice bench or mid-round bench); 50 when unknown."""
    if where == "bench":
        b = ((m["adv"].get("bench") or {}).get("metrics") or {}).get(key) or {}
    else:
        b = (((m["plan"].get("mid") or {}).get("bench") or {}).get("metrics") or {}).get(key) or {}
    return b.get("percentile")


# ---------- roles ----------
def t_fit(m, role):
    s = m["scores"]
    if role == "lurker":
        return s["lurker"] + 0.2 * s["closer"]
    if role == "flex":
        return 0.5 * s["closer"] + 0.3 * s["trader"] + 0.2 * s["anchor"]
    return s[role]


def assign(members, slots, fit):
    """Best injective assignment members -> slots (brute force, at most 5! cases). -> {member index: slot index}"""
    n, k = len(members), len(slots)
    best, best_v = {}, -1e9
    if n <= k:
        for perm in itertools.permutations(range(k), n):
            v = sum(fit(members[i], slots[perm[i]]) for i in range(n))
            if v > best_v:
                best, best_v = {i: perm[i] for i in range(n)}, v
    else:  # more members than slots: the best-suited members take them
        for perm in itertools.permutations(range(n), k):
            v = sum(fit(members[perm[j]], slots[j]) for j in range(k))
            if v > best_v:
                best, best_v = {perm[j]: j for j in range(k)}, v
    return best


def t_roles(M):
    awp_ok = max(m["scores"]["awper"] for m in M) >= 55 or any(
        (((m["plan"].get("weapons") or {}).get("duels") or {}).get("AWP") or {}).get("n", 0) >= 15 for m in M)
    roles = ["entry", "trader", "support", "lurker", "awper" if awp_ok else "flex"]
    # with fewer than 5, each member gets the role he fits best without overlap; random players take the rest
    a = assign(M, roles, lambda m, r: t_fit(m, r))
    out = {M[i]["steamid"]: roles[j] for i, j in a.items()}
    return out, [r for r in roles if r not in out.values()], awp_ok


def igl(M):
    res = []
    for m in M:
        vals, why = [], []
        for key, where, label in (("adv_conv", "mid", "converts advantages"), ("adv_throw", "mid", "rarely throws the advantage"),
                                  ("isolated", "mid", "rarely dies isolated"), ("traded_pct", "bench", "plays as a team (deaths traded)")):
            p = _pct(m, key, where)
            if p is not None:
                vals.append(p)
                if p >= 65:
                    why.append(label)
        role = m["arch"].get("role")
        bonus = 8 if role in ("support", "anchor", "closer", "lurker") else -8 if role in ("entry", "awper") else 0
        art = {"support": "Support", "anchor": "Anchor", "closer": "Closer", "lurker": "Lurker"}.get(role)
        hours = ((m["plan"].get("level") or {}).get("hours")) or 0
        exp = min(hours / 500, 8)
        score = (sum(vals) / len(vals) if vals else 50) + bonus + exp
        if bonus > 0:
            why.append(f"{art} profile: often in the back, sees the round unfold")
        if hours >= 1500:
            why.append(f"{hours:,} h played")
        res.append({"steamid": m["steamid"], "name": m["name"], "score": round(score), "why": why})
    res.sort(key=lambda x: -x["score"])
    return res


# ---------- maps ----------
def map_pool(M, meta):
    maps = set(PREMIER)
    for m in M:
        maps |= set(m["maps"]) | set((m["adv"].get("maps") or {}).keys())
    rows = []
    for mp in maps:
        per, w, t, known = [], 0, 0, 0
        for m in M:
            rec = (m["adv"].get("maps") or {}).get(mp) or {}
            rw = sum((rec.get(s) or {}).get("record", [0, 0])[0] for s in ("T", "CT"))
            rt = sum((rec.get(s) or {}).get("record", [0, 0])[1] for s in ("T", "CT"))
            n = (m["maps"].get(mp) or {}).get("matches", 0)
            if rt:
                known += 1
            w, t = w + rw, t + rt
            per.append({"steamid": m["steamid"], "name": m["name"], "matches": n, "rounds": rt, "win": round(100 * rw / rt) if rt else None})
        comfort = (w + 0.5 * 24) / (t + 24) * 100  # rounds won, pulled toward 50 % with few rounds
        rows.append({"map": mp, "premier": mp in PREMIER, "members_with_data": known, "rounds": t,
                     "round_win": round(100 * w / t) if t else None, "comfort": round(comfort, 1), "per_member": per,
                     "plants": (meta.get(mp) or {}).get("plants")})
    rows.sort(key=lambda r: (-(r["members_with_data"] > 0), -r["comfort"], -r["rounds"]))
    prem = [r for r in rows if r["premier"]]
    picks = [r["map"] for r in prem if r["members_with_data"]][:2]
    work = [r["map"] for r in prem if r["map"] not in picks][:2]
    return rows, picks, work


# ---------- per-map plan ----------
def _zone_perf(m, mp, side, key):
    for z in ((m["maps"].get(mp) or {}).get("sides", {}).get(side, {}) or {}).get("zones", []):
        if z["key"] == key:
            return z
    return None


def _shrunk(z, prior=0.5, k=6):
    if not z:
        return prior
    return (z["k"] + prior * k) / (z["k"] + z["d"] + k)


def _ref_map(M, mp):
    """Pool data of a map (identical for every member who played it): zones meta, spots, pool zones, lineups."""
    ref = None
    for m in M:
        x = m["maps"].get(mp)
        if x and (ref is None or x.get("pool", 0) > ref.get("pool", 0)):
            ref = x
    return ref


def _candidates(ref, side):
    """Positions of a side: the base's kill spots, completed by the base's zones (placed at the zone centre)."""
    spots = [dict(s) for s in ref["sides"].get(side, {}).get("best_spots", []) if s.get("zone")]
    have = {s["zone"] for s in spots}
    meta_px = {z["name"]: z for z in ref.get("zones_meta", [])}
    for z in ref["sides"].get(side, {}).get("pool_zones", []):
        zm = meta_px.get(z["name"])
        if zm and z["name"] not in have and z["k"] + z["d"] >= 8 and "spawn" not in z["key"].lower():
            spots.append({"px": zm["px"], "level": zm.get("level"), "zone": z["name"], "win": z.get("win"), "hold_pct": z.get("hold_pct"),
                          "scoped_pct": None, "t_med": z.get("t_med"), "players": max(1, round((z["k"] + z["d"]) / 4))})
            have.add(z["name"])
    return spots


def ct_setup(M, mp, ref, regions, meta):
    spots = _candidates(ref, "CT")
    key_of = {z["name"]: z["key"] for z in ref.get("zones_meta", [])}
    reg = lambda s: regions.get(key_of.get(s["zone"], s["zone"]), "mid")
    plants = (meta.get(mp) or {}).get("plants") or {}
    heavy = max(("A", "B"), key=lambda L: (plants.get(L) or {}).get("share", 0)) if plants else "B"

    def best(region, used, pred=lambda s: True):
        c = [s for s in spots if reg(s) == region and s["zone"] not in used and pred(s)]
        c.sort(key=lambda s: -((s.get("win") or 50) * min(s.get("players", 1), 20)))
        return c[0] if c else None
    slots, used = [], set()
    for kind, region, pred in (("anchor", "A", lambda s: True), ("anchor", "B", lambda s: True), ("mid", "mid", lambda s: True),
                               ("awp", None, lambda s: (s.get("scoped_pct") or 0) >= 25), ("support", heavy, lambda s: True)):
        s = None
        if region:
            s = best(region, used, pred)
        else:
            c = sorted([x for x in spots if x["zone"] not in used and pred(x)], key=lambda x: -((x.get("scoped_pct") or 0) * min(x.get("players", 1), 20)))
            s = c[0] if c else None
        if s is None:
            s = best(region or "mid", used) or best(heavy, used) or best("B" if heavy == "A" else "A", used) or best("mid", used)
        if s is None:
            continue
        used.add(s["zone"])
        if kind in ("anchor", "mid") and reg(s) != region:  # no spot in the wanted area: it becomes a reinforcement of where it is
            kind = "support" if reg(s) in ("A", "B") else "mid"
        slots.append({"kind": kind, "site": reg(s) if kind != "anchor" else region, "zone": s["zone"], "px": s["px"], "level": s.get("level"),
                      "base_win": s.get("win"), "hold_pct": s.get("hold_pct"), "t_med": s.get("t_med"), "players": s.get("players")})

    def fit(m, slot):
        s = m["scores"]
        role = {"anchor": s["anchor"] + 0.4 * s["closer"], "mid": 0.5 * s["entry"] + 0.5 * s["trader"], "awp": s["awper"] * 1.2,
                "support": s["support"] + 0.2 * s["anchor"]}[slot["kind"]] / 100
        z = _zone_perf(m, mp, "CT", key_of.get(slot["zone"], slot["zone"]))
        pres = min((z or {}).get("presence", 0) / 20, 1) * 0.15
        return 0.6 * role + 0.4 * _shrunk(z) + pres
    a = assign(M, slots, fit) if slots else {}
    for i, j in a.items():
        m, sl = M[i], slots[j]
        z = _zone_perf(m, mp, "CT", key_of.get(sl["zone"], sl["zone"]))
        sl["member"] = m["steamid"]
        sl["name"] = m["name"]
        why = []
        if z and z["k"] + z["d"] >= 4:
            why.append(f"{m['name']} goes {z['k']}-{z['d']} there ({z['win']}% of duels won)")
        elif z:
            why.append(f"{m['name']} plays there {z['presence']:.0f}% of the time")
        if sl["kind"] == "awp" and m["scores"]["awper"] >= 55:
            why.append("AWPer profile")
        if sl["kind"] == "anchor" and m["scores"]["anchor"] >= 60:
            why.append("anchor profile")
        sl["why"] = why
    for sl in slots:
        sl["do"] = CT_SLOT_DO[sl["kind"]]
        sl["label"] = {"anchor": f"Ancre {sl['site']}", "mid": "Milieu / rotation", "awp": "AWP",
                       "support": f"Renfort {sl['site']}" if sl["site"] in ("A", "B") else "Renfort milieu"}[sl["kind"]]
    return slots, heavy


def rotations(mp, slots):
    import midround
    refs = midround.route_refs().get(mp, {})
    out = []
    for sl in slots:
        if not sl.get("member") or sl["kind"] == "anchor":
            continue
        for L in ("A", "B"):
            if sl["site"] == L:
                continue
            r = refs.get(L, {})
            best = None
            for who in ("pro", "base"):
                rs = [x for x in (r.get(who) or {}).get("routes", []) if x.get("travel") is not None and x["n"] >= (5 if who == "pro" else 8)]
                if rs:
                    avg = ((r.get(who) or {}).get("timing") or {}).get("died_way") or 25
                    best = min(rs, key=lambda x: ((x["died"] * x["n"] + avg * 5) / (x["n"] + 5), x["travel"]))
                    best = dict(best, who=who)
                    break
            if best:
                out.append({"member": sl["member"], "name": sl["name"], "to": L, "route": " → ".join(humanize(z) for z in best["route"].split(" > ")),
                            "travel": best["travel"], "died": best["died"], "n": best["n"], "who": best["who"]})
    return out


def executes(M, mp, ref, regions, troles, meta):
    """Per site: the grenades of the execute (from the lineups the team's players know or the base throws) and who throws them."""
    key_of = {z["name"]: z["key"] for z in ref.get("zones_meta", [])}
    reg = lambda name: regions.get(key_of.get(name, name), "mid")
    lus = [l for l in ref["sides"].get("T", {}).get("lineups", []) if l.get("to_zone")]
    mine = defaultdict(set)  # lineups each member already threw (same from/to/type)
    for m in M:
        for l in (((m["maps"].get(mp) or {}).get("sides", {}).get("T") or {}).get("lineups", [])):
            if l.get("by") == m["name"]:
                mine[m["steamid"]].add((l["type"], l["from_zone"], l["to_zone"]))
    plants = (meta.get(mp) or {}).get("plants") or {}
    site_px = (meta.get(mp) or {}).get("site_px") or {}
    out = {}
    for L in ("A", "B"):
        c0 = site_px.get(L)
        near = lambda l: c0 and l.get("to_px") and ((l["to_px"][0] - c0[0]) ** 2 + (l["to_px"][1] - c0[1]) ** 2) ** 0.5 <= 190
        cand = [l for l in lus if near(l)]
        if len(cand) < 3:
            cand = [l for l in lus if reg(l["to_zone"]) == L or near(l)]
        picks = []
        for typ, n, key in (("smoke", 3, lambda l: -l["uses"]), ("flash", 2, lambda l: -((l.get("enemies_blind_avg") or 0) * 10 + l["uses"] / 50)),
                            ("molotov", 1, lambda l: -((l.get("damage_avg") or 0) + l["uses"] / 50))):
            seen = set()
            for l in sorted([x for x in cand if x["type"] == typ], key=key):
                if l["to_zone"] in seen:
                    continue
                seen.add(l["to_zone"])
                picks.append(l)
                if len(seen) >= n:
                    break
        # throwers: support first for smokes, trader flashes for the entry, entry keeps a self-flash
        order = {"smoke": ["support", "flex", "trader", "awper", "lurker", "entry"], "flash": ["trader", "support", "entry", "flex", "awper", "lurker"],
                 "molotov": ["support", "entry", "trader", "flex", "awper", "lurker"]}
        by_role = defaultdict(list)
        for sid, r in troles.items():
            by_role[r].append(sid)
        load = defaultdict(int)
        names = {m["steamid"]: m["name"] for m in M}
        items = []
        for l in picks:
            thrower = None
            for r in order[l["type"]]:
                for sid in by_role.get(r, []):
                    if (l["type"], l["from_zone"], l["to_zone"]) in mine[sid]:
                        thrower = sid
                        break
                if thrower:
                    break
            if not thrower:
                for r in order[l["type"]]:
                    c = [sid for sid in by_role.get(r, []) if load[sid] < 2 and r != "lurker"]
                    if c:
                        thrower = c[0]
                        break
            if thrower:
                load[thrower] += 1
            items.append({"type": l["type"], "from": l["from_zone"], "to": l["to_zone"], "setpos": l.get("setpos"), "t": l.get("t"),
                          "how": l.get("how"), "uses": l["uses"], "from_px": l.get("from_px"), "to_px": l.get("to_px"), "level": l.get("level"),
                          "member": thrower, "name": names.get(thrower, "a teammate"),
                          "known": bool(thrower and (l["type"], l["from_zone"], l["to_zone"]) in mine[thrower]),
                          "blind": l.get("enemies_blind_avg"), "damage": l.get("damage_avg")})
        p = plants.get(L) or {}
        out[L] = {"items": items, "plant_share": p.get("share"), "t_win": p.get("t_win"), "plant_t": p.get("plant_t")}
    return out


def t_lanes(M, mp, ref, regions, troles, target):
    """Early-round positions: pack on the execute side, lurker on the other side, AWP in the middle."""
    key_of = {z["name"]: z["key"] for z in ref.get("zones_meta", [])}
    spots = _candidates(ref, "T")
    reg = lambda s: regions.get(key_of.get(s["zone"], s["zone"]), "mid")
    other = "B" if target == "A" else "A"
    want = {"entry": target, "trader": target, "support": target, "flex": "mid", "awper": "mid", "lurker": other}
    used, out = set(), []
    for sid, role in sorted(troles.items(), key=lambda x: ["entry", "trader", "support", "awper", "flex", "lurker"].index(x[1])):
        s = None
        for region in (want[role], "mid", None):  # fall back to the middle, then anywhere
            c = [x for x in spots if (region is None or reg(x) == region) and x["zone"] not in used]
            c.sort(key=lambda x: -((x.get("win") or 50) * min(x.get("players", 1), 20)))
            if c:
                s = c[0]
                break
        if s:
            used.add(s["zone"])
        m = next(x for x in M if x["steamid"] == sid)
        out.append({"member": sid, "name": m["name"], "role": role, "role_name": ROLE_FR[role], "region": want[role],
                    "zone": s["zone"] if s else None, "px": s["px"] if s else None, "level": s.get("level") if s else None,
                    "t_med": s.get("t_med") if s else None, "do": T_ROLE_DO[role]})
    return out


def callouts(ref, regions):
    groups = defaultdict(list)
    for z in ref.get("zones_meta", []):
        groups[regions.get(z["key"], "mid")].append(z["name"])
    return {k: sorted(v) for k, v in groups.items()}


# ---------- together ----------
def synergy(M):
    """Matches played together (same team) and trades between each pair."""
    ids = [int(m["steamid"]) for m in M]
    pairs = {}
    for mid in os.listdir(config.DEEP):
        f = os.path.join(config.DEEP, mid, "samples.parquet")
        if not os.path.exists(f):
            continue
        s = pd.read_parquet(f, columns=["steamid", "side", "round"])
        present = [i for i in ids if i in set(s.steamid)]
        if len(present) < 2:
            continue
        r1 = s[s["round"] == s["round"].min()].drop_duplicates("steamid").set_index("steamid")["side"]
        D = pd.read_parquet(os.path.join(config.DEEP, mid, "duels.parquet"))
        R = os.path.join(config.DEEP, mid, "rounds.parquet")
        for a, b in itertools.combinations(sorted(present), 2):
            if r1.get(a) != r1.get(b):
                continue
            key = f"{a}-{b}"
            p = pairs.setdefault(key, {"a": str(a), "b": str(b), "matches": 0, "trades_ab": 0, "trades_ba": 0, "rounds": 0, "rounds_won": 0})
            p["matches"] += 1
            for x, y, k in ((a, b, "trades_ab"), (b, a, "trades_ba")):  # x avenges y
                for _, d in D[D.victim == y].iterrows():
                    if ((D.killer == x) & (D.victim == d.killer) & (D.tick > d.tick) & (D.tick <= d.tick + 5 * 64)).any():
                        p[k] += 1
            if os.path.exists(R):
                rr = pd.read_parquet(R)
                L = pd.read_parquet(os.path.join(config.DEEP, mid, "loadout.parquet"))
                la = L[L.steamid == a][["round", "side"]]
                w = rr.set_index("round").winner
                p["rounds"] += int(len(la))
                p["rounds_won"] += int(sum(w.get(r) == sd for r, sd in zip(la["round"], la.side)))
    names = {m["steamid"]: m["name"] for m in M}
    out = []
    for p in pairs.values():
        p["name_a"], p["name_b"] = names[p["a"]], names[p["b"]]
        p["round_win"] = round(100 * p["rounds_won"] / p["rounds"]) if p["rounds"] else None
        out.append(p)
    return sorted(out, key=lambda p: -p["matches"])


def collective(M):
    """Team averages of the percentiles that decide team rounds: the three weakest become collective goals."""
    checks = [("traded_pct", "bench", "Play in pairs (trades)", "Entry + trader always together, 1-2 s apart. In Team Deathmatch or on a retake server: no duel without a teammate in range."),
              ("flash_duels_pct", "bench", "Flash for the others", "Every execute starts with a flash thrown for the entry. Call 'flash' before throwing it."),
              ("nades_unused_24", "bench", "Empty the grenades", "Team 40-second rule: at 1:15 on the clock as T, all grenades are gone."),
              ("adv_conv", "mid", "Convert advantages", "At 5v4: regroup on a site, crossfires, no more solo duels."),
              ("isolated", "mid", "Espacement", "Nobody dies alone: everyone must be tradable within 2 s."),
              ("rt_solo", "mid", "Grouped retakes", "Bomb planted: regroup and go in together on the same flash."),
              ("rot_died", "mid", "Safe rotations", "A single voice calls the rotation, on solid info, and we rotate through the covered route.")]
    res = []
    for key, where, title, do in checks:
        vals = [(_pct(m, key, where), m["name"]) for m in M]
        known = [(v, n) for v, n in vals if v is not None]
        if not known:
            continue
        avg = sum(v for v, _ in known) / len(known)
        res.append({"key": key, "title": title, "avg_percentile": round(avg), "do": do,
                    "members": [{"name": n, "percentile": round(v)} for v, n in known]})
    res.sort(key=lambda r: r["avg_percentile"])
    return res


def individual(M, troles, ct_by_member):
    out = []
    for m in M:
        rules = (m["adv"].get("rules") or [])[:2]
        weak = [w for w in ((m["plan"].get("mid") or {}).get("weak") or []) if w.get("id") != "note"][:1]
        warm = ((m["plan"].get("training") or {}).get("warmup") or [])[:1]
        out.append({"steamid": m["steamid"], "name": m["name"], "t_role": ROLE_FR.get(troles.get(m["steamid"]), None),
                    "ct_role": ct_by_member.get(m["steamid"]),
                    "archetype": m["arch"].get("name"),
                    "priorities": [r.get("short") or r.get("title") for r in rules] + [w.get("fix") for w in weak if w.get("fix")],
                    "drill": warm[0]["map"] + " : " + warm[0]["text"] if warm else None})
    return out


def economy(M, troles, awp_ok):
    rows = []
    awper = next((sid for sid, r in troles.items() if r == "awper"), None)
    for m in M:
        W = m["plan"].get("weapons") or {}
        force = sorted([x for x in W.get("force", []) if x["rounds"] >= 4], key=lambda x: -x["adr"])
        pistol = [s for s in W.get("suggestions", []) if s["kind"] == "pistol_strong"]
        rows.append({"steamid": m["steamid"], "name": m["name"], "force": force[0]["key"] if force else None,
                     "force_adr": force[0]["adr"] if force else None, "pistol": bool(pistol),
                     "awp": m["steamid"] == awper})
    order = ([awper] if awper else []) + [sid for sid, r in sorted(troles.items(), key=lambda x: ["entry", "trader", "support", "flex", "lurker", "awper"].index(x[1])) if sid != awper]
    names = {m["steamid"]: m["name"] for m in M}
    return {"awp": names.get(awper) if awper else None, "awp_ok": awp_ok, "members": rows,
            "drop_order": [names[s] for s in order], "pistol_openers": [r["name"] for r in rows if r["pistol"]],
            "rules": ["We buy together: full, force or eco, called before buy time.",
                      "The richest drops first, in this order: " + ", ".join(names[s] for s in order) + (" (the AWP first)." if awper else "."),
                      "Force only if everyone's money plus the loss bonus still makes at least $4,000 next round."],
            "src": K.src("sw_economy", "h2k_economy")}


def team_matches(M):
    ids = {int(m["steamid"]) for m in M}
    rows = []
    for mid in os.listdir(config.DEEP):
        f = os.path.join(config.DEEP, mid, "samples.parquet")
        if not os.path.exists(f):
            continue
        s = pd.read_parquet(f, columns=["steamid", "side", "round"])
        r1 = s[s["round"] == s["round"].min()].drop_duplicates("steamid").set_index("steamid")["side"]
        here = [i for i in ids if i in r1.index]
        if len(here) < 2:
            continue
        sides = {r1[i] for i in here}
        if len(sides) != 1:
            continue
        st = None
        for i in here:
            st = _load(os.path.join(config.player_dir(i), "matches", mid, "stats.json"))
            if st:
                break
        meta = _load(os.path.join(config.DEEP, mid, "meta.json")) or {}
        rows.append({"id": mid, "map": meta.get("map"), "members": len(here), "time": (st or {}).get("match", {}).get("time"),
                     "result": (st or {}).get("result"), "score": (st or {}).get("final_score")})
    rows.sort(key=lambda r: r["time"] or "", reverse=True)
    return rows


# ---------- build ----------
def team_id(ids):
    return hashlib.sha1("-".join(sorted(str(i) for i in ids)).encode()).hexdigest()[:10]


def build(ids, owner=None):
    ids = list(dict.fromkeys(str(int(i)) for i in ids))
    if not 2 <= len(ids) <= 5:
        raise ValueError("A team has 2 to 5 players (you + 1 to 4 teammates).")
    M = [member(i) for i in ids]
    missing = [ids[i] for i, m in enumerate(M) if m is None]
    if missing:
        raise ValueError("These players are not analyzed yet: " + ", ".join(missing) + ". Run their analysis first from the search bar.")
    meta = map_meta()
    troles, missing_roles, awp_ok = t_roles(M)
    pool, picks, work = map_pool(M, meta)
    maps_plan = {}
    ct_by_member = {}
    for row in pool:
        mp = row["map"]
        ref = _ref_map(M, mp)
        if not ref or mp.startswith("cs_") or len(maps_plan) >= 5:
            continue
        regions = (meta.get(mp) or {}).get("regions") or {}
        slots, heavy = ct_setup(M, mp, ref, regions, meta)
        plants = (meta.get(mp) or {}).get("plants") or {}
        # the team's execute site: where the base Ts win most after planting, weighted by the team's own T rounds there
        target = max(("A", "B"), key=lambda L: (plants.get(L) or {}).get("t_win", 0)) if plants else "B"
        ex = executes(M, mp, ref, regions, troles, meta)
        lanes = t_lanes(M, mp, ref, regions, troles, target)
        for sl in slots:
            if sl.get("member"):
                ct_by_member.setdefault(sl["member"], {})[mp] = sl["label"]
        maps_plan[mp] = {"map": mp, "ct": slots, "heavy_site": heavy, "rotations": rotations(mp, slots), "t_target": target,
                         "t_lanes": lanes, "executes": ex, "callouts": callouts(ref, regions), "plants": plants,
                         "levels": ref.get("levels"), "site_px": (meta.get(mp) or {}).get("site_px"),
                         "videos": K.src(*K.MAP_VIDEOS.get(mp, []))}
    ct_summary = {sid: ", ".join(f"{humanize(mp.split('_')[-1]).capitalize()}: {lab}" for mp, lab in d.items()) for sid, d in ct_by_member.items()}
    plan = {"id": team_id(ids), "created": dt.datetime.now().isoformat(timespec="minutes"), "owner": str(owner or ids[0]),
            "members": [{"steamid": m["steamid"], "name": m["name"], "archetype": m["arch"].get("name"), "icon": m["arch"].get("icon"),
                         "light": m["light"], "has_scores": m["has_scores"], "scores": m["scores"],
                         "level": (m["plan"].get("level") or {}).get("name"), "t_role": troles.get(m["steamid"]),
                         "t_role_name": ROLE_FR.get(troles.get(m["steamid"])), "t_do": T_ROLE_DO.get(troles.get(m["steamid"]))} for m in M],
            "size": len(M), "missing_roles": [ROLE_FR[r] for r in missing_roles], "awp_ok": awp_ok,
            "igl": igl(M), "maps": pool, "picks": picks, "to_work": work, "plans": maps_plan,
            "economy": economy(M, troles, awp_ok), "synergy": synergy(M), "collective": collective(M)[:3],
            "individual": individual(M, troles, ct_summary), "matches": team_matches(M)[:20],
            "playbook": [{**{k: v for k, v in p.items() if k != "src"}, "src": K.src(*p["src"])} for p in K.PLAYBOOK
                         if set(p["tags"]) & {"rotation", "retake", "advantage", "postplant"}],
            "party": {k: {"title": v["title"], "items": v["items"], "src": K.src(*v["src"])} for k, v in K.PARTY.items()}}
    plan["party_key"] = {2: "duo", 3: "trio", 4: "quatuor", 5: "five"}[len(M)]
    os.makedirs(TEAMS, exist_ok=True)
    json.dump(plan, open(os.path.join(TEAMS, f"{plan['id']}.json"), "w", encoding="utf-8"), ensure_ascii=False, default=str)
    return plan


def suggestions(sid, limit=8):
    """Likely teammates of a player: partners seen in his team, then players met most often."""
    sid = int(sid)
    names = config.settings().get("players", {})
    cnt = defaultdict(int)
    for mid in os.listdir(config.DEEP):
        f = os.path.join(config.DEEP, mid, "samples.parquet")
        if not os.path.exists(f):
            continue
        s = pd.read_parquet(f, columns=["steamid", "side", "round"])
        r1 = s[s["round"] == s["round"].min()].drop_duplicates("steamid").set_index("steamid")["side"]
        if sid not in r1.index:
            continue
        for p, sd in r1.items():
            if p != sid and sd == r1[sid] and p:
                cnt[int(p)] += 1
    rows = [{"steamid": str(p), "name": (names.get(str(p)) or {}).get("name") or str(p), "together": n,
             "analyzed": os.path.exists(os.path.join(config.player_dir(p), "advice.json"))} for p, n in cnt.items()]
    rows.sort(key=lambda r: (-r["together"], not r["analyzed"]))
    return rows[:limit]


def index():
    out = []
    for f in sorted(os.listdir(TEAMS)) if os.path.exists(TEAMS) else []:
        if f.endswith(".json") and f != "index.json":
            t = _load(os.path.join(TEAMS, f))
            out.append({"id": t["id"], "created": t["created"], "members": [{"steamid": m["steamid"], "name": m["name"]} for m in t["members"]]})
    return sorted(out, key=lambda t: t["created"], reverse=True)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = build(sys.argv[1:])
    print(json.dumps({k: p[k] for k in ("id", "members", "picks", "to_work", "igl", "missing_roles")}, ensure_ascii=False, indent=1)[:4000])
