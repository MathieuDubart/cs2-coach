"""What the T side does, round after round, in every demo of the base: which site they hit and when, how many go,
where they come from, where the first duel happens, and what they did on the previous rounds of the half.

Feeds the CT side of the in-game sheet: the odds of A or B on the next round, from the kind of round (pistol,
round 2, eco, force, full) and from what the T did before (the same site after a win, the other one after a loss...).
Writes out/population/tside/<match>.parquet (one row per round).
Usage: python tside.py
"""
import os
import sys

import numpy as np
import pandas as pd

import config
import midround

OUT = os.path.join(config.OUT, "population", "tside")
ZONES = os.path.join(config.OUT, "population", "tside_zones.json")   # which zones lead to which site, per map
LANES = os.path.join(config.OUT, "population", "tside_lanes.json")   # how each site is entered, per map (lanes.py)
RUSH = 30.0          # site taken in the first 30 s (timer above 1:25): a rush
LATE = 75.0          # site taken after 75 s (timer under 0:40): a late hit
LONE = 1000.0        # a T with no teammate within 1000 units (about 25 m) is alone
ROUND_TIME = 115.0
DYN_FR = {"rush": "rush", "fast": "fast push by 1-2 Ts", "exec": "execute", "late": "late hit", "none": "no attack"}
CONTEXTS = ["pistol", "r2_win", "r2_loss", "eco", "force", "full"]
CTX_FR = {"pistol": "Pistol round", "r2_win": "Round 2, Ts won the pistol", "r2_loss": "Round 2, Ts lost the pistol",
          "eco": "T eco", "force": "T force-buy", "full": "T full buy"}
BUY_FR = {"eco": "eco", "force": "force-buy", "full": "full buy"}


def humanize(z, mp=None):
    from map_analysis import humanize as h
    return h(z, mp) if z else z


def five_v_five(R):
    """Wingman demos (2v2, one site) say nothing about 5v5 habits."""
    return len(R) and R.T_n.max() >= 4 and R.CT_n.max() >= 4


def _paths(T_, kd):
    """Every T's way through the map in the round: 'zone@t>zone@t>...>†@t' (raw place names, a change of zone at a
    time, † when killed), one T per ';'. Tells the route of an attack: through a main, through mid, or both."""
    dead = {}
    if len(kd) and "victim" in kd:
        for v, t, s in zip(kd.victim, kd.t, kd.victim_side):
            if s == "T" and v == v:
                dead.setdefault(v, float(t))
    out = []
    for sid, x in T_.sort_values("t").groupby("steamid"):
        seq, last = [], None
        for z, t in zip(x.zone, x.t):
            if isinstance(z, str) and z and z != "?" and z != last:
                seq.append(f"{z}@{t:.0f}")
                last = z
        if sid in dead:
            seq.append(f"†@{dead[sid]:.0f}")
        if seq:
            out.append(">".join(seq))
    return ";".join(out) or None


