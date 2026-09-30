"""Player archetype from weapons, movement, game sense, playstyle and reactions, relative to the reference base."""
import numpy as np
import pandas as pd

import style

MIN_ROUNDS_REF = 20
ROLES = {
    "awper": {"name": "AWPer", "icon": "🎯",
              "what": "Il tient les angles longs et prend le premier kill avec l'AWP. Son économie et son placement dictent le rythme de l'équipe.",
              "tips": ["Change de spot après chaque tir : un AWPer qui re-peek le même angle se fait punir.",
                       "Joue avec un coéquipier qui te trade ou te flashe : l'AWP coûte 4 750 $, ne la perds pas seul.",
                       "En eco, sauve l'AWP plutôt que de la jouer à 1 contre 3."],
              "key": [("awp_share", "part de kills à l'AWP"), ("open_win", "premiers duels gagnés"), ("hold_share", "duels commencés posé")]},
    "entry": {"name": "Entry fragger", "icon": "⚡",
              "what": "Il entre le premier sur le site en attaque pour prendre de l'espace. Sa mort est acceptable si elle est tradée.",
              "tips": ["Entre toujours derrière une flash (la tienne ou celle d'un coéquipier), jamais à sec.",
                       "Annonce ton entrée pour que ton second entry soit prêt à trader dans la seconde.",
                       "Vise les angles les plus probables dans l'ordre (pré-aim) : ta survie tient à ta première balle."],
              "key": [("open_rate_T", "premiers duels provoqués par round en T"), ("open_win", "premiers duels gagnés"), ("traded_share", "morts vengées")]},
    "trader": {"name": "Second entry / Trader", "icon": "🔁",
               "what": "Il suit l'entry à courte distance et venge chaque mort. Il transforme un 1 contre 1 perdu en échange équilibré.",
               "tips": ["Reste à moins de 500 unités de ton entry, dans la même ligne de vue.",
                        "Pré-vise l'angle d'où ton coéquipier va se faire tirer dessus, pas celui qu'il regarde.",
                        "Ne peeke pas en même temps que lui : un temps de retard, puis le trade."],
               "key": [("trade_rate", "trades par round"), ("trade_time", "délai de trade (s)"), ("iso_T", "distance au coéquipier en T")]},
    "lurker": {"name": "Lurker", "icon": "🐍",
               "what": "Il joue seul, loin du groupe, pour couper les rotations et prendre les défenseurs à revers au bon moment.",
               "tips": ["Ton timing compte plus que ton aim : frappe quand l'équipe exécute, pas avant.",
                        "Donne l'info : tu es souvent le seul à voir les rotations adverses.",
                        "Si le round est perdu d'avance, sauve ton arme : un lurker mort sans impact coûte cher."],
               "key": [("iso_T", "distance au coéquipier en T"), ("late_share", "part de kills après 60 s"), ("first_duel_t", "premier duel du round (s)")]},
    "support": {"name": "Support", "icon": "🛡️",
                "what": "Il prépare le terrain avec ses grenades (smokes, flashs, molotovs) et joue pour que ses coéquipiers gagnent leurs duels.",
                "tips": ["Apprends les exécutions complètes de tes cartes : 2 smokes, 2 flashs, 1 molotov par site.",
                         "Flashe pour tes coéquipiers : annonce, puis lance au-dessus du mur.",
                         "Garde une grenade pour le retake ou le post-plant."],
                "key": [("util_pr", "grenades par round"), ("blind_pr", "ennemis aveuglés par round"), ("util_dmg_pr", "dégâts de grenades par round")]},
    "anchor": {"name": "Anchor", "icon": "⚓",
               "what": "En défense, il tient un site, souvent seul, et gagne du temps jusqu'aux rotations. Patience et utilitaires défensifs.",
               "tips": ["Ton but est de retarder, pas de tuer : molotov et smoke dès le premier bruit.",
                        "Change de position d'un round à l'autre pour ne pas te faire pré-viser.",
                        "Joue en retrait quand tu es seul : recule et attends le retake plutôt que de mourir en 1 contre 3."],
               "key": [("ct_site", "temps passé sur un site en CT"), ("hold_share", "duels commencés posé"), ("ct_top", "concentration sur une zone en CT")]},
    "closer": {"name": "Closer / Clutcher", "icon": "🧊",
               "what": "Il fait ses kills tard dans le round : après-plant, retake, clutchs. Il garde son sang-froid quand le round se décide.",
               "tips": ["Joue le temps et la bombe en clutch : isole les duels un par un.",
                        "Reste en vie en début de round : ton impact arrive plus tard.",
                        "En après-plant, joue les angles qui voient la bombe, pas le spawn adverse."],
               "key": [("late_share", "part de kills après 60 s"), ("kpr", "kills par round"), ("hold_share", "duels commencés posé")]},
}
SOURCES = [("Refrag, les rôles d'une équipe CS2", "https://refrag.gg/blog/cs2-team-roles-explained/"),
           ("Esports.gg, tous les rôles en CS2", "https://esports.gg/news/counter-strike-2/all-roles-in-cs2/"),
           ("CS2Hype, rôle d'entry fragger", "https://cs2hype.com/roles/entry-fragger"),
           ("CS2Hype, rôle de rifler", "https://cs2hype.com/roles/rifler")]
