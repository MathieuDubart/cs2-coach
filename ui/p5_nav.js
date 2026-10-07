
// ---------- navigation: three moments (05/10): Live during the match, Prepare before it, Review after it ----------
const GROUP={ingame:"ingame",prepare:"prepare",review:"review",profile:"review",matches:"review",maps:"review",midround:"review",progress:"review",analysis:"review",routine:"review",team:"review",players:"review",pros:"review",settings:"settings"};
// Review in three levels (05/10): the session, your profile, every match; the detailed pages open from the profile
const SUB={review:[["review","Session"],["profile","Profile"],["matches","Matches"]]};   // 07/10: no Explore (the menu's favorites instead)
const PLAYER_VIEWS=["ingame","prepare","review","profile","matches","maps","midround","progress","analysis","routine"];
// old French addresses keep working, and the moments' names
const ALIAS={partie:"ingame",avant:"prepare",bilan:"review",matchs:"matches",cartes:"maps",mid:"midround",prog:"progress",synthese:"analysis",equipe:"team",joueurs:"players",steam:"settings",live:"ingame",prep:"prepare",warmup:"prepare"};
// your account on the right of the bar (05/10), its menu (07/10, the user: "juste un espace favoris quand je clique sur
// mon profil, avec les autres profils que j'ai mis en favoris, à la place d'une répétition des onglets de la nav; mets
// aussi les paramètres et le bouton update"): you and your favorite profiles, a player or a match to open, your
// update, the settings. Nothing the bar's three moments already give.
let ACCT=null;   // your Steam avatar when the profile has none (/api/account: the public profile, kept a day)
const avatarHtml=(av,nm,cls="av")=>av?`<img class="${cls}" src="${esc(av)}" alt="" width="22" height="22">`:`<span class="${cls} ini" aria-hidden="true">${esc(String(nm||"?").trim().charAt(0).toUpperCase())}</span>`;
function acctUpdate(){const ac=$("#acct"),ab=$("#acctbtn"),am=$("#acctmenu");if(!ac)return;
  ac.hidden=!D.local;if(ac.hidden)return;
  const mi=D.own&&IDX()[D.own],me=D.own&&D.players[D.own];
  const av=mi?((me&&((me.advice||{}).steam||{}).avatar)||mi.avatar||(ACCT&&ACCT.avatar)):null,nm=(me&&me.name)||(mi&&mi.name)||"Menu";
  if(mi&&!av&&ACCT===null){ACCT={};fetch("/api/account").then(r=>r.json()).then(j=>{ACCT=j||{};if(ACCT.avatar)acctUpdate()}).catch(()=>{})}
  ab.innerHTML=`${mi?avatarHtml(av,nm):`<span class="av ini" aria-hidden="true">☰</span>`}<span class="an">${esc(nm)}</span><span class="caret" aria-hidden="true">▾</span>`;
  ab.title=mi?`${nm}: your favorites, a player to open, update, settings`:"Menu";ab.setAttribute("aria-label",ab.title);
  const im=$("img.av",ab);if(im)im.onerror=()=>{const sp=document.createElement("span");sp.className="av ini";sp.setAttribute("aria-hidden","true");sp.textContent=String(nm).trim().charAt(0).toUpperCase();im.replaceWith(sp)};   // an avatar that doesn't load: your initial
  favRender();
  ab.onclick=e=>{e.stopPropagation();const open=am.hidden;am.hidden=!open;ab.setAttribute("aria-expanded",String(open));if(open){const f=$("a,input",am);if(f)f.focus()}};
  am.onclick=e=>e.stopPropagation()}
// favorites: profiles kept at hand (this browser); the first time, your team's players
function favs(){const f=store("favs");return Array.isArray(f)?f:[]}
function favToggle(sid){const f=favs();store("favs",f.includes(sid)?f.filter(x=>x!==sid):[...f,sid]);favRender();navUpdate(S.view)}
function favSeed(){if(store("favs")!==null||!D.local||!D.own)return;store("favs",[]);
  fetch("teams/index.json").then(r=>r.ok?r.json():[]).then(T=>{const m=new Set();for(const t of T||[])if((t.members||[]).some(x=>String(x.steamid)===D.own))for(const x of t.members||[])if(String(x.steamid)!==D.own)m.add(String(x.steamid));
    if(m.size){store("favs",[...m]);favRender()}}).catch(()=>{})}
