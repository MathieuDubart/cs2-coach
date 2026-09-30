"""Paths, Steam detection and user settings (out/settings.json)."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
CACHE = os.path.join(HERE, "cache")
DEEP = os.path.join(OUT, "deep")
PLAYERS = os.path.join(OUT, "players")
SETTINGS = os.path.join(OUT, "settings.json")


def steam_path():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\")
    except OSError:
        return r"C:\Program Files (x86)\Steam"


def logged_in_account():
    """(steamid64, persona) of the most recently logged-in Steam account on this PC."""
    path = os.path.join(steam_path(), "config", "loginusers.vdf")
    if not os.path.exists(path):
        return None, None
    txt = open(path, encoding="utf-8", errors="replace").read()
    best = None
    for sid, body in re.findall(r'"(\d{17})"\s*\{(.*?)\}', txt, re.S):
        fields = dict(re.findall(r'"(\w+)"\s+"([^"]*)"', body))
        key = (fields.get("MostRecent") == "1", int(fields.get("Timestamp", 0)))
        if best is None or key > best[0]:
            best = (key, int(sid), fields.get("PersonaName"))
    return (best[1], best[2]) if best else (None, None)


def settings():
    return json.load(open(SETTINGS, encoding="utf-8")) if os.path.exists(SETTINGS) else {}


def save_settings(s):
    os.makedirs(OUT, exist_ok=True)
    json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def player_dir(steamid):
    return os.path.join(PLAYERS, str(steamid))
