"""A player reports a bug from the app (05/10, the alpha): what happened, what they expected, their email address only
if they want an answer, and the technical details they chose to include, shown to them before sending:
- the app's, the base's and the runtime's versions, Windows, whether CS2, game detection and the training server are
  found, the page they were on and its last errors;
- the end of the app's log, with every SteamID, email address and the Windows user name taken out.
Sent to https://wily.valentingassend.com/api/report.php with this installation's random id (the one of contrib.py);
kept in out/reports_outbox until it is (no connection, the site down): sent again later."""
import json
import os
import platform
import re
import sys
import time
import urllib.request

import config

URL = os.environ.get("COACH_REPORT_URL") or "https://wily.valentingassend.com/api/report.php"
OUTBOX = os.path.join(config.OUT, "reports_outbox")
LOG_LINES = 150
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LONG_ID = re.compile(r"(?<!\d)7656119\d{10}(?!\d)")


def scrub(text):
    """No SteamID, email address or Windows user name in what leaves the PC."""
    import anon
    text = anon.SID_RE.sub("<steamid>", LONG_ID.sub("<steamid>", str(text)))
    text = EMAIL_RE.sub("<email>", text)
    for name in {os.environ.get("USERNAME"), os.path.basename(os.path.expanduser("~"))} - {None, ""}:
        if len(name) >= 3:
            text = re.sub(re.escape(name), "<user>", text, flags=re.I)
    for name in sorted(_player_names(), key=len, reverse=True):   # the in-game names the app knows (profiles, settings)
        text = text.replace(name, "<player>")
    return text


def _player_names():
    names = {(p or {}).get("name") for p in (config.settings().get("players") or {}).values()}
    try:
        names |= {e.get("name") for e in config.read_json(os.path.join(config.OUT, "site", "index.json"), []) or []}
    except (OSError, ValueError):
        pass
    return {n for n in names if isinstance(n, str) and len(n) >= 3}


def _log_tail():
    for f in (os.path.join(config.CACHE, "serve.log"), os.path.join(config.OUT, "refresh.log")):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()[-LOG_LINES:]
            return scrub("".join(lines))[-60000:]
        except OSError:
            continue
    return ""


def diagnostics(page=None, errors=None):
    """What "include the technical details" sends: shown to the player first."""
    v = config.read_json(os.path.join(config.HERE, "VERSION.json"), {}) or {}
    base = config.read_json(os.path.join(config.OUT, "base_pack.json"), {}) or {}
    rt = os.path.join(config.HERE, "python", ".runtime")
    out = {"app": v.get("app"), "runtime": open(rt).read().strip() if os.path.exists(rt) else v.get("runtime"),
           "base": base.get("version"), "base_matches": base.get("matches"), "role": config.role(),
           "windows": platform.platform(), "python": sys.version.split()[0], "time": time.strftime("%Y-%m-%d %H:%M %z"),
           "page": scrub(page or "")[:120], "page_errors": [scrub(e)[:500] for e in (errors or [])[-20:]]}
    try:
        out["cs2_found"] = bool(config.cs2_dir())
        import gsi
        out["game_detection"] = bool(gsi.cfg_dir() and os.path.exists(os.path.join(gsi.cfg_dir(), "gamestate_integration_coachcs2.cfg")))
        import replay
        out["training_server"] = replay.installed()
        out["matches_here"] = len(os.listdir(config.DEEP)) if os.path.isdir(config.DEEP) else 0
    except Exception as e:
        out["checks"] = f"{type(e).__name__}"
    out["log"] = _log_tail()
    return out


def _post(payload):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "CoachCS2-report"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def send(text, expected="", email="", include=True, page=None, errors=None, kind="bug"):
    """-> {"ok": True, "id": ...} or {"ok": False, "queued": True, "error": ...} (kept, sent again later)."""
    import contrib
    text = (text or "").strip()
    if not text:
        raise ValueError("Describe what happened first.")
    email = (email or "").strip()
    if email and not EMAIL_RE.fullmatch(email):
        raise ValueError("That email address does not look right.")
    v = config.read_json(os.path.join(config.HERE, "VERSION.json"), {}) or {}
    payload = {"install": contrib.state()["install_id"], "app": v.get("app") or "", "kind": kind if kind in ("bug", "idea", "feedback") else "bug",
               "text": text[:15000], "expected": (expected or "").strip()[:6000], "email": email,
               "page": (page or "")[:120], "diag": diagnostics(page, errors) if include else None}
    try:
        res = _post(payload)
        if not res.get("ok"):
            raise ValueError(res.get("error") or "refused")
        return {"ok": True, "id": res.get("id")}
    except urllib.error.HTTPError as e:   # the site said no (a field, the day's limit): nothing to send again
        try:
            msg = json.loads(e.read() or b"{}").get("error")
        except ValueError:
            msg = None
        raise ValueError(msg or f"the site refused it ({e.code})")
    except Exception as e:
        os.makedirs(OUTBOX, exist_ok=True)
        config.write_json(os.path.join(OUTBOX, f"{int(time.time() * 1000)}.json"), payload)
        return {"ok": False, "queued": True, "error": f"{type(e).__name__}: {str(e)[:120]}"}


def retry():
    """The reports kept while the site could not be reached. -> how many went."""
    n = 0
    for f in sorted(os.listdir(OUTBOX)) if os.path.isdir(OUTBOX) else []:
        p = os.path.join(OUTBOX, f)
        try:
            if _post(config.read_json(p, {})).get("ok"):
                os.remove(p)
                n += 1
        except urllib.error.HTTPError:
            os.replace(p, p + ".refused")   # refused by the site: kept here, never sent again
        except Exception:
            break   # still offline: next time
    return n
