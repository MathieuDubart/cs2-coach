"""The website of Wily for the players: https://wily.valentingassend.com (05/10). Built into dist/site_wily:
the home page (English, French), the privacy policy, the terms and legal notice, the licenses, the API (web/api: the
matches players share) and the releases (make_beta.py --release). Published by deploy_site.py.

    python site_wily.py      the pages again (after a release, make_beta.py does it)

Nothing on the site comes from elsewhere: no cookie, no analytics, no font or script from another server (the fonts
are the app's, under the SIL Open Font License)."""
import html
import json
import os
import re
import shutil
import sys
import time

import config

HERE = config.HERE
OUT = os.path.join(HERE, "dist", "site_wily")
SITE = "https://wily.valentingassend.com"
PUBLISHER = "Valentin Gassend"
CONTACT = "contact@valentingassend.com"
UPDATED = {"en": "8 October 2026", "fr": "8 octobre 2026"}
HOST = ("Infomaniak Network SA, Rue Eugène-Marziano 25, 1227 Les Acacias (GE), Switzerland · +41 22 820 35 44 · "
        "https://www.infomaniak.com")

CSS = """:root{--bg:#0d1117;--panel:#151b23;--ink:#e6edf3;--muted:#8b949e;--line:#2a313c;--ct:#5aa9ff;--t:#f0b23a;--good:#3ba55d;
--f-display:"Barlow Condensed",system-ui,sans-serif;--f-body:"IBM Plex Sans",system-ui,sans-serif;--f-mono:"JetBrains Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:light){:root{--bg:#f6f7f9;--panel:#fff;--ink:#14181f;--muted:#5b6470;--line:#d9dee5;--ct:#1f6fd1;--t:#a86b00}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 var(--f-body)}
a{color:var(--ct)}a:hover{text-decoration-thickness:2px}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
header.top{border-bottom:1px solid var(--line)}header.top .wrap{display:flex;align-items:center;gap:18px;min-height:60px;flex-wrap:wrap}
.brand{font:700 26px var(--f-display);letter-spacing:.02em;color:var(--ink);text-decoration:none}
nav.top{display:flex;gap:16px;margin-left:auto;flex-wrap:wrap}nav.top a{color:var(--muted);text-decoration:none;font-weight:500}nav.top a:hover,nav.top a[aria-current]{color:var(--ink)}
h1,h2,h3{font-family:var(--f-display);line-height:1.15;letter-spacing:.01em;text-wrap:balance}
h1{font-size:clamp(38px,6vw,60px);margin:56px 0 12px}h2{font-size:32px;margin:56px 0 12px}h3{font-size:22px;margin:0 0 6px}
.lede{font-size:19px;color:var(--muted);max-width:62ch}
.cta{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:26px 0 8px}
.btn{display:inline-block;background:var(--ink);color:var(--bg);font:600 17px var(--f-body);padding:12px 20px;border-radius:4px;text-decoration:none}
.btn:hover{opacity:.9}.btn.soon{background:var(--line);color:var(--muted)}
.note{color:var(--muted);font-size:14px}.mono{font-family:var(--f-mono);font-size:12.5px;word-break:break-all}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:18px 20px}
.card .eyebrow{font:600 12px var(--f-mono);text-transform:uppercase;letter-spacing:.08em;color:var(--t)}
.card ul{margin:8px 0 0;padding-left:18px}.card li{margin:4px 0}
ol.steps{padding-left:22px;max-width:75ch}ol.steps li{margin:10px 0}
code{font-family:var(--f-mono);font-size:13px;background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:1px 5px}
.doc{max-width:78ch}.doc h2{font-size:26px;margin:40px 0 8px}.doc p,.doc li{color:var(--ink)}
pre.notices{white-space:pre-wrap;font:13px/1.55 var(--f-mono);background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:18px;overflow-x:auto}
footer{border-top:1px solid var(--line);margin-top:64px;padding:26px 0 40px;color:var(--muted);font-size:14px}footer a{color:var(--muted)}
footer .wrap{display:flex;gap:18px;flex-wrap:wrap;justify-content:space-between}
@media (max-width:600px){h1{margin-top:36px}nav.top{margin-left:0}}
"""


def fonts_css():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble", os.path.join(HERE, "ui", "assemble.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    out = []
    for family, (fid, weights) in m.FONTS.items():
        for w in weights:
            out.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{w};font-display:swap;"
                       f"src:url(fonts/{fid}-latin-{w}-normal.woff2) format('woff2')}}")
    return "".join(out)


