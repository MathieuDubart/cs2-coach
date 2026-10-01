"""The coaching plan of a player: level and experience, what to work on at this level, role tips, mid-round findings
(vs the base and the pros), rotation routes, where to play with each weapon, routine by phase, party-size advice,
state of the game, warm-up programme, experiments and KPI tracking.

It merges the player's own numbers with the sourced knowledge of knowledge.py. Saved into advice.json["plan"].
"""
import datetime as dt
import json
import os

import numpy as np

import config
import knowledge as K
from map_analysis import humanize

MID_TAGS = {  # mid-round metric -> playbook tags / phase items it points to
    "rot_died": ["rotation"], "rot_react": ["rotation"], "anchor_hold": ["anchor"], "lurk_died": ["lurk"], "lurk_kpr": ["lurk"],
    "t_late": ["advantage"], "rt_solo": ["retake"], "adv_throw": ["advantage"], "adv_conv": ["advantage"], "lost_died": ["save"],
    "isolated": ["lurk", "duel"], "steps_alone": ["lurk"], "steps_clutch": ["clutch"], "pp_surv": ["postplant"], "pp_kpr": ["postplant"],
}
MID_FIX = {
    "rot_died": "Leave on solid info and take the route that keeps you covered. If the site has already fallen, wait for your teammates at the entrance.",
    "rot_react": "As soon as the bomb is seen or 3 players are called, go: every second counts for the retake.",
    "anchor_hold": "As the anchor, your job is to survive 10 s and call the numbers: fall back one angle instead of dying first.",
    "lurk_died": "Your lurk dies too often: wait for the CTs to rotate before showing yourself, and walk.",
    "t_late": "Stick to the execute: arrive with the last flash, not 10 s later.",
    "rt_solo": "Bomb planted: no solo retake. Wait for your teammates, go in on the same flash.",
    "adv_throw": "When your team has one more player: no more solo duels, play the trade and the clock.",
    "adv_conv": "With the advantage, regroup and play crossfires: structure converts, not one more kill.",
    "lost_died": "Alone against 3 or more with little time: save your weapon.",
    "isolated": "Too many deaths with nobody next to you to trade: get closer to a teammate before taking a duel.",
    "steps_alone": "You run when you are alone near enemies: Shift, and reload by holding R.",
    "steps_clutch": "In a clutch, walk: every step gives you away.",
    "pp_surv": "After the plant: don't look for the duel, make the CTs come into your crossfires.",
    "pp_kpr": "After the plant, position yourself to punish the defuser rather than peeking.",
}


def _zone(z, mp=None):
    return humanize(z, mp) if z else z


def _route(r):
    return " → ".join(_zone(x) for x in str(r).split(" > ")) if r else r


def level(adv, sid=None):
    """Level from Premier rating (csstats), else Competitive rank, else the median map rank seen in demos."""
    cs = (adv or {}).get("csstats") or {}
    prem = next((p for p in cs.get("premier", []) if p.get("current")), None)
    rating = prem["current"] if prem else None
    comp = (cs.get("competitive") or {}).get("current")
    import csstats
    comp_i = csstats.SKILL.index(comp) if comp in csstats.SKILL else None
    if comp_i is None:
        comp_i = ((adv or {}).get("bench") or {}).get("my_rank")
    lv = None
    if rating:
        lv = next(x for x in K.LEVELS if rating < x["max"])
    elif comp_i:
        lv = next((x for x in K.LEVELS if x["comp"][0] <= comp_i <= x["comp"][1]), None)
    wins = (cs.get("competitive") or {}).get("wins") or 0
    prem_w = sum(int(p.get("wins") or 0) for p in cs.get("premier", []) if str(p.get("wins") or "").isdigit())
    since = ((adv or {}).get("steam") or {}).get("member_since") or ""
    yr = next((int(t) for t in since.replace(",", " ").split() if t.isdigit() and len(t) == 4), None)
    total = wins + prem_w
    pt = None
    if sid:
        import steamlink
        pt = steamlink.local_playtime(sid) or (config.settings().get("players", {}).get(str(sid)) or {}).get("playtime")
    hours = (pt or {}).get("total_h")
    if hours is not None:
        exp = "veteran" if hours >= 1500 else "regular" if hours >= 300 else "improving"
    else:
        exp = "veteran" if total >= 400 or (yr and dt.date.today().year - yr >= 7 and total >= 150) else "regular" if total >= 100 else "improving"
    return {"key": lv["key"] if lv else None, "name": lv["name"] if lv else None, "focus": lv["focus"] if lv else [],
            "rating": rating, "season": prem["season"] if prem else None, "comp": comp, "wins": wins, "premier_wins": prem_w,
            "since": yr, "experience": exp, "hours": hours, "two_weeks_h": (pt or {}).get("two_weeks_h"), "playtime_source": (pt or {}).get("source"),
            "src": K.src(*K.LEVEL_SRC)}


