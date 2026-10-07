"""Photos of the lineups (06/10, the user: "les endroits avec les images de là où je dois viser, de là où je dois me
mettre", like the Fachwerk book): taken in your own game, on the training server.

A session per map: the lineups of Live's ways (tdirs.py: the Ts' stuff of each way in, the CTs' onto each site and
against its rushes), the most thrown first, the ones already photographed skipped. Numpad + puts you on the next
lineup's spot, aimed exactly (setpos / setang: the server allows them for the session only), and a moment later Wily
takes a picture of the game's window: the aim, what the crosshair covers at the middle of the picture. Where to stand
is Live's map (the arc from the spot to where it lands). Nothing is pressed for you: you press the key, Wily only
writes the file the key runs and reads the screen.
Photos in out/lineups/shots/<map>/<id>.webp (id: side, type, from and to zones of the game)."""
import ctypes
import ctypes.wintypes
import json
import os
import re
import threading
import time

import config

DIR = os.path.join(config.OUT, "lineups", "shots")
STATE = os.path.join(config.OUT, "lineshots.json")
KEY = "KP_PLUS"
CFG = "coach_lineup.cfg"
_LOCK = threading.Lock()
SAFE = re.compile(r"[^A-Za-z0-9_>-]")


def lid(side, u):
    """A lineup's id: its side, type, and the game's zones it's thrown from and lands in (the training's own key)."""
    return SAFE.sub("", f"{side}_{u['type']}_{u.get('from_key') or u.get('from') or ''}_{u.get('to_key') or u.get('to') or ''}").replace(">", "-")


def todo(mp):
    """The map's lineups worth a picture: Live's ways' stuff (T), the CTs' onto each site and against its rushes."""
    import tdirs
    M = tdirs.load_map(mp) or {}
    out, seen = [], set()

    def add(side, u):
        if not u.get("setpos") or not u.get("from_key"):
            return
        i = lid(side, u)
        if i in seen:
            return
        seen.add(i)
        out.append({"id": i, "side": side, "type": u["type"], "from": u.get("from"), "to": u.get("to"), "how": u.get("how"),
                    "setpos": u["setpos"], "n": int(u.get("n") or 0)})
    for d in M.get("dirs") or []:
        for u in d.get("util") or []:
            add("T", u)
    for D_ in (M.get("defense") or {}).values():
        for u in D_.get("util") or []:
            add("CT", u)
    for U in (M.get("ct_util") or {}).values():
        for u in U:
            add("CT", u)
    for side, key in (("T", "util_dt"), ("CT", "ct_util_t")):   # the stuff of a direction and a tempo (07/10)
        for T_ in (M.get(key) or {}).values():
            for U in T_.values():
                for u in U:
                    add(side, u)
    return sorted(out, key=lambda x: -x["n"])


def shots(mp):
    """The photos taken on a map: id -> its address on the app."""
    d = os.path.join(DIR, mp)
    if not os.path.isdir(d):
        return {}
    return {f[:-5]: f"/lineshot/{mp}/{f}" for f in os.listdir(d) if f.endswith(".webp")}


def _state():
    try:
        return json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(s):
    config.write_json(STATE, s)


def _cfg_dir():
    import gsi
    return gsi.cfg_dir()


def _write(item, i, n):
    d = _cfg_dir()
    if not d:
        return False
    if item:
        body = (f"{item['setpos']}\n"
                f'echo "Wily: lineup {i + 1}/{n}: {item["type"]} {item.get("from") or ""} > {item.get("to") or ""} ({item.get("how") or ""}): keep still, the photo is taken"\n')
    else:
        body = 'echo "Wily: no lineup photo session (Prepare: Photos of the lineups)"\n'
    open(os.path.join(d, CFG), "w", encoding="utf-8").write(body)
    return True


