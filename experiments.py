"""Experiments: the player tests something for a few games (a weapon, a position, a habit, a warm-up, a session limit)
and the coach measures it on the following matches, compared with the matches before the start.

Stored in out/experiments/<steamid>.json. Evaluated from the analyzed matches (no manual input).
"""
import datetime as dt
import json
import math
import os
import uuid

import pandas as pd

import config
import context

DIR = os.path.join(config.OUT, "experiments")

# metric: (label, unit, higher_is_better)
METRICS = {
    "rating": ("note du match (≈ rating HLTV 2.0)", "", True),
    "adr": ("dégâts par round", "", True),
    "traded_pct": ("morts vengées", "%", True),
    "nades_unused_pr": ("grenades mortes avec toi par round", "", False),
    "xhair": ("écart du viseur avant le duel", "°", False),
    "pistol_moving": ("tirs au pistolet en mouvement", "%", False),
    "isolated_pr": ("morts isolées par round", "", False),
    "adv_throw": ("avantages numériques rendus (par round d'avantage)", "%", False),
    "rot_died": ("morts pendant une rotation", "%", False),
    "rt_solo": ("morts seul en retake", "%", False),
    "steps_alone_pr": ("pas audibles quand tu es seul, par round", "", False),
    "open_win": ("premiers duels gagnés", "%", True),
    "weapon_duels": ("duels gagnés avec l'arme", "%", True),
    "weapon_adr": ("dégâts par round avec l'arme", "", True),
    "zone_duels": ("duels gagnés dans la zone", "%", True),
    "first_game": ("note de la 1re game de la session", "", True),
}

TEMPLATES = {
    "weapon_swap": {"cat": "Arme", "title": "Remplacer {weapon} par {alt}", "metric": "weapon_duels", "min": 25, "unit_n": "duels",
                    "how": ["Pendant 5 games, achète {alt} à chaque fois que tu aurais pris {weapon}.", "Le coach compare tes duels et tes dégâts avec chacune des deux armes."]},
    "weapon_keep": {"cat": "Arme", "title": "Jouer {weapon} en priorité", "metric": "weapon_adr", "min": 20, "unit_n": "rounds",
                    "how": ["Achète {weapon} dès que l'économie le permet pendant 5 games."]},
    "zone": {"cat": "Position", "title": "Jouer {zone_name} sur {map_name} en {side}", "metric": "zone_duels", "min": 12, "unit_n": "duels",
             "how": ["Sur {map_name} en {side}, prends {zone_name} dès que c'est libre, pendant 3 à 5 games sur cette carte.", "Le coach mesure tes duels dans la zone."]},
    "trade_distance": {"cat": "Habitude", "title": "Rester à distance de trade", "metric": "isolated_pr", "min": 4, "unit_n": "games",
                       "how": ["Avant chaque duel, un coéquipier doit pouvoir te venger en moins de 2 secondes.", "Si personne ne te couvre : recule ou attends."]},
    "nades_40s": {"cat": "Habitude", "title": "Règle des 40 secondes : grenades lancées", "metric": "nades_unused_pr", "min": 4, "unit_n": "games",
                  "how": ["En T, à 1:15 au chrono, toutes tes grenades doivent être parties.", "En CT, ralentis le premier contact avec une molotov ou une HE."]},
    "advantage": {"cat": "Habitude", "title": "En avantage numérique, je joue le trade", "metric": "adv_throw", "min": 4, "unit_n": "games",
                  "how": ["Dès que ton équipe a un joueur de plus : plus de duel seul, tu joues à deux et tu fais tourner le chrono.", "Regroupe-toi sur un site plutôt que de chercher un kill de plus."]},
    "rotation": {"cat": "Mi-round", "title": "Rotations par la route sûre, au bon signal", "metric": "rot_died", "min": 4, "unit_n": "games",
                 "how": ["Pars en rotation seulement sur une info sûre (bombe vue, 3 joueurs, 2 flashs et plus).", "Prends la route qui te garde couvert et annonce « je tourne »."]},
    "retake_group": {"cat": "Mi-round", "title": "Retake groupé, jamais seul", "metric": "rt_solo", "min": 4, "unit_n": "games",
                     "how": ["Bombe posée : attends tes coéquipiers et entrez sur la même flash.", "Seul contre 3 ou plus avec peu de temps : sauve ton arme."]},
    "silent": {"cat": "Habitude", "title": "Marcher (Shift) quand tu es seul", "metric": "steps_alone_pr", "min": 4, "unit_n": "games",
               "how": ["Dès que tu es à plus de 1 200 unités d'un coéquipier en T, et dans tous les clutchs : Shift.", "Recharge silencieuse (maintiens R) si un ennemi est proche."]},
    "prefire": {"cat": "Entraînement", "title": "10 min de prefire avant de jouer", "metric": "xhair", "min": 5, "unit_n": "games",
                "how": ["Avant chaque session : 10 minutes de carte de prefire (workshop) sur la carte que tu vas jouer.", "En jeu : viseur à hauteur de tête sur le prochain angle, pas au sol."]},
    "counter_strafe": {"cat": "Entraînement", "title": "Contre-strafe au pistolet", "metric": "pistol_moving", "min": 5, "unit_n": "games",
                       "how": ["Aim Botz, 5 min au pistolet : A-D, arrêt, un tir, jamais en mouvement.", "Deathmatch pistolets 5 min avant la session."]},
    "warmup": {"cat": "Session", "title": "Échauffement de 15 min avant la 1re game", "metric": "first_game", "min": 4, "unit_n": "sessions",
               "how": ["5 min Aim Botz ou Aim Rush, 5 min Deathmatch, 5 min de stuffs sur la carte du jour.", "Note-le dans le journal d'avant-session."]},
    "session_limit": {"cat": "Session", "title": "Maximum 3 games par session, stop après 2 défaites", "metric": "rating", "min": 6, "unit_n": "games",
                      "how": ["Au bout de 3 games ou de 2 défaites d'affilée : pause de 30 minutes minimum ou fin de session."]},
    "opening": {"cat": "Habitude", "title": "Ouvertures avec flash uniquement", "metric": "open_win", "min": 5, "unit_n": "games",
                "how": ["Plus de premier duel à sec : flash (la tienne ou celle d'un coéquipier) ou tu laisses l'ouverture."]},
}


