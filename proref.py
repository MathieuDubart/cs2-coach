"""Compare a player with the pro reference (HLTV demos): similar playstyle, same archetype, same zones per map/side."""
import json
import os

import numpy as np
import pandas as pd

import archetype
import config
from map_analysis import humanize

PRO = os.path.join(config.OUT, "pro")
DEEP_PRO = os.path.join(config.OUT, "deep_pro")
STYLE_PRO = os.path.join(config.OUT, "style_pro")
DIMS = ["awp_share", "iso_T", "iso_CT", "move_share", "hold_share", "open_rate_T", "open_win", "trade_rate",
        "late_share", "first_duel_t", "util_pr", "ct_site", "hs_share", "duel_len_won"]  # no blind data in pro demos
PHRASE = {  # dim -> (high, low)
    "awp_share": ("plays the AWP", "barely plays the AWP"),
    "iso_T": ("plays far from the team on attack", "stays grouped on attack"),
    "iso_CT": ("defends alone, far from teammates", "defends grouped"),
    "move_share": ("engages while moving", "rarely engages while moving"),
    "hold_share": ("plays still, waits for the enemy", "rarely plays still"),
    "open_rate_T": ("opens rounds on attack", "leaves the opening to others"),
    "trade_rate": ("trades a lot", "trades little"),
    "late_share": ("gets kills late in the round", "gets kills early"),
    "first_duel_t": ("takes their first duel late", "takes their first duel early"),
    "util_pr": ("uses a lot of grenades", "uses few grenades"),
    "ct_site": ("holds sites on defense", "plays off-site on defense"),
    "hs_share": ("aims for the head", ""),
}
_C = {}


def load():
    if "pro" in _C:
        return _C["pro"]
    fs = [os.path.join(STYLE_PRO, f) for f in os.listdir(STYLE_PRO)] if os.path.exists(STYLE_PRO) else []
    if not fs:
        _C["pro"] = None
        return None
    df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    reg = json.load(open(os.path.join(PRO, "matches.json"), encoding="utf-8")) if os.path.exists(os.path.join(PRO, "matches.json")) else {}
    team, event = {}, {}
    for m in reg.values():
        for d in m.get("demos", []):
            for sid, t in (d.get("teams") or {}).items():
                team[sid] = t
            event[d["id"]] = f"{' vs '.join(m.get('teams', []))} · {m.get('event') or ''} · {m.get('date') or ''}"
    agg = archetype.aggregate(df)
    agg = agg[agg.rounds >= 30].copy()
    _, _, ref, T, cols = archetype.reference()
    Tpro = archetype.pct_table(agg, cols)  # a pro's role is judged against other pros
    P = {}
    roles = {}
    for sid, r in agg.iterrows():
        P[sid] = {c: archetype.pct(T[c], r[c]) for c in cols}  # pub scale: comparable with the player
        pp = {c: archetype.pct(Tpro[c], r[c]) for c in cols}
        pp["blind_pr"] = None  # tournament demos do not record who got flashed
        roles[sid] = archetype.role_of(r.to_dict(), pp, archetype.damp_awp(archetype.scores(pp), r["awp_share"]))
    agg["role"] = pd.Series(roles)
    import pro_directory
    D = pro_directory.directory()
    # identity: the directory (current rosters) wins over the in-demo clan tag
    agg["team"] = [D[s]["team"] if s in D and D[s]["current"] else (team.get(s) or (D[s]["team"] if s in D else "")) for s in agg.index]
    agg["handle"] = [D[s]["handle"] if s in D else agg.loc[s, "name"] for s in agg.index]
    agg["real_name"] = [D[s]["name"] if s in D else None for s in agg.index]
    agg["prole"] = [D[s]["role"] if s in D else None for s in agg.index]
    agg["hltv"] = [D[s]["hltv"] if s in D else f"https://www.hltv.org/search?query={agg.loc[s, 'name']}" for s in agg.index]
    # zone presence per pro, map and side
    zones = {}
    for pid in df.match.unique():
        d = os.path.join(DEEP_PRO, pid)
        if not os.path.exists(os.path.join(d, "samples.parquet")):
            continue
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        sm = pd.read_parquet(os.path.join(d, "samples.parquet"), columns=["steamid", "side", "t", "zone"])
        sm = sm[(sm.t >= 5) & (sm.zone != "?")]
        for (sid, side), g in sm.groupby(["steamid", "side"]):
            zones.setdefault(str(sid), {}).setdefault(meta["map"], {}).setdefault(side, []).append(g.zone)
    zp = {s: {m: {sd: pd.concat(v).value_counts(normalize=True).to_dict() for sd, v in ss.items()} for m, ss in ms.items()}
          for s, ms in zones.items()}
    _C["pro"] = (agg, P, zp, event, len(df.match.unique()))
    return _C["pro"]


