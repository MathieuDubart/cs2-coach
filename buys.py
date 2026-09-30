"""Buys and positions by type of round: pistol, eco, force, full, anti-eco (your team full against an eco).

For every player-round of every matchmaking demo: what was bought (weapon, armour, helmet, grenades, defuse kit),
where the player stood between 15 and 25 s, and what came out of it (round won, damage, kills, survival).
Then, for a player, per map, side and type of round: where to play and what to buy, from his own rounds
(when there are enough) and from the base (same map, same side, same type of round).
"""
import math
import os
from collections import Counter

import pandas as pd

import config
from map_analysis import humanize

OUT = os.path.join(config.OUT, "population", "buys")
TYPES = ["pistol", "eco", "force", "full", "anti-eco"]
TYPE_FR = {"pistol": "Round pistolet", "eco": "Éco", "force": "Force-buy", "full": "Full buy", "anti-eco": "Anti-éco"}
ARMOR_FR = {"none": "sans kevlar", "kevlar": "kevlar", "helmet": "kevlar + casque"}
DEFAULT_PISTOLS = {"Glock-18", "USP-S", "P2000"}
# weapons a side cannot buy: holding one means it was picked up (often after winning), not a buy choice
NOT_BUYABLE = {"T": {"M4A4", "M4A1-S", "AUG", "FAMAS", "MP9", "Five-SeveN", "USP-S", "P2000", "MAG-7"},
               "CT": {"AK-47", "SG 553", "Galil AR", "MAC-10", "Tec-9", "Glock-18", "Sawed-Off"}}


def _rtype(team, enemy):
    if team == "pistol":
        return "pistol"
    if team == "full" and enemy == "eco":
        return "anti-eco"
    return team if team in ("eco", "force", "full") else None


def rows_for(ddir):
    d = ddir
    L = pd.read_parquet(os.path.join(d, "loadout.parquet"))
    R = pd.read_parquet(os.path.join(d, "rounds.parquet")).set_index("round")
    S = pd.read_parquet(os.path.join(d, "samples.parquet"), columns=["steamid", "round", "t", "zone"])
    import json
    mp = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8")).get("map")
    S = S[(S.t >= 15) & (S.t <= 25) & (S.zone != "?")]
    setup = S.groupby(["round", "steamid"]).zone.agg(lambda z: z.mode().iloc[0]).to_dict()
    known = "buy_util" in L.columns  # grenades bought, by type (older extractions only have their number)
    rows = []
    for _, x in L.iterrows():
        r = int(x["round"])
        if r not in R.index or x.side not in ("T", "CT"):
            continue
        other = "CT" if x.side == "T" else "T"
        rt = _rtype(R.loc[r].get(f"{x.side}_buy"), R.loc[r].get(f"{other}_buy"))
        if rt is None:
            continue
        util = [u for u in str(x.get("buy_util") or "").split(",") if u] if known else []
        rows.append({"map": mp, "steamid": int(x.steamid), "round": r, "side": x.side, "rtype": rt,
                     "weapon": x.primary if isinstance(x.primary, str) and x.primary else (x.pistol if isinstance(x.pistol, str) else "?"),
                     "wclass": x.wclass, "pistol": x.pistol if isinstance(x.pistol, str) else None,
                     "armor": "helmet" if x.helmet else "kevlar" if (x.armor or 0) > 0 else "none", "util": ",".join(util),
                     "util_n": len(util) if known else int(x.nades or 0), "util_known": known,
                     "defuser": bool(x.defuser), "equip": float(x.equip or 0),
                     "zone": humanize(setup.get((r, int(x.steamid)), "")) if setup.get((r, int(x.steamid))) else None,
                     "kills": int(x.kills), "damage": int(x.damage), "died": bool(pd.notna(x.died_t)), "won": bool(x.won)})
    return pd.DataFrame(rows)


def run_all(log=print):
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for mid in os.listdir(config.DEEP):
        d = os.path.join(config.DEEP, mid)
        f = os.path.join(OUT, f"{mid}.parquet")
        lo = os.path.join(d, "loadout.parquet")
        if not os.path.exists(lo) or not os.path.exists(os.path.join(d, "rounds.parquet")):
            continue
        if os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(lo):
            continue
        import pyarrow.parquet as pq
        if os.path.exists(f) and "buy_util" not in pq.read_schema(lo).names:
            continue
        try:
            rows_for(d).to_parquet(f)
            n += 1
        except Exception as e:
            log(f"[{mid}] achats : {e}")
    return n


def load():
    fs = [os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith(".parquet")] if os.path.exists(OUT) else []
    dfs = [pd.read_parquet(f) for f in fs]
    dfs = [x for x in dfs if len(x)]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def kit(row):
    """Readable buy, grouped the way the choice is made for this type of round."""
    rt, w, a, un = row["rtype"], row["weapon"], row["armor"], row["util_n"]
    util = [u for u in (row["util"] or "").split(",") if u]
    ut = ", ".join(f"{k}{f' ×{v}' if v > 1 else ''}" for k, v in Counter(util).most_common())
    if rt in ("pistol", "eco"):
        parts = [w if w != "?" else "pistolet de base", ARMOR_FR[a] if a != "none" else None, ut or None]
        return " + ".join(p for p in parts if p)
    if rt == "force":
        return f"{w} + {ARMOR_FR[a]}"
    if rt == "anti-eco":
        return w
    return f"{w} + {'3 grenades et plus' if un >= 3 else '1 ou 2 grenades' if un else 'sans grenade'}"


