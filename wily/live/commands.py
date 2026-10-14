"""What you ask Wily out loud during a match (06/10, the user: "que Wily fonctionne comme Jarvis: Wily exec B stuff,
Wily post-plant B, Wily rush A, Wily fake A go B, Wily force-buy A, Wily anti-éco B, Wily pistol round; en CT Wily fake
défense A, Wily reprise jungle, Wily contre rush B 5 stack; et les tendances: j'ai vu 3 rounds en B, tendance à fake,
3 A sans bombe").

parse(text) turns one phrase (French or English, as the live transcription gives it: "willy-rush-a", "WillyForceBuyA",
"Jarvis 3A sans bombe") into a list of orders; the phrase must start with Wily (or Jarvis, his first name for it):
nothing else is ever read as an order. gsi.wily() applies them to the round, the page shows what Wily understood and
what it changes, and asks in a few words when a piece is missing ("from A or B?").

Orders (k): dir (A, B, MID), tempo (rush, slow, control), exec, fake (site, then), split, stuff, plant / post (site),
cover (where), buy (force, eco, full, pistol: your buy), their (eco: an anti-eco), counter (rush on a site, how many),
fakedef (the site to fake, from where), retake (the site, through where), seen (rounds on a site), tendency (fake,
rush, slow), call (how many on a site, without the bomb), cancel."""
import re
import unicodedata
from wily.core.i18n import LANGS, tr

WAKE = re.compile(r"\b(?:wh?[iy]l+(?:y|ie|i|ey|ier|is|ee)|wylie|wiley|wili|wall?(?:y|i|ie|ey)|woll?(?:y|ie)|woody|jarv[iy]s|jerv[iy]s|jarvi)\b", re.I)
NUM = {"un": 1, "une": 1, "one": 1, "deux": 2, "two": 2, "trois": 3, "three": 3, "quatre": 4, "four": 4, "cinq": 5, "five": 5,
       "full": 5, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}
N_ = r"(un|une|one|deux|two|trois|three|quatre|four|cinq|five|[1-5])"
S_ = r"(a|b|mid|milieu|middle)"   # a site, or mid
WORDS = [   # what the live transcription hears for CS words (French mouths, English words)
    (r"\bpost[ -]?plain\b", "post plant"), (r"\bpost[ -]?plan\b", "post plant"), (r"\bpostplant\b", "post plant"),
    (r"\bplain\b", "plant"), (r"\bplanté\b", "plant"), (r"\bplanter\b", "plant"), (r"\bplante\b", "plant"),
    (r"\bexecute\b", "exec"), (r"\bexécute\b", "exec"), (r"\bexécution\b", "exec"), (r"\bexe\b", "exec"), (r"\bexecs?\b", "exec"),
    (r"\bforce[ -]?buy\b", "force"), (r"\bforcebuy\b", "force"), (r"\bforce[ -]?bail\b", "force"),
    (r"\banti[ -]?(?:éco|eco|echo|écho)\b", "antieco"), (r"\b(?:éco|echo|écho)\b", "eco"),
    (r"\bfull[ -]?buy\b", "fullbuy"), (r"\bpistol(?:et)?(?: round)?\b", "pistol"),
    (r"\b(?:stuffs?|stuf|stof|utilit(?:y|ies|aires?)|nades?|grenades?)\b", "stuff"),
    (r"\b(?:défense|defense|défends|defends|défendre|defend|def)\b", "defense"),
    (r"\b(?:reprise|retake|reprends|reprendre)\b", "retake"), (r"\b(?:contrôle|control|contrôler)(?: (?:de )?(?:la )?map)?\b", "control"),
    (r"\b(?:contre|counter|anti)\b", "counter"), (r"\b(?:face ?tack|five ?stack|5 ?stack|cinq ?stack|full ?stack)\b", "5stack"),
    (r"\b(?:tendance|tendances|tendency|habitude)\b", "tendency"), (r"\b(?:sans|without|no)\s+(?:la\s+)?(?:bombe|bomb|c4)\b", "nobomb"),
    (r"\b(?:j'ai vu|jai vu|j'invise|j'ai vus|i saw|i've seen|i seen|je vois|on a vu)\b", "seen"),
    (r"\b(?:rounds?|roundes?|manches?)\b", "rounds"), (r"\b(?:beaucoup|plein|a lot|lots|souvent)\b", "many"),
    (r"\b(?:rush|rushes|rusher|fast|vite|rapide|rapidement)\b", "rush"), (r"\b(?:slow|slowly|lent|lente|lentement|doucement)\b", "slow"),
    # 06/10 bot match: "Pistol Rush B, Apart", "go A from Ramp, slowly", "Mid slow to A", "Aigoo B" (I go B)
    (r"\b(?:aigoo|aïgo|i go|i'm going|im going|i will go|je vais|je pars|je file)\b", "go"),
    (r"\b(?:apart(?:ment)?s?|appart(?:ement)?s?|apse|apps)\b", "apps"),
    (r"\b(?:from|by|par|through|depuis|à travers|en passant par)\b", "via"),
    (r"\b(?:fake|fakes|feinte)\b", "fake"), (r"\b(?:split|splitte)\b", "split"), (r"\b(?:cover|couvre|couvrir|lurk)\b", "cover"),
    (r"\b(?:milieu|middle)\b", "mid"), (r"\b(?:annule|cancel|oublie|stop)\b", "cancel"),
]


