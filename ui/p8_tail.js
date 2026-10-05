
// ---------- data loading (profiles and radars are separate files) ----------
D.players={};D.radars={};D.viewboxes={};
const IDX=()=>Object.fromEntries(D.index.map(e=>[e.steamid,e]));
async function loadRadar(map){if(D.viewboxes[map])return;try{const r=await fetch(`radars/${map}.json`);if(!r.ok)return;const j=await r.json();
  Object.entries(j.levels).forEach(([k,u])=>D.radars[`${map}:${k}`]=u);D.viewboxes[map]=j.viewbox}catch(e){}}
async function loadPlayer(id,force){if(!force&&D.players[id])return D.players[id];
  const r=await fetch(`players/${id}.json`+(force?`?t=${Date.now()}`:""));if(!r.ok)throw new Error("profile not found");
  const p=await r.json();D.players[id]=p;const maps=new Set([...p.matches.map(m=>m.map),...((p.cross||{}).maps||[]).map(m=>m.map)]);
  await Promise.all([...maps].map(loadRadar));return p}

// ---------- view: players ----------
let jq="",jsort="n",jshow=24;   // 24 profiles at a time (the list had 22 screens)
function renderPlayers(){
  const v=$("#v-players");
  const list=D.index.filter(e=>!jq||e.name.toLowerCase().includes(jq)||e.steamid.includes(jq)||(e.archetype||"").toLowerCase().includes(jq)||Object.keys(e.maps||{}).some(m=>MAPN(m).toLowerCase().includes(jq)))
    .sort((a,b)=>(b.steamid===D.own)-(a.steamid===D.own)||(jsort==="n"?b.n-a.n:jsort==="kd"?(b.kd||0)-(a.kd||0):jsort==="adr"?(b.adr||0)-(a.adr||0):(b.last||"").localeCompare(a.last||"")));
  const shown=list.slice(0,jshow);
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${D.index.length} profiles · data built ${fmtDate(D.generated)}</span><h2>Players</h2></div></div>
  <div class="btns" style="align-items:center"><input id="jf" type="search" value="${esc(jq)}" placeholder="Filter by name, SteamID, map or archetype" aria-label="Filter players" style="font:14px var(--f-body);background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:6px 10px;min-width:260px">
    ${[["n","Most demos"],["kd","K/D"],["adr","ADR"],["last","Most recent"]].map(([k,t])=>`<button type="button" data-sort="${k}" aria-pressed="${jsort===k}">${t}</button>`).join("")}</div>
  ${jq?`<p class="note">${list.length} profile${list.length===1?"":"s"} match.</p>`:""}
  <div class="players">${shown.map(e=>`<button type="button" class="pcard" data-pid="${e.steamid}" aria-pressed="${e.steamid===S.player}">
    <b>${esc(e.name)}</b><span class="num note">${e.steamid}${e.rank?` · ${SKILL[e.rank]||""}`:""}</span>${e.archetype?`<span class="arch-tag" style="margin:0">${esc(e.archetype)}</span>`:""}
    <span>${e.minimal?"Minimal profile (public rankings, no demo)":e.light?"Leetify-only profile (no demo)":`${e.n} demo${e.n>1?"s":""} · K/D ${e.kd==null?"—":e.kd} · ADR ${e.adr==null?"—":Math.round(e.adr)} · ${e.record.win}W ${e.record.draw}D ${e.record.loss}L`}</span>
    <span class="note">${Object.entries(e.maps||{}).sort((a,b)=>b[1]-a[1]).slice(0,4).map(([m,n])=>`${MAPN(m)} ${n}`).join(" · ")}</span>
    ${e.top_rule?`<span class="note">Priority: ${esc(e.top_rule)}</span>`:""}</button>`).join("")||`<div class="empty">No player matches.</div>`}</div>
  ${list.length>shown.length?`<div class="btns"><button type="button" id="jmore">Show ${Math.min(24,list.length-shown.length)} more (${list.length-shown.length} left)</button></div>`:""}
  <div class="card"><h3>Analyze any player</h3>
    <p>${D.local?"Paste their Steam profile link, SteamID64 or custom URL name in the search bar at the top: the analysis runs on your PC.":"In the local version (double-click <code>Coach CS2.bat</code>), paste their Steam profile link or SteamID64 in the search bar at the top. This published page can only show players already analyzed."}</p>
    <p class="note">Demo sources: the ones already downloaded, their recent matchmaking matches via Leetify (about a month), their share codes (<code>--sharecode</code>) or their whole history with their authentication code (<code>--authcode</code>). Without demos, a light profile is built from their Leetify stats.</p></div>`;
  const jf=$("#jf",v);jf.oninput=()=>{jq=jf.value.trim().toLowerCase();jshow=24;const pos=jf.selectionStart;renderPlayers();const n=$("#jf");n.focus();n.setSelectionRange(pos,pos)};
  $$("[data-sort]",v).forEach(b=>b.onclick=()=>{jsort=b.dataset.sort;jshow=24;renderPlayers()});
  const jm=$("#jmore",v);if(jm)jm.onclick=()=>{const y=scrollY;jshow+=24;renderPlayers();scrollTo(0,y)};
  $$("[data-pid]",v).forEach(b=>b.onclick=()=>{setPlayer(b.dataset.pid).then(()=>go(b.dataset.pid===D.own?"ingame":"analysis"))});
}

// ---------- view: pros ----------
let PROS=null,pq="",proSel=null;
async function loadPros(){if(PROS)return PROS;try{const r=await fetch("pros.json");PROS=r.ok?await r.json():[]}catch(e){PROS=[]}return PROS}
function proDetail(x){const st=x.stats;const n=(v,s="")=>v==null?"—":String(v)+s;
  return `<article class="card prodetail"><div class="arch-h"><span class="ic" aria-hidden="true">${x.icon}</span><span class="nm">${esc(x.handle)}</span>
    ${x.prole==="igl"?`<span class="probadge">IGL</span>`:""}<span class="note">${esc(x.real_name||"")}${x.team?` · ${esc(x.team)}`:""} · ${esc(x.role_name)}</span>
    <a href="${esc(x.hltv)}" target="_blank" rel="noopener" style="color:var(--ct);font-size:13px">See on HLTV</a></div>
    ${x.traits.length?`<div class="traits">${x.traits.map(t=>`<span title="${esc(t.text)}">${esc(tEN(t.label))}</span>`).join("")}</div>`:""}
    <div class="kv"><div><b>${n(st.kpr)}</b><span>kills per round</span></div><div><b>${n(st.hs,"%")}</b><span>headshot kills</span></div>
      <div><b>${n(st.open_win,"%")}</b><span>opening duels won</span></div><div><b>${n(st.trade_rate)}</b><span>trades per round</span></div>
      <div><b>${n(st.iso_T==null?null:Math.round(st.iso_T)," u")}</b><span>distance to teammate as T</span></div><div><b>${n(st.util_pr)}</b><span>grenades per round</span></div>
      <div><b>${n(st.late_share,"%")}</b><span>kills after 0:55</span></div><div><b>${st.first_duel_t==null?"—":clock(st.first_duel_t)}</b><span>first duel of the round</span></div></div>
    <div><span class="lbl4" style="color:var(--muted)">Weapons (share of kills)</span>
      <div class="wbar">${Object.entries(x.weapons).filter(([k,v])=>v>0).map(([k,v])=>`<i style="width:${v}%;background:${WCOL[k]||"var(--muted)"}" title="${esc(k)} ${v}%"></i>`).join("")}</div>
      <div class="wleg">${Object.entries(x.weapons).filter(([k,v])=>v>0).map(([k,v])=>`<span><b style="background:${WCOL[k]||"var(--muted)"}"></b>${esc(k)} ${v}%</span>`).join("")}</div>
      ${x.top_weapons.length?`<p class="note">Favorites: ${x.top_weapons.slice(0,3).map(w=>`${esc(w.weapon)} (${w.kills})`).join(", ")}</p>`:""}</div>
    <span class="lbl4" style="color:var(--muted)">Zones played per map (${x.maps} map${x.maps>1?"s":""}, ${x.rounds} rounds)</span>
    <div class="zmaps">${Object.entries(x.zones).map(([m,sd])=>`<div><b>${MAPN(m)}</b>${["T","CT"].filter(k=>sd[k]).map(k=>`<br><span class="note">${k}:</span> ${sd[k].map(z=>`${esc(z.zone)} ${z.share}%`).join(" · ")}`).join("")}</div>`).join("")}</div>
  </article>`}
async function renderPros(){const v=$("#v-pros");const ps=await loadPros();
  const list=ps.filter(x=>!pq||[x.handle,x.real_name,x.team,x.role_name].some(t=>(t||"").toLowerCase().includes(pq)));
  const sel=ps.find(x=>x.steamid===proSel);
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${ps.length} pro players analyzed on their recent match demos (HLTV)</span><h2>Pros</h2></div></div>
   ${sel?proDetail(sel):""}
   <div class="btns" style="align-items:center"><input id="pf" type="search" value="${esc(pq)}" placeholder="Filter by handle, name, team or role" aria-label="Filter pros" style="font:14px var(--f-body);background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:6px 10px;min-width:260px"></div>
   <div class="players">${list.map(x=>`<button type="button" class="pcard" data-pro="${x.steamid}" aria-pressed="${x.steamid===proSel}"><b>${esc(x.handle)}${x.prole==="igl"?`<span class="probadge">IGL</span>`:""}</b>
     <span class="note">${esc(x.team||"")}${x.real_name?` · ${esc(x.real_name)}`:""}</span><span class="arch-tag" style="margin:0">${x.icon} ${esc(x.role_name)}</span>
     <span class="note">${x.traits.slice(0,3).map(t=>esc(tEN(t.label))).join(" · ")}</span></button>`).join("")||`<div class="empty">No pro matches.</div>`}</div>
   <p class="note">Pros without a recent demo (team absent from the downloaded matches) don't show up yet. Pros' Steam profiles: public community guides on Steam.</p>`;
  const pf=$("#pf",v);pf.oninput=()=>{pq=pf.value.trim().toLowerCase();const pos=pf.selectionStart;renderPros().then(()=>{const n=$("#pf");n.focus();n.setSelectionRange(pos,pos)})};
  $$("[data-pro]",v).forEach(b=>b.onclick=()=>{proSel=b.dataset.pro;renderPros();window.scrollTo(0,0)});
}
function openPro(sid){proSel=sid;go("pros")}

