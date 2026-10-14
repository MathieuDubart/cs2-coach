"""Coach notes per map and side, for any player: the few things to change or to keep, written from the cross-match
analysis (zones, deaths, duels on the move, the best spots of the other players, first contacts) and the grenades
that work from the player's zones.

Writes <player>/cross_notes.json: {map: {side: {title, plan: [html], kinds: [avoid|good|tip]}}}.
"""
from wily.insights.nades import _timer  # the game clock (1:55 at the start of the round)
import json
import os

from wily.core import config
from wily.core.i18n import tr, trn

SIDE_FR = {"T": "attack", "CT": "defense"}
SITE = {"BombsiteA": "A", "BombsiteB": "B"}


def map_name(mp):
    n = mp.split("_", 1)[-1]
    return n[:1].upper() + n[1:]


def _kills(n):
    return trn(n, "{n} kill", "{n} kills")


def _deaths(n):
    return trn(n, "{n} death", "{n} deaths")


def _site(name):
    """'A' for the A bomb site, whatever its name ('A Site' callout, 'Bombsite A' from older analyses)."""
    if isinstance(name, str) and (name in ("A Site", "B Site") or name in ("Bombsite A", "Bombsite B")):
        return "A" if "A" in name.replace("Bombsite", "") else "B"
    return None


def nm(name):
    """A Site -> A site (in a sentence)."""
    return tr("{site} site", site=_site(name)) if _site(name) else name


def cap(name):
    n = nm(name)
    return n[:1].upper() + n[1:] if n else n


def at(name):
    """'on A site', 'at Outside'."""
    return tr("on {site} site", site=_site(name)) if _site(name) else tr("at {zone}", zone=name)


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


_ZONES = {}   # callout -> radar point of the map being written (set by build)


def _near(x):
    """ "Outside → Outside" says nothing: the nearest other callout to where it lands."""
    if x.get("from") != x.get("to") or not x.get("to_px") or not _ZONES:
        return nm(x["to"])
    lv = x.get("land_level") or x.get("level")
    c = [(((z["px"][0] - x["to_px"][0]) ** 2 + (z["px"][1] - x["to_px"][1]) ** 2) ** .5, n) for n, z in _ZONES.items()
         if n != x["to"] and z.get("px") and (not lv or not z.get("level") or z["level"] == lv)]
    d, n = min(c) if c else (1e9, None)
    return tr("{zone}, near {other}", zone=nm(x['to']), other=n) if n and d < 140 else nm(x["to"])


def _nade_txt(t, x, side):
    name = {"flash": tr("The flash"), "smoke": tr("The smoke"), "he": tr("The HE"), "molotov": tr("The incendiary") if side == "CT" else tr("The molotov")}[t]
    if t == "flash":
        eff = tr("it flashes an enemy {p}% of the time", p=x.get('blind'))
    elif t == "he":
        eff = tr("{n} damage on average", n=x.get('dmg'))
    elif t == "smoke" and x.get("win") is not None:
        eff = tr("thrown in {n} rounds out of 100, {p}% of rounds won when it's used", n=round(x.get('per100') or 0), p=x['win'])
    else:
        eff = tr("thrown in {n} rounds out of 100", n=round(x.get('per100') or 0))
    return tr("{nade} {from} → {to}, around {t}: {effect} (base).", nade=name, **{"from": nm(x['from'])}, to=_near(x), t=x['timer'], effect=eff)


