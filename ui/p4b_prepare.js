// ---------- view: prepare (05/10): before you play. Your maps and a duration (5, 10, 20 or 30 min), a timed warm-up
// built on your weak points (the training server from 20 min), a 60-second sheet per map and side, your focus of the
// week; when CS2 loads a map, Live takes over ----------
const PREP_LEN=[5,10,20,30];
const PREP_NOTE={5:"Aim, then your map sheets.",10:"Aim, the lineups of your maps, then the sheets.",20:"Aim, the training server on your first map, lineups, deathmatch.",30:"Like 20 min with more time on the training server, the lineups and deathmatch."};
const PREP={tick:null,watch:null};
// what you chose today (your browser): the step, the maps, the duration, the blocks done, the one running
function prepState(){const day=new Date().toDateString();let st=store("prep");
  if(!st||st.day!==day)st={day,step:1,maps:[],min:20,done:{},cur:null,t0:null};return st}
function prepSave(st){store("prep",st)}
// the program: blocks that add up to the duration chosen
function prepProgram(p,sel,min){const PL=p.advice.plan||{},W=((PL.training||{}).warmup)||[];
  const pick=(re,d)=>W.find(w=>re.test(w.map||""))||d;
  const aim=pick(/aim/i,{map:"Aim Botz",text:"Still bots, then strafing bots: first-shot accuracy.",why:"First-shot accuracy."});
  const dm=pick(/deathmatch/i,{map:"Deathmatch",text:"Your round weapon, aiming at head level only.",why:"Get into rhythm before the game."});
  const nr=(p.advice.rules||[]).find(r=>r.id==="nades"),M=sel.map(MAPN).join(", ");
  const B=[],add=(kind,mins,title,text,why)=>{if(mins>0)B.push({kind,mins,title,text,why})};
  add("aim",min>=30?5:min>=10?4:3,aim.map,aim.text,aim.why);
  if(min>=20)add("train",min>=30?12:8,`Training server · ${MAPN(sel[0])}`,"Your situations on this map, with bots on the paths the demos recorded: your posts to hold, the routes to push, then the deaths that cost rounds.","The map in your hands before the first round.");
  if(min>=10)add("nades",min>=30?5:min>=20?3:4,`Lineups · ${M}`,"The key grenades of your positions: paste a position in the console of a practice server (sv_cheats 1), throw each one twice.",nr?`${nr.short}: thrown, your grenades win rounds.`:"The utility of your positions, ready before the round.");
  if(min>=20)add("dm",min>=30?8:5,dm.map,dm.text,dm.why);
  if(min<20)add("sheet",2,"Your map sheets","Play, avoid, grenades, timing: each map in 60 seconds, just below.","The plan in your head before the first round.");
  return B}
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
// the key grenades of your maps, both sides, with their position for a practice server
function prepNades(p,sel){const rows=[];
  for(const mp of sel){const m=crossMap(p,mp),R0=!m?((p.advice.plan||{}).map_refs||{})[mp]:null;
    for(const side of ["T","CT"]){const d=planData(p,m,R0,mp,side);((d.Sd&&d.plan&&d.plan.key_nades)||[]).slice(0,2).forEach(k=>{const l=d.Sd.lineups[k];if(l&&l.setpos)rows.push({mp,side,l})})}}
  if(!rows.length)return `<p class="note">No key grenade found yet on these maps: Live's Grenades tab has the pro catalog.</p>`;
  return `<div class="pnades">${rows.map(({mp,side,l})=>`<div class="pnade"><span class="tag ${side.toLowerCase()}">${side}</span><b>${TYPE[l.type]||esc(l.type)}</b> ${esc(l.from_zone)} → ${esc(nTo(l,mp)||"?")}${l.t!=null?` · ${clock(l.t)}`:""}<span class="note"> · ${esc(MAPN(mp))}${l.how?" · "+esc(l.how):""}</span><div class="cmd"><code>${esc(l.setpos)}</code><button type="button">Copy</button></div></div>`).join("")}</div>`}
