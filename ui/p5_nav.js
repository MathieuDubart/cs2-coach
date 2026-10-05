
// ---------- navigation: three moments (05/10): Live during the match, Prepare before it, Review after it ----------
const GROUP={ingame:"ingame",prepare:"prepare",review:"review",profile:"review",matches:"review",maps:"review",midround:"review",progress:"review",analysis:"review",routine:"review",team:"players",players:"players",pros:"players",settings:"settings"};
// Review in three levels (05/10): the session, your profile, every match; the detailed pages open from the profile
const SUB={review:[["review","Session"],["profile","Profile"],["matches","Matches"]],players:[["players","Players"],["pros","Pros"],["team","Team"]]};
const PLAYER_VIEWS=["ingame","prepare","review","profile","matches","maps","midround","progress","analysis","routine"];
// old French addresses keep working, and the moments' names
const ALIAS={partie:"ingame",avant:"prepare",bilan:"review",matchs:"matches",cartes:"maps",mid:"midround",prog:"progress",synthese:"analysis",equipe:"team",joueurs:"players",steam:"settings",live:"ingame",prep:"prepare",warmup:"prepare"};
// your account on the right of the bar, like a signed-in account (05/10): your Steam avatar and name, and a menu
let ACCT=null;   // your Steam avatar when the profile has none (/api/account: the public profile, kept a day)
function acctUpdate(){const ac=$("#acct"),ab=$("#acctbtn"),am=$("#acctmenu"),mi=D.own&&IDX()[D.own];if(!ac)return;
  ac.hidden=!(D.local&&mi);if(ac.hidden)return;
  const me=D.players[D.own],av=(me&&((me.advice||{}).steam||{}).avatar)||mi.avatar||(ACCT&&ACCT.avatar),nm=(me&&me.name)||mi.name||"You";
  if(!av&&ACCT===null){ACCT={};fetch("/api/account").then(r=>r.json()).then(j=>{ACCT=j||{};if(ACCT.avatar)acctUpdate()}).catch(()=>{})}
  ab.innerHTML=`${av?`<img class="av" src="${esc(av)}" alt="" width="26" height="26">`:`<span class="av ini" aria-hidden="true">${esc(String(nm).trim().charAt(0).toUpperCase())}</span>`}<span class="an">${esc(nm)}</span><span class="caret" aria-hidden="true">▾</span>`;
  ab.title=`Your account: ${nm}`;ab.setAttribute("aria-label",`Your account: ${nm}`);
  const im=$("img.av",ab);if(im)im.onerror=()=>{const sp=document.createElement("span");sp.className="av ini";sp.setAttribute("aria-hidden","true");sp.textContent=String(nm).trim().charAt(0).toUpperCase();im.replaceWith(sp)};   // an avatar that doesn't load: your initial
  am.innerHTML=`<a href="#profile" role="menuitem" data-acct="profile">Your profile</a><a href="#review" role="menuitem" data-acct="review">Your last session</a><a href="#prepare" role="menuitem" data-acct="prepare">Prepare your next game</a><a href="#settings" role="menuitem" data-acct="settings">Steam account and settings</a>`;
  ab.onclick=e=>{e.stopPropagation();const open=am.hidden;am.hidden=!open;ab.setAttribute("aria-expanded",String(open));if(open){const f=$("a",am);if(f)f.focus()}};
  $$("[data-acct]",am).forEach(a=>a.onclick=e=>{e.preventDefault();acctClose();const v=a.dataset.acct;
    if(v==="settings")go("settings");else if(S.player!==D.own){S.view=v;setPlayer(D.own)}else go(v)})}