def player_zones(steamid):
    out = {}
    for mid in os.listdir(config.DEEP):
        f = os.path.join(config.DEEP, mid, "samples.parquet")
        if not os.path.exists(f):
            continue
        sm = pd.read_parquet(f, columns=["steamid", "side", "t", "zone"])
        sm = sm[(sm.steamid == int(steamid)) & (sm.t >= 5) & (sm.zone != "?")]
        if not len(sm):
            continue
        meta = json.load(open(os.path.join(config.DEEP, mid, "meta.json"), encoding="utf-8"))
        for side, g in sm.groupby("side"):
            out.setdefault(meta["map"], {}).setdefault(side, []).append(g.zone)
    return {m: {sd: pd.concat(v).value_counts(normalize=True).to_dict() for sd, v in ss.items()} for m, ss in out.items()}


def shared_traits(pu, pp):
    out = []
    for d, (hi, lo) in PHRASE.items():
        a, b = pu.get(d), pp.get(d)
        if a is None or b is None or abs(a - b) > 15:
            continue
        if a >= 65 and b >= 65 and hi:
            out.append(hi)
        elif a <= 35 and b <= 35 and lo:
            out.append(lo)
    return out[:4]


def for_player(steamid):
    data = load()
    if not data:
        return None
    agg, P, zp, event, n_maps = data
    df, pagg, ref, T, cols = archetype.reference()
    sid = str(steamid)
    if sid not in pagg.index or pagg.loc[sid].rounds < 15:
        return None
    r = pagg.loc[sid]
    pu = {c: archetype.pct(T[c], r[c]) for c in cols}
    my_role = archetype.role_of(r.to_dict(), pu, archetype.damp_awp(archetype.scores(pu), r["awp_share"]))
    rows = []
    for psid, pr in agg.iterrows():
        pp = P[psid]
        diffs = [abs(pu[d] - pp[d]) for d in DIMS if pu.get(d) is not None and pp.get(d) is not None]
        if len(diffs) < 8:
            continue
        rows.append({"steamid": psid, "name": pr["handle"], "team": pr["team"], "role": pr["role"], "igl": pr["prole"] == "igl",
                     "role_name": archetype.ROLES[pr["role"]]["name"], "similarity": round(100 - float(np.mean(diffs))),
                     "rounds": int(pr.rounds), "traits": shared_traits(pu, pp),
                     "hltv": pr["hltv"]})
    rows.sort(key=lambda x: -x["similarity"])
    same_role = [x for x in rows if x["role"] == my_role][:6]
    # same zones on the player's maps
    mz = player_zones(sid)
    maps = {}
    for m, sides in mz.items():
        for side, dist in sides.items():
            cands = []
            for psid, pmaps in zp.items():
                pd_ = (pmaps.get(m) or {}).get(side)
                if not pd_ or psid not in agg.index:
                    continue
                overlap = sum(min(v, pd_.get(z, 0)) for z, v in dist.items())
                top = sorted(pd_.items(), key=lambda x: -x[1])[:3]
                cands.append({"steamid": psid, "name": agg.loc[psid, "handle"], "team": agg.loc[psid, "team"], "overlap": round(overlap * 100),
                              "zones": [{"zone": humanize(z, m), "share": round(v * 100)} for z, v in top]})
            if cands:
                cands.sort(key=lambda x: -x["overlap"])
                my_top = sorted(dist.items(), key=lambda x: -x[1])[:3]
                maps.setdefault(m, {})[side] = {"pros": cands[:4], "mine": [{"zone": humanize(z, m), "share": round(v * 100)} for z, v in my_top]}
    return {"similar": rows[:6], "same_role": same_role, "role": my_role, "role_name": archetype.ROLES[my_role]["name"],
            "maps": maps, "n_pros": int(len(agg)), "n_maps": n_maps,
            "note": "Official demos of recent pro matches (HLTV). Similarity = average closeness over 15 style indicators, in base percentiles."}


