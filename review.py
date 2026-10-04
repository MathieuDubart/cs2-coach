"""Cold review ("bilan"): what changed in the last session compared with the matches before, how much,
the likely reasons (time of day, session length, maps, group, sleep, experiments started), what was tested
and what to test next. Every "why" is a coincidence worth checking, not a proof: the text says so.
The page shows it in three tiers (04/10): a quick brief (the record, the rating's trend match by match, what works,
what slips, the one thing for next time), a brief per map of the session (record, rating, sides, what to play and
to avoid there) and the deep dive (every change with its possible reasons, the pro insights summed over the
session, the focus areas, the tests). New keys only: the page of an older plan still reads it.
"""
import datetime as dt
import json
import math
import os
from collections import Counter

import pandas as pd

KPI = {  # key: (label, unit, higher is better)
    "rating": ("Match rating (≈ HLTV 2.0)", "", True),
    "adr": ("Damage per round", "", True),
    "traded": ("Deaths traded", "%", True),
    "isolated": ("Isolated deaths (per 24 rounds)", "", False),
    "adv_throw": ("Man advantages thrown", "%", False),
    "nades": ("Grenades that died with you (per 24 rounds)", "", False),
    "xhair": ("Crosshair offset before the duel", "°", False),
    "open": ("Opening duels won", "%", True),
}
# experiments whose measure is one of these numbers
EXP_KPI = {"trade_distance": "isolated", "nades_40s": "nades", "prefire": "xhair", "advantage": "adv_throw", "opening": "open",
           "session_limit": "rating", "warmup": "rating", "rotation": "isolated", "retake_group": "isolated", "silent": "isolated"}
RULE_KPI = {"trade": "traded", "nades": "nades", "xhair": "xhair", "open": "open", "early": "isolated", "lastalive": "isolated",
            "hold": "isolated", "flash": "traded"}


def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def per_match(st, mid):
    """The numbers of one match, from stats.json and the mid-round row."""
    import context
    o = st["overview"]
    r = max(st["rounds"], 1)
    v = {"rating": context.rating(o["kills"], o["deaths"], o["assists"], o["adr"], o["kast_pct"], r), "adr": o["adr"],
         "nades": sum(len(x["grenades_unused_at_death"]) for x in st["per_round"]) / r * 24,
         "xhair": (st["aim"].get("crosshair_placement") or {}).get("median_error_deg")}
    d = o["trades"]["my_deaths"]
    v["traded"] = 100 * o["trades"]["my_deaths_traded"] / d if d else None
    ow, ol = o["opening_duels"]["won"], o["opening_duels"]["lost"]
    v["open"] = 100 * ow / (ow + ol) if ow + ol else None
    if mid is not None:
        rounds = _num(mid.get("rounds")) or r
        v["isolated"] = (_num(mid.get("isolated_deaths")) or 0) / max(rounds, 1) * 24
        ar = _num(mid.get("adv_rounds")) or 0
        v["adv_throw"] = 100 * (_num(mid.get("adv_throw")) or 0) / ar if ar >= 3 else None
    return v


def _insights_of(sid, st):
    """A match's pro insights (pro_analyst), computed again from its demo when its stats.json has none or the first
    version's (then saved in it): a few seconds a match, once."""
    pi = st.get("pro_insights")
    if isinstance(pi, dict) and pi.get("v") == 2:
        return pi
    import config
    mid = str((st.get("match") or {}).get("match_id") or "")
    dem = os.path.join(config.CACHE, f"{mid}.dem")
    if not mid or not os.path.exists(dem):
        return None
    try:
        import analyze
        pi = analyze.analyze(dem, int(sid)).get("pro_insights")
    except Exception:
        return None
    if not isinstance(pi, dict):
        return None
    st["pro_insights"] = pi
    f = os.path.join(config.player_dir(sid), "matches", mid, "stats.json")
    try:
        with open(f, encoding="utf-8") as fh:
            cur = json.load(fh)
        cur["pro_insights"] = pi
        config.write_json(f, cur, default=str)
    except (OSError, ValueError):
        pass
    return pi


def _map_name(mp):
    return str(mp).split("_")[-1].capitalize()


