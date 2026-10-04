"""Reference population benchmarks: where a player stands versus every player of every analyzed demo."""
import numpy as np
import pandas as pd

import population

# metric -> (label, higher_is_better, unit)
METRICS = {
    "traded_pct": ("deaths traded by a teammate", True, "%"),
    "nades_unused_24": ("grenades that died with you per match (24 rounds)", False, ""),
    "flash_eff": ("enemies blinded per flash", True, ""),
    "flash_mates_rate": ("teammates blinded per flash", False, ""),
    "flash_duels_pct": ("duels against a flashed enemy", True, "%"),
    "pistol_moving": ("pistol shots fired while moving", False, "%"),
    "rifle_moving": ("rifle shots fired while moving", False, "%"),
    "b1_hit": ("1st bullet hitting (rifle)", True, "%"),
    "b9_hit": ("bullets 9+ hitting (rifle)", True, "%"),
    "xhair": ("crosshair offset before the duel", False, "°"),
    "hold_win": ("duels won holding", True, "%"),
    "peek_win": ("duels won peeking", True, "%"),
    "lowhp_win": ("duels won under 50 HP", True, "%"),
    "close_win": ("duels won under 10 m", True, "%"),
    "far_win": ("duels won beyond 20 m", True, "%"),
    "open_win": ("opening duels won", True, "%"),
    "early_death_pct": ("deaths before 20 s", False, "%"),
    "last_alive_pct": ("deaths as the last one alive", False, "%"),
    "adr": ("damage per round", True, ""),
    "hs_pct": ("headshot kills", True, "%"),
    "kd": ("kills per death", True, ""),
}
# rare events, pooled over each player's matches (a rate per match would be 0 or 100 %):
# metric -> (numerator, denominator, minimum denominator, label, higher_is_better, unit)
POOLED = {
    "clutch_win_pct": ("clutch_won", "clutch_n", 4, "1v2+ clutches won", True, "%"),
    "clutch_multi_pct": ("clutch_multi", "clutch_n", 4, "1v2+ clutches where 2+ enemies see you at once", False, "%"),
    "flash_used_pct": ("flash_used", "flash_blind", 8, "enemies you flash that your team hits while blind", True, "%"),
    "untraded_pct": ("untraded_n", "dead_n", 15, "deaths without impact (not traded, no damage of yours)", False, "%"),
}


def derive(df):
    df = df.copy()
    r = df.rounds.clip(lower=1)
    df["nades_unused_24"] = df.nades_unused / r * 24
    df["flash_eff"] = np.where(df.flashes >= 3, df.flash_enemies / df.flashes.clip(lower=1), np.nan)
    df["flash_mates_rate"] = np.where(df.flashes >= 3, df.flash_mates / df.flashes.clip(lower=1), np.nan)
    df["flash_duels_pct"] = np.where(df.duels >= 8, df.flash_duels / df.duels.clip(lower=1) * 100, np.nan)
    op = df.open_won + df.open_lost
    df["open_win"] = np.where(op >= 2, df.open_won / op.clip(lower=1) * 100, np.nan)
    df["early_death_pct"] = np.where(df.deaths >= 5, df.early_deaths / df.deaths.clip(lower=1) * 100, np.nan)
    df["last_alive_pct"] = np.where(df.deaths >= 5, df.last_alive_deaths / df.deaths.clip(lower=1) * 100, np.nan)
    df["kd"] = df.kills / df.deaths.clip(lower=1)
    for m, n in (("hold_win", "n_hold"), ("peek_win", "n_peek"), ("lowhp_win", "n_lowhp"), ("close_win", "n_close"), ("far_win", "n_far")):
        df.loc[df[n] < 4, m] = np.nan
    df.loc[df.pistol_shots < 8, "pistol_moving"] = np.nan
    df.loc[df.rifle_shots < 20, "rifle_moving"] = np.nan
    df.loc[df.b9_shots < 10, "b9_hit"] = np.nan
    df.loc[df.b1_shots < 8, "b1_hit"] = np.nan
    return df


def load():
    df = population.load()
    if not len(df):
        return df
    df = df[(df.rounds >= 12) & ((df.kills + df.deaths) >= 8)]
    return derive(df)