TRAIT_TXT = [("move_share", 70, "Agressif", "engages while moving"), ("hold_share", 70, "Patient", "waits for the enemy standing still"),
             ("iso_T", 70, "Solitaire", "plays far from the team on attack"), ("iso_T", -30, "Team player", "stays grouped on attack"),
             ("duel_len_won", -30, "Fast reflexes", "finishes duels very fast"), ("trade_rate", 70, "Trader", "often avenges teammates"),
             ("hs_share", 75, "Headshot machine", "lots of headshot kills"), ("util_pr", 75, "Utilitaires", "throws a lot of grenades"),
             ("open_rate_T", 75, "Ouvreur", "takes the opening duels on attack"), ("late_share", 75, "End of round", "gets kills late")]


def pro_profiles():
    """One card per pro: identity, archetype, traits, weapons, key stats, zones per map/side."""
    data = load()
    if not data:
        return []
    agg, P, zp, event, n_maps = data
    df = pd.concat([pd.read_parquet(os.path.join(STYLE_PRO, f)) for f in os.listdir(STYLE_PRO)], ignore_index=True)
    out = []
    for sid, r in agg.iterrows():
        p = P[sid]
        traits = []
        for m, thr, label, txt in TRAIT_TXT:
            v = p.get(m)
            if v is None:
                continue
            if (thr > 0 and v >= thr) or (thr < 0 and v <= -thr):
                traits.append({"label": label, "text": txt})
        shares = {"AWP": r.awp_share, "rifles": r.rifle_share, "SMG": r.smg_share, "shotguns": r.shotgun_share,
                  "pistols": (r.pistol_share or 0) + (r.deagle_share or 0)}
        zones = {}
        for m, sides in zp.get(sid, {}).items():
            zones[m] = {sd: [{"zone": humanize(z, m), "share": round(v * 100)} for z, v in sorted(d.items(), key=lambda x: -x[1])[:5]]
                        for sd, d in sides.items()}
        f = lambda v, k=1: None if v is None or v != v else (round(float(v) * k) if k == 100 else round(float(v), 2))
        out.append({"steamid": sid, "handle": r.handle, "real_name": r.real_name, "team": r.team, "prole": r.prole, "hltv": r.hltv,
                    "role": r.role, "role_name": archetype.ROLES[r.role]["name"], "icon": archetype.ROLES[r.role]["icon"],
                    "traits": traits[:5], "rounds": int(r.rounds), "maps": int(r.matches),
                    "weapons": {k: round(float(v or 0) * 100) for k, v in shares.items()},
                    "top_weapons": [{"weapon": archetype.WEAPON_FR.get(w, w), "kills": n} for w, n in archetype.top_weapons(df, sid)],
                    "stats": {"kpr": f(r.kpr), "hs": f(r.hs_share, 100), "open_win": f(r.open_win, 100), "trade_rate": f(r.trade_rate),
                              "iso_T": f(r.iso_T), "util_pr": f(r.util_pr), "late_share": f(r.late_share, 100), "awp_share": f(r.awp_share, 100),
                              "first_duel_t": f(r.first_duel_t)},
                    "zones": zones})
    import pro_directory
    top = list(pro_directory.CURRENT)
    out.sort(key=lambda x: (top.index(x["team"]) if x["team"] in top else len(top), x["team"] or "zzz", x["handle"].lower()))
    return out
