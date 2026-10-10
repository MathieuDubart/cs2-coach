"""Your last month of matches without any match code (10/10, the user: "remonte sur les codes de match du compte de mon
client tout seul sur tous les matchs du dernier mois"). Valve's Steam API only walks a history forward from a code, and
the game gives the last 8: the matches before are out of reach that way. Steam's page of your personal game data
(steamcommunity.com/my/gcpd/730, tabs Premier, Competitive, Wingman) lists every match with the link of its demo while
Valve keeps it (about a month).

That page needs your Steam session, which stays in your browser: the app never sees it. A bookmark of the app (a small
script, BOOKMARKLET) runs on that page when you click it: it presses "Load more history" until the matches are older than
a month, reads each match (date, map, score, the demo's link, the players' account ids, your kills, assists, deaths and
score) and saves them as a file (wily-steam-history-<tab>-<time>.json) in your Downloads folder. Nothing is sent
anywhere. The app watches that folder: a file found is checked (only Valve's demo links, only your own account, only
the last 35 days), added to your matches (a match already known by its demo's link is skipped), moved out of the
Downloads, and the sync downloads and analyzes the new demos.

A match of that page has no match id (only the demo's link, whose name holds its reservation id): it is kept under that
number; when Valve's list later gives the same match (same link), the entry already there is used."""
import datetime as dt
import glob
import json
import os
import re
import shutil
import time

import config

PAGE = "https://steamcommunity.com/my/gcpd/730?tab=matchhistorypremier"
TABS = {"matchhistorypremier": "Premier", "matchhistorycompetitive": "Competitive", "matchhistorywingman": "Wingman"}
URL_RE = re.compile(r"^https?://replay\d{1,4}\.valve\.net/730/(\d{6,25})_(\d{1,12})\.dem\.bz2$")
NAME = "wily-steam-history-"
DONE = os.path.join(config.CACHE, "steam_history")
DAYS = 35
STEAM64 = 76561197960265728

# The bookmark's script (one line once minified by bookmarklet()): it runs on Steam's page, in your browser, and only
# writes a file there. The page keeps one table per match; a match's block is the largest element around its demo
# link that holds no other demo link.
_JS = r"""
(async()=>{
const tab=new URLSearchParams(location.search).get('tab')||'';
if(!/\/gcpd\/730/.test(location.pathname)){alert('Wily: open your Steam match history first (the button in Wily), then click this bookmark there.');return}
const LIM=Date.now()-%(days)d*864e5,sleep=ms=>new Promise(r=>setTimeout(r,ms));
const DATE=/(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) GMT/;
const times=()=>[...document.body.innerText.matchAll(new RegExp(DATE.source,'g'))].map(m=>Date.parse(m[1]+'T'+m[2]+'Z'));
const note=document.createElement('div');note.style.cssText='position:fixed;top:12px;right:12px;z-index:99999;background:#111;color:#fff;padding:10px 14px;border:2px solid #4b9;font:14px sans-serif;border-radius:4px';document.body.appendChild(note);
for(let i=0;i<80;i++){const t=times();note.textContent='Wily: reading your matches... '+t.length;
 const b=document.querySelector('#load_more_clickable,#load_more_button');
 if(!b||b.offsetParent===null||(t.length&&Math.min(...t)<LIM))break;
 const n=document.body.innerText.length;b.click();
 for(let k=0;k<60&&document.body.innerText.length===n;k++)await sleep(250);await sleep(400)}
const me=String(window.g_steamID||'');const myAcc=me?String(BigInt(me)-%(s64)dn):'';
const out=[];
for(const a of document.querySelectorAll('a[href*=".dem.bz2"]')){
 let el=a;while(el.parentElement&&el.parentElement.querySelectorAll('a[href*=".dem.bz2"]').length===1)el=el.parentElement;
 const tx=el.innerText,d=tx.match(DATE);if(!d)continue;
 const mp=(tx.match(/(Premier|Competitive|Wingman)[^\S\n]+([^\n]+)/)||[]);
 const sc=(tx.match(/\b(\d{1,2})\s*:\s*(\d{1,2})\b/)||[]);
 const acc=[...new Set([...el.querySelectorAll('[data-miniprofile]')].map(x=>x.getAttribute('data-miniprofile')))];
 let mine=null;const row=myAcc&&el.querySelector('[data-miniprofile="'+myAcc+'"]');
 if(row){const tr=row.closest('tr');if(tr){const v=[...tr.querySelectorAll('td')].map(c=>c.innerText.trim()).filter(s=>/^-?\d+%%?$/.test(s));mine=v}}
 out.push({url:a.href,time:d[1]+'T'+d[2]+'Z',map:(mp[2]||'').trim(),mode:mp[1]||'',score:sc[1]?[+sc[1],+sc[2]]:null,accounts:acc,mine})}
const f=new Blob([JSON.stringify({v:1,tab,steamid:me,at:new Date().toISOString(),matches:out})],{type:'application/json'});
const l=document.createElement('a');l.href=URL.createObjectURL(f);l.download='%(name)s'+(tab||'page')+'-'+Date.now()+'.json';document.body.appendChild(l);l.click();
note.textContent='Wily: '+out.length+' match(es) saved for the app. Other modes: open their tab and click the bookmark again.'})()
"""