def pro_summary(sid, sts):
    """The pro insights summed over the session's matches: only what stands out (with enough cases to say it)."""
    import nades
    rp = rpo = ut = uto = fl = flo = n = 0
    spots, deaths_on = Counter(), Counter()
    for st in sts:
        pi = _insights_of(sid, st)
        if not pi:
            continue
        n += 1
        rp += pi["repeek"]["value"]
        rpo += pi["repeek"]["of"]
        ut += pi["untraded"]["value"]
        uto += pi["untraded"]["of"]
        fl += pi["flash"]["value"]
        flo += pi["flash"]["of"]
        for k, c in (pi.get("spots") or {}).items():
            spots[(st["map"], k)] += c
            deaths_on[st["map"]] += c
    out = []
    if rpo >= 8:
        pct = 100 * rp / rpo
        sev = "high" if pct >= 30 else "medium" if pct >= 20 else "positive" if pct <= 10 else None
        if sev:
            out.append({"id": "repeek", "severity": sev, "value": rp, "of": rpo, "pct": round(pct),
                        "title": "Dead soon after your first kill" if sev != "positive" else "You keep the advantage after a kill",
                        "detail": f"In {rp} of the {rpo} rounds where you got a kill, you died within 8 s." +
                                  (" After a kill the numbers are on your side: fall back to a spot a teammate can trade from instead of peeking again."
                                   if sev != "positive" else " After a kill you fall back instead of peeking again: keep doing it.")})
    if uto >= 8:
        pct = 100 * ut / uto
        sev = "high" if pct >= 50 else "medium" if pct >= 35 else "positive" if pct <= 20 else None
        if sev:
            out.append({"id": "untraded", "severity": sev, "value": ut, "of": uto, "pct": round(pct),
                        "title": "Deaths without impact" if sev != "positive" else "Your deaths are rarely for nothing",
                        "detail": f"{ut} of your {uto} deaths: nobody traded you within 5 s and you hadn't hit anyone in the 3 s before." +
                                  (" Take the duel closer to a teammate, or with utility." if sev != "positive" else "")})
    if flo >= 6:
        pct = 100 * fl / flo
        sev = "medium" if pct <= 20 else "positive" if pct >= 50 else None
        if sev:
            out.append({"id": "flash", "severity": sev, "value": fl, "of": flo, "pct": round(pct),
                        "title": "Flashes your team doesn't use" if sev == "medium" else "Flashes that pay off",
                        "detail": f"Your flashes blinded {flo} enemies for over 1.5 s; your team hit {fl} of them while they were blind." +
                                  (" Call it before throwing, or flash for your own peek." if sev == "medium" else "")})
    for (mp, place), c in spots.most_common(5):   # a bombsite is where a CT anchor dies: the role, not a habit
        if c >= 4 and c >= 0.3 * deaths_on[mp] and not str(place).startswith("Bombsite"):
            nm = nades.humanize(place, mp) or place
            out.append({"id": "spot", "severity": "medium", "value": c, "of": deaths_on[mp], "map": mp, "place": nm,
                        "title": f"You keep dying at {nm} ({_map_name(mp)})",
                        "detail": f"{c} of your {deaths_on[mp]} deaths on {_map_name(mp)} this session: the enemies can expect you there. Change the angle or the timing."})
    order = {"high": 0, "medium": 1, "positive": 2}
    out.sort(key=lambda x: order[x["severity"]])
    return {"matches": n, "items": out}


def map_briefs(recent, by_id, adv):
    """Each map of the session: record, rating, damage, round wins per side, and what to play and to avoid there
    (the map advice, per side)."""
    out = {}
    for r in recent:
        st = by_id.get(r["id"]) or {}
        m = out.setdefault(r["map"], {"map": r["map"], "games": 0, "wins": 0, "losses": 0, "ratings": [], "adr": [],
                                      "T": [0, 0], "CT": [0, 0]})
        m["games"] += 1
        m["wins"] += r["result"] == "win"
        m["losses"] += r["result"] == "loss"
        m["ratings"].append(r["rating"])
        m["adr"].append(r["adr"])
        for side in ("T", "CT"):
            m[side][0] += int(((st.get("overview") or {}).get("rounds_won_on_side") or {}).get(side) or 0)
            m[side][1] += int((st.get("rounds_per_side") or {}).get(side) or 0)
    res = []
    for mp, m in out.items():
        adv_m = ((adv or {}).get("maps") or {}).get(mp) or {}
        sides = {}
        for side in ("T", "CT"):
            x = adv_m.get(side) or {}
            b = x.get("bullets") or []
            sides[side] = {"won": m[side][0], "of": m[side][1], "record": x.get("record"),
                           "play": next((y["text"] for y in b if y.get("kind") == "exploit"), None),
                           "avoid": next((y["text"] for y in b if y.get("kind") == "avoid"), None)}
        res.append({"map": mp, "games": m["games"], "wins": m["wins"], "losses": m["losses"],
                    "rating": round(sum(m["ratings"]) / len(m["ratings"]), 2), "adr": round(sum(m["adr"]) / len(m["adr"]), 1),
                    "sides": sides})
    res.sort(key=lambda x: (-x["games"], -x["rating"]))
    return res


