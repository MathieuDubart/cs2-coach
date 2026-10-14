// ---------- view: prepare (05/10, reworked 06/10): before you play. Your maps and a duration (5, 10, 20 or 30 min),
// then ONE warm-up on the training server (06/10, the user: "tout l'entraînement sur le même serveur comme avant, le
// bouton warmup pour tout lancer: de l'aim, de la défense de bomb site, du chemin de prefire, du stuff, du wallbang"):
// one button starts the server, builds the session in that order on your maps and sends the game there; the page
// follows it live. One page (07/10, the user on the map sheets, the lineup photos and the Ready step: "tout ça ne sert
// à rien", then "plus besoin de faire 2 steps, tu peux tout mettre sur la même page"): your maps, where you lose rounds
// lately, the warm-up of those maps right under them; when CS2 loads a map, Live takes over ----------
const PREP_LEN=[5,10,15,20,30,45];   // the warm-up card's durations: its plan follows the one you pick, live (07/10)
// pend: a start or a stop on its way, note: its outcome for 30 s; both outlive the card's refreshes (08/10: the 4 s
// refresh wiped "Starting the server…", he clicked Stop, reloaded, clicked again)
const PREP={tick:null,watch:null,warm:null,sec:null,pend:null,note:null,base:null,cnt:null};   // base: the maps the base covers (09/10); cnt: a focus block's drills per module
// the focus block (13/10, the user: "pouvoir jouer intensivement certains blocs, 10 min de stuff only, 10 min de défense de
// bombsite only"): one module for the whole time on one map, its durations, what each module is
const PREP_BLOCK=[10,15,20];
const FOCUS_DESC={crossfire:tl("real duels: hold an angle, peek, one spray for two"),defend:tl("hold a bombsite against the real hits, wave after wave"),
  push:tl("the push routes with their prefire angles"),nade:tl("your lineups: guided, then on your own"),wallbang:tl("the wallbangs and boosts that kill there"),
  situation:tl("your own rounds again, where they went wrong")};
const WBLOCK={aim:"🎯 "+tl("Aim"),crossfire:"🎯 Crossfire",defend:"🛡 "+tl("Defense"),push:"🚶 "+tl("Prefire"),nade:"💨 "+tl("Utility"),wallbang:"🧱 "+tl("Wallbang"),situation:"🔁 "+tl("Situations")};
// what you chose today (your browser): the maps, the duration, the blocks done, the one running
function prepState(){const day=new Date().toDateString();let st=store("prep");
  if(!st||st.day!==day)st={day,maps:[],min:20,done:{},cur:null,t0:null,mode:st&&st.mode,focus:st&&st.focus,bmin:st&&st.bmin};   // the warm-up's type kept from day to day
  st.mode=st.mode==="block"?"block":"full";st.bmin=PREP_BLOCK.includes(st.bmin)?st.bmin:10;return st}
function prepSave(st){store("prep",st)}
// your focus of the week: changed from Review or Profile (focus.py)
function wireFocus(v,p,rerender){const sel=$("[data-focus-pick]",v);if(!sel)return;
  sel.onchange=async()=>{const id=sel.value;if(!id)return;sel.disabled=true;
    try{const j=await api("/api/focus",{sid:p.steamid,id});const A=p.advice;A.plan=A.plan||{};A.plan.focus=j.focus;navUpdate(S.view);rerender()}
    catch(e){sel.disabled=false;sel.insertAdjacentHTML("afterend",` <span class="note">${esc(e.message)}</span>`)}}}