function favRender(){const box=$("#favlist");if(!box)return;favSeed();const I=IDX(),list=[...(D.own&&I[D.own]?[D.own]:[]),...favs().filter(s=>I[s]&&s!==D.own)];
  box.innerHTML=list.map(s=>{const e=I[s];return `<a href="#" data-fav="${s}" ${s===S.player?'aria-current="true"':""}>${avatarHtml(e.avatar,e.name)}<span>${esc(e.name)}${s===D.own?' <small>you</small>':""}</span></a>`}).join("")
    +(list.length<2?`<span class="none">Open a player below, then ☆ on the bar keeps them here.</span>`:"");
  $$("img.av",box).forEach(im=>im.onerror=()=>{const sp=document.createElement("span");sp.className="av ini";sp.setAttribute("aria-hidden","true");sp.textContent=(im.closest("a").textContent||"?").trim().charAt(0).toUpperCase();im.replaceWith(sp)});   // an avatar gone: the initial
  $$("[data-fav]",box).forEach(a=>a.onclick=e=>{e.preventDefault();acctClose();const s=a.dataset.fav;if(s===S.player)return;
    S.view=s===D.own?"review":(["profile","matches","maps","analysis","midround","progress","routine"].includes(S.view)?S.view:"profile");setPlayer(s)})}
function acctClose(){const am=$("#acctmenu"),ab=$("#acctbtn");if(am&&!am.hidden){am.hidden=true;if(ab)ab.setAttribute("aria-expanded","false")}}
document.addEventListener("click",e=>{if(!e.target.closest||!e.target.closest("#acct"))acctClose()});
document.addEventListener("keydown",e=>{if(e.key==="Escape"){const am=$("#acctmenu");if(am&&!am.hidden){acctClose();const ab=$("#acctbtn");if(ab)ab.focus()}}});
// the focus of the week (focus.py: the coach's first axis, kept 7 days); a profile built before it: the first axis
function focusOf(p){const A=p&&p.advice;if(!A)return null;const F=(A.plan||{}).focus;if(F&&F.short)return F;
  const r=(A.rules||[])[0];return r?{id:r.id,title:r.title,short:r.short||r.title,do:(r.do||[]).slice(0,2),drills:(r.drills||[]).slice(0,2),others:(A.rules||[]).slice(1,6).map(x=>({id:x.id,short:x.short||x.title}))}:null}