def _norm(text):
    """"WillyForceBuyA" -> "willy force buy a"; "willy-rush-a" -> "willy rush a"; accents kept for the French words."""
    t = re.sub(r"(?<=[a-zà-ÿ])(?=[A-Z])", " ", str(text or ""))
    t = re.sub(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])", " ", t)
    t = unicodedata.normalize("NFC", t).lower()
    t = re.sub(r"[-_/.,!?;:«»\"()]", " ", t).replace("’", "'")
    for a, b in WORDS:
        t = re.sub(a, b, t)
    return re.sub(r"\s+", " ", t).strip()


def site_of(w):
    w = (w or "").lower()
    return "MID" if w in ("mid", "milieu", "middle") else w.upper() if w in ("a", "b") else None


def addressed(text):
    """True when the phrase calls Wily (or Jarvis, his first name for it)."""
    return bool(WAKE.search(str(text or "")))


def parse(text, zones=()):
    """The orders of one phrase said to Wily; [] when the phrase doesn't call Wily. zones: the map's callouts (a retake
    through Jungle, a cover of Window)."""
    raw = re.sub(r"(?<=[a-zà-ÿ])(?=[A-Z])", " ", str(text or ""))   # "WillyForceBuyA": the words apart first
    raw = re.sub(r"[-_]", " ", raw)
    m = WAKE.search(raw)
    if not m:
        return []
    if re.search(r"(?:(?<![a-z])à|\bto|\bde|\bque|\bavec|\bwith|\babout|\ble|\bla)\s*$", raw[:m.start()].strip(" ,.").lower()):
        return []   # about Wily, not to it ("j'ai donné l'info à Wily", 06/10)
    # the whole phrase but the name: "Go mid Wily", "last mid Wily" name it at the end (06/10: only what came after
    # it was read)
    t = _norm(raw[:m.start()] + " " + WAKE.sub(" ", raw[m.end():]))
    out = []
    add = lambda **o: out.append(o) if o not in out else None
    if re.search(r"^\s*cancel\b", t):
        return [{"k": "cancel"}]
    zone = None
    for z in sorted(zones or (), key=len, reverse=True):   # a callout of the map said in the phrase (Jungle, Palace...)
        if z and re.search(r"\b" + re.escape(z.lower()) + r"\b", t):
            zone = z
            break
    # CT: faking a defense ("Wily B fake défense A": you're B, show them A), countering a rush, a retake
    fd = re.search(r"(?:\b" + S_ + r"\s+)?fake\s+defense\s+" + S_ + r"\b", t) or re.search(r"\bfake\s+" + S_ + r"\s+defense\b", t)
    if fd:
        g = [x for x in fd.groups() if x]
        frm, site = (site_of(g[0]), site_of(g[1])) if len(g) == 2 else (None, site_of(g[-1]))
        add(k="fakedef", site=site, **({"frm": frm} if frm else {}))
        return out
    cr = re.search(r"\bcounter\s+(?:(?:le|les|un|une|the|a)\s+)?rush\s+" + S_ + r"\b(?:\s+(?:" + N_ + r"\s*)?(5stack))?", t) \
        or re.search(r"\bcounter\s+" + S_ + r"\s+rush\b", t)
    if cr:
        n = 5 if "5stack" in t else NUM.get((cr.groups() + (None, None))[1] or "", None)
        add(k="counter", what="rush", site=site_of(cr.group(1)), **({"n": n} if n else {}))
        return out
    if re.search(r"\bretake\b", t):
        rs = re.search(r"\bretake\s+(?:en\s+|on\s+|sur\s+|par\s+|via\s+|from\s+|depuis\s+)?" + S_ + r"\b", t)
        add(k="retake", **({"site": site_of(rs.group(1))} if rs and site_of(rs.group(1)) != "MID" else {}),
            **({"via": zone} if zone else {"via": "Mid"} if rs and site_of(rs.group(1)) == "MID" else {}))
        return out
    # tendencies: what they did ("j'ai vu 3 rounds en B", "beaucoup de rounds en B"), how they play, a call without the bomb
    sn = re.search(r"\bseen\b.*?\b" + N_ + r"\s+rounds\s+(?:en|à|a|on|at|in|sur)?\s*" + S_ + r"\b", t) \
        or re.search(r"\bseen\s+(" + S_[1:-1] + r")(?:\s+(?:" + S_[1:-1] + r"))+\b", t)
    if sn and len(sn.groups()) >= 2:
        add(k="seen", rounds=NUM.get(sn.group(1), 3), site=site_of(sn.group(2)))
        return out
    if sn:   # "j'ai vu B, B, B": one round per letter
        letters = re.findall(r"\b(a|b)\b", t[sn.start():])
        if letters:
            add(k="seen", rounds=len(letters), site=site_of(letters[-1]))
            return out
    mn = re.search(r"\bmany\s+(?:de\s+|of\s+)?rounds\s+(?:en|à|a|on|at|in|sur)?\s*" + S_ + r"\b", t)
    if mn:
        add(k="seen", rounds=4, site=site_of(mn.group(1)), many=True)
        return out
    td = re.search(r"\btendency\s+(?:à|a|to)?\s*(fake|rush|slow)\b", t)
    if td:
        add(k="tendency", v=td.group(1))
        return out
    nb = re.search(r"\b" + N_ + r"\s*(a|b|mid)\b(?:\s+" + N_ + r"\s*(?:a|b|mid))?.*\bnobomb\b", t)
    if nb:
        add(k="call", n=NUM.get(nb.group(1), 1), site=site_of(nb.group(2)), nobomb=True)
        return out
    # T: the plan (a way, a tempo, an execute, a fake, a split), the stuff, the plant, a cover
    fk = re.search(r"\bfake\s+" + S_ + r"\b(?:\s+(?:go|puis|then|et|and|hit)?\s*" + S_ + r"\b)?", t)
    if fk:
        site, then = site_of(fk.group(1)), site_of(fk.group(2)) if fk.group(2) else None
        then = then or ("B" if site == "A" else "A" if site == "B" else None)
        add(k="fake", site=site, **({"then": then} if then else {}))
        if then:
            add(k="dir", v=then)
    pp = re.search(r"\bpost plant\s+" + S_ + r"\b", t) or re.search(r"\bpost plant\b", t)
    if pp:
        add(k="post", **({"site": site_of(pp.group(1))} if pp.groups() and pp.group(1) else {}))
    else:
        pl = re.search(r"\bplant\s+(?:en\s+|on\s+|sur\s+)?" + S_ + r"\b", t)
        if pl:
            add(k="plant", site=site_of(pl.group(1)))
    cv = re.search(r"\bcover\s+(?:le\s+|la\s+|the\s+)?" + S_ + r"\b", t)
    if cv:
        add(k="cover", where=site_of(cv.group(1)))
    elif re.search(r"\bcover\b", t) and zone:
        add(k="cover", where=zone)
    ae = re.search(r"\bantieco\b(?:\s+(?:en\s+)?" + S_ + r"\b)?", t)
    if ae:
        add(k="their", v="eco")
        if ae.group(1):
            add(k="dir", v=site_of(ae.group(1)))
    for v, w in (("force", "force"), ("eco", "eco"), ("fullbuy", "full"), ("pistol", "pistol")):
        b = re.search(r"\b" + v + r"\b(?:\s+(?:en\s+)?" + S_ + r"\b)?", t)
        if b and not (v == "eco" and ae):
            add(k="buy", v=w)
            if b.group(1):
                add(k="dir", v=site_of(b.group(1)))
    for v in ("rush", "slow", "control"):
        tp = re.search(r"\b" + v + r"\b(?:\s+(?:en\s+|on\s+|sur\s+|de\s+)?" + S_ + r"\b)?", t)
        if tp:
            add(k="tempo", v=v)
            if tp.group(1):
                add(k="dir", v=site_of(tp.group(1)))
    ex = re.search(r"\bexec\s+(?:en\s+|on\s+|sur\s+)?" + S_ + r"\b", t)
    if ex:
        add(k="exec", site=site_of(ex.group(1)))
        add(k="dir", v=site_of(ex.group(1)))
    sp = re.search(r"\bsplit\s+(?:en\s+|on\s+)?" + S_ + r"\b", t)
    if sp:
        add(k="split", site=site_of(sp.group(1)))
        add(k="dir", v=site_of(sp.group(1)))
    st = re.search(r"\bstuff\b(?:\s+(?:en\s+|on\s+|de\s+|pour\s+|for\s+)?" + S_ + r"\b)?", t) or re.search(r"\b" + S_ + r"\s+stuff\b", t)
    if st:
        s = site_of(st.group(1)) if st.groups() and st.group(1) else None
        add(k="stuff", **({"site": s} if s else {}))
        if s:
            add(k="dir", v=s)
    if re.search(r"\b(?:only|que|full|juste)\s+stack|\bstacking\b|\bils\s+stack\b", t) and not re.search(r"\bstack\s+(?:a|b)\b|\b(?:a|b)\s+stack\b", t):
        add(k="tendency", v="stack")   # "I feel they're playing only stack"
    # mid then a site ("mid to A", "Mid slow to A", "mid A"): that site through mid
    ms = re.search(r"\bmid\b(?:\s+(?:slow|rush|control))?\s+(?:to\s+|vers\s+|puis\s+|then\s+|go\s+)?(a|b)\b", t)
    if ms and not any(o["k"] == "dir" and o["v"] in ("A", "B") for o in out):
        add(k="dir", v=site_of(ms.group(1)), via="Mid")
    if not any(o["k"] == "dir" for o in out):   # "Wily A", "Wily mid", "go B", "I go mid": the way only
        w = re.search(r"\b(?:go|plan|on\s+va|on\s+joue|play|joue|vers)\s+(?:to\s+|en\s+|à\s+)?" + S_ + r"\b", t) \
            or re.match(r"^(?:en\s+)?" + S_ + r"\b", t)
        if w:
            add(k="dir", v=site_of(w.group(1)))
        elif not out and len(t.split()) <= 4:   # "non B, Wily B": the last letter of a short phrase
            ls = re.findall(r"\b" + S_ + r"\b", t)
            if ls:
                add(k="dir", v=site_of(ls[-1]))
    # one way per phrase: the last way said wins ("fake A go B": B)
    dirs = [o for o in out if o["k"] == "dir"]
    if len(dirs) > 1:
        keep = dirs[-1]
        out = [o for o in out if o["k"] != "dir" or o is keep]
    # its way in: a place of the map said with it ("B Apps", "A from Ramp", "A by Palace"), not the site itself
    d = next((o for o in out if o["k"] == "dir"), None)
    if d and not d.get("via"):   # a callout's own word said ("A Ramp": ramp), the generic ones apart; the last one said wins
        ws = t.split()
        best = None
        for z in zones or ():
            for w in re.findall(r"[a-zà-ÿ]+", (z or "").lower()):
                if len(w) >= 3 and w not in ("site", "bombsite", "mid", "top", "spawn", "the") and w in ws:
                    at = max(i for i, x in enumerate(ws) if x == w)
                    if best is None or at > best[0]:
                        best = (at, w)
        if best:
            d["via"] = best[1].capitalize()
    # what they do ("they tried to rush B", "ils stack A"): what you saw, not your plan: no way, no tempo of yours (the
    # call reads it)
    if re.search(r"\b(?:they|they're|theyre|ils|them|eux|leur|their)\b", t):
        out = [o for o in out if o["k"] not in ("dir", "tempo", "buy", "stuff", "exec", "split")]
    return out


