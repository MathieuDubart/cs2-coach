"""Coach notes per map and side, for any player: the few things to change or to keep, written from the cross-match
analysis (zones, deaths, duels on the move, the best spots of the other players, first contacts) and the grenades
that work from the player's zones.

Writes <player>/cross_notes.json: {map: {side: {title, plan: [html], kinds: [avoid|good|tip]}}}.
"""
import json
import os

import config

SIDE_FR = {"T": "attack", "CT": "defense"}
SITE = {"BombsiteA": "A", "BombsiteB": "B"}


def map_name(mp):
    n = mp.split("_", 1)[-1]
    return n[:1].upper() + n[1:]


def _p(n, one, many):
    return f"{n} {one if abs(n) == 1 else many}"


def _site(name):
    """'A' for the A bomb site, whatever its name ('A Site' callout, 'Bombsite A' from older analyses)."""
    if isinstance(name, str) and (name in ("A Site", "B Site") or name in ("Bombsite A", "Bombsite B")):
        return "A" if "A" in name.replace("Bombsite", "") else "B"
    return None


def nm(name):
    """A Site -> A site (in a sentence)."""
    return f"{_site(name)} site" if _site(name) else name


def cap(name):
    n = nm(name)
    return n[:1].upper() + n[1:] if n else n


def at(name):
    """'on A site', 'at Outside'."""
    return f"on {_site(name)} site" if _site(name) else f"at {name}"


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
    name = {"flash": "The flash", "smoke": "The smoke", "he": "The HE", "molotov": "The incendiary" if side == "CT" else "The molotov"}[t]
    if t == "flash":
        eff = f"it flashes an enemy {x.get('blind')}% of the time"
    elif t == "he":
        eff = f"{x.get('dmg')} damage on average"
    elif t == "molotov":
        eff = f"thrown in {round(x.get('per100') or 0)} rounds out of 100"
    else:
        eff = f"thrown in {round(x.get('per100') or 0)} rounds out of 100" + \
              (f", {x['win']}% of rounds won when it's used" if x.get("win") is not None else "")
    return f"{name} {nm(x['from'])} → {nm(x['to'])}, around {x['timer']}: {eff} (base)."


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
            txt = f"You spend {round(z['presence'])}% of your time there for {_p(k, 'kill', 'kills')} and {_p(d, 'death', 'deaths')}"
            src = nm(kz)
            txt += f", {kn} of them from {src}." if kz and kn >= 2 else "."
            if moving and spot and (spot.get("hold_pct") or 0) >= 35:
                head, kind = "change how you play it", "avoid"
                txt += f" You take your duels there while moving ({z['my_speed_med']} u/s median)."
                if ow is not None:
                    txt += f" Other players win {ow}% of their duels there, and the best spot ({_p(spot['k'], 'kill', 'kills')}, {_p(spot['d'], 'death', 'deaths')}) is a held angle, around {spot['t_med']} s into the round."
            elif alt:
                b, az = alt
                head, kind = (f"fall back to {nm(az['name'])}" if side == "CT" else f"go through {nm(az['name'])} instead"), "avoid"
                where = at(az["name"])
                txt += f" {where[:1].upper() + where[1:]}, you go {az['k']}-{az['d']}"
                if b:
                    held = ", held still" if (b.get("hold_pct") or 0) >= 40 else ""
                    txt += f", and the other players' best spot is there: {_p(b['k'], 'kill', 'kills')} for {_p(b['d'], 'death', 'deaths')}{held}."
                else:
                    txt += "."
                if same and kn >= 2:
                    txt += f" {kn} of your deaths are close-range fights inside the zone itself."
            elif nade:
                t, x = nade
                verb = {"smoke": f"smoke {nm(kz)}", "flash": f"flash {nm(kz)}", "molotov": f"molotov {nm(kz)}"}[t]
                goal = "setting up" if side == "CT" else "pushing"
                head, kind = f"{verb} before {goal}", "tip"
                txt += " " + _nade_txt(t, x, side)
                cited.add((t, x["from"], x["to"]))
            elif same and kn >= 2:
                head, kind = "hold it from further back", "avoid"
                txt += f" These are close-range duels inside the zone itself: hold an angle further back that the enemy has to come and take."
            elif ow is not None and ow <= 45:
                head, kind = "avoid it", "avoid"
                txt += f" Other players only win {ow}% of their duels there."
            else:
                head, kind = "stop playing it alone", "avoid"
                txt += f" Others win {ow if ow is not None else '—'}% there: play it with a teammate within trade distance, or hold the angle instead of taking it."
            out.append((z["presence"] * (d - k + 1), kind, f"<b>{cap(z['name'])}: {head}.</b> {txt}"))
            used.add(z["key"])
        elif good:
            txt = f"You go {_p(k, 'kill', 'kills')} for {_p(d, 'death', 'deaths')} there ({w}%)"
            txt += f", while other players only win {ow}% there." if ow is not None and ow < w else "."
            site = SITE.get(z["key"])
            if site and side == "T":
                txt += f" Plant {site} and play the post-plant."
            elif site:
                txt += " Keep it as your default position."
            nf = _nade_from(nd, z["key"])
            if nf and (nf[0], nf[1]["from"], nf[1]["to"]) not in cited:
                txt += " " + _nade_txt(nf[0], nf[1], side)
                cited.add((nf[0], nf[1]["from"], nf[1]["to"]))
            out.append((z["presence"] * (k - d + 2) / 2, "good", f"<b>{cap(z['name'])}: your strong spot.</b> {txt}"))
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
        verb = {"smoke": f"smoke {nm(kz)}", "flash": f"flash {nm(kz)}", "molotov": f"molotov {nm(kz)}"}[t]
        goal = "setting up" if side == "CT" else "pushing"
        src = nm(kz)
        out.append((z["presence"] * 0.8, "tip", f"<b>{cap(z['name'])}: {verb} before {goal}.</b> You spend {round(z['presence'])}% of your time there "
                                                f"({z['k']}-{z['d']}), and you get killed {kn} times from {src}. {_nade_txt(t, x, side)}"))
        cited.add((t, x["from"], x["to"]))
        used.add(z["key"])
    # a zone where everybody dies, and where you still go
    for z in zones:
        on, od = z.get("others_k") or 0, z.get("others_d") or 0
        if z["key"] in used or on + od < 15 or (z.get("others_win") or 100) > 35 or (z.get("presence") or 0) < 2:
            continue
        out.append((z["presence"] * 1.5 + 4, "avoid", f"<b>{cap(z['name'])}: avoid it.</b> Players in the base lose most of their duels there: "
                                                     f"{_p(on, 'kill', 'kills')} for {_p(od, 'death', 'deaths')} ({z['others_win']}%). You: {z['k']}-{z['d']}."))
        used.add(z["key"])
    # zones you rarely play but win in
    more = [z for z in zones if z["key"] not in used and (z.get("presence") or 0) < 8 and z["k"] + z["d"] >= 3 and (z.get("win") or 0) >= 60]
    if more:
        more = sorted(more, key=lambda z: -(z["k"] - z["d"]))[:2]
        held = all((z.get("my_speed_med") or 999) < 60 for z in more)
        names = " and ".join(f"{nm(z['name'])} ({z['k']}-{z['d']})" for z in more)
        pron = "them" if len(more) > 1 else "it"
        how = ", holding the angle" if held else ""
        pres = max(1, round(sum(z.get("presence") or 0 for z in more)))
        out.append((6, "good", f"<b>{names[:1].upper() + names[1:]}: play {pron} more often.</b> You win more duels than you lose there{how}, "
                              f"but you only spend {pres}% of your time there."))
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
            name = {"smoke": "your smoke", "molotov": "your incendiary" if side == "CT" else "your molotov", "flash": "your flash"}[t]
            txt = _nade_txt(t, x, side)
            ec = next((z.get("early_contact_s") for z in main if z["name"] == x["from"] and z.get("early_contact_s")), z0.get("early_contact_s"))
            if ec:
                txt += f" The first contact {at(x['from'])} comes around {round(ec)} s."
            head = f"Open the round with {name} toward {nm(x['to'])}" if side == "CT" else f"Before going in, {name} toward {nm(x['to'])}"
            out.append((5, "tip", f"<b>{head}.</b> {txt}"))
    # a position that pays off for everybody on this side and that you never play
    tries = [z for z in pool if (z.get("win") or 0) >= 60 and z["k"] + z["d"] >= 15 and (z.get("my_presence") or 0) < 1
             and (z.get("others_presence") or 0) >= 1 and "spawn" not in str(z.get("key", "")).lower()]
    if tries:
        z = max(tries, key=lambda z: z["k"] - z["d"])
        how = ", mostly holding the angle" if (z.get("hold_pct") or 0) >= 40 else ""
        out.append((3, "tip", f"<b>{cap(z['name'])}: worth a try.</b> Players in the base win {z['win']}% of their duels there ({z['k']}-{z['d']}){how}, "
                              f"around {z['t_med']} s into the round. You almost never play there."))
    out.sort(key=lambda b: -b[0])
    out = out[:5]
    if not out:
        return None
    title = f"{map_name(mp)} as {side} ({SIDE_FR[side]})" + (" · only 1 match here: to be confirmed" if n_matches == 1 else f" · {n_matches} matches")
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
