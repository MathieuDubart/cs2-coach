// ---------- view: prepare (05/10, reworked 06/10): before you play. Your maps and a duration (5, 10, 20 or 30 min),
// then ONE warm-up on the training server (06/10, the user: "tout l'entraînement sur le même serveur comme avant, le
// bouton warmup pour tout lancer: de l'aim, de la défense de bomb site, du chemin de prefire, du stuff, du wallbang"):
// one button starts the server, builds the session in that order on your maps and sends the game there; the page
// follows it live. A 60-second sheet per map and side, your focus of the week; when CS2 loads a map, Live takes over ----------
const PREP_LEN=[5,10,20,30];
const PREP_NOTE={5:"Aim, defense and prefire on the training server: the hands only.",10:"Aim, defense, prefire, stuff, wallbangs and your situations, all on the training server.",20:"The same, longer: more of your situations and of the defense where you lose rounds.",30:"Everything, with time: aim, defense, prefire, stuff, wallbangs, situations."};
const PREP={tick:null,watch:null,warm:null};
const WBLOCK={aim:"🎯 Aim",defend:"🛡 Defense",push:"🚶 Prefire",nade:"💨 Stuff",wallbang:"🧱 Wallbang",situation:"🔁 Situations"};
// what you chose today (your browser): the step, the maps, the duration, the blocks done, the one running
function prepState(){const day=new Date().toDateString();let st=store("prep");
  if(!st||st.day!==day)st={day,step:1,maps:[],min:20,done:{},cur:null,t0:null};return st}
function prepSave(st){store("prep",st)}
// a bullet's lead: its bold part (and the numbers in brackets after it), else its first sentence
function sheetLead(h){h=String(h||"").trim();const m=/^<b>([\s\S]*?)<\/b>(\s*\([^)]*\))?/.exec(h);if(m)return `<b>${m[1]}</b>${m[2]||""}`;
  const t=h.replace(/<[^>]+>/g,""),c=t.search(/\.\s/);return esc(c>0&&c<130?t.slice(0,c+1):t.slice(0,130))}
// one side of a map in five lines: where you win, where you lose, your grenades, the timing, a reflex
function sheetSide(p,mp,side){const m=crossMap(p,mp),R0=!m?((p.advice.plan||{}).map_refs||{})[mp]:null,d=planData(p,m,R0,mp,side);
  const play=[...d.baseGood,...d.cGood,...d.good.map(b=>b.text),...d.tries.slice(0,1).map(b=>b.text)].map(sheetLead).filter(Boolean).slice(0,2);
  const avoid=[...d.baseBad,...d.cAvoid,...d.bad.map(b=>b.text)].map(sheetLead).filter(Boolean).slice(0,2);
  const nades=((d.Sd&&d.plan&&d.plan.key_nades)||[]).slice(0,3).map(k=>d.Sd.lineups[k]).filter(Boolean);
  const timing=d.timesOk[0]?d.timesOk[0].text:"",rf=d.reflex[0];   // short already, and its clock is the point
  const row=(cls,lab,html)=>html?`<div class="srow"><span class="slab ${cls}">${lab}</span><span>${html}</span></div>`:"";
  return `<div class="sside"><h4 class="${side==="T"?"t":"ct"}">${side==="T"?"T · attack":"CT · defense"}</h4>
    ${row("ok","Play",play.join("<br>"))}${row("no","Avoid",avoid.join("<br>"))}
    ${row("nade","Nades",nades.map(l=>`${TYPE[l.type]||esc(l.type)} ${esc(l.from_zone)} → ${esc(nTo(l,mp)||"?")}${l.t!=null?` <span class="note">${clock(l.t)}</span>`:""}`).join("<br>"))}
    ${row("","Timing",timing)}${row("","If",rf?`${esc(lc(rf.if))} → ${esc(rf.then)}`:"")}
    ${!play.length&&!avoid.length&&!nades.length?`<p class="note">Not enough of your rounds here on this side yet.</p>`:""}</div>`}