def _mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    m = sum(xs) / len(xs)
    sd = pd.Series(xs).std() if len(xs) > 1 else None
    return m, (None if sd is None or math.isnan(sd) else float(sd)), len(xs)


def build(sid, stats, mid_rows, ctx, exps, adv):
    """-> the review, or None without at least 3 dated matches with a demo."""
    rows, by_id = [], {}
    for st in stats:
        t = (st.get("match") or {}).get("time")
        if not t:
            continue
        rows.append({"id": st["match"]["match_id"], "time": dt.datetime.fromisoformat(t), "map": st["map"], "result": st["result"],
                     "score": st["final_score"], **per_match(st, mid_rows.get(st["match"]["match_id"]))})
        by_id[st["match"]["match_id"]] = st
    rows.sort(key=lambda r: r["time"])
    if len(rows) < 3:
        return None
    # recent window: the last session when it has 2 games or more, else the last 3 matches
    ms = (ctx or {}).get("matches") or []
    sess_of = {m["id"]: (m.get("index"), m.get("start")) for m in ms}
    last = rows[-1]
    recent = [last]
    for r in reversed(rows[:-1]):
        gap = (recent[-1]["time"] - r["time"]).total_seconds() / 3600
        if gap <= 3.5:
            recent.append(r)
        else:
            break
    recent = list(reversed(recent))
    if len(recent) < 2:
        recent = rows[-3:]
    before = [r for r in rows if r["time"] < recent[0]["time"]][-12:]
    label = (f"your last session ({len(recent)} games, on {recent[0]['time']:%m/%d})" if len(recent) >= 2 and
             (recent[-1]["time"] - recent[0]["time"]).total_seconds() < 6 * 3600 else f"your last {len(recent)} matches")
    # context of each window, for the reasons
    def share_late(win):
        return sum(1 for r in win if r["time"].hour >= 23 or r["time"].hour < 6) / max(len(win), 1)
    wr = {}
    for side in ("T", "CT"):
        for mp, x in ((adv or {}).get("maps") or {}).items():
            rec = (x.get(side) or {}).get("record")
            if rec and rec[1]:
                w, t = wr.get(mp, (0, 0))
                wr[mp] = (w + rec[0], t + rec[1])
    map_win = {mp: 100 * w / t for mp, (w, t) in wr.items() if t >= 15}
    worst_map = min(map_win, key=map_win.get) if len(map_win) >= 2 else None
    best_map = max(map_win, key=map_win.get) if len(map_win) >= 2 else None
    reasons_bad, reasons_good = [], []
    if before and share_late(recent) >= 0.5 and share_late(before) < 0.3:
        n = sum(1 for r in recent if r["time"].hour >= 23 or r["time"].hour < 6)
        reasons_bad.append(f"{n} of these {len(recent)} games after 11pm")
    if len(recent) >= 4:
        reasons_bad.append(f"a session of {len(recent)} games in a row: fatigue builds up after each game")
    half = max(2, math.ceil(len(recent) / 2))
    if worst_map and sum(1 for r in recent if r["map"] == worst_map) >= half:
        reasons_bad.append(f"{sum(1 for r in recent if r['map'] == worst_map)} game(s) on {worst_map.split('_')[-1].capitalize()}, your hardest map ({map_win[worst_map]:.0f}% of rounds won)")
    if best_map and sum(1 for r in recent if r["map"] == best_map) >= half:
        reasons_good.append(f"{sum(1 for r in recent if r['map'] == best_map)} game(s) on {best_map.split('_')[-1].capitalize()}, your best map ({map_win[best_map]:.0f}% of rounds won)")
    party = {m["id"]: m.get("party_size") for m in ms}
    pr = [party.get(r["id"]) for r in recent if party.get(r["id"])]
    pb = [party.get(r["id"]) for r in before if party.get(r["id"])]
    if pr and pb:
        solo_r, solo_b = sum(1 for p in pr if p == 1) / len(pr), sum(1 for p in pb if p == 1) / len(pb)
        grp = next((f for f in (ctx or {}).get("factors", []) if f["title"] == "Group"), None)
        solo_perf = next((row["delta"] for row in (grp or {}).get("rows", []) if row["group"] == "solo"), None)
        if solo_r - solo_b >= 0.5:
            (reasons_bad if (solo_perf or 0) < 0 else reasons_good).append("you played solo more often than usual")
        elif solo_b - solo_r >= 0.5:
            (reasons_good if (solo_perf or 0) < 0 else reasons_bad).append("you played in a group more often than usual")
    started = [e for e in (exps or {}).get("experiments", []) if e.get("started") and
               dt.datetime.fromisoformat(e["started"]) <= recent[-1]["time"] and dt.datetime.fromisoformat(e["started"]) >= (before[-1]["time"] if before else rows[0]["time"])]
    changes, stable = [], []
    for k, (lab, unit, hib) in KPI.items():
        a, sa, na = _mean_sd([r.get(k) for r in recent])
        b, sb, nb = _mean_sd([r.get(k) for r in before])
        if a is None or b is None or na < 2 or nb < 2:
            continue
        se = math.sqrt((sa or abs(a) * 0.2 or 1) ** 2 / na + (sb or abs(b) * 0.2 or 1) ** 2 / nb)
        z = (a - b) / se if se else 0
        better = (a > b) == hib
        item = {"key": k, "label": lab, "unit": unit, "higher_better": hib, "before": round(b, 2), "after": round(a, 2),
                "delta": round(a - b, 2), "better": better, "z": round(z, 2), "n_before": nb, "n_after": na,
                # 8 indicators compared on a few games: 2.5 standard errors before calling a gap clear (with 2, one
                # session in three would show a "clear" change that is only chance)
                "level": "clear" if abs(z) >= 2.5 else "trend" if abs(z) >= 1.5 else None, "why": []}
        if item["level"] is None:
            stable.append(lab)
            continue
        for e in started:
            if EXP_KPI.get(e["template"]) == k:
                item["why"].append(f"matches the experiment '{e['title']}' started on {dt.datetime.fromisoformat(e['started']):%m/%d}")
        if k in ("rating", "adr", "traded", "open"):
            item["why"] += reasons_good if better else reasons_bad
        changes.append(item)
    changes.sort(key=lambda c: -abs(c["z"]))
    # the three axes of the moment, with their trend
    axes = []
    for r in ((adv or {}).get("rules") or [])[:3]:
        k = RULE_KPI.get(r.get("id"))
        a, _, na = _mean_sd([x.get(k) for x in recent]) if k else (None, None, 0)
        b, _, nb = _mean_sd([x.get(k) for x in before]) if k else (None, None, 0)
        trend = None
        if a is not None and b is not None and na and nb:
            hib = KPI[k][2]
            trend = "better" if (a > b) == hib and abs(a - b) > 0.05 * max(abs(b), 1) else "worse" if abs(a - b) > 0.05 * max(abs(b), 1) else "stable"
        axes.append({"id": r.get("id"), "title": r.get("title"), "short": r.get("short"), "do": (r.get("do") or [])[:2],
                     "drills": (r.get("drills") or [])[:1], "kpi": k, "kpi_label": KPI[k][0] if k else None, "unit": KPI[k][1] if k else None,
                     "before": None if b is None else round(b, 2), "after": None if a is None else round(a, 2), "trend": trend,
                     "sources": (r.get("sources") or [])[:2]})
    wins = sum(1 for r in recent if r["result"] == "win")
    losses = sum(1 for r in recent if r["result"] == "loss")
    ex = exps or {}
    active = [e for e in ex.get("experiments", []) if e["status"] == "active"]
    done = [e for e in ex.get("experiments", []) if e["status"] != "active"]
    nxt = None
    worse = [c for c in changes if not c["better"]]
    if worse:
        nxt = f"Fix what is slipping: {worse[0]['label'].lower()} ({worse[0]['before']:g} → {worse[0]['after']:g}).".replace(".", ",", 0)
    elif axes:
        nxt = f"Stay on track with your #1 focus: {axes[0]['short'].lower()}."
    trend = [{"id": r["id"], "time": r["time"].isoformat(timespec="minutes"), "map": r["map"], "result": r["result"],
              "rating": round(r["rating"], 2), "recent": r in recent} for r in before + recent]
    try:
        pro = pro_summary(sid, [by_id[r["id"]] for r in recent if r["id"] in by_id])
    except Exception as e:   # a bonus: never the review's end
        pro = {"matches": 0, "items": [], "error": str(e)[:200]}
    return {"label": label, "since": recent[0]["time"].isoformat(timespec="minutes"),
            "trend": trend, "maps": map_briefs(recent, by_id, adv), "pro": pro,
            "session": {"games": len(recent), "wins": wins, "losses": losses,
                        "matches": [{"id": r["id"], "time": r["time"].isoformat(timespec="minutes"), "map": r["map"], "result": r["result"],
                                     "score": r["score"], "rating": round(r["rating"], 2)} for r in recent]},
            "n_before": len(before), "changes": changes, "stable": stable, "axes": axes, "next": nxt,
            "tests": {"active": active, "done": done[-4:], "suggested": ex.get("suggested", [])[:3]}}
