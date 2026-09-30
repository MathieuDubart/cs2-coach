"""Grenades that work, from where you play.

For every map and side, the throws of the base grouped by where they are thrown from and where they land, with what
they did (flash: enemies blinded and kills in the next 3 s; HE and molotov: damage to enemies; smoke: how often it is
thrown, rounds won when it is) and the moment of the round when they work best.
Then, for a player: the throws from the zones they play, the order in which to buy utility there, and their own habits
(what they throw, what they still hold when they die).
Writes out/population/nades.parquet (every throw) and nades_summary.json (groups per map and side).
Usage: python nades.py
"""
import json
import os
import sys

import pandas as pd

import config

OUT = os.path.join(config.OUT, "population", "nades.parquet")
SUMMARY = os.path.join(config.OUT, "population", "nades_summary.json")
# CS2 prices, checked on the equipment values of the demos (the CT incendiary costs 500 $)
PRICE = {"flash": 200, "smoke": 300, "he": 300, "molotov": {"T": 400, "CT": 500}}
TYPES = ("smoke", "flash", "molotov", "he")
TYPE_FR = {"flash": "flash", "smoke": "smoke", "he": "HE", "molotov": "molotov"}
ROUND_TIME = 115.0
# moments of the round, in seconds after the freeze time (the timer starts at 1:55)
WINDOWS = [("debut", 0, 20), ("prise", 20, 40), ("action", 40, 70), ("fin", 70, 999)]
WINDOW_FR = {"debut": "début de round (1:55 à 1:35)", "prise": "prise d'infos (1:35 à 1:15)", "action": "attaque du site (1:15 à 0:45)",
             "fin": "fin de round (après 0:45)", "post": {"T": "après la pose", "CT": "retake"}}
COLS = ["map", "match", "round", "t", "type", "thrower", "side", "zone", "land_zone", "X", "Y", "Z", "pitch", "yaw", "px", "py",
        "level", "land_px", "land_py", "land_level", "jump", "speed", "crouch", "walk", "click", "flight_s", "damage",
        "enemies_blind", "mates_blind", "kills_after", "post", "won", "buy"]


def humanize(z):
    from map_analysis import humanize as h
    return h(z) if isinstance(z, str) and z else None


def _timer(t):
    left = max(0.0, ROUND_TIME - float(t))
    return f"{int(left // 60)}:{int(left % 60):02d}"


def _stamp():
    n, latest = 0, 0.0
    for mid in os.listdir(config.DEEP) if os.path.exists(config.DEEP) else []:
        f = os.path.join(config.DEEP, mid, "grenades.parquet")
        if os.path.exists(f):
            n += 1
            latest = max(latest, os.path.getmtime(f))
    return f"{n}-{int(latest)}"


def load_all(rebuild=False):
    """Every throw of the base (5v5 matchmaking demos), with the round's outcome, the side's buy and the bomb."""
    meta_f = OUT + ".json"
    stamp = _stamp()
    if not rebuild and os.path.exists(OUT) and os.path.exists(meta_f):
        try:
            if json.load(open(meta_f, encoding="utf-8")).get("stamp") == stamp:
                return pd.read_parquet(OUT)
        except ValueError:
            pass
    rows = []
    for mid in os.listdir(config.DEEP):
        d = os.path.join(config.DEEP, mid)
        f, fr = os.path.join(d, "grenades.parquet"), os.path.join(d, "rounds.parquet")
        if not os.path.exists(f) or not os.path.exists(fr):
            continue
        R = pd.read_parquet(fr)
        if not len(R) or R.T_n.max() < 4 or R.CT_n.max() < 4:  # wingman: other habits
            continue
        try:
            mp = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8")).get("map")
        except (OSError, ValueError):
            continue
        if not mp or mp.startswith("cs_"):
            continue
        g = pd.read_parquet(f)
        g = g[g.side.isin(["T", "CT"])] if len(g) else g
        if not len(g):
            continue
        R = R.set_index("round")
        plant = R["plant_t"] if "plant_t" in R else pd.Series(dtype=float)
        g = g.assign(map=mp, match=mid,
                     post=[bool(pd.notna(plant.get(r)) and t > plant.get(r)) for r, t in zip(g["round"], g.t)],
                     won=[R.winner.get(r) == s for r, s in zip(g["round"], g.side)],
                     buy=[(R[f"{s}_buy"].get(r) if f"{s}_buy" in R else None) for r, s in zip(g["round"], g.side)])
        for c in COLS:
            if c not in g:
                g[c] = None
        rows.append(g[COLS])
    df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=COLS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_parquet(OUT)
    json.dump({"stamp": stamp}, open(meta_f, "w", encoding="utf-8"))
    return df


