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

            seg = _Segmenter(rate, LIVE.push) if settings().get("live", True) else None

            def cb(indata, frames, tinfo, status):
                try:
                    block = indata[:, 0].copy()
                    self.file.write(block)
                    if seg is not None:
                        seg.feed(block, time.time())
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
    if auto and g.get("practice"):   # practice or custom server: nothing to line up with a match, no automatic recording
        if REC.recording() and (REC.meta or {}).get("source") == "auto":
            REC.meta["practice"] = True   # stopped without transcription; kept (Settings lists it, delete it there)
            REC.stop()
            LAST.update(key=None, gameover=None)
        return
    if auto and phase == "live" and g.get("map") and not REC.recording():
        try:
            pause_transcription()  # all the power for the game
            REC.start(g.get("map"), g.get("steamid"), "auto")
            LIVE.start(g.get("map"))
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
    LIVE.stop()
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


def _prompt(map_name, lang="fr"):
    words = ["Counter-Strike", "coach", "flash", "smoke", "molotov", "HE", "lurk", "rotate", "retake", "site A", "site B", "mid", "full buy", "éco", "force",
             "drop", "AWP", "heaven", "ramp", "long", "short", "one shot", "il est à 80"]
    words += ["site clear", "good job", "nice try", "last one", "one more", "low HP"] if lang == "en" else ["bien joué", "perdu", "énervé", "confiant", "bloqué"]
    try:
        import plan
        z = (plan.zone_refs().get(map_name or "") or {}).get("zones", [])
        words += [x["name"] for x in z][:40]
    except Exception:
        pass
    return ("Counter-Strike calls: " if lang == "en" else "Calls de Counter-Strike : ") + ", ".join(words) + "."


def _words(model, path, lang, map_name):
    segs, _ = model.transcribe(path, language=lang, vad_filter=True, word_timestamps=True, condition_on_previous_text=False,
                               initial_prompt=_prompt(map_name, lang))
    return [(w.start, w.end, w.word, w.probability) for s_ in segs if not HALLUCINATIONS.search(s_.text or "") for w in (s_.words or [])]


def _spans(words, gap=0.9):
    out, cur = [], None
    for w in words:
        if cur and w[0] - cur[1] <= gap:
            cur[1] = max(cur[1], w[1])
        else:
            if cur:
                out.append(cur)
            cur = [w[0], w[1]]
    if cur:
        out.append(cur)
    return out