function acctClose(){const am=$("#acctmenu"),ab=$("#acctbtn");if(am&&!am.hidden){am.hidden=true;if(ab)ab.setAttribute("aria-expanded","false")}}
document.addEventListener("click",e=>{if(!e.target.closest||!e.target.closest("#acct"))acctClose()});
document.addEventListener("keydown",e=>{if(e.key==="Escape"){const am=$("#acctmenu");if(am&&!am.hidden){acctClose();const ab=$("#acctbtn");if(ab)ab.focus()}}});
// the focus of the week (focus.py: the coach's first axis, kept 7 days); a profile built before it: the first axis
function focusOf(p){const A=p&&p.advice;if(!A)return null;const F=(A.plan||{}).focus;if(F&&F.short)return F;
  const r=(A.rules||[])[0];return r?{id:r.id,title:r.title,short:r.short||r.title,do:(r.do||[]).slice(0,2),drills:(r.drills||[]).slice(0,2),others:(A.rules||[]).slice(1,6).map(x=>({id:x.id,short:x.short||x.title}))}:null}
function navUpdate(view){const g=GROUP[view]||view;
  $$("nav a, .gear").forEach(a=>{if(a.dataset.view===g)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current")});
  const sn=$("#subnav"),items=SUB[g];sn.hidden=!items;
  if(items)sn.innerHTML=[...items,...(items.some(([k])=>k===view)||!VIEW_LABEL[view]?[]:[[view,VIEW_LABEL[view]]])]   // a detailed page: shown while open
    .map(([k,t])=>`<a href="#${k}" ${k===view?'aria-current="page"':""}>${t}</a>`).join("");
  // another profile on screen: said by the views, with the way back to yours (yours: the account on the right says it)
  const w=$("#whochip"),p=S.player&&D.players[S.player],other=!!(p&&D.own&&S.player!==D.own);
  w.innerHTML=p&&PLAYER_VIEWS.includes(view)&&(other||!D.local||!D.own)?`${other?"Viewing":"Profile"}: <b>${esc(p.name)}</b>${other&&IDX()[D.own]?` <button type="button" id="backme" title="Back to my profile">back to mine</button>`:""}`:"";
  const bm=$("#backme");if(bm)bm.onclick=()=>setPlayer(D.own);
  acctUpdate();
  const fc=$("#focuschip"),me=D.own&&D.players[D.own],F=me?focusOf(me):null;   // yours, whatever profile is on screen
  if(fc){fc.hidden=!F;if(F){fc.textContent="Focus · "+F.short;fc.title="Your focus of the week: see it in Review";fc.onclick=()=>{if(S.player!==D.own){S.view="review";setPlayer(D.own)}else go("review")}}}
  document.body.classList.toggle("ingame",view==="ingame")}
function welcome(v){const own=D.own;
  v.innerHTML=`<div class="welcome"><h2>Hi, I'm Wily</h2>
   <p class="lede">I watch your CS2 matches and tell you what wins rounds. I'm with you at three moments:</p>
   <ul style="font-size:15px"><li><b>Live</b>: a sheet to keep on a 2nd screen that follows your match (what to buy, where the Ts are likely to go, your paths, your rotations).</li>
     <li><b>Prepare</b>: before you play, a timed warm-up built on your weak points and a 60-second sheet for each map.</li>
     <li><b>Review</b>: after your session or the next day, what changed, why, your focus of the week and what you could test.</li></ul>
   ${D.local&&own?`<p><button type="button" class="primary" id="w-own">Analyze this PC's Steam account</button></p>`:""}
   <form class="search" id="w-form" autocomplete="off"><input id="w-q" type="search" placeholder="Your Steam profile link or SteamID64" aria-label="Your Steam profile link"><button type="submit">Analyze</button></form>
   <p class="note">${D.local?"I work right here on your PC (Steam open, CS2 closed so I can fetch your latest matches): a first look in seconds, your full profile in a few minutes.":"I run in the local app: double-click Wily.bat."} You can also look at any player in <a href="#players" style="color:var(--ct)">Explore</a>.</p></div>`;
  const wo=$("#w-own",v);if(wo)wo.onclick=()=>{partialShown=null;startAnalysis(own)};
  $("#w-form",v).onsubmit=e=>{e.preventDefault();const q=$("#w-q",v).value.trim();if(!q)return;$("#q").value=q;$("#search").requestSubmit()}}
