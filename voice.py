"""Your own calls: records YOUR microphone during CS2 matches (opt-in, in the settings), transcribes it on this PC
(Whisper, nothing leaves the PC), aligns the calls on the rounds of the match and measures how you communicate:
information given before dying, "where + how many" calls, grenades announced, talking during a teammate's clutch,
tilt words.

Recording starts and stops with the match (CS2 Game State Integration) or by hand. Only your microphone is recorded:
with a headset, your teammates' voices do not reach it. Files stay in out/voice (not versioned). Recording other
people's words without their consent is forbidden in France (article 226-1 of the Code pénal): record your own
voice, or teammates who agreed.

Usage: python voice.py transcribe <recording id>
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
import time

import config

DIR = os.path.join(config.OUT, "voice")
SR = 16000
MODEL = "large-v2"


def settings():
    return config.settings().get("voice") or {}


def save_settings(**kw):
    s = config.settings()
    v = s.setdefault("voice", {})
    v.update(kw)
    config.save_settings(s)
    return v


def cs2_voice_device():
    """The microphone CS2 uses for voice chat (voice_device_override in CS2's settings), if one is set."""
    try:
        own = config.logged_in_account()[0]
        f = os.path.join(config.steam_path(), "userdata", str(int(own) - 76561197960265728), "730", "local", "cfg", "cs2_machine_convars.vcfg")
        m = re.search(r'"voice_device_override"\s*"([^"]+)"', open(f, encoding="utf-8", errors="replace").read())
        return m.group(1) if m else None
    except Exception:
        return None


def chosen_device():
    return settings().get("device") or cs2_voice_device()


def devices():
    import sounddevice as sd
    default = sd.query_devices(kind="input")["name"]
    cs2 = cs2_voice_device()
    seen, out = set(), []
    for d in sd.query_devices():
        if d["max_input_channels"] > 0 and d["name"] not in seen:
            seen.add(d["name"])
            out.append({"name": d["name"], "default": d["name"] == default, "cs2": bool(cs2) and d["name"].startswith(cs2[:31])})
    return out


# ---------- recording ----------
class Recorder:
    def __init__(self):
        self.lock = threading.Lock()
        self.stream = self.file = self.meta = None
        self.peak = 0.0          # loudest sample of the recording (silence = wrong microphone)

    def recording(self):
        return self.stream is not None

    def start(self, map_name=None, steamid=None, source="auto"):
        import sounddevice as sd
        import soundfile as sf
        with self.lock:
            if self.stream:
                return self.meta
            os.makedirs(DIR, exist_ok=True)
            now = dt.datetime.now()
            rid = f"{now:%Y%m%d_%H%M%S}_{(map_name or 'match').replace('de_', '').replace('cs_', '')}"
            name = chosen_device()
            dev = None
            if name:  # PortAudio shortens names to 31 characters with some drivers
                dev = next((i for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0
                            and (d["name"] == name or name.startswith(d["name"]) or d["name"].startswith(name[:31]))), None)
            self.peak = 0.0
            info = sd.query_devices(dev, kind="input")
            rate = SR
            try:
                sd.check_input_settings(device=dev, samplerate=SR, channels=1)
            except Exception:
                rate = int(info["default_samplerate"])  # Whisper resamples on reading
            self.file = sf.SoundFile(os.path.join(DIR, rid + ".flac"), mode="w", samplerate=rate, channels=1, format="FLAC")
            self.meta = {"id": rid, "file": rid + ".flac", "start": time.time(), "start_iso": now.isoformat(timespec="seconds"),
                         "map": map_name, "steamid": str(steamid or ""), "device": info["name"], "rate": rate, "source": source, "rounds": []}

            def cb(indata, frames, tinfo, status):
                try:
                    block = indata[:, 0].copy()
                    self.file.write(block)
                    p = float(abs(block).max()) if len(block) else 0.0
                    if p > self.peak:
                        self.peak = p
                except Exception:
                    pass
            self.stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32", callback=cb, device=dev)
            self.stream.start()
            self._save()
            return self.meta

    def mark(self, **event):
        with self.lock:
            if self.meta is not None:
                event["t"] = round(time.time() - self.meta["start"], 2)
                self.meta["rounds"].append(event)
                if event.get("map") and not self.meta.get("map"):
                    self.meta["map"] = event["map"]
                self._save()

    def stop(self):
        with self.lock:
            if not self.stream:
                return None
            try:
                self.stream.stop()
                self.stream.close()
            finally:
                self.stream = None
                self.file.close()
                self.file = None
                self.meta["end"] = time.time()
                self.meta["duration"] = round(self.meta["end"] - self.meta["start"], 1)
                self.meta["peak"] = round(self.peak, 4)
                self.meta["silent"] = self.peak < 0.01  # nothing above -40 dB: the microphone was not the one in use
                self._save()
                m, self.meta = self.meta, None
            return m

    def _save(self):
        json.dump(self.meta, open(os.path.join(DIR, self.meta["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


REC = Recorder()
LAST = {"key": None, "gameover": None}


def on_gsi(g):
    """Called for every message of the game: start with the match (automatic mode), mark the rounds of any
    recording, stop at the end (automatic mode)."""
    if not g:
        return
    auto = bool(settings().get("auto"))
    phase = g.get("map_phase")
    if auto and phase == "live" and g.get("map") and not REC.recording():
        try:
            pause_transcription()  # all the power for the game
            REC.start(g.get("map"), g.get("steamid"), "auto")
        except Exception as e:
            print("microphone unavailable:", e, flush=True)
            return
    if REC.recording():
        key = (g.get("round"), g.get("round_phase"), g.get("side"))
        if key != LAST["key"]:
            LAST["key"] = key
            REC.mark(round=g.get("round"), phase=g.get("round_phase"), side=g.get("side"), map=g.get("map"),
                     score=[g.get("score_ct"), g.get("score_t")])
        if not auto:
            return
        if phase == "gameover":
            LAST["gameover"] = LAST["gameover"] or time.time()
            if time.time() - LAST["gameover"] > 20:  # keep the last words
                finish()
        elif phase is None and g.get("map") is None:  # back to the menu
            finish()
        else:
            LAST["gameover"] = None


def watchdog(g):
    """No message from the game for 2 minutes while recording automatically: the game was closed."""
    if REC.recording() and (REC.meta or {}).get("source") == "auto":
        if not g or g.get("age", 999) > 120:
            finish()


def finish():
    m = REC.stop()
    LAST.update(key=None, gameover=None)
    if m and m.get("duration", 0) >= 60 and not m.get("silent"):
        start_transcription(m["id"])
    return m


# ---------- transcription (separate low-priority process) ----------
JOB = {"proc": None, "id": None}


def start_transcription(rid):
    if JOB["proc"] and JOB["proc"].poll() is None:
        return False
    flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log = open(os.path.join(DIR, rid + ".log"), "w", encoding="utf-8")
    JOB["proc"] = subprocess.Popen([sys.executable, os.path.join(config.HERE, "voice.py"), "transcribe", rid], cwd=config.HERE,
                                   stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    JOB["id"] = rid
    return True


def transcribing():
    return JOB["id"] if JOB["proc"] and JOB["proc"].poll() is None else None


def pause_transcription():
    """A new match starts: stop the transcription (it will be done again later) to keep all the power for the game."""
    if JOB["proc"] and JOB["proc"].poll() is None:
        JOB["proc"].terminate()
        JOB.update(proc=None, id=None)


HALLUCINATIONS = re.compile(r"merci d'avoir regard|sous-titr|abonnez|à bientôt pour|merci de votre attention|n'oubliez pas de|amara\.org", re.I)


def _prompt(map_name):
    words = ["Counter-Strike", "flash", "smoke", "molotov", "HE", "lurk", "rotate", "retake", "site A", "site B", "mid", "full buy", "éco", "force",
             "drop", "AWP", "heaven", "ramp", "long", "short", "one shot", "il est à 80"]
    try:
        import plan
        z = (plan.zone_refs().get(map_name or "") or {}).get("zones", [])
        words += [x["name"] for x in z][:40]
    except Exception:
        pass
    return "Calls de Counter-Strike : " + ", ".join(words) + "."


def transcribe(rid):
    meta = json.load(open(os.path.join(DIR, rid + ".json"), encoding="utf-8"))
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=min(8, os.cpu_count() or 4))
    segs, info = model.transcribe(os.path.join(DIR, meta["file"]), language="fr", vad_filter=True, word_timestamps=True,
                                  condition_on_previous_text=False, initial_prompt=_prompt(meta.get("map")))
    words = [(w.start, w.end, w.word) for s in segs if not HALLUCINATIONS.search(s.text or "") for w in (s.words or [])]
    utts, cur = [], []
    for w in words:
        if cur and w[0] - cur[-1][1] > 0.9:
            utts.append(cur)
            cur = []
        cur.append(w)
    if cur:
        utts.append(cur)
    out = [{"start": round(u[0][0], 2), "end": round(u[-1][1], 2), "text": "".join(x[2] for x in u).strip()} for u in utts]
    out = [o for o in out if o["text"] and not HALLUCINATIONS.search(o["text"])]
    json.dump({"id": rid, "model": MODEL, "time": dt.datetime.now().isoformat(timespec="minutes"), "utterances": out},
              open(os.path.join(DIR, rid + ".transcript.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(out)


def recordings():
    if not os.path.exists(DIR):
        return []
    out = []
    for f in sorted(os.listdir(DIR), reverse=True):
        if f.endswith(".json") and not f.endswith((".transcript.json", ".analysis.json")):
            m = json.load(open(os.path.join(DIR, f), encoding="utf-8"))
            rid = m["id"]
            a = os.path.join(DIR, rid + ".analysis.json")
            out.append({"id": rid, "start": m.get("start_iso"), "map": m.get("map"), "duration": m.get("duration"), "device": m.get("device"),
                        "rounds_marked": len({r.get("round") for r in m.get("rounds", [])}), "source": m.get("source"),
                        "transcribed": os.path.exists(os.path.join(DIR, rid + ".transcript.json")),
                        "silent": bool(m.get("silent")) or (m.get("peak") is not None and m["peak"] < 0.01),
                        "match": json.load(open(a, encoding="utf-8")).get("match") if os.path.exists(a) else None,
                        "audio": os.path.exists(os.path.join(DIR, m["file"]))})
    return out


def delete(rid):
    for ext in (".flac", ".json", ".transcript.json", ".analysis.json", ".log"):
        f = os.path.join(DIR, rid + ext)
        if os.path.exists(f):
            os.remove(f)


# ---------- analysis ----------
NUM = r"\b(un|une|deux|trois|quatre|cinq|[1-5]|tous|toute l'équipe|full|personne|seul)\b"
DMG = r"\b(touch[ée]|tagged|lit|one ?shot|one|il est à|à \d+|\d+ ?(hp|pv)|moins \d+|low|bas|cramé)\b"
UTIL = r"\b(flash|flashe|smoke|smok|molo|molotov|incendiaire|he|grenade|stuff|nade|decoy|déco)\b"
PLAN = r"\b(on (va|part|joue|fait|rush|push|exec|tourne|save|sauve|reste)|rush|push|exec|default|split|fake|save|sauve|éco|eco|force|full ?buy|drop|stack|retake|rotate|tourne|rotation|attends|go)\b"
TILT = r"\b(putain|bordel|merde|nuls?|c'est pas possible|sérieux|fdp|ta gueule|ff|abusé|n'importe quoi)\b"
GENERIC_POS = ["a", "b", "mid", "milieu", "site", "long", "short", "court", "banane", "banana", "apps", "pit", "arch", "connector", "palace", "jungle",
               "window", "fenêtre", "ramp", "rampe", "heaven", "hell", "outside", "lobby", "silo", "hut", "squeaky", "secret", "vent", "vents", "mini",
               "garage", "rafters", "catwalk", "tunnel", "tunnels", "canal", "bridge", "pont", "ruins", "alley", "spawn", "ct", "t", "boîte", "box",
               "car", "voiture", "truck", "camion", "tree", "arbre", "sun", "stairs", "escalier", "back", "fond", "top", "bas", "haut", "upper", "lower"]


def _pos_re(map_name):
    words = set(GENERIC_POS)
    try:
        import plan
        for z in (plan.zone_refs().get(map_name or "") or {}).get("zones", []):
            for w in re.findall(r"[a-zà-ÿ]+", z["name"].lower()):
                if len(w) >= 3 or w in ("a", "b"):
                    words.add(w)
    except Exception:
        pass
    return re.compile(r"\b(" + "|".join(sorted(map(re.escape, words), key=len, reverse=True)) + r")\b", re.I)


def normalize(text):
    t = text.lower()
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    t = re.sub(r"\b(part|va|joue|fait|rush|push|exec|tourne|site|sur|en)\s+à\b", r"\1 a", t)  # "on part à" = site A
    return t


def classify(text, pos_re):
    t = normalize(text)
    pos, num, dmg = bool(pos_re.search(t)), bool(re.search(NUM, t)), bool(re.search(DMG, t))
    dmg_value = bool(re.search(r"à \d+|\d+ ?(hp|pv)|one ?shot|touch[ée]|tagged", t))
    return {"info": pos or dmg, "complete": (pos and (num or dmg)) or dmg_value, "util": bool(re.search(UTIL, t)),
            "plan": bool(re.search(PLAN, t)), "tilt": bool(re.search(TILT, t))}


def _match_for(meta, sid):
    """The analyzed match played during this recording (same map, start time inside the recording)."""
    import cs2coach
    reg = cs2coach.registry()
    start, end = meta["start"], meta.get("end") or meta["start"] + 3600
    best = None
    for mid in cs2coach.player_matches(int(sid)):
        r = reg.get(mid) or {}
        f = os.path.join(config.DEEP, mid, "meta.json")
        mp = json.load(open(f, encoding="utf-8")).get("map") if os.path.exists(f) else None
        if not r.get("time") or (meta.get("map") and mp and mp != meta["map"]):
            continue
        t = dt.datetime.fromisoformat(r["time"]).timestamp()
        if start - 15 * 60 <= t <= end:
            d = abs(t - start)
            if best is None or d < best[0]:
                best = (d, mid)
    return best[1] if best else None


def analyze(rid, sid):
    """Calls of one recording, aligned on the rounds of its match."""
    import pandas as pd
    meta = json.load(open(os.path.join(DIR, rid + ".json"), encoding="utf-8"))
    tf = os.path.join(DIR, rid + ".transcript.json")
    if not os.path.exists(tf):
        return None
    utts = json.load(open(tf, encoding="utf-8"))["utterances"]
    pos_re = _pos_re(meta.get("map"))
    for u in utts:
        u.update(classify(u["text"], pos_re))
    mid = _match_for(meta, sid)
    # round windows from the game's marks: live start of each round, in seconds of recording
    marks = meta.get("rounds") or []
    if not any(e.get("phase") == "live" for e in marks):  # manual recording: take the rounds from the game's timeline
        import gsi
        marks = [dict(e, t=round(e["t"] - meta["start"], 2)) for e in gsi.timeline(meta["start"] - 5, meta.get("end") or meta["start"] + 4 * 3600)]
        if marks and not meta.get("map"):
            meta["map"] = next((e.get("map") for e in marks if e.get("map")), None)
    live = {}
    for e in marks:
        if e.get("phase") == "live" and e.get("round") and e["round"] not in live:
            live[e["round"]] = e["t"]
    starts = sorted(live.items())
    rounds = []
    died, clutch_windows, throws = {}, {}, []
    if mid and starts:
        d = os.path.join(config.DEEP, mid)
        L = pd.read_parquet(os.path.join(d, "loadout.parquet")) if os.path.exists(os.path.join(d, "loadout.parquet")) else None
        D = pd.read_parquet(os.path.join(d, "duels.parquet")) if os.path.exists(os.path.join(d, "duels.parquet")) else None
        G = pd.read_parquet(os.path.join(d, "grenades.parquet")) if os.path.exists(os.path.join(d, "grenades.parquet")) else None
        S = pd.read_parquet(os.path.join(d, "samples.parquet"), columns=["steamid", "side", "round"]) if os.path.exists(os.path.join(d, "samples.parquet")) else None
        me = int(sid)
        if L is not None:
            for _, x in L[L.steamid == me].iterrows():
                if pd.notna(x.died_t):
                    died[int(x["round"])] = float(x.died_t)
        if D is not None and S is not None:
            for r, g in D.sort_values("tick").groupby("round"):
                r = int(r)
                side_of = S[S["round"] == r].drop_duplicates("steamid").set_index("steamid")["side"].to_dict()
                my_side = side_of.get(me)
                if my_side is None or r not in died:
                    continue
                mates = [p for p, sd in side_of.items() if sd == my_side]
                alive = set(mates)
                for _, k in g.iterrows():
                    alive.discard(int(k.victim))
                    if len(alive) == 1 and me not in alive and k.t >= died[r]:
                        clutch_windows[r] = float(k.t)  # a teammate is alone from this moment
                        break
        if G is not None:
            throws = [(int(x["round"]), float(x.t), x["type"]) for _, x in G[G.thrower == int(sid)].iterrows()]
    for i, (r, t0) in enumerate(starts):
        t1 = starts[i + 1][1] - 16 if i + 1 < len(starts) else (meta.get("duration") or t0 + 115)
        us = [u for u in utts if t0 - 16 <= u["start"] < t1]
        dt_ = died.get(r)
        alive_us = [u for u in us if u["start"] >= t0 and (dt_ is None or u["start"] <= t0 + dt_)]
        before_death = [u for u in us if dt_ is not None and t0 + dt_ - 10 <= u["start"] <= t0 + dt_ + 1.5]
        dead_us = [u for u in us if dt_ is not None and u["start"] > t0 + dt_ + 1.5]
        cl = clutch_windows.get(r)
        clutch_talk = [u for u in dead_us if cl is not None and u["start"] >= t0 + cl]
        buy_us = [u for u in us if u["start"] < t0]
        announced = sum(1 for (rr, tt, typ) in throws if rr == r and any(u["util"] and t0 + tt - 6 <= u["start"] <= t0 + tt + 0.5 for u in us))
        n_throws = sum(1 for (rr, _, _) in throws if rr == r)
        rounds.append({"round": r, "died_t": dt_, "calls": len(us), "alive_calls": len(alive_us), "info_before_death": any(u["info"] for u in before_death),
                       "dead_calls": len(dead_us), "clutch_talk": len(clutch_talk), "buy_calls": len(buy_us), "throws": n_throws, "announced": announced,
                       "texts": [{"t": round(u["start"] - t0, 1), "text": u["text"], "kind": "tilt" if u["tilt"] else "info" if u["info"] else "util" if u["util"] else "plan" if u["plan"] else ""} for u in us]})
    n = len(utts)
    tot = lambda k: sum(1 for u in utts if u[k])
    rr = [r for r in rounds]
    deaths = [r for r in rr if r["died_t"] is not None]
    thr = sum(r["throws"] for r in rr)
    res = {"id": rid, "match": mid, "map": meta.get("map"), "start": meta.get("start_iso"), "duration": meta.get("duration"),
           "aligned": bool(rounds), "utterances": n, "speech_s": round(sum(u["end"] - u["start"] for u in utts)),
           "info": tot("info"), "complete": tot("complete"), "util": tot("util"), "plan": tot("plan"), "tilt": tot("tilt"),
           "complete_share": round(100 * tot("complete") / max(tot("info"), 1)),
           "rounds": rr, "rounds_n": len(rr),
           "silent_rounds": sum(1 for r in rr if r["alive_calls"] == 0),
           "silent_deaths": sum(1 for r in deaths if not r["info_before_death"]), "deaths": len(deaths),
           "clutch_talk_rounds": sum(1 for r in rr if r["clutch_talk"]), "clutch_rounds": sum(1 for r in rr if r["round"] in clutch_windows),
           "throws": thr, "announced": sum(r["announced"] for r in rr),
           "examples": [u["text"] for u in utts if u["complete"]][:4],
           "tilt_rounds": [r["round"] for r in rr if any(x["kind"] == "tilt" for x in r["texts"])][:6]}
    res["tips"] = tips(res)
    json.dump(res, open(os.path.join(DIR, rid + ".analysis.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return res


def tips(a):
    T = []
    if a["aligned"] and a["deaths"] and a["silent_deaths"] / a["deaths"] >= 0.4:
        T.append(f"{a['silent_deaths']} deaths out of {a['deaths']} without any info in the 10 s before: call what you see before taking the duel, not after.")
    if a["info"] >= 5 and a["complete_share"] < 50:
        T.append(f"Only {a['complete_share']}% of your calls say where AND how many (or the damage): 'two B, one tagged for 80' rather than 'they're B'.")
    if a["throws"] >= 4 and a["announced"] / a["throws"] < 0.5:
        T.append(f"{a['announced']} grenades called out of {a['throws']}: say 'flash' before throwing it, your teammates turn away.")
    if a["clutch_talk_rounds"]:
        T.append(f"You talked during {a['clutch_talk_rounds']} teammate clutch(es): one useful piece of info, then silence.")
    if a["tilt"] >= 3:
        T.append(f"{a['tilt']} frustrated phrases: after a mistake, one breath, then one useful piece of info for the team.")
    if a["aligned"] and a["rounds_n"] and a["silent_rounds"] / a["rounds_n"] >= 0.4:
        T.append(f"No call in {a['silent_rounds']} rounds out of {a['rounds_n']}: even when lurking, call what you hear (rotations, steps).")
    if not T:
        T.append("Your calls are clean: keep saying where, how many and what you are going to do.")
    return T


def summary(sid, limit=6):
    """Latest analyzed recordings of a player, for the plan."""
    out = []
    for r in recordings():
        m = json.load(open(os.path.join(DIR, r["id"] + ".json"), encoding="utf-8"))
        if m.get("steamid") and str(m["steamid"]) != str(sid):
            continue
        if r["transcribed"] and not r.get("silent"):
            try:
                a = analyze(r["id"], sid)
            except Exception as e:
                print("call analysis impossible:", e)
                a = None
            if a:
                out.append(a)
        if len(out) >= limit:
            break
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 2 and sys.argv[1] == "transcribe":
        print(transcribe(sys.argv[2]), "phrases")