def transcribe(rid):
    """Two passes over the recording, one in French and one in English (Whisper translates what isn't in the language
    it is told: "site clear" became "cité claire"). The phrases of both passes are lined up, and each keeps the pass
    whose words the model is surest of (mean log-probability): your English calls stay English, your French stays
    French."""
    import math
    meta = json.load(open(os.path.join(DIR, rid + ".json"), encoding="utf-8"))
    from faster_whisper import WhisperModel
    threads = int(os.environ.get("COACH_TX_THREADS") or min(8, os.cpu_count() or 4))   # fewer when it runs next to a match
    model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=threads)
    path = os.path.join(DIR, meta["file"])
    W = {lang: _words(model, path, lang, meta.get("map")) for lang in ("fr", "en")}
    spans = sorted(_spans(W["fr"]) + _spans(W["en"]))
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + 0.3:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        best = None
        for lang, ws in W.items():
            sel = [w for w in ws if w[0] >= a - 0.05 and w[1] <= b + 0.05]
            if not sel:
                continue
            score = sum(math.log(max(w[3], 1e-4)) for w in sel) / len(sel)
            if best is None or score > best[0]:
                best = (score, lang, sel)
        if not best:
            continue
        text = "".join(w[2] for w in best[2]).strip()
        if text and not HALLUCINATIONS.search(text):
            out.append({"start": round(best[2][0][0], 2), "end": round(best[2][-1][1], 2), "text": text, "lang": best[1],
                        "p": round(best[0], 2)})
    json.dump({"id": rid, "model": MODEL, "bilingual": True, "time": dt.datetime.now().isoformat(timespec="minutes"), "utterances": out},
              open(os.path.join(DIR, rid + ".transcript.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(out)


def transcribe_mono(rid):
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
                        "rounds_marked": len({r.get("round") for r in m.get("rounds", [])}), "source": m.get("source"), "practice": bool(m.get("practice")),
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


# what a phrase says about how you feel. Said on purpose: "coach" then one word ("coach, perdu", "coach confiant");
# otherwise read from the words: frustration (with the team, with yourself, or plain), doubt, suspicion, positive
COACH_RE = re.compile(r"^\W*(?:coach|coache|coatch|couch|koch|kosh|coch|coche)\b[\s,.:;!-]*(.*)$", re.I)
COACH_ANY = re.compile(r"\b(?:coach|coache|coatch)\b", re.I)   # anywhere: "round coach plutôt satisfait", "coach premier round ok, coach deuxième mitigé"
COACH_WORDS = {
    "frustration": ["énervé", "énervée", "enervé", "tilt", "tilté", "frustré", "rage", "saoulé", "soûlé", "agacé", "dégoûté", "nul", "bloqué",
                    "déçu", "mauvais", "raté", "pas content", "pas satisfait",
                    "seul", "lâché", "bait", "baité", "angry", "tilted", "frustrated", "blocked", "alone", "mad", "annoyed"],
    "doubt": ["perdu", "paumé", "doute", "hésite", "hésitant", "confus", "stressé", "stress", "tendu", "fatigué", "crevé", "lent", "lost",
              "mitigé", "moyen", "bof", "pas sûr", "incertain",
              "confused", "stressed", "tired", "unsure", "nervous"],
    "positive": ["confiant", "chaud", "bien", "serein", "calme", "facile", "fort", "à l'aise", "focus", "concentré", "en forme", "confident",
                 "satisfait", "content", "ok", "propre", "réussi", "solide", "bon round",
                 "good", "calm", "easy", "focused", "great", "comfortable"],
    "suspicion": ["cheat", "cheater", "cheateur", "triche", "tricheur", "wallhack", "suspect", "aimbot"],
}
MOOD_RE = [
    ("suspicion", None, r"\b(cheat\w*|wall ?hack|aimbot|spinbot|trich\w+|utilisateur suspect|suspect)\b"),
    ("frustration", "team", r"(\bbloqu\w+|\bm'a bloqu|\bme bloqu|\bbait\w*|pique après|peek après|t'es mute|tu parles pas|arrête de (peek|regarder)|"
                            r"pourquoi tu|ta smoke|smoke (est |qui )?(mal|pue)|fake info|stop peek)"),
    ("frustration", "self", r"(j'ai pas touché|pas touché (un|une|de)|mourir trop tôt|c'est moi qui ai pris|je suis (nul|la salope|éclaté)|"
                            r"\bmy bad\b|ma faute|j'ai raté)"),
    ("frustration", None, TILT[:-3] + r"|j'en peux plus|ferme ta gueule|ta mère|\bpute\b|fils de|stupide|\bfuck\w*|\bshit\b|\bwtf\b|"
                          r"dans mes veines|ça me met bien|ah vas-y)\b"),
    ("doubt", None, r"(qu'est-ce qu'on fait|on fait quoi|je sais pas|j'sais pas|aucune idée|je comprends (pas|rien)|j'comprends pas|"
                    r"c'est quoi ce|\bpourquoi\b|\bbizarre\b|\bétrange\b|"
                    r"what do we do|\bperdu\b|\bpaumé\b)"),
    ("positive", None, r"\b(nickel|facile|easy|let'?s go|on les a|trop fort|parfait|good job|gg|bien joué|bien fait|nice|bon travail)\b"),
]
MOOD_RE = [(k, sb, re.compile(rx, re.I)) for k, sb, rx in MOOD_RE]
MOODS = ("frustration", "doubt", "suspicion", "positive")


def _coach_word(rest):
    """The feeling in what follows "coach": the first word of the lists found in it (a "pas" just before a positive
    word makes it a frustration: "pas content"); nothing known: a note, kept as said."""
    best = None
    for kind, words in COACH_WORDS.items():
        for w in words:
            m = re.search(r"(?<![a-zà-ÿ])" + re.escape(w) + r"(?![a-zà-ÿ])", rest)
            if m and (best is None or m.start() < best[0]):
                k = kind
                if kind == "positive" and re.search(r"\bpas (très |trop |vraiment )?$", rest[:m.start()]):
                    k = "frustration"
                best = (m.start(), k, w)
    if not best:
        return {"kind": "note", "sub": None, "word": rest.strip(" ,.")[:40], "coach": True} if rest.strip(" ,.") else None
    sb = "team" if best[2] in ("bloqué", "seul", "lâché", "bait", "baité", "blocked", "alone") else None
    return {"kind": best[1], "sub": sb, "word": best[2], "coach": True}


def mood_all(text):
    """Every feeling of a phrase: each "coach …" part on its own (one phrase can say two), else the one read from the
    words."""
    t = (text or "").strip()
    parts = COACH_ANY.split(t)
    if len(parts) > 1:
        return [m for m in (_coach_word(normalize(p_)) for p_ in parts[1:]) if m]
    m = mood_of(t)
    return [m] if m else []


ANALYSIS_V = 2   # bump when the analysis changes: mood_stats analyzes the older ones again


def mood_of(text):
    """-> {"kind", "sub", "word", "coach"} or None (the first feeling of the phrase)."""
    t = (text or "").strip()
    if COACH_ANY.search(t):
        for p_ in COACH_ANY.split(t)[1:]:
            m = _coach_word(normalize(p_))
            if m:
                return m
        return None
    tl = normalize(t)
    for kind, sb, rx in MOOD_RE:
        mm = rx.search(tl)
        if mm:
            return {"kind": kind, "sub": sb, "word": mm.group(0)[:30], "coach": False}
    return None


def _match_for(meta, sid):
    """The analyzed match played during this recording (same map, start time inside the recording)."""
    import cs2coach
    reg = cs2coach.registry()
    start, end = meta["start"], meta.get("end") or meta["start"] + 3600
    first = min([e.get("round") for e in meta.get("rounds") or [] if e.get("round")] or [1])
    back = 15 * 60 + max(0, first - 1) * 120   # a recording that starts mid-match (the server restarted, a reconnect): its match began earlier
    best = None
    for mid in cs2coach.player_matches(int(sid)):
        r = reg.get(mid) or {}
        f = os.path.join(config.DEEP, mid, "meta.json")
        mp = json.load(open(f, encoding="utf-8")).get("map") if os.path.exists(f) else None
        if not r.get("time") or (meta.get("map") and mp and mp != meta["map"]):
            continue
        t = dt.datetime.fromisoformat(r["time"]).timestamp()
        if start - back <= t <= end:
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
        u["moods"] = mood_all(u["text"])
        u["mood"] = u["moods"][0] if u["moods"] else None
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
    L = None
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
        xr = L[(L.steamid == int(sid)) & (L["round"] == r)] if L is not None else None
        xr = xr.iloc[0] if xr is not None and len(xr) else None
        rounds.append({"round": r, "side": xr.side if xr is not None else None, "won": bool(xr.won) if xr is not None else None,
                       "dmg": int(xr.damage) if xr is not None else None, "kills": int(xr.kills) if xr is not None else None,
                       "moods": [{"t": round(u["start"] - t0, 1), **mo} for u in us for mo in u.get("moods") or []],
                       "died_t": dt_, "calls": len(us), "alive_calls": len(alive_us), "info_before_death": any(u["info"] for u in before_death),
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
           "tilt_rounds": [r["round"] for r in rr if any(x["kind"] == "tilt" for x in r["texts"])][:6],
           "moods": {k: sum(1 for u in utts for mo in u.get("moods") or [] if mo["kind"] == k) for k in MOODS + ("note",)}}
    res["tips"] = tips(res)
    res["v"] = ANALYSIS_V
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


def mood_stats(sid):
    """Every aligned recording of the player: the rounds after a frustrated moment (the 3 next rounds) against the
    others, damage per round and rounds won. None under 10 such rounds."""
    rows = []
    for r in recordings():
        if not r["transcribed"] or r.get("practice"):
            continue
        try:
            m = json.load(open(os.path.join(DIR, r["id"] + ".json"), encoding="utf-8"))
            if m.get("steamid") and str(m["steamid"]) != str(sid):
                continue
            f = os.path.join(DIR, r["id"] + ".analysis.json")
            a = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else None
            if a is None or a.get("v") != ANALYSIS_V:
                a = analyze(r["id"], sid)
        except Exception:
            a = None
        if not a or not a.get("match") or not a.get("aligned"):
            continue
        rs = [x for x in a["rounds"] if x.get("dmg") is not None]
        frus = {x["round"] for x in rs if any(mo["kind"] == "frustration" for mo in x.get("moods", []))}
        for x in rs:
            rows.append((any(x["round"] - k in frus for k in (1, 2, 3)), x["dmg"], bool(x["won"])))
    A, O = [r for r in rows if r[0]], [r for r in rows if not r[0]]
    if len(A) < 10 or len(O) < 10:
        return None
    f_ = lambda R: {"n": len(R), "adr": round(sum(r[1] for r in R) / len(R)), "won": round(100 * sum(r[2] for r in R) / len(R))}
    return {"after": f_(A), "other": f_(O)}


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


# ---------- your calls, live ----------
# The calls you already make ("3 B", "rush A", "bombe B", "un Banana") count like a tap on the T read, without a click.
# Only short utterances (a call, not a sentence: dictation is long), transcribed by a low-priority child process on
# the CPU (the graphics card stays for the game). Measured on your own calls: large-v2 takes 10-25 s for a 3 s call on
# 4 cores, small about 1.6 s on 6, base 0.6 s but it gets the words wrong. It listens in English: your callouts are
# English words, and French gets written the English way ("trois" -> "three", "en bas" -> "down").
LIVE_MODEL = "small"
LIVE_THREADS = 6
LIVE_MAX_S, LIVE_MIN_S = 4.5, 0.25
LIVE_FLOOR = 0.003   # speech of a desk microphone can peak at 0.01 RMS


class _Segmenter:
    """Cuts the microphone into utterances (speech, then half a second of silence). A sentence longer than 4.5 s is
    not a call: skipped up to the next silence."""
    def __init__(self, rate, on_utt):
        self.rate, self.on_utt = rate, on_utt
        self.noise, self.buf, self.voiced, self.sil, self.t0, self.skip, self.e = 0.0008, [], 0.0, 0.0, None, False, 0.0

    def feed(self, block, now):
        import numpy as np
        if not len(block):
            return
        dur = len(block) / self.rate
        rms = float(np.sqrt(np.mean(block * block)))
        if rms > max(LIVE_FLOOR, self.noise * 4):
            if not self.buf and not self.skip:
                self.t0 = now - dur
            if not self.skip:
                self.buf.append(block)
            self.voiced += dur
            self.e += rms * rms * dur
            self.sil = 0.0
        else:
            if not self.buf and not self.skip:
                self.noise = 0.98 * self.noise + 0.02 * rms
                return
            self.sil += dur
            if not self.skip:
                self.buf.append(block)
            if self.sil >= 0.5:
                self._flush()
                return
        if not self.skip and sum(len(b) for b in self.buf) / self.rate > LIVE_MAX_S + 0.5:
            self.buf, self.skip = [], True   # a sentence: not a call

    def _flush(self):
        import numpy as np
        buf, voiced, t0, skip, e = self.buf, self.voiced, self.t0, self.skip, self.e
        self.buf, self.voiced, self.sil, self.skip, self.e = [], 0.0, 0.0, False, 0.0
        if skip or not buf or voiced < LIVE_MIN_S:
            return
        a = np.concatenate(buf)
        if self.rate != SR:
            x = np.linspace(0, len(a) - 1, int(len(a) * SR / self.rate))
            a = np.interp(x, np.arange(len(a)), a)
        try:
            self.on_utt(a.astype("float32"), t0, (e / voiced) ** 0.5 if voiced else 0.0)
        except Exception:
            pass


class LiveCalls:
    def __init__(self):
        import queue
        self.q = queue.Queue(maxsize=3)
        self.proc, self.map, self.pending, self.n, self.last, self.levels = None, None, 0, 0, None, []

    def running(self):
        return bool(self.proc and self.proc.poll() is None)

    def start(self, map_name):
        if not settings().get("live", True):
            return
        self.map = map_name
        if self.running():
            return
        try:
            flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            os.makedirs(DIR, exist_ok=True)
            self.proc = subprocess.Popen([sys.executable, os.path.join(config.HERE, "voice.py"), "live"], cwd=config.HERE,
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=open(os.path.join(DIR, "live.log"), "w", encoding="utf-8"), creationflags=flags)
            self.pending = 0
            threading.Thread(target=self._send, args=(self.proc,), daemon=True).start()
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        except Exception as e:
            print("live calls unavailable:", e, flush=True)
            self.proc = None

    def stop(self):
        if self.running():
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None

    def push(self, audio, t0, rms=0.0):
        """From the microphone thread: never blocks (a call that waits too long is useless anyway). A shout (twice as
        loud as your usual speech, once 8 phrases are known) after your death or a lost round is a frustrated moment."""
        if rms:
            lv = sorted(self.levels)
            if len(lv) >= 8 and rms >= 2.2 * lv[len(lv) // 2]:
                try:
                    import gsi
                    gsi.voice_heat(t0)
                except Exception:
                    pass
            self.levels = (self.levels + [rms])[-60:]
        if self.running() and self.pending < 2:
            try:
                self.q.put_nowait((audio, t0))
            except Exception:
                pass

    def _send(self, proc):
        while proc.poll() is None:
            try:
                audio, t0 = self.q.get(timeout=1)
            except Exception:
                continue
            try:
                self.pending += 1
                self.n += 1
                fr = False
                try:   # dead, between rounds or buying: what you say then is more often how you feel than a call
                    import gsi
                    fr = (not gsi.STATE.get("_alive", True)) or gsi.STATE.get("round_phase") in ("over", "freezetime")
                except Exception:
                    pass
                proc.stdin.write((json.dumps({"id": self.n, "t": t0, "map": self.map, "n": int(len(audio)), "fr": fr}) + "\n").encode())
                proc.stdin.write(audio.astype("<f4").tobytes())
                proc.stdin.flush()
            except Exception:
                return

    def _read(self, proc):
        for line in proc.stdout:
            self.pending = max(0, self.pending - 1)
            try:
                r = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            p = parse_call(r.get("text") or "", r.get("map"))
            mo = mood_of(r.get("mood_text") or "") if r.get("mood_text") else None
            self.last = {"text": r.get("text"), "s": r.get("s"), "parsed": p, "mood": mo}
            if mo and mo["kind"] in MOODS:
                try:
                    import gsi
                    gsi.voice_mood(mo, r.get("t"))
                except Exception as e:
                    print("live mood:", e, flush=True)
                continue
            if p:
                try:
                    import gsi
                    gsi.voice_call(p, r.get("t"))
                except Exception as e:
                    print("live call:", e, flush=True)


LIVE = LiveCalls()


def _live_prompt(map_name):
    words = ["A", "B", "mid", "one", "two", "three", "un", "deux", "trois", "rush", "bomb", "full"]
    try:
        import plan
        words += [x["name"] for x in (plan.zone_refs().get(map_name or "") or {}).get("zones", [])][:30]
    except Exception:
        pass
    return "Calls: " + ", ".join(words) + "."


def live_loop():
    """Child process: utterances in on stdin (a JSON line, then the 16 kHz samples), their text out on stdout."""
    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(LIVE_MODEL, device="cpu", compute_type="int8", cpu_threads=LIVE_THREADS)
    inp, prompts = sys.stdin.buffer, {}
    while True:
        line = inp.readline()
        if not line:
            break
        try:
            h = json.loads(line)
            a = np.frombuffer(inp.read(4 * int(h["n"])), dtype="<f4")
        except Exception:
            continue
        mp = h.get("map")
        if mp not in prompts:
            prompts[mp] = _live_prompt(mp)
        t = time.time()
        try:
            segs, _ = model.transcribe(a, language="en", beam_size=1, condition_on_previous_text=False, vad_filter=False,
                                       initial_prompt=prompts[mp], without_timestamps=True, max_new_tokens=20,
                                       temperature=0.0)   # no retries: a late call is useless
            # unsure (noise, a mumble): the model tends to repeat its prompt, dropped
            text = " ".join(x.text for x in segs if (x.no_speech_prob or 0) < 0.6 and (x.avg_logprob or 0) > -1.0).strip()
        except Exception as e:
            text = ""
            print("live transcription:", e, file=sys.stderr, flush=True)
        if HALLUCINATIONS.search(text):
            text = ""
        mood_text = None
        if COACH_ANY.search(text):   # "coach, perdu": the word said in French, read again in French
            try:
                segs, _ = model.transcribe(a, language="fr", beam_size=1, condition_on_previous_text=False, vad_filter=False,
                                           initial_prompt="Coach, perdu. Coach, confiant. Coach, énervé. Coach, bloqué. Coach, stressé. Coach, fatigué. Coach, cheat.",
                                           without_timestamps=True, max_new_tokens=12, temperature=0.0)
                fr = " ".join(x.text for x in segs).strip()
                mood_text = fr if COACH_ANY.search(fr) else "coach " + fr
            except Exception as e:
                print("live mood transcription:", e, file=sys.stderr, flush=True)
                mood_text = text
        elif h.get("fr") and len(a) >= SR // 2 and not parse_call(text, mp):   # not a call: read in French for how you feel
            try:
                segs, _ = model.transcribe(a, language="fr", beam_size=1, condition_on_previous_text=False, vad_filter=False,
                                           initial_prompt="Putain. Qu'est-ce qu'on fait ? Je comprends pas. Pourquoi tu peek ? Bien joué. Ah vas-y.",
                                           without_timestamps=True, max_new_tokens=24, temperature=0.0)
                fr_ = " ".join(x.text for x in segs if (x.no_speech_prob or 0) < 0.6 and (x.avg_logprob or 0) > -1.0).strip()
                mood_text = fr_ if fr_ and mood_of(fr_) else None
            except Exception as e:
                print("live mood transcription:", e, file=sys.stderr, flush=True)
        sys.stdout.write(json.dumps({"id": h.get("id"), "t": h.get("t"), "map": mp, "text": text, "mood_text": mood_text,
                                     "s": round(time.time() - t, 2)}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


# what a call says: a site, how many, a zone (with its side of the map), a rush, the bomb, one alone
CALL_NUM = {"un": 1, "une": 1, "1": 1, "deux": 2, "2": 2, "trois": 3, "3": 3, "quatre": 4, "4": 4, "cinq": 5, "5": 5, "full": 5, "tous": 5,
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}   # your calls mix French and English
LEVEL_SITE = {"de_nuke": {"bas": "B", "lower": "B", "down": "B", "downstairs": "B", "haut": "A", "upper": "A", "upstairs": "A"}}   # Nuke: B is downstairs
_VOCAB = {}


def _zone_vocab(map_name):
    """Spoken word -> (callout, side of the map) for a map: the words of its callouts, plus the French ones."""
    if map_name in _VOCAB:
        return _VOCAB[map_name]
    v = {}
    try:
        import team
        from map_analysis import humanize
        for key, reg in ((team.map_meta().get(map_name) or {}).get("regions") or {}).items():
            name = humanize(key, map_name) if key != "?" else None
            if not name or "spawn" in name.lower():
                continue
            for w in re.findall(r"[a-zà-ÿ]+", name.lower()):
                if len(w) >= 4 and w not in ("site", "main", "long", "short", "back", "upper", "lower", "middle", "side", "room"):
                    v.setdefault(w, (name, reg))
    except Exception:
        pass
    fr = {"banane": "banana", "appart": "apps", "apparts": "apps", "appartements": "apartments", "rampe": "ramp", "fenêtre": "window",
          "palais": "palace", "connecteur": "connector", "tunnel": "tunnels", "pont": "bridge"}
    for w_fr, w_en in fr.items():
        if w_en in v and w_fr not in v:
            v[w_fr] = v[w_en]
    _VOCAB[map_name] = v
    return v


A_CTX = (r"(?:\b(?:en|sur|site|vers|bombe|bomb|rush|full|tous|sont|est|c'est|go|là|on|at|in|to|is|are)\s+"
         r"|\b(?:un|une|deux|trois|quatre|cinq|one|two|three|four|five|[1-5])\s+(?:en\s+|on\s+|at\s+)?)a\b"
         r"|\ba\s+(?:site|main|long|short)\b|^a(?:\s+a)*$")


def parse_call(text, map_name):
    """A short call ("3 B", "rush A", "bombe B", "un seul Banana") read for the T read; None for anything else (a
    sentence, small talk)."""
    if not text or HALLUCINATIONS.search(text):
        return None
    t = normalize(text).strip(" .!?,")
    words = [re.sub(r"'s$", "", w) for w in re.findall(r"[a-zà-ÿ0-9']+", t)]
    if not words or len(words) > 8:
        return None
    site = "B" if re.search(r"\b(b|bé|bee)\b", t) else None
    if re.search(A_CTX, t):
        site = "A" if site is None else None   # both letters: unclear
    n = next((CALL_NUM[w] for w in words if w in CALL_NUM), None)
    zone = reg = None
    vocab = _zone_vocab(map_name)
    hits = [vocab.get(w) or vocab.get(w + "s") for w in words]
    hits = [h for h in hits if h]
    if len({h[0] for h in hits}) >= 3:
        return None   # a list of callouts: the model repeating its prompt, not a call
    if hits:
        zone, reg = hits[0]
    if site is None and reg in ("A", "B"):
        site = reg
    if site is None:
        site = next((LEVEL_SITE.get(map_name, {})[w] for w in words if w in LEVEL_SITE.get(map_name, {})), None)
    rush = bool(re.search(r"\b(rush|rushent|rouch|rushs)\b", t))
    bomb = bool(re.search(r"\b(bombe|bomb|plant|plantée?|posée?|planted)\b", t))
    lone = bool(re.search(r"\b(seul|solo|lurk|lurker)\b", t)) or n == 1
    clear = bool(re.search(r"\b(clear|clean|empty|nobody|vide|personne|no one)\b", t))   # "B clear", "personne en B"
    me = bool(re.search(r"\b(je suis|j'suis|chui|i'?m|i am|je joue|je reste|je tiens|i play|i'?ll play|i hold|moi je suis)\b", t))   # your own spot
    if not (site or zone or rush or bomb):
        return None
    if len(words) > 5 and not (n or zone or rush or bomb):
        return None   # a sentence with a letter in it, not a call
    regs = [h[1] for h in hits if h[1] in ("A", "B")]   # every zone named, with its side of the map ("1 jungle, 1 connector": A twice)
    return {"site": site, "n": n, "zone": zone, "rush": rush, "bomb": bomb, "lone": lone, "clear": clear, "regs": regs, "me": me}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        live_loop()
    elif len(sys.argv) > 2 and sys.argv[1] == "transcribe":
        print(transcribe(sys.argv[2]), "phrases")
