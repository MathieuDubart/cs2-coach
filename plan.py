"""The coaching plan of a player: level and experience, what to work on at this level, role tips, mid-round findings
(vs the base and the pros), rotation routes, where to play with each weapon, routine by phase, party-size advice,
state of the game, warm-up programme, experiments and KPI tracking.

It merges the player's own numbers with the sourced knowledge of knowledge.py. Saved into advice.json["plan"].
"""
import datetime as dt
import json
import os

import config
import knowledge as K
from map_analysis import humanize

MID_TAGS = {  # mid-round metric -> playbook tags / phase items it points to
    "rot_died": ["rotation"], "rot_react": ["rotation"], "anchor_hold": ["anchor"], "lurk_died": ["lurk"], "lurk_kpr": ["lurk"],
    "t_late": ["advantage"], "rt_solo": ["retake"], "adv_throw": ["advantage"], "adv_conv": ["advantage"], "lost_died": ["save"],
    "isolated": ["lurk", "duel"], "steps_alone": ["lurk"], "steps_clutch": ["clutch"], "pp_surv": ["postplant"], "pp_kpr": ["postplant"],
}
MID_FIX = {
    "rot_died": "Pars sur une info sûre et prends la route qui te garde couvert. Si le site est déjà tombé, attends tes coéquipiers à l'entrée.",
    "rot_react": "Dès que la bombe est vue ou que 3 joueurs sont annoncés, pars : chaque seconde compte pour le retake.",
    "anchor_hold": "En ancre, ton job est de survivre 10 s et d'annoncer le nombre : recule d'un angle au lieu de mourir en premier.",
    "lurk_died": "Ton lurk meurt trop souvent : attends que les CT tournent avant de te montrer, et marche.",
    "t_late": "Colle à l'exécution : arrive avec la dernière flash, pas 10 s après.",
    "rt_solo": "Bombe posée : pas de retake seul. Attends tes coéquipiers, entrez sur la même flash.",
    "adv_throw": "Quand ton équipe a un joueur de plus : plus de duel seul, joue le trade et le temps.",
    "adv_conv": "En avantage, regroupe-toi et joue en tirs croisés : c'est la structure qui convertit, pas un kill de plus.",
    "lost_died": "Seul contre 3 ou plus avec peu de temps : sauve ton arme.",
    "isolated": "Trop de morts sans personne à côté pour te venger : rapproche-toi d'un coéquipier avant de prendre un duel.",
    "steps_alone": "Tu cours quand tu es seul près des ennemis : Shift, et recharge en maintenant R.",
    "steps_clutch": "En clutch, marche : chaque pas te trahit.",
    "pp_surv": "Après la pose : ne cherche pas le duel, fais venir les CT dans tes tirs croisés.",
    "pp_kpr": "Après la pose, place-toi pour punir le défuseur plutôt que de peeker.",
}


def _zone(z):
    return humanize(z) if z else z


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
        exp = "vétéran" if hours >= 1500 else "régulier" if hours >= 300 else "en progression"
    else:
        exp = "vétéran" if total >= 400 or (yr and dt.date.today().year - yr >= 7 and total >= 150) else "régulier" if total >= 100 else "en progression"
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
        fmt = lambda v: "—" if v is None else (f"{v:.0f} %" if u == "%" else f"{v:.1f}{u}".replace(".", ","))
        item = {"id": k, "label": m["label"], "you": m["you"], "median": m["median"], "pro": m.get("pro"), "percentile": m["percentile"],
                "unit": u, "text": f"{m['label'][0].upper() + m['label'][1:]} : toi {fmt(m['you'])}, médiane de la base {fmt(m['median'])}"
                                   + (f", pros {fmt(m['pro'])}" if m.get("pro") is not None else "") + f" (sur {m['n_you']:.0f})."}
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
            notes.append(f"Les pros partent en rotation plus tard que toi ({rr['pro']:.0f} s après l'arrivée des T sur le site, contre {rr['you']:.0f} s), "
                         f"mais meurent moins en route ({rd['pro']:.0f} % contre {rd['you']:.0f} %) : ils attendent une info sûre et arrivent groupés.")
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
                    "label": "AWPers pros (démos HLTV)" if wc == "pro_awp" else K_CLASS.get(wc, wc), "rounds": v["rounds"],
                    "zones": [{**z, "name": _zone(z["zone"])} for z in zones[:5]]}
    return out


K_CLASS = {"awp": "AWP", "scout": "Scout", "rifle": "Fusils (AK, M4, AUG, SG)", "rifle_eco": "Galil / FAMAS", "smg": "SMG", "shotgun": "Fusils à pompe"}


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
        blocks.append(("reaction", f"Ton temps de réaction est plus lent que {100 - react} % des joueurs de tes matchs."))
    if (pct("xhair") is not None and pct("xhair") < 50) or (pre is not None and pre < 50) or "xhair" in rid:
        blocks.append(("xhair", "Ton viseur n'est pas encore à hauteur de tête au moment où l'ennemi apparaît."))
    if "pistol" in rid or (pct("pistol_moving") is not None and pct("pistol_moving") < 40):
        blocks.append(("pistol", "Trop de tirs au pistolet en mouvement."))
    if "spray" in rid or (pct("b9_hit") is not None and pct("b9_hit") < 40):
        blocks.append(("spray", "Ton spray décroche après quelques balles."))
    if len(blocks) < 2:
        blocks.append(("precision", "Précision du premier tir."))
    blocks = blocks[:2] + [("dm", "Mettre le rythme avant la game.")]
    if "nades" in rid:
        blocks.append(("nades", "Tu meurs souvent avec tes grenades."))
    warm = [{"drill": k, "why": why, **{a: b for a, b in K.DRILLS[k].items() if a != "src"}, "src": K.src(*K.DRILLS[k]["src"])} for k, why in blocks]
    week = [
        {"title": "1 séance de démo", "text": "Revois tes 5 morts les plus coûteuses de la semaine dans le replay 2D (onglet Matchs), en te demandant : étais-je tradable ?"},
        {"title": "1 expérience à la fois", "text": "Lance une expérience de l'onglet Progresser et tiens-la jusqu'au verdict."},
        {"title": "4 cartes prêtes", "text": "Relis les fiches T et CT de tes 4 cartes Premier (choix de cartes depuis le 22 septembre 2026)."},
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
    meta = {"rating": ("Note du match (≈ HLTV 2.0)", "", True), "adr": ("Dégâts par round", "", True), "traded": ("Morts vengées", "%", True),
            "nades": ("Grenades mortes avec toi (par 24 rounds)", "", False), "xhair": ("Écart du viseur", "°", False),
            "isolated": ("Morts isolées (par 24 rounds)", "", False), "adv_throw": ("Avantages rendus", "%", False)}
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
    plan["weapon_positions"] = weapon_positions(weapons.weapon_zones(), maps)
    wp = weapons.player(sid, mids)
    plan["weapons"] = wp
    ctx = context.analyze(sid)
    if ctx:
        ctx["matches"] = ctx["matches"][-40:]
    plan["context"] = ctx
    grp = next((f for f in (ctx or {}).get("factors", []) if f["title"] == "Groupe"), None)
    if grp and grp["rows"]:
        top = max(grp["rows"], key=lambda r: r["n"])["group"]
        plan["party_mode"] = {"solo": "solo", "duo": "duo", "groupe de 3": "trio", "groupe de 4": "quatuor", "groupe de 5": "five"}.get(top, "solo")
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
    return plan