SAY = {"A": "A", "B": "B", "MID": "mid"}


def ack(orders, lang="en"):
    """What Wily says back, a few words in a language of the app (12/10: French and English; 13/10: every language,
    gsi.wily keeps one per language for the voice): the plan first ("rush A"), then the rest."""
    sy = lambda x: tr("mid", lang) if x == "MID" else SAY.get(x, x)
    O = {o["k"]: o for o in orders}
    plan = []
    if "tempo" in O:
        plan.append({"rush": tr("rush", lang), "slow": tr("slow", lang), "control": tr("map control", lang)}[O["tempo"]["v"]])
    if "fake" in O:
        f = O["fake"]
        plan.append(tr("fake {site}, then {then}", lang, site=f['site'], then=sy(f['then'])) if f.get("then") else tr("fake {site}", lang, site=f['site']))
    elif "exec" in O:
        plan.append(tr("exec {site}", lang, site=O['exec']['site']))
    elif "split" in O:
        plan.append(tr("split {site}", lang, site=O['split']['site']))
    elif "dir" in O:
        d = sy(O["dir"]["v"])
        plan.append(tr("{way} through {via}", lang, way=d, via=O['dir']['via']) if O["dir"].get("via") else d)
    parts = [" ".join(plan)] if plan else []
    for o in orders:
        k = o["k"]
        if k == "stuff" or (k == "exec"):
            parts.append(tr("your utility is up", lang))
        elif k in ("plant", "post"):
            parts.append(tr("post-plant {site}", lang, site=sy(o.get('site'))).strip() if o.get("site") else tr("post-plant", lang))
        elif k == "cover":
            parts.append(tr("cover {where}", lang, where=sy(o['where'])))
        elif k == "buy":
            parts.append({"force": tr("force-buy", lang), "eco": tr("eco", lang), "full": tr("full buy", lang), "pistol": tr("pistol", lang)}[o["v"]])
        elif k == "their":
            parts.append(tr("anti-eco", lang))
        elif k == "counter":
            parts.append(tr("vs rush {site}", lang, site=o['site']) if o.get("site") else tr("vs rush", lang))
        elif k == "fakedef":
            parts.append(tr("fake defense {site}", lang, site=o['site']) if o.get("site") else tr("fake defense", lang))
        elif k == "retake":
            r = tr("retake {site}", lang, site=o['site']) if o.get("site") else tr("retake", lang)
            parts.append(tr("{retake} through {via}", lang, retake=r, via=o['via']) if o.get("via") else r)
        elif k == "seen":
            parts.append(tr("{n} rounds on {site}, noted", lang, n=o['rounds'], site=sy(o['site'])))
        elif k == "tendency":
            they = {"fake": tr("they fake", lang), "rush": tr("they rush", lang), "slow": tr("they play slow", lang), "stack": tr("they stack", lang)}[o["v"]]
            parts.append(tr("{what}, noted", lang, what=they))
        elif k == "call":
            parts.append(tr("{n} {site} without the bomb, noted", lang, n=o['n'], site=sy(o['site'])))
        elif k == "cancel":
            parts.append(tr("cancelled", lang))
    seen = []
    for x in parts:
        if x and x not in seen:
            seen.append(x)
    return ", ".join(seen)
