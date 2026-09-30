"""Public data from a SteamID alone: profile resolution (Steam) and Leetify public API."""
import json
import re
import urllib.request

API = "https://api-public.cs-prod.leetify.com"


_LAST = [0.0]
MIN_GAP = 3.2  # Leetify's public API allows roughly one request every 3 seconds


def _get(url, timeout=20, tries=4):
    import time
    import urllib.error
    for attempt in range(tries):
        wait = MIN_GAP - (time.time() - _LAST[0])
        if wait > 0 and "leetify" in url:
            time.sleep(wait)
        _LAST[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 cs2-coach"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < tries - 1:
                time.sleep(15 * (attempt + 1))
                continue
            raise


def resolve_steamid(s):
    """SteamID64, profile URL (/profiles/<id> or /id/<vanity>) or vanity name -> (steamid64, name)."""
    s = str(s).strip().rstrip("/")
    m = re.search(r"(7656\d{13})", s)
    url = f"https://steamcommunity.com/profiles/{m.group(1)}" if m else \
        (s if s.startswith("http") else f"https://steamcommunity.com/id/{s}")
    try:
        xml = _get(url + "/?xml=1").decode("utf-8", "replace")
        sid = re.search(r"<steamID64>(\d+)</steamID64>", xml)
        name = re.search(r"<steamID><!\[CDATA\[(.*?)\]\]>", xml)
        if sid:
            return int(sid.group(1)), name.group(1) if name else None
    except Exception:
        pass
    return (int(m.group(1)), None) if m else (None, None)


def profile(steamid):
    try:
        return json.loads(_get(f"{API}/v3/profile?steam64_id={steamid}"))
    except Exception:
        return None


def matches(steamid):
    try:
        return json.loads(_get(f"{API}/v3/profile/matches?steam64_id={steamid}"))
    except Exception:
        return []


def light_advice(prof, ms, steamid):
    """Diagnosis from Leetify's aggregated stats when no demo is available."""
    st, rt = prof.get("stats", {}), prof.get("rating", {})
    R, S = [], []

    def add(score, title, short, why, do):
        R.append({"id": short, "score": score, "title": title, "short": short, "why": why, "do": do})

    g = lambda k: st.get(k)
    if g("preaim") is not None:
        (S.append(f"Viseur bien placé ({g('preaim'):.1f}° d'écart)".replace(".", ",")) if g("preaim") <= 7 else
         add(10 + g("preaim"), f"Viseur mal placé avant les duels : {g('preaim'):.1f}° d'écart".replace(".", ","), "Viseur à hauteur de tête",
             ["Écart moyen entre ton viseur et l'ennemi au moment où il apparaît (Leetify)."],
             ["Pré-vise les angles à hauteur de tête en te déplaçant.", "Map d'entraînement : Prefire / crosshair placement."]))
    if g("counter_strafing_good_shots_ratio") is not None:
        cs = g("counter_strafing_good_shots_ratio")
        (S.append(f"Contre-strafe propre ({cs:.0f} % de bons tirs)") if cs >= 80 else
         add(25 - cs / 5, f"Seulement {cs:.0f} % de tirs bien contre-strafés", "Contre-strafe avant de tirer",
             ["Part de tes tirs partis à l'arrêt."], ["Tape la direction opposée avant chaque tir, au pistolet comme au rifle."]))
    fr, fo = g("flashbang_hit_friend_per_flashbang"), g("flashbang_hit_foe_per_flashbang")
    if fr is not None and fr >= 0.35:
        add(15 + fr * 10, f"Tes flashs aveuglent {fr:.2f} coéquipier par flash".replace(".", ","), "Flashe pour tes coéquipiers, pas sur eux",
            [f"Ennemis aveuglés par flash : {fo:.2f}.".replace(".", ","), f"Flashs menant à un kill : {g('flashbang_leading_to_kill') or 0:.0f} %."],
            ["Annonce ta flash avant de la lancer.", "Apprends 2 popflashs par site : elles explosent au-dessus du mur, pas sur ton équipe."])
    ud = g("utility_on_death_avg")
    if ud is not None and ud >= 100:
        add(10 + ud / 20, f"{ud:.0f} $ de grenades en poche à chaque mort en moyenne", "Vide ta poche avant 40 s",
            ["Valeur moyenne des grenades non utilisées au moment de ta mort."], ["Lance tes grenades avant le contact."])
    for side, k in (("CT", "ct_opening_duel_success_percentage"), ("T", "t_opening_duel_success_percentage")):
        v = g(k)
        if v is not None and v < 45:
            add(8 + (45 - v) / 2, f"Premiers duels en {side} : {v:.0f} % gagnés", f"Ne prends pas le 1er duel seul en {side}",
                ["Taux de victoire des duels d'ouverture (Leetify)."], ["Laisse l'ouverture à un coéquipier ou prends-la avec une flash."])
    tr = g("traded_deaths_success_percentage")
    if tr is not None and tr < 50:
        add(20 - tr / 5, f"Seulement {tr:.0f} % de tes morts « tradables » sont vengées", "Joue à 2 secondes d'un coéquipier",
            ["Quand un trade était possible, il a eu lieu dans ce pourcentage de cas."], ["Reste à portée de trade d'un coéquipier."])
    rtm = g("reaction_time_ms")
    if rtm is not None and rtm > 650:
        add(8, f"Temps de réaction de {rtm:.0f} ms", "Échauffement avant de jouer", ["Mesuré sur tes duels (Leetify)."],
            ["10 minutes d'Aim Botz et de deathmatch avant chaque session."])
    by_map = {}
    for m in ms:
        me = next((x for x in m.get("stats", []) if x.get("steam64_id") == str(steamid)), None)
        if not me:
            continue
        b = by_map.setdefault(m["map_name"], {"n": 0, "w": 0, "k": 0, "d": 0, "dmg": 0, "rounds": 0})
        b["n"] += 1
        b["w"] += me.get("rounds_won", 0) > me.get("rounds_lost", 0)
        b["k"] += me.get("total_kills", 0)
        b["d"] += me.get("total_deaths", 0)
        b["dmg"] += me.get("total_damage", 0)
        b["rounds"] += me.get("rounds_count", 0)
    return {"rules": sorted(R, key=lambda r: -r["score"]), "strengths": S, "maps": {}, "match_notes": {},
            "leetify": {"name": prof.get("name"), "ratings": rt, "stats": st, "ranks": prof.get("ranks"), "total_matches": prof.get("total_matches"),
                        "winrate": prof.get("winrate"), "by_map": by_map,
                        "recent": [{"time": m["finished_at"], "source": m["data_source"], "map": m["map_name"],
                                    "score": [t["score"] for t in m["team_scores"]],
                                    "me": next(({k: x.get(k) for k in ("total_kills", "total_deaths", "total_assists", "dpr", "rounds_won", "rounds_lost",
                                                                        "accuracy_head", "counter_strafing_shots_good_ratio", "flashbang_hit_friend", "flashbang_hit_foe", "leetify_rating")}
                                                for x in m.get("stats", []) if x.get("steam64_id") == str(steamid)), None)} for m in ms[:30]]}}
