"""Coach notes per map and side, for any player: the few things to change or to keep, written from the cross-match
analysis (zones, deaths, duels on the move, the best spots of the other players, first contacts) and the grenades
that work from the player's zones.

Writes <player>/cross_notes.json: {map: {side: {title, plan: [html], kinds: [avoid|good|tip]}}}.
"""
import json
import os

import config

SIDE_FR = {"T": "attaque", "CT": "défense"}
SITE = {"BombsiteA": "A", "BombsiteB": "B"}


def map_name(mp):
    n = mp.split("_", 1)[-1]
    return n[:1].upper() + n[1:]


def _p(n, one, many):
    return f"{n} {one if abs(n) < 2 else many}"   # French: 0 and 1 are singular


def nm(name):
    """Bombsite A -> site A."""
    return f"site {name[-1]}" if isinstance(name, str) and name.startswith("Bombsite ") else name


def cap(name):
    n = nm(name)
    return n[:1].upper() + n[1:] if n else n


def at(name):
    """'sur le site A', 'en Outside'."""
    return f"sur le site {name[-1]}" if isinstance(name, str) and name.startswith("Bombsite ") else f"en {name}"


def _nade_to(nd, zone_key, to_name, types=("smoke", "flash", "molotov")):
    """A grenade that works from this zone toward another one (base), if there is one."""
    for t in types:
        for x in ((nd or {}).get("types", {}).get(t) or {}).get("picks", []):
            if x.get("from_key") == zone_key and x.get("to") == to_name:
                return t, x
    return None


def _nade_from(nd, zone_key, types=("smoke", "molotov", "flash", "he")):
    for t in types:
        for x in ((nd or {}).get("types", {}).get(t) or {}).get("picks", []):
            if x.get("from_key") == zone_key:
                return t, x
    return None


def _nade_txt(t, x, side):
    name = {"flash": "La flash", "smoke": "La smoke", "he": "La HE", "molotov": "L'incendiaire" if side == "CT" else "La molotov"}[t]
    if t == "flash":
        eff = f"elle aveugle un ennemi {x.get('blind')} % du temps"
    elif t == "he":
        eff = f"{x.get('dmg')} dégâts en moyenne"
    elif t == "molotov":
        eff = f"lancée dans {round(x.get('per100') or 0)} rounds sur 100"
    else:
        eff = f"lancée dans {round(x.get('per100') or 0)} rounds sur 100" + \
              (f", {x['win']} % de rounds gagnés quand elle est posée" if x.get("win") is not None else "")
    return f"{name} {nm(x['from'])} → {nm(x['to'])}, vers {x['timer']} : {eff} (base)."