def page(lang, title, body, here, desc):
    other = {"index.html": "fr.html", "fr.html": "index.html", "privacy.html": "confidentialite.html",
             "confidentialite.html": "privacy.html", "terms.html": "conditions.html", "conditions.html": "terms.html",
             "licenses.html": "fr.html"}.get(here, "index.html")
    t = {"en": {"dl": "Download", "how": "How it works", "priv": "Privacy", "terms": "Terms", "lic": "Licenses", "home": "index.html",
                "pp": "privacy.html", "tt": "terms.html", "switch": "Français"},
         "fr": {"dl": "Télécharger", "how": "Comment ça marche", "priv": "Confidentialité", "terms": "Conditions", "lic": "Licences",
                "home": "fr.html", "pp": "confidentialite.html", "tt": "conditions.html", "switch": "English"}}[lang]
    cur = lambda f: ' aria-current="page"' if f == here else ""
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/site.css"></head>
<body><header class="top"><div class="wrap"><a class="brand" href="{t['home']}">Wily</a>
<nav class="top" aria-label="Site"><a href="{t['home']}#download">{t['dl']}</a><a href="{t['home']}#how">{t['how']}</a>
<a href="{t['pp']}"{cur(t['pp'])}>{t['priv']}</a><a href="{t['tt']}"{cur(t['tt'])}>{t['terms']}</a><a href="{other}" hreflang="{'fr' if lang == 'en' else 'en'}">{t['switch']}</a></nav></div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap"><span>Wily · {PUBLISHER} · <a href="mailto:{CONTACT}">{CONTACT}</a></span>
<span><a href="{t['pp']}">{t['priv']}</a> · <a href="{t['tt']}">{t['terms']}</a> · <a href="licenses.html">{t['lic']}</a></span>
<span>{'Not affiliated with Valve Corporation.' if lang == 'en' else 'Non affilié à Valve Corporation.'}</span></div></footer>
</body></html>
"""


def _release():
    try:
        return json.load(open(os.path.join(OUT, "releases", "latest.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def download_block(lang, rel):
    if not rel:
        return (f'<div class="cta"><span class="btn soon">{"Coming soon" if lang == "en" else "Bientôt disponible"}</span></div>')
    s, ins = rel["setup"], rel.get("installer")
    mb = s["size"] / 2 ** 20
    parts = sum(rel[k]["size"] for k in ("runtime", "code", "base") if isinstance(rel.get(k), dict)) / 2 ** 20
    when = time.strftime("%d/%m/%Y", time.localtime(rel["released"]))
    if not ins:   # a release made before the installer (08/10): the zip alone
        if lang == "en":
            return (f'<div class="cta"><a class="btn" href="releases/{s["file"]}" download>Download for Windows · {mb:.0f} MB</a>'
                    f'<span class="note">Version {html.escape(rel["app"])} · {when} · base of {rel["base"]["matches"]:,} matches</span></div>'
                    f'<p class="note">SHA-256: <span class="mono">{s["sha256"]}</span></p>')
        return (f'<div class="cta"><a class="btn" href="releases/{s["file"]}" download>Télécharger pour Windows · {mb:.0f} Mo</a>'
                f'<span class="note">Version {html.escape(rel["app"])} · {when} · base de {rel["base"]["matches"]:,} matchs</span></div>'
                f'<p class="note">SHA-256 : <span class="mono">{s["sha256"]}</span></p>').replace(",", " ")
    # 08/10, the user: a much simpler install. The setup (2 MB) downloads the rest and checks it; not signed with a paid
    # certificate yet: Windows' SmartScreen warns once, said here
    if lang == "en":
        return (f'<div class="cta"><a class="btn" href="releases/{ins["file"]}" download>Download Wily for Windows</a>'
                f'<span class="note">Version {html.escape(rel["app"])} · {when} · base of {rel["base"]["matches"]:,} matches · the setup downloads {parts:.0f} MB</span></div>'
                f'<p class="note">If Windows says <i>"Windows protected your PC"</i>: click <b>More info</b>, then <b>Run anyway</b>. The app isn\'t signed with a paid certificate yet; every part it downloads is checked against my author\'s signature.</p>'
                f'<p class="note">SHA-256 of the setup: <span class="mono">{ins["sha256"]}</span> · or <a href="releases/{s["file"]}" download>the zip</a> ({mb:.0f} MB, to unzip yourself)</p>')
    return (f'<div class="cta"><a class="btn" href="releases/{ins["file"]}" download>Télécharger Wily pour Windows</a>'
            f'<span class="note">Version {html.escape(rel["app"])} · {when} · base de {rel["base"]["matches"]:,} matchs · l\'installation télécharge {parts:.0f} Mo</span></div>'
            f'<p class="note">Si Windows affiche <i>« Windows a protégé votre ordinateur »</i> : clique sur <b>Informations complémentaires</b>, puis <b>Exécuter quand même</b>. L\'application n\'est pas encore signée par un certificat payant ; chaque partie qu\'elle télécharge est vérifiée avec la signature de son auteur.</p>'
            f'<p class="note">SHA-256 de l\'installation : <span class="mono">{ins["sha256"]}</span> · ou <a href="releases/{s["file"]}" download>le zip</a> ({mb:.0f} Mo, à décompresser toi-même)</p>').replace(",", " ")


HOME = {
"en": lambda rel: f"""
<h1>Hi, I'm Wily.</h1>
<p class="lede">Your CS2 coach, on your second screen. I give you live advice during your matches, warm you up with bots on your own situations before you play, and tell you clearly what to fix after. I learn from your demos and from a base of thousands of matches. Free alpha for Windows: the first version open to all, expect rough edges.</p>
<section id="download">{download_block("en", rel)}</section>
<div class="grid">
 <article class="card"><span class="eyebrow">Live</span><h3>During the match</h3><ul><li>What to buy for this round and the next</li><li>Where the Ts are likely to go, updated with the clock and what you see</li><li>Your paths and your strong spots on the radar, the grenades worth throwing now</li></ul></article>
 <article class="card"><span class="eyebrow">Prepare</span><h3>Before you play</h3><ul><li>A timed warm-up built on your weak points (5 to 45 min)</li><li>A training server with bots replaying your real deaths and clutches</li></ul></article>
 <article class="card"><span class="eyebrow">Review</span><h3>After the session</h3><ul><li>What changed against your previous matches, and why</li><li>Your focus of the week and the experiments to try</li><li>Every match round by round</li></ul></article>
</div>
<h2 id="how">How it works</h2>
<ol class="steps">
 <li>Open <b>WilySetup.exe</b>, then <b>Install</b>: it downloads me, checks every part and installs me for your Windows account (no administrator rights). I start with Windows and open Live by myself when CS2 starts.</li>
 <li>At my first launch, three steps: your Steam account (I find it), CS2 connected (one launch option to paste), your match history code (no Steam key to create). Then your matches are analyzed on your PC, a few minutes each.</li>
 <li>Prepare → <b>Warm-up</b>: the training server installs itself the first time (a separate copy of CS2 next to the game, links to its files, no extra space).</li>