def start(mp):
    """A photo session on a map: the training server on that map with setpos / setang allowed, the game sent to it,
    the first lineup in the key's file."""
    import replay
    import train
    items = [x for x in todo(mp) if x["id"] not in shots(mp)]
    if not items:
        return {"map": mp, "done": len(shots(mp)), "total": len(todo(mp)), "left": 0}
    if not replay.claim("a photo session"):
        raise RuntimeError(f"{replay.busy()} is starting on the training server: wait for it")
    try:
        st = replay.status()
        if st.get("session"):   # a warm-up runs there: not under its feet
            raise RuntimeError("a warm-up runs on the training server: stop it first")
        if not st.get("running") or st.get("map") != mp:
            replay.start(mp)
        replay.rcon("sv_cheats 1")   # setpos / setang for the session; stop() puts it back
    finally:
        replay.release()
    with _LOCK:
        _save({"map": mp, "items": items, "i": 0, "t": time.time(), "on": True})
        _write(items[0], 0, len(items))
    threading.Thread(target=train._connect, daemon=True).start()
    return status()


def stop():
    with _LOCK:
        s = _state()
        s["on"] = False
        _save(s)
        _write(None, 0, 0)
    try:
        import replay
        replay.rcon("sv_cheats 0")
    except Exception:
        pass
    return status()


def status(map_name=None):
    """The photo session (or, with a map, that map's photos taken / lineups to photograph)."""
    if map_name:
        return {"map": map_name, "done": len(shots(map_name)), "total": len(todo(map_name))}
    s = _state()
    mp = s.get("map")
    out = {"on": bool(s.get("on")), "map": mp}
    if mp:
        out.update(done=len(shots(mp)), total=len(todo(mp)), left=max(0, len(s.get("items") or []) - int(s.get("i") or 0)) if s.get("on") else 0)
        if s.get("on") and s.get("items") and s.get("i", 0) < len(s["items"]):
            out["next"] = {k: s["items"][s["i"]][k] for k in ("type", "from", "to", "how")}
    return out


def on_key():
    """Numpad + pressed (its file was run): the picture once the view has settled, then the next lineup."""
    s = _state()
    if not s.get("on"):
        return
    threading.Thread(target=_shoot, daemon=True).start()


def _window_box():
    """The game's window on the screen (physical pixels), None when it isn't there or is minimized."""
    try:
        u = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            u.SetProcessDPIAware()
        h = u.FindWindowW(None, "Counter-Strike 2")
        if not h or u.IsIconic(h):
            return None
        r = ctypes.wintypes.RECT()
        u.GetClientRect(h, ctypes.byref(r))
        pt = (ctypes.c_long * 2)(0, 0)
        u.ClientToScreen(h, pt)
        return (pt[0], pt[1], pt[0] + r.right, pt[1] + r.bottom)
    except Exception:
        return None


def _shoot():
    from PIL import ImageDraw, ImageGrab
    time.sleep(0.9)   # the view settles (a jumpthrow's spot drops you to the ground first)
    with _LOCK:
        s = _state()
        if not s.get("on"):
            return
        items, i = s.get("items") or [], int(s.get("i") or 0)
        if i >= len(items):
            return
        box = _window_box()
        if not box:
            return
        img = ImageGrab.grab(bbox=box, all_screens=True)
        w, h = img.size
        cw, ch = int(w * 0.5), int(h * 0.55)
        x0, y0 = (w - cw) // 2, (h - ch) // 2
        img = img.crop((x0, y0, x0 + cw, y0 + ch)).convert("RGB")
        dr = ImageDraw.Draw(img)
        cx, cy = cw // 2, ch // 2   # the aim: the middle of the screen, marked
        for r_, col in ((15, (11, 15, 20)), (13, (255, 211, 77))):
            dr.ellipse([cx - r_, cy - r_, cx + r_, cy + r_], outline=col, width=3)
        d = os.path.join(DIR, s["map"])
        os.makedirs(d, exist_ok=True)
        img.thumbnail((960, 960))
        img.save(os.path.join(d, items[i]["id"] + ".webp"), "WEBP", quality=80)
        s["i"] = i + 1
        _save(s)
        _write(items[i + 1] if i + 1 < len(items) else None, i + 1, len(items))
        if i + 1 >= len(items):
            s["on"] = False
            _save(s)
    if i + 1 >= len(items):
        stop()