def side_notes(mp, side, S, nd, regions, n_matches):
    zones = [z for z in S.get("zones", []) if z.get("key") and "spawn" not in z["key"].lower()]
    best = S.get("best_spots", [])
    pool = S.get("pool_zones", [])
    out = []   # (priority, kind, html)
    used = set()
    cited = set()   # grenades already in a note (type, from, to)
    main = [z for z in zones if (z.get("presence") or 0) >= 5]
    for z in main:
        k, d, n = z["k"], z["d"], z["k"] + z["d"]
        ow, w = z.get("others_win"), z.get("win")
        bad = z.get("verdict") == "avoid" or (n >= 3 and k == 0) or (n >= 4 and w is not None and w <= 35) or \
            (n >= 6 and w is not None and w <= 40 and (ow is None or w <= ow - 8))
        good = z.get("verdict") == "exploit" or (n >= 4 and w is not None and w >= 60 and (ow is None or w >= ow + 5))
        spot = next((b for b in best if b.get("zone") == z["name"]), None)
        if bad:
            kf = (z.get("killed_from") or [{}])[0]
            kz, kn = kf.get("zone"), kf.get("n", 0)
            moving = (z.get("my_speed_med") or 0) >= 90 and (z.get("others_speed_med") is None or z["my_speed_med"] >= z["others_speed_med"] + 15)
            same = kz == z["name"]   # killed from the very zone: close fights there
            nade = _nade_to(nd, z["key"], kz) if kz and not same and kn >= max(2, d / 2) else None
            # a better spot of the other players in a zone of the same area, where you already do at least as well
            # (not a bomb site for the attackers: they only get there at the end)
            alt = None
            for b in best:
                az = next((x for x in zones if x["name"] == b.get("zone")), None)
                if not az or az["key"] == z["key"] or not regions.get(az["key"]) or regions.get(az["key"]) != regions.get(z["key"]):
                    continue
                if b["k"] < 2 * max(1, b["d"]) or az["k"] + az["d"] < 2 or az["k"] < az["d"] or (side == "T" and az["key"] in SITE):
                    continue
                alt = (b, az)
                break
            if not alt:
                for az in zones:
                    if az["key"] != z["key"] and regions.get(az["key"]) and regions.get(az["key"]) == regions.get(z["key"]) \
                            and az["k"] + az["d"] >= 3 and az["k"] > az["d"] and not (side == "T" and az["key"] in SITE):
                        alt = (None, az)
                        break
            txt = f"Tu y passes {round(z['presence'])} % de ton temps pour {_p(k, 'kill', 'kills')} et {_p(d, 'mort', 'morts')}"
            src = f"le {nm(kz)}" if str(kz).startswith("Bombsite") else kz
            txt += f", dont {kn} tué{'s' if kn > 1 else ''} depuis {src}." if kz and kn >= 2 else "."
            if moving and spot and (spot.get("hold_pct") or 0) >= 35:
                head, kind = "change ta façon de le jouer", "avoid"
                txt += f" Tu y prends tes duels en mouvement ({z['my_speed_med']} u/s en médiane)."
                if ow is not None:
                    txt += f" Les autres joueurs y gagnent {ow} % de leurs duels, et le spot qui marche le mieux ({spot['k']} kills, {spot['d']} morts) est un angle tenu, vers {spot['t_med']} s de round."
            elif alt:
                b, az = alt
                head, kind = (f"recule {at(az['name'])}" if side == "CT" else f"passe plutôt {at(az['name'])}"), "avoid"
                where = at(az["name"])
                txt += f" {where[:1].upper() + where[1:]}, tu fais {az['k']}-{az['d']}"
                if b:
                    held = ", tenu posé" if (b.get("hold_pct") or 0) >= 40 else ""
                    txt += f", et le meilleur spot des autres joueurs y est : {b['k']} kills pour {b['d']} morts{held}."
                else:
                    txt += "."
                if same and kn >= 2:
                    txt += f" {kn} de tes morts arrivent au corps à corps, dans la zone même."
            elif nade:
                t, x = nade
                verb = {"smoke": f"smoke {nm(kz)}", "flash": f"flashe {nm(kz)}", "molotov": f"molotov sur {nm(kz)}"}[t]
                goal = "de t'installer" if side == "CT" else "d'avancer"
                head, kind = f"{verb} avant {goal}", "tip"
                txt += " " + _nade_txt(t, x, side)
                cited.add((t, x["from"], x["to"]))
            elif same and kn >= 2:
                head, kind = "tiens-le de plus loin", "avoid"
                txt += f" Ce sont des duels au corps à corps, dans la zone même : tiens un angle en retrait, que l'adversaire doit venir chercher."
            elif ow is not None and ow <= 45:
                head, kind = "évite-le", "avoid"
                txt += f" Les autres joueurs n'y gagnent que {ow} % de leurs duels."
            else:
                head, kind = "ne le joue plus seul", "avoid"
                txt += f" Les autres y gagnent {ow if ow is not None else '—'} % : joue-le avec un coéquipier à portée de trade, ou tiens l'angle au lieu de le prendre."
            out.append((z["presence"] * (d - k + 1), kind, f"<b>{cap(z['name'])} : {head}.</b> {txt}"))
            used.add(z["key"])
        elif good:
            txt = f"Tu y fais {_p(k, 'kill', 'kills')} pour {_p(d, 'mort', 'morts')} ({w} %)"
            txt += f", alors que les autres joueurs n'y gagnent que {ow} %." if ow is not None and ow < w else "."
            site = SITE.get(z["key"])
            if site and side == "T":
                txt += f" Plante {site} et joue l'après-plant."
            elif site:
                txt += " Garde-le comme position de base."
            nf = _nade_from(nd, z["key"])
            if nf and (nf[0], nf[1]["from"], nf[1]["to"]) not in cited:
                txt += " " + _nade_txt(nf[0], nf[1], side)
                cited.add((nf[0], nf[1]["from"], nf[1]["to"]))
            out.append((z["presence"] * (k - d + 2) / 2, "good", f"<b>{cap(z['name'])} : ton point fort.</b> {txt}"))
            used.add(z["key"])
    # a zone you play a lot, neither good nor bad, where your deaths come from one place a grenade can deal with
    for z in main:
        if z["key"] in used or (z.get("presence") or 0) < 10:
            continue
        kf = (z.get("killed_from") or [{}])[0]
        kz, kn = kf.get("zone"), kf.get("n", 0)
        if not kz or kz == z["name"] or kn < 2 or kn < z["d"] / 2:
            continue
        nade = _nade_to(nd, z["key"], kz)
        if not nade or (nade[0], nade[1]["from"], nade[1]["to"]) in cited:
            continue
        t, x = nade
        verb = {"smoke": f"smoke {nm(kz)}", "flash": f"flashe {nm(kz)}", "molotov": f"molotov sur {nm(kz)}"}[t]
        goal = "de t'installer" if side == "CT" else "d'avancer"
        src = f"le {nm(kz)}" if str(kz).startswith("Bombsite") else kz
        out.append((z["presence"] * 0.8, "tip", f"<b>{cap(z['name'])} : {verb} avant {goal}.</b> Tu y passes {round(z['presence'])} % de ton temps "
                                                f"({z['k']}-{z['d']}), et tu es tué {kn} fois depuis {src}. {_nade_txt(t, x, side)}"))
        cited.add((t, x["from"], x["to"]))
        used.add(z["key"])
    # a zone where everybody dies, and where you still go
    for z in zones:
        on, od = z.get("others_k") or 0, z.get("others_d") or 0
        if z["key"] in used or on + od < 15 or (z.get("others_win") or 100) > 35 or (z.get("presence") or 0) < 2:
            continue
        out.append((z["presence"] * 1.5 + 4, "avoid", f"<b>{cap(z['name'])} : évite-le.</b> Les joueurs de la base y perdent la plupart de leurs duels : "
                                                     f"{on} kills pour {od} morts ({z['others_win']} %). Toi : {z['k']}-{z['d']}."))
        used.add(z["key"])
    # zones you rarely play but win in
    more = [z for z in zones if z["key"] not in used and (z.get("presence") or 0) < 8 and z["k"] + z["d"] >= 3 and (z.get("win") or 0) >= 60]
    if more:
        more = sorted(more, key=lambda z: -(z["k"] - z["d"]))[:2]
        held = all((z.get("my_speed_med") or 999) < 60 for z in more)
        names = " et ".join(f"{nm(z['name'])} ({z['k']}-{z['d']})" for z in more)
        pron = "les" if len(more) > 1 else "le"
        how = ", en tenant l'angle" if held else ""
        pres = max(1, round(sum(z.get("presence") or 0 for z in more)))
        out.append((6, "good", f"<b>{names[:1].upper() + names[1:]} : joue-{pron} plus souvent.</b> Tu y gagnes plus de duels que tu n'en perds{how}, "
                              f"mais tu n'y passes que {pres} % de ton temps."))
    # the opening grenade from your main zone
    if main:
        z0 = main[0]
        first = None
        for t in (("molotov", "smoke") if side == "CT" else ("smoke", "flash")):
            for x in ((nd or {}).get("types", {}).get(t) or {}).get("picks", []):
                if x.get("from_key") in {z["key"] for z in main} and x.get("usual") in ("debut", "prise") and (t, x["from"], x["to"]) not in cited:
                    first = (t, x)
                    break
            if first:
                break
        if first:
            t, x = first
            name = {"smoke": "ta smoke", "molotov": "ton incendiaire" if side == "CT" else "ta molotov", "flash": "ta flash"}[t]
            txt = _nade_txt(t, x, side)
            ec = next((z.get("early_contact_s") for z in main if z["name"] == x["from"] and z.get("early_contact_s")), z0.get("early_contact_s"))
            if ec:
                txt += f" Le premier contact {at(x['from'])} arrive vers {round(ec)} s."
            head = f"Ouvre le round avec {name} vers {nm(x['to'])}" if side == "CT" else f"Avant d'entrer, {name} vers {nm(x['to'])}"
            out.append((5, "tip", f"<b>{head}.</b> {txt}"))
    # a position that pays off for everybody on this side and that you never play
    tries = [z for z in pool if (z.get("win") or 0) >= 60 and z["k"] + z["d"] >= 15 and (z.get("my_presence") or 0) < 1
             and (z.get("others_presence") or 0) >= 1 and "spawn" not in str(z.get("key", "")).lower()]
    if tries:
        z = max(tries, key=lambda z: z["k"] - z["d"])
        how = ", surtout en tenant l'angle" if (z.get("hold_pct") or 0) >= 40 else ""
        out.append((3, "tip", f"<b>{cap(z['name'])} : à essayer.</b> Les joueurs de la base y gagnent {z['win']} % de leurs duels ({z['k']}-{z['d']}){how}, "
                              f"vers {z['t_med']} s de round. Tu n'y joues presque jamais."))
    out.sort(key=lambda b: -b[0])
    out = out[:5]
    if not out:
        return None
    title = f"{map_name(mp)} en {side} ({SIDE_FR[side]})" + (" · 1 seul match ici : à confirmer" if n_matches == 1 else f" · {n_matches} matchs")
    return {"title": title, "plan": [b[2] for b in out], "kinds": [b[1] for b in out], "auto": True}


def build(sid, cross=None, plan=None):
    pdir = config.player_dir(sid)
    if cross is None:
        f = os.path.join(pdir, "cross.json")
        cross = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None
    if not cross:
        return {}
    nd_all = ((plan or {}).get("nades") or {}).get("maps", {})
    try:
        import team
        meta = team.map_meta()
    except Exception:
        meta = {}
    res = {}
    for m in cross.get("maps", []):
        mp = m["map"]
        if not mp.startswith("de_"):
            continue
        regions = (meta.get(mp) or {}).get("regions", {})
        for side, S in (m.get("sides") or {}).items():
            n = side_notes(mp, side, S, (nd_all.get(mp) or {}).get(side), regions, m.get("matches") or 0)
            if n:
                res.setdefault(mp, {})[side] = n
    return res


def write(sid, cross=None, plan=None):
    notes = build(sid, cross, plan)
    json.dump(notes, open(os.path.join(config.player_dir(sid), "cross_notes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return notes