</ol>
<p class="note">Needs Windows 10 or 11 (64-bit), CS2 on Steam, 8 GB of RAM, and disk space for your demos (about 250 MB per match).</p>
<h2>Fair play and privacy</h2>
<div class="grid">
 <article class="card"><h3>Only what Valve provides</h3><p>Game State Integration (the game's official feature for HUDs and RGB keyboards), the console log CS2 writes, the Steam Web API, the demos of your matches. I never read the game's memory or network traffic and I never play for you. The training server is a local copy of the game that only you join.</p></article>
 <article class="card"><h3>Your data stays on your PC</h3><p>Your matches, profile, Steam codes and voice stay on your PC (without a Steam key of your own, your match list goes through this site to Steam, nothing kept). The base I come with is anonymized. If you choose to, your new matches can join the base anonymized: no SteamID, no name, no match id. <a href="privacy.html">Privacy policy</a></p></article>
 <article class="card"><h3>Free alpha</h3><p>Free while it is tested. It's the first version open to all players: tell me what breaks with the <b>alpha · report</b> tag at the top of my page (you see what is sent), or by email. My updates are signed by my author, and I check them before installing anything. Questions or bugs: <a href="mailto:{CONTACT}">{CONTACT}</a>.</p></article>
</div>
""",
"fr": lambda rel: f"""
<h1>Salut, moi c'est Wily.</h1>
<p class="lede">Ton coach CS2, sur ton deuxième écran. Je te conseille en direct pendant tes matchs, je t'échauffe avec des bots sur tes propres situations avant de jouer, et je te dis clairement quoi corriger après. J'apprends de tes démos et d'une base de milliers de matchs. Alpha gratuite pour Windows : la première version ouverte à tous, des défauts restent à corriger.</p>
<section id="download">{download_block("fr", rel)}</section>
<div class="grid">
 <article class="card"><span class="eyebrow">Live</span><h3>Pendant le match</h3><ul><li>Quoi acheter pour ce round et le suivant</li><li>Où les T vont probablement aller, mis à jour avec le chrono et ce que tu vois</li><li>Tes chemins et tes bons spots sur le radar, les grenades à lancer maintenant</li></ul></article>
 <article class="card"><span class="eyebrow">Prepare</span><h3>Avant de jouer</h3><ul><li>Un échauffement chronométré construit sur tes points faibles (5 à 45 min)</li><li>Un serveur d'entraînement avec des bots qui rejouent tes vraies morts et tes clutchs</li></ul></article>
 <article class="card"><span class="eyebrow">Review</span><h3>Après la session</h3><ul><li>Ce qui a changé par rapport à tes matchs précédents, et pourquoi</li><li>Ton focus de la semaine et les expériences à tenter</li><li>Chaque match round par round</li></ul></article>
</div>
<h2 id="how">Comment ça marche</h2>
<ol class="steps">
 <li>Ouvre <b>WilySetup.exe</b>, puis <b>Installer</b> : il me télécharge, vérifie chaque partie et m'installe pour ton compte Windows (sans droits administrateur). Je démarre avec Windows et j'ouvre Live tout seul quand CS2 démarre.</li>
 <li>À mon premier lancement, trois étapes : ton compte Steam (je le trouve), CS2 connecté (une option de lancement à coller), ton code d'historique des matchs (aucune clé Steam à créer). Ensuite tes matchs sont analysés sur ton PC, quelques minutes chacun.</li>
 <li>Prepare → <b>Warm-up</b> : le serveur d'entraînement s'installe tout seul la première fois (une copie séparée de CS2 à côté du jeu, des liens vers ses fichiers, sans espace en plus).</li>
</ol>
<p class="note">Il faut Windows 10 ou 11 (64 bits), CS2 sur Steam, 8 Go de RAM et de la place pour tes démos (environ 250 Mo par match). L'app est en anglais.</p>
<h2>Fair-play et vie privée</h2>
<div class="grid">
 <article class="card"><h3>Seulement ce que Valve fournit</h3><p>Le Game State Integration (la fonction officielle du jeu pour les HUD et les claviers RGB), le journal de console que CS2 écrit, l'API Steam, les démos de tes matchs. Je ne lis jamais la mémoire du jeu ni son trafic réseau, et je ne joue jamais à ta place. Le serveur d'entraînement est une copie locale du jeu que toi seul rejoins.</p></article>
 <article class="card"><h3>Tes données restent sur ton PC</h3><p>Tes matchs, ton profil, tes codes Steam et ta voix restent sur ton PC (sans ta propre clé Steam, ta liste de matchs passe par ce site jusqu'à Steam, rien n'est gardé). La base qui vient avec moi est anonymisée. Si tu le choisis, tes nouveaux matchs peuvent rejoindre la base anonymisés : sans SteamID, sans pseudo, sans identifiant de match. <a href="confidentialite.html">Politique de confidentialité</a></p></article>
 <article class="card"><h3>Alpha gratuite</h3><p>Gratuite pendant les tests. C'est la première version ouverte à tous les joueurs : dis-moi ce qui casse avec l'étiquette <b>alpha · report</b> en haut de ma page (tu vois ce qui est envoyé), ou par e-mail. Mes mises à jour sont signées par mon auteur, et je les vérifie avant d'installer quoi que ce soit. Questions ou bugs : <a href="mailto:{CONTACT}">{CONTACT}</a>.</p></article>
</div>
""",
}

PRIVACY = {
"en": f"""<div class="doc"><h1>Privacy policy</h1><p class="note">Last updated: {UPDATED['en']}</p>
<p><b>Who we are.</b> Wily is a free app published by {PUBLISHER} (France), contact: <a href="mailto:{CONTACT}">{CONTACT}</a>. This website is hosted by Infomaniak Network SA (Switzerland).</p>
<p><b>In short.</b> The app runs on your PC: your matches, your profile, your voice recordings and your Steam codes stay there (without a Steam key of your own, the app lists your matches through this site, which keeps nothing: see 6). There are no accounts. What reaches this website: the app's update checks, anonymous usage counters (you can turn them off), the bug reports you choose to send, and your matches, anonymized, if you choose to share them. This website sets no cookies and has no analytics, advertising or tracking.</p>
<h2>1. This website</h2>
<p>When you visit it or download the app, the host's servers record technical logs (IP address, date and time, page or file requested, browser) for security and operation. The host keeps them for a limited time; we do not use them for anything else. The site loads nothing from other servers.</p>
<h2>2. Update checks</h2>
<p>The app downloads <code>releases/latest.json</code> from this site at start-up and every few hours, and the update files when you choose to install them. These requests carry no identifier; like any web request, they show your IP address to the host (see 1).</p>
<h2>3. Sharing your matches (off unless you turn it on)</h2>
<p>If you turn on <i>Share my matches</i> in the app's Settings, the app sends, for each new match analyzed on your PC, the tables it extracted from the demo (player positions every half second, duels, grenades, purchases, rounds), after anonymizing them on your PC:</p>
<ul><li>every SteamID is replaced by an identifier drawn with a random key used for that match only and never kept: no one, including us, can link it back to an account or link a player across two matches;</li>
<li>every player name is removed;</li><li>the match's Valve identifier is replaced by a random number.</li></ul>
<p>With them: a random identifier of your installation (made by the app, not linked to your Steam account), the app's version, each match's map and a fingerprint of its rounds (a match shared twice is kept once). Never your demos, your voice, your settings, your keys, your profile or your name.</p>
<ul><li><b>Purpose:</b> improve the reference base the app compares players with.</li>
<li><b>Legal basis:</b> your consent (Article 6(1)(a) GDPR). You can withdraw it at any time by turning the option off: nothing more is sent.</li>
<li><b>On the server:</b> the upload script does not store your IP address. It keeps, for two days at most, a hash of it with a daily salt, to limit uploads per day. The files wait on the host until the publisher's computer retrieves them (usually within an hour), then they are deleted from the host.</li>
<li><b>In the base:</b> the matches are then anonymous data. They cannot be linked to you or to the other players, and are kept as long as the base exists.</li>
<li><b>Before that:</b> you can ask us to delete what your installation sent, with your installation identifier (Settings → Share my matches).</li></ul>
<h2>4. Bug reports and feedback (only when you send them)</h2>
<p>The <i>alpha · report</i> button of the app sends what you write, your email address only if you give it (to answer you), the app's version, your installation identifier, and, if you leave the box ticked, technical details: versions, Windows version, the page you were on and its last errors, and the end of the app's log with SteamIDs, email addresses, in-game names it knows and your Windows user name removed. You see all of it before sending. The short "how was it?" asked after a warm-up or a match sends, only if you press Send, the face, the tags and the words you chose, with what it was about (the warm-up's score, or the map and score of the match). The <i>!report</i> command of the training server sends what you type with the drill you were on and where you stood on the map.</p>
<ul><li><b>Purpose:</b> fixing and improving the app. <b>Legal basis:</b> your consent, given by sending.</li>
<li><b>Retention:</b> the report waits on the host until the publisher's computer retrieves it (usually within an hour), then is deleted there; the publisher keeps it until the problem is solved, at most one year.</li>
<li>To have a report deleted, or to know what we keep: write to us.</li></ul>
<h2>5. Anonymous usage statistics (you can turn them off)</h2>
<p>To know which parts of the app are used and which are not, and to rework it on that basis, the app counts, per day: the pages opened and the time spent on each (only while the page is shown), the buttons used (identified by the page and the element, never by what is written on them), the number of errors the page meets, the time Live runs during a match, plus the app's version and a screen size class. Nothing else: no identifier (not even the installation's), no SteamID, no name, nothing you write, no match data.</p>
<ul><li>A day once over is sent to this site, added to that day's totals for all players, and the report itself is thrown away: only sums per day are kept, which cannot be linked to anyone. Your IP address is not kept (see 3 for the daily salted hash used to limit sending).</li>
<li><b>Legal basis:</b> our legitimate interest in measuring the use of the app, under the conditions the CNIL sets for exempted audience measurement (anonymous statistics only, for the publisher alone). <b>You can object at any time</b>: Settings → Usage statistics → Turn it off; nothing more is counted or sent. The app tells you about it the first time it opens.</li>
<li><b>Retention:</b> the daily totals, at most 25 months; the counters kept on your PC, 30 days.</li></ul>
<h2>6. Listing your matches through this site (when you have no Steam key of your own)</h2>
<p>To find your new matches, the app asks Valve's Steam Web API for the next match of your history. That needs a Steam Web API key: if you added your own in the app, the app asks Valve directly. If not, it sends this site, in the body of an encrypted request, your SteamID, your match history code and the code of the last match it knows; the site passes them to Valve with its own key and returns Valve's answer. The same way, the app can ask for the public Steam names of SteamIDs and a public friend list (to recognize your group).</p>
<ul><li><b>Nothing is kept:</b> the codes are used for that request only, never written to a file or a log by the site. Only a counter per day limits the volume (your address as a hash with a salt of the day, deleted after two days, see 3).</li>
<li><b>Legal basis:</b> the performance of the service you ask for (Article 6(1)(b) GDPR). To avoid it entirely, add your own key in Settings.</li></ul>
<h2>7. What the app does on your PC (not sent to us)</h2>
<ul><li><b>Match history code (and your own Steam Web API key, if you add one):</b> stored in <code>out/settings.json</code> on your PC, sent to Valve's Steam Web API to list your matches, directly with your key or through this site (see 6).</li>
<li><b>Your matches' demos</b> (downloaded from Valve's servers through your Steam client) and what the app extracts from them, including the other players of your matches (their SteamIDs and in-game names, as in any demo): processed on your PC to coach you, kept on your PC.</li>
<li><b>Voice (optional, off by default):</b> the app can record your microphone during matches and transcribe it on your PC. Recording your teammates (your PC's sound output) needs their agreement for each match; the app starts it only after you confirm it in game. Recordings never leave your PC.</li>
<li><b>Services the app contacts from your PC</b> when you use the related feature, under their own privacy policies: Valve (Steam Web API, Steam Community, the game coordinator through your Steam client, demo servers), Leetify's public API (statistics of the players you analyze), GitHub (map radars, a lineup book), Hugging Face (the speech recognition model, if you use voice).</li></ul>
<h2>8. The base that comes with the app</h2>
<p>The app ships reference tables computed from Counter-Strike 2 matchmaking demos. Every player in them has a made-up identifier and no name. Professional matches (from public demos published by HLTV.org) keep the players' public names; if you are one of them and want a data point removed, contact us.</p>
<h2>9. Your rights</h2>
<p>Under the GDPR you have the right to access, rectify and erase your personal data, to restrict or object to its processing, to data portability and to withdraw your consent. Contact: <a href="mailto:{CONTACT}">{CONTACT}</a>. You can also lodge a complaint with the CNIL (<a href="https://www.cnil.fr">www.cnil.fr</a>) or the supervisory authority of your country.</p>
<h2>10. Where the data is</h2>
<p>The host is in Switzerland, which the European Commission recognizes as providing adequate protection. The publisher's computer is in France.</p>
<h2>11. Changes</h2><p>This page changes when the app's use of data changes; the date at the top is the last update.</p></div>""",
"fr": f"""<div class="doc"><h1>Politique de confidentialité</h1><p class="note">Dernière mise à jour : {UPDATED['fr']}</p>
<p><b>Qui sommes-nous.</b> Wily est une application gratuite éditée par {PUBLISHER} (France), contact : <a href="mailto:{CONTACT}">{CONTACT}</a>. Ce site est hébergé par Infomaniak Network SA (Suisse).</p>
<p><b>En bref.</b> L'application tourne sur ton PC : tes matchs, ton profil, tes enregistrements de voix et tes codes Steam y restent (sans ta propre clé Steam, l'application liste tes matchs par ce site, qui ne garde rien : voir 6). Il n'y a pas de compte. Ce qui arrive sur ce site : les vérifications de mise à jour de l'application, des compteurs d'usage anonymes (tu peux les désactiver), les signalements de bug que tu choisis d'envoyer, et tes matchs, anonymisés, si tu choisis de les partager. Ce site ne dépose aucun cookie et n'a ni statistiques de visite, ni publicité, ni pistage.</p>
<h2>1. Ce site</h2>
<p>Quand tu le visites ou télécharges l'application, les serveurs de l'hébergeur enregistrent des journaux techniques (adresse IP, date et heure, page ou fichier demandé, navigateur) pour la sécurité et le fonctionnement. L'hébergeur les conserve une durée limitée ; nous ne les utilisons pas à d'autres fins. Le site ne charge rien depuis d'autres serveurs.</p>
<h2>2. Vérifications de mise à jour</h2>
<p>L'application télécharge <code>releases/latest.json</code> depuis ce site au démarrage puis toutes les quelques heures, et les fichiers de mise à jour quand tu choisis de les installer. Ces requêtes ne portent aucun identifiant ; comme toute requête web, elles montrent ton adresse IP à l'hébergeur (voir 1).</p>
<h2>3. Partage de tes matchs (désactivé tant que tu ne l'actives pas)</h2>
<p>Si tu actives <i>Share my matches</i> dans les Settings de Wily, l'application envoie, pour chaque nouveau match analysé sur ton PC, les tables extraites de la démo (positions des joueurs toutes les demi-secondes, duels, grenades, achats, rounds), après les avoir anonymisées sur ton PC :</p>
<ul><li>chaque SteamID est remplacé par un identifiant tiré avec une clé aléatoire propre à ce match et jamais conservée : personne, nous compris, ne peut remonter à un compte ni relier un joueur d'un match à l'autre ;</li>
<li>chaque pseudo est supprimé ;</li><li>l'identifiant Valve du match est remplacé par un nombre aléatoire.</li></ul>
<p>Avec elles : un identifiant aléatoire de ton installation (créé par l'application, sans lien avec ton compte Steam), la version de l'application, la map de chaque match et une empreinte de ses rounds (un match partagé deux fois n'est gardé qu'une fois). Jamais tes démos, ta voix, tes réglages, tes clés, ton profil ni ton nom.</p>
<ul><li><b>Finalité :</b> améliorer la base de référence à laquelle l'application compare les joueurs.</li>
<li><b>Base légale :</b> ton consentement (article 6.1.a du RGPD). Tu peux le retirer à tout moment en désactivant l'option : plus rien n'est envoyé.</li>
<li><b>Sur le serveur :</b> le script de réception ne conserve pas ton adresse IP. Il garde, deux jours au plus, une empreinte de celle-ci avec un sel du jour, pour limiter les envois par jour. Les fichiers attendent chez l'hébergeur que l'ordinateur de l'éditeur les récupère (en général dans l'heure), puis ils y sont supprimés.</li>
<li><b>Dans la base :</b> les matchs sont alors des données anonymes. Ils ne peuvent être reliés ni à toi ni aux autres joueurs, et sont conservés tant que la base existe.</li>
<li><b>Avant cela :</b> tu peux nous demander de supprimer ce que ton installation a envoyé, avec son identifiant (Settings → Share my matches).</li></ul>
<h2>4. Signalements de bug et avis (seulement quand tu les envoies)</h2>
<p>Le bouton <i>alpha · report</i> de l'application envoie ce que tu écris, ton adresse e-mail seulement si tu la donnes (pour te répondre), la version de l'application, l'identifiant de ton installation et, si tu laisses la case cochée, des détails techniques : versions, version de Windows, la page où tu étais et ses dernières erreurs, et la fin du journal de l'application dont sont retirés les SteamID, les adresses e-mail, les pseudos connus de l'application et ton nom d'utilisateur Windows. Tu vois tout avant d'envoyer. Le court « comment c'était ? » proposé après un échauffement ou un match envoie, seulement si tu appuies sur Send, le visage, les étiquettes et les mots que tu as choisis, avec ce dont il s'agit (le score de l'échauffement, ou la carte et le score du match). La commande <i>!report</i> du serveur d'entraînement envoie ce que tu tapes avec l'exercice en cours et l'endroit où tu étais sur la carte.</p>
<ul><li><b>Finalité :</b> corriger et améliorer l'application. <b>Base légale :</b> ton consentement, donné en envoyant.</li>
<li><b>Conservation :</b> le signalement attend chez l'hébergeur que l'ordinateur de l'éditeur le récupère (en général dans l'heure), puis y est supprimé ; l'éditeur le garde jusqu'à ce que le problème soit réglé, un an au plus.</li>
<li>Pour faire supprimer un signalement ou savoir ce que nous gardons : écris-nous.</li></ul>
<h2>5. Statistiques d'usage anonymes (tu peux les désactiver)</h2>
<p>Pour savoir quelles parties de l'application servent et lesquelles ne servent pas, et la retravailler sur cette base, l'application compte, par jour : les pages ouvertes et le temps passé sur chacune (seulement quand la page est affichée), les boutons utilisés (désignés par la page et l'élément, jamais par ce qui y est écrit), le nombre d'erreurs rencontrées par la page, le temps où Live tourne pendant un match, ainsi que la version de l'application et une classe de taille d'écran. Rien d'autre : aucun identifiant (pas même celui de l'installation), aucun SteamID, aucun pseudo, rien de ce que tu écris, aucune donnée de match.</p>
<ul><li>Une journée terminée est envoyée à ce site, ajoutée aux totaux de ce jour pour tous les joueurs, et le rapport lui-même est jeté : ne restent que des sommes par jour, qui ne peuvent être reliées à personne. Ton adresse IP n'est pas conservée (voir 3 pour l'empreinte salée du jour qui limite les envois).</li>
<li><b>Base légale :</b> notre intérêt légitime à mesurer l'usage de l'application, dans les conditions fixées par la CNIL pour la mesure d'audience exemptée de consentement (statistiques anonymes, pour l'éditeur seul). <b>Tu peux t'y opposer à tout moment</b> : Settings → Usage statistics → Turn it off ; plus rien n'est compté ni envoyé. L'application te le signale à sa première ouverture.</li>
<li><b>Conservation :</b> les totaux par jour, 25 mois au plus ; les compteurs gardés sur ton PC, 30 jours.</li></ul>
<h2>6. La liste de tes matchs par ce site (quand tu n'as pas ta propre clé Steam)</h2>
<p>Pour trouver tes nouveaux matchs, l'application demande à l'API Steam de Valve le match suivant de ton historique. Il faut pour cela une clé Steam Web API : si tu as ajouté la tienne dans l'application, elle interroge Valve directement. Sinon, elle envoie à ce site, dans le corps d'une requête chiffrée, ton SteamID, ton code d'historique des matchs et le code du dernier match qu'elle connaît ; le site les transmet à Valve avec sa propre clé et renvoie la réponse de Valve. De la même façon, l'application peut demander les pseudos Steam publics de SteamID et une liste d'amis publique (pour reconnaître ton groupe).</p>
<ul><li><b>Rien n'est conservé :</b> les codes servent à cette requête seulement, le site ne les écrit ni dans un fichier ni dans un journal. Seul un compteur par jour limite le volume (ton adresse sous forme d'empreinte avec un sel du jour, supprimée après deux jours, voir 3).</li>
<li><b>Base légale :</b> l'exécution du service que tu demandes (article 6(1)(b) du RGPD). Pour l'éviter complètement, ajoute ta propre clé dans Settings.</li></ul>
<h2>7. Ce que l'application fait sur ton PC (rien ne nous est envoyé)</h2>
<ul><li><b>Code d'historique des matchs (et ta propre clé Steam Web API, si tu en ajoutes une) :</b> enregistrés dans <code>out/settings.json</code> sur ton PC, envoyés à l'API Steam de Valve pour lister tes matchs, directement avec ta clé ou par ce site (voir 6).</li>
<li><b>Les démos de tes matchs</b> (téléchargées depuis les serveurs de Valve via ton client Steam) et ce que l'application en extrait, y compris les autres joueurs de tes matchs (leurs SteamID et pseudos, comme dans toute démo) : traités sur ton PC pour te coacher, conservés sur ton PC.</li>
<li><b>Voix (facultatif, désactivé par défaut) :</b> l'application peut enregistrer ton micro pendant tes matchs et le transcrire sur ton PC. Enregistrer tes coéquipiers (la sortie son de ton PC) demande leur accord à chaque match ; l'application ne le démarre qu'après ta confirmation en jeu. Les enregistrements ne quittent jamais ton PC. En France, enregistrer la parole d'autrui sans son consentement est puni par l'article 226-1 du Code pénal.</li>
<li><b>Services contactés depuis ton PC</b> quand tu utilises la fonction concernée, selon leurs propres politiques : Valve (API Steam, Steam Community, le coordinateur de jeu via ton client Steam, serveurs de démos), l'API publique de Leetify (statistiques des joueurs que tu analyses), GitHub (radars des maps, un livre de lineups), Hugging Face (le modèle de reconnaissance vocale, si tu utilises la voix).</li></ul>
<h2>8. La base fournie avec l'application</h2>
<p>L'application contient des tables de référence calculées à partir de démos de matchmaking de Counter-Strike 2. Chaque joueur y a un identifiant inventé et aucun pseudo. Les matchs professionnels (issus des démos publiques publiées par HLTV.org) gardent les noms publics des joueurs ; si tu es l'un d'eux et veux qu'une donnée soit retirée, contacte-nous.</p>
<h2>9. Tes droits</h2>
<p>Le RGPD te donne un droit d'accès, de rectification et d'effacement de tes données personnelles, de limitation et d'opposition à leur traitement, de portabilité et de retrait de ton consentement. Contact : <a href="mailto:{CONTACT}">{CONTACT}</a>. Tu peux aussi adresser une réclamation à la CNIL (<a href="https://www.cnil.fr">www.cnil.fr</a>).</p>
<h2>10. Où sont les données</h2>
<p>L'hébergeur est en Suisse, pays reconnu par la Commission européenne comme offrant une protection adéquate. L'ordinateur de l'éditeur est en France.</p>
<h2>11. Modifications</h2><p>Cette page change quand l'usage des données par l'application change ; la date en haut indique la dernière mise à jour.</p></div>""",
}