function mapSheet(p,mp){return `<article class="psheet"><div class="psh"><h3>${esc(MAPN(mp))}</h3><span class="note">read in 60 s</span></div><div class="psides">${sheetSide(p,mp,"T")}${sheetSide(p,mp,"CT")}</div></article>`}
// your focus of the week (focus.py), and its change among the coach's next axes (Review and Prepare)
function focusCard(p,extra){const F=focusOf(p);
  if(!F)return `<article class="card b-next"><span class="eyebrow">Focus of the week</span><p class="note">I pick it once a few of your matches are analyzed.</p></article>`;
  const own=D.local&&p.steamid===D.own,u=F.until?new Date(F.until):null;
  return `<article class="card b-next focus-card"><span class="eyebrow">Focus of the week${u&&!isNaN(u)?` · until ${u.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})}`:""}${F.manual?" · your pick":""}</span>
   <p class="lead">${esc(F.short)}</p>
   ${(F.do||[]).length?`<ul>${F.do.slice(0,2).map(t=>`<li>${esc(t)}</li>`).join("")}</ul>`:""}
   ${(F.drills||[]).length?`<p class="note">Drill: ${esc(F.drills[0])}</p>`:""}${extra||""}
   ${own&&(F.others||[]).length?`<label class="note focus-pick">Change it: <select data-focus-pick><option value="">keep this one</option>${F.others.map(o=>`<option value="${esc(o.id)}">${esc(o.short)}</option>`).join("")}</select></label>`:""}</article>`}
function wireFocus(v,p,rerender){const sel=$("[data-focus-pick]",v);if(!sel)return;
  sel.onchange=async()=>{const id=sel.value;if(!id)return;sel.disabled=true;
    try{const j=await api("/api/focus",{sid:p.steamid,id});const A=p.advice;A.plan=A.plan||{};A.plan.focus=j.focus;navUpdate(S.view);rerender()}
    catch(e){sel.disabled=false;sel.insertAdjacentHTML("afterend",` <span class="note">${esc(e.message)}</span>`)}}}
