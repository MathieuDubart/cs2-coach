"""Cold review ("bilan"): what changed in the last session compared with the matches before, how much,
the likely reasons (time of day, session length, maps, group, sleep, experiments started), what was tested
and what to test next. Every "why" is a coincidence worth checking, not a proof: the text says so.
"""
import datetime as dt
import math
import os

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


def _mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    m = sum(xs) / len(xs)
    sd = pd.Series(xs).std() if len(xs) > 1 else None
    return m, (None if sd is None or math.isnan(sd) else float(sd)), len(xs)


def build(sid, stats, mid_rows, ctx, exps, adv):
    """-> the review, or None without at least 3 dated matches with a demo."""
    rows = []
    for st in stats:
        t = (st.get("match") or {}).get("time")
        if not t:
            continue
        rows.append({"id": st["match"]["match_id"], "time": dt.datetime.fromisoformat(t), "map": st["map"], "result": st["result"],
                     "score": st["final_score"], **per_match(st, mid_rows.get(st["match"]["match_id"]))})
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
    return {"label": label, "since": recent[0]["time"].isoformat(timespec="minutes"),
            "session": {"games": len(recent), "wins": wins, "losses": losses,
                        "matches": [{"id": r["id"], "time": r["time"].isoformat(timespec="minutes"), "map": r["map"], "result": r["result"],
                                     "score": r["score"], "rating": round(r["rating"], 2)} for r in recent]},
            "n_before": len(before), "changes": changes, "stable": stable, "axes": axes, "next": nxt,
            "tests": {"active": active, "done": done[-4:], "suggested": ex.get("suggested", [])[:3]}}
