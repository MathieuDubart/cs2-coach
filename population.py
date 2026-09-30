"""Per-player metrics for EVERY player of a demo (reference population).

Usage: python population.py            # all cached demos with a deep extraction
Writes out/population/<match_id>.parquet (one row per player of the match).
"""
import math
import os
import sys

import numpy as np
import pandas as pd
from demoparser2 import DemoParser

import config

TICK = 64
GRENADE_INV = {"Flashbang", "High Explosive Grenade", "Smoke Grenade", "Molotov", "Incendiary Grenade", "Decoy Grenade"}
NADE_W = {"weapon_flashbang", "weapon_hegrenade", "weapon_smokegrenade", "weapon_molotov", "weapon_incgrenade", "weapon_decoy"}
RIFLES = {"weapon_ak47", "weapon_m4a1", "weapon_m4a1_silencer", "weapon_aug", "weapon_sg556", "weapon_famas", "weapon_galilar"}
SNIPERS = {"weapon_awp", "weapon_ssg08"}
PISTOLS = {"weapon_glock", "weapon_usp_silencer", "weapon_hkp2000", "weapon_p250", "weapon_fiveseven", "weapon_tec9",
           "weapon_cz75a", "weapon_deagle", "weapon_elite", "weapon_revolver"}
SKILL = ["", "Silver I", "Silver II", "Silver III", "Silver IV", "Silver Elite", "Silver Elite Master", "Gold Nova I",
         "Gold Nova II", "Gold Nova III", "Gold Nova Master", "Master Guardian I", "Master Guardian II",
         "Master Guardian Elite", "Distinguished Master Guardian", "Legendary Eagle", "Legendary Eagle Master",
         "Supreme Master First Class", "Global Elite"]
OUT = os.path.join(config.OUT, "population")