function renderPrepare(){
  const p=P(),v=$("#v-prepare"),PL=p.advice.plan;if(!PL)return noPlan(v);
  clearTimeout(PREP.warm);
  const st=prepState(),own=D.local&&p.steamid===D.own,maps=mapsOf(p),sel=(st.maps||[]).filter(m=>maps.some(x=>x.map===m)).slice(0,3);
  if(st.step>1&&!sel.length)st.step=1;
  const steps=[[1,"Maps & time"],[2,`Warm-up · ${st.min} min`],[3,"Ready"]];
  const step1=()=>`<section class="prep1">
    <h3>Which maps?</h3><p class="note">One to three: the warm-up and the sheets follow them. Your most played first.</p>
    <div class="btns prep-maps" role="group" aria-label="Maps">${maps.map(m=>`<button type="button" data-pmap="${esc(m.map)}" aria-pressed="${sel.includes(m.map)}">${esc(MAPN(m.map))} <span class="note">${m.n||0}</span></button>`).join("")}</div>
    <h3>How long?</h3>
    <div class="btns" role="group" aria-label="Duration">${PREP_LEN.map(n=>`<button type="button" data-pmin="${n}" aria-pressed="${st.min===n}">${n} min</button>`).join("")}</div>
    <p class="note">${PREP_NOTE[st.min]||""}</p>${own?`<div class="pstrug" data-pstrug></div>`:""}
    <div class="btns"><button type="button" class="primary" data-pgo ${sel.length?"":"disabled"}>Build my warm-up →</button></div>
    ${own?`<div style="margin-top:18px">${checkinCard((PL.context||{}).journal_n)}</div>`:""}</section>`;
  const step2=()=>`<section class="prep2">
    <article class="card pwarm" data-pwarm>${own?`<p class="note"><span class="spin" aria-hidden="true"></span>Preparing your warm-up…</p>`:`<p class="note">The warm-up runs on the training server, from the local app (double-click <code>Wily.bat</code>).</p>`}</article>
    ${own?`<details class="pextra"><summary>📷 Photos of the lineups (where to aim, for Live)</summary><div class="pshots" data-pshots></div></details>`:""}
    <div class="btns"><button type="button" data-pstep="3">I'm ready →</button></div>
    <h3>Your map sheets</h3><div class="psheets">${sel.map(mp=>mapSheet(p,mp)).join("")}</div></section>`;
  const step3=()=>{const recs=((PL.context||{}).recs||[]).filter(r=>r.kind==="stop"||r.kind==="tilt"),exps=((PL.experiments||{}).experiments||[]).filter(e=>e.status==="active");
    return `<section class="prep3"><div class="prep-ready">${focusCard(p)}
      <article class="card"><span class="eyebrow">Session rule</span><p class="lead">${esc(recs.length?recs[0].text:"A 10-15 min break after a loss, stop after 2 losses in a row.")}</p>${exps.map(e=>`<p class="note">Running experiment: ${esc(e.title)}</p>`).join("")}</article>
      <article class="card"><span class="eyebrow">Next</span><p class="lead">Your match</p><p class="note">${D.local?"When CS2 loads a map, this page hands over to Live by itself.":"Live follows your match in the local app."}</p><div class="btns"><a class="btnlink" href="#ingame">Open Live</a></div></article></div>
     <h3>Your maps</h3><div class="psheets">${sel.map(mp=>mapSheet(p,mp)).join("")}</div></section>`};
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)} · before you play</span><h2>Prepare</h2></div></div>
   <nav class="prep-steps" aria-label="Steps">${steps.map(([n,t])=>`<button type="button" data-pstep="${n}"${st.step===n?' aria-current="step"':""}${n>1&&!sel.length?" disabled":""}><b>${n}</b>${esc(t)}</button>`).join("")}</nav>
   ${st.step===1?step1():st.step===2?step2():step3()}`;
  const save=()=>{prepSave(st);renderPrepare()};
  $$("[data-pstep]",v).forEach(b=>b.onclick=()=>{st.step=+b.dataset.pstep;save()});
  $$("[data-pmap]",v).forEach(b=>b.onclick=()=>{const m=b.dataset.pmap,i=sel.indexOf(m);if(i>=0)sel.splice(i,1);else if(sel.length<3)sel.push(m);else return;
    st.maps=sel.slice();save()});
  $$("[data-pmin]",v).forEach(b=>b.onclick=()=>{st.min=+b.dataset.pmin;save()});
  const gb=$("[data-pgo]",v);if(gb)gb.onclick=()=>{st.step=2;save()};
  wireCheckin(v,p);wireFocus(v,p,renderPrepare);prepStruggles(v,p);
  if(st.step===2&&own){prepWarm(v,p,sel,st);prepShots(v,sel)}}
// the warm-up's card: what the session will be (each part's minutes, your priorities), the bots' level, ONE button that
// starts the server, builds the session and sends the game, then the session live (part, drill, points, time left)
async function prepWarm(v,p,sel,st){const box=$("[data-pwarm]",v);if(!box||!D.local)return;clearTimeout(PREP.warm);
  const get=u=>fetch(u).then(r=>r.ok?r.json():null).catch(()=>null),where=sel.join(",");
  const [d,pv,sg]=await Promise.all([get("/api/train?sid="+p.steamid),get(`/api/train/preview?sid=${p.steamid}&minutes=${st.min}&where=${encodeURIComponent(where)}`),get("/api/train/struggles?sid="+p.steamid)]);
  if(!box.isConnected||S.view!=="prepare")return;
  if(!d){box.innerHTML=`<p class="note">The local server doesn't answer.</p>`;return}
  const T=d.status||{},Pg=d.progress||{level:1,xp:0,from:0,to:300},ss=T.session;
  if(!T.installed){trainInstall(box,p.steamid,T);if((T.install||{}).running)PREP.warm=setTimeout(()=>prepWarm(v,p,sel,st),2500);return}
  // the aim first, on the game's aim map (06/10), then your maps
  const B=(pv&&pv.blocks)||[],byMap=[...new Set([...B.filter(x=>!sel.includes(x.map)).map(x=>x.map),...sel])].map(mp=>({mp,b:B.filter(x=>x.map===mp)})).filter(x=>x.b.length);
  const sug=Pg.suggest||null,chose=Date.now()-(+tPref("at","0"))<12*3600e3,df=sug&&!chose?sug.diff:trainDiff(),pct=Math.max(0,Math.min(100,100*(Pg.xp-Pg.from)/Math.max(1,Pg.to-Pg.from)));
  const top=((sg&&sg.struggles)||[]).filter(x=>sel.includes(x.map)).slice(0,2);
  const running=ss&&T.running;
  const live=running?`<div class="tlive"><b>●</b><span>${WBLOCK[ss.block]||BLOCK[ss.block]||"Session"} · ${esc(ss.drill||"…")}</span><span>⭐ ${ss.points||0} · ${ss.ok||0}/${ss.done||0} ✔${ss.streak>=2?` · 🔥${ss.streak}`:""}</span><span>${ss.left?`${Math.floor(ss.left/60)}:${String(ss.left%60).padStart(2,"0")}`:""}</span>${T.humans?"":`<span class="note">waiting for you on the server</span>`}</div>`:"";
  box.innerHTML=`<div class="pwarm-h"><span class="eyebrow">Warm-up · ${st.min} min · ${sel.map(MAPN).join(", ")} · all on the training server</span></div>
    <ol class="pwarm-plan">${byMap.map(({mp,b})=>`${byMap.length>1?`<li class="pwmap">${esc(MAPN(mp))}</li>`:""}${b.map(x=>`<li class="k-${x.kind}"><b>${WBLOCK[x.kind]||x.kind}</b><span>${Math.max(1,Math.round(x.seconds/60))}′</span></li>`).join("")}`).join("")}</ol>
    ${top.length?`<p class="note">⚠ First where you lose rounds lately: ${top.map(x=>`<b>${esc(MAPN(x.map))}</b> ${esc(x.text)}`).join(" · ")}</p>`:""}
    ${live}
    <div class="trow"><button type="button" class="tbig" data-pwgo>${running?"↻ NEW WARM-UP":"▶ WARM-UP"}</button>${running&&!T.humans?`<button type="button" data-pwjoin>↪ Rejoin the server</button>`:""}${T.running?`<button type="button" data-pwstop>Stop</button>`:""}<span class="note" role="status" data-pwmsg></span></div>
    <div class="trow" role="group" aria-label="Bots' level"><span class="tk2" title="Bots' level">🤖</span>${DIFF.map((n,i)=>`<button type="button" data-pwdiff="${i}" aria-pressed="${i===df}">${n}</button>`).join("")}${sug?`<span class="note">suggested: ${DIFF[sug.diff]} · ${esc(sug.why)}</span>`:""}</div>
    <div class="tlvl"><b>LVL ${Pg.level}</b><div class="tbar"><i style="width:${pct}%"></i></div><span>${Pg.xp} / ${Pg.to} XP</span></div>
    <p class="note">One button: the server starts, the session is built on your maps, CS2 joins it (started first if it is closed). In game: <b>!n</b> skips a drill, <b>!r</b> again, <b>!stop</b> ends.</p>`;
  const msg=$("[data-pwmsg]",box);
  $$("[data-pwdiff]",box).forEach(b=>b.onclick=()=>{try{localStorage.setItem("coach_diff",b.dataset.pwdiff)}catch(e){}tSet("at",Date.now());prepWarm(v,p,sel,st)});   // your pick wins for 12 h
  const go=$("[data-pwgo]",box);if(go)go.onclick=async()=>{go.disabled=true;$$("[data-pshot]",v).forEach(b=>b.disabled=true);   // one thing at a time on the servermsg.textContent=T.running?"Preparing the session (30 s, a few minutes the first time) · CS2 starts meanwhile…":"Starting the server and preparing the session (30 s, a few minutes the first time) · CS2 starts meanwhile…";
    try{const r=await api("/api/train/session",{sid:p.steamid,minutes:st.min,where,diff:df});
      msg.textContent=`${r.blocks.map(b=>`${WBLOCK[b.kind]||b.kind} ${Math.max(1,Math.round(b.seconds/60))}′`).join(" → ")} — CS2 joins the server. If Steam opens its "game info" window instead, click "Join game" (Rejoindre la partie).`;
      PREP.warm=setTimeout(()=>prepWarm(v,p,sel,st),5000)}
    catch(e){msg.textContent="Failed: "+e.message;go.disabled=false}};
  const jn=$("[data-pwjoin]",box);if(jn)jn.onclick=async()=>{jn.disabled=true;msg.textContent="CS2 joins the server (started first if it is closed)…";
    try{await api("/api/train/join",{})}catch(e){msg.textContent="Failed: "+e.message;jn.disabled=false}};
  const sp=$("[data-pwstop]",box);if(sp)sp.onclick=async()=>{sp.disabled=true;try{await api("/api/train/stop",{})}catch(e){msg.textContent="Failed: "+e.message}prepWarm(v,p,sel,st)};
  if(T.running)PREP.warm=setTimeout(()=>{if(box.isConnected&&S.view==="prepare")prepWarm(v,p,sel,st)},4000)}
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
  const html=`<p class="note"><b>⚠ The training puts first</b> where you lose rounds lately:</p><ul class="pstrug-l">${S.map(x=>`<li><b>${esc(MAPN(x.map))}</b> · ${esc(x.text)}${x.last?` <span class="note">(last ${esc(x.last)})</span>`:""}</li>`).join("")}</ul>`;
  boxes.forEach(b=>b.innerHTML=html)}