def mid_findings(mb):
    """Weak and strong mid-round points, most important first."""
    if not mb:
        return [], []
    bad, good = [], []
    for k, m in mb.get("metrics", {}).items():
        if m.get("percentile") is None or m.get("you") is None:
            continue
        u = m["unit"]
        fmt = lambda v: "—" if v is None else (f"{v:.0f}%" if u == "%" else f"{v:.1f}{u}")
        item = {"id": k, "label": m["label"], "you": m["you"], "median": m["median"], "pro": m.get("pro"), "percentile": m["percentile"],
                "unit": u, "text": f"{m['label'][0].upper() + m['label'][1:]}: you {fmt(m['you'])}, base median {fmt(m['median'])}"
                                   + (f", pros {fmt(m['pro'])}" if m.get("pro") is not None else "") + f" (out of {m['n_you']:.0f})."}
        if m["percentile"] <= 30:
            item["fix"] = MID_FIX.get(k)
            item["tags"] = MID_TAGS.get(k, [])
            bad.append(item)
        elif m["percentile"] >= 75:
            good.append(item)
    bad.sort(key=lambda x: x["percentile"])
    good.sort(key=lambda x: -x["percentile"])
    M = mb.get("metrics", {})
    rr, rd = M.get("rot_react"), M.get("rot_died")
    notes = []
    if rr and rd and rr.get("pro") and rd.get("pro") is not None and rr["you"] is not None and rd["you"] is not None:
        if rr["pro"] > rr["you"] + 2 and rd["pro"] < rd["you"]:
            notes.append(f"Pros rotate later than you ({rr['pro']:.0f} s after the Ts reach the site, vs {rr['you']:.0f} s), "
                         f"but die less on the way ({rd['pro']:.0f}% vs {rd['you']:.0f}%): they wait for solid info and arrive grouped.")
    return bad + [{"id": "note", "text": t, "percentile": None} for t in notes], good


def playbook(bad):
    tags = {t for b in bad for t in b.get("tags", [])}
    out = []
    for p in K.PLAYBOOK:
        prio = 2 if set(p["tags"]) & tags else 0
        out.append({**{k: v for k, v in p.items() if k != "src"}, "src": K.src(*p["src"]), "prio": prio})
    out.sort(key=lambda x: -x["prio"])
    return out


def routes_view(proutes, maps):
    """Per map and site: the player's rotations next to the base and pros, with readable zone names."""
    out = {}
    for mp, sites in (proutes or {}).items():
        for site, v in sites.items():
            ref = v.get("ref", {})
            base, pro = ref.get("base", {}), ref.get("pro", {})

            def pick(rs, timing, min_n):
                # death rate pulled toward the map average (5 virtual rotations): 3 rotations with no death is not "0 %"
                avg = (timing or {}).get("died_way") or 25
                rs = [r for r in rs if r.get("travel") is not None and r["n"] >= min_n]
                smooth = lambda r: (r["died"] * r["n"] + avg * 5) / (r["n"] + 5)
                return min(rs, key=lambda r: (smooth(r), r["travel"])) if rs else None
            best_b, best_p = pick(base.get("routes", []), base.get("timing"), 8), pick(pro.get("routes", []), pro.get("timing"), 5)
            out.setdefault(mp, {})[site] = {
                "n": v["n"], "arrived": v["arrived"], "died_way": v["died_way"], "react": v["react_med"], "travel": v["travel_med"],
                "mine": [{"route": _route(r), "n": n} for r, n in v["routes"].items()],
                "base": {"react": base.get("timing", {}).get("react_med"), "travel": base.get("timing", {}).get("travel_med"),
                         "died": base.get("timing", {}).get("died_way"), "n": base.get("timing", {}).get("n"),
                         "best": best_b and {**best_b, "route": _route(best_b["route"])},
                         "by_weapon": {w: {**x, "routes": [{"route": _route(r["route"]), "n": r["n"]} for r in x["routes"]]} for w, x in base.get("by_weapon", {}).items()}},
                "pro": {"react": pro.get("timing", {}).get("react_med"), "travel": pro.get("timing", {}).get("travel_med"),
                        "died": pro.get("timing", {}).get("died_way"), "n": pro.get("timing", {}).get("n"),
                        "best": best_p and {**best_p, "route": _route(best_p["route"])},
                        "top": [{**r, "route": _route(r["route"])} for r in pro.get("routes", [])[:3]]},
            }
    return out