def _file(sid):
    return os.path.join(DIR, f"{sid}.json")


def load(sid):
    f = _file(sid)
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else []


def save(sid, exps):
    os.makedirs(DIR, exist_ok=True)
    json.dump(exps, open(_file(sid), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def title_of(template, params):
    t = TEMPLATES[template]
    p = dict(params or {})
    if "map" in p:
        p["map_name"] = p["map"].split("_")[-1].capitalize()
    return t["title"].format(**p) if p else t["title"]


def start(sid, template, params=None):
    if template not in TEMPLATES:
        raise ValueError("expérience inconnue")
    exps = load(sid)
    e = {"id": uuid.uuid4().hex[:8], "template": template, "params": params or {}, "title": title_of(template, params),
         "started": dt.datetime.now().isoformat(timespec="minutes"), "status": "active", "ended": None}
    exps.append(e)
    save(sid, exps)
    return e


def stop(sid, eid, status="stopped"):
    exps = load(sid)
    for e in exps:
        if e["id"] == eid:
            e["status"] = status
            e["ended"] = dt.datetime.now().isoformat(timespec="minutes")
    save(sid, exps)
    return exps


# ---------- per-match values ----------
def _mid_rows(mid, sid):
    f = os.path.join(config.OUT, "population", "midround", f"{mid}.parquet")
    if not os.path.exists(f):
        return None
    r = pd.read_parquet(f)
    r = r[r.steamid == sid]
    return r.iloc[0] if len(r) else None


def match_values(sid, m, st, template, params):
    """-> (value, weight) or (k, n) counts for proportion metrics, for one match."""
    metric = TEMPLATES[template]["metric"]
    o = st["overview"]
    rounds = max(st["rounds"], 1)
    if metric == "rating":
        return context.rating(o["kills"], o["deaths"], o["assists"], o["adr"], o["kast_pct"], rounds), 1
    if metric == "adr":
        return o["adr"], 1
    if metric == "traded_pct":
        d = o["trades"]["my_deaths"]
        return (100 * o["trades"]["my_deaths_traded"] / d, 1) if d else (None, 0)
    if metric == "nades_unused_pr":
        return sum(len(r["grenades_unused_at_death"]) for r in st["per_round"]) / rounds, 1
    if metric == "xhair":
        v = (st["aim"].get("crosshair_placement") or {}).get("median_error_deg")
        return (v, 1) if v is not None else (None, 0)
    if metric == "pistol_moving":
        from advice import PISTOLS
        sh = mv = 0.0
        for w, v in st["aim"]["by_weapon"].items():
            if w in PISTOLS and v.get("shots_while_moving_pct") is not None:
                sh += v["shots"]
                mv += v["shots"] * v["shots_while_moving_pct"] / 100
        return (100 * mv / sh, 1) if sh >= 5 else (None, 0)
    if metric == "open_win":
        w, l = o["opening_duels"]["won"], o["opening_duels"]["lost"]
        return (100 * w / (w + l), 1) if w + l else (None, 0)
    if metric in ("isolated_pr", "adv_throw", "rot_died", "rt_solo", "steps_alone_pr"):
        r = _mid_rows(m["id"], sid)
        if r is None:
            return None, 0
        g = lambda k: float(r.get(k)) if pd.notna(r.get(k)) else 0.0
        if metric == "isolated_pr":
            return g("isolated_deaths") / max(g("rounds"), 1), 1
        if metric == "steps_alone_pr":
            return g("steps_alone") / max(g("rounds"), 1), 1
        if metric == "adv_throw":
            return ("k", g("adv_throw"), g("adv_rounds"))
        if metric == "rot_died":
            return ("k", g("rot_died_way"), g("rot_done"))
        if metric == "rt_solo":
            return ("k", g("rt_solo_death"), g("rt_n"))
    if metric in ("weapon_duels", "weapon_adr"):
        w = params.get("alt") if template == "weapon_swap" and params.get("_phase") == "trial" else params.get("weapon")
        if metric == "weapon_duels":
            f = os.path.join(config.DEEP, str(m["id"]), "deaths_w.parquet")
            if not os.path.exists(f):
                return None, 0
            dw = pd.read_parquet(f)
            k = int(((dw.killer == sid) & (dw.killer_weapon_name == w)).sum())
            d = int(((dw.victim == sid) & (dw.victim_weapon == w)).sum())
            return ("k", k, k + d)
        f = os.path.join(config.DEEP, str(m["id"]), "loadout.parquet")
        if not os.path.exists(f):
            return None, 0
        L = pd.read_parquet(f)
        x = L[(L.steamid == sid) & (L.primary == w)]
        return (float(x.damage.mean()), len(x)) if len(x) else (None, 0)
    if metric == "zone_duels":
        if m["map"] != params.get("map"):
            return None, 0
        f = os.path.join(config.DEEP, str(m["id"]), "duels.parquet")
        if not os.path.exists(f):
            return None, 0
        D = pd.read_parquet(f)
        side = params.get("side")
        k = int(((D.killer == sid) & (D.killer_zone == params.get("zone")) & (D.killer_side == side)).sum())
        d = int(((D.victim == sid) & (D.victim_zone == params.get("zone")) & (D.victim_side == side)).sum())
        return ("k", k, k + d)
    if metric == "first_game":
        return (m.get("_first_rating"), 1) if m.get("_first_rating") is not None else (None, 0)
    return None, 0


def _summ(vals):
    props = [v for v in vals if isinstance(v, tuple) and len(v) == 3 and v[0] == "k"]
    if props:
        k = sum(v[1] for v in props)
        n = sum(v[2] for v in props)
        return {"kind": "prop", "k": k, "n": n, "value": round(100 * k / n, 1) if n else None, "games": len(props)}
    xs = [(v[0], v[1]) for v in vals if isinstance(v, tuple) and len(v) == 2 and v[0] is not None and v[1]]
    if not xs:
        return {"kind": "mean", "value": None, "n": 0, "games": 0}
    w = sum(b for _, b in xs)
    mean = sum(a * b for a, b in xs) / w
    sd = pd.Series([a for a, _ in xs]).std() if len(xs) > 1 else None
    return {"kind": "mean", "value": round(mean, 2), "n": len(xs), "sd": None if sd is None or math.isnan(sd) else float(sd), "games": len(xs)}


def evaluate(sid, e, hist=None, stats_by_id=None):
    """Baseline (15 matches before the start) vs trial (matches after the start)."""
    sid = int(sid)
    hist = hist if hist is not None else context.history(sid)
    stats_by_id = stats_by_id or {}
    tpl = TEMPLATES[e["template"]]
    t0 = dt.datetime.fromisoformat(e["started"])
    t1 = dt.datetime.fromisoformat(e["ended"]) if e.get("ended") else None
    # first game of each session, for the warm-up experiment
    prev_end = None
    for m in hist:
        m["_first_rating"] = m["perf"] if (prev_end is None or (m["start"] - prev_end).total_seconds() > context.SESSION_GAP_MIN * 60) else None
        prev_end = m["end"]
    before = [m for m in hist if m["start"] < t0 and m["source"] == "demo"][-15:]
    after = [m for m in hist if m["start"] >= t0 and (t1 is None or m["start"] <= t1) and m["source"] == "demo"]

    def vals(ms, phase):
        out = []
        for m in ms:
            st = stats_by_id.get(m["id"])
            if st is None:
                f = os.path.join(config.player_dir(sid), "matches", m["id"], "stats.json")
                if not os.path.exists(f):
                    continue
                st = json.load(open(f, encoding="utf-8"))
                stats_by_id[m["id"]] = st
            p = dict(e.get("params") or {}, _phase=phase)
            out.append(match_values(sid, m, st, e["template"], p))
        return out
    b, a = _summ(vals(before, "base")), _summ(vals(after, "trial"))
    label, unit, hib = METRICS[tpl["metric"]]
    need = tpl["min"]
    have = a["n"] if tpl["unit_n"] in ("duels", "rounds") else a["games"]
    verdict, z = "en cours", None
    if a["value"] is not None and b["value"] is not None:
        if a["kind"] == "prop" and b["kind"] == "prop" and a["n"] and b["n"]:
            p = (a["k"] + b["k"]) / (a["n"] + b["n"])
            se = math.sqrt(max(p * (1 - p), 1e-6) * (1 / a["n"] + 1 / b["n"])) * 100
            z = (a["value"] - b["value"]) / se if se else None
        elif a["kind"] == "mean" and b["kind"] == "mean" and a["n"] >= 2 and b["n"] >= 2:
            se = math.sqrt((a.get("sd") or 1) ** 2 / a["n"] + (b.get("sd") or 1) ** 2 / b["n"])
            z = (a["value"] - b["value"]) / se if se else None
    if have >= need and z is not None:
        good = z if hib else -z
        verdict = "ça marche" if good >= 1.64 else "ça dégrade" if good <= -1.64 else "pas d'effet net"
    elif have >= need:
        verdict = "pas assez de données de comparaison"
    return {**e, "category": tpl["cat"], "how": [h.format(**{**(e.get("params") or {}), "map_name": (e.get("params") or {}).get("map", "").split("_")[-1].capitalize()}) for h in tpl["how"]],
            "metric": label, "unit": unit, "higher_better": hib, "before": b, "after": a, "progress": [min(have, need), need, tpl["unit_n"]],
            "z": None if z is None else round(z, 2), "verdict": verdict}


def suggestions(sid, adv, mid_bench=None, weapons_info=None, ctx=None, cross=None):
    """Experiments worth running, from the player's own weak points."""
    S = []
    rid = [r["id"] for r in (adv or {}).get("rules", [])]

    def add(template, why, params=None, prio=5):
        S.append({"template": template, "params": params or {}, "title": title_of(template, params), "why": why,
                  "category": TEMPLATES[template]["cat"], "metric": METRICS[TEMPLATES[template]["metric"]][0], "prio": prio})
    for s in (weapons_info or {}).get("suggestions", []):
        if s["kind"] == "weapon_weak":
            alt = {"M4A1-S": "M4A4", "M4A4": "M4A1-S", "Galil AR": "FAMAS", "FAMAS": "Galil AR", "MP9": "MP5-SD", "MAC-10": "Galil AR",
                   "AWP": "M4A4", "Desert Eagle": "P250", "SSG 08": "Galil AR", "AK-47": "Galil AR", "MAG-7": "MP9", "Nova": "MP9"}.get(s["weapon"])
            if alt:
                add("weapon_swap", s["text"], {"weapon": s["weapon"], "alt": alt}, 8)
        elif s["kind"] == "weapon_strong":
            add("weapon_keep", s["text"], {"weapon": s["weapon"]}, 3)
    if "trade" in rid or "lastalive" in rid:
        add("trade_distance", "Tes morts sont rarement vengées : c'est la piste la plus rentable.", prio=9)
    if "nades" in rid:
        add("nades_40s", "Tu meurs souvent avec des grenades en poche.", prio=7)
    if "xhair" in rid:
        add("prefire", "Ton viseur est loin de la tête quand le duel commence.", prio=7)
    if "pistol" in rid:
        add("counter_strafe", "Beaucoup de tes tirs au pistolet partent en mouvement.", prio=6)
    if "open" in rid or "early" in rid:
        add("opening", "Tes premiers duels coûtent des rounds.", prio=6)
    MB = (mid_bench or {}).get("metrics", {})
    if (MB.get("adv_throw") or {}).get("percentile") is not None and MB["adv_throw"]["percentile"] <= 35:
        add("advantage", f"Tu rends l'avantage numérique plus souvent que {100 - MB['adv_throw']['percentile']:.0f} % des joueurs.", prio=8)
    if (MB.get("rot_died") or {}).get("percentile") is not None and MB["rot_died"]["percentile"] <= 35:
        add("rotation", "Tu meurs souvent pendant tes rotations.", prio=7)
    if (MB.get("rt_solo") or {}).get("percentile") is not None and MB["rt_solo"]["percentile"] <= 35:
        add("retake_group", "Tu meurs souvent seul en retake.", prio=7)
    if (MB.get("steps_alone") or {}).get("percentile") is not None and MB["steps_alone"]["percentile"] <= 40:
        add("silent", "Tu fais du bruit à portée d'ennemi quand tu es seul : la base de ton rôle de lurker.", prio=6)
    recs = (ctx or {}).get("recs", [])
    if any(r["kind"] in ("stop", "tilt") for r in recs) or (ctx and ctx["sessions"]["max_games"] >= 4):
        add("session_limit", "Tes sessions longues ou après défaites font baisser ta note.", prio=5)
    add("warmup", "Mesure l'effet d'un vrai échauffement sur ta première game.", prio=4)
    # positions the base wins in and the player rarely plays
    for m in (cross or {}).get("maps", [])[:3]:
        for side, Sd in m["sides"].items():
            pz = [z for z in Sd.get("pool_zones", []) if (z.get("win") or 0) >= 56 and z["k"] + z["d"] >= 12 and z["my_presence"] < 4
                  and "spawn" not in z["key"].lower() and z["t_med"] <= 45]
            if pz:
                z = pz[0]
                add("zone", f"Sur {m['map'].split('_')[-1].capitalize()} en {side}, les joueurs de la base gagnent {z['win']} % de leurs duels en {z['name']} et tu n'y vas presque jamais.",
                    {"map": m["map"], "side": side, "zone": z["key"], "zone_name": z["name"]}, 4)
                break
    seen, out = set(), []
    for s in sorted(S, key=lambda x: -x["prio"]):
        key = (s["template"], json.dumps(s["params"], sort_keys=True))
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out[:8]


def report(sid, adv=None, mid_bench=None, weapons_info=None, ctx=None, cross=None):
    hist = context.history(sid)
    cache = {}
    exps = [evaluate(sid, e, hist, cache) for e in load(sid)]
    active = {(e["template"], json.dumps({k: v for k, v in e["params"].items()}, sort_keys=True)) for e in exps if e["status"] == "active"}
    sug = [s for s in suggestions(sid, adv, mid_bench, weapons_info, ctx, cross) if (s["template"], json.dumps(s["params"], sort_keys=True)) not in active]
    return {"experiments": exps, "suggested": sug, "templates": {k: {"cat": v["cat"], "title": v["title"]} for k, v in TEMPLATES.items()}}
