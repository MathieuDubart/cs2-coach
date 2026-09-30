"""Enrich rule-based advice with reference-population benchmarks, drills and sources."""
LEET = ("Leetify, glossaire des statistiques", "https://leetify.com/blog/leetify-stats-glossary/")
SOURCES = {
    "trade": [("CSGO-Guides, trading et refrag", "https://csgo-guides.com/gameplay/trading"),
              ("scope.gg, qu'est-ce qu'un trade kill", "https://blog.scope.gg/trade-kills-en/"),
              ("Boosteria, angles et tirs croisés", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires")],
    "nades": [LEET, ("CSNADES.gg, lineups par carte", "https://csnades.gg/maps"), ("lineups.gg", "https://lineups.gg/")],
    "flash": [LEET, ("CSNADES.gg, popflashs par carte", "https://csnades.gg/maps")],
    "flashmates": [LEET, ("CSNADES.gg, popflashs par carte", "https://csnades.gg/maps")],
    "pistol": [("Guide Steam, pourquoi et comment contre-strafer", "https://steamcommunity.com/sharedfiles/filedetails/?id=3099945585"), LEET],
    "spray": [LEET, ("Guide Steam, contre-strafe et précision", "https://steamcommunity.com/sharedfiles/filedetails/?id=3099945585")],
    "hold": [("Boosteria, angles et tirs croisés", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires"),
             ("CS2Hype, rôle de rifler", "https://cs2hype.com/roles/rifler")],
    "range": [("Boosteria, angles et tirs croisés", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires")],
    "hp": [("CSGO-Guides, trading et refrag", "https://csgo-guides.com/gameplay/trading")],
    "eco": [("CSGO-Guides, gestion de l'argent", "https://csgo-guides.com/gameplay/money-management"),
            ("Hard2Kill, guide de l'économie", "https://hard2kill.gg/guides/cs2-economy-guide")],
    "xhair": [LEET],
    "early": [("CS2Hype, rôle d'entry fragger", "https://cs2hype.com/roles/entry-fragger"), ("CSGO-Guides, trading et refrag", "https://csgo-guides.com/gameplay/trading")],
    "lastalive": [("Boosteria, angles et tirs croisés", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires"),
                  ("CSGO-Guides, trading et refrag", "https://csgo-guides.com/gameplay/trading")],
    "open": [("CS2Hype, rôle d'entry fragger", "https://cs2hype.com/roles/entry-fragger"), LEET],
}
DRILLS = {
    "trade": ["En match, pendant 3 parties : avant chaque duel, dis à voix haute qui peut te trader. Si personne, recule.",
              "Deathmatch par équipe (Team DM), 10 min : reste toujours à portée de vue d'un coéquipier."],
    "nades": ["Règle des 40 s : à 1:15 au chrono en attaque, toutes tes grenades doivent être parties.",
              "Mode entraînement, 10 min par carte : apprends 1 smoke, 2 flashs et 1 molotov pour ta position favorite."],
    "flash": ["Mode entraînement (sv_cheats 1; sv_infinite_ammo 1) : 20 popflashs sur tes 2 angles les plus joués, la flash doit exploser au-dessus du mur."],
    "flashmates": ["Annonce chaque flash (« flash B ») et lance-la au-dessus ou derrière le mur, jamais devant un coéquipier."],
    "pistol": ["Aim Botz, 5 min au Glock ou à l'USP : strafe A-D, arrêt, un seul tir par cible.",
               "Deathmatch pistolets uniquement, 5 min : aucun tir en mouvement."],
    "spray": ["Recoil Master, 5 min : les 10 premières balles de l'AK et de la M4, sur un mur puis sur un bot.",
              "Deathmatch, 10 min : rafales de 3 à 5 balles, décalage entre chaque."],
    "hold": ["Choisis 2 angles tenus par site sur tes cartes, et joue-les en attendant l'info au lieu d'aller la chercher.",
             "Jiggle-peek (A-D rapide) pour prendre l'info sans t'engager."],
    "range": ["Privilégie les positions en fond de site ou en angle long. Évite les coins où l'ennemi arrive à 3 m."],
    "hp": ["Sous 50 PV : annonce tes PV, recule d'un angle et laisse le duel suivant à un coéquipier en pleine forme."],
    "eco": ["Pendant le temps d'achat : Tab, regarde l'argent des 4 autres, et annonce « full », « force » ou « eco » avant d'acheter.",
            "Drop une arme dès que tu as plus de 5 000 $ et qu'un coéquipier a moins de 2 500 $."],
    "xhair": ["Yprac Prefire (workshop), 10 min sur ta carte : viseur à hauteur de tête sur chaque angle.",
              "En match : quand tu te déplaces, ton viseur suit le bord du mur, à hauteur de tête."],
    "early": ["Les 20 premières secondes : prends l'info et garde ta position. Pas de duel sans flash ni trade."],
    "lastalive": ["Dès que 2 coéquipiers sont morts, rapproche-toi du survivant le plus proche au lieu de rester sur ton spot.",
                  "Seul contre 3 ou plus sans objectif urgent : sauve ton arme plutôt que de chercher le clutch."],
    "open": ["Laisse l'ouverture à ton entry, ou prends-la avec une flash d'un coéquipier."],
}
# rule id -> metrics shown as benchmarks (first = main)
RULE_METRICS = {"trade": ["traded_pct", "last_alive_pct"], "nades": ["nades_unused_24", "flash_eff"],
                "hold": ["peek_win", "hold_win"], "flash": ["flash_duels_pct"], "hp": ["lowhp_win"],
                "range": ["close_win", "far_win"], "pistol": ["pistol_moving"], "spray": ["b9_hit", "b1_hit"],
                "eco": [], "early": ["early_death_pct"], "xhair": ["xhair"], "open": ["open_win"], "flashmates": ["flash_mates_rate"], "lastalive": ["last_alive_pct"]}
EXTRA = {  # rules only triggered by the reference population (bottom third)
    "xhair": ("Ton viseur est loin de la tête quand le duel commence", "Viseur à hauteur de tête",
              ["Écart médian entre ton viseur et la tête adverse, 125 ms avant ton premier tir."]),
    "open": ("Tu perds tes premiers duels", "Pas d'ouverture sans flash", ["Premiers kills du round, gagnés ou perdus."]),
    "flashmates": ("Tes flashs aveuglent ton équipe", "Flashe pour ton équipe, pas sur elle", ["Coéquipiers aveuglés plus d'une seconde par flash lancée."]),
    "early": ("Trop de morts en début de round", "Pas de duel gratuit avant 20 s", ["Part de tes morts avant 20 s de round."]),
    "lastalive": ("Tu finis souvent seul face à plusieurs ennemis", "Regroupe-toi quand l'équipe tombe",
                  ["Part de tes morts où tu étais le dernier en vie de ton équipe."]),
}


def fmt(v, unit):
    if v is None:
        return "—"
    s = f"{v:.1f}" if abs(v) < 10 and unit != "%" else f"{v:.0f}"
    return s.replace(".", ",") + (" %" if unit == "%" else unit)


def enrich(rules, bench):
    """Attach benchmarks / drills / sources; add population-only rules; re-score by percentile."""
    have = {r["id"] for r in rules}
    M = (bench or {}).get("metrics", {})
    for rid, (title, short, why) in EXTRA.items():
        m = RULE_METRICS[rid][0]
        b = M.get(m)
        if rid not in have and b and b["you"] is not None and b["percentile"] is not None and b["percentile"] <= 30:
            rules.append({"id": rid, "score": 12, "title": title, "short": short, "why": list(why), "do": []})
    for r in rules:
        rid = r["id"]
        r["sources"] = [{"label": a, "url": u} for a, u in SOURCES.get(rid, [])]
        r["drills"] = DRILLS.get(rid, [])
        bl = []
        for m in RULE_METRICS.get(rid, []):
            b = M.get(m)
            if not b or b["you"] is None:
                continue
            bl.append({"metric": m, "label": b["label"], "you": b["you"], "percentile": b["percentile"], "median": b["median"],
                       "good": b["good"], "same": b["same_rank_median"], "higher": b["higher_rank_median"], "unit": b["unit"],
                       "higher_better": b["higher_better"], "n": b["n"]})
        r["bench"] = bl
        if bl and bl[0]["percentile"] is not None:
            p = bl[0]["percentile"]
            r["score"] = round(r["score"] * 0.6 + (60 - p) * 0.5, 1)
            b0 = bl[0]
            target = b0["higher"] if b0["higher"] is not None else b0["good"]
            r["target"] = f"Objectif : {fmt(target, b0['unit'])} ({'niveau des joueurs mieux classés' if b0['higher'] is not None else 'quart supérieur de la base'})"
            r["standing"] = f"Toi {fmt(b0['you'], b0['unit'])} · médiane {fmt(b0['median'], b0['unit'])} · tu fais mieux que {p:.0f} % des joueurs"
    return sorted(rules, key=lambda r: -r["score"])


def strengths_from_bench(bench, limit=4):
    out = []
    for m, b in (bench or {}).get("metrics", {}).items():
        if b["you"] is not None and b["percentile"] is not None and b["percentile"] >= 75:
            out.append((b["percentile"], f"{b['label'][0].upper() + b['label'][1:]} : {fmt(b['you'], b['unit'])} (mieux que {b['percentile']:.0f} % des joueurs)"))
    return [t for _, t in sorted(out, reverse=True)[:limit]]