def sid(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def extract(mid):
    dem = os.path.join(config.CACHE, f"{mid}.dem")
    ddir = os.path.join(config.DEEP, mid)
    duels = pd.read_parquet(os.path.join(ddir, "duels.parquet"))
    nades = pd.read_parquet(os.path.join(ddir, "grenades.parquet"))
    samples = pd.read_parquet(os.path.join(ddir, "samples.parquet"), columns=["steamid", "name", "side", "round"])
    p = DemoParser(dem)
    hdr = p.parse_header()
    freeze = p.parse_event("round_freeze_end")["tick"].tolist()
    n_rounds = len(freeze)
    players = samples.drop_duplicates("steamid")[["steamid", "name"]]
    players = players[players.steamid != 0]

    # ranks
    rank = {}
    try:
        ru = p.parse_event("rank_update")
        ru["user_steamid"] = ru["user_steamid"].map(sid)
        for _, r in ru.iterrows():
            rank[r.user_steamid] = (int(r.rank_type_id), int(r.rank_old or 0), int(r.rank_new or 0))
    except Exception:
        pass

    # damage (capped to remaining health)
    hurt = p.parse_event("player_hurt")
    for c in ("attacker_steamid", "user_steamid"):
        hurt[c] = hurt[c].map(sid)
    hurt = hurt.sort_values("tick")
    team_at = p.parse_ticks(["team_num"], ticks=[freeze[0] + 1, freeze[-1] + 1] if freeze else [0])
    team_at["steamid"] = team_at["steamid"].map(sid)
    hp, real = {}, []
    rid = np.searchsorted(np.array(freeze), hurt.tick.values, side="right")
    for (r_, v, d, h) in zip(rid, hurt.user_steamid, hurt.dmg_health, hurt.health):
        before = hp.get((r_, v), 100)
        real.append(min(int(d), before))
        hp[(r_, v)] = max(int(h), 0)
    hurt["real"] = real
    hurt["weapon_full"] = "weapon_" + hurt.weapon.astype(str)
    deaths = p.parse_event("player_death")
    for c in ("attacker_steamid", "user_steamid", "assister_steamid"):
        deaths[c] = deaths[c].map(sid)
    enemy_hurt = hurt[hurt.attacker_steamid != hurt.user_steamid]

    # grenades still in inventory at death
    dticks = sorted({max(int(t) - 2, 0) for t in deaths.tick})
    inv = p.parse_ticks(["inventory"], ticks=dticks) if dticks else pd.DataFrame(columns=["tick", "steamid", "inventory"])
    inv["steamid"] = inv["steamid"].map(sid)
    inv = inv.set_index(["tick", "steamid"])["inventory"]
    unused = {}
    for _, d in deaths.iterrows():
        try:
            items = inv.loc[(max(int(d.tick) - 2, 0), d.user_steamid)]
            unused[d.user_steamid] = unused.get(d.user_steamid, 0) + sum(1 for x in items if x in GRENADE_INV)
        except (KeyError, TypeError):
            pass

    # economy at freeze end: money left vs poorest teammate
    eco = p.parse_ticks(["balance", "current_equip_value", "round_start_equip_value", "team_num", "inventory"], ticks=freeze)
    eco["steamid"] = eco["steamid"].map(sid)
    drops, bought = {}, {}
    for t, g in eco.groupby("tick"):
        g = g.assign(start=g.balance + g.current_equip_value - g.round_start_equip_value.fillna(0))
        for team, tg in g.groupby("team_num"):
            poorest = tg.start.min()
            for _, r in tg.iterrows():
                if r.balance >= 3000 and poorest < 2500:
                    drops[r.steamid] = drops.get(r.steamid, 0) + 1
        for _, r in g.iterrows():
            bought[r.steamid] = bought.get(r.steamid, 0) + sum(1 for x in (r.inventory if isinstance(r.inventory, (list, np.ndarray)) else []) if x in GRENADE_INV)

    # shooting: moving shots, spray
    wf = p.parse_event("weapon_fire", player=["velocity_X", "velocity_Y"])
    wf["user_steamid"] = wf["user_steamid"].map(sid)
    wf["speed"] = np.hypot(wf.user_velocity_X, wf.user_velocity_Y)
    shoot = {}
    hit_ticks = hurt.groupby("attacker_steamid").tick.apply(set).to_dict()
    for s, g in wf.groupby("user_steamid"):
        pis, rif = g[g.weapon.isin(PISTOLS)], g[g.weapon.isin(RIFLES)]
        rs = rif.sort_values("tick")
        idx, last, i = [], -999, 0
        for t in rs.tick:
            i = i + 1 if t - last <= 10 else 1
            idx.append(i)
            last = t
        hits = hit_ticks.get(s, set())
        rs = rs.assign(b=idx, hit=[any((t + k) in hits for k in range(3)) for t in rs.tick])
        shoot[s] = {"pistol_shots": len(pis), "pistol_moving": float((pis.speed > 85).mean() * 100) if len(pis) else None,
                    "rifle_shots": len(rif), "rifle_moving": float((rif.speed > 75).mean() * 100) if len(rif) else None,
                    "b1_hit": float(rs[rs.b == 1].hit.mean() * 100) if (rs.b == 1).sum() else None,
                    "b9_hit": float(rs[rs.b >= 9].hit.mean() * 100) if (rs.b >= 9).sum() else None,
                    "b9_shots": int((rs.b >= 9).sum()), "b1_shots": int((rs.b == 1).sum())}

    # crosshair placement: angle to the head ~125 ms before the first shot of each engagement
    eng = enemy_hurt[~enemy_hurt.weapon.isin(["hegrenade", "inferno", "molotov", "incgrenade", "flashbang", "smokegrenade", "knife"])]
    fires = wf[~wf.weapon.isin(NADE_W)][["tick", "user_steamid"]].sort_values("tick")
    samples_x, last_hit = [], {}
    fire_by = {s: g.tick.values for s, g in fires.groupby("user_steamid")}
    for a, v, t in zip(eng.attacker_steamid, eng.user_steamid, eng.tick):
        k = (a, v)
        if k in last_hit and t - last_hit[k] < 3 * TICK:
            last_hit[k] = t
            continue
        last_hit[k] = t
        ft = fire_by.get(a)
        if ft is None:
            continue
        w = ft[(ft <= t) & (ft >= t - TICK)]
        if len(w):
            samples_x.append((int(w.min()) - 8, a, v))
    xh = {}
    if samples_x:
        pos = p.parse_ticks(["X", "Y", "Z", "pitch", "yaw", "ducking"], ticks=sorted({t for t, _, _ in samples_x}))
        pos["steamid"] = pos["steamid"].map(sid)
        pos = pos.set_index(["tick", "steamid"])
        for t, a, v in samples_x:
            try:
                m, e = pos.loc[(t, a)], pos.loc[(t, v)]
            except KeyError:
                continue
            ex, ey, ez = m.X, m.Y, m.Z + (46 if m.ducking else 64)
            tx, ty, tz = e.X, e.Y, e.Z + (46 if e.ducking else 64)
            pr, yr = math.radians(m.pitch), math.radians(m.yaw)
            view = np.array([math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), -math.sin(pr)])
            to = np.array([tx - ex, ty - ey, tz - ez])
            n = np.linalg.norm(to)
            if n < 1:
                continue
            xh.setdefault(a, []).append(math.degrees(math.acos(max(-1, min(1, float(view @ (to / n)))))))

    rows = []
    for _, pl in players.iterrows():
        s = pl.steamid
        k_ = duels[duels.killer == s]
        d_ = duels[duels.victim == s]
        a_ = deaths[(deaths.assister_steamid == s)]
        side_rounds = samples[samples.steamid == s].drop_duplicates("round").side.value_counts().to_dict()
        pov = pd.concat([pd.DataFrame({"won": True, "speed": k_.killer_speed, "hp": k_.killer_hp, "dist": k_.distance,
                                       "oppfl": k_.victim_flashed, "mates": k_.killer_mates_alive, "opp": k_.victim_mates_alive}),
                         pd.DataFrame({"won": False, "speed": d_.victim_speed, "hp": d_.victim_hp, "dist": d_.distance,
                                       "oppfl": d_.killer_flashed, "mates": d_.victim_mates_alive, "opp": d_.killer_mates_alive})])
        wr = lambda m: (float(pov[m].won.mean() * 100), int(m.sum())) if m.sum() else (None, 0)
        hold, n_hold = wr(pov.speed < 40)
        peek, n_peek = wr(pov.speed > 110)
        low, n_low = wr(pov.hp < 50)
        far, n_far = wr(pov.dist >= 20)
        close, n_close = wr(pov.dist < 10)
        my_n = nades[nades.thrower == s]
        fl = my_n[my_n.type == "flash"]
        rt = rank.get(s, (None, None, None))
        kills, dths = len(k_), len(d_)
        sh = shoot.get(s, {})
        xs = xh.get(s, [])
        rows.append({
            "match": mid, "map": hdr.get("map_name"), "steamid": str(s), "name": pl["name"], "rounds": n_rounds,
            "rank_type": rt[0], "rank": rt[2] or rt[1] or None,
            "kills": kills, "deaths": dths, "assists": len(a_),
            "adr": float(enemy_hurt[enemy_hurt.attacker_steamid == s].real.sum() / max(n_rounds, 1)),
            "hs_pct": float(k_.headshot.mean() * 100) if kills else None,
            "traded_pct": float(d_.traded.mean() * 100) if dths else None,
            "open_won": int(k_.opening.sum()), "open_lost": int(d_.opening.sum()),
            "nades_unused": unused.get(s, 0), "nades_owned": bought.get(s, 0),
            "flashes": int(len(fl)), "flash_enemies": int(fl.enemies_blind.fillna(0).sum()) if len(fl) else 0,
            "flash_mates": int(fl.mates_blind.fillna(0).sum()) if len(fl) else 0,
            "util_dmg": float(my_n.damage.fillna(0).sum()) if "damage" in my_n else 0.0,
            "drops_missed": drops.get(s, 0),
            "early_deaths": int((d_.t <= 20).sum()), "last_alive_deaths": int((d_.victim_mates_alive == 0).sum()),
            "hold_win": hold, "n_hold": n_hold, "peek_win": peek, "n_peek": n_peek,
            "lowhp_win": low, "n_lowhp": n_low, "far_win": far, "n_far": n_far, "close_win": close, "n_close": n_close,
            "flash_duels": int(pov.oppfl.fillna(False).astype(bool).sum()), "duels": int(len(pov)),
            "xhair": float(np.median(xs)) if len(xs) >= 5 else None, "n_xhair": len(xs),
            **sh,
        })
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    df.to_parquet(os.path.join(OUT, f"{mid}.parquet"))
    return df


def run_all(force=False):
    done = 0
    for mid in sorted(os.listdir(config.DEEP)):
        if not os.path.exists(os.path.join(config.DEEP, mid, "meta.json")) or not os.path.exists(os.path.join(config.CACHE, f"{mid}.dem")):
            continue
        if not force and os.path.exists(os.path.join(OUT, f"{mid}.parquet")):
            continue
        try:
            extract(mid)
            done += 1
            print(f"[{mid}] population OK", flush=True)
        except Exception as e:
            print(f"[{mid}] population ERROR {e}", flush=True)
    return done


def load():
    fs = [os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith(".parquet")] if os.path.exists(OUT) else []
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run_all("--force" in sys.argv)
    df = load()
    print(len(df), "player-match rows,", df.steamid.nunique() if len(df) else 0, "players")