def side_notes(mp, side, S, nd, regions, n_matches):
    zones = [z for z in S.get("zones", []) if z.get("key") and "spawn" not in z["key"].lower()]
    best = S.get("best_spots", [])
    pool = S.get("pool_zones", [])
    out = []   # (priority, kind, html)
    used = set()
    cited = set()   # grenades already in a note (type, from, to)
    avoided = set()   # zones this sheet tells you to leave
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
            src = nm(kz)
            txt = (tr("You spend {p}% of your time there for {k} and {d}, {n} of them from {zone}.", p=round(z['presence']), k=_kills(k), d=_deaths(d), n=kn, zone=src)
                   if kz and kn >= 2 else tr("You spend {p}% of your time there for {k} and {d}.", p=round(z['presence']), k=_kills(k), d=_deaths(d)))
            if moving and spot and (spot.get("hold_pct") or 0) >= 35:
                head, kind = tr("change how you play it"), "avoid"
                txt += " " + tr("You take your duels there while moving ({v} u/s median).", v=z['my_speed_med'])
                if ow is not None:
                    txt += " " + tr("Other players win {p}% of their duels there, and the best spot ({k}, {d}) is a held angle, around {t}.",
                                    p=ow, k=_kills(spot['k']), d=_deaths(spot['d']), t=_timer(spot['t_med']))
            elif alt:
                b, az = alt
                head, kind = (tr("fall back to {zone}", zone=nm(az['name'])) if side == "CT" else tr("go through {zone} instead", zone=nm(az['name']))), "avoid"
                where = (tr("On {site} site, you go {k}-{d}", site=_site(az["name"]), k=az['k'], d=az['d']) if _site(az["name"])
                         else tr("At {zone}, you go {k}-{d}", zone=az["name"], k=az['k'], d=az['d']))
                if b:
                    held = ", " + tr("held still") if (b.get("hold_pct") or 0) >= 40 else ""
                    txt += " " + tr("{where}, and the other players' best spot is there: {k} for {d}{held}.", where=where, k=_kills(b['k']), d=_deaths(b['d']), held=held)
                else:
                    txt += " " + where + "."
                if same and kn >= 2:
                    txt += " " + tr("{n} of your deaths are close-range fights inside the zone itself.", n=kn)
            elif nade:
                t, x = nade
                verb = {"smoke": tr("smoke {zone}", zone=nm(kz)), "flash": tr("flash {zone}", zone=nm(kz)), "molotov": tr("molotov {zone}", zone=nm(kz))}[t]
                head, kind = (tr("{action} before setting up", action=verb) if side == "CT" else tr("{action} before pushing", action=verb)), "tip"
                txt += " " + _nade_txt(t, x, side)
                cited.add((t, x["from"], x["to"]))
            elif same and kn >= 2:
                head, kind = tr("hold it from further back"), "avoid"
                txt += " " + tr("These are close-range duels inside the zone itself: hold an angle further back that the enemy has to come and take.")
            elif ow is not None and ow <= 45:
                head, kind = tr("avoid it"), "avoid"
                txt += " " + tr("Other players only win {p}% of their duels there.", p=ow)
            else:
                head, kind = tr("stop playing it alone"), "avoid"
                txt += " " + tr("Others win {p}% there: play it with a teammate within trade distance, or hold the angle instead of taking it.", p=ow if ow is not None else '—')
            out.append((z["presence"] * (d - k + 1), kind, f"<b>{cap(z['name'])}: {head}.</b> {txt}"))
            used.add(z["key"])
            if kind == "avoid":
                avoided.add(z["key"])
        elif good:
            txt = (tr("You go {k} for {d} there ({w}%), while other players only win {o}% there.", k=_kills(k), d=_deaths(d), w=w, o=ow) if ow is not None and ow < w
                   else tr("You go {k} for {d} there ({w}%).", k=_kills(k), d=_deaths(d), w=w))
            site = SITE.get(z["key"])
            if site and side == "T":
                txt += " " + tr("Plant {site} and play the post-plant.", site=site)
            elif site:
                txt += " " + tr("Keep it as your default position.")
            nf = _nade_from(nd, z["key"])
            if nf and (nf[0], nf[1]["from"], nf[1]["to"]) not in cited:
                txt += " " + _nade_txt(nf[0], nf[1], side)
                cited.add((nf[0], nf[1]["from"], nf[1]["to"]))
            out.append((z["presence"] * (k - d + 2) / 2, "good", f"<b>{cap(z['name'])}: {tr('your strong spot')}.</b> {txt}"))
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
        verb = {"smoke": tr("smoke {zone}", zone=nm(kz)), "flash": tr("flash {zone}", zone=nm(kz)), "molotov": tr("molotov {zone}", zone=nm(kz))}[t]
        head = tr("{action} before setting up", action=verb) if side == "CT" else tr("{action} before pushing", action=verb)
        src = nm(kz)
        out.append((z["presence"] * 0.8, "tip", f"<b>{cap(z['name'])}: {head}.</b> "
                    + tr("You spend {p}% of your time there ({k}-{d}), and you get killed {n} times from {zone}.", p=round(z['presence']), k=z['k'], d=z['d'], n=kn, zone=src)
                    + " " + _nade_txt(t, x, side)))
        cited.add((t, x["from"], x["to"]))
        used.add(z["key"])
    # a zone where everybody dies, and where you still go
    for z in zones:
        on, od = z.get("others_k") or 0, z.get("others_d") or 0
        if z["key"] in used or on + od < 15 or (z.get("others_win") or 100) > 35 or (z.get("presence") or 0) < 2:
            continue
        out.append((z["presence"] * 1.5 + 4, "avoid", f"<b>{cap(z['name'])}: {tr('avoid it')}.</b> "
                    + tr("Players in the base lose most of their duels there: {k} for {d} ({p}%). You: {a}-{b}.", k=_kills(on), d=_deaths(od), p=z['others_win'], a=z['k'], b=z['d'])))
        used.add(z["key"])
    # zones you rarely play but win in
    more = [z for z in zones if z["key"] not in used and (z.get("presence") or 0) < 8 and z["k"] + z["d"] >= 3 and (z.get("win") or 0) >= 60]
    if more:
        more = sorted(more, key=lambda z: -(z["k"] - z["d"]))[:2]
        held = all((z.get("my_speed_med") or 999) < 60 for z in more)
        each = [f"{nm(z['name'])} ({z['k']}-{z['d']})" for z in more]
        names = tr("{a} and {b}", a=each[0], b=each[1]) if len(each) > 1 else each[0]
        how = ", " + tr("holding the angle") if held else ""
        pres = max(1, round(sum(z.get("presence") or 0 for z in more)))
        out.append((6, "good", f"<b>{names[:1].upper() + names[1:]}: {tr('play them more often') if len(more) > 1 else tr('play it more often')}.</b> "
                    + tr("You win more duels than you lose there{how}, but you only spend {p}% of your time there.", how=how, p=pres)))
    # the opening grenade from your main zone
    main_ok = [z for z in main if z["key"] not in avoided]
    if main_ok:
        z0 = main_ok[0]
        first = None
        for t in (("molotov", "smoke") if side == "CT" else ("smoke", "flash")):
            for x in ((nd or {}).get("types", {}).get(t) or {}).get("picks", []):
                if x.get("from_key") in {z["key"] for z in main_ok} and x.get("usual") in ("debut", "prise") and (t, x["from"], x["to"]) not in cited:
                    first = (t, x)
                    break
            if first:
                break
        if first:
            t, x = first
            name = {"smoke": tr("your smoke"), "molotov": tr("your incendiary") if side == "CT" else tr("your molotov"), "flash": tr("your flash")}[t]
            txt = _nade_txt(t, x, side)
            ec = next((z.get("early_contact_s") for z in main if z["name"] == x["from"] and z.get("early_contact_s")), z0.get("early_contact_s"))
            if ec:
                txt += " " + tr("The first contact {where} comes around {t}.", where=at(x['from']), t=_timer(ec))
            head = (tr("Open the round with {nade} toward {zone}", nade=name, zone=nm(x['to'])) if side == "CT"
                    else tr("Before going in, {nade} toward {zone}", nade=name, zone=nm(x['to'])))
            out.append((5, "tip", f"<b>{head}.</b> {txt}"))
    # a position that pays off for everybody on this side and that you never play
    tries = [z for z in pool if (z.get("win") or 0) >= 60 and z["k"] + z["d"] >= 15 and (z.get("my_presence") or 0) < 1
             and (z.get("others_presence") or 0) >= 1 and "spawn" not in str(z.get("key", "")).lower()]
    if tries:
        z = max(tries, key=lambda z: z["k"] - z["d"])
        how = ", " + tr("mostly holding the angle") if (z.get("hold_pct") or 0) >= 40 else ""
        out.append((3, "tip", f"<b>{cap(z['name'])}: {tr('worth a try')}.</b> "
                    + tr("Players in the base win {p}% of their duels there ({k}-{d}){how}, around {t}. You almost never play there.", p=z['win'], k=z['k'], d=z['d'], how=how, t=_timer(z['t_med']))))
    out.sort(key=lambda b: -b[0])
    out = out[:5]
    if not out:
        return None
    title = tr("{map} as {side} ({role})", map=map_name(mp), side=side, role=tr(SIDE_FR[side])) + " · " + (tr("only 1 match here: to be confirmed") if n_matches == 1 else trn(n_matches, "{n} match", "{n} matches"))
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
        from wily.coaching import team
        meta = team.map_meta()
    except Exception:
        meta = {}
    res = {}
    for m in cross.get("maps", []):
        mp = m["map"]
        if not mp.startswith("de_"):
            continue
        regions = (meta.get(mp) or {}).get("regions", {})
        _ZONES.clear()
        _ZONES.update(((((plan or {}).get("tside") or {}).get("maps") or {}).get(mp) or {}).get("geo", {}).get("zones") or {})
        for side, S in (m.get("sides") or {}).items():
            n = side_notes(mp, side, S, (nd_all.get(mp) or {}).get(side), regions, m.get("matches") or 0)
            if n:
                res.setdefault(mp, {})[side] = n
    return res


def write(sid, cross=None, plan=None):
    notes = build(sid, cross, plan)
    json.dump(notes, open(os.path.join(config.player_dir(sid), "cross_notes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return notes