// your focus of the week (focus.py), and its change among the coach's next axes (Review and Prepare)
function focusCard(p,extra){const F=focusOf(p);
  if(!F)return `<article class="card b-next"><span class="eyebrow">Focus of the week</span><p class="note">The coach picks it once a few of your matches are analyzed.</p></article>`;
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
const fmtLeft=s=>`${Math.floor(Math.max(0,s)/60)}:${String(Math.floor(Math.max(0,s)%60)).padStart(2,"0")}`;
function renderPrepare(){
  const p=P(),v=$("#v-prepare"),PL=p.advice.plan;if(!PL)return noPlan(v);
  clearInterval(PREP.tick);
  const st=prepState(),own=D.local&&p.steamid===D.own,maps=mapsOf(p),sel=(st.maps||[]).filter(m=>maps.some(x=>x.map===m)).slice(0,3);
  if(st.step>1&&!sel.length)st.step=1;
  const B=sel.length?prepProgram(p,sel,st.min):[];
  const steps=[[1,"Maps & time"],[2,`Warm-up · ${st.min} min`],[3,"Ready"]];
  const step1=()=>`<section class="prep1">
    <h3>Which maps?</h3><p class="note">One to three: the warm-up and the sheets follow them. Your most played first.</p>
    <div class="btns prep-maps" role="group" aria-label="Maps">${maps.map(m=>`<button type="button" data-pmap="${esc(m.map)}" aria-pressed="${sel.includes(m.map)}">${esc(MAPN(m.map))} <span class="note">${m.n||0}</span></button>`).join("")}</div>
    <h3>How long?</h3>
    <div class="btns" role="group" aria-label="Duration">${PREP_LEN.map(n=>`<button type="button" data-pmin="${n}" aria-pressed="${st.min===n}">${n} min</button>`).join("")}</div>
    <p class="note">${PREP_NOTE[st.min]||""}</p>
    <div class="btns"><button type="button" class="primary" data-pgo ${sel.length?"":"disabled"}>Build my warm-up →</button></div>
    ${own?`<div style="margin-top:18px">${checkinCard((PL.context||{}).journal_n)}</div>`:""}</section>`;
  const block=(b,i)=>{const done=!!st.done[i],cur=st.cur===i,left=cur&&st.t0?b.mins*60-(Date.now()-st.t0)/1000:b.mins*60;
    return `<li class="pblk k-${b.kind}${done?" done":""}${cur?" cur":""}">
      <div class="pmin"><b>${b.mins}</b><span>min</span></div>
      <div class="pbody"><h4>${esc(b.title)}</h4><p>${esc(b.text)}</p><p class="note">Why: ${esc(b.why)}</p>
       ${b.kind==="nades"?prepNades(p,sel):""}
       ${b.kind==="train"&&own?`<div class="btns" data-ptrainbox style="align-items:center"><button type="button" data-ptrain="${i}">▶ Launch on the training server</button><span class="note" id="ptmsg" role="status"></span></div>`:""}</div>
      <div class="pact">${done?`<button type="button" data-pundo="${i}" title="Mark it not done">✓ Done</button>`:cur?`<b class="ptime" id="ptime">${fmtLeft(left)}</b><button type="button" data-pdone="${i}">Done</button>`:`<button type="button" class="primary" data-pstart="${i}">Start</button>`}</div></li>`};
  const step2=()=>`<section class="prep2"><ol class="prep-prog">${B.map(block).join("")}</ol>
    <div class="btns"><button type="button" data-pstep="3">I'm ready →</button></div>
    <h3>Your map sheets</h3><div class="psheets">${sel.map(mp=>mapSheet(p,mp)).join("")}</div></section>`;
  const step3=()=>{const recs=((PL.context||{}).recs||[]).filter(r=>r.kind==="stop"||r.kind==="tilt"),exps=((PL.experiments||{}).experiments||[]).filter(e=>e.status==="active"),nd=B.filter((b,i)=>st.done[i]).length;
    return `<section class="prep3"><div class="prep-ready">${focusCard(p)}
      <article class="card"><span class="eyebrow">Session rule</span><p class="lead">${esc(recs.length?recs[0].text:"A 10-15 min break after a loss, stop after 2 losses in a row.")}</p>${exps.map(e=>`<p class="note">Running experiment: ${esc(e.title)}</p>`).join("")}</article>
      <article class="card"><span class="eyebrow">Warm-up</span><p class="lead">${nd} of ${B.length} done</p><p class="note">${D.local?"When CS2 loads a map, this page hands over to Live by itself.":"Live follows your match in the local app."}</p><div class="btns"><a class="btnlink" href="#ingame">Open Live</a></div></article></div>
     <h3>Your maps</h3><div class="psheets">${sel.map(mp=>mapSheet(p,mp)).join("")}</div></section>`};
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)} · before you play</span><h2>Prepare</h2></div></div>
   <nav class="prep-steps" aria-label="Steps">${steps.map(([n,t])=>`<button type="button" data-pstep="${n}"${st.step===n?' aria-current="step"':""}${n>1&&!sel.length?" disabled":""}><b>${n}</b>${esc(t)}</button>`).join("")}</nav>
   ${st.step===1?step1():st.step===2?step2():step3()}`;
  const save=()=>{prepSave(st);renderPrepare()};
  $$("[data-pstep]",v).forEach(b=>b.onclick=()=>{st.step=+b.dataset.pstep;save()});
  $$("[data-pmap]",v).forEach(b=>b.onclick=()=>{const m=b.dataset.pmap,i=sel.indexOf(m);if(i>=0)sel.splice(i,1);else if(sel.length<3)sel.push(m);else return;
    st.maps=sel.slice();st.done={};st.cur=null;save()});
  $$("[data-pmin]",v).forEach(b=>b.onclick=()=>{st.min=+b.dataset.pmin;st.done={};st.cur=null;save()});
  const gb=$("[data-pgo]",v);if(gb)gb.onclick=()=>{st.step=2;save()};
  $$("[data-pstart]",v).forEach(b=>b.onclick=()=>{st.cur=+b.dataset.pstart;st.t0=Date.now();save()});
  const finish=i=>{st.done[i]=true;if(st.cur===i){st.cur=null;st.t0=null}if(B.every((b,k)=>st.done[k]))st.step=3;save()};
  $$("[data-pdone]",v).forEach(b=>b.onclick=()=>finish(+b.dataset.pdone));
  $$("[data-pundo]",v).forEach(b=>b.onclick=()=>{delete st.done[+b.dataset.pundo];save()});
  $$("[data-ptrain]",v).forEach(b=>b.onclick=async()=>{const i=+b.dataset.ptrain,msg=$("#ptmsg",v);b.disabled=true;if(msg)msg.textContent="Preparing the session and starting the server (about 15 s)…";
    try{const r=await api("/api/train/session",{sid:p.steamid,minutes:B[i].mins,where:sel[0],diff:trainDiff()});
      if(st.cur!==i){st.cur=i;st.t0=Date.now();prepSave(st)}
      if(msg)msg.textContent=`${r.blocks.map(x=>`${BLOCK[x.kind]} ${Math.round(x.seconds/60)}′`).join(" → ")}: CS2 joins the server, follow the screen.`;
      PREP.tick=null;setTimeout(()=>{if(S.view==="prepare")renderPrepare()},6000)}
    catch(e){if(msg)msg.textContent="Failed: "+e.message;b.disabled=false}});
  copyBtn(v);wireCheckin(v,p);wireFocus(v,p,renderPrepare);prepTrainCheck(v);
  if(st.cur!=null&&st.t0&&B[st.cur]){const b=B[st.cur];   // the block running: its clock, and done when it reaches zero
    PREP.tick=setInterval(()=>{const t=$("#ptime",v);if(!t||S.view!=="prepare"){clearInterval(PREP.tick);return}
      const left=b.mins*60-(Date.now()-st.t0)/1000;t.textContent=fmtLeft(left);if(left<=0){clearInterval(PREP.tick);finish(st.cur)}},1000)}}
// CS2 loads a map (not the training server): Live takes over
function prepWatch(){clearTimeout(PREP.watch);if(S.view!=="prepare"||!D.local)return;
  fetch("/api/gsi/state").then(r=>r.json()).then(g=>{if(S.view!=="prepare")return;
    if(g&&g.map&&!g.practice&&(g.age==null||g.age<30)&&g.map_phase&&g.map_phase!=="gameover"){if(D.own&&S.player!==D.own){S.view="ingame";setPlayer(D.own)}else go("ingame");return}
    PREP.watch=setTimeout(prepWatch,3000)}).catch(()=>{PREP.watch=setTimeout(prepWatch,6000)})}

// the training server not on this PC yet (a player's copy of the app, 05/10): installed from the warm-up's block, which
// then launches it
async function prepTrainCheck(v){const box=$("[data-ptrainbox]",v);if(!box||!D.local)return;
  let st;try{const r=await fetch("/api/train/status");if(!r.ok)return;st=await r.json()}catch(e){return}
  if(typeof st.installed!=="boolean"||!box.isConnected||S.view!=="prepare")return;   // an older local server: the launch button stays
  if(st.installed){if(!$("[data-ptrain]",box))renderPrepare();return}
  const ins=st.install||{};
  box.innerHTML=ins.running?`<span class="note"><span class="spin" aria-hidden="true"></span>Installing the training server: ${esc(ins.log||"…")}</span>`
    :`<button type="button" class="primary" data-pinstall>Install the training server</button><span class="note" role="status">${ins.error?`Failed: ${esc(ins.error)}`:"Once, a few minutes: a separate copy of CS2 next to the game, its files linked (no extra space, the game itself untouched)."}</span>`;
  const b=$("[data-pinstall]",box);
  if(b)b.onclick=async()=>{b.disabled=true;try{await api("/api/train/install",{})}catch(e){b.disabled=false;$(".note",box).textContent="Failed: "+e.message;return}prepTrainCheck(v)};
  if(ins.running)setTimeout(()=>prepTrainCheck(v),2500)}
