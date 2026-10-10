"""Anonymous usage statistics (05/10, the alpha): what players open, how long they stay, which buttons they use, the
page's errors, whether Live runs during a match, to sort the app and rework its UX on real use.

A player's PC: the page counts (ui: the usage tracker), this module adds it up per day in out/usage/<day>.json. A day
once over goes to the coach's site (api/usage.php) with the app's version and a screen size class: no identifier,
no SteamID, no name, nothing the player wrote. There each report is added to the day's totals and thrown away.
On by default with a notice the first time (anonymous audience measurement); Settings turns it off: nothing more is
counted or sent.

The coach's PC: the days' totals pulled from the site (contributions.pull_usage) into out/usage_all, ranked here."""
import datetime as dt
import json
import os
import re
import threading
import time
import urllib.request

import config

URL = os.environ.get("COACH_USAGE_URL") or "https://wily.valentingassend.com/api/usage.php"
DIR = os.path.join(config.OUT, "usage")
ALL = os.path.join(config.OUT, "usage_all")
KEEP_DAYS = 30
VIEW_RE = re.compile(r"^[a-z0-9_.:-]{1,40}$")
ACTION_RE = re.compile(r"^[A-Za-z0-9_.:#=\[\]/-]{1,80}$")
SCREENS = {"phone", "tablet", "laptop", "desktop", "wide"}
LOCK = threading.Lock()


NOTICE_V = 2   # the first-launch notice's version: 2 (10/10) also tells that the anonymized matches are shared by default


def settings():
    return (config.settings().get("usage") or {})


def noticed():
    """The player saw the current notice (an older one, about the usage statistics only, does not count)."""
    v = settings().get("noticed")
    return (v if isinstance(v, int) and not isinstance(v, bool) else int(bool(v))) >= NOTICE_V


def enabled():
    """A player's copy, unless they turned it off (the coach's own app counts nothing)."""
    return config.role() == "client" and settings().get("on", True)


def set_options(on=None, noticed=None):
    s = config.settings()
    u = s.setdefault("usage", {})
    if on is not None:
        u["on"] = bool(on)
    if noticed is not None:
        u["noticed"] = NOTICE_V if noticed else 0
    config.save_settings(s)
    return status()


def _today():
    return dt.date.today().isoformat()


def add(batch):
    """One batch from the page (every minute and when it closes), added to today's counters. Only known shapes are
    kept: view names, action keys, numbers."""
    if not enabled() or not isinstance(batch, dict):
        return False
    f = os.path.join(DIR, f"{_today()}.json")
    with LOCK:
        cur = config.read_json(f, {}) or {"views": {}, "actions": {}, "errors": 0, "live": 0, "screen": None}
        for k, v in (batch.get("views") or {}).items():
            if VIEW_RE.match(str(k)) and isinstance(v, dict) and len(cur["views"]) < 80:
                x = cur["views"].setdefault(k, {"visits": 0, "seconds": 0})
                x["visits"] += max(0, min(500, int(v.get("visits") or 0)))
                x["seconds"] += max(0, min(3600, int(v.get("seconds") or 0)))
        for k, n in (batch.get("actions") or {}).items():
            if ACTION_RE.match(str(k)) and (k in cur["actions"] or len(cur["actions"]) < 300):
                cur["actions"][k] = cur["actions"].get(k, 0) + max(0, min(1000, int(n or 0)))
        cur["errors"] += max(0, min(1000, int(batch.get("errors") or 0)))
        cur["live"] += max(0, min(3600, int(batch.get("live") or 0)))
        if batch.get("screen") in SCREENS:
            cur["screen"] = batch["screen"]
        config.write_json(f, cur)
    return True


def status():
    s = settings()
    today = config.read_json(os.path.join(DIR, f"{_today()}.json"), None)
    sent = len([f for f in os.listdir(DIR) if f.endswith(".sent.json")]) if os.path.isdir(DIR) else 0
    return {"on": enabled(), "client": config.role() == "client", "noticed": noticed(), "today": today, "days_sent": sent}


