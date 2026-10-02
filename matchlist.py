"""Fetch and decode the recent-matches list from the CS2 Game Coordinator (via boiler-writter).

Needs Steam running and CS2 closed.
"""
import datetime as dt
import os
import re
import struct
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BOILER = os.path.join(HERE, "tools", "boiler", "bin", "boiler-writter.exe")
OUT = os.path.join(HERE, "cache", "matchlist.bin")
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def _varint(b, i):
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def decode(b):
    """Minimal protobuf decoder -> {field: [values]} (bytes left raw)."""
    out, i = {}, 0
    while i < len(b):
        key, i = _varint(b, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 2:
            n, i = _varint(b, i)
            v, i = b[i:i + n], i + n
        elif wt == 5:
            v, i = struct.unpack("<I", b[i:i + 4])[0], i + 4
        elif wt == 1:
            v, i = struct.unpack("<Q", b[i:i + 8])[0], i + 8
        else:
            raise ValueError(f"wire type {wt}")
        out.setdefault(f, []).append(v)
    return out


def _packed(v):
    if isinstance(v, int):
        return [v]
    vals, i = [], 0
    while i < len(v):
        x, i = _varint(v, i)
        vals.append(x)
    return vals


BOILER_ZIP = "https://github.com/akiver/boiler-writter/releases/download/v1.7.0/boiler-writter-win-1.7.0.zip"


def ensure_boiler():
    """boiler-writter (MIT, by akiver) is not versioned here: fetch the Windows release on first use."""
    if os.path.exists(BOILER):
        return
    import io
    import urllib.request
    import zipfile
    dest = os.path.join(HERE, "tools", "boiler")
    os.makedirs(dest, exist_ok=True)
    data = urllib.request.urlopen(BOILER_ZIP, timeout=60).read()
    zipfile.ZipFile(io.BytesIO(data)).extractall(dest)


def fetch():
    ensure_boiler()
    subprocess.run([BOILER, OUT], cwd=os.path.dirname(BOILER), check=True, capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return parse(open(OUT, "rb").read())


def parse(raw):
    top = decode(raw)
    me = top.get(2, [None])[0]  # our account id
    matches = []
    for m in top.get(4, []):
        mi = decode(m)
        rounds = [decode(r) for r in mi.get(5, [])]
        last = rounds[-1] if rounds else {}
        url = next((x.decode() for x in last.get(3, []) if isinstance(x, bytes) and x.startswith(b"http")), None)
        res = decode(last[2][0]) if 2 in last else {}
        accounts = [a for v in res.get(1, []) for a in _packed(v)]
        col = lambda f: [x for v in last.get(f, []) for x in _packed(v)]
        kills, assists, deaths, scores = col(5), col(6), col(7), col(8)
        idx = accounts.index(me) if me in accounts else None
        team_scores = col(12)
        mine = None
        if idx is not None and idx < len(kills):
            my_team = 0 if idx < len(accounts) // 2 else 1
            # teams swap at half-time: the final state lists scores for the starting sides
            mine = {"kills": kills[idx], "assists": assists[idx], "deaths": deaths[idx], "score": scores[idx],
                    "team_index": my_team}
        # share code of the match (match id, outcome = reservation id, token = GOTV port)
        watch = decode(mi[3][0]) if 3 in mi else {}
        outcome, token = last.get(1, [None])[0], watch.get(2, [None])[0]
        hs, mvps = col(17), col(21)
        matches.append({
            "match_id": str(mi[1][0]),
            "time": dt.datetime.fromtimestamp(mi[2][0]).isoformat(timespec="minutes"),
            "url": url, "players": len(accounts), "team_scores": team_scores,
            "rounds": len(rounds), "duration_s": last.get(15, [None])[0],
            "me": mine,
            "sharecode": encode_sharecode(mi[1][0], outcome, token) if outcome and token else None,
            "accounts": accounts,  # first half = first team; SteamID64 = account + 76561197960265728
            "stats": [{"k": kills[i] if i < len(kills) else None, "a": assists[i] if i < len(assists) else None,
                       "d": deaths[i] if i < len(deaths) else None, "hs": hs[i] if i < len(hs) else None,
                       "mvp": mvps[i] if i < len(mvps) else None} for i in range(len(accounts))],
        })
    return matches


if __name__ == "__main__":
    import json
    import sys
    ms = fetch() if "--fetch" in sys.argv else parse(open(OUT, "rb").read())
    print(json.dumps(ms, indent=1))


# ---------- share codes (CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx) ----------
SC_DICT = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"


def decode_sharecode(code):
    """-> (match_id, outcome_id, token)"""
    s = code.replace("CSGO", "").replace("-", "")
    n = 0
    for c in reversed(s):
        n = n * 57 + SC_DICT.index(c)
    b = n.to_bytes(18, "big")
    return int.from_bytes(b[0:8], "little"), int.from_bytes(b[8:16], "little"), int.from_bytes(b[16:18], "little")


def encode_sharecode(match_id, outcome_id, token):
    b = match_id.to_bytes(8, "little") + outcome_id.to_bytes(8, "little") + (token & 0xFFFF).to_bytes(2, "little")
    n = int.from_bytes(b, "big")
    chars = []
    for _ in range(25):
        n, r = divmod(n, 57)
        chars.append(SC_DICT[r])
    s = "".join(chars)
    return "CSGO-" + "-".join(s[i:i + 5] for i in range(0, 25, 5))


def fetch_one(match_id, outcome_id, token):
    """Full info of one match by its share-code triple, through this PC's Steam session."""
    ensure_boiler()
    out = os.path.join(os.path.dirname(OUT), f"one_{match_id}.bin")
    subprocess.run([BOILER, out, str(match_id), str(outcome_id), str(token)], cwd=os.path.dirname(BOILER),
                   check=True, capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return parse(open(out, "rb").read())


def history_codes(api_key, steamid, auth_code, known_code, limit=30):
    """Walk a player's match history with the Steam Web API (needs the player's match-history auth code)."""
    import json as _json
    import urllib.request
    codes, cur = [], known_code
    for _ in range(limit):
        url = ("https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1"
               f"?key={api_key}&steamid={steamid}&steamidkey={auth_code}&knowncode={cur}")
        with urllib.request.urlopen(url, timeout=20) as r:
            nxt = _json.load(r)["result"]["nextcode"]
        if not nxt or nxt == "n/a":
            break
        codes.append(nxt)
        cur = nxt
    return codes
