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
const PREP={tick:null,watch:null,warm:null,sec:null,pend:null,note:null};
const WBLOCK={aim:"🎯 Aim",defend:"🛡 Defense",push:"🚶 Prefire",nade:"💨 Stuff",wallbang:"🧱 Wallbang",situation:"🔁 Situations"};
// what you chose today (your browser): the maps, the duration, the blocks done, the one running
function prepState(){const day=new Date().toDateString();let st=store("prep");
  if(!st||st.day!==day)st={day,maps:[],min:20,done:{},cur:null,t0:null};return st}
function prepSave(st){store("prep",st)}
// your focus of the week: changed from Review or Profile (focus.py)
function wireFocus(v,p,rerender){const sel=$("[data-focus-pick]",v);if(!sel)return;
  sel.onchange=async()=>{const id=sel.value;if(!id)return;sel.disabled=true;
    try{const j=await api("/api/focus",{sid:p.steamid,id});const A=p.advice;A.plan=A.plan||{};A.plan.focus=j.focus;navUpdate(S.view);rerender()}
    catch(e){sel.disabled=false;sel.insertAdjacentHTML("afterend",` <span class="note">${esc(e.message)}</span>`)}}}
function renderPrepare(){
  const p=P(),v=$("#v-prepare"),PL=p.advice.plan;if(!PL)return noPlan(v);
  clearTimeout(PREP.warm);
  const st=prepState(),own=D.local&&p.steamid===D.own,maps=mapsOf(p),sel=(st.maps||[]).filter(m=>maps.some(x=>x.map===m)).slice(0,3);
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)} · before you play</span><h2>Prepare</h2></div></div>
   <section class="prep1">
    <h3>Which maps?</h3><p class="note">One to three: the warm-up follows them. Your most played first.</p>
    <div class="btns prep-maps" role="group" aria-label="Maps">${maps.map(m=>`<button type="button" data-pmap="${esc(m.map)}" aria-pressed="${sel.includes(m.map)}">${esc(MAPN(m.map))} <span class="note">${m.n||0}</span></button>`).join("")}</div>
    ${own?`<div class="pstrug" data-pstrug></div>`:""}</section>
   <section class="prep2">${!sel.length?`<p class="note">Pick a map: the warm-up builds itself here.</p>`
     :`<article class="card pwarm" data-pwarm>${own?`<p class="note"><span class="spin" aria-hidden="true"></span>Preparing your warm-up…</p>`:`<p class="note">The warm-up runs on the training server, from the local app (double-click <code>Wily.bat</code>).</p>`}</article>`}</section>`;   // no pre-session journal here either (07/10: "tu peux aussi enlever ça")
  $$("[data-pmap]",v).forEach(b=>b.onclick=()=>{const m=b.dataset.pmap,i=sel.indexOf(m);if(i>=0)sel.splice(i,1);else if(sel.length<3)sel.push(m);else return;
    st.maps=sel.slice();prepSave(st);renderPrepare()});   // another map: the warm-up redone under it
  prepStruggles(v,p);
  if(sel.length&&own)prepWarm(v,p,sel,st)}
// the warm-up's card: what the session will be (each part's minutes, your priorities), the bots' level, ONE button that
// starts the server, builds the session and sends the game, then the session live (part, drill, points, time left)
async function prepWarm(v,p,sel,st){const box=$("[data-pwarm]",v);if(!box||!D.local)return;clearTimeout(PREP.warm);
  const get=u=>fetch(u).then(r=>r.ok?r.json():null).catch(()=>null),where=sel.join(",");
  const [d,pv]=await Promise.all([get("/api/train?sid="+p.steamid),get(`/api/train/preview?sid=${p.steamid}&minutes=${st.min}&where=${encodeURIComponent(where)}`)]);
  if(!box.isConnected||S.view!=="prepare")return;
  if(!d){box.innerHTML=`<p class="note">The local server doesn't answer.</p>`;return}
  const T=d.status||{},Pg=d.progress||{level:1,xp:0,from:0,to:300},ss=T.session;
  if(!T.installed){trainInstall(box,p.steamid,T);if((T.install||{}).running)PREP.warm=setTimeout(()=>prepWarm(v,p,sel,st),2500);return}
  // the aim first, on the game's aim map (06/10), then your maps
  const B=(pv&&pv.blocks)||[],byMap=[...new Set([...B.filter(x=>!sel.includes(x.map)).map(x=>x.map),...sel])].map(mp=>({mp,b:B.filter(x=>x.map===mp)})).filter(x=>x.b.length);
  const sug=Pg.suggest||null,chose=Date.now()-(+tPref("at","0"))<12*3600e3,df=sug&&!chose?sug.diff:trainDiff(),pct=Math.max(0,Math.min(100,100*(Pg.xp-Pg.from)/Math.max(1,Pg.to-Pg.from)));
  const running=ss&&T.running,pend=PREP.pend,wait=!!(pend||T.busy);   // T.busy: a start the server side runs (a reload meanwhile)
  const say=pend?`${pend.text} (${Math.round((Date.now()-pend.t0)/1e3)} s)`:T.busy?`${T.busy.charAt(0).toUpperCase()+T.busy.slice(1)} is starting on the training server…`
    :PREP.note&&Date.now()-PREP.note.t<30e3?PREP.note.text:T.dead?"The training server stopped answering: ▶ WARM-UP starts it again.":"";
  const live=running?`<div class="tlive"><b>●</b><span>${WBLOCK[ss.block]||BLOCK[ss.block]||"Session"} · ${esc(ss.drill||"…")}</span><span>⭐ ${ss.points||0} · ${ss.ok||0}/${ss.done||0} ✔${ss.streak>=2?` · 🔥${ss.streak}`:""}</span><span>${ss.left?`${Math.floor(ss.left/60)}:${String(ss.left%60).padStart(2,"0")}`:""}</span>${T.humans?"":T.join&&/refused|failed/.test(T.join.state)?`<span class="note" style="color:var(--bad,#f87171)">${esc(T.join.why||"CS2 did not get in")}</span>`:`<span class="note">waiting for you on the server</span>`}</div>`:"";
  box.innerHTML=`<div class="pwarm-h"><span class="eyebrow">Warm-up · all on the training server</span></div>
    ${running?"":`<div class="btns pwlen" role="group" aria-label="Duration">${PREP_LEN.map(n=>`<button type="button" data-pwlen="${n}" aria-pressed="${st.min===n}">${n} min</button>`).join("")}</div>`}
    <ol class="pwarm-plan">${byMap.map(({mp,b})=>`${byMap.length>1?`<li class="pwmap">${esc(MAPN(mp))}</li>`:""}${b.map(x=>`<li class="k-${x.kind}"><b>${WBLOCK[x.kind]||x.kind}</b><span>${Math.max(1,Math.round(x.seconds/60))}′</span></li>`).join("")}`).join("")}</ol>
    ${live}
    <div class="trow"><button type="button" class="tbig" data-pwgo${wait?" disabled":""}>${running?"↻ NEW WARM-UP":"▶ WARM-UP"}</button>${running&&!T.humans&&!wait?`<button type="button" data-pwjoin>↪ Rejoin the server</button>`:""}${T.running?`<button type="button" data-pwstop${wait?" disabled":""}>Stop</button>`:""}<span class="note" role="status" data-pwmsg>${esc(say)}</span></div>
    <div class="trow" role="group" aria-label="Bots' level"><span class="tk2" title="Bots' level">🤖</span>${DIFF.map((n,i)=>`<button type="button" data-pwdiff="${i}" aria-pressed="${i===df}">${n}</button>`).join("")}${sug?`<span class="note">suggested: ${DIFF[sug.diff]} · ${esc(sug.why)}</span>`:""}</div>
    <div class="tlvl"><b>LVL ${Pg.level}</b><div class="tbar"><i style="width:${pct}%"></i></div><span>${Math.max(0,Pg.xp-Pg.from).toLocaleString("en-US")} / ${Math.max(1,Pg.to-Pg.from).toLocaleString("en-US")} XP to LVL ${Pg.level+1}</span></div>
    <p class="note">One button: the server starts, the session is built on your maps, CS2 joins it (started first if it is closed). In game: <b>!n</b> skips a drill, <b>!r</b> again, <b>!stop</b> ends, <b>!report</b> followed by a few words tells my author what's wrong.</p>`;
  const msg=$("[data-pwmsg]",box);
  $$("[data-pwlen]",box).forEach(b=>b.onclick=()=>{st.min=+b.dataset.pwlen;prepSave(st);   // another duration: the parts redone at once
    $$("[data-pwlen]",box).forEach(x=>x.setAttribute("aria-pressed",String(x===b)));
    const pl=$(".pwarm-plan",box);if(pl)pl.style.opacity=".45";prepWarm(v,p,sel,st)});
  $$("[data-pwdiff]",box).forEach(b=>b.onclick=()=>{try{localStorage.setItem("coach_diff",b.dataset.pwdiff)}catch(e){}tSet("at",Date.now());prepWarm(v,p,sel,st)});   // your pick wins for 12 h
  // a start or a stop: shown, with its seconds, until it answers (a refresh meanwhile keeps it)
  const run=async(text,path,body,done)=>{PREP.pend={t0:Date.now(),text};PREP.note=null;
    $$("[data-pwgo],[data-pwstop],[data-pwjoin]",box).forEach(x=>x.disabled=true);msg.textContent=text;prepWarm(v,p,sel,st);   // at once: the card's own fetches take a second or two
    try{const r=await api(path,body);PREP.note=done?{t:Date.now(),text:done(r)}:null}catch(e){PREP.note={t:Date.now(),text:"Failed: "+e.message}}
    PREP.pend=null;if(S.view==="prepare")prepWarm(v,p,sel,st)};
  const go=$("[data-pwgo]",box);if(go)go.onclick=()=>run(T.running?"Preparing the session (30 s, a few minutes the first time) · CS2 starts meanwhile…":"Starting the server and preparing the session (30 s, a few minutes the first time) · CS2 starts meanwhile…",
    "/api/train/session",{sid:p.steamid,minutes:st.min,where,diff:df},
    r=>`${r.blocks.map(b=>`${WBLOCK[b.kind]||b.kind} ${Math.max(1,Math.round(b.seconds/60))}′`).join(" → ")} — CS2 joins the server. If Steam opens its "game info" window instead, click "Join game" (Rejoindre la partie).`);
  const jn=$("[data-pwjoin]",box);if(jn)jn.onclick=async()=>{jn.disabled=true;PREP.note={t:Date.now(),text:"CS2 joins the server (started first if it is closed)…"};msg.textContent=PREP.note.text;
    try{await api("/api/train/join",{})}catch(e){PREP.note={t:Date.now(),text:"Failed: "+e.message};msg.textContent=PREP.note.text;jn.disabled=false}};
  const sp=$("[data-pwstop]",box);if(sp)sp.onclick=()=>run("Stopping the training server…","/api/train/stop",{});
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
  const html=`<p class="note"><b>⚠ The training puts first</b> where you lose rounds lately:</p><ul class="pstrug-l">${S.map(x=>`<li><b>${esc(MAPN(x.map))}</b> · ${esc(x.text)}${x.last?` <span class="note">(last ${esc(x.last)})</span>`:""}</li>`).join("")}</ul>`;
  boxes.forEach(b=>b.innerHTML=html)}
