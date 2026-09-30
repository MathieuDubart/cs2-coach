# Coach CS2

Coach personnel pour Counter-Strike 2 : il récupère automatiquement tes démos de matchmaking (sans téléchargement manuel), les analyse en profondeur et génère une application locale avec des conseils précis, sourcés et directement applicables.

## Deux usages principaux

- **En partie** (2e écran) : la fiche de la carte jouée, qui suit ta game toute seule grâce au Game State Integration de CS2 (carte, camp, round, argent). Tes forces et tes positions fortes, ce qu'il faut éviter, tes réflexes, tes rotations, tes stuffs clés, et le bon conseil au bon moment (achat pendant le freeze time, bombe posée, fin de round). Bouton « Mode 2e écran » pour un affichage plein écran.
- **Bilan** (à froid, après la session ou le lendemain) : ce qui change par rapport à tes matchs d'avant, de combien, les pistes d'explication (horaires, longueur de session, cartes, groupe, expériences lancées), tes axes du moment, ce que tu testes et ce que tu pourrais tester. L'analyse complète (matchs, cartes, mi-round, progression, routine) est accessible depuis le Bilan.
- Aussi : **Équipe** (plan de jeu à plusieurs), **Explorer** (n'importe quel joueur, pros), **⚙ Réglages** (connexion Steam, détection de la partie). À la première ouverture, l'accueil propose d'analyser son propre profil.

La détection de la partie s'active dans les Réglages : l'app écrit `gamestate_integration_coachcs2.cfg` dans le dossier `cfg` de CS2 (fonction officielle de Valve, utilisée par les HUD et claviers RGB ; en partie, CS2 n'envoie que tes propres infos). Relancer CS2 après l'activation.

## Ce que ça analyse

- **Économie** : achats, force-buys, sauvegardes, argent gaspillé.
- **Utilitaires** : grenades lancées, dégâts de HE/molotov, flashs efficaces, lineups utilisés sur tes positions.
- **Positionnement** : zones fortes/faibles par carte (callouts), duels gagnés/perdus par zone, positions à exploiter ou à éviter.
- **Déplacements et tir** : temps de réaction, pré-visée, précision, contre-strafe, trades, repeeks.
- **Archétype** : Entry, Lurker, AWPer, Support, Closer… selon tes armes, déplacements, notions et réactions, avec des **pros de référence** qui jouent aux mêmes endroits ou ont le même style.
- **Fiche d'avant-match par carte** + résumé global, replays 2D des rounds clés.
- **Mi-round** : rotations (délai de départ, trajet, route, morts en route), tenue de site, lurk, post-plant, retakes, avantage numérique rendu, sauvegardes, bruit à portée d'ennemi, comparés à la base et aux pros ; routes de rotation les plus sûres et positions selon l'arme, par carte ; réflexes « si… alors… ».
- **Routine** : avant, pendant et après le round et la game, hors du jeu (sommeil, caféine, pauses), selon le groupe (solo, duo, trio, quatuor, five-stack), avec les changements récents du jeu. Habitudes mesurées : horaires, rang dans la session, séries de défaites, partenaires, et journal d'avant-session (sommeil, énergie, échauffement).
- **Progresser** : priorités selon le niveau et l'expérience, conseils du rôle, échauffement ciblé, stats par arme, suivi des indicateurs match par match, et **expériences** (une arme, une position, une habitude…) évaluées automatiquement sur les matchs suivants.
- **Équipe** : toi + 1 à 4 coéquipiers analysés. Le coach croise leurs données (rôles, zones, stuffs connues, armes, mi-round, matchs joués ensemble) avec la base et les pros : rôles T, setup CT par carte (qui joue où, sur le radar), exécutions A et B (qui lance quelle grenade, avec la commande `setpos`), rotations, IGL proposé, cartes à choisir en Premier, vocabulaire et calls, économie (AWP, ordre de drop, force-buy de chacun), synergies (trades entre vous), objectifs collectifs et travail individuel au service de l'équipe.
- Chaque conseil cite ses sources : guides, vidéos de pros, études scientifiques, notes de patch (voir `knowledge.py`).
- Comparaison à une population de référence (joueurs aléatoires + démos pro HLTV).

N'importe quel joueur peut être analysé à la volée depuis la barre de recherche (lien Steam, SteamID64, URL personnalisée ou code de partage).

## Prérequis

- Windows, Python 3.11+
- Steam lancé et connecté, **CS2 fermé** (pour la récupération de la liste des matchs via le Game Coordinator)
- Optionnel : [7-Zip](https://www.7-zip.org/) (démos pro HLTV) et [Git for Windows](https://gitforwindows.org/) (son `curl` est utilisé pour csstats.gg)

```bash
pip install -r requirements.txt
```

`boiler-writter` et les radars des cartes sont téléchargés automatiquement au premier lancement.

## Utilisation

| Commande | Rôle |
|---|---|
| `Coach CS2.bat` | Lance l'application locale (http://localhost:8765) |
| `python cs2coach.py` | Récupère et analyse tes derniers matchs (compte Steam connecté) |
| `python cs2coach.py --steamid <id>` | Analyse un autre joueur |
| `python cs2coach.py --sharecode CSGO-...` | Analyse un match précis |
| `python cs2coach.py --authcode XXXX-XXXXX-XXXX --knowncode CSGO-...` | Tout l'historique (nécessite `steam_api_key` dans `out/settings.json`) |
| `python crawl.py` / `python profile_all.py` | Étoffe la population de référence (joueurs croisés en match) |
| `python pro.py --teams` | Télécharge et analyse des démos pro (HLTV) |
| `python deepdive.py` | Analyse approfondie : engagements, audit des grenades, zones vs pros |
| `python rounds.py` puis `python midround.py` | Contexte des rounds et analyse mi-round de toutes les démos (lancés automatiquement par l'app) |
| `python profile_all.py --plans` | Recalcule le plan de progression de tous les profils |
| `autostart.bat` | Lancement automatique au démarrage de Windows |

Le port du serveur se change avec la variable d'environnement `COACH_PORT`.

## Connexion Steam (facultative, onglet « Compte Steam »)

- **Se connecter avec Steam** : la page officielle de Steam confirme ton compte (OpenID), l'app ne voit jamais ton mot de passe.
- **Temps de jeu** : lu dans les fichiers du client Steam de ce PC, sans connexion.
- **Historique complet et automatique** : avec une clé d'API Steam ([steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)) et le code d'authentification de ton historique ([page d'aide Steam pour CS2](https://help.steampowered.com/fr/wizard/HelpWithGameIssue/?appid=730&issueid=128)), chaque nouveau match est retrouvé, même des semaines plus tard, puis analysé. L'app vérifie au lancement puis toutes les 30 minutes. Les matchs sans démo comptent quand même dans tes habitudes (date, score, K/A/D, coéquipiers), et tes amis Steam servent à repérer ton groupe.
- Clé et code restent dans `out/settings.json` (non versionné) et ne partent que vers l'API officielle de Steam. « Tout déconnecter » les retire.

## Limites

- Valve ne fournit que les **8 derniers matchs**, et les démos expirent au bout d'environ **un mois**.
- Un joueur sans profil Leetify public ni démo partagée n'obtient qu'un profil allégé (rangs Steam/csstats).
- FACEIT n'est pas pris en charge.

## Données et confidentialité

Tout reste en local dans `cache/` (démos) et `out/` (analyses, site généré, `settings.json` qui peut contenir une clé API Steam et un code d'authentification). Ces dossiers ne sont **pas versionnés**.

## Crédits

- [demoparser2](https://github.com/LaihoE/demoparser) — parsing des démos
- [boiler-writter](https://github.com/akiver/boiler-writter) (MIT) — liste des matchs via le Game Coordinator
- Radars et métadonnées de cartes issus de [CS Demo Manager](https://github.com/akiver/cs-demo-manager)
- [Leetify](https://leetify.com), [csstats.gg](https://csstats.gg), [HLTV](https://www.hltv.org) — statistiques publiques et démos pro