def analyze(ddir):
    """-> one row per round: the site the T hit (A, B or '-' when they never did), when, with how many."""
    meta = midround._meta(ddir)
    mname = meta.get("map")
    sites = midround.site_centers().get(mname)
    fr = os.path.join(ddir, "rounds.parquet")
    if not sites or not os.path.exists(fr):
        return pd.DataFrame()
    R = pd.read_parquet(fr).sort_values("round")
    if not five_v_five(R):
        return pd.DataFrame()
    S = pd.read_parquet(os.path.join(ddir, "samples.parquet"), columns=["steamid", "side", "round", "t", "X", "Y", "Z", "zone", "health"])
    S = S[(S.steamid != 0) & (S.health > 0)]
    fd = os.path.join(ddir, "duels.parquet")
    dcols = ["round", "t", "victim", "killer_side", "victim_side", "victim_zone", "killer_zone", "victim_mate_dist", "killer_mate_dist", "traded"]
    D = pd.read_parquet(fd).reindex(columns=dcols) if os.path.exists(fd) else pd.DataFrame()
    # teams: the T of the first round are team a, whatever side they play later
    first = S[S["round"] == R["round"].min()]
    team_a = set(first[first.side == "T"].steamid)
    team_b = set(first[first.side == "CT"].steamid)
    rows, score, prev_team, half = [], {"a": 0, "b": 0}, None, -1
    rih = 0
    for _, r in R.iterrows():
        rnd = int(r["round"])
        g = S[S["round"] == rnd]
        tset = set(g[g.side == "T"].steamid)
        if not tset:
            continue
        team = "a" if len(tset & team_a) >= len(tset & team_b) else "b"
        if team != prev_team:  # sides swapped: a new half (or overtime half)
            half, rih, prev_team = half + 1, 0, team
        rih += 1
        T_ = g[g.side == "T"]
        # the site is the game's own area (nav place BombsiteA / BombsiteB): exact, even on stacked sites (Nuke)
        in_site = {L: T_[T_.zone == f"Bombsite{L}"] for L in ("A", "B")}

        def first_n(x, k=2, lo=0.0, hi=1e9):
            x = x[(x.t >= lo) & (x.t <= hi)]
            c = x.groupby("t").steamid.nunique()
            ok = c[c >= k]
            return float(ok.index[0]) if len(ok) else None
        plant_site = r.get("plant_site") if r.get("plant_site") in ("A", "B") else None
        plant_t = float(r.plant_t) if plant_site and pd.notna(r.get("plant_t")) else None
        hit = None
        if plant_site:
            x = in_site[plant_site]
            ft = first_n(x, 2, plant_t - 25, plant_t)
            if ft is None:
                ft = first_n(x, 1, plant_t - 25, plant_t)
            hit = (plant_site, ft if ft is not None else max(plant_t - 3, 0.0))
        else:
            cand = [(x, L_) for x, L_ in ((first_n(in_site["A"]), "A"), (first_n(in_site["B"]), "B")) if x is not None]
            if cand:
                t0, L_ = min(cand)
                hit = (L_, t0)
        kd = D[D["round"] == rnd].sort_values("t") if len(D) else D
        entered = hit is not None
        # T fights after the first 12 s (before they got in): tells the side of an attack stopped before the site
        ev = kd[(kd.t >= 12) & (kd.t < (hit[1] if hit else 1e9))] if len(kd) else kd
        t_events = [(z, float(t)) for z, t in zip(ev[ev.victim_side == "T"].victim_zone, ev[ev.victim_side == "T"].t)] +                    [(z, float(t)) for z, t in zip(ev[ev.killer_side == "T"].killer_zone, ev[ev.killer_side == "T"].t)] if len(ev) else []
        rec = {"map": mname, "round": rnd, "half": half, "rih": rih, "t_team": team, "entered": entered,
               "score_t": score[team], "score_ct": score["b" if team == "a" else "a"],
               "T_buy": r.T_buy, "CT_buy": r.CT_buy, "winner": r.winner, "reason": r.reason,
               "T_won": r.winner == "T", "plant_site": plant_site, "plant_t": plant_t, "end_t": float(r.end_t) if pd.notna(r.end_t) else None,
               "site": "-", "hit_t": None, "n_exec": None, "n_push": None, "lurk_other": None, "approaches": None, "pre_zones": None,
               "t_events": ";".join(f"{z}@{t:.1f}" for z, t in t_events if isinstance(z, str) and z) or None,
               "first_zone": None, "first_t": None, "first_t_side_won": None, "t_alive_hit": None, "ct_alive_hit": None,
               "fc_alone": None, "t_deaths": None, "ct_deaths": None, "bunch_t": None, "bunch_zone": None,
               "t_paths": _paths(T_, kd)}
        if len(kd):
            k0 = kd.iloc[0]
            # the T of the first duel: alone (no teammate within LONE units) or with others
            md = k0.victim_mate_dist if k0.victim_side == "T" else k0.killer_mate_dist if k0.killer_side == "T" else None
            rec.update(first_zone=humanize(k0.victim_zone, mname), first_t=float(k0.t), first_t_side_won=k0.killer_side == "T",
                       fc_alone=bool(md > LONE) if md is not None and md == md else None)
            # who died where and when: a T killed alone and not traded is flagged
            td = kd[kd.victim_side == "T"]
            lone = (td.victim_mate_dist.fillna(0) > LONE) & ~td.traded.fillna(False).astype(bool)
            rec["t_deaths"] = ";".join(f"{humanize(z, mname) if isinstance(z, str) and z != '?' else '?'}@{t:.1f}@{int(l)}"
                                       for z, t, l in zip(td.victim_zone, td.t, lone)) or None
            cd = kd[kd.victim_side == "CT"]
            rec["ct_deaths"] = ";".join(f"{humanize(z, mname) if isinstance(z, str) and z != '?' else '?'}@{t:.1f}"
                                        for z, t in zip(cd.victim_zone, cd.t)) or None
            # 3 Ts down within 10 s: the push died there
            tt = td.t.to_numpy()
            for i in range(len(tt) - 2):
                if tt[i + 2] - tt[i] <= 10:
                    zz = td[(td.t >= tt[i]) & (td.t <= tt[i] + 10)].victim_zone.dropna()
                    rec.update(bunch_t=float(tt[i]), bunch_zone=humanize(zz.mode().iloc[0], mname) if len(zz) else None)
                    break
        if hit:
            site, ht = hit
            other = "B" if site == "A" else "A"
            x = in_site[site]
            hitters = set(x[(x.t >= ht) & (x.t <= ht + 6)].steamid)
            # where the players who took the site came from, 3 to 6 s earlier
            skip = T_.zone.str.startswith("Bombsite") | T_.zone.isin(["?", "TSpawn", "CTSpawn"])
            before = T_[T_.steamid.isin(hitters) & (T_.t >= ht - 6) & (T_.t <= ht - 3) & ~skip]
            came = before.groupby("steamid").zone.agg(lambda z: z.mode().iloc[0]) if len(before) else pd.Series(dtype=object)
            # every zone each T went through in the 20 s before: learns which zones lead to which site
            pre = T_[(T_.t >= ht - 20) & (T_.t <= ht - 2) & ~skip]
            pre_zones = ";".join(",".join(sorted(set(z))) for _, z in pre.groupby("steamid").zone) if len(pre) else None
            # a T still next to the other site when this one is taken (lurk, or a split)
            oc, orad = sites[other]["c"], sites[other]["r"]
            at = T_[(T_.t >= ht - 1) & (T_.t <= ht + 1) & ~T_.steamid.isin(hitters)]
            lurk = bool((midround._dist(at.X.values, at.Y.values, at.Z.values, oc) <= orad).any()) if len(at) else False
            deaths_before = kd[kd.t < ht] if len(kd) else kd
            # the Ts of the push: the ones who got in, plus the ones killed on the way in the last 10 s
            died_on_way = int(((deaths_before.victim_side == "T") & (deaths_before.t >= ht - 10)).sum()) if len(kd) else 0
            rec.update(site=site, hit_t=round(ht, 1), n_exec=int(len(hitters)), n_push=int(len(hitters)) + died_on_way,
                       lurk_other=lurk, pre_zones=pre_zones,
                       approaches=",".join(humanize(z, mname) for z in came.values) if len(came) else None,
                       t_alive_hit=int(r.T_n) - int((deaths_before.victim_side == "T").sum()) if len(kd) else int(r.T_n),
                       ct_alive_hit=int(r.CT_n) - int((deaths_before.victim_side == "CT").sum()) if len(kd) else int(r.CT_n))
        rows.append(rec)
        if r.winner in ("T", "CT"):
            score[team if r.winner == "T" else ("b" if team == "a" else "a")] += 1
    return pd.DataFrame(rows)


def _outdated(f):
    """A file written by an older version (no deaths per round yet) is analyzed again."""
    import pyarrow.parquet as pq
    try:
        names = pq.read_schema(f).names
    except Exception:
        return True
    return "map" in names and ("t_deaths" not in names or "t_paths" not in names)