def weapon_positions(wz, maps):
    """Where to set up with each weapon class on the player's maps (base: duel win rate; pros: AWP spots)."""
    out = {}
    for mp in maps:
        for side, classes in (wz.get(mp) or {}).items():
            for wc, v in classes.items():
                if wc in ("pistol", "heavy", "auto"):
                    continue
                zones = [z for z in v["zones"] if z.get("duel_win") is not None or wc == "pro_awp"]
                if wc != "pro_awp":
                    zones = sorted(zones, key=lambda z: -(z["duel_win"] or 0))
                out.setdefault(mp, {}).setdefault(side, {})[wc] = {
                    "label": "Pro AWPers (HLTV demos)" if wc == "pro_awp" else K_CLASS.get(wc, wc), "rounds": v["rounds"],
                    "zones": [{**z, "name": _zone(z["zone"], mp)} for z in zones[:5]]}
    return out


K_CLASS = {"awp": "AWP", "scout": "Scout", "rifle": "Rifles (AK, M4, AUG, SG)", "rifle_eco": "Galil / FAMAS", "smg": "SMG", "shotgun": "Shotguns"}


def training(adv, deep, mb):
    """15-minute warm-up built on the player's weak points, plus a weekly routine."""
    B = ((adv or {}).get("bench") or {}).get("metrics", {})
    rid = {r["id"] for r in (adv or {}).get("rules", [])}
    blocks = []

    def pct(m):
        return (B.get(m) or {}).get("percentile")
    react = ((deep or {}).get("reaction") or {}).get("better_than_pct")
    pre = ((deep or {}).get("preaim") or {}).get("better_than_pct")
    if react is not None and react < 50:
        blocks.append(("reaction", f"Your reaction time is slower than {100 - react}% of the players in your matches."))
    if (pct("xhair") is not None and pct("xhair") < 50) or (pre is not None and pre < 50) or "xhair" in rid:
        blocks.append(("xhair", "Your crosshair is not at head height yet when the enemy appears."))
    if "pistol" in rid or (pct("pistol_moving") is not None and pct("pistol_moving") < 40):
        blocks.append(("pistol", "Too many pistol shots while moving."))
    if "spray" in rid or (pct("b9_hit") is not None and pct("b9_hit") < 40):
        blocks.append(("spray", "Your spray falls apart after a few bullets."))
    if len(blocks) < 2:
        blocks.append(("precision", "First-shot accuracy."))
    blocks = blocks[:2] + [("dm", "Get into rhythm before the game.")]
    if "nades" in rid:
        blocks.append(("nades", "You often die with your grenades."))
    warm = [{"drill": k, "why": why, **{a: b for a, b in K.DRILLS[k].items() if a != "src"}, "src": K.src(*K.DRILLS[k]["src"])} for k, why in blocks]
    week = [
        {"title": "1 demo session", "text": "Rewatch your 5 most costly deaths of the week in the 2D replay (Matches tab), asking yourself: could I be traded?"},
        {"title": "1 experiment at a time", "text": "Start an experiment from the Progress tab and keep it until the verdict."},
        {"title": "4 maps ready", "text": "Reread the T and CT sheets of your 4 Premier maps (map picks since September 22, 2026)."},
    ]
    return {"warmup": warm, "total_min": sum(w["min"] for w in warm), "week": week}