// ---------- search ----------
function playerOptions(){}
function findKnown(q){const t=q.trim(),low=t.toLowerCase().replace(/\/+$/,"");const id=(t.match(/7656\d{13}/)||[])[0];const I=IDX();if(id)return I[id]?id:null;
  const van=(low.match(/\/id\/([^\/?#]+)/)||[])[1]||(!/[\/:]/.test(low)?low:null);
  for(const e of D.index){if((e.name||"").toLowerCase()===low||(van&&(e.vanity||"").toLowerCase()===van))return e.steamid}
  return null}
function jobPanel(html,cls){const j=$("#job");j.hidden=false;const box=$(".in",j);box.className="in "+(cls||"");box.innerHTML=html+`<div><button type="button" class="close">Close</button></div>`;$(".close",box).onclick=()=>{j.hidden=true}}
// the page only switches player or view for a job you started from here and while you stayed on that view:
// a background sync, or a job finishing while you read something else, never pulls you away
let polling=null,partialShown=null,jobFrom=null;
const mayGo=()=>jobFrom!==null&&S.view===jobFrom;
const openBtn=(sid,name,view)=>`<div class="btns"><button type="button" data-open="${sid}" data-view="${view}">Open ${esc(name||"the profile")}</button></div>`;
function bindOpen(){$$("[data-open]",$("#job")).forEach(b=>b.onclick=async()=>{delete D.players[b.dataset.open];await setPlayer(b.dataset.open,true);go(b.dataset.view)})}
async function startAnalysis(q,after){
  jobFrom=S.view;afterJob=after||null;   // after: what to open once done (the match of a /match/ address)
  $("#qbtn").disabled=true;
  try{const r=await fetch("/api/analyze?q="+encodeURIComponent(q));const j=await r.json();
    if(!r.ok){jobPanel(`<b>${esc(j.error||"Error")}</b>${j.query?` (${esc(j.query)})`:""}`,"err");$("#qbtn").disabled=false;if(r.status===409)poll();return}
    poll()}catch(e){jobPanel(`<b>The local server doesn't answer.</b> Restart "Coach CS2.bat".`,"err");$("#qbtn").disabled=false}}
function poll(){clearTimeout(polling);polling=setTimeout(async()=>{
  let j;try{j=await (await fetch("/api/job")).json()}catch(e){return poll()}
  const logs=(j.log||[]).slice(-60).map(esc).join("\n");
  if(j.running){
    if(j.partial&&partialShown!==j.partial&&mayGo()){partialShown=j.partial;try{D.index=await (await fetch(`index.json?t=${Date.now()}`)).json();playerOptions();delete D.players[j.partial];await setPlayer(j.partial,true);go(j.partial===D.own?"ingame":"analysis");jobFrom=S.view}catch(e){}}
    jobPanel(`<div class="row"><b><span class="spin" aria-hidden="true"></span>${partialShown?"First preview shown. Full demo analysis running…":j.view==="matches"?"Analyzing the match again…":/^Steam sync/.test(j.query||"")?"Updating your matches…":`Analyzing ${esc(j.query)}…`}</b><span class="note">The profile completes itself at the end (from a few seconds to a few minutes).</span></div><pre>${logs||"Starting…"}</pre>`);poll();return}
  $("#qbtn").disabled=false;const go_=mayGo(),aj=afterJob;jobFrom=null;afterJob=null;
  if(j.error){updFrom=null;const ub=$("#updbtn");if(ub)ub.disabled=false;jobPanel(`<b>${esc(j.error)}</b><pre>${logs}</pre>`,"err");return}
  if(j.players&&j.players.length){D.index=await (await fetch(`index.json?t=${Date.now()}`)).json();playerOptions();
    const nm=((j.query||"").match(/CSGO(-[\w]{5}){5}/g)||[]).length,ps=[...j.players].sort((a,b)=>(b.steamid===D.own)-(a.steamid===D.own)),
      btn=p=>`<button type="button" data-mp="${p.steamid}">${esc(p.name)}</button>`;
    jobPanel(`<b>${j.players.length} players analyzed${nm>1?` in these ${nm} matches`:" in this match"}.</b><div class="btns">${ps.slice(0,10).map(btn).join("")}</div>
      ${ps.length>10?`<details><summary style="cursor:pointer" class="note">The other ${ps.length-10} players</summary><div class="btns">${ps.slice(10).map(btn).join("")}</div></details>`:""}<pre>${logs}</pre>`,"ok");
    $$("[data-mp]",$("#job")).forEach(b=>b.onclick=()=>{delete D.players[b.dataset.mp];setPlayer(b.dataset.mp,true).then(()=>go("analysis"))});
    if(aj&&go_)aj();return}
  if(j.steamid&&j.view==="matches"){try{D.index=await (await fetch(`index.json?t=${Date.now()}`)).json();playerOptions();delete D.players[j.steamid];   // a re-analysis: back on that match
      if(go_){await setPlayer(j.steamid,true);const i=P().matches.findIndex(x=>x.id===j.match);S.match=i<0?0:i;S.mpin=i>=0;go("matches")}
      jobPanel(`<b>The match is analyzed again.</b> Profile, plan and in-game sheet updated.${go_?"":openBtn(j.steamid,null,"matches")}<pre>${logs}</pre>`,"ok");bindOpen()}
    catch(e){jobPanel(`<b>The match could not be shown.</b><pre>${logs}</pre>`,"err")}return}
  if(j.steamid){try{D.index=await (await fetch(`index.json?t=${Date.now()}`)).json();playerOptions();delete D.players[j.steamid];
      const upd=updFrom;updFrom=null;const ub=$("#updbtn");if(ub)ub.disabled=false;
      if(upd&&/(^|\D)0 new match/.test((j.log||[]).slice(-3).join(" "))&&!(j.log||[]).some(l=>/demo\(s\) from Valve|Analyzing/.test(l))){if(S.player===j.steamid)await setPlayer(j.steamid,true);go(upd);jobPanel(`<b>Up to date</b>: no new match since the last analysis.`,"ok");return}
      const e=(D.index||[]).find(x=>x.steamid===j.steamid)||{},view=upd||(j.steamid===D.own?"ingame":"analysis");
      if(go_){await setPlayer(j.steamid,true);S.map=null}
      jobPanel(`<b>${esc(e.name||j.steamid)} is analyzed.</b> ${e.light?"Light profile (Leetify stats, no demo available).":e.n!=null?`${e.n} demo(s) analyzed.`:""}${go_?"":openBtn(j.steamid,e.name,view)}<pre>${logs}</pre>`,"ok");bindOpen();if(go_)go(view)}
    catch(e){jobPanel(`<b>Nothing to show for this player.</b><pre>${logs}</pre>`,"err")}}},1000)}
$("#search").addEventListener("submit",async e=>{e.preventDefault();const q=$("#q").value.trim();if(!q)return;
  const ps=await loadPros(),ql=q.toLowerCase(),idm=(q.match(/7656\d{13}/)||[])[0];
  const pro=ps.find(x=>x.handle.toLowerCase()===ql||x.steamid===idm);
  if(pro){$("#q").value="";$("#job").hidden=true;openPro(pro.steamid);return}
  const known=findKnown(q);
  if(known){await setPlayer(known);$("#job").hidden=true;$("#q").value="";go(S.view==="players"?"ingame":S.view);
    if(D.local){jobPanel(`<b>${esc(P().name)} is already analyzed.</b> To fetch their new matches: <button type="button" class="close" id="refresh">Update</button>`,"ok");$("#refresh").onclick=()=>startAnalysis(q)}
    return}
  if(D.local){partialShown=null;startAnalysis(q);return}
  const local=`http://127.0.0.1:8765/?q=${encodeURIComponent(q)}#ingame`;
  jobPanel(`<b>This player isn't in this page yet.</b><p>The analysis runs on your PC. Click below: the local app opens in a new tab and starts the analysis right away (a first preview in seconds, the full profile in a few minutes).</p>
    <p><a href="${esc(local)}" target="_blank" rel="noopener" style="display:inline-block;font:600 15px var(--f-body);padding:8px 14px;background:var(--ink);color:var(--bg);border-radius:3px;text-decoration:none">Analyze on my PC</a></p>
    <p class="note">The local app must be running: double-click <code>Coach CS2.bat</code> in the app folder, or turn on its automatic start with <code>autostart.bat</code>.</p>`)});

// ---------- routing ----------
const RENDER={ingame:renderIngame,prepare:renderPrepare,review:renderReview,profile:renderProfile,analysis:renderAnalysis,routine:renderRoutine,midround:renderMidround,progress:renderProgress,team:renderTeam,matches:renderMatches,maps:renderMaps,players:renderPlayers,pros:renderPros,settings:renderSettings};
// The local app has addresses like csrep's: /player/<steamid> (their first view: In game for you, Analysis for the others),
// /player/<steamid>/<view>, /match/<share code, or match id when it has none>[?as=<steamid>: seen as someone else than
// you], /team, /players, /pros, /settings; old links (/#review) still open. The published page (one file) keeps #view.
const GLOBAL=["team","players","pros","settings"],homeView=sid=>sid&&sid===D.own?"ingame":"profile";
let navAt=0,navQuiet=0,afterJob=null,CODES={};   // CODES: match id -> share code
// /live: your In game page, the address to keep open during a match (a second screen, OBS) (04/10)
function pathNow(){const v=S.view;if(GLOBAL.includes(v))return "/"+v;if(!S.player)return "/";if(v==="ingame"&&S.player===D.own)return "/live";
  if((v==="prepare"||v==="review")&&S.player===D.own)return "/"+v;   // your three moments: /live, /prepare, /review
  const m=v==="matches"&&S.mpin&&P()?P().matches[S.match]:null;
  return m?`/match/${CODES[m.id]||m.id}${S.player!==D.own?"?as="+S.player:""}`:`/player/${S.player}${v===homeView(S.player)?"":"/"+v}`}
// the address of what is on screen: a new history entry for each move of yours (back works), the same entry for the
// steps of one move (a profile loading, then its view) and when the address itself led here
function syncUrl(){
  if(!D.local){if(location.hash.slice(1)!==S.view)history.replaceState(null,"",location.pathname+location.search+"#"+S.view);return}
  let u=pathNow();
  if(navQuiet){const k=[...new URLSearchParams(location.search)].filter(([n])=>n!=="as"&&n!=="q");if(k.length)u+=(u.includes("?")?"&":"?")+new URLSearchParams(k)}   // ?steam=… (back from Steam) stays for its page
  if(location.pathname+location.search+location.hash===u)return;
  const now=Date.now();if(navQuiet||now-navAt<500)history.replaceState(null,"",u);else{history.pushState(null,"",u);navAt=now}}
function defPlayer(){const sp=store("player");return sp&&IDX()[sp]?sp:(D.own&&IDX()[D.own]?D.own:(D.local&&D.own?null:(D.default||(D.index[0]||{}).steamid||null)))}
// the address -> what to show
async function route(){
  const path=location.pathname.replace(/\/+$/,"")||"/",as=new URLSearchParams(location.search).get("as");
  const h=ALIAS[location.hash.slice(1)]||location.hash.slice(1),hv=RENDER[h]?h:null;   // an old link (/#review), or a #view link opened in a new tab
  let m;
  if((m=path.match(/^\/match\/([A-Za-z0-9-]+)$/)))return openMatch(m[1],as);
  if((m=path.match(/^\/player\/(\d{17})(?:\/([a-z]+))?$/))){const sid=m[1],v=ALIAS[m[2]]||m[2];
    if(!IDX()[sid])return notYet(`This player (SteamID ${sid}) isn't analyzed yet.`,sid);
    S.view=hv||(RENDER[v]&&!GLOBAL.includes(v)?v:homeView(sid));return setPlayer(sid)}
  if(path==="/live"&&D.own&&IDX()[D.own]){S.view="ingame";return setPlayer(D.own)}
  if((path==="/prepare"||path==="/review")&&D.own&&IDX()[D.own]){S.view=hv||path.slice(1);return setPlayer(D.own)}
  m=path.match(/^\/([a-z]+)$/);const g=m&&(ALIAS[m[1]]||m[1]),p=defPlayer();
  S.view=hv||(GLOBAL.includes(g)?g:homeView(p));return setPlayer(p)}
// /match/<id or share code>: that match, seen as the player of the address (?as=), else you, else an analyzed player in it
async function openMatch(code,as){
  let j=null;try{const r=await fetch("/api/match?code="+encodeURIComponent(code));if(r.ok)j=await r.json()}catch(e){}
  if(!j)return notYet(`No match at this address: a share code (CSGO-…) or a match id goes after /match/.`);
  if(j.code)CODES[j.id]=j.code;
  for(const sid of [...new Set([as,D.own,...j.players])].filter(x=>x&&IDX()[x]&&(x===as||j.players.includes(x)))){
    S.view="matches";await setPlayer(sid);const i=((P()||{}).matches||[]).findIndex(x=>x.id===j.id);
    if(i>=0){S.match=i;S.mpin=true;show("matches");return}}
  const what=esc([j.map?MAPN(j.map):null,j.time?fmtDate(j.time):null].filter(Boolean).join(" · ")||"match "+j.id);
  if(j.code)return notYet(j.analyzed?`No analyzed profile shows this match yet (${what}).`:`This match (${what}) isn't analyzed yet.`,j.code,()=>openMatch(j.id,as));
  notYet(`This match (${what}) isn't analyzed: paste its share code (CSGO-…) in the search, or open /match/ with it.`)}
// an address of a player or match the app doesn't show yet: said, and one click analyzes it
function notYet(msg,q,after){
  if(!S.player){const d=defPlayer();if(d){S.player=d;loadPlayer(d).catch(()=>{})}}   // the menus keep working
  if(!RENDER[S.view]||GLOBAL.includes(S.view))S.view=homeView(S.player);
  const v=$("#v-"+S.view);$$("main>.view").forEach(x=>x.hidden=x!==v);navUpdate(S.view);
  v.innerHTML=`<div class="empty">${msg}${q&&D.local?`<div class="btns" style="justify-content:center;margin-top:12px"><button type="button" id="nyet">Analyze it</button></div>`:""}</div>`;
  const b=$("#nyet",v);if(b)b.onclick=()=>{b.disabled=true;partialShown=null;startAnalysis(q,after)}}
function go(view){view=ALIAS[view]||view;if(!D.local&&location.hash!=="#"+view)history.replaceState(null,"",location.pathname+location.search+"#"+view);show(view)}
function show(view){view=ALIAS[view]||view;if(!RENDER[view])view="ingame";if(view!=="ingame")document.body.classList.remove("igfull");
  S.view=view;$$("main>.view").forEach(x=>x.hidden=x.id!=="v-"+view);
  if(!D.local||GLOBAL.includes(view)||!S.player||D.players[S.player])syncUrl();   // a profile still loading: its address once it is in
  navUpdate(view);if(view!=="ingame")clearTimeout(gsiTimer);
  if(view==="players"){renderPlayers();return}
  if(view==="pros"){renderPros();window.scrollTo(0,0);return}
  if(view==="settings"){renderSettings();window.scrollTo(0,0);return}
  if(view==="team"){renderTeam();window.scrollTo(0,0);return}
  if(!S.player){if(view==="ingame"||view==="review")welcome($("#v-"+view));else $("#v-"+view).innerHTML=`<div class="empty">Pick a profile first: yours from the home page, or anyone in Explore.</div>`;return}
  if(!D.players[S.player]){$("#v-"+view).innerHTML=`<div class="empty"><span class="spin" aria-hidden="true"></span>Loading the profile…</div>`;return}
  RENDER[view]();navUpdate(view);window.scrollTo(0,0);
  if(view==="prepare"&&D.local)prepWatch();   // CS2 loads a map: Live takes over
  if(view==="ingame"&&D.local){if(!gsiStatus)fetch("/api/gsi/status").then(r=>r.json()).then(j=>{gsiStatus=j;if(S.view==="ingame"&&D.players[S.player])renderIngame()}).catch(()=>{});gsiPoll()}}
async function setPlayer(id,force){S.player=id;store("player",id);S.match=0;S.mpin=false;if(!id){show(S.view);return}
  if(!D.players[id]||force){show(S.view);try{await loadPlayer(id,force)}catch(e){$("#v-"+S.view).innerHTML=`<div class="empty">Couldn't load this profile (${esc(e.message)}).</div>`;return}}
  show(S.view)}
S.map=HOST(store("map"))?null:store("map");S.side=store("side")||"T";
// a #view link: that view, at its address (the same history entry); back and forward: what their address says
window.addEventListener("hashchange",()=>{const h=location.hash.slice(1),v=ALIAS[h]||h;if(!D.local)return show(h);if(!RENDER[v])return;navQuiet++;try{show(v)}finally{navQuiet--}});
window.addEventListener("popstate",()=>{const h=location.hash.slice(1);if(!D.local||RENDER[ALIAS[h]||h])return;navQuiet++;route().finally(()=>navQuiet--)});
S.view=ALIAS[location.hash.slice(1)]||location.hash.slice(1)||"ingame";if(!RENDER[S.view])S.view="ingame";
if(store("focus"))document.body.classList.add("focus");
// Update: your new matches fetched and analyzed (the same as the automatic sync, now)
let updFrom=null;
{const ub=$("#updbtn");if(ub&&D.local&&D.own){ub.hidden=false;
  ub.onclick=async()=>{ub.disabled=true;updFrom=S.view;jobFrom=S.view;
    try{await api("/api/steam/sync",{sid:D.own});poll()}
    catch(e){if(/already running/i.test(e.message||""))poll();else{ub.disabled=false;updFrom=null;jobPanel(`<b>${esc(e.message||"Update impossible")}</b>`,"err")}}}}}
if(D.local){navQuiet++;route().finally(()=>navQuiet--);
  fetch("/api/codes").then(r=>r.json()).then(c=>{CODES={...c,...CODES};if(S.view==="matches"&&S.mpin){navQuiet++;try{syncUrl()}finally{navQuiet--}}}).catch(()=>{})}
else setPlayer(defPlayer());
if(D.local){
  const q0=new URLSearchParams(location.search).get("q");
  if(q0){history.replaceState(null,"",location.pathname+location.hash);$("#q").value=q0;$("#search").requestSubmit()}
  else fetch("/api/job").then(r=>r.json()).then(j=>{if(j.running)poll()}).catch(()=>{});
}