// the photos of your maps' lineups (06/10: "les images de là où je dois viser"): taken in your game on the training
// server, numpad + from one lineup to the next; Live shows them with the way's stuff
async function prepShots(v,sel){const box=$("[data-pshots]",v);if(!box||!D.local)return;let st;
  const get=u=>fetch(u).then(r=>r.ok?r.json():null).catch(()=>null);   // read-only: GET (api() posts)
  st=await get("/api/lineshots/status");if(!st)return;
  const per=await Promise.all(sel.map(mp=>get("/api/lineshots/status?map="+encodeURIComponent(mp))));
  box.innerHTML=`<p class="note"><b>📷 Where to aim:</b> I photograph each lineup in your game (training server: numpad + puts you on the spot, aimed; keep still a second). Live then shows the photo with the way's stuff.</p>
   <div class="btns">${sel.map((mp,i)=>{const s=per[i]||{};const on=st.on&&st.map===mp;
     return on?`<span class="note">${esc(MAPN(mp))}: ${s.done||0}/${s.total||0} · <b>numpad +</b> for the next${st.next?` (${esc(st.next.type)} → ${esc(st.next.to||"")})`:""}</span><button type="button" data-pshotstop>Stop</button>`
       :`<button type="button" data-pshot="${esc(mp)}" ${s.total&&s.done>=s.total?"disabled":""}>📷 ${esc(MAPN(mp))} · ${s.done||0}/${s.total||0}</button>`}).join("")}<span class="note" role="status" data-pshotmsg></span></div>`;
  $$("[data-pshot]",box).forEach(b=>b.onclick=async()=>{const m=$("[data-pshotmsg]",box);b.disabled=true;if(m)m.textContent="Starting the training server and sending the game (about 20 s)…";
    try{await api("/api/lineshots/start",{map:b.dataset.pshot});if(m)m.textContent="In the game: numpad + for each lineup (exec coach_binds once if it does nothing).";setTimeout(()=>{if(S.view==="prepare")prepShots(v,sel)},4000)}
    catch(e){if(m)m.textContent="Failed: "+e.message;b.disabled=false}});
  const sb=$("[data-pshotstop]",box);if(sb)sb.onclick=async()=>{try{await api("/api/lineshots/stop",{})}catch(e){}prepShots(v,sel)};
  if(st.on&&S.view==="prepare")setTimeout(()=>{if(S.view==="prepare")prepShots(v,sel)},5000)}
