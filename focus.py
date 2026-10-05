"""The focus of the week: the coach's first axis (the advice's rules, ranked) kept 7 days, so that its effect can show
in the matches (05/10, the user's choice: weekly, changed by hand when wanted). One focus for the three moments of the
app: Live (a chip), Prepare (the Ready step) and Review (first). Stored per player in focus.json."""
import datetime as dt
import os

import config

DAYS = 7


def _file(sid):
    return os.path.join(config.player_dir(str(sid)), "focus.json")


def _card(r):
    return {"id": r.get("id"), "title": r.get("title"), "short": r.get("short") or r.get("title"), "do": (r.get("do") or [])[:2],
            "drills": (r.get("drills") or [])[:2], "sources": (r.get("sources") or [])[:2]}


def weekly(sid, rules, now=None):
    """-> the focus card with since, until, manual and the next axes to pick from: the stored focus while its week
    lasts and its rule is still among the coach's, else the first rule from now on. None without rules."""
    rules = [r for r in (rules or []) if r.get("id")]
    if not rules:
        return None
    now = now or dt.datetime.now()
    cur = config.read_json(_file(sid), {}) or {}
    by = {r["id"]: r for r in rules}
    try:
        since = dt.datetime.fromisoformat(cur["since"])
    except (KeyError, TypeError, ValueError):
        since = None
    if cur.get("id") in by and since and dt.timedelta(0) <= now - since < dt.timedelta(days=DAYS):
        r, manual = by[cur["id"]], bool(cur.get("manual"))
    else:
        r, since, manual = rules[0], now, False
        config.write_json(_file(sid), {"id": r["id"], "since": since.isoformat(timespec="minutes"), "manual": False})
    return {**_card(r), "since": since.isoformat(timespec="minutes"), "until": (since + dt.timedelta(days=DAYS)).isoformat(timespec="minutes"),
            "manual": manual, "others": [{"id": x["id"], "short": x.get("short") or x.get("title")} for x in rules[:6] if x["id"] != r["id"]]}


def choose(sid, rule_id, rules):
    """You pick the focus among the coach's axes: a new week starts with it. -> its card, None if unknown."""
    if not any(r.get("id") == rule_id for r in rules or []):
        return None
    config.write_json(_file(sid), {"id": rule_id, "since": dt.datetime.now().isoformat(timespec="minutes"), "manual": True})
    return weekly(sid, rules)