def kpis(sid, stats, mid_rows):
    """Per-match series of the numbers the plan asks to move."""
    import context
    series = {"rating": [], "adr": [], "traded": [], "nades": [], "xhair": [], "isolated": [], "adv_throw": []}
    for st in stats:
        o = st["overview"]
        t = st["match"].get("time")
        r = max(st["rounds"], 1)
        series["rating"].append([t, round(context.rating(o["kills"], o["deaths"], o["assists"], o["adr"], o["kast_pct"], r), 2)])
        series["adr"].append([t, o["adr"]])
        d = o["trades"]["my_deaths"]
        if d:
            series["traded"].append([t, round(100 * o["trades"]["my_deaths_traded"] / d)])
        series["nades"].append([t, round(sum(len(x["grenades_unused_at_death"]) for x in st["per_round"]) / r * 24, 1)])
        xh = (st["aim"].get("crosshair_placement") or {}).get("median_error_deg")
        if xh is not None:
            series["xhair"].append([t, round(xh, 1)])
        mr = mid_rows.get(st["match"]["match_id"])
        if mr is not None:
            g = lambda k: 0.0 if mr.get(k) is None or mr.get(k) != mr.get(k) else float(mr.get(k))  # NaN -> 0
            series["isolated"].append([t, round(g("isolated_deaths") / max(g("rounds"), 1) * 24, 1)])
            if g("adv_rounds") >= 3:
                series["adv_throw"].append([t, round(100 * g("adv_throw") / g("adv_rounds"))])
    meta = {"rating": ("Match rating (≈ HLTV 2.0)", "", True), "adr": ("Damage per round", "", True), "traded": ("Deaths traded", "%", True),
            "nades": ("Grenades that died with you (per 24 rounds)", "", False), "xhair": ("Crosshair offset", "°", False),
            "isolated": ("Isolated deaths (per 24 rounds)", "", False), "adv_throw": ("Avantages rendus", "%", False)}
    out = []
    for k, s in series.items():
        s = sorted([x for x in s if x[0]], key=lambda x: x[0])
        if len(s) < 2:
            continue
        vals = [v for _, v in s]
        last = vals[-3:]
        prev = vals[:-3] or vals
        out.append({"key": k, "label": meta[k][0], "unit": meta[k][1], "higher_better": meta[k][2], "series": s,
                    "recent": round(sum(last) / len(last), 2), "before": round(sum(prev) / len(prev), 2)})
    return out


PREMIER = ["de_ancient", "de_anubis", "de_cache", "de_dust2", "de_inferno", "de_mirage", "de_nuke"]
ZONE_PX = os.path.join(config.OUT, "population", "zone_px.json")


def zone_refs():
    """Radar position of every zone and the floors of each map, from the analyzed player with the most data there."""
    import weapons
    n = f"v3-{weapons._n_demos()}"   # v3: callouts
    if os.path.exists(ZONE_PX):
        cur = json.load(open(ZONE_PX, encoding="utf-8"))
        if cur.get("_n") == n:
            return cur
    best = {}
    for sid in os.listdir(config.PLAYERS):
        f = os.path.join(config.player_dir(sid), "cross.json")
        if not os.path.exists(f):
            continue
        try:
            c = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for m in c.get("maps", []):
            if m["map"] not in best or m.get("pool", 0) > best[m["map"]]["pool"]:
                best[m["map"]] = {"pool": m.get("pool", 0), "levels": m.get("levels"),
                                  "zones": [{"name": z["name"], "px": z["px"], "level": z.get("level")} for z in m.get("zones_meta", [])]}
    best["_n"] = n
    json.dump(best, open(ZONE_PX, "w", encoding="utf-8"), ensure_ascii=False)
    return best


def map_refs(maps):
    """What works on a map for everyone (base and pros): positions by weapon and side, where the Ts plant, safest
    rotations. Used by the in-game sheet when the player has no match of his own on that map yet."""
    import midround
    import team
    import weapons
    meta, wz, rr, zr = team.map_meta(), weapons.weapon_zones(), midround.route_refs(), zone_refs()
    out = {}
    for mp in maps:
        z = zr.get(mp) or {}
        px = {x["name"]: x for x in z.get("zones", [])}
        ent = {"plants": (meta.get(mp) or {}).get("plants"), "rounds": (meta.get(mp) or {}).get("rounds"), "levels": z.get("levels"),
               "positions": {}, "rotations": {}, "videos": K.src(*K.MAP_VIDEOS.get(mp, []))}
        for side in ("T", "CT"):
            for wc in ("rifle", "awp", "pro_awp", "smg"):
                v = ((wz.get(mp) or {}).get(side) or {}).get(wc)
                if not v:
                    continue
                zs = []
                for zz in v["zones"][:6]:
                    name = _zone(zz["zone"], mp)
                    p = px.get(name) or {}
                    zs.append({"name": name, "share": zz["share"], "duel_win": zz.get("duel_win"), "duels": zz.get("duels"),
                               "round_win": zz.get("round_win"), "px": p.get("px"), "level": p.get("level")})
                ent["positions"].setdefault(side, {})[wc] = {"rounds": v["rounds"], "zones": zs}
        for site, d in (rr.get(mp) or {}).items():
            best = None
            for who in ("pro", "base"):
                x = d.get(who) or {}
                avg = (x.get("timing") or {}).get("died_way") or 25
                rs = [r for r in x.get("routes", []) if r.get("travel") is not None and r["n"] >= (5 if who == "pro" else 8)]
                if rs:
                    b = min(rs, key=lambda r: ((r["died"] * r["n"] + avg * 5) / (r["n"] + 5), r["travel"]))
                    best = {"route": _route(b["route"]), "travel": b["travel"], "died": b["died"], "n": b["n"], "who": who}
                    break
            if best:
                ent["rotations"][site] = best
        out[mp] = ent
    return out