def _post(day, counts):
    v = config.read_json(os.path.join(config.HERE, "VERSION.json"), {}) or {}
    payload = {"day": day, "app": v.get("app") or "", "views": counts.get("views") or {}, "actions": counts.get("actions") or {},
               "errors": counts.get("errors") or 0, "live": counts.get("live") or 0, "screen": counts.get("screen") or "unknown"}
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "CoachCS2-usage"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def send_pending():
    """The days that are over and not sent yet (a day is sent once); the files older than 30 days removed."""
    if not os.path.isdir(DIR):
        return 0
    n, today = 0, _today()
    for f in sorted(os.listdir(DIR)):
        p = os.path.join(DIR, f)
        if f.endswith(".sent.json") or not f.endswith(".json"):
            if f.endswith(".json") and f[:10] < (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat():
                os.remove(p)
            continue
        day = f[:-5]
        if day >= today:
            continue
        if day < (dt.date.today() - dt.timedelta(days=8)).isoformat():   # too old for the site: kept here only
            os.replace(p, p[:-5] + ".sent.json")
            continue
        if not enabled():   # turned off: nothing leaves the PC
            continue
        try:
            if _post(day, config.read_json(p, {}) or {}).get("ok"):
                os.replace(p, p[:-5] + ".sent.json")
                n += 1
        except urllib.error.HTTPError:
            os.replace(p, p[:-5] + ".sent.json")   # refused (shape, limit): never sent again
        except Exception:
            break   # offline: the next round
    return n


# ---------------------------------------------------------------- the coach's side

def stats(days=30):
    """The players' use over the last days, from the days' totals: views by players and time, actions by players,
    the rarely used ones, errors, Live during a match, versions, screens. "players" = player-days (one per app and day)."""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    views, actions = {}, {}
    tot = {"reports": 0, "errors": 0, "error_reports": 0, "live_users": 0, "live_seconds": 0, "apps": {}, "screens": {}, "days": 0}
    for f in sorted(os.listdir(ALL)) if os.path.isdir(ALL) else []:
        if not f.endswith(".json") or f[:10] < since:
            continue
        d = config.read_json(os.path.join(ALL, f), {}) or {}
        tot["days"] += 1
        tot["reports"] += d.get("reports") or 0
        tot["errors"] += d.get("errors") or 0
        tot["error_reports"] += d.get("error_reports") or 0
        tot["live_users"] += (d.get("live") or {}).get("users") or 0
        tot["live_seconds"] += (d.get("live") or {}).get("seconds") or 0
        for k in ("apps", "screens"):
            for name, n in (d.get(k) or {}).items():
                tot[k][name] = tot[k].get(name, 0) + n
        for k, v in (d.get("views") or {}).items():
            x = views.setdefault(k, {"view": k, "users": 0, "visits": 0, "seconds": 0})
            for f2 in ("users", "visits", "seconds"):
                x[f2] += v.get(f2) or 0
        for k, v in (d.get("actions") or {}).items():
            x = actions.setdefault(k, {"action": k, "users": 0, "count": 0})
            x["users"] += v.get("users") or 0
            x["count"] += v.get("count") or 0
    for x in views.values():
        x["minutes_per_user"] = round(x["seconds"] / 60 / max(1, x["users"]), 1)
        x["share"] = round(100 * x["users"] / max(1, tot["reports"]))
    for x in actions.values():
        x["share"] = round(100 * x["users"] / max(1, tot["reports"]))
    acts = sorted(actions.values(), key=lambda x: (-x["users"], -x["count"]))
    return {"days": days, "totals": tot, "views": sorted(views.values(), key=lambda x: (-x["users"], -x["seconds"])),
            "actions": acts[:40], "rare": [a for a in reversed(acts) if a["users"] <= max(1, tot["reports"] // 20)][:25]}
