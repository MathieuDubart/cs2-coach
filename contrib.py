"""A player's matches shared with the base, anonymized (05/10, off until the player turns it on in Settings):
the coach's base grows with the players who use the app, without their accounts.

What leaves the PC, per match: the tables the app extracted from its demo (positions every half second, duels,
grenades, buys, rounds), where
- every SteamID becomes a made-up id drawn with a random key used for this match only and never kept: nobody, the
  coach included, can go back from it to an account, nor link the same player across two matches;
- every player name is blank;
- the match's Valve id becomes a random number (a Valve id leads to the match and its players);
- nothing else: not the demo, not the voice, not the settings, not the player's profile.
With them: a random id of this installation (to refuse a flood and to delete what one installation sent if it asks),
the app's version, each match's map and a fingerprint of its rounds (the same match shared twice is kept once).

Sent to https://wily.valentingassend.com/api/contribute.php; the coach's PC pulls them from there (contributions.py).
The matches that came from the base with a player's package are not sent back (base_pack.json "player_matches")."""
import io
import json
import os
import secrets
import threading
import time
import urllib.request
import uuid
import zipfile

import pyarrow.parquet as pq

import anon
import config

URL = os.environ.get("COACH_CONTRIB_URL") or "https://wily.valentingassend.com/api/contribute.php"
STATE_F = os.path.join(config.OUT, "contrib.json")
MAX_BYTES = 24 * 2 ** 20   # one upload; the rest goes with the next one
EVERY = 1800
LOCK = threading.Lock()
ST = {"sending": False}


def state():
    s = config.read_json(STATE_F, {}) or {}
    if not s.get("install_id"):
        s["install_id"] = str(uuid.uuid4())
        config.write_json(STATE_F, s)
    return s


def set_on(on):
    s = state()
    s["on"] = bool(on)
    s["since"] = s.get("since") or (time.time() if on else None)
    config.write_json(STATE_F, s)
    return status()


def candidates():
    """The matches extracted on this PC that the base does not have from this installation yet."""
    s = state()
    sent = set(s.get("sent") or {})
    pack = set((config.read_json(os.path.join(config.OUT, "base_pack.json"), {}) or {}).get("player_matches") or [])
    out = []
    for mid in sorted(os.listdir(config.DEEP)) if os.path.isdir(config.DEEP) else []:
        d = os.path.join(config.DEEP, mid)
        if (mid.isdigit() and mid not in sent and mid not in pack and os.path.exists(os.path.join(d, "meta.json"))
                and os.path.exists(os.path.join(d, "rounds.parquet")) and os.path.exists(os.path.join(d, "samples.parquet"))):
            out.append(mid)
    return out


def status():
    s = state()
    return {"on": bool(s.get("on")), "install": s["install_id"], "sent": len(s.get("sent") or {}), "waiting": len(candidates()) if s.get("on") else None,
            "last": s.get("last"), "error": s.get("error"), "sending": ST["sending"], "url": URL}


def _match(mid):
    """One match, anonymized: {new id: {file: bytes}} and its manifest entry."""
    d = os.path.join(config.DEEP, mid)
    new = "8" + "".join(secrets.choice("0123456789") for _ in range(18))   # no Valve id starts with 8; < 2^63
    pseudo = anon.Pseudo()   # a random key for this match, forgotten right after
    files = {}
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if f.endswith(".parquet"):
            tb = anon.table(pq.read_table(p), pseudo, replace={mid: new})
            left = anon.leftovers(tb)
            if left:
                raise ValueError(f"{f}: {left}")
            buf = io.BytesIO()
            pq.write_table(tb, buf)
            files[f] = buf.getvalue()
        elif f == "meta.json":
            t = open(p, encoding="utf-8").read().replace(mid, new)
            if anon.SID_RE.search(t):
                raise ValueError("meta.json: a SteamID")
            files[f] = t.encode()
    mp = (json.loads(files.get("meta.json", b"{}")) or {}).get("map")
    return new, files, {"id": new, "map": mp, "fingerprint": anon.fingerprint(d)}


def pack(mids):
    """A zip of anonymized matches up to MAX_BYTES -> (bytes, [match ids in it])."""
    s = state()
    buf = io.BytesIO()
    done, man = [], []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for mid in mids:
            try:
                new, files, entry = _match(mid)
            except Exception as e:
                print(f"share {mid}: left out ({e})", flush=True)
                continue
            if done and buf.tell() + sum(len(v) for v in files.values()) > MAX_BYTES:
                break
            for f, b in files.items():
                z.writestr(f"{new}/{f}", b)
            done.append(mid)
            man.append(entry)
        version = (config.read_json(os.path.join(config.HERE, "VERSION.json"), {}) or {}).get("app")
        z.writestr("manifest.json", json.dumps({"install": s["install_id"], "app": version, "matches": man}))
    return buf.getvalue(), done


def _post(data, install, app):
    """multipart/form-data by hand (no extra library): the zip and who sends it."""
    b = "----coachcs2" + secrets.token_hex(8)
    parts = []
    for k, v in (("install", install), ("app", app or "")):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="matches.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode() + data + b"\r\n")
    body = b"".join(parts) + f"--{b}--\r\n".encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={b}",
                                                                          "User-Agent": "CoachCS2-contrib"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"{}")


def send(limit=None):
    """The waiting matches, in uploads of MAX_BYTES at most. -> how many were sent."""
    if not LOCK.acquire(blocking=False):
        return 0
    ST["sending"] = True
    n = 0
    try:
        while True:
            s = state()
            if not s.get("on") or config.in_match():
                break
            todo = candidates()[:limit] if limit else candidates()
            if not todo:
                break
            data, done = pack(todo)
            if not done:
                break
            version = (config.read_json(os.path.join(config.HERE, "VERSION.json"), {}) or {}).get("app")
            res = _post(data, s["install_id"], version)
            if not res.get("ok"):
                raise ValueError(res.get("error") or "refused")
            s = state()
            s.setdefault("sent", {}).update({mid: int(time.time()) for mid in done})
            s.update(last=time.time(), error=None)
            config.write_json(STATE_F, s)
            n += len(done)
            if limit:
                break
    except Exception as e:
        s = state()
        s["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        config.write_json(STATE_F, s)
    finally:
        ST["sending"] = False
        LOCK.release()
    return n


def watch():
    """Every 30 minutes, when the player turned it on and no match is running."""
    time.sleep(120)
    while True:
        try:
            if state().get("on") and not config.in_match():
                send()
        except Exception as e:
            print("share:", e, flush=True)
        time.sleep(EVERY)
