"""Sourced coaching knowledge: routines (before / during / after the round and the game, outside the game),
mid-round playbook (if this, then that), party size, level, role, weapons and the current state of the game.

Every entry cites where it comes from (guides, pro videos, studies, patch notes). The coach engine (plan.py)
picks what applies to a player from his own numbers. Researched in September 2026.
"""
UPDATED = "2026-09-30"

SRC = {
    # guides
    "boosteria_ct": ("Boosteria, tenir un site en CT : setups et rotations (2026)", "https://boosteria.org/guides/hold-sites-ct-cs2-setups-rotations-2026"),
    "cs2hype_rot": ("CS2Hype, rotations : quand et comment tourner", "https://cs2hype.com/guides/dynamic-map-rotations-when-and-how-to-rotate-in-cs2"),
    "boosteria_retake": ("Boosteria, guide des retakes (2026)", "https://boosteria.org/guides/cs2-retake-guide-2026-site-retake-strategy-teamplay"),
    "refrag_retake": ("Refrag, 5 conseils pour les retakes", "https://refrag.gg/blog/reclaim-control-5-tips-to-improve-your-retakes-in-cs2/"),
    "scope_adv": ("scope.gg, convertir un avantage numérique", "https://blog.scope.gg/realizing-the-advantage-en/"),
    "t_fund": ("Boosteria, fondamentaux T (2026)", "https://boosteria.org/guides/cs2-t-side-fundamentals-guide-2026-takes-fakes-executes"),
    "positioning": ("Boosteria, positionnement : angles et tirs croisés", "https://boosteria.org/guides/cs2-positioning-fundamentals-2026-angles-crossfires"),
    "refrag_roles": ("Refrag, les rôles en CS2", "https://refrag.gg/blog/cs2-team-roles-explained/"),
    "lurk_blast": ("BLAST.tv, jouer lurker", "https://blast.tv/article/cs2-lurker-guide"),
    "lurk_bo3": ("bo3.gg, guide du lurker", "https://bo3.gg/articles/lurker-position-guide-in-cs2"),
    "csgonews_solo": ("CSGO-News, gagner en solo queue Premier", "https://csgo-news.com/en/guides/how-to-play-solo-queue-in-premier-and-win/"),
    "steam_solo": ("Guide Steam, sortir de l'enfer de la solo queue", "https://steamcommunity.com/sharedfiles/filedetails/?id=3664156230"),
    "rank_tiers": ("CS2 Central, monter en Premier (2026)", "https://cs2central.gg/blog/cs2-premier-rank-up-guide/"),
    "sw_economy": ("Switchblade Gaming, économie 2026 : seuils et bonus de défaite", "https://www.switchbladegaming.com/cs2/economy-guide/"),
    "h2k_economy": ("Hard2Kill, guide de l'économie", "https://hard2kill.gg/guides/cs2-economy-guide"),
    "demo_review": ("CS2Hype, analyser ses démos pas à pas", "https://cs2hype.com/guides/how-to-analyze-and-learn-from-your-cs2-demos-a-step-by-step-guide"),
    "boosteria_demo": ("Boosteria, ce que les pros regardent en démo", "https://boosteria.org/guides/cs2-demo-review-guide-pros-look-improve-fast"),
    "workshop_maps": ("CS2.eu, cartes workshop d'échauffement (2026)", "https://cs2.eu/news/cs2-warm-up-maps-the-best-workshop-maps-for-practice-in-2026"),
    "sound": ("bo3.gg, le son dans CS2", "https://bo3.gg/articles/sound-mechanics-in-cs2-footsteps-utility-and-audio-cues"),
    "boosteria_audio": ("Boosteria, guide audio (2026)", "https://boosteria.org/guides/cs2-audio-awareness-guide-2026-sound-cues-win-rounds"),
    "smg": ("CS.MONEY, jouer la MP9", "https://cs.money/blog/games/weapons-guide-mp9/"),
    "leetify_glossary": ("Leetify, glossaire des statistiques", "https://leetify.com/blog/leetify-stats-glossary/"),
    # patch notes and state of the game
    "rush_hour": ("Dust2.us, mise à jour du 22 septembre 2026 (Rush Hour)", "https://www.dust2.us/news/78121/breaking-cs2-september-22nd-update-brings-silent-reloads-new-gamemode-changes-to-premier-in-rush-hour-patch"),
    "reload_update": ("CS2 Central, rechargements par chargeur (mars 2026)", "https://cs2central.gg/blog/cs2-reload-update-explained/"),
    "april_update": ("Swap.gg, mise à jour d'avril 2026", "https://swap.gg/blog/cs2-april-2026-update"),
    "map_pool": ("ProSettings, pool de cartes CS2 (juillet 2026)", "https://prosettings.net/blog/cs2-maps/"),
    "party4": ("Esports Kingdom, groupes de 4 en Premier", "https://esportskingdom.gg/counter-strike/cs2s-latest-update-allows-groups-of-four-to-play-premier-mode/"),
    # studies
    "sleep_cs": ("Étude : sommeil de 27 joueurs de Counter-Strike et performance (Frontiers, 2021)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8794592/"),
    "caffeine": ("Étude : caféine et tir en FPS, 24 joueurs (Frontiers, 2024)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11270538/"),
    "mood_games": ("Étude : humeur et fatigue sur 3 games consécutives (PMC, 2023)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10728599/"),
    "streaks": ("Étude : séries de victoires et de défaites sur 597 680 matchs (CHI PLAY, 2024)", "https://dl.acm.org/doi/abs/10.1145/3665463.3678787"),
    "breathing": ("Étude : 5 min de soupir cyclique par jour (Cell Reports Medicine, 2023)", "https://www.cell.com/cell-reports-medecine/fulltext/S2666-3791(22)00474-8"),
    "attention": ("Revue : rythmes circadiens de l'attention (PMC, 2019)", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6430172/"),
    "exercise": ("Étude : 8 semaines de sport chez des joueurs esport (Frontiers, 2024)", "https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2024.1504205/full"),
    "bef_health": ("British Esports, rester en forme", "https://britishesports.org/the-hub/health-and-wellbeing/staying-healthy-in-esports/"),
    "aoa_eyes": ("American Optometric Association, jeux vidéo et fatigue visuelle", "https://www.aoa.org/healthy-eyes/caring-for-your-eyes/gaming-and-digital-eye-strain"),
    "rating": ("flashed.gg, rating HLTV 2.0 reconstitué", "https://flashed.gg/posts/reverse-engineering-hltv-rating/"),
    # videos
    "yt_ropz_lurk": ("Vidéo : Be like ropz, lurker comme un pro", "https://www.youtube.com/watch?v=OslKO06LpwI"),
    "yt_hunter_lurk": ("Vidéo : How To Lurk In CS2 ft. G2 huNter", "https://www.youtube.com/watch?v=SrnhpgR0UtI"),
    "yt_tyloo_lurk": ("Vidéo : lurker sur Inferno (TYLOO Academy)", "https://www.youtube.com/watch?v=tRxzBc-JySg"),
    "yt_ct_setups": ("Vidéo : Best CT Setups on Every Map", "https://www.youtube.com/watch?v=bCbg3hjSr80"),
    "yt_nuke_outside": ("Vidéo : Nuke Outside en CT avec dev1ce (Astralis Academy)", "https://www.youtube.com/watch?v=0Q4nVKtXmRM"),
    "yt_anubis_awp": ("Vidéo : l'AWP sur Anubis en CT", "https://www.youtube.com/watch?v=vPTHUtkDuuo"),
    "yt_anubis_ct": ("Vidéo : chaque position CT sur Anubis", "https://www.youtube.com/watch?v=_HzOy7MBagk"),
    "yt_mirage_ct": ("Vidéo : chaque position CT sur Mirage", "https://www.youtube.com/watch?v=b65hyOMbi0g"),
    "yt_cache_ct": ("Vidéo : gagner le côté CT de Cache", "https://www.youtube.com/watch?v=yZBtbDSBQkM"),
    "yt_nuke_high": ("Vidéo : How to Play Nuke at a High Level", "https://www.youtube.com/watch?v=TqaOW5as6q4"),
    "yt_solo": ("Vidéo : How to Solo Queue Correctly in CS2", "https://www.youtube.com/watch?v=mbnEq-QStug"),
    "yt_solo_concepts": ("Vidéo : 4 Solo Queue Concepts You Don't Know", "https://www.youtube.com/watch?v=D8mU4mipv1A"),
    "yt_no5stack": ("Vidéo : You Don't Need a 5 Stack to Rank Up", "https://www.youtube.com/watch?v=c4HqtNTmWkc"),
    "yt_warmup_ropz": ("Vidéo : l'échauffement de ropz", "https://www.youtube.com/watch?v=TmEwsVodlhc"),
    "yt_warmup_pros": ("Vidéo : How the PROS warmup (2026)", "https://www.youtube.com/watch?v=VTuokRukVoc"),
    "yt_awp": ("Vidéo : How to AWP, passif ou agressif", "https://m.youtube.com/watch?v=lannGAJbszI"),
    "yt_positioning": ("Vidéo : The GREATEST CS2 Positioning Guide (2026)", "https://www.youtube.com/watch?v=RrGFGUIzCt0"),
    "yt_workshop": ("Vidéo : BEST Workshop Maps to FIX Your Aim (2026)", "https://www.youtube.com/watch?v=8aC976zFzIM"),
    "yt_t_advantage": ("Vidéo : utiliser l'avantage numérique en T", "https://www.youtube.com/watch?v=6b1MfRjStLQ"),
}


def src(*keys):
    return [{"label": SRC[k][0], "url": SRC[k][1]} for k in keys if k in SRC]


# ---------- state of the game (September 2026) ----------
META = [
    {"date": "22 sept. 2026", "title": "Rechargement silencieux et dézoom silencieux",
     "text": "Maintenir R recharge sans bruit, mais plus lentement. Dézoomer un sniper ne fait plus de bruit.",
     "impact": "Lurker et clutch : recharge en maintenant R quand un ennemi est à portée d'oreille. AWP : tu peux décrocher d'un angle sans te trahir.",
     "src": ["rush_hour"]},
    {"date": "22 sept. 2026", "title": "Premier : nouveau choix des cartes",
     "text": "Plus de bans : l'équipe 1 choisit une carte, l'équipe 2 deux, l'équipe 1 une dernière, puis une des quatre est tirée au sort.",
     "impact": "Il faut être prêt sur 4 cartes. Choisis tes meilleures cartes, et prépare au moins une fiche CT et une fiche T pour chacune.",
     "src": ["rush_hour"]},
    {"date": "22 sept. 2026", "title": "Nouveau mode 3v3 Rush",
     "text": "Mode rapide en 3 contre 3 sur des arènes tirées au sort, avec une tour à contrôler.",
     "impact": "Bon mode d'échauffement pour les duels et le jeu à 2-3. Il ne remplace pas le travail des cartes du pool.",
     "src": ["rush_hour"]},
    {"date": "été 2026", "title": "Cache revient, Overpass sort du pool",
     "text": "Pool Active Duty et Premier : Ancient, Anubis, Cache, Dust2, Inferno, Mirage, Nuke.",
     "impact": "Si tu joues Premier, Cache devient une carte à préparer.",
     "src": ["map_pool", "yt_cache_ct"]},
    {"date": "avril 2026", "title": "M4A1-S renforcée à distance, SMG moins chers",
     "text": "La M4A1-S fait plus de dégâts à distance. MP9 à 1 150 $ et MAC-10 à 950 $.",
     "impact": "Les forces en SMG coûtent moins cher : à comparer avec tes chiffres en force-buy.",
     "src": ["april_update"]},
    {"date": "18 mars 2026", "title": "Rechargement par chargeur : les balles restantes sont perdues",
     "text": "Recharger jette le chargeur en cours. AWP : 15 balles par round (5 + 2 chargeurs). M4A4 : 150 balles, M4A1-S : 80, Galil : 175, AK : 120.",
     "impact": "Ne recharge plus par réflexe après 3 balles : recharge presque vide, à l'abri, ou ramasse une arme. À l'AWP, chaque tir compte.",
     "src": ["reload_update"]},
]

# ---------- routine by phase ----------
PHASES = [
    {"key": "hors_jeu", "title": "En dehors du jeu", "items": [
        {"id": "sleep", "title": "Horaires de sommeil réguliers",
         "text": "Chez 27 joueurs de Counter-Strike suivis 56 jours, les meilleurs dormaient plus longtemps et avaient plus de sommeil profond. L'efficacité du sommeil était basse chez presque tous (67,7 % en moyenne).",
         "do": ["Couche-toi et lève-toi à heure fixe, y compris le week-end.", "Remplis le journal d'avant-session : le coach mesure l'effet de tes nuits sur tes games."],
         "src": ["sleep_cs"], "tags": ["all"]},
        {"id": "caffeine", "title": "Caféine : petite dose, 1 h avant",
         "text": "Une étude sur 24 joueurs de FPS : 1 à 3 mg par kg, pris 60 min avant, améliorent le tir et le temps de réaction (environ 17 ms). 1 mg/kg (un expresso pour 70 kg) fait presque aussi bien que 3 mg/kg.",
         "do": ["Si tu en prends : un café environ 1 h avant la session, pas un litre de boisson énergisante.", "Aucune caféine après ta dernière session de la journée."],
         "src": ["caffeine"], "tags": ["all"]},
        {"id": "sport", "title": "Activité physique pour le bien-être",
         "text": "8 semaines de sport ont amélioré la coordination, la force de préhension et le bien-être de joueurs esport, sans gain direct sur les tests de jeu à court terme.",
         "do": ["2 à 3 séances de 40 min par semaine. Attends-en de l'énergie et du moral, pas du HS en plus."],
         "src": ["exercise", "bef_health"], "tags": ["all"]},
        {"id": "eyes", "title": "Yeux et posture",
         "text": "En jeu, on cligne beaucoup moins des yeux. Règle des 20-20-20 : toutes les 20 min, regarde à 6 m (20 pieds) pendant 20 s. Lève-toi et étire-toi au moins une fois par heure.",
         "do": ["Écran à hauteur des yeux, pieds à plat, bras relâchés.", "Un verre d'eau à chaque pause entre deux games."],
         "src": ["aoa_eyes", "bef_health"], "tags": ["all"]},
        {"id": "weekly_review", "title": "Une séance de démo par semaine",
         "text": "Regarde un match en x2 depuis ta vue, note les rounds où tu meurs en premier, puis revois-les en vitesse normale. Garde 2-3 erreurs pour la semaine.",
         "do": ["Utilise le replay 2D de l'onglet Matchs pour tes morts isolées.", "Transforme chaque erreur récurrente en expérience dans l'onglet Progresser."],
         "src": ["demo_review", "boosteria_demo"], "tags": ["all"]},
    ]},
    {"key": "avant_session", "title": "Avant la session", "items": [
        {"id": "checkin", "title": "Journal en 20 secondes",
         "text": "Heures de sommeil, énergie, humeur, échauffement. Au bout de quelques semaines, le coach te dit quels jours tu joues bien et pourquoi.",
         "do": ["Remplis le formulaire en haut de cet onglet avant ta première game."], "src": ["sleep_cs"], "tags": ["all"]},
        {"id": "warmup", "title": "Échauffement de 15 minutes",
         "text": "Les pros s'échauffent avec des cartes workshop : Aim Botz pour la précision, Aim Rush pour les réflexes, Recoil Master pour le spray, une carte de prefire pour le placement du viseur.",
         "do": ["Ton programme personnalisé est dans l'onglet Progresser.", "Finis par 5 min de Deathmatch avec l'arme de ton rôle."],
         "src": ["workshop_maps", "yt_warmup_ropz", "yt_warmup_pros", "yt_workshop"], "tags": ["all"]},
        {"id": "one_goal", "title": "Un seul objectif pour la session",
         "text": "Entre dans chaque match avec une tâche que tu peux tenir même si la game commence mal, au lieu de vouloir porter le lobby.",
         "do": ["Prends la 1re règle de « Toujours, sur toutes les cartes » et joue toute la session avec."],
         "src": ["csgonews_solo", "yt_solo_concepts"], "tags": ["all"]},
        {"id": "maps4", "title": "Prépare tes 4 cartes Premier",
         "text": "Depuis le 22 septembre, 4 cartes sont choisies puis une est tirée au sort : il faut un plan sur chacune.",
         "do": ["Choisis tes cartes où ton bilan est le meilleur (onglet Avant la game).", "Relis la fiche de la carte tirée pendant le chargement."],
         "src": ["rush_hour"], "tags": ["premier"]},
    ]},
    {"key": "avant_round", "title": "Avant chaque round (temps d'achat)", "items": [
        {"id": "buy_team", "title": "On achète ensemble",
         "text": "Full buy à partir d'environ 4 000 $ en T et 4 200 $ en CT. Bonus de défaite : 1 400, 1 900, 2 400, 2 900 puis 3 400 $. Une victoire fait redescendre le compteur d'un cran.",
         "do": ["Tab : regarde l'argent des 4 autres avant d'acheter.", "Force seulement si ton argent, moins l'achat, plus le bonus de défaite, fait au moins 4 000 $ au round suivant.", "Drop une arme dès que tu dépasses 5 000 $ et qu'un coéquipier ne peut pas acheter."],
         "src": ["sw_economy", "h2k_economy"], "tags": ["all"]},
        {"id": "one_job", "title": "Un rôle précis pour le round",
         "text": "Qui prend l'info, qui trade, qui lance quelle grenade. Une grenade = une mission (retarder, prendre le contrôle, bloquer la pose).",
         "do": ["Annonce ta position et ta 1re grenade en une phrase."],
         "src": ["boosteria_ct", "t_fund"], "tags": ["all"]},
    ]},
    {"key": "pendant_round", "title": "Pendant le round", "items": [
        {"id": "trade_spacing", "title": "Distance de trade",
         "text": "Assez près pour venger, assez loin pour ne pas mourir sur le même spray. Deux joueurs sur la même ligne donnent un double kill.",
         "do": ["Avant chaque duel : qui peut me venger en moins de 2 secondes ?", "Angles complémentaires : l'un prend le contact, l'autre punit celui qui l'a tué."],
         "src": ["positioning", "boosteria_retake"], "tags": ["all"]},
        {"id": "info_calls", "title": "Une annonce = où, combien, quel type de pression",
         "text": "« Deux B, un lurk, grenades qui arrivent, pas encore full » vaut mieux que « ils sont tous B ! » après ta mort.",
         "do": ["Annonce avant de mourir, pas après.", "Mort : donne encore l'info utile, sans commander les vivants."],
         "src": ["boosteria_ct", "csgonews_solo", "steam_solo"], "tags": ["all"]},
        {"id": "reload", "title": "Rechargement 2026",
         "text": "Recharger jette le chargeur en cours. Recharge à peu de balles, à l'abri. Ramasse l'arme d'un coéquipier mort. Près d'un ennemi, maintiens R pour recharger sans bruit.",
         "do": ["Ne recharge jamais par réflexe après un kill en plein milieu d'une zone ouverte."],
         "src": ["reload_update", "rush_hour"], "tags": ["all"]},
        {"id": "sound_disc", "title": "Discipline sonore",
         "text": "Courir s'entend à environ 1 100 unités (≈ 28 m). Marcher (Shift) est silencieux. Un saut s'entend de loin.",
         "do": ["Shift dès que tu es seul près des ennemis, en lurk comme en clutch.", "Écoute avant de bouger : le son te dit qui reste et qui part."],
         "src": ["sound", "boosteria_audio"], "tags": ["all"]},
    ]},
    {"key": "apres_round", "title": "Après chaque round", "items": [
        {"id": "why_died", "title": "5 secondes de bilan",
         "text": "Pourquoi je suis mort ? Étais-je tradable ? Si tu meurs 3 fois du même angle, ce n'est plus l'aim : change de position ou demande une flash.",
         "do": ["Une phrase dans ta tête, puis on passe au round suivant."],
         "src": ["csgonews_solo"], "tags": ["all"]},
        {"id": "breath", "title": "Respiration de reset",
         "text": "Le soupir cyclique (double inspiration, longue expiration) a mieux réduit le stress que la méditation dans une étude de 2023.",
         "do": ["Pendant le chargement du round : 2 cycles, expiration longue.", "Après une grosse erreur : une respiration, puis une info utile à ton équipe."],
         "src": ["breathing"], "tags": ["all"]},
    ]},
    {"key": "apres_game", "title": "Après la game", "items": [
        {"id": "break_after_loss", "title": "Pause après une défaite",
         "text": "Sur 597 680 matchs de joueurs du top 3 % coréen (League of Legends), les séries de défaites s'accompagnaient d'une baisse de performance, et les joueurs qui faisaient une pause plus longue après une défaite s'en sortaient mieux. La fatigue augmente après chaque game, victoire ou défaite.",
         "do": ["10 à 15 min de pause après une défaite, 30 min après deux.", "Tes propres chiffres (onglet Routine, contexte) disent à partir de quelle game tu baisses."],
         "src": ["streaks", "mood_games"], "tags": ["all"]},
        {"id": "one_lesson", "title": "Une leçon, pas dix",
         "text": "Après une défaite, trouve la raison principale au lieu de tout changer. Après une victoire, note ce qui a marché.",
         "do": ["Écris-la dans le journal. Si elle revient 3 fois : lance une expérience."],
         "src": ["csgonews_solo"], "tags": ["all"]},
    ]},
]

# ---------- mid-round playbook ----------
PLAYBOOK = [
    # CT
    {"side": "CT", "if": "Un seul bruit, une seule smoke ou une molotov sur l'autre site", "then": "Ne tourne pas. Penche-toi vers le connecteur (« je penche A ») et attends une vraie info.",
     "why": "Les T font des fakes avec un seul utilitaire pour faire tourner.", "src": ["boosteria_ct", "cs2hype_rot"], "tags": ["rotation"]},
    {"side": "CT", "if": "Bombe vue, 3 joueurs annoncés, ou 2 flashs + molotov + bruits de rifles", "then": "Rotation complète tout de suite, par la route qui te garde couvert, en annonçant « je tourne ».",
     "why": "Ce sont les signaux d'une vraie exécution.", "src": ["boosteria_ct"], "tags": ["rotation"]},
    {"side": "CT", "if": "Tu tournes et tes coéquipiers sont déjà morts sur le site", "then": "Ne rentre pas seul : arrête-toi à l'entrée, attends les autres et préparez un retake groupé.",
     "why": "La pire erreur en rotation : arriver seul et trop tard.", "src": ["boosteria_ct", "boosteria_retake"], "tags": ["rotation", "retake"]},
    {"side": "CT", "if": "Tu es l'ancre et ça arrive sur toi", "then": "Priorité : survivre 10 secondes et annoncer combien ils sont et quels utilitaires ils lancent. Recule d'un angle plutôt que de mourir en premier.",
     "why": "L'ancre gagne le round en tenant jusqu'aux rotations.", "src": ["refrag_roles", "boosteria_ct"], "tags": ["anchor"]},
    {"side": "CT", "if": "Pendant une rotation, un lurk est possible derrière toi", "then": "Un joueur reste sur la route de flanc (anti-lurk). Vérifie avant de quitter ton site.",
     "why": "Les rotations sans anti-lurk se font couper par derrière.", "src": ["boosteria_ct"], "tags": ["rotation"]},
    {"side": "CT", "if": "Bombe posée, 3 CT ou plus, avec utilitaires", "then": "Retake : deux entrées, flash synchronisée, un joueur tape la bombe tout de suite pour forcer les T à se montrer.",
     "why": "Un retake groupé bat un retake au goutte-à-goutte.", "src": ["boosteria_retake", "refrag_retake"], "tags": ["retake"]},
    {"side": "CT", "if": "Bombe posée, seul contre 3 ou plus, moins de 20 s ou pas de kit", "then": "Sauve ton arme.",
     "why": "En MR12, garder ton arme pour le round suivant rapporte plus qu'un retake perdu d'avance.", "src": ["refrag_retake", "boosteria_retake"], "tags": ["save"]},
    {"side": "CT", "if": "Ton équipe est à 4 contre 5", "then": "Joue passif : un kill puis recule, regroupez-vous sur un site ou préparez le retake. Pas de peek héroïque.",
     "why": "Perdre le site ET un joueur de plus est le pire scénario.", "src": ["scope_adv"], "tags": ["advantage"]},
    {"side": "CT", "if": "Ton équipe est à 5 contre 4", "then": "Plus de duel seul : tirs croisés, laisse les T venir à toi, le chrono joue pour vous.",
     "why": "En matchmaking, seuls 60 % des 5v4 sont convertis, contre plus de 75 % chez les pros.", "src": ["scope_adv"], "tags": ["advantage"]},
    # T
    {"side": "T", "if": "Vous gagnez le 1er duel (5 contre 4)", "then": "Regroupez-vous et frappez le site affaibli en trade propre. Pas besoin d'un fake compliqué.",
     "why": "Un avantage se convertit par la structure, pas par la vitesse.", "src": ["t_fund", "yt_t_advantage", "scope_adv"], "tags": ["advantage"]},
    {"side": "T", "if": "Vous perdez le 1er duel (4 contre 5)", "then": "Ralentissez : prenez le contrôle de la carte, cherchez un pick à deux, frappez tard avec les utilitaires.",
     "why": "Rusher à 4 contre 5 sans info donne le round.", "src": ["t_fund", "scope_adv"], "tags": ["advantage"]},
    {"side": "T", "if": "Tu lurkes pendant que l'équipe exécute", "then": "Marche (Shift), écoute qui tourne, et frappe au moment où les CT quittent ton côté : coupe la rotation.",
     "why": "Le lurk marche quand il tombe au moment où les CT s'engagent ailleurs.", "src": ["lurk_blast", "lurk_bo3", "yt_ropz_lurk", "yt_hunter_lurk"], "tags": ["lurk"]},
    {"side": "T", "if": "Tu lurkes et rien ne se passe à 0:45", "then": "Rejoins l'exécution ou pars sur le site vide : un lurker qui attend trop joue un 1 contre 4 à la fin.",
     "why": "Un lurk sans impact ressemble à un bait ou à une sauvegarde.", "src": ["refrag_roles", "yt_tyloo_lurk"], "tags": ["lurk"]},
    {"side": "T", "if": "Bombe posée", "then": "Tirs croisés, joue le temps et les utilitaires (molotov ou smoke sur la bombe). Ne cherche pas le duel : fais-les venir.",
     "why": "Le temps est votre arme après la pose.", "src": ["boosteria_retake"], "tags": ["postplant"]},
    {"side": "T", "if": "Moins de 20 s, pas de pose, seul contre plusieurs", "then": "Sauve ton arme.",
     "why": "Un rifle gardé vaut plus qu'un kill de sortie.", "src": ["h2k_economy"], "tags": ["save"]},
    # both
    {"side": "tous", "if": "Tu viens de faire un kill en clutch", "then": "Ne re-peek pas le même angle tout de suite : repositionne-toi, écoute, isole le duel suivant.",
     "why": "Le kill te révèle : l'adversaire attend ce re-peek.", "src": ["csgonews_solo"], "tags": ["clutch"]},
    {"side": "tous", "if": "Tu es blessé (moins de 50 PV)", "then": "Annonce tes PV, recule d'un angle et laisse le duel suivant à un coéquipier en pleine forme.",
     "why": "Un duel blessé se perd plus souvent qu'il ne se gagne.", "src": ["positioning"], "tags": ["duel"]},
    {"side": "tous", "if": "Tu as l'AWP et tu viens de tirer", "then": "Change d'angle : le dézoom est désormais silencieux. Garde tes 15 balles pour les vrais duels.",
     "why": "Un AWPer qui re-peek le même angle se fait punir.", "src": ["yt_awp", "rush_hour", "reload_update"], "tags": ["awp"]},
    {"side": "tous", "if": "Tu joues une SMG ou un fusil à pompe", "then": "Prends des angles courts où l'ennemi apparaît à moins de 15 m. Loin, ton arme perd tout son intérêt.",
     "why": "Les dégâts des SMG chutent avec la distance, mais un kill rapporte 600 $.", "src": ["smg"], "tags": ["smg"]},
]

# ---------- party size ----------
PARTY = {
    "solo": {"title": "En solo", "items": [
        "Sois le joueur qui ne donne jamais un round gratuit : info, trade, sauvegarde, grenades au bon moment.",
        "Prends un rôle qui n'a pas besoin d'être coordonné : ancre en CT, second joueur en T, et donne l'info.",
        "Des annonces courtes et factuelles, jamais d'émotion. Après ta mort, l'info utile seulement.",
        "Attends-toi à perdre environ 1 game sur 2 : même les très bons joueurs plafonnent vers 55 % en solo.",
    ], "src": ["csgonews_solo", "steam_solo", "yt_solo", "yt_no5stack"]},
    "duo": {"title": "En duo", "items": [
        "Jouez en paire de trade : l'un prend le contact, l'autre punit. Toujours sur des angles complémentaires.",
        "Grenades synchronisées : ta flash pour son entrée, sa smoke pour ta rotation.",
        "En Premier, mettez-vous d'accord sur vos cartes avant la phase de choix.",
        "Regardez ensemble un round perdu par session.",
    ], "src": ["positioning", "rush_hour"]},
    "trio": {"title": "À trois", "items": [
        "Vous formez le cœur de l'exécution : entry, second, support. Donnez un rôle simple aux deux autres (ancre, lurk).",
        "Parlez en premier : les deux joueurs seuls suivent qui donne un plan clair.",
    ], "src": ["refrag_roles", "steam_solo"]},
    "quatuor": {"title": "À quatre", "items": [
        "Le 5e joueur est immunisé contre le vote-kick : intégrez-le au lieu de l'ignorer.",
        "Donnez-lui une mission claire dès le 1er round (ancre B, lurk…).",
    ], "src": ["party4"]},
    "five": {"title": "À cinq", "items": [
        "Des rôles fixes : IGL, entry, support, lurker, AWPer. Un default par carte et une exécution par site.",
        "En Premier à 5, vous jouez surtout contre d'autres groupes : les matchs sont plus structurés.",
        "Revoyez vos démos d'équipe : l'IGL cherche les erreurs de timing et d'espacement.",
    ], "src": ["refrag_roles", "steam_solo"]},
}

# ---------- level ----------
LEVELS = [
    {"key": "debut", "max": 10000, "name": "Moins de 10 000", "comp": (1, 10), "focus": [
        "Placement du viseur à hauteur de tête sur chaque angle.", "Contre-strafe : arrêt net avant de tirer.",
        "Une seule carte, apprise à fond.", "Économie : acheter avec l'équipe."]},
    {"key": "inter", "max": 15000, "name": "10 000 à 15 000", "comp": (11, 13), "focus": [
        "Viseur et trades avant tout.", "Contrôle de la carte et utilitaires de base (1 smoke, 2 flashs par site).",
        "Jouer à 2 plutôt que seul."]},
    {"key": "confirme", "max": 20000, "name": "15 000 à 20 000", "comp": (14, 16), "focus": [
        "Maîtriser 2-3 cartes : callouts, timings et lineups.", "Rounds pistolets et rounds de conversion : pas d'achat impulsif.",
        "Les décisions en mi-round : rotations, retakes, avantage numérique."]},
    {"key": "avance", "max": 25000, "name": "20 000 à 25 000", "comp": (17, 17), "focus": [
        "Les 3 leviers qui débloquent : utilitaires, économie, espacement (spacing).", "Une carte signature maîtrisée à fond."]},
    {"key": "elite", "max": 99999, "name": "25 000 et plus", "comp": (18, 18), "focus": [
        "Arrêter après 2-3 défaites d'affilée : l'habitude la plus rentable pour le classement.", "Annonces et coordination : les joueurs qui communiquent gagnent plus."]},
]
LEVEL_SRC = ["rank_tiers"]

# ---------- roles ----------
ROLE_TIPS = {
    "lurker": {"items": [
        "Ton job : tenir l'espace que l'équipe a laissé, couper la rotation, être le dernier vivant avec l'info.",
        "Discipline sonore : Shift quand tu es seul, recharge silencieuse près des ennemis.",
        "Frappe au moment où les CT tournent, pas avant. Rien à 0:45 : rejoins ou prends le site vide.",
        "Évite de mourir seul avant l'exécution : un lurk mort tôt, c'est un 4 contre 5 gratuit."],
        "src": ["lurk_blast", "lurk_bo3", "refrag_roles", "yt_ropz_lurk", "yt_hunter_lurk", "yt_tyloo_lurk"]},
    "entry": {"items": [
        "Ton objectif : prendre de l'espace sur le site, pas forcément des kills.", "Entre derrière une flash, avec un second à distance de trade.",
        "Après ta mort : l'info précise pour le second."], "src": ["refrag_roles", "csgonews_solo"]},
    "trader": {"items": [
        "Reste à distance de trade de ton entry, jamais sur la même ligne.", "Punis immédiatement celui qui vient de tuer ton coéquipier."],
        "src": ["refrag_roles", "positioning"]},
    "support": {"items": [
        "Tu lances la majorité des grenades : connais les smokes de chaque exécution.", "Flashe pour les autres, jamais sur eux.",
        "Deuxième dans l'engagement : trade pour cimenter le contrôle."], "src": ["refrag_roles"]},
    "anchor": {"items": [
        "Survis 10 secondes : c'est ce qui fait gagner les rounds.", "Chaque angle, timing et cachette de ton site doit être un réflexe.",
        "Accepte de lâcher le site pour préparer le retake."], "src": ["refrag_roles", "boosteria_ct"]},
    "closer": {"items": [
        "Fin de round : isole les duels, vérifie le temps et la bombe, marche.", "Ne re-peek pas après un kill : repositionne-toi.",
        "Sauve quand le round est perdu : ton arme vaut plus qu'un kill de sortie."], "src": ["csgonews_solo", "h2k_economy"]},
    "awper": {"items": [
        "Passif ou agressif selon le round, mais jamais deux fois le même angle.", "15 balles par round depuis mars 2026 : pas de tir de spam.",
        "Dézoom silencieux depuis le 22 septembre : décroche sans te trahir."], "src": ["yt_awp", "reload_update", "rush_hour", "yt_anubis_awp"]},
}

# ---------- map video guides ----------
MAP_VIDEOS = {
    "de_anubis": ["yt_anubis_ct", "yt_anubis_awp"],
    "de_mirage": ["yt_mirage_ct"],
    "de_cache": ["yt_cache_ct"],
    "de_nuke": ["yt_nuke_outside", "yt_nuke_high"],
    "de_inferno": ["yt_tyloo_lurk"],
}

# ---------- training (workshop maps and drills) by weakness ----------
DRILLS = {
    "xhair": {"map": "Carte de prefire (workshop) de la carte du jour", "min": 5, "text": "Viseur à hauteur de tête sur chaque angle, sans tirer au sol.", "src": ["workshop_maps"]},
    "reaction": {"map": "Aim Rush", "min": 5, "text": "Cibles réactives : le plus proche du vrai duel pour le temps de réaction.", "src": ["workshop_maps", "yt_workshop"]},
    "pistol": {"map": "Aim Botz (pistolet)", "min": 5, "text": "A-D, arrêt net, un tir : jamais en mouvement.", "src": ["workshop_maps"]},
    "spray": {"map": "Recoil Master", "min": 5, "text": "Les 10 premières balles de l'AK et de la M4, puis rafales de 3-5.", "src": ["workshop_maps"]},
    "precision": {"map": "Aim Botz", "min": 5, "text": "Bots immobiles puis en strafe : précision du 1er tir.", "src": ["workshop_maps"]},
    "dm": {"map": "Deathmatch", "min": 5, "text": "Avec l'arme de ton rôle, en visant uniquement la tête.", "src": ["csgonews_solo"]},
    "nades": {"map": "Mode entraînement (sv_cheats 1)", "min": 5, "text": "Les stuffs clés de ta position favorite sur la carte du jour (onglet Avant la game).", "src": ["csgonews_solo"]},
}