// your profile in tabs (07/10, the user: "plein de liens différents qui redirigent vers plein de choses"): one row, the
// same on each of its pages, instead of cards that each led somewhere else
const PTABS=[["profile","Overview"],["analysis","Reads"],["midround","Mid-round"],["maps","Maps"],["progress","Weapons & buys"],["routine","Habits"]];
// the Live button as a camera's REC (07/10, the user: "met le bouton live beaucoup plus visible et met le en rouge avec
// un point à côté quand il détecte une game live et qu'il est actif"): red with a blinking dot while Wily follows a match
// (CS2 sends its state, a map is loaded, not the training server), a plain pill otherwise. A peek at the game state every
// 4 s (15 s in a hidden tab) that doesn't count as an open Live page
const LIVEDOT={t:null,on:null};
const liveIs=g=>!!(g&&g.map&&!g.practice&&(g.age==null||g.age<30)&&g.map_phase&&g.map_phase!=="gameover");
function liveDot(){clearTimeout(LIVEDOT.t);if(!D.local)return;const next=()=>{LIVEDOT.t=setTimeout(liveDot,document.hidden?15000:4000)};
  fetch("/api/gsi/state?peek=1").then(r=>r.ok?r.json():null).then(g=>{const on=liveIs(g),a=$('nav a[data-view="ingame"]');
    if(a){if(on!==LIVEDOT.on){LIVEDOT.on=on;a.classList.toggle("rec",on);a.innerHTML=on?`<i class="recdot" aria-hidden="true"></i>LIVE`:"Live"}
      a.title=on?`Your match is live${g.map?` · ${MAPN(g.map)}`:""}${g.round?` · round ${g.round}`:""}: open Live`:"During your match, on a 2nd screen"}
    next()}).catch(next)}
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&D.local)liveDot()});
function navUpdate(view){const g=GROUP[view]||view;
  $$("nav a, .gear").forEach(a=>{if(a.dataset.view===g)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");
    if(D.local&&typeof viewPath==="function"){a.setAttribute("href",viewPath(a.dataset.view));a.dataset.go=a.dataset.view}});   // real addresses (07/10)
  const sn=$("#subnav"),items=SUB[g],inProf=PTABS.some(([k])=>k===view);sn.hidden=!items;
  const hr=k=>D.local&&typeof viewPath==="function"?`href="${viewPath(k)}" data-go="${k}"`:`href="#${k}"`;
  if(items)sn.innerHTML=`<div class="sn-row">${items.map(([k,t])=>`<a ${hr(k)} ${k===view||(k==="profile"&&inProf)?'aria-current="page"':""}>${t}</a>`).join("")}</div>`
    +(inProf?`<div class="sn-row sn-2" aria-label="Your profile">${PTABS.map(([k,t])=>`<a ${hr(k)} ${k===view?'aria-current="page"':""}>${t}</a>`).join("")}</div>`:"");
  // another profile on screen: said by the views, with the way back to yours (yours: the account on the right says it)
  const w=$("#whochip"),p=S.player&&D.players[S.player],other=!!(p&&D.own&&S.player!==D.own);
  const fav=other&&D.local&&favs().includes(S.player);
  w.innerHTML=p&&PLAYER_VIEWS.includes(view)&&(other||!D.local||!D.own)?`${other?"Viewing":"Profile"}: <b>${esc(p.name)}</b>${other&&D.local?` <button type="button" id="favme" class="fav" aria-pressed="${fav}" title="${fav?"In your favorites: click to remove":"Keep in your favorites (your menu, top right)"}">${fav?"★":"☆"}</button>`:""}${other&&IDX()[D.own]?` <button type="button" id="backme" title="Back to my profile">back to mine</button>`:""}`:"";
  const bm=$("#backme");if(bm)bm.onclick=()=>{S.view="review";setPlayer(D.own)};
  const fm=$("#favme");if(fm)fm.onclick=()=>favToggle(S.player);
  acctUpdate();
  document.body.classList.toggle("ingame",view==="ingame")}
function welcome(v){const own=D.own;
  v.innerHTML=`<div class="welcome"><h2>Hi, I'm Wily</h2>
   <p class="lede">I watch your CS2 matches and tell you what wins rounds. I'm with you at three moments:</p>
   <ul style="font-size:15px"><li><b>Live</b>: a sheet to keep on a 2nd screen that follows your match (what to buy, where the Ts are likely to go, your paths, your rotations).</li>
     <li><b>Prepare</b>: before you play, a timed warm-up built on your weak points.</li>
     <li><b>Review</b>: after your session or the next day, what changed, why, your focus of the week and what you could test.</li></ul>
   ${D.local&&own?`<p><button type="button" class="primary" id="w-own">Analyze this PC's Steam account</button></p>`:""}
   <form class="search" id="w-form" autocomplete="off"><input id="w-q" type="search" placeholder="Your Steam profile link or SteamID64" aria-label="Your Steam profile link"><button type="submit">Analyze</button></form>
   <p class="note">${D.local?"I work right here on your PC (Steam open, CS2 closed so I can fetch your latest matches): a first look in seconds, your full profile in a few minutes.":"I run in the local app: double-click Wily.bat."}</p></div>`;
  const wo=$("#w-own",v);if(wo)wo.onclick=()=>{partialShown=null;startAnalysis(own)};
  $("#w-form",v).onsubmit=e=>{e.preventDefault();const q=$("#w-q",v).value.trim();if(!q)return;$("#q").value=q;$("#search").requestSubmit()}}

// the bar's height for what sticks under it (a profile page has a second row)
try{new ResizeObserver(()=>{const b=$(".bar");if(b)document.documentElement.style.setProperty("--bar-h",b.offsetHeight+"px")}).observe($(".bar"))}catch(e){}