WEAPON_FR = {"ak47": "AK-47", "m4a1": "M4A4", "m4a1_silencer": "M4A1-S", "awp": "AWP", "ssg08": "Scout", "deagle": "Desert Eagle",
             "galilar": "Galil", "famas": "FAMAS", "aug": "AUG", "sg556": "SG 553", "mac10": "MAC-10", "mp9": "MP9", "mp7": "MP7",
             "ump45": "UMP-45", "p90": "P90", "glock": "Glock", "usp_silencer": "USP-S", "hkp2000": "P2000", "p250": "P250",
             "tec9": "Tec-9", "fiveseven": "Five-SeveN", "cz75a": "CZ75", "mag7": "MAG-7", "nova": "Nova", "xm1014": "XM1014"}


def aggregate(df):
    """Per-player pooled features."""
    g = df.groupby("steamid")
    s = lambda c: g[c].sum()

    def wmean(col, w):
        x = df[[col, w, "steamid"]].dropna()
        x = x[x[w] > 0]
        return (x[col] * x[w]).groupby(x.steamid).sum() / x.groupby("steamid")[w].sum()
    out = pd.DataFrame({"name": g["name"].last(), "rounds": s("rounds"), "t_rounds": s("t_rounds"), "ct_rounds": s("ct_rounds"),
                        "kills": s("kills"), "deaths": s("deaths"), "matches": g.size()})
    k = out.kills.clip(lower=1)
    out["kpr"] = out.kills / out.rounds.clip(lower=1)
    for c in ("awp", "rifle", "smg", "shotgun", "pistol", "deagle"):
        out[f"{c}_share"] = s(f"k_{c}") / k
    out["open_rate"] = s("open_att") / out.rounds.clip(lower=1)
    out["open_rate_T"] = s("open_att_T") / out.t_rounds.clip(lower=1)
    out["open_win"] = s("open_won") / s("open_att").clip(lower=1)
    out["trade_rate"] = s("trade_kills") / out.rounds.clip(lower=1)
    out["traded_share"] = s("traded_deaths") / out.deaths.clip(lower=1)
    out["hs_share"] = s("hs_kills") / k
    out["late_share"] = s("late_kills") / k
    out["early_share"] = s("early_kills") / k
    util = s("flashes") + s("smokes") + s("molotovs") + s("hes")
    out["util_pr"] = util / out.rounds.clip(lower=1)
    out["flash_pr"] = s("flashes") / out.rounds.clip(lower=1)
    out["blind_pr"] = s("flash_enemies") / out.rounds.clip(lower=1)
    out["util_dmg_pr"] = s("util_dmg") / out.rounds.clip(lower=1)
    out["iso_T"] = wmean("iso_T", "t_rounds")
    out["iso_CT"] = wmean("iso_CT", "ct_rounds")
    out["move_share"] = wmean("move_share", "duels")
    out["hold_share"] = wmean("hold_share", "duels")
    out["scoped"] = wmean("scoped_share", "duels")
    out["first_duel_t"] = wmean("first_duel_t", "rounds")
    out["duel_len_won"] = wmean("duel_len_won", "kills")
    out["trade_time"] = wmean("trade_time", "trade_kills")
    out["ct_site"] = wmean("ct_site_share", "ct_rounds")
    out["ct_top"] = wmean("ct_top_zone_share", "ct_rounds")
    return out