def bookmarklet():
    """The bookmark's address (javascript:...), to drag to the bookmarks bar."""
    js = _JS % {"days": DAYS, "s64": STEAM64, "name": NAME}
    js = "".join(line.strip() for line in js.strip().splitlines())
    from urllib.parse import quote
    return "javascript:" + quote(js, safe="()[]{}=,;:'+-*/!?.<>&|$_")


def downloads_dir():
    """Your Downloads folder (where Windows really keeps it: it can be moved)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            v = winreg.QueryValueEx(k, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
            v = os.path.expandvars(v)
            if os.path.isdir(v):
                return v
    except OSError:
        pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


def _num(v):
    try:
        return int(str(v).rstrip("%"))
    except ValueError:
        return None


def parse(data, sid):
    """The page's matches as entries of the app's match list; refused when the file is another account's."""
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("matches"), list):
        raise ValueError("not a file of Wily's bookmark")
    if str(data.get("steamid") or "") != str(sid):
        raise ValueError("this file is another Steam account's history")
    since = dt.datetime.utcnow() - dt.timedelta(days=DAYS)
    out = []
    for m in data["matches"][:500]:
        url = str(m.get("url") or "").replace("https://", "http://")
        g = URL_RE.match(url)
        if not g:
            continue
        try:
            t = dt.datetime.strptime(str(m.get("time"))[:19], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
        if t < since:
            continue
        accs = [int(a) for a in (m.get("accounts") or []) if str(a).isdigit()][:10]
        mine = [_num(x) for x in (m.get("mine") or []) if _num(x) is not None]
        me = {"source": "steam history"}   # the demo gives the rest
        if len(mine) >= 4:   # the row's numbers: ping, kills, assists, deaths, (MVPs), (HS %), score
            k, a, d = mine[1:4]
            me.update(kills=k, assists=a, deaths=d, score=mine[-1])
        sc = m.get("score") if isinstance(m.get("score"), list) and len(m["score"]) == 2 else None
        mid = str(int(g.group(1)))
        out.append({"match_id": mid, "time": t.strftime("%Y-%m-%dT%H:%M"), "url": url, "players": len(accs) or None,
                    "team_scores": sc, "rounds": sum(sc) if sc else None, "me": me, "accounts": accs,
                    "mode": str(m.get("mode") or "")[:20], "map_name": str(m.get("map") or "")[:40], "from": "steam history"})
    return out


def add(entries, log=print):
    """Adds the page's matches to the match list. -> the new ones' ids (a match already known by its demo's link is
    skipped)."""
    import cs2coach
    reg = cs2coach.registry()
    urls = {m.get("url") for m in reg.values() if m.get("url")}
    new = []
    for e in entries:
        if e["url"] in urls or e["match_id"] in reg:
            continue
        reg[e["match_id"]] = e
        urls.add(e["url"])
        new.append(e["match_id"])
    if new:
        cs2coach.save_registry(reg)
    log(f"Steam history: {len(entries)} match(es) of the last month read, {len(new)} new")
    return new


def scan(sid, log=print):
    """The bookmark's files in your Downloads: each one read, added, then moved out (kept in the app's cache).
    -> (files read, new matches, error or None)."""
    files = sorted(glob.glob(os.path.join(downloads_dir(), NAME + "*.json")))
    n_new, err = 0, None
    for f in files:
        try:
            if time.time() - os.path.getmtime(f) < 1:   # still being written
                continue
            data = json.load(open(f, encoding="utf-8"))
            n_new += len(add(parse(data, sid), log))
        except (OSError, ValueError) as e:
            err = f"{os.path.basename(f)}: {e}"
            log(f"Steam history: {err}")
        os.makedirs(DONE, exist_ok=True)
        try:
            shutil.move(f, os.path.join(DONE, os.path.basename(f)))
        except OSError:
            pass
    if files:
        s = config.settings()
        s.setdefault("players", {}).setdefault(str(sid), {})["history_import"] = {
            "at": dt.datetime.now().isoformat(timespec="minutes"), "files": len(files), "new": n_new, "error": err}
        config.save_settings(s)
    return len(files), n_new, err