def _window(t, post):
    if post:
        return "post"
    for k, lo, hi in WINDOWS:
        if lo <= t < hi:
            return k
    return "fin"


def _eff(x, typ):
    """How well a set of throws worked: share of flashes that blind an enemy (1.5 s or more), damage of HE and molotovs."""
    if typ == "flash":
        return float((x.enemies_blind.fillna(0) >= 1).mean())
    if typ in ("he", "molotov"):
        return float(x.damage.fillna(0).mean())
    return None


def _how(b):
    how = []
    if b.jump:
        how.append("sauté")
    if b.speed > 150:
        how.append("en courant")
    elif b.walk or 20 < b.speed <= 150:
        how.append("en marchant")
    if b.crouch:
        how.append("accroupi")
    return " + ".join(how) or "à l'arrêt"


def groups(df, side_rounds):
    """Throws grouped by (type, thrown from, lands in), per map and side, with effect and timing."""
    out = {}
    df = df[df.zone.notna() & df.land_zone.notna() & (df.zone != "?") & (df.land_zone != "?")]
    for (mp, side), g in df.groupby(["map", "side"]):
        rounds = side_rounds.get((mp, side), 0)
        if rounds < 60:
            continue
        res = {}
        for typ in TYPES:
            t = g[g.type == typ]
            if len(t) < 20:
                continue
            prior = _eff(t, typ)
            if typ == "flash":
                prior_k = float((t.kills_after.fillna(0) >= 1).mean())
            full = t[t.buy == "full"]
            base_win = float(g[g.buy == "full"].drop_duplicates(["match", "round"]).won.mean()) if typ == "smoke" and len(full) else None
            lst = []
            for (z, lz), c in t.groupby(["zone", "land_zone"]):
                if len(c) < 8:
                    continue
                n = len(c)
                e = {"n": int(n), "players": int(c.thrower.nunique()), "per100": round(100 * n / rounds, 1)}
                if typ == "flash":
                    blind = float((c.enemies_blind.fillna(0) >= 1).sum())
                    e["blind"] = round(100 * (blind + prior * 10) / (n + 10))
                    e["kill"] = round(100 * (float((c.kills_after.fillna(0) >= 1).sum()) + prior_k * 10) / (n + 10))
                    e["team"] = round(100 * float((c.mates_blind.fillna(0) >= 1).mean()))
                    score = e["blind"] / 100 + 0.5 * e["kill"] / 100 - 0.5 * e["team"] / 100
                elif typ in ("he", "molotov"):
                    e["dmg"] = round((float(c.damage.fillna(0).sum()) + prior * 10) / (n + 10))
                    e["hit"] = round(100 * float((c.damage.fillna(0) > 0).mean()))
                    # a molotov mostly closes a passage (the enemy waits or goes around): how often it is used counts
                    # as much as its damage; an HE is worth its damage
                    score = e["dmg"] / 25 if typ == "he" else 0.6 * min(1.0, e["per100"] / 25) + 0.4 * min(1.0, e["dmg"] / 20)
                else:
                    fc = c[c.buy == "full"].drop_duplicates(["match", "round"])
                    if len(fc) >= 10 and base_win is not None:
                        e["win"] = round(100 * float(fc.won.mean()))
                        e["base_win"] = round(100 * base_win)
                    score = min(1.0, e["per100"] / 25)
                # when it is thrown, and when it works
                c = c.assign(w=[_window(tt, p) for tt, p in zip(c.t, c.post)])
                wins = {}
                for w, cw in c.groupby("w"):
                    wins[w] = {"n": int(len(cw))}
                    ew = _eff(cw, typ)
                    if ew is not None:
                        wins[w]["eff"] = round(100 * (ew * len(cw) + prior * 5) / (len(cw) + 5)) if typ == "flash" else round((ew * len(cw) + prior * 5) / (len(cw) + 5))
                usual = max(wins, key=lambda k: wins[k]["n"])
                best = usual
                if typ != "smoke":
                    ok = {k: v for k, v in wins.items() if v["n"] >= 5 and "eff" in v}
                    if ok:
                        best = max(ok, key=lambda k: ok[k]["eff"])
                # the usual way to throw it: most common standing spot among throws easy to repeat
                rep = c.assign(cell=list(zip((c.px // 20).astype(int), (c.py // 20).astype(int))), repro=(c.speed < 20) | c.jump)
                pool = rep[rep.repro] if rep.repro.any() else rep
                cell = pool.cell.value_counts().index[0]
                cand = pool[pool.cell == cell]
                if typ == "flash":
                    cand = cand.sort_values("enemies_blind", ascending=False)
                elif typ in ("he", "molotov"):
                    cand = cand.sort_values("damage", ascending=False)
                b = cand.iloc[0]
                lst.append({"from_key": z, "from": humanize(z), "to_key": lz, "to": humanize(lz), "score": round(float(score), 3), **e,
                            "t_med": round(float(c.t.median()), 1), "timer": _timer(c.t.median()),
                            "timer_span": [_timer(c.t.quantile(0.25)), _timer(c.t.quantile(0.75))],
                            "windows": wins, "usual": usual, "best": best, "post": round(100 * float(c.post.mean())),
                            "how": _how(b), "click": b.click, "flight_s": None if pd.isna(b.flight_s) else float(b.flight_s),
                            "from_px": [round(float(cand.px.mean())), round(float(cand.py.mean()))], "level": b.level,
                            "to_px": [round(float(c.land_px.median())), round(float(c.land_py.median()))], "land_level": b.land_level,
                            "setpos": f"setpos {b.X:.1f} {b.Y:.1f} {b.Z:.1f}; setang {b.pitch:.2f} {b.yaw:.2f} 0"})
            lst.sort(key=lambda x: -x["score"])
            res[typ] = {"prior": None if prior is None else (round(100 * prior) if typ == "flash" else round(prior)), "groups": lst}
        out.setdefault(mp, {})[side] = {"rounds": int(rounds), "types": res}
    return out


def _side_rounds():
    """Rounds played per map and side in the base (5v5 only), to turn counts into 'per 100 rounds'."""
    cnt = {}
    for mid in os.listdir(config.DEEP):
        d = os.path.join(config.DEEP, mid)
        fr = os.path.join(d, "rounds.parquet")
        if not os.path.exists(fr):
            continue
        R = pd.read_parquet(fr, columns=["T_n", "CT_n"])
        if not len(R) or R.T_n.max() < 4 or R.CT_n.max() < 4:
            continue
        try:
            mp = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8")).get("map")
        except (OSError, ValueError):
            continue
        for s in ("T", "CT"):
            cnt[(mp, s)] = cnt.get((mp, s), 0) + len(R)
    return cnt


BUY_NAME = {"flash": "flash", "smoke": "smoke", "HE": "he", "molotov": "molotov"}


def payoff():
    """What utility pays off, from the buys of every player of the base:
    rounds won by number of grenades bought per type of round, and, when only one grenade is bought (force and full
    buys), rounds won by its type against no grenade at all, per side (pulled toward 'no grenade' when rare)."""
    import buys
    B = buys.load()
    if not len(B):
        return {}
    out = {"count": {}, "single": {}}
    for rt in ("eco", "force", "full"):
        x = B[B.rtype == rt]
        x = x.assign(nn=x.util_n.clip(upper=4))
        t = x.groupby("nn").agg(n=("won", "size"), win=("won", "mean"), adr=("damage", "mean"))
        out["count"][rt] = {int(k): {"n": int(v.n), "win": round(100 * v.win), "adr": round(v.adr)} for k, v in t.iterrows() if v.n >= 30}
    B = B[B.util_known.fillna(False).astype(bool) & B.rtype.isin(["force", "full"])]
    for side in ("T", "CT"):
        x = B[B.side == side]
        none = x[x.util_n == 0]
        w0 = float(none.won.mean()) if len(none) else 0.5
        res = {"none": {"n": int(len(none)), "win": round(100 * w0)}}
        one = x[x.util_n == 1]
        for u, g in one.groupby("util"):
            typ = BUY_NAME.get(u)
            if typ:
                k = 150  # rare buys stay close to 'no grenade'
                res[typ] = {"n": int(len(g)), "win": round(100 * float(g.won.mean())),
                            "uplift": round(100 * ((float(g.won.sum()) + w0 * k) / (len(g) + k) - w0), 1)}
        out["single"][side] = res
    return out


def summary(rebuild=False):
    stamp = _stamp()
    if not rebuild and os.path.exists(SUMMARY):
        try:
            cur = json.load(open(SUMMARY, encoding="utf-8"))
            if cur.get("_stamp") == stamp:
                return cur
        except ValueError:
            pass
    df = load_all()
    res = {"_stamp": stamp, "maps": groups(df, _side_rounds()), "payoff": payoff(), "price": PRICE, "windows": WINDOW_FR}
    json.dump(res, open(SUMMARY, "w", encoding="utf-8"), ensure_ascii=False)
    return res


def _my_zones(cross, mp, side, top=4, min_presence=5.0):
    """The zones you play on this side of this map (everybody goes through the spawns: not a choice)."""
    for m in (cross or {}).get("maps", []):
        if m["map"] == mp:
            zs = [z for z in (m.get("sides", {}).get(side) or {}).get("zones", [])
                  if (z.get("presence") or 0) >= min_presence and "spawn" not in str(z.get("key", "")).lower()]
            return [z["key"] for z in sorted(zs, key=lambda z: -z["presence"])[:top]], {z["key"]: z["presence"] for z in zs}
    return [], {}


def for_player(sid, maps, cross=None, stats=None):
    """Per map and side: the grenades that work from the zones you play, in buying order, with when and how to throw
    them; and your habits (grenades you throw, grenades you still hold when you die)."""
    S = summary()
    df = load_all()
    mine = df[df.thrower == int(sid)] if len(df) else df
    res = {"price": PRICE, "windows": WINDOW_FR, "payoff": S.get("payoff", {}), "maps": {}}
    for mp in maps:
        for side in ("T", "CT"):
            M = (S["maps"].get(mp) or {}).get(side)
            if not M:
                continue
            zones, pres = _my_zones(cross, mp, side)
            own = mine[(mine["map"] == mp) & (mine.side == side)]
            entry = {"zones": [humanize(z) for z in zones], "personal": bool(zones), "types": {}}
            share = {}
            for typ, T in M["types"].items():
                gs = T["groups"]
                pick = [dict(x) for x in gs if x["from_key"] in zones][:3] if zones else []
                other = False
                if not pick:  # nothing thrown from your zones: the best of the side
                    pick, other = [dict(x) for x in gs[:2]], True
                for x in pick:
                    o = own[(own.type == typ) & (own.zone == x["from_key"]) & (own.land_zone == x["to_key"])]
                    x["mine"] = int(len(o))
                    x.pop("windows", None) if typ == "smoke" else None
                # after the plant (retake for the CT, post-plant for the T): throws mostly made once the bomb is down
                post = [dict(x) for x in gs if x.get("post", 0) >= 30]
                post.sort(key=lambda x: (x["from_key"] not in zones, -x["score"]))
                for x in post:
                    x.pop("windows", None)
                entry["types"][typ] = {"prior": T["prior"], "picks": pick, "elsewhere": other, "post": post[:2]}
                share[typ] = sum(x["n"] for x in gs if x["from_key"] in zones) if zones else sum(x["n"] for x in gs[:5])
            # buying order when money is short: what one grenade alone adds to the rounds won on this side (base),
            # plus a bonus when it works well from your zones; a flash that rarely blinds from there is left out
            single = (S.get("payoff", {}).get("single") or {}).get(side, {})
            tot = sum(share.values()) or 1
            order = []
            for typ in TYPES:
                p = entry["types"].get(typ, {}).get("picks") or []
                if not p:
                    continue
                best = p[0]
                if typ == "flash" and best.get("blind", 0) < 20:
                    continue
                strong = (typ == "flash" and best.get("blind", 0) >= 40) or (typ == "he" and best.get("dmg", 0) >= 12) or                          (typ == "smoke" and (best.get("per100", 0) >= 10 or (best.get("win") or 0) - (best.get("base_win") or 0) >= 5)) or                          (typ == "molotov" and best.get("per100", 0) >= 10)
                up = (single.get(typ) or {}).get("uplift", 0.0)
                price = PRICE[typ][side] if isinstance(PRICE[typ], dict) else PRICE[typ]
                order.append({"type": typ, "price": price, "value": round(up + (2 if strong else 0), 1), "uplift": up,
                              "alone": single.get(typ), "strong": strong, "share": round(100 * share.get(typ, 0) / tot),
                              "to": best["to"], "from": best["from"]})
            order.sort(key=lambda o: -o["value"])
            entry["order"] = order
            entry["none"] = single.get("none")
            entry["mine"] = {t: int((own.type == t).sum()) for t in TYPES}
            res["maps"].setdefault(mp, {})[side] = entry
    # habits: grenades still in hand at death, and grenades thrown per round, against the base
    if stats:
        unused = sum((s.get("utility") or {}).get("grenades_unused_at_death") or 0 for s in stats)
        deaths = sum((s.get("overview") or {}).get("deaths") or 0 for s in stats)
        res["unused_per_death"] = round(unused / deaths, 2) if deaths else None
        res["unused_last"] = [{"map": s.get("map"), "unused": (s.get("utility") or {}).get("grenades_unused_at_death")} for s in stats[-5:]]
    if len(df):
        rounds_me = mine.groupby(["match", "round"]).ngroups if len(mine) else 0
        per = df.groupby(["match", "thrower"]).size()
        res["thrown_per_match_base"] = round(float(per.median()), 1) if len(per) else None
        res["thrown_per_match_me"] = round(float(mine.groupby("match").size().median()), 1) if len(mine) else None
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    s = summary(rebuild=True)
    print({mp: {side: {t: len(v["groups"]) for t, v in S["types"].items()} for side, S in sides.items()} for mp, sides in s["maps"].items()})