def my_spots(sid, cross, maps):
    """Per map and side: the zones you play, how often, the duels you win there, and the rounds where you got two
    kills or more from there (multi-kills), with where on the radar your kills come from."""
    import collections
    import glob
    rounds = collections.defaultdict(list)
    for f in glob.glob(os.path.join(config.player_dir(sid), "matches", "*", "map.json")):
        try:
            m = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("map") not in maps:
            continue
        mid = os.path.basename(os.path.dirname(f))
        for k in m.get("my_kills") or []:
            rounds[(m["map"], k.get("side"), mid, k.get("round"))].append(k)
    multi = collections.defaultdict(lambda: {"m2": 0, "m3": 0, "best": 0, "px": []})
    for (mp, side, _, _), ks in rounds.items():
        for k in ks:
            if k.get("zone") and k.get("px"):
                multi[(mp, side, k["zone"])]["px"].append(k["px"])
        zc = collections.Counter(k["zone"] for k in ks if k.get("zone"))
        if len(ks) >= 2 and zc:
            e = multi[(mp, side, zc.most_common(1)[0][0])]
            e["m2"] += 1
            e["m3"] += len(ks) >= 3
            e["best"] = max(e["best"], len(ks))
    out = {}
    for m in (cross or {}).get("maps", []):
        mp = m["map"]
        if mp not in maps:
            continue
        meta = {z["name"]: z for z in m.get("zones_meta", [])}
        for side in ("T", "CT"):
            res = []
            for z in (m.get("sides", {}).get(side) or {}).get("zones", []):
                mm = multi.get((mp, side, z["name"])) or {}
                if (z.get("presence") or 0) < 4 and not mm.get("m2"):
                    continue
                pts = mm.get("px") or []
                px = [round(float(np.median([p[0] for p in pts]))), round(float(np.median([p[1] for p in pts])))] if len(pts) >= 3 else (meta.get(z["name"]) or {}).get("px")
                if not px:
                    continue
                res.append({"name": z["name"], "px": [round(px[0]), round(px[1])], "level": (meta.get(z["name"]) or {}).get("level"),
                            "presence": z.get("presence"), "k": z.get("k"), "d": z.get("d"), "win": z.get("win"),
                            "others_win": z.get("others_win"), "verdict": z.get("verdict"),
                            "multi2": mm.get("m2", 0), "multi3": mm.get("m3", 0), "best": mm.get("best", 0)})
            res.sort(key=lambda x: -(x["presence"] or 0))
            if res:
                out.setdefault(mp, {})[side] = res[:8]
    return out


