"""Paths, Steam detection and user settings (out/settings.json)."""
import copy
import json
import os
import re
import threading
import time

# tools run in the background never open a console window (it would take the focus away from the game)
NO_WINDOW = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)

HERE = os.path.dirname(os.path.abspath(__file__))


def _own_libraries_only():
    """A player's copy runs on its own embedded Python (python/ next to the app): the libraries a Python user
    installed on that PC (%APPDATA%\\Python, the "user site") must not mix with the app's own (05/10: the first
    package found psutil there on the coach's PC and lacked it). This process drops them, its children never add them."""
    import sys
    if not os.path.normcase(os.path.abspath(sys.prefix)).startswith(os.path.normcase(os.path.join(HERE, "python"))):
        return
    os.environ["PYTHONNOUSERSITE"] = "1"
    try:
        import site
        user = os.path.normcase(site.getuserbase())
        sys.path[:] = [p for p in sys.path if not os.path.normcase(p).startswith(user)]
    except Exception:
        pass


_own_libraries_only()
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


def cs2_dir():
    """CS2's install folder on any PC, found through Steam's library list: the library Steam installed it in (its
    appmanifest_730.acf) with the game in it. A library can keep an old partial copy (here 19 GB on C: without cs2.exe)."""
    sp = steam_path()
    libs = [sp]
    try:
        txt = open(os.path.join(sp, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="replace").read()
        libs += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s*"([^"]+)"', txt)]
    except OSError:
        pass
    found = []
    for lib in dict.fromkeys(libs):
        d = os.path.join(lib, "steamapps", "common", "Counter-Strike Global Offensive")
        if os.path.isdir(os.path.join(d, "game", "csgo")):
            found.append((os.path.exists(os.path.join(lib, "steamapps", "appmanifest_730.acf"))
                          and os.path.exists(os.path.join(d, "game", "bin", "win64", "cs2.exe")), d))
    return max(found, key=lambda f: f[0])[1] if found else None


def cs2server_dir():
    """The training server's folder: set by COACH_CS2SERVER or in the settings, else E:\\CS2Server where it was made
    first, else next to the game on its drive (its files are hard links to the game's: the same drive)."""
    p = os.environ.get("COACH_CS2SERVER") or settings().get("cs2server")
    if p:
        return p
    if os.path.isdir(r"E:\CS2Server"):
        return r"E:\CS2Server"
    g = cs2_dir()
    return os.path.join(os.path.splitdrive(g)[0] + os.sep, "CS2CoachServer") if g else os.path.join(HERE, "CS2CoachServer")


def role():
    """"client": a player's own copy of the app (the beta, 05/10); the base grows on the coach's server only."""
    return settings().get("role") or "server"


# ---------- files shared between the server, its threads and the worker processes ----------
def _retry(fn, what, tries=100, wait=0.05):
    """Windows: a file open in another process can't be replaced or is being replaced: wait a little."""
    for i in range(tries):
        try:
            return fn()
        except (PermissionError, json.JSONDecodeError):
            if i == tries - 1:
                raise
            time.sleep(wait)


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    return _retry(lambda: json.load(open(path, encoding="utf-8")), path)


