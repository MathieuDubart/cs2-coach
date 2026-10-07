// ---------- view: profile (05/10): Review's third level, what stays true over weeks. Your focus of the week and your
// strengths, your axes ranked by the coach's priority score (one list instead of a "Fix first" on every page), the
// evidence of each part of your game with the way to its detailed page, your tests ----------
const VIEW_LABEL={maps:"Maps",midround:"Mid-round",progress:"Progress",analysis:"Full analysis",routine:"Routine"};
function renderProfile(){
  const p=P(),v=$("#v-profile"),A=p.advice||{},PL=A.plan||{},ms=p.matches||[],own=D.local&&p.steamid===D.own;
  const rules=(A.rules||[]).slice(0,8),mx=Math.max(1,...rules.map(r=>r.score||0)),F=focusOf(p),X=PL.experiments||null;
  const act=X?(X.experiments||[]).filter(e=>e.status==="active"):[],sug=X?(X.suggested||[]):[];
  const win=ms.filter(m=>m.result==="win").length,loss=ms.filter(m=>m.result==="loss").length,draw=ms.length-win-loss;
  const role=(A.archetype||{}).name||((PL.role||{}).role)||null;
  const auto=(A.rules||[]).map((r,i)=>({level:i<2?"high":"mid",title:r.title,evidence:r.why,fix:r.do,standing:r.standing,target:r.target,bench:r.bench,drills:r.drills,sources:r.sources}));
  // each part of your game: the "works" and "costs" of its detailed page, and the way there
  const topMaps=mapsOf(p).filter(m=>m.n>0).slice(0,2).map(m=>crossMap(p,m.map)).filter(Boolean);
  const parts=[["analysis","My reads","your duels and reads, against the base and the pros",ms.length?briefOf(analysisBrief,p,auto):null],
    ["midround","Mid-round decisions","rotations, executes, after the first duel",PL.mid?briefOf(midBrief,PL):null],
    ...topMaps.map(m=>["maps",MAPN(m.map),`${m.matches} of your matches there`,briefOf(mapBrief,p,m),m.map]),
    ["progress","Weapons, buys and trends","your weapons, your buys by kind of round, your indicators",PL.kpis||PL.weapons?briefOf(progBrief,PL):null],
    ["routine","Habits","time of day, session length, group",PL.context?briefOf(routineBrief,PL):null]].filter(x=>x[3]);
  const li=xs=>(xs||[]).filter(Boolean).slice(0,2).map(x=>`<li>${x}</li>`).join("");
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)}${PL.level?` · ${levelLine(PL.level)}`:""}</span><h2>Your profile</h2></div>
    ${ms.length?`<div class="record"><span>${win}<small>wins</small></span><span>${draw}<small>draws</small></span><span>${loss}<small>losses</small></span></div>`:""}</div>
   <p class="note">What stays true over weeks${ms.length?`, from ${ms.length} analyzed matches`:""}${role?` · your role: <b>${esc(role)}</b>`:""}.</p>
   <h3>Your axes, ranked ${itip(`What costs you the most rounds, in my order (my priority score: the bar). One list for the whole app: the first is your focus of the week unless you picked another${F&&F.until&&!isNaN(new Date(F.until))?` (until ${new Date(F.until).toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})})`:""}. What works for you is in the evidence, part by part, below.`)}</h3>
   ${rules.length?`<div class="axes-list">${rules.map((r,i)=>{const isF=F&&F.id===r.id;return `<article class="axis${isF?" is-focus":""}">
     <div class="ax-n">${i+1}</div>
     <div class="ax-b"><h4>${esc(r.short||r.title)}</h4>${r.short&&r.title&&r.short!==r.title?`<p class="note">${esc(r.title)}</p>`:""}
      ${(r.why||[]).length?`<ul>${r.why.slice(0,2).map(t=>`<li>${esc(t)}</li>`).join("")}</ul>`:""}
      ${(r.do||[]).length?`<p><b>Fix:</b> ${esc(r.do[0])}</p>`:""}${(r.drills||[]).length?`<p class="note">Drill: ${esc(r.drills[0])}</p>`:""}</div>
     <div class="ax-s"><div class="ax-bar" title="priority ${Math.round(r.score||0)}"><i style="width:${Math.round(100*(r.score||0)/mx)}%"></i></div>
      ${isF?`<span class="pill strong">focus of the week</span>`:own?`<button type="button" data-axfocus="${esc(r.id)}">Make it my focus</button>`:""}</div></article>`}).join("")}</div>`
     :`<p class="note">No axis yet: I rank them once a few of your matches are analyzed with their demo.</p>`}
   ${parts.length?`<h3>The evidence, part by part</h3><div class="evid">${parts.map(([view,t,sub,o,mp])=>`<article class="card ev">
     <div class="ev-h"><b>${esc(t)}</b><span class="note">${esc(sub)}</span></div>
     ${li(o.works)?`<p class="lab good">Works</p><ul>${li(o.works)}</ul>`:""}${li(o.fix)?`<p class="lab bad">Costs</p><ul>${li(o.fix)}</ul>`:""}${o.next?`<p class="note"><b>To try:</b> ${o.next}</p>`:""}
     <a href="#${view}" class="ev-go"${mp?` data-evmap="${esc(mp)}"`:""}>${esc(VIEW_LABEL[view]||t)} in detail →</a></article>`).join("")}</div>`:""}
   ${X?`<h3>Your tests ${itip(`You start a test and play normally: I compare your next matches with your previous 15 and give a verdict once there is enough data.${D.local?"":" Starting or ending one happens in the local app."}`)}</h3>
    ${act.length?`<div class="exps">${act.map(expCard).join("")}</div>`:`<p class="note">No test running.</p>`}
    ${sug.length?`<span class="lbl4" style="color:var(--muted)">Worth testing</span><div class="exps">${sug.slice(0,4).map(suggestCard).join("")}</div>`:""}
    <p class="note" id="xmsg" role="status"></p>`:""}
`;
  if(X)wireExp(v,X,p);
  wireFocus(v,p,renderProfile);
  $$("[data-axfocus]",v).forEach(b=>b.onclick=async()=>{b.disabled=true;
    try{const j=await api("/api/focus",{sid:p.steamid,id:b.dataset.axfocus});const A_=p.advice;A_.plan=A_.plan||{};A_.plan.focus=j.focus;navUpdate(S.view);renderProfile()}
    catch(e){b.disabled=false;b.textContent=e.message}});
  $$("[data-evmap]",v).forEach(a=>a.onclick=()=>{S.cmap=a.dataset.evmap})}