def build(steamid, adv, cross=None, deep=None, light=False):
    import context
    import experiments
    sid = int(steamid)
    lv = level(adv, sid)
    role = (adv.get("archetype") or {}).get("role")
    plan = {"updated": K.UPDATED, "level": lv, "meta": [{**m, "src": K.src(*m["src"])} for m in K.META],
            "phases": [{"key": p["key"], "title": p["title"], "items": [{**{a: b for a, b in i.items() if a != "src"}, "src": K.src(*i["src"])} for i in p["items"]]}
                       for p in K.PHASES],
            "party": {k: {"title": v["title"], "items": v["items"], "src": K.src(*v["src"])} for k, v in K.PARTY.items()},
            "role": ({"role": role, **{a: b for a, b in K.ROLE_TIPS[role].items() if a != "src"}, "src": K.src(*K.ROLE_TIPS[role]["src"])}
                     if role in K.ROLE_TIPS else None)}
    if light:
        plan["playbook"] = playbook([])
        try:
            plan["map_refs"] = map_refs(PREMIER)
        except Exception as e:
            print("map references unavailable:", e)
        try:
            import tside
            plan["tside"] = tside.tendencies(PREMIER)
        except Exception as e:
            print("T tendencies unavailable:", e)
        return plan
    import cs2coach
    import midround
    import weapons
    mids = cs2coach.player_matches(sid)
    mb = midround.bench(sid)
    bad, good = mid_findings(mb)
    plan["mid"] = {"bench": mb, "weak": bad, "strong": good}
    plan["playbook"] = playbook(bad)
    maps = sorted({m["map"] for m in (cross or {}).get("maps", [])})
    plan["routes"] = routes_view(midround.player_routes(sid), maps)
    try:
        plan["spots"] = my_spots(sid, cross, maps)
    except Exception as e:
        print("spots unavailable:", e)
    plan["weapon_positions"] = weapon_positions(weapons.weapon_zones(), maps)
    try:
        plan["map_refs"] = map_refs(sorted(set(PREMIER) | set(maps)))
    except Exception as e:
        print("map references unavailable:", e)
    wp = weapons.player(sid, mids)
    plan["weapons"] = wp
    try:
        import buys
        zd = {(m["map"], side): {z["name"]: (z["k"], z["d"]) for z in S.get("zones", [])}
              for m in (cross or {}).get("maps", []) for side, S in m.get("sides", {}).items()}
        plan["buys"] = buys.adapted(sid, sorted(set(PREMIER) | set(maps)), adv.get("archetype"), zd, wp)
    except Exception as e:
        print("buys by round type unavailable:", e)
    try:
        import tside
        plan["tside"] = tside.tendencies(sorted(set(PREMIER) | set(maps)))
    except Exception as e:
        print("T tendencies unavailable:", e)
    try:
        import nades
        stats_n = []
        mdir_n = os.path.join(config.player_dir(sid), "matches")
        for mid in os.listdir(mdir_n) if os.path.exists(mdir_n) else []:
            f = os.path.join(mdir_n, mid, "stats.json")
            if os.path.exists(f):
                st = json.load(open(f, encoding="utf-8"))
                if not st.get("error"):
                    stats_n.append(st)
        stats_n.sort(key=lambda s: (s.get("match") or {}).get("time") or "")
        lanes = {mp: (M.get("plays") or {}).get("lanes") for mp, M in ((plan.get("tside") or {}).get("maps") or {}).items()}
        plan["nades"] = nades.for_player(sid, sorted(set(PREMIER) | set(maps)), cross, stats_n, lanes=lanes)
    except Exception as e:
        print("grenades unavailable:", e)
    ctx = context.analyze(sid)
    if ctx:
        ctx["matches"] = ctx["matches"][-40:]
    plan["context"] = ctx
    grp = next((f for f in (ctx or {}).get("factors", []) if f["title"] == "Group"), None)
    if grp and grp["rows"]:
        top = max(grp["rows"], key=lambda r: r["n"])["group"]
        plan["party_mode"] = {"solo": "solo", "duo": "duo", "group of 3": "trio", "group of 4": "quatuor", "group of 5": "five"}.get(top, "solo")
    plan["videos"] = {mp: K.src(*K.MAP_VIDEOS[mp]) for mp in maps if mp in K.MAP_VIDEOS}
    plan["training"] = training(adv, deep, mb)
    stats = []
    mdir = os.path.join(config.player_dir(sid), "matches")
    for mid in os.listdir(mdir) if os.path.exists(mdir) else []:
        f = os.path.join(mdir, mid, "stats.json")
        if os.path.exists(f):
            st = json.load(open(f, encoding="utf-8"))
            if not st.get("error"):
                stats.append(st)
    import pandas as pd
    mid_rows = {}
    for st in stats:
        f = os.path.join(midround.OUT, f"{st['match']['match_id']}.parquet")
        if os.path.exists(f):
            r = pd.read_parquet(f)
            r = r[r.steamid == sid]
            if len(r):
                mid_rows[st["match"]["match_id"]] = r.iloc[0].to_dict()
    plan["kpis"] = kpis(sid, stats, mid_rows)
    plan["experiments"] = experiments.report(sid, adv, mb, wp, ctx, cross)
    try:
        import voice
        if os.path.exists(voice.DIR):
            plan["calls"] = voice.summary(sid)
    except Exception as e:
        print("calls unavailable:", e)
    try:
        import review
        plan["review"] = review.build(sid, stats, mid_rows, ctx, plan["experiments"], adv)
    except Exception as e:  # the review is a bonus: never block the plan
        plan["review"] = None
        print("review unavailable:", e)
    return plan