def player_values(pop, steamid):
    """The player's value per metric, pooled over their matches (weighted by rounds)."""
    me = pop[pop.steamid == str(steamid)]
    out = {}
    for m in METRICS:
        s = me[[m, "rounds"]].dropna()
        out[m] = float(np.average(s[m], weights=s.rounds)) if len(s) else None
    return out, me


def benchmarks(steamid):
    pop = load()
    if not len(pop):
        return None
    vals, me = player_values(pop, steamid)
    others = pop[pop.steamid != str(steamid)]
    # competitive map rank (1-18): the player's median rank, and players ranked 2+ above
    my_rank = me[(me.rank_type == 12) & me["rank"].notna()]["rank"].median() if len(me) else None
    comp = others[(others.rank_type == 12) & others["rank"].notna() & (others["rank"] > 0)]
    higher = comp[comp["rank"] >= (my_rank or 0) + 2] if my_rank and my_rank > 0 else comp.iloc[0:0]
    same = comp[(comp["rank"] - (my_rank or 0)).abs() <= 1] if my_rank and my_rank > 0 else comp.iloc[0:0]
    res = {"n_rows": int(len(others)), "n_players": int(others.steamid.nunique()), "n_matches": int(pop.match.nunique()),
           "my_rank": None if my_rank is None or pd.isna(my_rank) else int(my_rank),
           "n_higher": int(higher.steamid.nunique()), "n_same": int(same.steamid.nunique()), "metrics": {}}
    for m, (label, hib, unit) in METRICS.items():
        col = others[m].dropna()
        if len(col) < 15:
            continue
        v = vals.get(m)
        pct = None
        if v is not None:
            pct = float((col < v).mean() * 100) if hib else float((col > v).mean() * 100)  # 100 = best
        hi = higher[m].dropna()
        sm = same[m].dropna()
        res["metrics"][m] = {"label": label, "higher_better": hib, "unit": unit, "you": v, "percentile": pct,
                             "median": float(col.median()), "p25": float(col.quantile(.25)), "p75": float(col.quantile(.75)),
                             "good": float(col.quantile(.75 if hib else .25)), "n": int(len(col)),
                             "higher_rank_median": float(hi.median()) if len(hi) >= 8 else None,
                             "same_rank_median": float(sm.median()) if len(sm) >= 8 else None}
    cols = sorted({c for v in POOLED.values() for c in v[:2]} & set(pop.columns))
    if cols:
        g = pop.groupby("steamid")[cols].sum(min_count=1)
        prank = pop[(pop.rank_type == 12) & pop["rank"].notna() & (pop["rank"] > 0)].groupby("steamid")["rank"].median()
        me_ = str(steamid)
        for m, (a, b, mn, label, hib, unit) in POOLED.items():
            if a not in g or b not in g:
                continue
            ok = g[b] >= mn
            vals = (g.loc[ok, a] / g.loc[ok, b] * 100).astype(float)
            col = vals.drop(me_, errors="ignore")
            if len(col) < 15:
                continue
            v = float(vals[me_]) if me_ in vals.index else None
            pct = None if v is None else float((col < v).mean() * 100) if hib else float((col > v).mean() * 100)
            rk = prank.reindex(col.index)
            hi = col[rk >= my_rank + 2] if my_rank and my_rank > 0 else col.iloc[0:0]
            sm = col[(rk - my_rank).abs() <= 1] if my_rank and my_rank > 0 else col.iloc[0:0]
            res["metrics"][m] = {"label": label, "higher_better": hib, "unit": unit, "you": v, "percentile": pct,
                                 "median": float(col.median()), "p25": float(col.quantile(.25)), "p75": float(col.quantile(.75)),
                                 "good": float(col.quantile(.75 if hib else .25)), "n": int(len(col)),
                                 "n_you": float(g.loc[me_, b]) if me_ in g.index and g.loc[me_, b] == g.loc[me_, b] else 0.0,
                                 "higher_rank_median": float(hi.median()) if len(hi) >= 8 else None,
                                 "same_rank_median": float(sm.median()) if len(sm) >= 8 else None}
    return res