def _wilson_low(k, n, z=1.28):
    if not n:
        return 0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def _table(df, key, min_n, by="win"):
    """Options ranked by rounds won (lower bound of the win rate), or by damage for eco rounds (mostly lost anyway)."""
    if not len(df):
        return []
    g = df.groupby(key).agg(n=("won", "size"), won=("won", "sum"), adr=("damage", "mean"), kpr=("kills", "mean"), died=("died", "mean"))
    g = g[g.n >= min_n]
    out = []
    for k, x in g.iterrows():
        if not k:
            continue
        score = _wilson_low(x.won, x.n) if by == "win" else (x.adr * x.n + 70 * 8) / (x.n + 8)
        out.append({"key": k, "n": int(x.n), "win": round(100 * x.won / x.n), "adr": round(x.adr), "kpr": round(x.kpr, 2),
                    "survival": round(100 * (1 - x.died)), "score": score})
    return sorted(out, key=lambda r: -r["score"])


def advise(sid, maps):
    """Per map, side and type of round: where to play and what to buy (you, then the base)."""
    B = load()
    if not len(B):
        return None
    B["kit"] = B.apply(kit, axis=1)
    if "util_known" in B:
        B.loc[B.rtype.isin(["pistol", "eco"]) & ~B.util_known.fillna(False).astype(bool), "kit"] = None
    me = B[B.steamid == int(sid)]
    res = {"types": {}, "maps": {}}
    for rt in TYPES:  # all maps together: what works for you on each type of round
        m = me[me.rtype == rt]
        b = B[B.rtype == rt]
        res["types"][rt] = {"label": TYPE_FR[rt], "rounds": int(len(m)), "win": round(100 * m.won.mean()) if len(m) else None,
                            "adr": round(m.damage.mean()) if len(m) else None, "base_win": round(100 * b.won.mean()) if len(b) else None,
                            "my_kits": _table(m, "kit", 2)[:4], "base_kits": _table(b, "kit", 40)[:4]}
    for mp in maps:
        for side in ("T", "CT"):
            for rt in TYPES:
                b = B[(B["map"] == mp) & (B.side == side) & (B.rtype == rt)]
                m = me[(me["map"] == mp) & (me.side == side) & (me.rtype == rt)]
                if len(b) < 20 and len(m) < 2:
                    continue
                by = "adr" if rt == "eco" else "win"
                # where to play: not the spawn, and for T not the bomb site itself (being there at 15-25 s is a result, not a choice)
                ok_zone = lambda z: bool(z) and "spawn" not in z.lower() and not (side == "T" and z.lower().startswith("bombsite"))
                buyable = lambda df: df[~df.weapon.isin(NOT_BUYABLE[side])]
                kn = 20 if rt in ("force", "full") else 12
                bz, bk = _table(b[b.zone.map(ok_zone)], "zone", 12, by), _table(buyable(b), "kit", kn, by)
                mz, mk = _table(m[m.zone.map(ok_zone)], "zone", 2, by), _table(buyable(m), "kit", 2, by)
                base_win = round(100 * b.won.mean()) if len(b) else None
                # recommendation: your own zone/buy when it has worked at least as well as the base, else the base's best
                base_adr = b.damage.mean() if len(b) else None
                better = (lambda x: x["win"] >= base_win) if by == "win" else (lambda x: base_adr is not None and x["adr"] >= base_adr)
                rz = next((z for z in mz if z["n"] >= 3 and base_win is not None and better(z)), None)
                rk = next((k for k in mk if k["n"] >= 3 and base_win is not None and better(k)), None)
                res["maps"].setdefault(mp, {}).setdefault(side, {})[rt] = {
                    "label": TYPE_FR[rt], "n_base": int(len(b)), "n_me": int(len(m)), "base_win": base_win, "by": by,
                    "my_win": round(100 * m.won.mean()) if len(m) else None,
                    "zone": {"name": (rz or (bz[0] if bz else {})).get("key"), "from": "toi" if rz else "base",
                             **{k: v for k, v in (rz or (bz[0] if bz else {})).items() if k in ("n", "win", "adr")}} if (rz or bz) else None,
                    "kit": {"name": (rk or (bk[0] if bk else {})).get("key"), "from": "toi" if rk else "base",
                            **{k: v for k, v in (rk or (bk[0] if bk else {})).items() if k in ("n", "win", "adr")}} if (rk or bk) else None,
                    "base_zones": bz[:4], "base_kits": bk[:4], "my_zones": mz[:3], "my_kits": mk[:3],
                    "avoid_zone": (bz[-1] if len(bz) >= 4 and bz[-1]["win"] <= (base_win or 50) - 8 else None)}
    return res


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(run_all(), "matchs")
    r = advise(int(sys.argv[1]) if len(sys.argv) > 1 else config.logged_in_account()[0], ["de_nuke", "de_anubis"])
    print(json.dumps(r["types"], ensure_ascii=False, indent=1)[:3000])
    print(json.dumps(r["maps"].get("de_nuke", {}).get("CT", {}).get("pistol"), ensure_ascii=False, indent=1))