def top_weapons(df, steamid):
    c = {}
    for tw in df[df.steamid == steamid].top_weapons.dropna():
        for part in tw.split(";"):
            if ":" in part:
                w, n = part.rsplit(":", 1)
                c[w] = c.get(w, 0) + int(n)
    return sorted(c.items(), key=lambda x: -x[1])[:4]


def pct_table(ref, cols):
    return {c: ref[c].dropna().sort_values().to_numpy() for c in cols}


def pct(sorted_vals, v):
    if v is None or pd.isna(v) or not len(sorted_vals):
        return None
    return float(np.searchsorted(sorted_vals, v, side="right") / len(sorted_vals) * 100)


def scores(P):
    """Role scores (0-100) from percentiles P (dict metric -> percentile)."""
    p = lambda k, inv=False: (100 - P[k] if inv else P[k]) if P.get(k) is not None else 50
    sc = {
        "awper": 0.6 * p("awp_share") + 0.4 * p("scoped"),
        "entry": 0.45 * p("open_rate_T") + 0.25 * p("move_share") + 0.3 * p("first_duel_t", True),
        "trader": 0.5 * p("trade_rate") + 0.3 * p("iso_T", True) + 0.2 * p("trade_time", True),
        "lurker": 0.55 * p("iso_T") + 0.25 * p("first_duel_t") + 0.2 * p("late_share"),
        "support": 0.45 * p("util_pr") + 0.35 * p("blind_pr") + 0.2 * p("open_rate", True),
        "anchor": 0.4 * p("ct_site") + 0.3 * p("ct_top") + 0.3 * p("hold_share"),
        "closer": 0.6 * p("late_share") + 0.4 * p("kpr"),
    }
    return sc


def damp_awp(sc, awp_share):
    """An AWPer score only means something for players who actually kill with the AWP."""
    sc = dict(sc)
    sc["awper"] *= min(1.0, (awp_share or 0) / 0.25)
    return sc


def role_of(row, P, sc):
    if (row.get("awp_share") or 0) >= 0.25:
        return "awper"
    return max((k for k in sc if k != "awper"), key=sc.get)


_CACHE = {}


def reference():
    if "ref" not in _CACHE:
        df = style.load()
        agg = aggregate(df)
        ref = agg[agg.rounds >= MIN_ROUNDS_REF].copy()
        cols = [c for c in agg.columns if c not in ("name", "rounds", "t_rounds", "ct_rounds", "kills", "deaths", "matches")]
        T = pct_table(ref, cols)
        # archetype of every reference player, to compare a player with his peers
        roles = []
        for sid, r in ref.iterrows():
            P = {c: pct(T[c], r[c]) for c in cols}
            roles.append(role_of(r.to_dict(), P, damp_awp(scores(P), r["awp_share"])))
        ref["role"] = roles
        _CACHE["ref"] = (df, agg, ref, T, cols)
    return _CACHE["ref"]


