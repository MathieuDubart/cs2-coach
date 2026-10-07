// ---------- view: profile (05/10): Review's third level, what stays true over weeks. Your focus of the week and your
// strengths, your axes ranked by the coach's priority score (one list instead of a "Fix first" on every page), the
// evidence of each part of your game with the way to its detailed page, your tests ----------
const VIEW_LABEL={maps:"Maps",midround:"Mid-round",progress:"Progress",analysis:"Full analysis",routine:"Routine"};
// an axis's evidence and every fix (07/10: the Full analysis listed the same axes again with these; said once, here)
function axisMore(r){const why=(r.why||[]).slice(2),fx=(r.do||[]).slice(1),dr=(r.drills||[]).slice(1),src=r.sources||[];
  if(!r.standing&&!why.length&&!fx.length&&!dr.length&&!src.length)return "";
  return `<details class="ax-more"><summary>The numbers, every fix and drill, the sources</summary>
   ${r.standing?`<div class="standing"><span>${esc(r.standing)}</span>${benchExtra(r.bench)}${r.target?`<span class="tg">${esc(r.target)}</span>`:""}</div>`:""}
   ${why.length?`<ul>${why.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>`:""}
   ${fx.length?`<p class="mini">Also:</p><ul>${fx.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>`:""}
   ${dr.length?`<p class="mini">Other drills:</p><ul class="drills">${dr.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>`:""}
   ${src.length?`<div class="srcs"><span class="note">Sources:</span>${src.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>`).join("")}</div>`:""}</details>`}
function renderProfile(){
  const p=P(),v=$("#v-profile"),A=p.advice||{},PL=A.plan||{},ms=p.matches||[],own=D.local&&p.steamid===D.own;
  const rules=(A.rules||[]).slice(0,8),mx=Math.max(1,...rules.map(r=>r.score||0)),F=focusOf(p),X=PL.experiments||null;
  const act=X?(X.experiments||[]).filter(e=>e.status==="active"):[],old=X?(X.experiments||[]).filter(e=>e.status!=="active"):[],sug=X?(X.suggested||[]):[];
  const axIn=(r,i)=>i<3||F&&F.id===r.id,axVis=rules.map((r,i)=>[r,i]).filter(([r,i])=>axIn(r,i)),axRest=rules.map((r,i)=>[r,i]).filter(([r,i])=>!axIn(r,i));
  const win=ms.filter(m=>m.result==="win").length,loss=ms.filter(m=>m.result==="loss").length,draw=ms.length-win-loss;
  const role=(A.archetype||{}).name||((PL.role||{}).role)||null;
  const auto=(A.rules||[]).map((r,i)=>({level:i<2?"high":"mid",title:r.title,evidence:r.why,fix:r.do,standing:r.standing,target:r.target,bench:r.bench,drills:r.drills,sources:r.sources}));
  const axCard=(r,i)=>{const isF=F&&F.id===r.id;return `<article class="axis${isF?" is-focus":""}">
     <div class="ax-n">${i+1}</div>
     <div class="ax-b"><h4>${esc(r.short||r.title)}</h4>${r.short&&r.title&&r.short!==r.title?`<p class="note">${esc(r.title)}</p>`:""}
      ${(r.why||[]).length?`<ul>${r.why.slice(0,2).map(t=>`<li>${esc(t)}</li>`).join("")}</ul>`:""}
      ${(r.do||[]).length?`<p><b>Fix:</b> ${esc(r.do[0])}</p>`:""}${(r.drills||[]).length?`<p class="note">Drill: ${esc(r.drills[0])}</p>`:""}${axisMore(r)}</div>
     <div class="ax-s"><div class="ax-bar" title="priority ${Math.round(r.score||0)}"><i style="width:${Math.round(100*(r.score||0)/mx)}%"></i></div>
      ${isF?`<span class="pill strong">focus of the week</span>`:own?`<button type="button" data-axfocus="${esc(r.id)}">Make it my focus</button>`:""}</div></article>`};
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)}${PL.level?` · ${levelLine(PL.level,true)}`:""}</span><h2>Your profile</h2></div>
    ${ms.length?`<div class="record"><span>${win}<small>wins</small></span><span>${draw}<small>draws</small></span><span>${loss}<small>losses</small></span></div>`:""}</div>
   <p class="note">What stays true over weeks${ms.length?`, from ${ms.length} analyzed matches`:""}${role?` · your role: <b>${esc(role)}</b>`:""}.</p>
   <h3>Your axes, ranked ${itip(`What costs you the most rounds, in my order (my priority score: the bar). One list for the whole app: the first is your focus of the week unless you picked another${F&&F.until&&!isNaN(new Date(F.until))?` (until ${new Date(F.until).toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})})`:""}. What works for you is in the evidence, part by part, below.`)}</h3>
   ${rules.length?`<div class="axes-list">${axVis.map(([r,i])=>axCard(r,i)).join("")}</div>${fold(`${axRest.length} more ax${axRest.length>1?"es":"is"}`,axRest.length?`<div class="axes-list">${axRest.map(([r,i])=>axCard(r,i)).join("")}</div>`:"","axes-more")}`
     :`<p class="note">No axis yet: I rank them once a few of your matches are analyzed with their demo.</p>`}
   ${X?`<h3>Your tests ${itip(`You start a test and play normally: I compare your next matches with your previous 15 and give a verdict once there is enough data.${D.local?"":" Starting or ending one happens in the local app."}`)}</h3>
    ${act.length?`<div class="exps">${act.map(expCard).join("")}</div>`:`<p class="note">No test running.</p>`}
    ${sug.length?`<span class="lbl4" style="color:var(--muted)">Worth testing</span><div class="exps">${sug.slice(0,2).map(suggestCard).join("")}</div>`:""}
    ${fold(`${sug.length-2} more idea${sug.length>3?"s":""} to test`,sug.length>2?`<div class="exps">${sug.slice(2).map((s,i)=>suggestCard(s,i+2)).join("")}</div>`:"","x-ideas")}
    ${fold(`Finished tests (${old.length})`,old.length?`<div class="exps">${old.map(expCard).join("")}</div>`:"","x-old")}
    <p class="note" id="xmsg" role="status"></p>`:""}
`;
  if(X)wireExp(v,X,p);
  wireFocus(v,p,renderProfile);
  $$("[data-axfocus]",v).forEach(b=>b.onclick=async()=>{b.disabled=true;
    try{const j=await api("/api/focus",{sid:p.steamid,id:b.dataset.axfocus});const A_=p.advice;A_.plan=A_.plan||{};A_.plan.focus=j.focus;navUpdate(S.view);renderProfile()}
    catch(e){b.disabled=false;b.textContent=e.message}});
}