TERMS = {
"en": f"""<div class="doc"><h1>Terms of use and legal notice</h1><p class="note">Last updated: {UPDATED['en']}</p>
<h2>1. The app</h2><p>Wily is a free Windows app that analyzes your Counter-Strike 2 matches on your PC and coaches you during, before and after them. It is an alpha, the first version open to all: features can change, break or stop.</p>
<h2>2. Free, as is</h2><p>The app is provided free of charge and "as is", without warranty that it is accurate, uninterrupted or fit for a particular purpose. Its advice comes from statistics and can be wrong.</p>
<h2>3. Your use</h2><p>You may use the app for your own, non-commercial use. You may not sell it or distribute modified versions of it. You are responsible for using it lawfully: recording other people's voices needs their consent (in France, article 226-1 of the Penal Code), and the app records your teammates only after you confirm they agreed.</p>
<h2>4. Fair play</h2><p>The app only uses what Valve provides for third-party tools: Game State Integration, the console log the game writes, the Steam Web API and your matches' demos. It never reads the game's memory or network traffic and never acts in the game for you. The training server is a separate local copy of the game that only you join. Valve alone decides how its rules apply.</p>
<h2>5. Valve</h2><p>Wily is not affiliated with, endorsed or sponsored by Valve Corporation. Counter-Strike, Counter-Strike 2, CS2 and Steam are trademarks of Valve Corporation.</p>
<h2>6. Third-party components</h2><p>The app ships third-party software and data under their own licenses: see <a href="licenses.html">Licenses</a>.</p>
<h2>7. Liability</h2><p>As far as the law allows, the publisher is not liable for indirect damage, loss of data or of in-game results caused by the app. Nothing in these terms limits a liability the law does not allow to limit.</p>
<h2>8. Law</h2><p>These terms are governed by French law. If you are a consumer, you keep the protection of the mandatory rules of your country.</p>
<h2>9. Legal notice</h2><p><b>Publisher and director of publication:</b> {PUBLISHER}, <a href="mailto:{CONTACT}">{CONTACT}</a>.<br><b>Host:</b> {HOST}.</p></div>""",
"fr": f"""<div class="doc"><h1>Conditions d'utilisation et mentions légales</h1><p class="note">Dernière mise à jour : {UPDATED['fr']}</p>
<h2>1. L'application</h2><p>Wily est une application Windows gratuite qui analyse tes matchs de Counter-Strike 2 sur ton PC et te coache pendant, avant et après. C'est une alpha, la première version ouverte à tous : ses fonctions peuvent changer, casser ou s'arrêter.</p>
<h2>2. Gratuite, en l'état</h2><p>L'application est fournie gratuitement et « en l'état », sans garantie d'exactitude, de continuité ou d'adéquation à un usage particulier. Ses conseils viennent de statistiques et peuvent se tromper.</p>
<h2>3. Ton usage</h2><p>Tu peux utiliser l'application pour ton usage personnel et non commercial. Tu ne peux ni la vendre ni en distribuer des versions modifiées. Tu es responsable d'un usage conforme à la loi : enregistrer la parole d'autrui exige son consentement (article 226-1 du Code pénal), et l'application n'enregistre tes coéquipiers qu'après ta confirmation de leur accord.</p>
<h2>4. Fair-play</h2><p>L'application n'utilise que ce que Valve fournit aux outils tiers : le Game State Integration, le journal de console écrit par le jeu, l'API Steam et les démos de tes matchs. Wily ne lit jamais la mémoire du jeu ni son trafic réseau et n'agit jamais en jeu à ta place. Le serveur d'entraînement est une copie locale séparée du jeu que toi seul rejoins. Valve reste seul juge de l'application de ses règles.</p>
<h2>5. Valve</h2><p>Wily n'a aucun lien avec Valve Corporation : ni affiliation, ni approbation, ni sponsoring de sa part. Counter-Strike, Counter-Strike 2, CS2 et Steam sont des marques de Valve Corporation.</p>
<h2>6. Composants tiers</h2><p>L'application contient des logiciels et des données de tiers sous leurs propres licences : voir <a href="licenses.html">Licences</a>.</p>
<h2>7. Responsabilité</h2><p>Dans la mesure permise par la loi, l'éditeur n'est pas responsable des dommages indirects, pertes de données ou de résultats en jeu causés par l'application. Rien dans ces conditions ne limite une responsabilité que la loi ne permet pas de limiter.</p>
<h2>8. Droit applicable</h2><p>Ces conditions sont régies par le droit français. Si tu es consommateur, tu gardes la protection des règles impératives de ton pays.</p>
<h2>9. Mentions légales</h2><p><b>Éditeur et directeur de la publication :</b> {PUBLISHER}, <a href="mailto:{CONTACT}">{CONTACT}</a>.<br><b>Hébergeur :</b> {HOST.replace("Switzerland", "Suisse")}.</p></div>""",
}

ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#0d1117"/><circle cx="32" cy="32" r="17" fill="none" stroke="#5aa9ff" stroke-width="5"/><path d="M32 6v14M32 44v14M6 32h14M44 32h14" stroke="#f0b23a" stroke-width="5" stroke-linecap="round"/></svg>
"""

HTACCESS = """# Wily's site: no listing, no sniffing, nothing loaded from elsewhere
Options -Indexes
<Files ".user.ini">
Require all denied
</Files>
<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set Referrer-Policy "no-referrer"
Header always set Content-Security-Policy "default-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
<FilesMatch "^latest\\.json(\\.sig)?$">
Header set Cache-Control "no-cache"
</FilesMatch>
</IfModule>
AddType application/zip .zip
AddType application/octet-stream .exe
AddType application/json .json
AddType font/woff2 .woff2
"""


def steam_key_php():
    """The coach's Steam Web API key for the site's relay (web/api/steam.php, 08/10: players have no key of their own to
    create): written from his settings into web/api/steam_key.php (not versioned, refused to the web by .htaccess)."""
    key = str(config.settings().get("steam_api_key") or "")
    f = os.path.join(HERE, "web", "api", "steam_key.php")
    if re.fullmatch(r"[0-9A-Fa-f]{32}", key):
        open(f, "w", encoding="utf-8", newline="\n").write(f"<?php\nreturn '{key}';\n")
    else:
        print("note: no Steam Web API key in out/settings.json: the site's Steam relay will answer 'not set up'", flush=True)


def build():
    rel = _release()
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "fonts"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "licenses"), exist_ok=True)
    for f in os.listdir(os.path.join(HERE, "ui", "fonts")):
        if f.endswith(".woff2"):
            shutil.copy2(os.path.join(HERE, "ui", "fonts", f), os.path.join(OUT, "fonts"))
    for f in os.listdir(os.path.join(HERE, "ui", "fonts")):
        if f.endswith("-LICENSE.txt"):
            shutil.copy2(os.path.join(HERE, "ui", "fonts", f), os.path.join(OUT, "licenses", "font-" + f))
    open(os.path.join(OUT, "assets", "icon.svg"), "w", encoding="utf-8").write(ICON)
    open(os.path.join(OUT, "assets", "site.css"), "w", encoding="utf-8").write(fonts_css().replace("url(fonts/", "url(../fonts/") + CSS)
    for f in os.listdir(os.path.join(HERE, "legal", "licenses")):
        shutil.copy2(os.path.join(HERE, "legal", "licenses", f), os.path.join(OUT, "licenses"))
    shutil.copy2(os.path.join(HERE, "plugin", "CoachReplay", "LICENSE.txt"), os.path.join(OUT, "licenses", "CoachReplay-LICENSE.txt"))
    steam_key_php()
    shutil.copytree(os.path.join(HERE, "web"), OUT, dirs_exist_ok=True)   # the API (PHP) and its .htaccess
    desc = {"en": "Wily, your CS2 coach: live advice on your second screen, a warm-up with bots on your own situations, and a review of your matches.",
            "fr": "Wily, ton coach CS2 : des conseils en direct sur ton deuxième écran, un échauffement avec des bots sur tes situations, et la revue de tes matchs."}
    pages = {"index.html": ("en", "Wily · your CS2 coach on your second screen", HOME["en"](rel)),
             "fr.html": ("fr", "Wily · ton coach CS2 sur ton deuxième écran", HOME["fr"](rel)),
             "privacy.html": ("en", "Privacy policy · Wily", PRIVACY["en"]),
             "confidentialite.html": ("fr", "Politique de confidentialité · Wily", PRIVACY["fr"]),
             "terms.html": ("en", "Terms of use · Wily", TERMS["en"]),
             "conditions.html": ("fr", "Conditions d'utilisation · Wily", TERMS["fr"])}
    notices = html.escape(open(os.path.join(HERE, "legal", "THIRD_PARTY_NOTICES.txt"), encoding="utf-8").read())
    lic_links = " · ".join(f'<a href="licenses/{f}">{f[:-4]}</a>' for f in sorted(os.listdir(os.path.join(OUT, "licenses"))))
    pages["licenses.html"] = ("en", "Licenses · Wily", f'<div class="doc"><h1>Licenses</h1><p>{lic_links}</p></div><pre class="notices">{notices}</pre>')
    for f, (lang, title, body) in pages.items():
        open(os.path.join(OUT, f), "w", encoding="utf-8").write(page(lang, title, body, f, desc[lang]))
    open(os.path.join(OUT, ".htaccess"), "w", encoding="utf-8", newline="\n").write(HTACCESS)
    open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write("User-agent: *\nDisallow: /api/\nDisallow: /releases/\n")
    print(f"site: {OUT} ({len(pages)} pages, release {rel['app'] if rel else 'none yet'})", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