def fmt(v, kind):
    if v is None or pd.isna(v):
        return "—"
    if kind == "pct":
        return f"{v * 100:.0f} %"
    if kind == "s":
        return f"{v:.1f} s".replace(".", ",")
    if kind == "u":
        return f"{v:.0f} u"
    return f"{v:.2f}".replace(".", ",")


KIND = {"awp_share": "pct", "open_win": "pct", "hold_share": "pct", "open_rate_T": "n", "traded_share": "pct", "trade_rate": "n",
        "trade_time": "s", "iso_T": "u", "late_share": "pct", "first_duel_t": "s", "util_pr": "n", "blind_pr": "n",
        "util_dmg_pr": "n", "ct_site": "pct", "ct_top": "pct", "kpr": "n", "move_share": "pct", "duel_len_won": "s", "hs_share": "pct"}


def profile(steamid, xhair_pct=None):
    df, agg, ref, T, cols = reference()
    sid = str(steamid)
    if sid not in agg.index:
        return None
    r = agg.loc[sid]
    if r.rounds < 15:
        return None
    P = {c: pct(T[c], r[c]) for c in cols}
    sc = damp_awp(scores(P), r.awp_share)
    main = role_of(r.to_dict(), P, sc)
    ranked = sorted(sc.items(), key=lambda x: -x[1])
    second = next((k for k, v in ranked if k != main and v >= 55 and (k != "awper" or (r.awp_share or 0) >= 0.15)), None)
    versatile = sc.get(main, 0) < 60 and main != "awper"
    # traits
    traits = []
    def trait(cond, label, text):
        if cond:
            traits.append({"label": label, "text": text() if callable(text) else text})
    ms, iso, dl, tt, hs, up = P.get("move_share"), P.get("iso_T"), P.get("duel_len_won"), P.get("trade_time"), P.get("hs_share"), P.get("util_pr")
    trait(ms is not None and ms >= 70, "Agressif", lambda: f"Tu engages en mouvement dans {fmt(r.move_share, 'pct')} de tes duels (plus que {ms:.0f} % des joueurs).")
    trait(ms is not None and ms <= 30, "Patient", lambda: f"Tu attends l'adversaire : {fmt(r.hold_share, 'pct')} de tes duels commencent posé.")
    trait(iso is not None and iso >= 70, "Solitaire", lambda: f"En attaque, ton coéquipier le plus proche est en médiane à {fmt(r.iso_T, 'u')} (plus loin que {iso:.0f} % des joueurs).")
    trait(iso is not None and iso <= 30, "Joueur d'équipe", lambda: f"En attaque, tu restes groupé : {fmt(r.iso_T, 'u')} du coéquipier le plus proche en médiane.")
    trait(dl is not None and dl <= 30, "Réflexes rapides", lambda: f"Tu conclus tes duels gagnés en {fmt(r.duel_len_won, 's')} en médiane (plus vite que {100 - dl:.0f} % des joueurs).")
    trait(dl is not None and dl >= 75, "Duels longs", lambda: f"Tes duels gagnés durent {fmt(r.duel_len_won, 's')} en médiane : tu gagnes à l'usure plus qu'au premier tir.")
    trait(tt is not None and tt <= 30 and r.trade_rate > 0, "Réflexe de trade", lambda: f"Tu venges un coéquipier en {fmt(r.trade_time, 's')} en médiane.")
    trait(hs is not None and hs >= 75, "Tireur de tête", lambda: f"{fmt(r.hs_share, 'pct')} de tes kills à la tête (plus que {hs:.0f} % des joueurs).")
    trait(up is not None and up >= 75, "Utilitaires", lambda: f"{fmt(r.util_pr, 'n')} grenade(s) par round (plus que {up:.0f} % des joueurs).")
    trait(up is not None and up <= 25, "Peu de grenades", lambda: f"Seulement {fmt(r.util_pr, 'n')} grenade par round (moins que {100 - up:.0f} % des joueurs).")
    fd = P.get("first_duel_t")
    trait(fd is not None and fd <= 25, "Début de round", lambda: f"Ton premier duel arrive vers {fmt(r.first_duel_t, 's')} : tu joues le contact tôt.")
    trait(fd is not None and fd >= 75, "Fin de round", lambda: f"Ton premier duel arrive vers {fmt(r.first_duel_t, 's')} : tu laisses le round se développer.")
    trait(xhair_pct is not None and xhair_pct >= 75, "Viseur bien placé", lambda: f"Ton viseur est mieux placé que celui de {xhair_pct:.0f} % des joueurs avant les duels.")
    # weapons
    shares = {"AWP": r.awp_share, "rifles": r.rifle_share, "SMG": r.smg_share, "fusils à pompe": r.shotgun_share,
              "pistolets": r.pistol_share + r.deagle_share}
    main_w = max(shares, key=lambda k: shares[k] or 0)
    tw = top_weapons(df, sid)
    weapons = {"shares": {k: round(float(v or 0) * 100) for k, v in shares.items()},
               "top": [{"weapon": WEAPON_FR.get(w, w), "kills": n} for w, n in tw]}
    # peers: players of the same archetype in the base
    peers = ref[ref.role == main]
    peer_rows = []
    for m, label in ROLES[main]["key"]:
        if m not in r or peers[m].dropna().empty:
            continue
        top = peers.sort_values("kpr", ascending=False).head(max(5, len(peers) // 4))
        peer_rows.append({"metric": m, "label": label, "you": fmt(r[m], KIND.get(m, "n")),
                          "peers": fmt(peers[m].median(), KIND.get(m, "n")), "best": fmt(top[m].median(), KIND.get(m, "n"))})
    role = ROLES[main]
    name = ("Rifler polyvalent, tendance " + role["name"]) if versatile else role["name"]
    desc = [f"{'Profil polyvalent' if versatile else role['name']} : {role['what']}"]
    desc.append(f"Armes : {weapons['shares']['rifles']} % de tes kills au rifle, {weapons['shares']['AWP']} % à l'AWP, "
                f"{weapons['shares']['SMG']} % en SMG, {weapons['shares']['pistolets']} % au pistolet. "
                + ("Favorites : " + ", ".join(f"{t['weapon']} ({t['kills']})" for t in weapons["top"][:3]) + "." if weapons["top"] else ""))
    desc.append(f"Déplacements : {'tu engages souvent en mouvement' if (r.move_share or 0) > 0.4 else 'tu joues surtout posé'}, "
                f"à {fmt(r.iso_T, 'u')} de ton coéquipier le plus proche en attaque et {fmt(r.iso_CT, 'u')} en défense.")
    desc.append(f"Notions : {fmt(r.util_pr, 'n')} grenade(s) et {fmt(r.blind_pr, 'n')} ennemi(s) aveuglé(s) par round, "
                f"{fmt(r.trade_rate, 'n')} trade(s) par round, {fmt(r.traded_share, 'pct')} de tes morts vengées.")
    desc.append(f"Réactions : duels gagnés conclus en {fmt(r.duel_len_won, 's')}, premier duel du round vers {fmt(r.first_duel_t, 's')}"
                + (f", trade en {fmt(r.trade_time, 's')}" if r.trade_time == r.trade_time and r.trade_rate > 0 else "") + ".")
    return {"role": main, "name": name, "icon": role["icon"], "versatile": bool(versatile),
            "second": {"role": second, "name": ROLES[second]["name"]} if second else None,
            "scores": [{"role": k, "name": ROLES[k]["name"], "score": round(v)} for k, v in ranked],
            "traits": traits, "weapons": weapons, "description": desc, "what": role["what"], "tips": role["tips"],
            "peers": peer_rows, "n_peers": int(len(peers)), "n_ref": int(len(ref)), "rounds": int(r.rounds),
            "sources": [{"label": a, "url": u} for a, u in SOURCES]}