def run_all(log=print, force=False):
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for mid in os.listdir(config.DEEP):
        d = os.path.join(config.DEEP, mid)
        f = os.path.join(OUT, f"{mid}.parquet")
        src = os.path.join(d, "rounds.parquet")
        if not os.path.exists(src) or not os.path.exists(os.path.join(d, "samples.parquet")):
            continue
        if not force and os.path.exists(f) and os.path.getmtime(f) >= os.path.getmtime(src) and not _outdated(f):
            continue
        try:
            analyze(d).to_parquet(f)
            n += 1
        except Exception as e:
            log(f"[{mid}] T side: {e}")
    return n


def load():
    fs = [os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith(".parquet")] if os.path.exists(OUT) else []
    dfs = []
    for f in fs:
        x = pd.read_parquet(f)
        if len(x):
            x["match"] = os.path.basename(f)[:-8]
            dfs.append(x)
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    zs = zone_sites(df)
    try:   # kept for the round-by-round story of a single match (no need to load the whole base)
        import json
        tmp = ZONES + f".{os.getpid()}.tmp"
        json.dump(zs, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, ZONES)
    except OSError:
        pass
    df = _sequences(_dynamics(_directions(df, zs=zs)))
    return _with_plays(df)


def _with_plays(df):
    """Lanes of every site and the play of every round (lanes.py); kept on disk for single matches."""
    import json
    import lanes as LN
    try:
        G = LN.geo()
        ls, mem = LN.learn(df, G)
        df = LN.classify(df, ls, G, mem)
        tmp = LANES + f".{os.getpid()}.tmp"
        json.dump(ls, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, LANES)
    except Exception as e:   # the rest of the reading stays usable
        print(f"plays unavailable ({e})")
    return df