function renderPrepare(){
  const p=P(),v=$("#v-prepare"),PL=p.advice.plan;if(!PL)return noPlan(v);
  clearTimeout(PREP.warm);
  const st=prepState(),own=D.local&&p.steamid===D.own,maps=mapsOf(p);
  // 09/10, his warm-up: "trainer les maps sur lesquelles je n'ai pas de démo téléchargée, puisque j'ai le dataset des
  // matchs": the base's other bomb maps, trained on its own spots and lineups (no situations: they come from your demos)
  if(own&&PREP.base===null){PREP.base=[];fetch("/api/train/maps").then(r=>r.ok?r.json():null).then(j=>{PREP.base=(j&&j.maps)||[];if(S.view==="prepare"&&PREP.base.length)renderPrepare()}).catch(()=>{})}
  const extra=own?(PREP.base||[]).filter(m=>!maps.some(x=>x.map===m.map)):[];
  const okMap=m=>maps.some(x=>x.map===m)||extra.some(x=>x.map===m);
  const full=(st.maps||[]).filter(okMap).slice(0,3),block=own&&st.mode==="block";
  // a focus block: one map (its own pick, else the first of the session's)
  const sel=block?[okMap(st.bmap)?st.bmap:full[0]].filter(Boolean):full;
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)} · ${tl("before you play")}</span><h2>${tl("Prepare")}</h2></div></div>
   ${own?`<div class="prep-mode"><div class="btns" role="group" aria-label="${tl("Warm-up type")}"><button type="button" data-pmode="full" aria-pressed="${!block}">🧩 ${tl("Full session")}</button><button type="button" data-pmode="block" aria-pressed="${block}">🎯 ${tl("Focus block")}</button></div>
     <p class="note">${block?tl("One module only, 10 to 20 minutes on one map: its drills back to back."):tl("A bit of everything on one to three maps, the time shared out for you.")}</p></div>`:""}
   <section class="prep1">
    <h3>${block?tl("Which map?"):tl("Which maps?")}</h3><p class="note">${block?tl("One map for the block."):tl("One to three: the warm-up follows them. Your most played first.")}</p>
    <div class="btns prep-maps" role="group" aria-label="${tl("Maps")}">${maps.map(m=>`<button type="button" data-pmap="${esc(m.map)}" aria-pressed="${sel.includes(m.map)}">${esc(MAPN(m.map))} <span class="note">${m.n||0}</span></button>`).join("")}</div>
    ${extra.length?`<p class="note">${tl("Maps you have no match of: trained on the base's spots and lineups (no situations).")}</p><div class="btns prep-maps" role="group" aria-label="${tl("Other maps")}">${extra.map(m=>`<button type="button" data-pmap="${esc(m.map)}" aria-pressed="${sel.includes(m.map)}">${esc(MAPN(m.map))}</button>`).join("")}</div>`:""}
    ${own?`<div class="pstrug" data-pstrug></div>`:""}</section>
   <section class="prep2">${!sel.length?`<p class="note">${tl("Pick a map: the warm-up builds itself here.")}</p>`
     :`<article class="card pwarm" data-pwarm>${own?`<p class="note"><span class="spin" aria-hidden="true"></span>${tl("Preparing your warm-up…")}</p>`:`<p class="note">${tl("The warm-up runs on the training server, from the local app (double-click <code>Wily.bat</code>).")}</p>`}</article>`}</section>`;   // no pre-session journal here either (07/10: "tu peux aussi enlever ça")
  $$("[data-pmap]",v).forEach(b=>b.onclick=()=>{const m=b.dataset.pmap;
    if(block){st.bmap=m;prepSave(st);renderPrepare();return}   // a focus block: that map
    const i=sel.indexOf(m);if(i>=0)sel.splice(i,1);else if(sel.length<3)sel.push(m);else return;
    st.maps=sel.slice();prepSave(st);renderPrepare()});   // another map: the warm-up redone under it
  $$("[data-pmode]",v).forEach(b=>b.onclick=()=>{st.mode=b.dataset.pmode;prepSave(st);renderPrepare()});
  prepStruggles(v,p);
  if(sel.length&&own)prepWarm(v,p,sel,st)}
// the warm-up's card: what the session will be (each part's minutes, your priorities), the bots' level, ONE button that
// starts the server, builds the session and sends the game, then the session live (part, drill, points, time left)
async function prepWarm(v,p,sel,st){const box=$("[data-pwarm]",v);if(!box||!D.local)return;clearTimeout(PREP.warm);
  const get=u=>fetch(u).then(r=>r.ok?r.json():null).catch(()=>null),where=sel.join(",");
  const block=st.mode==="block",mins=block?st.bmin:st.min,focus=block?(FOCUS_DESC[st.focus]?st.focus:"crossfire"):null;   // a focus block: one module, 10 to 20 min
  const [d,pv]=await Promise.all([get("/api/train?sid="+p.steamid),get(`/api/train/preview?sid=${p.steamid}&minutes=${mins}&where=${encodeURIComponent(where)}${focus?`&focus=${focus}`:""}`)]);
  if(!box.isConnected||S.view!=="prepare")return;
  if(!d){box.innerHTML=`<p class="note">${tl("The local server doesn't answer.")}</p>`;return}
  const T=d.status||{},Pg=d.progress||{level:1,xp:0,from:0,to:300},ss=T.session,Mo=(pv&&pv.modules)||[];
  if(focus&&Mo.length&&!Mo.some(m=>m.kind===focus&&m.ok)){const f=Mo.find(m=>m.ok);if(f){st.focus=f.kind;prepSave(st);return prepWarm(v,p,sel,st)}}   // nothing of it on that map: the first module that has
  if(!T.installed){trainInstall(box,p.steamid,T,()=>prepWarm(v,p,sel,st));if((T.install||{}).running)PREP.warm=setTimeout(()=>prepWarm(v,p,sel,st),2500);return}
  // the aim first, on the game's aim map (06/10), then your maps
  const B=(pv&&pv.blocks)||[],byMap=[...new Set([...B.filter(x=>!sel.includes(x.map)).map(x=>x.map),...sel])].map(mp=>({mp,b:B.filter(x=>x.map===mp)})).filter(x=>x.b.length);
  const sug=Pg.suggest||null,chose=Date.now()-(+tPref("at","0"))<12*3600e3,df=sug&&!chose?sug.diff:trainDiff(),pct=Math.max(0,Math.min(100,100*(Pg.xp-Pg.from)/Math.max(1,Pg.to-Pg.from)));
  const running=ss&&T.running,pend=PREP.pend,wait=!!(pend||T.busy);   // T.busy: a start the server side runs (a reload meanwhile)
  const say=pend?`${pend.text} (${Math.round((Date.now()-pend.t0)/1e3)} s)`:T.busy?tl("{what} is starting on the training server…",{what:T.busy.charAt(0).toUpperCase()+T.busy.slice(1)})
    :PREP.note&&Date.now()-PREP.note.t<30e3?PREP.note.text:T.dead?tl("The training server stopped answering: ▶ WARM-UP starts it again."):"";
  // the last session's recap (13/10, a focus block's "bilan": what worked, its measures, what comes back next time)
  const L=Pg.last,when=L&&L.t?new Date(L.t*1e3).toLocaleString(LOC,{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}):"";
  const recap=!running&&L&&L.n?`<details class="plast"><summary><b>${tl("Last warm-up")}</b> · ${esc(when)} · ${L.focus?`${WBLOCK[L.focus]||esc(L.focus)} ${L.minutes}′`:tl("{n} min",{n:L.minutes})} · ${esc((L.maps||[]).map(MAPN).join(", "))} · ${L.ok}/${L.n} ✔${L.points?` · ⭐ ${L.points}`:""}${L.again?` · 🔁 ${tln(L.again,"{n} comes back next time","{n} come back next time")}`:""}</summary>
    <ul class="plast-l">${L.drills.map(x=>`<li class="${x.ok?"ok":"ko"}"><b>${x.ok?"✔":"✘"} ${esc(x.title)}</b>${x.detail?` <span class="note">${esc(x.detail)}</span>`:""}</li>`).join("")}</ul>
    ${L.again?`<p class="note">${tl("The missed ones come first next time you train these maps.")}</p>`:""}</details>`:"";
  // a focus block's modules: one tile each, its drills on that map counted after (a map's first count takes a few seconds)
  const tiles=focus&&!running?`<div class="pfocus" role="group" aria-label="${tl("Module")}">${Mo.map(m=>`<button type="button" data-pfocus="${m.kind}" aria-pressed="${m.kind===focus}"${m.ok?"":" disabled"}><b>${WBLOCK[m.kind]||m.kind}</b><span>${esc(m.ok?(m.note||FOCUS_DESC[m.kind]||""):(m.why||""))}</span><small data-pfn="${m.kind}">${m.ok?"…":""}</small></button>`).join("")}</div>`:"";
  const live=running?`<div class="tlive"><b>${ss.paused?"⏸":"●"}</b><span>${ss.paused?tl("PAUSED")+" · ":""}${WBLOCK[ss.block]||BLOCK[ss.block]||tl("Session")} · ${esc(ss.drill||"…")}</span><span>⭐ ${ss.points||0} · ${ss.ok||0}/${ss.done||0} ✔${ss.streak>=2?` · 🔥${ss.streak}`:""}</span><span>${ss.left?`${Math.floor(ss.left/60)}:${String(ss.left%60).padStart(2,"0")}`:""}</span>${T.humans?"":T.join&&/refused|failed/.test(T.join.state)?`<span class="note" style="color:var(--bad,#f87171)">${esc(T.join.why||tl("CS2 did not get in"))}</span>`:`<span class="note">${tl("waiting for you on the server")}</span>`}</div>`:"";
  const lxOff=D.local&&D.linux&&!D.linux_training;   // Linux: the training server is experimental, off until turned on here or in Settings
  box.innerHTML=`<div class="pwarm-h"><span class="eyebrow">${block?tl("Focus block · on the training server"):tl("Warm-up · all on the training server")}</span></div>
    ${recap}${tiles}
    ${lxOff?`<div class="note" style="border:1px solid var(--line);border-radius:6px;padding:10px 12px;display:grid;gap:8px"><span>${tl("<b>Linux: the training server is experimental.</b> Its first runs on Linux: if it fails, the <b>alpha · report</b> tag sends its log to the developer.")}</span><div class="btns"><button type="button" class="primary" data-lxt>${tl("Turn on the training server")}</button></div></div>`:""}
    ${running?"":`<div class="btns pwlen" role="group" aria-label="${tl("Duration")}">${(block?PREP_BLOCK:PREP_LEN).map(n=>`<button type="button" data-pwlen="${n}" aria-pressed="${mins===n}">${tl("{n} min",{n})}</button>`).join("")}</div>`}
    ${block&&!B.length?`<p class="note">${tl("nothing of this module on this map yet")}</p>`:""}<ol class="pwarm-plan">${byMap.map(({mp,b})=>`${byMap.length>1?`<li class="pwmap">${esc(MAPN(mp))}</li>`:""}${b.map(x=>`<li class="k-${x.kind}"><b>${WBLOCK[x.kind]||x.kind}</b><span>${Math.max(1,Math.round(x.seconds/60))}′</span></li>`).join("")}`).join("")}</ol>
    ${live}
    <div class="trow"><button type="button" class="tbig" data-pwgo${wait?" disabled":""}>${running?"↻ "+tl("NEW WARM-UP"):"▶ "+tl("WARM-UP")}</button>${running&&!T.humans&&!wait?`<button type="button" data-pwjoin>↪ ${tl("Rejoin the server")}</button>`:""}${running&&T.humans?`<button type="button" data-pwpause${wait?" disabled":""}>${ss.paused?"▶ "+tl("Resume"):"⏸ "+tl("Pause")}</button>`:""}${T.running?`<button type="button" data-pwstop${wait?" disabled":""}>${tl("Stop")}</button>`:""}<span class="note" role="status" data-pwmsg>${esc(say)}</span></div>
    <div class="trow" role="group" aria-label="${tl("Bots' level")}"><span class="tk2" title="${tl("Bots' level")}">🤖</span>${DIFF.map((n,i)=>`<button type="button" data-pwdiff="${i}" aria-pressed="${i===df}">${n}</button>`).join("")}${sug?`<span class="note">${tl("suggested: {level}",{level:DIFF[sug.diff]})} · ${esc(sug.why)}</span>`:""}</div>
    <div class="tlvl"><b>${tl("LVL {n}",{n:Pg.level})}</b><div class="tbar"><i style="width:${pct}%"></i></div><span>${tl("{a} / {b} XP to LVL {n}",{a:Math.max(0,Pg.xp-Pg.from).toLocaleString(LOC),b:Math.max(1,Pg.to-Pg.from).toLocaleString(LOC),n:Pg.level+1})}</span></div>
    <p class="note">${tl("One button: the server starts, the session is built on your maps, CS2 joins it (started first if it is closed). In game: <b>!n</b> skips a drill, <b>!r</b> again, <b>!pause</b> / <b>!resume</b>, <b>!stop</b> ends, <b>!report</b> followed by a few words tells the developer what's wrong.")}</p>`;
  const msg=$("[data-pwmsg]",box);
  $$("[data-pwlen]",box).forEach(b=>b.onclick=()=>{if(block)st.bmin=+b.dataset.pwlen;else st.min=+b.dataset.pwlen;prepSave(st);   // another duration: the parts redone at once
    $$("[data-pwlen]",box).forEach(x=>x.setAttribute("aria-pressed",String(x===b)));
    const pl=$(".pwarm-plan",box);if(pl)pl.style.opacity=".45";prepWarm(v,p,sel,st)});
  $$("[data-pwdiff]",box).forEach(b=>b.onclick=()=>{try{localStorage.setItem("coach_diff",b.dataset.pwdiff)}catch(e){}tSet("at",Date.now());prepWarm(v,p,sel,st)});   // your pick wins for 12 h
  // a start or a stop: shown, with its seconds, until it answers (a refresh meanwhile keeps it)
  const run=async(text,path,body,done)=>{PREP.pend={t0:Date.now(),text};PREP.note=null;
    $$("[data-pwgo],[data-pwstop],[data-pwjoin],[data-pwpause]",box).forEach(x=>x.disabled=true);msg.textContent=text;prepWarm(v,p,sel,st);   // at once: the card's own fetches take a second or two
    try{const r=await api(path,body);PREP.note=done?{t:Date.now(),text:done(r)}:null}catch(e){PREP.note={t:Date.now(),text:tl("Failed: {why}",{why:e.message})}}
    PREP.pend=null;if(S.view==="prepare")prepWarm(v,p,sel,st)};
  const lxt=$("[data-lxt]",box);if(lxt)lxt.onclick=async()=>{lxt.disabled=true;try{await api("/api/app/options",{linux_training:true});D.linux_training=true;prepWarm(v,p,sel,st)}catch(e){lxt.disabled=false;lxt.insertAdjacentHTML("afterend",`<span class="note"> ${esc(e.message)}</span>`)}};
  const old=focus&&pv&&!pv.modules;   // an app started before the focus blocks (13/10): it would start a full session
  if(lxOff||(block&&!B.length)||old){const g0=$("[data-pwgo]",box);if(g0)g0.disabled=true}
  if(old&&!pend)msg.textContent=tl("Restart Wily to use focus blocks.");
  $$("[data-pfocus]",box).forEach(b=>b.onclick=()=>{st.focus=b.dataset.pfocus;prepSave(st);   // another module: its plan at once
    $$("[data-pfocus]",box).forEach(x=>x.setAttribute("aria-pressed",String(x===b)));const pl=$(".pwarm-plan",box);if(pl)pl.style.opacity=".45";prepWarm(v,p,sel,st)});
  if(tiles){const mp=sel[0],fill=c=>{if(!box.isConnected)return;let gone=false;
      $$("[data-pfn]",box).forEach(el=>{const k=el.dataset.pfn,n=c.counts[k],bt=el.closest("button");if(n==null||bt.disabled){el.textContent="";return}
        if(k==="crossfire"){el.textContent=n?tln(n,"{n} spot","{n} spots"):"";return}
        if(!n){el.textContent=tl("none on this map yet");bt.disabled=true;if(k===focus)gone=true;return}
        const m=Math.max(1,Math.round(n*c.repeat*(c.est[k]||60)/60));   // each drill three times at most: a short block
        el.textContent=m<mins?`${tln(n,"{n} drill","{n} drills")} · ${tl("about {m} min here",{m})}`:tln(n,"{n} drill","{n} drills")});
      if(gone){const f=$$("[data-pfocus]",box).find(x=>!x.disabled);if(f){st.focus=f.dataset.pfocus;prepSave(st);prepWarm(v,p,sel,st)}}};
    if(PREP.cnt&&PREP.cnt.map===mp&&Date.now()-PREP.cnt.at<6e5)fill(PREP.cnt);
    else get(`/api/train/modules?sid=${p.steamid}&map=${encodeURIComponent(mp)}`).then(c=>{if(!c)return;PREP.cnt={...c,at:Date.now()};if(sel[0]===mp)fill(PREP.cnt)})}
  const go=$("[data-pwgo]",box);if(go)go.onclick=()=>run(T.running?tl("Preparing the session (30 s, a few minutes the first time) · CS2 starts meanwhile…"):tl("Starting the server and preparing the session (30 s, a few minutes the first time) · CS2 starts meanwhile…"),
    "/api/train/session",focus?{sid:p.steamid,minutes:mins,where,diff:df,focus}:{sid:p.steamid,minutes:mins,where,diff:df},
    r=>`${r.blocks.map(b=>`${WBLOCK[b.kind]||b.kind} ${Math.max(1,Math.round(b.seconds/60))}′`).join(" → ")} — ${tl("CS2 joins the server. If Steam opens its \"game info\" window instead, click \"Join game\".")}`);
  const jn=$("[data-pwjoin]",box);if(jn)jn.onclick=async()=>{jn.disabled=true;PREP.note={t:Date.now(),text:tl("CS2 joins the server (started first if it is closed)…")};msg.textContent=PREP.note.text;
    try{await api("/api/train/join",{})}catch(e){PREP.note={t:Date.now(),text:tl("Failed: {why}",{why:e.message})};msg.textContent=PREP.note.text;jn.disabled=false}};
  const sp=$("[data-pwstop]",box);if(sp)sp.onclick=()=>run(tl("Stopping the training server…"),"/api/train/stop",{});
  const pz=$("[data-pwpause]",box);if(pz)pz.onclick=()=>run(ss.paused?tl("Going on…"):tl("Pausing (the block's clock waits)…"),ss.paused?"/api/train/resume":"/api/train/pause",{});   // 09/10: "la mettre en pause, et la reprendre"
  clearInterval(PREP.sec);if(pend)PREP.sec=setInterval(()=>{if(!PREP.pend||!box.isConnected){clearInterval(PREP.sec);return}   // its seconds, each second
    msg.textContent=`${PREP.pend.text} (${Math.round((Date.now()-PREP.pend.t0)/1e3)} s)`},1000);
  if(T.running||wait)PREP.warm=setTimeout(()=>{if(box.isConnected&&S.view==="prepare")prepWarm(v,p,sel,st)},4000)}
// CS2 loads a map (not the training server): Live takes over
function prepWatch(){clearTimeout(PREP.watch);if(S.view!=="prepare"||!D.local)return;
  fetch("/api/gsi/state").then(r=>r.json()).then(g=>{if(S.view!=="prepare")return;
    if(g&&g.map&&!g.practice&&(g.age==null||g.age<30)&&g.map_phase&&g.map_phase!=="gameover"){if(D.own&&S.player!==D.own){S.view="ingame";setPlayer(D.own)}else go("ingame");return}
    PREP.watch=setTimeout(prepWatch,3000)}).catch(()=>{PREP.watch=setTimeout(prepWatch,6000)})}

// where you lose rounds lately (06/10: "la game d'Overpass où on s'est pris des execs B en CT: priorise-les en
// entraînement"): the training puts their maps, the defense of those sites and those rounds first
async function prepStruggles(v,p){const boxes=$$("[data-pstrug]",v);if(!boxes.length||!D.local)return;let r;
  try{const x=await fetch("/api/train/struggles?sid="+encodeURIComponent(p.steamid));if(!x.ok)return;r=await x.json()}catch(e){return}
  const S=(r.struggles||[]).slice(0,3);if(!S.length)return;
  const html=`<p class="note">${tl("<b>⚠ The training puts first</b> where you lose rounds lately:")}</p><ul class="pstrug-l">${S.map(x=>`<li><b>${esc(MAPN(x.map))}</b> · ${esc(x.text)}${x.last?` <span class="note">(${tl("last {date}",{date:esc(x.last)})})</span>`:""}</li>`).join("")}</ul>`;
  boxes.forEach(b=>b.innerHTML=html)}