def write_json(path, obj, **kw):
    """All or nothing: a reader sees the old file or the new one, never half of it (and a crash leaves the old one)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, **({"ensure_ascii": False} | kw))
        f.flush()
        os.fsync(f.fileno())
    try:
        _retry(lambda: os.replace(tmp, path), path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class Settings(dict):
    """The settings as read: remembers that state, so a save only writes what the caller changed."""
    def __init__(self, d):
        super().__init__(d)
        self._base = copy.deepcopy(d)


_MISSING = object()


def _merge(base, mine, cur):
    """Apply the changes made from base to mine onto cur (dicts key by key, any other value replaced)."""
    for k in set(base) | set(mine):
        b, m = base.get(k, _MISSING), mine.get(k, _MISSING)
        if m is _MISSING:
            cur.pop(k, None)   # removed by the caller
        elif isinstance(m, dict) and isinstance(b, dict) and isinstance(cur.get(k), dict):
            _merge(b, m, cur[k])
        elif b is _MISSING or m != b:
            cur[k] = copy.deepcopy(m)
    return cur


_SLOCK = threading.Lock()


class _FileLock:
    """Between processes (the profile workers write the settings too)."""
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "a+")
        end = time.time() + 30
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.time() > end:
                    self.f.close()
                    raise TimeoutError("settings.json is locked by another process")
                time.sleep(0.05)

    def __exit__(self, *a):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.f.close()


def settings():
    return Settings(read_json(SETTINGS, {}) or {})


def save_settings(s):
    """Saves what the caller changed since it read the settings, on top of what other threads or processes
    saved in the meantime (an API key saved during a sync is not lost), in one atomic write."""
    with _SLOCK, _FileLock(SETTINGS + ".lock"):
        cur = read_json(SETTINGS, {}) or {}
        new = _merge(s._base, s, cur) if isinstance(s, Settings) else dict(s)
        write_json(SETTINGS, new, indent=1)
    if isinstance(s, Settings):
        s._base = copy.deepcopy(dict(s))


# ---------- the game first: heavy work waits while you play ----------
PLAYING = os.path.join(OUT, "playing.json")


def in_match():
    """True while CS2 says you are in a match (kept fresh by the game detection, stale 75 s after its last news)."""
    try:
        d = read_json(PLAYING)
    except (OSError, ValueError):
        return False
    return bool(d and d.get("until", 0) > time.time())


def wait_for_match_end(log=None, what="analysis"):
    """Demo downloads, extraction and analyses take the CPU, the disk and the connection: during a match they wait
    for its end, then go on where they stopped. Returns True when it waited."""
    if not in_match():
        return False
    if log:
        log(f"Match in progress: {what} paused until the end of your match (your game comes first)…")
    while in_match():
        time.sleep(10)
    if log:
        log("Match over: resuming.")
    return True


_BG = {"on": None}


def full_speed(pid=None):
    """Windows 11's efficiency mode (EcoQoS) off for this process or `pid`: a windowless process at low priority runs
    on the efficiency cores at a low clock (05/10 at night: the update's 6 workers and a transcription shared 8
    cores, the processor at 39 %; with it off, 81 %)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class _State(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.SetProcessInformation.restype = wintypes.BOOL
        h = k.OpenProcess(0x0200, False, pid) if pid else k.GetCurrentProcess()   # PROCESS_SET_INFORMATION
        st = _State(1, 0x1, 0)   # execution speed: never throttled
        ok = bool(h) and bool(k.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st)))   # ProcessPowerThrottling
        if pid and h:
            k.CloseHandle(h)
        return ok
    except Exception:
        return False


def background(on):
    """Windows' background mode for this process (lower processor, disk and memory priority: the game keeps its own)
    while on; back to its priority class when off. Changed only when it changes."""
    if _BG["on"] == on or os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00100000 if on else 0x00200000)   # PROCESS_MODE_BACKGROUND_BEGIN / END
        if not on:
            full_speed()   # no match: every core at full clock
        _BG["on"] = on
    except Exception:
        pass


def low_priority():
    """This process only gets the CPU the game doesn't use (worker processes of the analyses)."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            k = ctypes.windll.kernel32
            k.GetCurrentProcess.restype = wintypes.HANDLE   # 64-bit handle (the default int would cut it)
            k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            k.SetPriorityClass(k.GetCurrentProcess(), 0x40)   # IDLE_PRIORITY_CLASS
        else:
            os.nice(15)
    except Exception:
        pass


_NAMES = {"mtime": None, "map": {}}


def display_name(sid, fallback=None):
    """One name per player everywhere: the one of the player list (their latest in-game name), else the Steam name
    remembered in the settings, else the fallback."""
    p = os.path.join(OUT, "site", "index.json")
    try:
        mt = os.path.getmtime(p)
        if mt != _NAMES["mtime"]:
            _NAMES.update(mtime=mt, map={e["steamid"]: e["name"] for e in read_json(p, []) or [] if e.get("name")})
    except OSError:
        pass
    sid = str(sid)
    return _NAMES["map"].get(sid) or (settings().get("players", {}).get(sid) or {}).get("name") or fallback or sid


def player_dir(steamid):
    return os.path.join(PLAYERS, str(steamid))