def _lanes():
    import json
    try:
        return json.load(open(LANES, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def zone_sites(df):
    """For every zone of a map: in how many rounds the T who went through it then got into A, or into B."""
    out = {}
    ent = df[df.entered.fillna(False).astype(bool) & df.site.isin(["A", "B"])]
    for mp, g in ent.groupby("map"):
        cnt = {}
        for site, pz in zip(g.site, g.pre_zones):
            for z in {z for p in str(pz or "").split(";") for z in p.split(",") if z}:
                c = cnt.setdefault(z, [0, 0])
                c[site == "B"] += 1
        out[mp] = {z: c for z, c in cnt.items() if sum(c) >= 15}
    return out


def _directions(df, lean=0.7, zs=None):
    """An attack stopped before the site still has a side: where the T fought, when those zones lead to one site
    in at least 70 % of the rounds where the T got in. Also counts the fights of that push in its first 10 s."""
    zs = zone_sites(df) if zs is None else zs
    site, when, many = df.site.tolist(), [None] * len(df), [None] * len(df)
    for i, (mp, ent, evs) in enumerate(zip(df["map"], df.entered, df.t_events)):
        if ent or not isinstance(evs, str):
            continue
        votes = {"A": [], "B": []}
        for e in evs.split(";"):
            z, _, t = e.rpartition("@")
            if z in ("BombsiteA", "BombsiteB"):
                votes[z[-1]].append(float(t))
                continue
            c = zs.get(mp, {}).get(z)
            if c:
                pA = c[0] / sum(c)
                if pA >= lean:
                    votes["A"].append(float(t))
                elif pA <= 1 - lean:
                    votes["B"].append(float(t))
        top = max(votes, key=lambda k: len(votes[k]))
        if len(votes[top]) >= 2 and len(votes[top]) > len(votes["B" if top == "A" else "A"]):
            t0 = min(votes[top])
            site[i], when[i], many[i] = top, t0, sum(1 for t in votes[top] if t <= t0 + 10)
    df["site"] = site
    df["stop_t"] = when
    df["stop_n"] = many
    df["entered"] = df.entered.fillna(False).astype(bool)
    return df


def _deaths_list(s, lone_flag=True):
    """'zone@t@1;...' -> [(zone, t, alone)]"""
    out = []
    for e in str(s or "").split(";"):
        p = e.split("@")
        if len(p) >= 2:
            try:
                out.append((p[0], float(p[1]), p[2] == "1" if lone_flag and len(p) > 2 else False))
            except ValueError:
                pass
    return out


def _dynamics(df):
    """The shape of each attack, as the CT side sees it in the kill feed: a rush (3+ Ts on a site in the first 30 s),
    a fast push by 1-2 Ts, an execute, a late hit (after 75 s), or no attack; and the Ts lost alone before it
    (no teammate within 1000 units, not traded)."""
    if "t_deaths" not in df:
        df["t_deaths"] = None
    ent = df.entered.to_numpy(dtype=bool)
    ht = pd.to_numeric(df.hit_t, errors="coerce").to_numpy(dtype=float)
    stt = pd.to_numeric(df.stop_t, errors="coerce").to_numpy(dtype=float)
    commit = np.where(ent, ht, stt)
    push = df.n_push if "n_push" in df else df.n_exec
    grp = np.where(ent, pd.to_numeric(push, errors="coerce").to_numpy(dtype=float),
                   pd.to_numeric(df.get("stop_n"), errors="coerce").to_numpy(dtype=float) if "stop_n" in df else np.nan)
    has = df.site.isin(["A", "B"]).to_numpy() & ~np.isnan(commit)
    dyn = np.where(~has, "none", np.where(commit <= RUSH, np.where(np.nan_to_num(grp) >= 3, "rush", "fast"),
                                          np.where(commit <= LATE, "exec", "late")))
    lone_n, lone_zone, lone_t = [], [], []
    for c, s in zip(commit, df.t_deaths):
        lim = c if c == c else 60.0
        lo = [(z, t) for z, t, a in _deaths_list(s) if a and t < lim]
        lone_n.append(len(lo))
        lone_zone.append(lo[0][0] if lo else None)
        lone_t.append(lo[0][1] if lo else None)
    df["commit"], df["grp"], df["dyn"] = commit, grp, dyn
    df["lone_n"], df["lone_zone"], df["lone_t"] = lone_n, lone_zone, lone_t
    return df


def _context(r):
    if r.rih == 1:
        return "pistol"
    if r.rih == 2 and r.pistol_won is not None:
        return "r2_win" if r.pistol_won else "r2_loss"
    return r.T_buy if r.T_buy in ("eco", "force", "full") else None


def _sequences(df):
    """What the same T team did before, in the same half: last site, won or lost, streak, how often each site."""
    df = df.sort_values(["match", "half", "round"]).reset_index(drop=True)
    cols = {k: [] for k in ("prev_site", "prev_won", "streak", "nA", "nB", "pistol_won", "losses", "prev_dyn", "prev_lone",
                            "rush_before", "n_before")}
    for _, g in df.groupby(["match", "half"], sort=False):
        last_site, last_won, streak, nA, nB, pw, losses = None, None, 0, 0, 0, None, 0
        last_dyn, last_lone, rushes, nb = None, None, 0, 0
        for _, r in g.iterrows():
            cols["prev_site"].append(last_site)
            cols["prev_won"].append(last_won)
            cols["streak"].append(streak)
            cols["nA"].append(nA)
            cols["nB"].append(nB)
            cols["pistol_won"].append(pw)
            cols["losses"].append(losses)
            cols["prev_dyn"].append(last_dyn)
            cols["prev_lone"].append(last_lone)
            cols["rush_before"].append(rushes)
            cols["n_before"].append(nb)
            last_dyn, last_lone = r.get("dyn"), bool(r.get("lone_n") or 0)
            rushes += r.get("dyn") == "rush"
            nb += 1
            if r.rih == 1:
                pw = bool(r.T_won)
            losses = 0 if r.T_won else losses + 1
            last_won = bool(r.T_won)
            if r.site in ("A", "B"):
                streak = streak + 1 if r.site == last_site else 1
                last_site = r.site
                nA += r.site == "A"
                nB += r.site == "B"
            else:
                last_site, streak = "-", 0
    for k, v in cols.items():
        df[k] = v
    df["ctx"] = df.apply(_context, axis=1)
    return df


# ---------- what the CT side can expect ----------
def _pct(x):
    return int(round(100 * x)) if x == x else None


def _timer(t):
    left = max(0, ROUND_TIME - t)
    return f"{int(left // 60)}:{int(left % 60):02d}"


def _profile(g):
    """Odds of A / B / no hit, rushes, how many go in, where from, first duel."""
    n = len(g)
    hits = g[g.site.isin(["A", "B"]) & g.entered]
    out = {"n": int(n), "A": _pct((g.site == "A").mean()), "B": _pct((g.site == "B").mean()), "none": _pct((g.site == "-").mean()),
           "t_win": _pct(g.T_won.mean())}
    if len(hits) >= 5:
        out["rush"] = _pct((hits.hit_t <= RUSH).mean())
        out["hit_timer"] = _timer(hits.hit_t.median())
        out["lurk"] = _pct(hits.lurk_other.mean())
        for L in ("A", "B"):
            h = hits[hits.site == L]
            if len(h) >= 5:
                ap = pd.Series([z for v in h.approaches.dropna() for z in v.split(",") if z]).value_counts(normalize=True)
                out[f"{L}_detail"] = {"n": int(len(h)), "timer": _timer(h.hit_t.median()), "rush": _pct((h.hit_t <= RUSH).mean()),
                                      "t_win": _pct(h.T_won.mean()),
                                      "from": [{"zone": z, "pct": _pct(p)} for z, p in ap.head(2).items() if p >= 0.15]}
    fz = g.first_zone.dropna().value_counts(normalize=True)
    if len(g.first_zone.dropna()) >= 8:
        out["first"] = [{"zone": z, "pct": _pct(p)} for z, p in fz.head(3).items()]
        out["first_timer"] = _timer(g.first_t.dropna().median())
    if "dyn" in g:   # the shape of the attacks, and how often they lose a T alone before it
        vc = g.dyn.value_counts(normalize=True)
        out["dyn"] = {k: _pct(vc.get(k, 0.0)) for k in DYN_FR}
        out["rush_all"] = out["dyn"]["rush"]
        out["lone"] = _pct((g.lone_n > 0).mean())
    return out


def _switch_table(df):
    """After a hit on one site, how often the next hit is on the other one, by result and streak."""
    h = df[df.site.isin(["A", "B"]) & df.prev_site.isin(["A", "B"])]
    out = []
    for label, sel in (("after a site take they won", h.prev_won == True),
                       ("after a site take they lost", h.prev_won == False),
                       ("after 2+ takes of the same site, the last one lost", (h.streak >= 2) & (h.prev_won == False)),
                       ("after 2+ takes of the same site, the last one won", (h.streak >= 2) & (h.prev_won == True))):
        x = h[sel]
        if len(x) >= 15:
            out.append({"label": label, "n": int(len(x)), "switch": _pct((x.site != x.prev_site).mean())})
    return out


def _after_table(g, min_n=12):
    """Where the next attack goes, after an attack on A or B won or lost (and after two in a row on the same site)."""
    out = []
    d = g[g.prev_site.isin(["A", "B"])]
    for last in ("A", "B"):
        for won in (True, False):
            for two in (False, True):
                x = d[(d.prev_site == last) & (d.prev_won == won) & ((d.streak >= 2) if two else True)]
                if len(x) >= min_n:
                    out.append({"last": last, "won": won, "twice": two, "n": int(len(x)),
                                "A": _pct((x.site == "A").mean()), "B": _pct((x.site == "B").mean()), "none": _pct((x.site == "-").mean())})
    return out


def _fit(X, y, off, l2=1.0, it=30):
    """Logistic regression with an offset (the map's own odds), a little ridge, Newton steps."""
    b = np.zeros(X.shape[1])
    for _ in range(it):
        z = off + X @ b
        p = 1 / (1 + np.exp(-z))
        W = p * (1 - p)
        g = X.T @ (y - p) - l2 * b
        H = X.T @ (X * W[:, None]) + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        b += step
        if np.abs(step).max() < 1e-6:
            break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return b, se


FEATURES = ["repeat_won", "repeat_lost", "streak2", "pref"]
FEATURES_FR = {"repeat_won": "the same site after a take they won", "repeat_lost": "the same site after a take they lost",
               "streak2": "the same site after 2 takes in a row or more", "pref": "the site they took most this half"}


def _features(d):
    """+1 pushes toward A, -1 toward B."""
    sgn = np.where(d.prev_site == "A", 1.0, np.where(d.prev_site == "B", -1.0, 0.0))
    won = d.prev_won.fillna(False).astype(bool).values
    tot = (d.nA + d.nB).values.astype(float)
    return np.column_stack([sgn * won, sgn * ~won, sgn * (d.streak.values >= 2),
                            np.where(tot > 0, (d.nA.values - d.nB.values) / np.sqrt(np.maximum(tot, 1)), 0.0)])


def model(df):
    """A or B on the next round: the map's odds for this kind of round, moved by what the T did before (fit on every
    map of the base together, since 'going back after a win' does not depend on the map)."""
    h = df[df.site.isin(["A", "B"]) & df.ctx.notna()].copy()
    if len(h) < 200:
        return None
    base = {}
    for (mp, c), g in h.groupby(["map", "ctx"]):
        base[(mp, c)] = ((g.site == "A").sum() + 3 * (h[h["map"] == mp].site == "A").mean(), len(g) + 3)
    pA = np.array([base[(m, c)][0] / base[(m, c)][1] for m, c in zip(h["map"], h.ctx)])
    off = np.log(pA / (1 - pA))
    X = _features(h)
    y = (h.site == "A").values.astype(float)
    b, se = _fit(X, y, off)
    keep = {k: round(float(v), 3) if abs(v) >= 1.5 * e else 0.0 for k, v, e in zip(FEATURES, b, se)}
    return {"beta": keep, "raw": {k: round(float(v), 3) for k, v in zip(FEATURES, b)}, "se": {k: round(float(v), 3) for k, v in zip(FEATURES, se)},
            "n": int(len(h)), "fr": FEATURES_FR}


TEMPO = ["rush_won", "half_excess"]
TEMPO_FR = {"rush_won": "they rushed and won the last round", "half_excess": "they rushed more than usual this half"}


def _rush_rates(df):
    """P(rush) per map, and per map and kind of round (pulled toward the map's rate when there are few rounds)."""
    r_map = df.groupby("map").dyn.agg(lambda s: (s == "rush").mean()).to_dict()
    r_ctx = {}
    for (mp, c), g in df[df.ctx.notna()].groupby(["map", "ctx"]):
        r_ctx[(mp, c)] = float(((g.dyn == "rush").sum() + 10 * r_map[mp]) / (len(g) + 10))
    return r_map, r_ctx


def _tempo_x(d, r_map):
    """The features of the tempo model: a rush they won last round, and how many more rushes than the map's usual
    rate they did in the half so far (0 before the 3rd round of the half)."""
    rm = d["map"].map(r_map).fillna(0.2).to_numpy(dtype=float)
    nb = d.n_before.to_numpy(dtype=float)
    rw = ((d.prev_dyn == "rush") & d.prev_won.fillna(False).astype(bool)).to_numpy(dtype=float)
    ex = np.where(nb >= 2, (d.rush_before.to_numpy(dtype=float) - nb * rm) / np.sqrt(np.maximum(nb, 1)), 0.0)
    return np.column_stack([rw, ex])


def tempo_model(df):
    """Will the T rush this round? The map's rate for this kind of round, moved by what this team did in the half
    (fit on every map together). Rushes do not predict the next site, but a team that rushes keeps rushing."""
    if "dyn" not in df:
        return None
    d = df[(df.n_before >= 1) & df.ctx.notna()]
    if len(d) < 300:
        return None
    r_map, r_ctx = _rush_rates(df)
    p0 = np.clip(np.array([r_ctx[(m, c)] for m, c in zip(d["map"], d.ctx)]), .02, .98)
    off = np.log(p0 / (1 - p0))
    X = _tempo_x(d, r_map)
    y = (d.dyn == "rush").to_numpy(dtype=float)
    b, se = _fit(X, y, off)
    return {"beta": {k: round(float(v), 3) if abs(v) >= 1.5 * e else 0.0 for k, v, e in zip(TEMPO, b, se)},
            "raw": {k: round(float(v), 3) for k, v in zip(TEMPO, b)}, "se": {k: round(float(v), 3) for k, v in zip(TEMPO, se)},
            "n": int(len(d)), "fr": TEMPO_FR}


def alone_gamma(df):
    """A T alone at the first duel (no teammate within 1000 units) is often a lurker or an info player: the team is
    elsewhere. Pooled over every map: how much of the zone's usual lean such a contact keeps
    (1 = the same as a group, 0 = no information, below 0 = the other way)."""
    if "fc_alone" not in df:
        return None
    f = df[df.first_zone.notna() & df.site.isin(["A", "B"]) & df.fc_alone.notna()]
    xs, ys, offs = [], [], []
    lo = lambda p: np.log(p / (1 - p))
    for mp, g in f.groupby("map"):
        alone = g.fc_alone.astype(bool)
        grp = g[~alone]
        if len(grp) < 30:
            continue
        prior = float((grp.site == "A").mean())
        lean = grp.groupby("first_zone").site.agg(lambda s: ((s == "A").sum() + 4 * prior) / (len(s) + 4))
        a = g[alone & g.first_zone.isin(lean.index)]
        if not len(a):
            continue
        pg = a.first_zone.map(lean).clip(.03, .97).to_numpy(dtype=float)
        xs += list(lo(pg) - lo(prior))
        ys += list((a.site == "A").to_numpy(dtype=float))
        offs += [lo(prior)] * len(a)
    if len(xs) < 100:
        return None
    b, se = _fit(np.array(xs)[:, None], np.array(ys), np.array(offs), l2=0.1)
    return {"gamma": round(float(b[0]), 3), "se": round(float(se[0]), 3), "n": len(xs),
            "share": _pct(f.fc_alone.astype(bool).mean())}


def _dyn_after(df):
    """What the same team does on the next round after each kind of attack (every map together)."""
    if "dyn" not in df:
        return None
    d = df[df.prev_dyn.notna() & df.prev_won.notna()]
    if len(d) < 300:
        return None
    rows = []
    for key in ("rush", "fast", "exec", "late", "none"):
        for won in (True, False):
            x = d[(d.prev_dyn == key) & (d.prev_won == won)]
            if len(x) < 40:
                continue
            s = x[x.prev_site.isin(["A", "B"])]
            rows.append({"dyn": key, "won": won, "n": int(len(x)), "rush": _pct((x.dyn == "rush").mean()),
                         "same": _pct((s.site == s.prev_site).mean()) if len(s) >= 30 else None,
                         "other": _pct((s.site.isin(["A", "B"]) & (s.site != s.prev_site)).mean()) if len(s) >= 30 else None})
    lone = []
    for flag in (True, False):
        x = d[(d.prev_lone == flag) & (d.prev_won == False)]
        s = x[x.prev_site.isin(["A", "B"])]
        if len(s) >= 40:
            lone.append({"lone": flag, "n": int(len(s)), "same": _pct((s.site == s.prev_site).mean()), "rush": _pct((x.dyn == "rush").mean())})
    return {"rows": rows, "lone": lone, "base_rush": _pct((d.dyn == "rush").mean()), "dyn_fr": DYN_FR}


def econ_table(df):
    """What the T probably buy, from what the CT side can see: pistol won or lost, last round, losses in a row."""
    out = {}
    d = df[(df.rih >= 3) & df.T_buy.isin(["eco", "force", "full"])]
    for key, sel in (("won", d.prev_won == True), ("lost1", (d.prev_won == False) & (d.losses == 1)),
                     ("lost2", (d.prev_won == False) & (d.losses == 2)), ("lost3", (d.prev_won == False) & (d.losses >= 3))):
        x = d[sel]
        if len(x) >= 20:
            vc = x.T_buy.value_counts(normalize=True)
            out[key] = {k: _pct(vc.get(k, 0.0)) for k in ("eco", "force", "full")}
            out[key]["n"] = int(len(x))
    return out


SUMMARY = os.path.join(config.OUT, "population", "tside_summary.json")
VERSION = 6   # bump when the summary changes shape: the cache is rebuilt


def _stamp():
    fs = [f for f in os.listdir(OUT) if f.endswith(".parquet")] if os.path.exists(OUT) else []
    return f"v{VERSION}-{len(fs)}-{int(max((os.path.getmtime(os.path.join(OUT, f)) for f in fs), default=0))}"


def tendencies(maps, df=None):
    """Per map: odds by kind of round, habits after a win or a loss, and what the live predictor needs."""
    import json
    if df is not None:
        return _tendencies(maps, df)
    try:
        cur = json.load(open(SUMMARY, encoding="utf-8"))
        if cur.get("_stamp") == _stamp():
            cur["maps"] = {m: v for m, v in cur["maps"].items() if m in maps}
            return cur
    except (OSError, ValueError):
        pass
    df = load()
    # every map of the base at once: the cache then serves any player, whatever their maps
    res = _tendencies(sorted(set(df["map"].unique()) | set(maps)) if len(df) else maps, df)
    if res:
        tmp = SUMMARY + f".{os.getpid()}.tmp"
        json.dump(dict(res, _stamp=_stamp()), open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, SUMMARY)   # never a half-written file for the other processes
        res["maps"] = {m: v for m, v in res["maps"].items() if m in maps}
    return res


def _tendencies(maps, df):
    if not len(df):
        return None
    res = {"model": model(df), "econ": econ_table(df), "switch_all": _switch_table(df), "rush_s": RUSH, "late_s": LATE, "maps": {},
           "ctx_fr": CTX_FR, "tempo": tempo_model(df), "alone": alone_gamma(df), "dyn_after": _dyn_after(df), "dyn_fr": DYN_FR}
    r_map, r_ctx = _rush_rates(df) if "dyn" in df else ({}, {})
    dirs = _map_dirs()
    rot = None
    pool = []
    for mp in maps:
        g = df[df["map"] == mp]
        if len(g) < 60:
            continue
        hits = g[g.site.isin(["A", "B"]) & g.ctx.notna()]
        allA = (hits.site == "A").mean() if len(hits) else 0.5
        ctx = {}
        for c in CONTEXTS:
            x = g[g.ctx == c]
            if len(x) >= 8:
                ctx[c] = _profile(x)
                hx = hits[hits.ctx == c]
                ctx[c]["pA_hit"] = round(float(((hx.site == "A").sum() + 3 * allA) / (len(hx) + 3)), 3)
                if (mp, c) in r_ctx:
                    ctx[c]["rush_p"] = round(r_ctx[(mp, c)], 3)
        res["maps"][mp] = {"n_rounds": int(len(g)), "n_matches": int(g.match.nunique()), "all": _profile(g), "ctx": ctx,
                           "after": _after_table(g), "pA_hit": round(float(allA), 3),
                           "rush_p": round(float(r_map[mp]), 3) if mp in r_map else None}
        try:
            res["maps"][mp]["evidence"] = evidence(mp, g, dirs.get(mp, []), pool)
        except Exception as e:  # the rest of the reading stays usable
            print(f"{mp}: in-round evidence unavailable ({e})")
        try:   # plays (rush, split, one lane), what the radar needs, rotations of the CTs toward each site
            import lanes as LN
            if rot is None:
                rot = midround.retake_routes()
            res["maps"][mp]["rotations"] = rot.get(mp)
            ls = _lanes().get(mp)
            cz = ((res["maps"][mp].get("evidence") or {}).get("contact") or {}).get("zones")
            res["maps"][mp]["plays"] = LN.summary(g, ls, cz) if ls else None
            res["maps"][mp]["geo"] = LN.radar(LN.geo(), mp)
        except Exception as e:
            print(f"{mp}: plays unavailable ({e})")
    res["retake_all"] = retake_table(pool)
    return res

# ---------- evidence during the round: what the CT side sees, and what it says about the site ----------
WINDOWS = [("early", 0, 20), ("setup", 20, 40), ("hit", 40, 70), ("late", 70, 999)]
STEP = 5


def _map_dirs():
    by = {}
    for mid in os.listdir(config.DEEP):
        d = os.path.join(config.DEEP, mid)
        m = midround._meta(d).get("map")
        if m:
            by.setdefault(m, []).append(d)
    return by


def _survival(g):
    """Chance that no site has been taken yet at t seconds, for each place the attack ends up going.
    The longer a round goes quiet, the more the late option becomes likely: this is the likelihood of 'still nothing'."""
    ts = list(range(0, 101, STEP))
    out = {"t": ts}
    for site in ("A", "B", "-"):
        x = g[g.site == site]
        if len(x) < 10:
            continue
        if site == "-":
            c = x.end_t.fillna(ROUND_TIME).to_numpy(dtype=float)
        else:
            c = np.where(x.entered.to_numpy(dtype=bool), x.hit_t.to_numpy(dtype=float), x.stop_t.to_numpy(dtype=float))
            c = np.where(np.isnan(c), ROUND_TIME, c)
        out["none" if site == "-" else site] = [round(float((c > t).mean()) + 1e-3, 4) for t in ts]
    return out


def _contact(g, top=8):
    """Where the first duel of the round happens, for each place the attack ends up going (smoothed)."""
    f = g[g.first_zone.notna()]
    if len(f) < 30:
        return None
    zones = f.first_zone.value_counts().head(top).index.tolist()
    res = {"zones": zones, "lik": {}, "lik_g": {}, "t": {}}
    # lik: every first duel; lik_g: only the ones where the T had a teammate close (the user said "2+ Ts")
    grp = f[f.fc_alone.notna() & ~f.fc_alone.fillna(False).astype(bool)] if "fc_alone" in f else f.iloc[0:0]
    for key, src in (("lik", f), ("lik_g", grp)):
        for site in ("A", "B", "-"):
            x = src[src.site == site]
            if len(x) < 10:
                continue
            vc = x.first_zone.where(x.first_zone.isin(zones), "other").value_counts()
            tot = len(x) + len(zones) + 1
            res[key]["none" if site == "-" else site] = {z: round(float((vc.get(z, 0) + 1) / tot), 4) for z in zones + ["other"]}
    for z in zones:
        res["t"][z] = _timer(f[f.first_zone == z].first_t.median())
    return res


def _compass(dx, dy):
    if (dx * dx + dy * dy) ** 0.5 < 14:
        return "center"
    a = np.degrees(np.arctan2(-dy, dx)) % 360   # radar: y goes down
    return ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"][int(((a + 22.5) % 360) // 45)]


def _plants_and_retakes(mp, dirs):
    """Where the bomb goes down on each site (spots on the radar), how the round ends from there, and how often the
    CT side wins the retake by the number of players alive on each side when the bomb is planted."""
    from sklearn.cluster import DBSCAN
    from map_analysis import ZoneMap
    try:
        zm = ZoneMap(mp)
    except Exception:
        return None, None, None
    sites = midround.site_centers().get(mp) or {}
    rows = []
    for d in dirs:
        fr = os.path.join(d, "rounds.parquet")
        if not os.path.exists(fr):
            continue
        R = pd.read_parquet(fr)
        if not five_v_five(R) or "plant_X" not in R:
            continue
        P = R[R.plant_site.isin(["A", "B"]) & R.plant_X.notna() & R.plant_t.notna()]
        if not len(P):
            continue
        fd = os.path.join(d, "duels.parquet")
        D = pd.read_parquet(fd, columns=["round", "t", "victim_side"]) if os.path.exists(fd) else pd.DataFrame(columns=["round", "t", "victim_side"])
        for _, r in P.iterrows():
            dd = D[(D["round"] == r["round"]) & (D.t < r.plant_t)]
            rows.append({"site": r.plant_site, "x": float(r.plant_X), "y": float(r.plant_Y), "t": float(r.plant_t), "win_t": r.winner == "T",
                         "ct": int(r.CT_n) - int((dd.victim_side == "CT").sum()), "tt": int(r.T_n) - int((dd.victim_side == "T").sum())})
    if len(rows) < 20:
        return None, None, None
    df = pd.DataFrame(rows)
    px, py = zm.px(df.x.to_numpy(), df.y.to_numpy())
    df["px"], df["py"] = np.asarray(px, dtype=float), np.asarray(py, dtype=float)
    plants, retakes = {}, {}
    for site, g in df.groupby("site"):
        c = sites.get(site, {}).get("c")
        level = zm.level(c[2])[0] if c else None
        cx, cy = (np.asarray(zm.px([c[0]], [c[1]])[0])[0], np.asarray(zm.px([c[0]], [c[1]])[1])[0]) if c else (g.px.median(), g.py.median())
        lab = DBSCAN(eps=16, min_samples=max(3, int(0.04 * len(g)))).fit(g[["px", "py"]].to_numpy()).labels_
        g = g.assign(cl=lab)
        spots = []
        for k, s in g[g.cl >= 0].groupby("cl"):
            mx, my = float(s.px.mean()), float(s.py.mean())
            spots.append({"n": int(len(s)), "share": round(100 * len(s) / len(g)), "px": [round(mx), round(my)], "level": level,
                          "where": _compass(mx - cx, my - cy), "timer": _timer(s.t.median()), "t_win": round(100 * float(s.win_t.mean()))})
        spots.sort(key=lambda x: -x["n"])
        plants[site] = {"n": int(len(g)), "timer": _timer(g.t.median()), "t_win": round(100 * float(g.win_t.mean())), "spots": spots[:3]}
        rt = []
        for (ct, tt), s in g.groupby(["ct", "tt"]):
            if len(s) >= 6 and ct >= 1 and tt >= 1:
                rt.append({"ct": int(ct), "t": int(tt), "n": int(len(s)), "ct_win": round(100 * (1 - float(s.win_t.mean())))})
        retakes[site] = sorted(rt, key=lambda x: (-x["ct"], x["t"]))
    return plants, retakes, df[["ct", "tt", "win_t"]]


def _deaths(mp, dirs, site_of):
    """Where the players of each side die, by moment of the round, overall and when the attack goes A or B."""
    rows = []
    for d in dirs:
        fd = os.path.join(d, "duels.parquet")
        fr = os.path.join(d, "rounds.parquet")
        if not os.path.exists(fd) or not os.path.exists(fr):
            continue
        R = pd.read_parquet(fr, columns=["T_n", "CT_n"])
        if not five_v_five(R):
            continue
        mid = os.path.basename(d)
        D = pd.read_parquet(fd, columns=["round", "t", "victim_side", "victim_zone"])
        D = D.assign(site=[site_of.get((mid, int(r)), "-") for r in D["round"]])
        rows.append(D)
    if not rows:
        return None
    df = pd.concat(rows, ignore_index=True)
    df = df[df.victim_zone.notna() & (df.victim_zone != "?")]
    df["w"] = pd.cut(df.t, [lo for _, lo, _ in WINDOWS] + [999], labels=[k for k, _, _ in WINDOWS], right=False)
    out = {}
    for side, g in df.groupby("victim_side"):
        if side not in ("T", "CT"):
            continue
        res = {}
        for key, sel in (("all", slice(None)), ("A", g.site == "A"), ("B", g.site == "B")):
            x = g[sel] if key != "all" else g
            wins = {}
            for w, xw in x.groupby("w", observed=True):
                if len(xw) < 15:
                    continue
                vc = xw.victim_zone.value_counts(normalize=True).head(3)
                wins[str(w)] = {"n": int(len(xw)), "zones": [{"zone": humanize(z, mp), "pct": _pct(p)} for z, p in vc.items()]}
            res[key] = wins
        out[side] = res
    return out


def evidence(mp, g, dirs, pool=None):
    site_of = {(m, int(r)): s for m, r, s in zip(g.match, g["round"], g.site)}
    plants, retakes, rows = _plants_and_retakes(mp, dirs)
    if pool is not None and rows is not None:
        pool.append(rows)
    return {"survival": _survival(g), "contact": _contact(g), "plants": plants, "retakes": retakes,
            "deaths": _deaths(mp, dirs, site_of), "windows": {k: [lo, hi] for k, lo, hi in WINDOWS}}


def retake_table(pool):
    """Retakes on every map together: the CT side's chances by players alive on each side when the bomb goes down."""
    if not pool:
        return []
    df = pd.concat(pool, ignore_index=True)
    out = []
    for (ct, tt), s in df.groupby(["ct", "tt"]):
        if len(s) >= 15 and ct >= 1 and tt >= 1:
            out.append({"ct": int(ct), "t": int(tt), "n": int(len(s)), "ct_win": round(100 * (1 - float(s.win_t.mean())))})
    return sorted(out, key=lambda x: (-x["ct"], x["t"]))


def match_story(mid):
    """Round by round, for one match: where the Ts went and how (rush, execute...), who died where and when (the Ts
    killed alone flagged), the plant and the result. Times in seconds since the end of the freeze time."""
    import json
    f = os.path.join(OUT, f"{mid}.parquet")
    if not os.path.exists(f):
        return None
    df = pd.read_parquet(f)
    if not len(df) or "t_deaths" not in df:
        return None
    try:
        zs = json.load(open(ZONES, encoding="utf-8"))
    except (OSError, ValueError):
        zs = {}
    df = _dynamics(_directions(df, zs=zs))
    try:   # the play of each round, with the lanes this match's Ts used
        import lanes as LN
        ls = _lanes()
        df = LN.classify(df, ls, LN.geo())
        mp = df["map"].iloc[0]
        df["play_name"] = [LN.name(p, ls.get(mp), [int(i) for i in str(u).split(",") if i != ""]) for p, u in zip(df.play, df.play_lanes)]
    except Exception:
        df["play"], df["play_name"] = None, None
    num = lambda v: round(float(v), 1) if v is not None and v == v else None
    out = []
    for _, r in df.sort_values("round").iterrows():
        out.append({"r": int(r["round"]), "team": r.t_team, "site": r.site, "in": bool(r.entered), "dyn": r.dyn,
                    "play": r.get("play"), "play_name": r.get("play_name"),
                    "at": num(r.commit), "grp": int(r.grp) if r.grp == r.grp and r.grp is not None else None,
                    "plant": [r.plant_site, num(r.plant_t)] if r.plant_site in ("A", "B") else None,
                    "tw": bool(r.T_won), "why": r.reason, "end": num(r.end_t),
                    "lurk": bool(r.lurk_other) if isinstance(r.lurk_other, (bool, np.bool_)) else None,
                    "td": [[z, round(t, 1), a] for z, t, a in _deaths_list(r.t_deaths)],
                    "cd": [[z, round(t, 1)] for z, t, _ in _deaths_list(r.get("ct_deaths"), lone_flag=False)],
                    "fc": [r.first_zone, num(r.first_t), None if r.fc_alone is None or r.fc_alone != r.fc_alone else bool(r.fc_alone)]
                          if isinstance(r.first_zone, str) else None,
                    "bunch": [r.bunch_zone, num(r.bunch_t)] if r.bunch_t is not None and r.bunch_t == r.bunch_t else None})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(run_all(force="--force" in sys.argv), "demos analyzed")
