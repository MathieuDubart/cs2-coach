
// ---------- shared: sources, local API ----------
const srcLinks=(l,sm,lab)=>l&&l.length?`<div class="srcs${sm?" sm":""}"><span class="note">${lab||"Sources:"}</span>${l.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>`).join("")}</div>`:"";
async function api(path,body){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||"local server error");return j}
async function reloadPlayer(){const id=S.player;delete D.players[id];await loadPlayer(id,true);RENDER[S.view]()}
const lc=s=>s?s.charAt(0).toLowerCase()+s.slice(1):s;
const WNAME={awp:"AWP",scout:"Scout",rifle:"Rifles",rifle_eco:"Galil / FAMAS",smg:"SMG",shotgun:"Shotguns",pistol:"Pistol",heavy:"Machine gun",auto:"Auto-sniper",pro_awp:"Pro AWPers"};
// short (the Profile's line): the level and the hours; Premier, ranks, wins and the account's age are the Full analysis'
// public profile (07/10: said once)
function levelLine(L,short){if(!L)return "";const bits=[];
  if(L.rating&&!short)bits.push(`Premier ${esc(L.season||"")}: ${L.rating.toLocaleString("en-US")}`);
  if(L.comp&&!short)bits.push(`${esc(L.comp)} in Competitive`);
  const xp=[L.hours!=null?`${L.hours.toLocaleString("en-US")} h of CS2${L.two_weeks_h!=null?`, ${L.two_weeks_h} h in the last 2 weeks`:""}`:"",
    L.wins&&!short?`${L.wins} Competitive wins`:"",L.premier_wins&&!short?`${L.premier_wins} in Premier`:"",L.since&&!short?`Steam account since ${L.since}`:""].filter(Boolean).join(", ");
  return `${L.name?`level ${esc(L.name)}`:"unknown level"}${bits.length?` · ${bits.join(" · ")}`:""} · ${esc(L.experience)} player${xp?` (${xp})`:""}`}

// ---------- view: routine ----------
let partySel=null,ckState={};
const LVL={"reliable":"reliable","trend":"trend","no clear gap":"no clear gap","not enough data":"too few games"};
const lvlCls=l=>l==="reliable"?"reliable":l==="trend"?"trend":"";
function phaseCard(ph){return `<article class="phase"><h3>${esc(ph.title)}</h3>${ph.items.map(i=>`<div class="tip"><b>${esc(i.title)}</b><p>${esc(i.text)}</p>
  ${i.do&&i.do.length?`<ul>${i.do.map(d=>`<li>${esc(d)}</li>`).join("")}</ul>`:""}${srcLinks(i.src,true)}</div>`).join("")}</article>`}
function contextBlock(C){
  const pf=v=>v==null?"—":v.toFixed(2),recs=C.recs||[];
  const src=Object.entries(C.sources_count||{}).map(([k,n])=>`${n} ${k==="demo"?"with a demo":k==="steam"?"from the Steam history":"from Leetify"}`).join(", ");
  return `<article class="card"><h3>Your playing habits ${itip(`${C.n} dated matches (${src}) · ${C.sessions.n} session${C.sessions.n>1?"s":""} of ${C.sessions.avg_games} game(s) on average, ${C.sessions.max_games} at most · ${C.sessions.games_after_2_losses} game(s) started after 2 losses in a row · journal: ${C.journal_n} entr${C.journal_n===1?"y":"ies"}. "Rating": match rating on the HLTV 2.0 model (1.00 = average player of the lobby). Your average: ${pf(C.overall.perf)}.`)}</h3>
   ${D.local&&!(C.sources_count||{}).steam?`<p class="note">To measure your habits over your whole history (not only demos), connect your Steam history: <a href="#settings" style="color:var(--ct)">Settings</a>.</p>`:""}
   ${recs.length?`<ul class="pl-list">${recs.map(r=>`<li class="coach">${esc(r.text)} <span class="lvl ${lvlCls(r.level)}">${esc(LVL[r.level]||r.level)}</span></li>`).join("")}</ul>`
     :`<p>No reliable personal rule yet: it takes more matches. Meanwhile, apply the general rules of "After the game".</p>`}
   ${fold(`Every situation: time of day, game of the session, after a loss, group, rest (${C.n} games)`,`<div class="tbl"><table><thead><tr><th>Situation</th><th class="n">Games</th><th class="n">W-L</th><th class="n">Wins</th><th class="n">Rating</th><th class="n">Rating gap</th><th>Reliability</th></tr></thead><tbody>
   ${C.factors.map(f=>`<tr><td class="grp" colspan="7">${esc(f.title)}</td></tr>`+f.rows.map(r=>`<tr><td>${esc(r.group)}</td><td class="n">${r.n}</td><td class="n">${r.w}-${r.l}</td>
     <td class="n">${r.winrate==null?"—":r.winrate+"%"}</td><td class="n">${pf(r.perf)}</td>
     <td class="n ${lvlCls(r.level)&&r.delta!=null?(r.delta>0?"good":"bad"):""}">${r.delta==null?"—":(r.delta>0?"+":"")+pf(r.delta)}</td>
     <td><span class="lvl ${lvlCls(r.level)}">${esc(LVL[r.level]||r.level)}</span></td></tr>`).join("")).join("")}
   </tbody></table></div>
   ${C.partners&&C.partners.length?`<p><b>Regular partners</b> (seen on your team in at least 2 matches): ${C.partners.map(x=>`${esc(x.name)} ${x.w}W-${x.l}L, rating ${pf(x.perf)} over ${x.n} games`).join(" · ")}</p>`:""}
   ${srcLinks([C.rating_source],true)}`,"rt-table")}</article>`}
// your journal: only on your own profile; folded until it becomes a habit (3 entries), with its count
function checkinCard(nj){
  if(!D.local)return `<article class="card"><h3>Pre-session journal</h3><p class="note">The journal (sleep, energy, warm-up) is filled in the local app: double-click <code>Wily.bat</code>.</p></article>`;
  const b=(k,vals)=>`<div class="btns" role="group" data-ck="${k}">${vals.map(([val,t])=>`<button type="button" data-v="${val}" aria-pressed="${String(ckState[k])===String(val)}">${t}</button>`).join("")}</div>`;
  const five=[[1,"1"],[2,"2"],[3,"3"],[4,"4"],[5,"5"]];
  return `<article class="card form"><details${(nj||0)>=3?" open":""}><summary style="cursor:pointer;font-family:var(--f-display);font-size:20px;font-weight:600">Pre-session journal <span class="note" style="font:13px var(--f-body)">· ${nj?`${nj} entr${nj>1?"ies":"y"} so far`:"not used yet"}</span></summary>
   <p class="note">20 seconds before your first game. Each entry is linked to the matches of the next 6 hours: over the weeks, I measure how your sleep, energy and warm-up affect your rating.</p>
   <div class="row"><label class="f" for="ck-sleep">Sleep (hours)</label><input id="ck-sleep" type="number" min="0" max="14" step="0.5" value="${esc(ckState.sleep_h??"")}"></div>
   <div class="row"><span class="f">Energy (1-5)</span>${b("energy",five)}</div>
   <div class="row"><span class="f">Mood (1-5)</span>${b("mood",five)}</div>
   <div class="row"><span class="f">Warm-up</span>${b("warmup",[["none","none"],["short","under 10 min"],["full","15 min or more"]])}</div>
   <div class="row"><span class="f">Caffeine</span>${b("caffeine",[["yes","yes"],["no","no"]])}</div>
   <div class="row"><span class="f">Group</span>${b("party",[["solo","solo"],["duo","duo"],["trio","trio"],["quatuor","4-stack"],["five","5-stack"]])}</div>
   <div class="row"><label class="f" for="ck-note">Goal</label><input id="ck-note" type="text" value="${esc(ckState.note??"")}" placeholder="Your goal for the session"></div>
   <div class="row"><button type="button" class="primary" id="ck-save">Save</button><span class="note" id="ck-msg" role="status"></span></div></details></article>`}
function partyBlock(PL){const P_=PL.party;if(!P_)return "";const keys=["solo","duo","trio","quatuor","five"],cur=partySel||PL.party_mode||"solo",x=P_[cur];
  const how={solo:"solo",duo:"as a duo",trio:"as a trio",quatuor:"as a 4-stack",five:"as a 5-stack"};
  return `<article class="card"><h3>Depending on your group</h3>${PL.party_mode?`<p class="note">From the teammates who keep showing up in your matches, you mostly play ${how[PL.party_mode]}.</p>`:""}
   <div class="btns" role="group" aria-label="Group size">${keys.map(k=>`<button type="button" data-party="${k}" aria-pressed="${k===cur}">${esc(P_[k].title)}</button>`).join("")}</div>
   <ul>${x.items.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>${srcLinks(x.src,true)}</article>`}
function metaBlock(PL){if(!PL.meta||!PL.meta.length)return "";
  return `<h3>What changed in the game</h3><p class="note">Research of ${esc(PL.updated)}: patches, map pool and what they mean for your game.</p>
  <div class="meta-list">${PL.meta.map(m=>`<article><span class="eyebrow">${esc(m.date)}</span><b>${esc(m.title)}</b><p>${esc(m.text)}</p><p><b>For you:</b> ${esc(m.impact)}</p>${srcLinks(m.src,true)}</article>`).join("")}</div>`}
function noPlan(v){v.innerHTML=`<div class="empty">This player's plan isn't computed yet. Run their analysis again from the search bar ("Update" button).</div>`}
// ---------- the tabs' briefs (04/10) ----------
// mid-round: your weakest decisions against the base and the pros, your strengths, the fix or reflex to apply
function midBrief(PL){const M=PL.mid;if(!M)return "";const wk=M.weak.filter(w=>w.id!=="note"),pb=(PL.playbook||[]).find(x=>x.prio>0);
  const ln=w=>`<b>${esc(w.label[0].toUpperCase()+w.label.slice(1))}</b>: you ${fmtU(w.you,w.unit)} <span class="note">· base ${fmtU(w.median,w.unit)}${w.pro!=null?`, pros ${fmtU(w.pro,w.unit)}`:""}</span>`;
  return tabBrief({id:"mr-brief",works:M.strong.slice(0,3).map(x=>esc(x.text)),fix:wk.slice(0,3).map(ln),
    next:wk[0]&&wk[0].fix?esc(wk[0].fix):pb?`If ${esc(lc(pb.if))} → ${esc(pb.then)}`:null,nextLabel:"In your next match"})}
// progress: what improves and what slips over your last 3 matches, the test to run
function progBrief(PL){const K=PL.kpis||[],X=PL.experiments||{},act=(X.experiments||[]).filter(e=>e.status==="active"),L=PL.level;
  const d=k=>k.recent-k.before,better=k=>k.higher_better?d(k)>0:d(k)<0,moved=k=>k.recent!=null&&k.before!=null&&Math.abs(d(k))>1e-9;
  const kl=k=>`${esc(k.label)}: <b>${fmtU(k.recent,k.unit)}</b> <span class="note">· before ${fmtU(k.before,k.unit)}</span>`;
  const nx=act[0]?`Keep testing: ${esc(act[0].title)}`:(X.suggested||[])[0]?`Start a test: ${esc(X.suggested[0].title)}`:L&&L.focus&&L.focus[0]?esc(L.focus[0]):null;
  return tabBrief({id:"pg-brief",works:K.filter(k=>moved(k)&&better(k)).map(kl),fix:K.filter(k=>moved(k)&&!better(k)).map(kl),next:nx,nextLabel:"This week",
    worksNone:"No indicator is improving over your last 3 matches yet.",fixNone:"No indicator is slipping over your last 3 matches."})}
// routine: the situations where you play clearly better or worse (time, session, group...), the first habit to keep
function routineBrief(PL){const C=PL.context,ph=(PL.phases||[])[0],first=ph&&ph.items&&ph.items[0];
  const rows=C?C.factors.flatMap(x=>x.rows.filter(r=>r.delta!=null&&(r.level==="reliable"||r.level==="trend")).map(r=>({...r,title:x.title}))):[];
  const rl=r=>`${esc(r.title)}: <b>${esc(r.group)}</b> <span class="note">· rating ${r.delta>0?"+":""}${r.delta.toFixed(2)} over ${r.n} games</span>`;
  return tabBrief({id:"rt-brief",works:rows.filter(r=>r.delta>0).sort((a,b)=>b.delta-a.delta).map(rl),fix:rows.filter(r=>r.delta<0).sort((a,b)=>a.delta-b.delta).map(rl),
    next:C&&C.recs&&C.recs[0]?esc(C.recs[0].text):first?`<b>${esc(first.title)}</b>: ${esc(first.text)}`:null,nextLabel:"Before your next session",
    worksNone:"No situation where you clearly play better yet.",fixNone:"No situation where you clearly play worse yet."})}
function renderRoutine(){
  const p=P(),v=$("#v-routine"),PL=p.advice.plan;if(!PL)return noPlan(v);
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)}</span><h2>Your habits</h2></div></div>
   ${routineBrief(PL)}${anchor("rt-habits")}
   <div class="pg-grid2">${P().steamid===D.own?checkinCard((PL.context||{}).journal_n):""}${PL.context?contextBlock(PL.context):`<article class="card"><h3>Your playing habits</h3><p class="note">No dated match for this player: habits (times, sessions, group) need demos or a Leetify history.</p></article>`}</div>
   ${fold("Your routine: before, during and after the game",`<div class="phases">${PL.phases.map(phaseCard).join("")}</div>`,"rt-phases")}
   ${fold("Depending on your group",partyBlock(PL),"rt-group")}
   ${fold("What changed in the game lately",metaBlock(PL),"rt-meta")}`;
  wireCheckin(v,p);
  $$("[data-party]",v).forEach(b=>b.onclick=()=>{partySel=b.dataset.party;renderRoutine()});
}
// the journal's controls (Routine and Prepare)
function wireCheckin(v,p){
  $$("[data-ck]",v).forEach(g=>$$("button",g).forEach(bt=>bt.onclick=()=>{ckState[g.dataset.ck]=bt.dataset.v;press(g,"button",bt)}));
  const sl=$("#ck-sleep",v),nt=$("#ck-note",v);if(sl)sl.oninput=()=>ckState.sleep_h=sl.value;if(nt)nt.oninput=()=>ckState.note=nt.value;
  const sv=$("#ck-save",v);if(sv)sv.onclick=async()=>{sv.disabled=true;const msg=$("#ck-msg",v);
    try{const j=await api("/api/checkin",{sid:p.steamid,...ckState});ckState={};msg.textContent=`Saved: ${j.n} entr${j.n===1?"y":"ies"} in your journal.`;
      $$("[data-ck] button",v).forEach(x=>x.setAttribute("aria-pressed","false"));if(sl)sl.value="";if(nt)nt.value=""}
    catch(e){msg.textContent="Failed: "+e.message}sv.disabled=false}}

// ---------- view: mid-round ----------
let pbSide="me",midMap=null,wpSide=null;
const isBoth=x=>x.side==="both"||x.side==="tous";
function midMetricRows(B){const rows=Object.entries(B.metrics).filter(([k,m])=>m.you!=null).sort((a,b)=>(a[1].percentile??101)-(b[1].percentile??101));
  const col=q=>q<30?"var(--bad)":q<60?"var(--warn)":"var(--good)";
  return `<div class="card bench wide">${rows.map(([k,m])=>`<div class="row"><span class="lb">${esc(m.label[0].toUpperCase()+m.label.slice(1))}${m.higher_better==null?' <span class="note">(indicative)</span>':""}</span>
    <div class="pbar" title="${m.percentile==null?"Neither good nor bad in itself":`Better than ${m.percentile}% of players`}">${m.percentile==null?"":`<i style="width:${Math.max(2,m.percentile)}%;background:${col(m.percentile)}"></i>`}<b></b></div>
    <span class="v">you ${fmtU(m.you,m.unit)} · med. ${fmtU(m.median,m.unit)}${m.pro!=null?` · pros ${fmtU(m.pro,m.unit)}`:""}</span></div>`).join("")}</div>`}
function rotCard(site,r){const s=x=>x==null?"—":x+" s",pc=x=>x==null?"—":x+"%";
  const my=r.n?Math.round(100*r.died_way/r.n):null,bd=r.base.died;
  return `<article class="card"><h3>Rotations to ${esc(site)}</h3>
   <div class="tbl"><table><thead><tr><th></th><th class="n">Leave after the hit</th><th class="n">Travel</th><th class="n">Deaths on the way</th><th class="n">Rotations</th></tr></thead><tbody>
    <tr><td>You</td><td class="n">${s(r.react)}</td><td class="n">${s(r.travel)}</td><td class="n ${my!=null&&bd!=null?(my>=bd+10?"bad":my<=bd-10?"good":""):""}">${pc(my)}</td><td class="n">${r.n}</td></tr>
    <tr><td>Base</td><td class="n">${s(r.base.react)}</td><td class="n">${s(r.base.travel)}</td><td class="n">${pc(bd)}</td><td class="n">${r.base.n??"—"}</td></tr>
    <tr><td>Pros</td><td class="n">${s(r.pro.react)}</td><td class="n">${s(r.pro.travel)}</td><td class="n">${pc(r.pro.died)}</td><td class="n">${r.pro.n??"—"}</td></tr></tbody></table></div>
   <ul>${r.mine.length?`<li><b>Your routes:</b> ${r.mine.map(x=>`${esc(x.route)}${x.n>1?` ×${x.n}`:""}`).join(" · ")}</li>`:""}
    ${r.base.best?`<li><b>Safest in the base:</b> ${esc(r.base.best.route)} (${s(r.base.best.travel)}, ${r.base.best.died}% deaths on the way, ${r.base.best.n} rotations)</li>`:""}
    ${r.pro.best?`<li><b>Safest among pros:</b> ${esc(r.pro.best.route)} (${s(r.pro.best.travel)}, ${r.pro.best.died}% deaths, ${r.pro.best.n} rotations)</li>`:""}</ul>
   ${Object.keys(r.base.by_weapon||{}).length?`<details><summary style="cursor:pointer" class="note">Routes by weapon (base)</summary><ul class="note">${Object.entries(r.base.by_weapon).map(([w,x])=>`<li><b>${esc(WNAME[w]||w)}</b>: ${x.routes.map(y=>esc(y.route)).join(" or ")} · ${x.died}% deaths on the way over ${x.n} rotations</li>`).join("")}</ul></details>`:""}
  </article>`}
function wpBlock(W,side){const cl=W&&W[side];if(!cl)return `<p class="note">Not enough rounds on this map for this side.</p>`;
  const order=["awp","pro_awp","rifle","rifle_eco","smg","shotgun","scout"];
  return `<div class="insights wide">${order.filter(k=>cl[k]&&cl[k].zones.length).map(k=>{const x=cl[k],pro=k==="pro_awp";
    const lab=k==="rifle"?(side==="T"?"Rifles (AK-47, SG 553)":"Rifles (M4, AUG)"):k==="rifle_eco"?(side==="T"?"Galil AR":"FAMAS"):x.label;
    return `<article class="card"><h3>${esc(lab)}</h3><span class="note">${x.rounds} rounds${pro?" with an AWP kill":""}</span>
    <div class="tbl"><table><thead><tr><th>Zone</th><th class="n">Share</th>${pro?"":`<th class="n">Duels won</th><th class="n">Rounds won</th>`}</tr></thead><tbody>
    ${x.zones.map(z=>`<tr><td>${esc(z.name)}</td><td class="n">${z.share}%</td>${pro?"":`<td class="n ${z.duel_win!=null&&z.duel_win>=55?"good":z.duel_win!=null&&z.duel_win<=42?"bad":""}">${z.duel_win==null?"—":z.duel_win+"%"} <span class="note">(${z.duels})</span></td><td class="n">${z.round_win}%</td>`}</tr>`).join("")}
    </tbody></table></div></article>`}).join("")}</div>`}
function renderMidround(){
  const p=P(),v=$("#v-midround"),PL=p.advice.plan;if(!PL)return noPlan(v);
  const M=PL.mid,all=PL.playbook||[],anyMe=all.some(x=>x.prio>0);if(pbSide==="me"&&!anyMe)pbSide="all";
  const pb=all.filter(x=>pbSide==="all"||(pbSide==="me"?x.prio>0:(x.side===pbSide||isBoth(x))));
  const maps=bombFirst([...new Set([...Object.keys(PL.routes||{}),...Object.keys(PL.weapon_positions||{})])]);
  if(!midMap||!maps.includes(midMap))midMap=maps.includes(S.map)&&!HOST(S.map)?S.map:maps[0];
  const R=(PL.routes||{})[midMap]||{},W=(PL.weapon_positions||{})[midMap],ws=W?Object.keys(W).sort():[];
  if(!wpSide||!ws.includes(wpSide))wpSide=ws.includes(S.side)?S.side:ws[0];
  const B=M&&M.bench,pbCard=x=>`<article class="pbc ${isBoth(x)?"":x.side}">${x.prio>0?`<span class="you">Priority for you</span>`:""}<span class="eyebrow">${isBoth(x)?"CT and T":x.side}</span>
     <span class="if">If ${esc(lc(x.if))}</span><span>→ ${esc(x.then)}</span><span class="why">${esc(x.why)}</span>${srcLinks(x.src,true)}</article>`;
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)}${B?` · ${B.matches} matches · compared with ${B.n_players} players of the base and ${B.n_pros} pros`:""}</span><h2>Mid-round: movement and decisions</h2></div></div>
   ${midBrief(PL)}${anchor("mr-decisions")}
   ${M?`${M.weak.length?`<div class="insights">${M.weak.map(w=>`<article class="card"><h3>${w.id==="note"?"What pros do":esc(w.label[0].toUpperCase()+w.label.slice(1))}</h3>
       <p>${w.id==="note"?esc(w.text):`<span class="num">you ${fmtU(w.you,w.unit)}</span> · base median ${fmtU(w.median,w.unit)}${w.pro!=null?` · pros ${fmtU(w.pro,w.unit)}`:""}`}</p>
       ${w.fix?`<div class="fix"><h4>What to do</h4><p>${esc(w.fix)}</p></div>`:""}${w.percentile!=null?`<span class="note">You do better than ${w.percentile}% of the players of the base.</span>`:""}</article>`).join("")}</div>`:""}
     ${M.strong.length?`<div class="strengths">${M.strong.map(s=>`<span>${esc(s.text)}</span>`).join("")}</div>`:""}
     ${B?fold("All your mid-round indicators",`<p class="note">Bar: your percentile in the base (further right, you do better than most; the line marks the median). "Indicative": neither good nor bad in itself, read it with the rest.</p>${midMetricRows(B)}`,"mr-all"):""}`
     :`<div class="empty">Mid-round indicators need demos of this player. The reflexes below apply to everyone.</div>`}
   ${anchor("mr-reflexes")}<h3>If… then…: mid-round reflexes</h3>
   <div class="btns" role="group" aria-label="Filter the reflexes">${[...(anyMe?[["me","Priority for you"]]:[]),["all","All"],["CT","CT"],["T","T"]].map(([k,t])=>`<button type="button" data-pb="${k}" aria-pressed="${pbSide===k}">${t}</button>`).join("")}</div>
   <div class="pb">${pb.slice(0,4).map(pbCard).join("")}</div>
   ${fold(`${pb.length-4} more reflexes`,pb.length>4?`<div class="pb">${pb.slice(4).map(pbCard).join("")}</div>`:"","mr-reflexes")}
   ${maps.length?fold("Per map: rotations, and where to play with your weapon",`
   <div class="chips" role="group" aria-label="Map">${maps.map((m,i)=>`${chipSep(maps,i)}<button type="button" data-mm="${m}" aria-pressed="${m===midMap}">${MAPN(m)}</button>`).join("")}</div>
   ${Object.keys(R).length?`<div class="rot">${Object.entries(R).sort().map(([s,r])=>rotCard(s,r)).join("")}</div>
     <p class="note">"Leave": seconds between at least 2 Ts reaching the site and you leaving toward it (negative: you had left before). "Travel": from leaving to arriving. Routes: the first 3 zones crossed.</p>`
     :`<p class="note">No rotation of yours found on ${MAPN(midMap)}.</p>`}
   ${W?`<h3>Where to play with your weapon on ${MAPN(midMap)}</h3><div class="btns side" role="group" aria-label="Side">${ws.map(s=>`<button type="button" data-wps="${s}" aria-pressed="${s===wpSide}">${s}</button>`).join("")}</div>${wpBlock(W,wpSide)}
     <p class="note">Position of each player between ${clock(15)} and ${clock(25)} on the clock, depending on their weapon that round (matchmaking base). "Duels won": their duels in that zone. Pro AWPers: players who got an AWP kill in the round (HLTV demos).</p>`:""}
   ${(PL.videos||{})[midMap]?`${srcLinks(PL.videos[midMap],false,`Videos on ${MAPN(midMap)}:`)}`:""}`,"mr-maps"):""}`;
  $$("[data-pb]",v).forEach(b=>b.onclick=()=>{pbSide=b.dataset.pb;renderMidround()});
  $$("[data-mm]",v).forEach(b=>b.onclick=()=>{midMap=b.dataset.mm;renderMidround()});
  $$("[data-wps]",v).forEach(b=>b.onclick=()=>{wpSide=b.dataset.wps;renderMidround()});
}

// ---------- view: progress ----------
const WORKS=v=>v==="it works"||v==="ça marche",HURTS=v=>v==="it hurts"||v==="ça dégrade";
function expValue(x,unit){if(!x||x.value==null)return "—";return x.kind==="prop"?`${x.value}% (${x.k}/${x.n})`:fmtU(x.value,unit)}
function expCard(e){const pr=e.progress||[0,1,""],pct=Math.min(100,Math.round(100*pr[0]/Math.max(pr[1],1)));
  const cls=WORKS(e.verdict)?"strong":HURTS(e.verdict)?"weak":"";
  return `<article class="card exp"><div class="top"><span class="tag">${esc(e.category)}</span><span class="pill ${cls}">${e.status==="active"?"":"finished · "}${esc(e.verdict)}</span></div>
   <span class="ttl">${esc(e.title)}</span>
   <ul>${(e.how||[]).map(h=>`<li>${esc(h)}</li>`).join("")}</ul>
   <div class="prog" title="${pct}%"><i style="width:${pct}%"></i></div><span class="note">${pr[0]}/${pr[1]} ${esc(pr[2])} · started ${fmtDate(e.started)}${e.ended?` · finished ${fmtDate(e.ended)}`:""}</span>
   <div class="standing"><span>${esc(e.metric)}</span><span>before: ${expValue(e.before,e.unit)} · since: ${expValue(e.after,e.unit)}</span></div>
   ${e.status==="active"&&D.local?`<div class="btns"><button type="button" data-xstop="${e.id}">End the experiment</button></div>`:""}</article>`}
function suggestCard(s,i){return `<article class="card exp"><div class="top"><span class="tag">${esc(s.category)}</span></div><span class="ttl">${esc(s.title)}</span><p>${esc(s.why)}</p><span class="note">Measured with: ${esc(s.metric)}</span>${D.local?`<div class="btns"><button type="button" class="primary" data-xstart="${i}">Start</button></div>`:""}</article>`}
function kpiCard(k){const vals=k.series.map(x=>x[1]),W=200,H=40,mn=Math.min(...vals),mx=Math.max(...vals),rg=(mx-mn)||1;
  const pts=vals.map((y,i)=>`${(i/Math.max(vals.length-1,1)*W).toFixed(1)},${(H-4-(y-mn)/rg*(H-8)).toFixed(1)}`).join(" ");
  const d=k.recent-k.before,better=k.higher_better?d>0:d<0;
  return `<div class="kpi"><span class="note">${esc(k.label)}</span><b class="${Math.abs(d)<1e-9?"":better?"good":"bad"}">${fmtU(k.recent,k.unit)}</b>
   <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Trend over ${vals.length} matches"><polyline points="${pts}" fill="none" stroke="var(--ct)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>
   <span class="note">last 3 ${fmtU(k.recent,k.unit)} · before ${fmtU(k.before,k.unit)} · ${vals.length} matches</span></div>`}
function weaponsBlock(W){const RD=W.ref_duels||{};
  return `<h3>Your weapons ${itip(`Over ${W.n_rounds} analyzed rounds. Duels: kills and deaths with the weapon in hand, compared with every player of the base.`)}</h3>${W.suggestions.length?`<ul class="pl-list">${W.suggestions.map(s=>`<li class="${s.kind==="weapon_weak"?"avoid":/strong/.test(s.kind)?"exploit":"coach"}">${esc(s.text)}</li>`).join("")}</ul>`:""}
   ${fold(`Every weapon you played: kills, damage, survival and duels (${W.by_weapon.length})`,`<div class="tbl"><table><thead><tr><th>Main weapon of the round</th><th class="n">Rounds</th><th class="n">Kills / round</th><th class="n">Damage / round</th><th class="n">Survival</th><th class="n">Rounds won</th><th class="n">Duels won: you · base</th></tr></thead><tbody>
   ${W.by_weapon.map(x=>{const d=W.duels[x.key],r=RD[x.key];return `<tr><td>${esc(x.key)}</td><td class="n">${x.rounds}</td><td class="n">${f1(x.kpr)}</td><td class="n">${x.adr}</td><td class="n">${x.survival}%</td><td class="n">${x.win}%</td>
     <td class="n ${d&&r!=null&&d.n>=10?(d.win>=r+8?"good":d.win<=r-8?"bad":""):""}">${d?`${d.win}% <span class="note">(${d.n})</span>`:"—"} · ${r!=null?r+"%":"—"}</td></tr>`}).join("")}
   </tbody></table></div>
   ${W.force&&W.force.length?`<p class="note"><b>On force-buys:</b> ${W.force.filter(x=>x.rounds>=2).map(x=>`${esc(x.key)} ${x.adr} damage/round (${x.rounds} rounds)`).join(" · ")}</p>`:""}`,"pg-wtable")}`}
function buysBlock(B){if(!B||!B.types)return "";const T=B.types,p=P(),sw=s=>typeof expSwapTxt==="function"?expSwapTxt(p,s):s;
  const cell=(s,r)=>{const b=s&&s.kits&&s.kits[0];return b?`<b>${esc(sw(b.key))}</b> ${itip(b.why.map(esc).join(" · "),r)}${s.kits.length>1?`<br><span class="note">or ${s.kits.slice(1).map(y=>esc(sw(y.key))).join(", ")}</span>`:""}`:'<span class="note">not enough rounds</span>'};
  return `<h3>Your buys by type of round ${itip(`Adapted to you: your rounds first, then players of your profile (${(B.profile||[]).map(esc).join(", ")}), then the whole base, per side. All maps together; the detail per map is in "In game". Eco: the weapon only, what keeps your next full buy.${(typeof expSwaps==="function"?expSwaps(p):[]).length?" 🧪 = the weapon of your running experiment.":""}`)}</h3>
   <div class="tbl"><table><thead><tr><th>Round</th><th class="n">Your rounds</th><th class="n">Won: you · your profile</th><th>As T</th><th>As CT</th></tr></thead><tbody>
   ${["pistol","eco","force","full","anti-eco"].filter(k=>T[k]).map(k=>{const x=T[k],S2=x.sides||{};return `<tr><td><b>${esc(x.label)}</b></td><td class="n">${x.rounds}</td><td class="n">${x.win??"—"}% · ${x.peer_win??"—"}%</td>
     <td class="wrap">${cell(S2.T||(S2.CT?null:x))}</td><td class="wrap">${cell(S2.CT,true)}</td></tr>`}).join("")}</tbody></table></div>`}
function renderProgress(){
  const p=P(),v=$("#v-progress"),PL=p.advice.plan;if(!PL)return noPlan(v);
  const L=PL.level,Wp=PL.weapons,K=PL.kpis||[];
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)}</span><h2>Weapons and buys</h2></div></div>
   ${progBrief(PL)}
   ${Wp?anchor("pg-weapons")+weaponsBlock(Wp):""}
   ${PL.buys&&PL.buys.types?anchor("pg-buys"):""}${buysBlock(PL.buys)}
   ${fold(`At your level${L&&L.name?` (${esc(L.name)})`:""}, work on`,L&&L.focus.length?`<ol>${L.focus.map(f=>`<li>${esc(f)}</li>`).join("")}</ol>${srcLinks(L.src,true)}`:"","pg-level")}
   ${K.length?fold("Your indicators, match by match",`<p class="note">In color: the trend of your last 3 matches against the previous ones.</p><div class="kpis">${K.map(kpiCard).join("")}</div>`,"pg-kpis"):""}`;
}
// ---------- training: your situations played again on the local server (bots on the recorded paths) ----------
const TRAIN={map:null,timer:null};
const DIFF=["Easy","Normal","Hard","Expert"];
function trainDiff(){try{return +(localStorage.getItem("coach_diff")??2)}catch(e){return 2}}
function tPref(k,d){try{return localStorage.getItem("coach_t"+k)??d}catch(e){return d}}
function tSet(k,v){try{localStorage.setItem("coach_t"+k,v)}catch(e){}}
const BLOCK={defend:"🛡 Defense",push:"🚶 Push",aim:"🎯 Aim",nade:"💨 Stuff",situation:"🔁 Situations"};
// not on this PC yet (a player's copy of the app, 05/10): made from the app, CS2's files linked next to the game
function trainInstall(box,sid,st){const ins=st.install||{};
  box.innerHTML=`<div class="tinstall"><p><b>The training server isn't on this PC yet.</b> It is a separate copy of CS2 next to the game, where bots replay real situations of your matches. Its files are links to the game's: no extra space, and the game itself is never touched. Metamod:Source, CounterStrikeSharp and my plugin go in that copy only. It takes a few minutes.</p>
   ${ins.running?`<p class="note"><span class="spin" aria-hidden="true"></span>${esc(ins.log||"Installing…")}</p>`:`${ins.error?`<p class="note">Failed: ${esc(ins.error)}</p>`:""}<div class="btns"><button type="button" class="primary" id="t-install">Install the training server</button></div>`}
   ${st.path?`<p class="note">Folder: <code>${esc(st.path)}</code></p>`:""}</div>`;
  const b=box.querySelector("#t-install");
  if(b)b.onclick=async()=>{b.disabled=true;try{await api("/api/train/install",{})}catch(e){b.disabled=false;b.insertAdjacentHTML("afterend",`<span class="note">${esc(e.message)}</span>`);return}trainLoad(box,sid)};
  if(ins.running)TRAIN.timer=setTimeout(()=>{if(box.isConnected)trainLoad(box,sid)},2500)}
async function trainLoad(box,sid){clearTimeout(TRAIN.timer);
  let d;try{d=await (await fetch("/api/train?sid="+sid)).json()}catch(e){box.innerHTML=`<span class="note">The local server doesn't answer.</span>`;return}
  if(!box.isConnected)return;
  const st=d.status||{},R=d.results||{},sc=d.scenarios||[],P=d.progress||{level:1,xp:0,from:0,to:300,due:{}},M=d.maps||{},ss=st.session;
  if(!st.installed){trainInstall(box,sid,st);return}
  // the bots' level and the warm-up preselected from your last sessions and matches, unless you chose them in the last
  // 12 hours (04/10: "the bots' level preselected from my level in training")
  const sg=P.suggest||null,chose=Date.now()-(+tPref("at","0"))<12*3600e3;
  let mins=+tPref("min","20"),df=trainDiff();if(sg&&!chose){df=sg.diff;if(sg.warmup)mins=5}
  const where=tPref("where","random"),due=P.due||{},nd=Object.values(due).reduce((a,b)=>a+b,0);
  const pct=Math.max(0,Math.min(100,100*(P.xp-P.from)/Math.max(1,P.to-P.from)));
  const mapsTop=Object.keys(M).slice(0,8);
  const chip=(k,v,lab,on)=>`<button type="button" data-t${k}="${v}" aria-pressed="${on}">${lab}</button>`;
  // the session running: what the server says (block, drill, points)
  const live=ss&&st.running?`<div class="tlive"><b>●</b><span>${BLOCK[ss.block]||"Session"} · ${esc(ss.drill||"…")}</span><span>⭐ ${ss.points||0} · ${ss.ok||0}/${ss.done||0} ✔${ss.streak>=2?` · 🔥${ss.streak}`:""}</span><span>${ss.left?`${Math.floor(ss.left/60)}:${String(ss.left%60).padStart(2,"0")}`:""}</span>${st.humans?"":`<span class="note">waiting for you on the server</span>`}</div>`:"";
  const maps=[...new Set(sc.map(s=>s.map))];if(TRAIN.map&&!maps.includes(TRAIN.map))TRAIN.map=null;
  const list=sc.filter(s=>!TRAIN.map||s.map===TRAIN.map).slice(0,12);
  const lab=s=>s.kind==="clutch"?`1v${s.vs} clutch`:`death${s.opening?" · 1st":""}${s.traded?"":" · no trade"}`;
  const res=s=>{const r=R[s.id];return r&&r.tries?`<span class="tres ${r.won+r.survived?"ok":""}">${r.tries}× · ${r.won+r.survived} ✓</span>`:r&&r.watched?`<span class="tres">👁 ${r.watched}</span>`:`<span class="tres">new</span>`};
  box.innerHTML=`<div class="tplay">
     <div class="tlvl"><b>LVL ${P.level}</b><div class="tbar"><i style="width:${pct}%"></i></div><span>${P.xp} / ${P.to} XP</span>${nd?`<span class="tdue">🔁 ${nd} to redo</span>`:""}${P.mastered?`<span>⭐ ${P.mastered} mastered</span>`:""}</div>
     ${live}
     <div class="trow"><span class="tk2">⏱</span>${[5,10,20,30,45].map(m=>chip("min",m,m===5?"5 min · warm-up":m+" min",m===mins)).join("")}</div>
     <div class="trow"><span class="tk2">🗺</span>${chip("where","random","🎲 Random",where==="random")}${chip("where","mix","🔀 Mix",where==="mix")}${mapsTop.map(m=>chip("where",m,MAPN(m),where===m)).join("")}</div>
     <div class="trow"><span class="tk2">🤖</span>${DIFF.map((n,i)=>`<button type="button" data-tdiff="${i}" aria-pressed="${i===df}">${n}</button>`).join("")}${sg?`<span class="note">suggested: ${DIFF[sg.diff]} · ${esc(sg.why)}${sg.warmup?` · warm-up: ${esc(sg.warm_why)}`:""}</span>`:""}</div>
     <div class="trow"><button type="button" class="tbig" data-tgo>${ss&&st.running?"↻ NEW SESSION":"▶ PLAY"}</button>${ss&&st.running&&!st.humans?`<button type="button" data-tjoin>↪ Rejoin the server</button>`:""}${st.running?`<button type="button" data-tstop>Stop server</button>`:""}<span class="note" id="tmsg" role="status">${mins<=5?`${BLOCK.defend} → ${BLOCK.push}`:`${BLOCK.defend} → ${BLOCK.push} → ${BLOCK.nade} → ${BLOCK.situation}`}</span></div>
   </div>
   <details class="tcarte"><summary>Situations one by one (${sc.length})</summary>
   ${maps.length>1?`<div class="btns" role="group" aria-label="Map"><button type="button" data-tmap="" aria-pressed="${!TRAIN.map}">All</button>${maps.map(m=>`<button type="button" data-tmap="${m}" aria-pressed="${TRAIN.map===m}">${MAPN(m)}</button>`).join("")}</div>`:""}
   <div class="tlist">${list.map((s,i)=>`<div class="tsit ${st.scenario===s.id?"cur":""}"><b>${MAPN(s.map)} R${s.round}</b>
     <span class="tk ${s.kind}">${lab(s)}</span><span class="tz">${esc(s.zone||"")}${s.mine?` · ${esc(s.mine)}`:""}${s.by?` <span class="note">vs ${esc(s.by)} (${esc(s.weapon||"")})</span>`:""}</span>${res(s)}
     <button type="button" data-tplay="${i}" data-mode="actor">▶ Play</button><button type="button" data-tplay="${i}" data-mode="spec">👁 Watch</button></div>`).join("")||`<span class="note">No situation yet: the demos of your matches are needed.</span>`}</div>
   <p class="note">In game: <b>!r</b> again · <b>!n</b> next · <b>!p</b> previous · <b>!spec</b> watch / play · <b>!stop</b></p></details>`;
  if(TRAIN.open)$(".tcarte",box).open=true;
  $(".tcarte",box).ontoggle=e=>TRAIN.open=e.target.open;
  const msg=$("#tmsg",box);
  $$("[data-tmin]",box).forEach(b=>b.onclick=()=>{tSet("min",b.dataset.tmin);tSet("at",Date.now());trainLoad(box,sid)});
  $$("[data-twhere]",box).forEach(b=>b.onclick=()=>{tSet("where",b.dataset.twhere);trainLoad(box,sid)});
  $$("[data-tmap]",box).forEach(b=>b.onclick=()=>{TRAIN.map=b.dataset.tmap||null;trainLoad(box,sid)});
  $$("[data-tdiff]",box).forEach(b=>b.onclick=()=>{try{localStorage.setItem("coach_diff",b.dataset.tdiff)}catch(e){}tSet("at",Date.now());trainLoad(box,sid)});
  // the game crashed or was closed during a session: back on its server (04/10: "a rejoin button is missing")
  const jn=$("[data-tjoin]",box);if(jn)jn.onclick=async()=>{jn.disabled=true;msg.textContent="CS2 joins the server (started first if it is closed)…";
    try{await api("/api/train/join",{})}catch(e){msg.textContent="Failed: "+e.message;jn.disabled=false}};
  const sp=$("[data-tstop]",box);if(sp)sp.onclick=async()=>{sp.disabled=true;try{await api("/api/train/stop",{})}catch(e){msg.textContent="Failed: "+e.message}trainLoad(box,sid)};
  const go=$("[data-tgo]",box);if(go)go.onclick=async()=>{go.disabled=true;msg.textContent=st.running?"Preparing the session…":"Preparing the session and starting the server (about 15 s)…";
    try{const r=await api("/api/train/session",{sid,minutes:mins,where,diff:df});
      msg.innerHTML=`${r.blocks.map(b=>`${BLOCK[b.kind]} ${Math.round(b.seconds/60)}′`).join(" → ")} · ${r.session.maps.map(MAPN).join(", ")} — CS2 joins the server: follow the screen.`;
      setTimeout(()=>trainLoad(box,sid),4000)}
    catch(e){msg.textContent="Failed: "+e.message;go.disabled=false}};
  $$("[data-tplay]",box).forEach(b=>b.onclick=async()=>{const s=list[+b.dataset.tplay];$$("[data-tplay]",box).forEach(x=>x.disabled=true);
    msg.textContent=st.running?"Loading the situation…":"Starting the training server (about 10 s)…";
    try{const r=await api("/api/train/play",{sid,mid:s.mid,round:s.round,kind:s.kind,mode:b.dataset.mode,diff:df});
      msg.innerHTML=r.humans?`${esc(r.scenario.title)}: starting on the server.`:`Ready. In the CS2 console: <code>connect 127.0.0.1</code> (copied).`;
      if(!r.humans)try{navigator.clipboard.writeText("connect 127.0.0.1")}catch(e){}
      setTimeout(()=>trainLoad(box,sid),2500)}
    catch(e){msg.textContent="Failed: "+e.message;$$("[data-tplay]",box).forEach(x=>x.disabled=false)}});
  if(st.running)TRAIN.timer=setTimeout(()=>{if(box.isConnected&&S.view==="prepare")trainLoad(box,sid)},4000)}
function wireExp(v,X,p){const msg=$("#xmsg",v);
  $$("[data-xstart]",v).forEach(b=>b.onclick=async()=>{const s=X.suggested[+b.dataset.xstart];b.disabled=true;
    try{await api("/api/experiment",{sid:p.steamid,action:"start",template:s.template,params:s.params});await reloadPlayer()}catch(e){if(msg)msg.textContent="Failed: "+e.message;b.disabled=false}});
  $$("[data-xstop]",v).forEach(b=>b.onclick=async()=>{b.disabled=true;
    try{await api("/api/experiment",{sid:p.steamid,action:"stop",id:b.dataset.xstop});await reloadPlayer()}catch(e){if(msg)msg.textContent="Failed: "+e.message;b.disabled=false}})}

// ---------- view: settings ----------
let steamForget=false;
// the base grows by itself (grow.py): your matches' players, their recent matchmaking games (Leetify), the players of
// those, until the target; paused while you play
function growCard(g){
  if(!g)return "";
  if(g.client){const pk=g.pack||{};
    return `<article class="card"><h3>My base: ${pk.matches?Number(pk.matches).toLocaleString():"?"} matches <span class="pill">came with this version</span></h3>
   <p>The references you are compared with, the lineups and their groups, the T side's plays, the weapons and the training's real attacks come from the full base${pk.built?`, as it was on ${esc(new Date(pk.built*1000).toLocaleDateString())}`:""}. Your own matches are downloaded and analyzed right here; each new version of me brings my base as it grew.</p></article>`}
  const n=g.n||0,t=g.target||5000,pct=Math.min(100,Math.round(n/t*100)),ok=(g.counts||{}).ok||0;
  return `<article class="card"><h3>The base: ${n} matches ${g.on?`<span class="pill strong">${g.alive?"growing":"starting"}</span>`:`<span class="pill">stopped</span>`}</h3>
   <p>The players of your matches, their recent matchmaking games (from Leetify, for the players who use it: all of their last month), then the players of those matches, and so on until the target: more duels, grenades and real hits to compare you with and to train on.</p>
   <div style="height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin:6px 0"><div style="width:${pct}%;height:100%;background:var(--ct)"></div></div>
   <p class="note">${esc(g.status||"not started")}${g.on||ok?` · ${ok} new match(es) · ${g.codes} waiting · ${g.looked} player(s) looked up`:""} · ${g.free_gb} GB free on the disk</p>
   <p class="note">One match from Valve every 30 s at most, through your Steam session (Steam may show you in game a few seconds). It pauses while CS2 is open, during an analysis, a recording or a transcription, at the lowest priority otherwise. The demos stay (the practice part uses them); it stops at the target or when the disk has 150 GB left.</p>
   <div class="btns" style="align-items:center">${g.on?"":`<label class="note">Target <input id="gr-n" type="number" min="100" max="20000" step="100" value="${t}" style="width:90px;font:14px var(--f-body);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:4px 6px"> matches</label>`}<button type="button" id="gr-go"${g.on?"":` class="primary"`}>${g.on?"Stop":"Grow the base"}</button></div></article>`}
// a player's copy (05/10): the coach's new versions of the app and of the base, signed by him, installed on a click
const fmtMB=b=>`${Math.max(1,Math.round((b||0)/1048576))} MB`,UPW={code:"the app",base:"the base",runtime:"Python and its libraries"};
const when=t=>new Date(t*1000).toLocaleString([], {dateStyle:"short",timeStyle:"short"});
function updateCard(u){
  if(!u||!u.enabled)return "";
  const c=u.current||{},av=u.available||[],pr=u.progress||{},busy=pr.busy||pr.restarting,pct=pr.total?Math.round(100*pr.done/pr.total):0;
  const list=av.map(a=>`<li>${UPW[a.part]||esc(a.part)} ${esc(a.version||"")}${a.matches?` · ${Number(a.matches).toLocaleString()} matches`:""} · ${fmtMB(a.size)}</li>`).join("");
  return `<article class="card" id="up-card"><h3>App updates ${av.length?`<span class="pill strong">available</span>`:""}</h3>
   <p class="note">This version: ${esc(c.app||"?")}${c.build?` · build ${esc(c.build)}`:""} · base ${esc(c.base||"?")}${c.matches?` (${Number(c.matches).toLocaleString()} matches)`:""}${u.checked?` · checked ${when(u.checked)}`:""}</p>
   ${av.length?`<ul class="note">${list}</ul>${u.latest&&u.latest.notes?`<p>${esc(u.latest.notes)}</p>`:""}`:`<p class="note">${u.error?`Check failed: ${esc(u.error)}`:"Up to date."}</p>`}
   ${busy?`<div style="height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin:6px 0"><div style="width:${pct}%;height:100%;background:var(--ct)"></div></div><p class="note">${pr.restarting?"Restarting the app…":pr.part==="installing"?"Installing…":`Downloading ${UPW[pr.part]||""}…`}</p>`:""}
   ${pr.error?`<p class="note">Failed: ${esc(pr.error)}</p>`:""}
   <p class="note">Every update is signed by my author and checked here before I install it. Your settings, matches, profile and voice stay as they are.</p>
   <div class="btns">${av.length&&!busy?`<button type="button" class="primary" id="up-go">Install the update</button>`:""}<button type="button" id="up-check"${busy?" disabled":""}>Check now</button></div></article>`}
function wireUpdate(v){
  const go=$("#up-go",v),ck=$("#up-check",v);
  if(ck)ck.onclick=async()=>{ck.disabled=true;try{await api("/api/update/check",{})}catch(e){}pollUpdate(v)};
  if(go)go.onclick=async()=>{go.disabled=true;try{await api("/api/update/apply",{})}catch(e){go.disabled=false;go.insertAdjacentHTML("afterend",`<span class="note">${esc(e.message)}</span>`);return}pollUpdate(v)}}
async function pollUpdate(v){clearTimeout(S.upTimer);
  let u=null;try{u=await (await fetch("/api/update")).json()}catch(e){S.upTimer=setTimeout(()=>pollUpdate(v),2000);return}   // restarting: back when it answers
  const pr=u.progress||{};
  if(S.upRestart&&!pr.restarting){location.reload();return}
  if(pr.restarting)S.upRestart=true;
  gearDot(u);const c=$("#up-card",v);if(!c||!c.isConnected)return;
  c.outerHTML=updateCard(u);wireUpdate(v);
  if(pr.busy||pr.restarting)S.upTimer=setTimeout(()=>{if(S.view==="settings")pollUpdate(v)},1500)}
function gearDot(u){const g=$(".gear");if(!g)return;const n=((u||{}).available||[]).length;g.classList.toggle("has-update",!!n);
  const ab=$("#acctbtn");if(ab)ab.classList.toggle("has-update",!!n);
  g.title=n?"Settings: an update of the app is available":"Settings: Steam, game detection, microphone"}
// the base grows with the players (05/10): a player's switch (off until they turn it on), or what the coach received
function shareCard(c){
  if(!c)return "";
  if(!c.client){const st=c.stats||{};
    return `<article class="card" id="ct-card"><h3>Matches shared by players</h3>
     <p class="note">${c.token?`${st.joined||0} joined the base · ${st.duplicates||0} already there · ${st.refused||0} refused${c.waiting?` · ${c.waiting} waiting here`:""}${c.last?` · last pull ${when(c.last)}`:""}`:"Not set up yet: python contributions.py init, then publish the site (deploy_site.py)."}</p>
     <p class="note">The base loop pulls them every hour while it runs; each match is checked again here (the app's own tables, no real SteamID, no name) and kept once.</p>
     ${c.token?`<div class="btns"><button type="button" id="ct-pull">Pull now</button></div>`:""}</article>`}
  return `<article class="card" id="ct-card"><h3>Share my matches with the base ${c.on?`<span class="pill strong">on</span>`:`<span class="pill">off</span>`}</h3>
   <p>The base you are compared with grows with the players who use the app. When this is on, your new matches come to me anonymized: what the app extracted from each demo (positions, duels, grenades, buys, rounds), where every SteamID becomes a random id used for that match only, every name is blank and the match id is random. Never your demos, your voice, your settings or your profile.</p>
   <p class="note">${c.on?`${c.sent} match(es) shared${c.waiting?` · ${c.waiting} waiting`:""}${c.last?` · last ${when(c.last)}`:""}`:"Off: nothing leaves this PC."}${c.error?` · last try failed: ${esc(c.error)}`:""}</p>
   <p class="note">You can turn it off at any time. To have what this PC sent deleted before it joins the base, write to my author with this installation's id: <code>${esc(c.install||"")}</code>. <a href="https://wily.valentingassend.com/privacy.html" target="_blank" rel="noopener" style="color:var(--ct)">Privacy policy</a></p>
   <div class="btns"><button type="button"${c.on?"":` class="primary"`} id="ct-on">${c.on?"Stop sharing":"Share my matches"}</button>${c.on&&c.waiting?`<button type="button" id="ct-send"${c.sending?" disabled":""}>Send now</button>`:""}</div></article>`}
function wireShare(v){
  const on=$("#ct-on",v),sd=$("#ct-send",v),pl=$("#ct-pull",v);
  const redo=async()=>{let c=null;try{c=await (await fetch("/api/contrib")).json()}catch(e){return}const k=$("#ct-card",v);if(k&&k.isConnected){k.outerHTML=shareCard(c);wireShare(v)}};
  if(on)on.onclick=async()=>{on.disabled=true;try{await api("/api/contrib/set",{on:!on.textContent.startsWith("Stop")})}catch(e){}redo()};
  if(sd)sd.onclick=async()=>{sd.disabled=true;try{await api("/api/contrib/send",{})}catch(e){}setTimeout(redo,3000)};
  if(pl)pl.onclick=async()=>{pl.disabled=true;try{await api("/api/contrib/pull",{})}catch(e){}setTimeout(redo,5000)}}
// a bug report (05/10, the alpha): the player writes, sees what is sent, sends; kept and sent later when offline
function bugPage(){return `${S.view||"?"}${S.player&&S.player===D.own?" (own profile)":S.player?" (another profile)":""} ${location.pathname}${location.hash}`.slice(0,120)}
function openReport(kind){const d=$("#bugdlg");if(!d)return;$("#bug-msg").textContent="";$("#bug-send").disabled=false;
  $$("input[name=kind]",d).forEach(r=>r.checked=r.value===(kind||"bug"));$("#bug-pre").textContent="…";$("#bug-prev").open=false;
  if(typeof d.showModal==="function")d.showModal();else d.setAttribute("open","");$("#bug-text").focus()}
function wireReport(){const d=$("#bugdlg");if(!d||d.dataset.wired)return;d.dataset.wired="1";
  $("#bug-close").onclick=()=>d.close();
  $("#bug-prev").ontoggle=async()=>{if(!$("#bug-prev").open)return;$("#bug-pre").textContent="Reading…";
    if(!$("#bug-diag").checked){$("#bug-pre").textContent="No technical details: only what you wrote.";return}
    try{const r=await api("/api/report/preview",{page:bugPage(),errors:ERRS});$("#bug-pre").textContent=JSON.stringify(r,null,1)}catch(e){$("#bug-pre").textContent=e.message}};
  $("#bug-diag").onchange=()=>{if($("#bug-prev").open)$("#bug-prev").ontoggle()};
  $("#bug-send").onclick=async()=>{const t=$("#bug-text").value.trim(),m=$("#bug-msg");if(!t){m.textContent="Describe what happened first.";$("#bug-text").focus();return}
    const b=$("#bug-send");b.disabled=true;m.textContent="Sending…";
    try{const r=await api("/api/report/send",{text:t,expected:$("#bug-exp").value,email:$("#bug-email").value,include:$("#bug-diag").checked,
        page:bugPage(),errors:ERRS,kind:($("input[name=kind]:checked",d)||{}).value||"bug"});
      if(r.ok){m.textContent=`Sent, thank you (report ${r.id}).`;$("#bug-text").value="";$("#bug-exp").value="";setTimeout(()=>d.close(),2500)}
      else{m.textContent="The site can't be reached right now: your report is kept on this PC and sent as soon as it can.";b.disabled=false}}
    catch(e){m.textContent=e.message;b.disabled=false}}}
function reportCard(){if(D.role!=="client")return "";
  return `<article class="card"><h3>Alpha <span class="pill">0.0.x</span></h3><p>I'm in alpha: open to every player for the first time, so things will break. Tell me what broke, or an idea: the "alpha · report" tag at the top works from any page.</p>
   <div class="btns"><button type="button" class="primary" data-report="bug">Report a bug</button><button type="button" data-report="idea">Suggest an idea</button></div></article>`}
// the coach's PC: what players reported, the newest first
function reportsCard(rs){if(D.role==="client"||!Array.isArray(rs))return "";
  const fbk=r=>r.kind==="feedback"||/^\[feedback/.test(r.text||""),face=r=>{const m=/(\d)\/5\]/.exec(r.text||"");const n=r.rating||(m?+m[1]:0);return n?" "+["😖","😕","😐","🙂","🤩"][n-1]:""};
  const open=rs.filter(r=>!r.done),one=r=>`<li class="rep${r.done?" done":""}"><div><b>${fbk(r)?`💬 Feedback${face(r)}`:/^\[in-game !report/.test(r.text||"")?"🎮 In-game report":r.kind==="idea"?"💡 Idea":"🐞 Bug"}</b> · ${when(r.at)} · ${esc(r.app||"?")}${r.email?` · <a href="mailto:${esc(r.email)}">${esc(r.email)}</a>`:""}</div>
     <p>${esc(r.text||"")}</p>${r.expected?`<p class="note">Expected: ${esc(r.expected)}</p>`:""}<p class="note">${esc(r.page||"")}</p>
     <div class="btns">${r.has_diag?`<button type="button" data-rdiag="${esc(r.id)}">Technical details</button>`:""}<button type="button" data-rdone="${esc(r.id)}" data-v="${r.done?0:1}">${r.done?"Reopen":"Done"}</button></div><pre class="rdiag" hidden></pre></li>`;
  return `<article class="card" id="rp-card"><h3>Bug reports ${open.length?`<span class="pill strong">${open.length} open</span>`:""}</h3>
   <p class="note">Sent by players from their app (the "alpha · report" tag), pulled every hour by the base loop while it runs.</p>
   ${rs.length?`<ul class="replist">${rs.slice(0,30).map(one).join("")}</ul>`:`<p class="note">None yet.</p>`}
   <div class="btns"><button type="button" id="rp-pull">Pull now</button></div></article>`}
function wireReports(v){
  $$("[data-report]",v).forEach(b=>b.onclick=()=>openReport(b.dataset.report));
  const redo=rs=>{const k=$("#rp-card",v);if(k&&k.isConnected){k.outerHTML=reportsCard(rs);wireReports(v)}};
  const pl=$("#rp-pull",v);if(pl)pl.onclick=async()=>{pl.disabled=true;try{redo(await api("/api/reports/pull",{}))}catch(e){pl.disabled=false;pl.insertAdjacentHTML("afterend",`<span class="note">${esc(e.message)}</span>`)}};
  $$("[data-rdone]",v).forEach(b=>b.onclick=async()=>{b.disabled=true;try{redo(await api("/api/reports/done",{id:b.dataset.rdone,done:b.dataset.v==="1"}))}catch(e){b.disabled=false}});
  $$("[data-rdiag]",v).forEach(b=>b.onclick=async()=>{const pre=b.closest("li").querySelector(".rdiag");if(!pre.hidden){pre.hidden=true;return}
    try{const r=(await (await fetch("/api/reports?id="+encodeURIComponent(b.dataset.rdiag))).json()).find(x=>x.id===b.dataset.rdiag);pre.textContent=JSON.stringify(r&&r.diag,null,1);pre.hidden=false}catch(e){}})}
// anonymous usage statistics (05/10): a player's switch and today's counters; the coach's ranking of what players use
function usageCard(u){if(!u||!u.client)return "";
  const t=u.today||{},nv=Object.keys(t.views||{}).length,na=Object.values(t.actions||{}).reduce((a,b)=>a+b,0);
  return `<article class="card" id="us-card"><h3>Usage statistics ${u.on?`<span class="pill strong">on</span>`:`<span class="pill">off</span>`}</h3>
   <p>Anonymous counters, per day: the pages you open and how long, the buttons you use, the errors the page meets, whether Live runs during a match, the app's version and your screen's size class. No identifier, no SteamID, no name, nothing you write. A finished day is sent to me, added to that day's totals and thrown away.</p>
   <p class="note">${u.on?`Today so far: ${nv} page(s), ${na} click(s) counted · ${u.days_sent} day(s) sent`:"Off: nothing is counted or sent."}</p>
   ${u.on&&u.today?`<details><summary>Today's counters, exactly</summary><pre class="uspre">${esc(JSON.stringify(u.today,null,1))}</pre></details>`:""}
   <div class="btns"><button type="button" id="us-on">${u.on?"Turn it off":"Turn it on"}</button></div></article>`}
const VLABEL={ingame:"Live",prepare:"Prepare",review:"Review",profile:"Profile",players:"Players",pros:"Pros",team:"Team",settings:"Settings"};
function usageStatsCard(st){if(!st||D.role==="client")return "";
  const T=st.totals||{},pd=T.reports||0,mins=s=>(s/60).toFixed(1);
  if(!pd)return `<article class="card" id="ust-card"><h3>How players use the app</h3><p class="note">No usage statistics yet: they come from players' apps (0.0.2-alpha and later), one day after use, pulled every hour by the base loop.</p><div class="btns"><button type="button" id="ust-pull">Pull now</button></div></article>`;
  const row=(c)=>`<tr>${c.map(x=>`<td>${x}</td>`).join("")}</tr>`;
  const views=(st.views||[]).map(v=>row([esc(VLABEL[v.view]||v.view),`${v.users} <span class="note">(${v.share}%)</span>`,v.visits,mins(v.seconds),v.minutes_per_user])).join("");
  const acts=(st.actions||[]).slice(0,25).map(a=>row([`<code>${esc(a.action)}</code>`,`${a.users} <span class="note">(${a.share}%)</span>`,a.count])).join("");
  const rare=(st.rare||[]).map(a=>`<code>${esc(a.action)}</code> ${a.users}`).join(" · ");
  const dict=o=>Object.entries(o||{}).sort((a,b)=>b[1]-a[1]).map(([k,n])=>`${esc(k)} ${n}`).join(" · ");
  return `<article class="card" id="ust-card"><h3>How players use the app <span class="pill">last ${st.days} days</span></h3>
   <p class="note">${pd} player-day(s) over ${T.days} day(s) · Live during a match: ${T.live_users} player-day(s), ${mins(T.live_seconds)} min · days with page errors: ${T.error_reports} (${T.errors} errors) · versions: ${dict(T.apps)} · screens: ${dict(T.screens)}</p>
   <h4>Pages</h4><table class="ustab"><thead><tr><th>Page</th><th>Player-days</th><th>Visits</th><th>Minutes</th><th>Min / player-day</th></tr></thead><tbody>${views}</tbody></table>
   <h4>Most used actions</h4><table class="ustab"><thead><tr><th>Action (page:element)</th><th>Player-days</th><th>Clicks</th></tr></thead><tbody>${acts}</tbody></table>
   ${rare?`<h4>Rarely used</h4><p class="note">${rare}</p>`:""}
   <p class="note">An element never clicked does not appear at all: compare with the page to find what nobody uses.</p>
   <div class="btns"><button type="button" id="ust-pull">Pull now</button></div></article>`}
function wireUsage(v){
  const on=$("#us-on",v);if(on)on.onclick=async()=>{on.disabled=true;try{const r=await api("/api/usage/set",{on:on.textContent.includes("on")&&!on.textContent.includes("off"),noticed:true});D.usage={on:r.on,noticed:true};const k=$("#us-card",v);if(k){k.outerHTML=usageCard(r);wireUsage(v)}}catch(e){on.disabled=false}};
  const pl=$("#ust-pull",v);if(pl)pl.onclick=async()=>{pl.disabled=true;try{const r=await api("/api/usage/pull",{days:30});const k=$("#ust-card",v);if(k){k.outerHTML=usageStatsCard(r);wireUsage(v)}}catch(e){pl.disabled=false;pl.insertAdjacentHTML("afterend",`<span class="note">${esc(e.message)}</span>`)}}}
// the app updated with the base as it grows (04/10: "a button in the settings to update every data of the app with the
// base that grows"): what every page reads from the base, then the profiles, yours first
function refreshCard(r){
  r=r||{};const run=r.running,ago=t=>t?new Date(t*1000).toLocaleString([], {dateStyle:"short",timeStyle:"short"}):"";
  const pb=r.phase==="profiles"?`profiles ${r.profiles_done||0}/${r.profiles_total||0}`:`the base's references ${r.steps_done||0}/${r.steps_total||0}`;
  const pct=r.phase==="profiles"?Math.round(100*(r.profiles_done||0)/Math.max(1,r.profiles_total||1)):Math.round(100*(r.steps_done||0)/Math.max(1,r.steps_total||1));
  const state=run?`${r.paused?`paused: ${esc(r.paused)}`:`${esc(r.current||"…")}`} · ${pb}`:r.finished?`last update ${ago(r.finished)}${r.stopped?" (stopped)":""} · ${r.profiles_done||0}/${r.profiles_total||0} profiles`:"never run";
  if(r.client)return `<article class="card" id="rf-card"><h3>Update my profile ${run?`<span class="pill strong">updating</span>`:""}</h3>
   <p>Your profile and your team's analyzed again against the base's references that came with this version of the app: plan, pages, training.</p>
   ${run?`<div style="height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin:6px 0"><div style="width:${pct}%;height:100%;background:var(--ct)"></div></div>`:""}
   <p class="note">${state}</p>
   ${(r.errors||[]).length?`<p class="note">Failed: ${(r.errors||[]).map(esc).join(" · ")}</p>`:""}
   <div class="btns">${run?`<button type="button" id="rf-stop">Stop</button>`:`<button type="button" class="primary" id="rf-mine">Update my profile</button>`}</div></article>`;
  return `<article class="card" id="rf-card"><h3>Update the app with the base ${run?`<span class="pill strong">updating</span>`:""}</h3>
   <p>The base grows every day: the lineups and their groups, the references you are compared with, the T side's plays, the weapons, the training's sites, held spots and real attacks, the pro catalog are computed again from it, then your profile, your team's, and every other analyzed player's (their analysis against the base, their plan and pages).</p>
   ${run?`<div style="height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin:6px 0"><div style="width:${pct}%;height:100%;background:var(--ct)"></div></div>`:""}
   <p class="note">${state}</p>
   ${(r.errors||[]).length?`<p class="note">Failed: ${(r.errors||[]).map(esc).join(" · ")}</p>`:""}
   <p class="note">At the lowest priority, paused while a map is loaded in CS2, a recording or a transcription runs: the base's part takes a few tens of minutes, yours a few minutes, every profile several hours (in the background, yours first).</p>
   <div class="btns">${run?`<button type="button" id="rf-stop">Stop</button>`:`<button type="button" class="primary" id="rf-all">Update everything</button><button type="button" id="rf-mine">Only the base, mine and my team's</button>`}</div></article>`}
function wireRefresh(v){
  const go=async mine=>{try{await api("/api/refresh/start",{mine})}catch(e){}pollRefresh(v)};
  const a=$("#rf-all",v),m=$("#rf-mine",v),s=$("#rf-stop",v);
  if(a)a.onclick=()=>{a.disabled=true;go(false)};if(m)m.onclick=()=>{m.disabled=true;go(true)};
  if(s)s.onclick=async()=>{s.disabled=true;try{await api("/api/refresh/stop",{})}catch(e){}pollRefresh(v)}}
async function pollRefresh(v){clearTimeout(S.rfTimer);
  let r=null;try{r=await (await fetch("/api/refresh")).json()}catch(e){return}
  const c=$("#rf-card",v);if(!c||!c.isConnected)return;
  c.outerHTML=refreshCard(r);wireRefresh(v);
  if(r.running)S.rfTimer=setTimeout(()=>{if(S.view==="settings")pollRefresh(v)},5000)}
async function renderSettings(){
  const v=$("#v-settings");
  const head=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">Everything stays on this PC</span><h2>Settings</h2></div></div>`;
  if(!D.local){v.innerHTML=head+`<div class="empty">My settings live in the local app: double-click <code>Wily.bat</code>, then open Settings.</div>`;return}
  v.innerHTML=head+`<div class="empty"><span class="spin" aria-hidden="true"></span>Reading your Steam connection…</div>`;
  let st;try{st=await (await fetch("/api/steam/status"+(D.own?`?sid=${D.own}`:""))).json()}catch(e){v.innerHTML=head+`<div class="empty">I don't answer: restart "Wily.bat" and I'll be back.</div>`;return}
  let gs=null;try{gs=await (await fetch("/api/gsi/status")).json()}catch(e){}
  let vs=null;try{vs=await (await fetch("/api/voice/status")).json()}catch(e){}
  let cc=null;try{cc=await (await fetch("/api/coach/status")).json()}catch(e){}
  let gr=null;try{gr=await (await fetch("/api/grow")).json()}catch(e){}
  let rf=null;try{rf=await (await fetch("/api/refresh")).json()}catch(e){}
  let up=null;try{up=await (await fetch("/api/update")).json()}catch(e){}
  let ct=null;try{ct=await (await fetch("/api/contrib")).json()}catch(e){}
  let rs=null;if(D.role!=="client"){try{rs=await (await fetch("/api/reports")).json()}catch(e){}}
  let us=null;try{us=await (await fetch(D.role==="client"?"/api/usage":"/api/usage/stats?days=30")).json()}catch(e){}
  const flag=new URLSearchParams(location.search).get("steam");
  const ok=b=>b?`<span class="pill strong">done</span>`:`<span class="pill">to do</span>`;
  const pt=st.playtime,L=st.links||{};
  v.innerHTML=head+`
  ${flag==="ok"?`<div class="jobpanel" style="padding:0"><div class="in ok">Steam confirmed the sign-in.</div></div>`:flag==="refused"||flag==="refus"?`<div class="jobpanel" style="padding:0"><div class="in err">Steam didn't confirm the sign-in. Try again.</div></div>`:""}
  <h3 class="set-h">In game</h3>
  <article class="card"><h3>Game detection ${ok(gs&&gs.installed)}</h3>
   <p>CS2 sends the app the map, your side, the round, the score, your money and your grenades: the "In game" page follows your match on its own and gives the right advice at the right time (buys during freeze time, bomb planted, end of round).</p>
   <p class="note">This is Valve's Game State Integration, the official feature used by HUDs and RGB keyboards. During a match, CS2 only sends your own info, never the enemies'.${gs&&gs.path?` File: <code>${esc(gs.path)}</code>.`:""}${gs&&gs.installed?(gs.receiving?" CS2 is sending its data.":" Restart CS2 so it picks it up."):""}</p>
   <div class="btns">${gs&&gs.installed?`<button type="button" id="gsi-off">Turn detection off</button>`:`<button type="button" class="primary" id="gsi-on" ${gs&&gs.cfg_dir?"":"disabled"}>Turn detection on</button>`}${gs&&!gs.cfg_dir?`<span class="note">CS2 folder not found on this PC.</span>`:""}</div>
   <div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="o-cs2" ${!gs||gs.open_on_cs2!==false?"checked":""}> Open my In game page when CS2 starts (when no Wily page is open yet)</label></div>
   <div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="o-fb" ${!gs||gs.feedback_prompts!==false?"checked":""}> Ask me how it went after a warm-up and after a match (the closed alpha's feedback)</label></div>
   <p class="note">CS2 lets nothing write in its lobby's chat, so I open myself instead: the page first, CS2's window comes up over it. It needs me running: I start with Windows when a shortcut to me is in your Startup folder (Win+R, shell:startup).</p></article>
  <article class="card"><h3>Your plan with the numpad (1 to 6) ${ok(cc&&cc.bound&&cc.tempo_bound)}</h3>
   <p>Numpad <b>1</b> = A, <b>2</b> = mid, <b>3</b> = B; <b>4</b> = rush, <b>5</b> = slow, <b>6</b> = map control; <b>minus</b> drops them. On T, the key says only what you pressed in the team chat: your direction and your tempo ("A", "Rush B", "Map control, then mid"; on A and B with CS2's own "Go A" / "Go B" of the chat wheel, the order bots follow). It tells me too: Live then shows you the way in that wins most, its odds this round, when to be on the site and its stuff, with a ping on the map; that stays on your screen. On CT, the keys only tell me: 1-2-3 where you play, 4-5-6 what the Ts do.</p>
   ${cc&&!cc.console?`<p class="note">I read the keys in CS2's console log (game/csgo/console.log, written when CS2 starts with <code>-condebug</code> in its launch options): not found or old.</p>`:""}
   ${cc&&cc.bound&&!cc.tempo_bound?`<p>Numpad 4-5-6 are new: run <code>exec coach_binds</code> once more in CS2's console. Your numpad 5 ran <code>bot_crouch 1</code>: it becomes slow (bind it elsewhere if you still use it on a practice server).</p>`:""}
   <p>Numpad <b>7</b> = A, <b>9</b> = B still work: on CT, the site you play; once the bomb is down, on both sides, the site it went down on. Numpad <b>+</b>: the next lineup's photo, in a photo session (Prepare, the lineups' block).</p>
   ${cc&&cc.bound&&cc.tempo_bound?`<p class="note">The keys are set.</p>`:cc&&cc.bound?"":`<p>One time only, in CS2's console: <code>exec coach_binds</code> (the keys then stay in your CS2 settings).</p>`}
   <p class="note">The In game page must be open during the match (it writes the lines). A key's file only says its line and the chat wheel's order, never another command.</p></article>
  <article class="card"><h3>My voice at the buy time</h3>
   <p>When you're frustrated (a word or a shout after your death, "coach, énervé"), after two rounds lost dead without a kill, or when you don't understand ("qu'est-ce qu'on fait", "coach, perdu"): a few seconds of voice during the buy time, once per round. Calm, then one thing to do this round, or a simple plan.</p>
   <div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="c-voice" ${voiceOn()?"checked":""}> Speak at the buy time</label><button type="button" id="c-voice-test">Hear it</button></div>
   <div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="c-info" ${infoOn()?"checked":""}> Say "l'info !" when I die (your rounds with a call before your death are won far more often)</label></div>
   <p class="note">A French voice of Windows (Julie, Paul or Hortense), on this PC: nothing is sent anywhere. The browser only lets a page speak after one click on it: click the In game page once when you open it.</p></article>
  <article class="card form"><h3>Your calls (microphone) ${ok(vs&&vs.settings&&vs.settings.auto)}</h3>
   <p>During your matches, the app records <b>your microphone</b>, transcribes your calls on this PC and lines them up with the rounds: info given before dying, "where + how many", grenades called, talking during a teammate's clutch, frustration. The result shows up in the Review.</p>
   <p class="note">Only your voice: with a headset, your teammates' voices don't reach your microphone. Nothing leaves the PC (folder <code>out/voice</code>, not versioned). Only record other people with their consent: recording someone's words without consent is illegal in France (article 226-1 of the Code pénal) and in many other countries.</p>
   ${vs&&vs.available?`
    <div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="v-auto" ${vs.settings.auto?"checked":""}> Record automatically during my matches (with game detection)</label></div>
    <div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="v-live" ${(vs.live||{}).on!==false?"checked":""}> Live calls: my short calls ("3 B", "rush A", "bombe B", "one Banana") count like a tap on the T read, no click</label></div>
    <p class="note">Short calls only (a sentence is not read), transcribed on this PC by a small model at low priority, on the processor: the graphics card stays for the game. About 2 to 3 s after you speak.${(vs.live||{}).last&&(vs.live||{}).last.text?` Last heard: "${esc(vs.live.last.text)}"${vs.live.last.parsed?` → ${esc([vs.live.last.parsed.rush?"rush":"",vs.live.last.parsed.n||"",vs.live.last.parsed.site||"",vs.live.last.parsed.zone||"",vs.live.last.parsed.bomb?"bomb":""].filter(Boolean).join(" · "))}`:" (not a call)"}.`:""}</p>
    <p class="note">Recorded microphone: <b>${esc(vs.device||"Windows default microphone")}</b>${vs.cs2_device&&vs.device===vs.cs2_device?" (the same as in CS2)":""}.</p>
    <div class="row"><span class="f">Microphone</span><select id="v-dev" style="font:14px var(--f-body);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:5px 8px;max-width:360px"><option value="">Windows default microphone</option></select></div>
    ${vs.recording?`<p><b class="bad">● Recording</b> ${vs.current.map?`(${MAPN(vs.current.map)})`:""}, since ${fmtDate(vs.current.start_iso)} <button type="button" id="v-stop">Stop</button></p>`:""}
    ${vs.transcribing?`<p class="note"><span class="spin" aria-hidden="true"></span>Transcribing (${esc(vs.transcribing)}): it runs at low priority and pauses when a match starts.</p>`:""}
    ${vs.recordings.length?`<div class="tbl"><table><thead><tr><th>Date</th><th>Map</th><th class="n">Length</th><th class="n">Rounds found</th><th>Transcription</th><th></th></tr></thead><tbody>
      ${vs.recordings.map(r=>`<tr><td>${fmtDate(r.start)}</td><td>${r.map?MAPN(r.map):"—"}${r.practice?' <span class="pill">practice</span>':""}${r.team?` <span class="pill" title="${esc(r.team)}">+ team sound</span>`:""}</td><td class="n">${r.duration?Math.round(r.duration/60)+" min":"in progress"}</td><td class="n">${r.rounds_marked||"—"}</td>
        <td>${r.silent?'<span class="bad">silent: wrong microphone</span>':r.transcribed?"done":r.duration?`<button type="button" data-vtr="${r.id}">Transcribe</button>`:"—"}</td><td><button type="button" data-vdel="${r.id}">Delete</button></td></tr>`).join("")}</tbody></table></div>`
      :`<p class="note">No recording yet.</p>`}<span class="note" id="v-msg" role="status"></span>`
    :`<p class="note">Microphone unavailable on this PC${vs&&vs.error?` (${esc(vs.error)})`:""}.</p>`}</article>
  <h3 class="set-h">Your Steam account</h3>
   <article class="card"><h3>1. Who are you? ${ok(st.login)}</h3>
    ${st.login?`<p>Signed in with Steam: <b>${esc(st.login.name||st.login.steamid)}</b> <span class="num note">${esc(st.login.steamid)}</span>, on ${fmtDate(st.login.time)}. This account is your default profile in the app.</p>`
      :`<p>Sign in through Steam's official page: it confirms your account to me. I never see your password, only your SteamID.</p>`}
    <p><a class="primary" style="display:inline-block;text-decoration:none" href="/api/steam/login">${st.login?"Sign in with Steam again":"Sign in with Steam"}</a></p>
    ${st.pc_account&&st.pc_account.steamid?`<p class="note">Steam account open on this PC: ${esc(st.pc_account.name||"")} <span class="num">${esc(st.pc_account.steamid)}</span>.</p>`:""}</article>
  <article class="card form"><h3>2. Full, automatic history ${ok(st.has_key&&st.has_auth)}</h3>
   <p>Valve only gives your <b>last 8 matches</b> and deletes demos after about <b>a month</b>. With these two codes, I find <b>every new match</b>, even if it hasn't run for weeks. It analyzes the demos still available and keeps the date, score, your kills and deaths and your teammates for all the others: your times, sessions, streaks and group become measurable over your whole history.</p>
   <div class="row"><span class="f">Steam API key ${ok(st.has_key)}</span><input id="st-key" type="password" autocomplete="off" spellcheck="false" placeholder="${st.has_key?"already saved · paste a new key to replace it":"32 characters"}" style="flex:1;min-width:220px;font:14px var(--f-mono);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:5px 8px"></div>
   <p class="note">Create it on <a href="${esc(L.key)}" target="_blank" rel="noopener" style="color:var(--ct)">steamcommunity.com/dev/apikey</a> (signed in to your Steam account). Domain name: write <code>localhost</code>.</p>
   <div class="row"><span class="f">Authentication code ${ok(st.has_auth)}</span><input id="st-auth" type="password" autocomplete="off" spellcheck="false" placeholder="${st.has_auth?"already saved":"XXXX-XXXXX-XXXX"}" style="width:220px;font:14px var(--f-mono);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:5px 8px">
     <input id="st-known" type="text" autocomplete="off" spellcheck="false" placeholder="Code of your last match CSGO-… (optional)" style="flex:1;min-width:240px;font:14px var(--f-mono)"></div>
   <p class="note">On <a href="${esc(L.auth)}" target="_blank" rel="noopener" style="color:var(--ct)">Steam's CS2 help page</a> (signed in to your account): "Create authentication code". The same page shows the code of your last match. If it's empty, I find it from your last 8 matches (Steam open, CS2 closed).</p>
   <div class="row"><button type="button" class="primary" id="st-save">Save and check</button>
     <button type="button" class="primary" id="st-sync" ${st.has_auth?"":"disabled"}>Sync now</button><span class="note" id="st-msg" role="status"></span></div>
   ${st.has_auth?`<div class="row"><label style="display:flex;gap:8px;align-items:center;font-size:14px"><input type="checkbox" id="st-auto" ${st.auto_sync?"checked":""}> Sync automatically when the app starts, then every 30 minutes (off: "Update my matches" in your menu, top right, does it when you want)</label></div>
     <p class="note">Last sync: ${st.last_sync?fmtDate(st.last_sync):"never"} · ${st.known_matches} match(es) known for this account${st.pending?` · ${st.pending} pending (Steam must be open and CS2 closed)`:""}${st.friends!=null?` · ${st.friends} Steam friends (used to detect your group)`:""}.</p>`:""}
   <details class="set-more"><summary>What it unlocks</summary><ul>
    <li><b>No lost match</b>: every matchmaking match is found, analyzed while the demo exists, and counted in your habits afterwards.</li>
    <li><b>Habits over your whole history</b>: hours when you play best, ideal number of games per session, effect of loss streaks (Routine tab).</li>
    <li><b>Your group</b>: your Steam friends on your team are recognized as your group, even after a single match together.</li>
    <li><b>Your experience</b>: your playtime sets the priorities of the Progress tab.</li></ul></details>
   <p class="note">Your codes stay in <code>out/settings.json</code> on this PC: this file is not versioned and the codes only go to Steam's official API. You can remove everything at any time.</p>
   <div class="btns"><button type="button" id="st-forget">${steamForget?"Confirm: remove the sign-in and the codes":"Disconnect everything"}</button></div></article>
  <h3 class="set-h">This app</h3>
  <article class="card"><h3>Display</h3>
   <div class="btns" role="group" aria-label="Theme">${[["dark","Dark"],["light","Light"],["system","Your system's"]].map(([k,l])=>`<button type="button" data-theme-set="${k}" aria-pressed="${(store("theme")||"dark")===k}">${l}</button>`).join("")}</div>
   <p class="note">The theme of the app on this browser. Dark is the default; "your system's" follows Windows.</p></article>${reportCard()}${updateCard(up)}${D.role==="client"?shareCard(ct)+usageCard(us):""}
  ${D.role!=="client"?`<h3 class="set-h">The base and the players' apps</h3>${growCard(gr)}${refreshCard(rf)}${shareCard(ct)}${reportsCard(rs)}${usageStatsCard(us)}`:""}`;
  wireRefresh(v);if(rf&&rf.running)pollRefresh(v);
  const msg=$("#st-msg",v),sid=st.steamid;
  const vmsg=$("#v-msg",v),vcall=async(path,body)=>{try{await api(path,Object.assign({sid},body||{}));renderSettings()}catch(e){if(vmsg)vmsg.textContent=e.message}};
  const va=$("#v-auto",v);if(va)va.onchange=()=>vcall("/api/voice/settings",{auto:va.checked});
  const vl=$("#v-live",v);if(vl)vl.onchange=()=>vcall("/api/voice/settings",{live:vl.checked});
  const cvo=$("#c-voice",v);if(cvo)cvo.onchange=()=>{try{localStorage.setItem("coach_voice",cvo.checked?"on":"off")}catch(e){}};
  const cin=$("#c-info",v);if(cin)cin.onchange=()=>{try{localStorage.setItem("coach_info",cin.checked?"on":"off")}catch(e){}};
  const cvt=$("#c-voice-test",v);if(cvt)cvt.onclick=()=>{if(!coachSay("Respire. Le round d'avant est fini. Ce round, joue le trade, à côté d'un coéquipier."))cvt.textContent="No French voice of Windows found"};
  const vd=$("#v-dev",v);if(vd){fetch("/api/voice/devices").then(r=>r.json()).then(list=>{if(!Array.isArray(list))return;const cur=(vs.settings||{}).device||"";
    vd.innerHTML=`<option value="">${vs.cs2_device?`The same as CS2 (${esc(vs.cs2_device)})`:"Windows default microphone"}</option>`+list.map(d=>`<option value="${esc(d.name)}" ${d.name===cur?"selected":""}>${esc(d.name)}${d.cs2?" (used by CS2)":d.default?" (Windows default)":""}</option>`).join("")}).catch(()=>{});
    vd.onchange=()=>vcall("/api/voice/settings",{device:vd.value||null})}
  const vst=$("#v-stop",v);if(vst)vst.onclick=()=>vcall("/api/voice/stop");
  $$("[data-vtr]",v).forEach(b=>b.onclick=()=>{b.disabled=true;vcall("/api/voice/transcribe",{id:b.dataset.vtr})});
  $$("[data-vdel]",v).forEach(b=>b.onclick=()=>{if(b.dataset.ok!=="1"){b.dataset.ok="1";b.textContent="Confirm";return}vcall("/api/voice/delete",{id:b.dataset.vdel})});
  const gon=$("#gsi-on",v),goff=$("#gsi-off",v);
  if(gon)gon.onclick=async()=>{gon.disabled=true;try{gsiStatus=await api("/api/gsi/install",{});renderSettings()}catch(e){msg.textContent=e.message;gon.disabled=false}};
  if(goff)goff.onclick=async()=>{goff.disabled=true;try{gsiStatus=await api("/api/gsi/uninstall",{});renderSettings()}catch(e){msg.textContent=e.message;goff.disabled=false}};
  $("#st-save",v).onclick=async()=>{const b=$("#st-save",v);b.disabled=true;msg.textContent="Checking with Steam…";
    try{const j=await api("/api/steam/credentials",{sid,api_key:$("#st-key",v).value.trim(),auth_code:$("#st-auth",v).value.trim(),known_code:$("#st-known",v).value.trim()});
      msg.textContent=j.saved.length?`Saved: ${j.saved.join(" and ")}.`:"Nothing new to save.";setTimeout(renderSettings,900)}
    catch(e){msg.textContent=e.message;b.disabled=false}};
  $("#st-sync",v).onclick=async()=>{msg.textContent="";try{await api("/api/steam/sync",{sid});poll()}catch(e){msg.textContent=e.message}};
  const au=$("#st-auto",v);if(au)au.onchange=async()=>{try{await api("/api/steam/options",{sid,auto_sync:au.checked})}catch(e){msg.textContent=e.message}};
  const oc=$("#o-cs2",v);if(oc)oc.onchange=async()=>{try{await api("/api/app/options",{open_on_cs2:oc.checked})}catch(e){}};
  const ofb=$("#o-fb",v);if(ofb)ofb.onchange=async()=>{try{await api("/api/app/options",{feedback_prompts:ofb.checked})}catch(e){}};
  $$("[data-theme-set]",v).forEach(b=>b.onclick=()=>{store("theme",b.dataset.themeSet);applyTheme(b.dataset.themeSet);$$("[data-theme-set]",v).forEach(x=>x.setAttribute("aria-pressed",x===b))});
  wireUpdate(v);wireShare(v);wireReports(v);wireUsage(v);
  const grb=$("#gr-go",v);if(grb)grb.onclick=async()=>{grb.disabled=true;try{await api(gr.on?"/api/grow/stop":"/api/grow/start",{target:+($("#gr-n",v)||{}).value||gr.target})}catch(e){}renderSettings()};
  $("#st-forget",v).onclick=async()=>{if(!steamForget){steamForget=true;renderSettings();return}steamForget=false;
    try{await api("/api/steam/forget",{sid});renderSettings()}catch(e){msg.textContent=e.message}};
}

// ---------- view: team ----------
const TCOL=["#e8d44d","#4cb87a","#e0663a","#5b9be0","#c77dff"];
let teamSel=null,teamId=null,teamPlan=null,teamIdx=null,teamSug=null,teamQ="",teamMap=null,teamSide="CT",teamLevel=null,teamExec=null;
async function loadTeamIdx(force){if(teamIdx&&!force)return teamIdx;try{const r=await fetch("teams/index.json"+(force?`?t=${Date.now()}`:""));teamIdx=r.ok?await r.json():[]}catch(e){teamIdx=[]}return teamIdx}
async function loadTeam(id){const r=await fetch(`teams/${id}.json?t=${Date.now()}`);if(!r.ok)throw new Error("plan not found");teamPlan=await r.json();teamId=id;
  await Promise.all(Object.keys(teamPlan.plans||{}).map(loadRadar));return teamPlan}
function teamRadarDraw(box,map,level,items){const svg=$("svg",box),g=$("g",box);
  $("image",box).setAttribute("href",D.radars[`${map}:${level}`]||"");svg.setAttribute("viewBox",(D.viewboxes[map]||[0,0,1024,1024]).join(" "));g.replaceChildren();
  const defs=el("defs",{},g),mk=el("marker",{id:"tarrow",viewBox:"0 0 10 10",refX:"7",refY:"5",markerWidth:"5",markerHeight:"5",orient:"auto-start-reverse"},defs);
  el("path",{d:"M0,0 L10,5 L0,10 z",style:"fill:#ff5a4e"},mk);
  const on=it=>it.px&&(!it.level||!level||it.level===level);
  // T lanes: a red arrow toward the site, as thick as the lane is used, with its share of the rounds
  items.filter(it=>it.kind==="lane"&&on(it)&&it.to).forEach(it=>{
    const [x1,y1]=it.px,[x2,y2]=it.to,dx=x2-x1,dy=y2-y1,L=Math.hypot(dx,dy)||1,k=Math.max(0,(L-40)/L);
    tip(el("line",{x1,y1,x2:x1+dx*k,y2:y1+dy*k,"marker-end":"url(#tarrow)",style:`stroke:#ff5a4e;stroke-opacity:.75;stroke-width:${it.w||4};stroke-linecap:round;${it.dash?"stroke-dasharray:10 8":""}`},g),it.title||"");
    if(it.label)el("text",{x:x1,y:y1-10,"text-anchor":"middle",class:"zlabel",style:"fill:#ffb3ad"},g).textContent=it.label});
  items.filter(it=>it.kind==="site"&&on(it)).forEach(it=>{
    el("circle",{cx:it.px[0],cy:it.px[1],r:30,style:"fill:none;stroke:#fff;stroke-opacity:.5;stroke-width:2;stroke-dasharray:4 4"},g);
    el("text",{x:it.px[0],y:it.px[1]+46,"text-anchor":"middle",class:"zlabel"},g).textContent=it.label});
  // grenades: dotted arc from the thrower's spot to where it lands, letter on the landing
  items.filter(it=>it.kind==="nade"&&it.to&&on(it)).forEach(it=>{
    const [x1,y1]=it.px,[x2,y2]=it.to,mx=(x1+x2)/2-(y2-y1)*.15,my=(y1+y2)/2+(x2-x1)*.15;
    el("path",{d:`M${x1},${y1} Q${mx},${my} ${x2},${y2}`,style:`fill:none;stroke:${it.color};stroke-width:2;stroke-dasharray:3 4;opacity:.85`},g);
    tip(el("rect",{x:x2-9,y:y2-9,width:18,height:18,rx:4,style:`fill:${{smoke:"#9aa5b1",flash:"#f2e14c",molotov:"#ff8a3d",he:"#7bd88f"}[it.type]||"#ccc"};stroke:#111;stroke-width:1.5`},g),it.title||"");
    el("text",{x:x2,y:y2+4,"text-anchor":"middle",style:"font:700 11px var(--f-mono);fill:#111"},g).textContent=it.short||""});
  // positions: a disc in the player's color (grey with a number for an extra player), a ring when it is the player's own spot
  items.filter(it=>it.kind==="dot"&&on(it)).forEach(it=>{
    if(it.ring)el("circle",{cx:it.px[0],cy:it.px[1],r:18,style:`fill:none;stroke:${it.color};stroke-width:2.5`},g);
    tip(el("circle",{cx:it.px[0],cy:it.px[1],r:12,style:`fill:${it.color};stroke:#111;stroke-width:2`},g),it.title||"");
    if(it.n)el("text",{x:it.px[0],y:it.px[1]+4,"text-anchor":"middle",style:"font:700 12px var(--f-mono);fill:#111"},g).textContent=it.n;
    el("text",{x:it.px[0],y:it.px[1]-19,"text-anchor":"middle",class:"zlabel"},g).textContent=it.label})}
function teamBuilder(){
  const I=IDX(),own=D.own&&I[D.own]?D.own:S.player;
  if(!teamSel)teamSel=own?[own]:[];
  const chips=teamSel.map((id,i)=>`<button type="button" data-rm="${id}" ${i===0?"disabled":""} aria-label="Remove ${esc((I[id]||{}).name||id)}"><b style="color:${TCOL[i]}">●</b> ${esc((I[id]||{}).name||id)}${i===0?" (you)":" ✕"}</button>`).join("");
  const q=teamQ.toLowerCase(),res=q?D.index.filter(e=>!teamSel.includes(e.steamid)&&!e.minimal&&(e.name.toLowerCase().includes(q)||e.steamid.includes(q))).slice(0,8):[];
  const sug=(teamSug||[]).filter(s=>!teamSel.includes(s.steamid));
  return `<article class="card"><h3>Build the team</h3>
   <p class="note">You and 1 to 4 teammates already analyzed. To add someone new: paste their Steam link in the search bar at the top, then come back here.</p>
   <div class="btns" role="group" aria-label="Members">${chips}</div>
   ${sug.length?`<span class="lbl4" style="color:var(--muted)">Your frequent teammates</span><div class="btns">${sug.map(s=>`<button type="button" data-add="${s.steamid}" ${s.analyzed&&teamSel.length<5?"":"disabled"} title="${s.analyzed?"":"Not analyzed yet"}">${esc(s.name)} <span class="note">${s.together} match${s.together>1?"es":""} together</span></button>`).join("")}</div>`:""}
   <div class="btns" style="align-items:center"><input id="tq" type="search" value="${esc(teamQ)}" placeholder="Find an analyzed player (name, SteamID)" aria-label="Find a player" style="font:14px var(--f-body);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:6px 10px;min-width:260px"></div>
   ${res.length?`<div class="btns">${res.map(e=>`<button type="button" data-add="${e.steamid}" ${teamSel.length<5?"":"disabled"}>${esc(e.name)}${e.archetype?` <span class="note">${esc(e.archetype)}</span>`:""}</button>`).join("")}</div>`:""}
   <div class="row" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">${D.local?`<button type="button" class="primary" id="tbuild" ${teamSel.length>=2?"":"disabled"}>Create the team plan</button>`:`<span class="note">Team plans are created in the local app.</span>`}<span class="note" id="tmsg" role="status"></span></div>
   ${(teamIdx||[]).length?`<span class="lbl4" style="color:var(--muted)">Saved plans</span><div class="btns">${teamIdx.map(t=>`<button type="button" data-team="${t.id}" aria-pressed="${t.id===teamId}">${t.members.map(m=>esc(m.name)).join(" · ")}</button>`).join("")}</div>`:""}</article>`}
function renderTeam(){
  const v=$("#v-team");
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">Cross-data of every member, the base and pros</span><h2>Team</h2></div></div>${teamBuilder()}<div id="tplan"></div>`;
  const tq=$("#tq",v);tq.oninput=()=>{teamQ=tq.value.trim();const pos=tq.selectionStart;renderTeam();const n=$("#tq");n.focus();n.setSelectionRange(pos,pos)};
  $$("[data-add]",v).forEach(b=>b.onclick=()=>{if(teamSel.length<5&&!teamSel.includes(b.dataset.add))teamSel.push(b.dataset.add);teamQ="";renderTeam()});
  $$("[data-rm]",v).forEach(b=>b.onclick=()=>{teamSel=teamSel.filter(x=>x!==b.dataset.rm);renderTeam()});
  $$("[data-team]",v).forEach(b=>b.onclick=async()=>{try{await loadTeam(b.dataset.team);teamSel=teamPlan.members.map(m=>m.steamid);teamMap=null;renderTeam()}catch(e){$("#tmsg",v).textContent=e.message}});
  const tb=$("#tbuild",v);if(tb)tb.onclick=async()=>{tb.disabled=true;$("#tmsg",v).textContent="Crossing the data…";
    try{const j=await api("/api/team",{sid:teamSel[0],ids:teamSel});await loadTeamIdx(true);await loadTeam(j.id);teamMap=null;renderTeam()}catch(e){$("#tmsg",v).textContent=e.message;tb.disabled=false}};
  if(!teamSug&&D.local&&teamSel[0]){fetch(`/api/team/suggest?sid=${teamSel[0]}`).then(r=>r.json()).then(j=>{teamSug=j;if(S.view==="team")renderTeam()}).catch(()=>{teamSug=[]})}
  if(!teamIdx){loadTeamIdx().then(()=>{if(S.view==="team"&&teamIdx.length)renderTeam()})}
  if(teamPlan)teamPlanView($("#tplan",v));
}
function teamPlanView(host){
  const T=teamPlan,col=Object.fromEntries(T.members.map((m,i)=>[m.steamid,TCOL[i]])),nm=Object.fromEntries(T.members.map(m=>[m.steamid,m.name]));
  const maps=Object.keys(T.plans||{});if(!teamMap||!maps.includes(teamMap))teamMap=maps[0];
  const P=T.plans[teamMap];
  const ind=Object.fromEntries((T.individual||[]).map(x=>[x.steamid,x]));
  const igl=T.igl[0],GREY="#8a96a3",pc=v=>v==null?"—":v+"%",rec=r=>r&&r.n?`${r.won}/${r.n}`:"—";
  const nExtra=5-T.size;
  host.innerHTML=`
  <div class="head" style="border-bottom-width:1px"><div style="display:grid;gap:4px"><span class="eyebrow">Plan created ${fmtDate(T.created)} · ${T.size} players${nExtra?` + ${nExtra} extra player${nExtra>1?"s":""}`:""}</span>
    <h2>${T.members.map((m,i)=>`<span style="color:${TCOL[i]}">${esc(m.name)}</span>`).join(" · ")}</h2></div></div>
  <div class="tbl"><table><thead><tr><th>Player</th><th>Profile</th><th>T role</th><th>CT positions</th><th>Individual work</th></tr></thead><tbody>
   ${T.members.map((m,i)=>{const x=ind[m.steamid]||{};return `<tr><td><b style="color:${TCOL[i]}">●</b> ${esc(m.name)}${igl&&igl.steamid===m.steamid?' <span class="probadge">suggested IGL</span>':""}</td>
     <td>${esc(m.archetype||"—")}${m.light?' <span class="note">(limited data)</span>':""}</td><td><b>${esc(m.t_role_name||"—")}</b></td>
     <td class="wrap">${esc(x.ct_role||"—")}</td><td class="wrap">${(x.priorities||[]).slice(0,2).map(esc).join(" · ")}</td></tr>`}).join("")}
   ${nExtra?`<tr><td><b style="color:${GREY}">●</b> Extra player${nExtra>1?"s":""} (${nExtra})</td><td class="note">random teammates</td><td><b>${T.missing_roles.map(esc).join(", ")}</b></td><td class="wrap note">the grey positions on each map</td><td class="note">Tell them their spot in the lobby.</td></tr>`:""}</tbody></table></div>
  <div class="insights">
   <article class="card"><h3>Who calls?</h3><p>Suggestion: <b>${esc(igl.name)}</b>${igl.why.length?` (${igl.why.map(esc).join(", ")})`:""}.</p>
     <p class="note">Ranking: ${T.igl.map(x=>`${esc(x.name)} ${x.score}`).join(" · ")}. Measured on converting advantages, isolated deaths, trades, profile and experience. It's your call: the IGL mostly needs to talk clearly and stay calm.</p></article>
   <article class="card"><h3>Your maps</h3><p>Pick in Premier: <b>${T.picks.length?T.picks.map(MAPN).join(", "):"no pool map with data yet"}</b>${T.to_work.length?` · to work on: ${T.to_work.map(MAPN).join(", ")}`:""}.</p>
     <div class="tbl"><table><thead><tr><th>Map</th><th class="n">Rounds won</th><th class="n">Rounds</th>${T.members.map((m,i)=>`<th class="n" style="color:${TCOL[i]}">${esc(m.name.slice(0,10))}</th>`).join("")}</tr></thead><tbody>
      ${T.maps.filter(r=>r.members_with_data&&!/^cs_/.test(r.map)).slice(0,8).map(r=>`<tr><td>${MAPN(r.map)}${r.premier?' <span class="pill">Premier</span>':""}</td><td class="n">${pc(r.round_win)}</td><td class="n">${r.rounds}</td>
        ${r.per_member.map(x=>`<td class="n">${x.win==null?"—":`${x.win}% <span class="note">(${x.rounds})</span>`}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
     <p class="note">Rounds won by each member on the map (their demos, number of rounds in brackets). Bomb maps only. Since September 22, 2026, each team picks its maps and one of the four is drawn at random.</p></article>
  </div>
  ${maps.length?`<h3>Game plan per map</h3>
  <div class="chips" role="group" aria-label="Map">${maps.map(m=>`<button type="button" data-tmap="${m}" aria-pressed="${m===teamMap}">${MAPN(m)}</button>`).join("")}</div>
  <div class="btns side big" role="group" aria-label="Side"><button type="button" data-tside="CT" aria-pressed="${teamSide==="CT"}">CT · setup</button><button type="button" data-tside="T" aria-pressed="${teamSide==="T"}">T · plays</button></div>
  <div class="stage">${radarShell((P.levels||[]).length>1?`<div class="btns" role="group" aria-label="Level">${P.levels.map(l=>`<button type="button" data-tlevel="${l.key}" aria-pressed="${l.key===(teamLevel||P.levels[0].key)}">${esc(l.name)}</button>`).join("")}</div>`:"")}
   <div style="display:grid;gap:14px;min-width:0" id="tside"></div></div>
  <div id="tplays"></div>
  <div class="insights" id="tcalls"></div>`:`<div class="empty">No map in common with detailed data: play a few matches together, then create the plan again.</div>`}
  <h3>Economy and weapons</h3>
  <div class="insights"><article class="card"><ul>${T.economy.rules.map(r=>`<li>${esc(r)}</li>`).join("")}</ul>
    <p>${T.economy.awp?`AWP: <b>${esc(T.economy.awp)}</b>.`:"No dedicated AWPer: the AWP is only bought when the team is rich."} ${T.economy.pistol_openers.length?`Pistol rounds: ${T.economy.pistol_openers.map(esc).join(", ")} take${T.economy.pistol_openers.length>1?"":"s"} the opening duels.`:""}</p>${srcLinks(T.economy.src,true)}</article>
   <article class="card"><h3>Everyone's force-buy</h3><ul>${T.economy.members.map(x=>`<li><b>${esc(x.name)}</b>: ${x.force?`${esc(x.force)}: ${x.force_win!=null?`${x.force_win}% of ${x.force_n} force-buy rounds won, `:""}${x.force_adr} damage per round`:"not enough force-buy rounds yet (8 needed)"}</li>`).join("")}</ul>
    <p class="note">Cheap weapons only (SMGs, shotguns, pistols, Galil, FAMAS): an AWP or a full rifle isn't a force-buy.</p></article></div>
  ${T.synergy.length?`<h3>You together</h3><div class="tbl"><table><thead><tr><th>Duo</th><th class="n">Matches together</th><th class="n">Rounds won</th><th>Trades (one avenges the other within 5 s)</th></tr></thead><tbody>
   ${T.synergy.map(s=>`<tr><td>${esc(s.name_a)} + ${esc(s.name_b)}</td><td class="n">${s.matches}</td><td class="n">${pc(s.round_win)}</td><td>${esc(s.name_a)} avenges ${esc(s.name_b)} ${s.trades_ab}× · ${esc(s.name_b)} avenges ${esc(s.name_a)} ${s.trades_ba}×</td></tr>`).join("")}</tbody></table></div>`:""}
  ${T.matches.length?`<p class="note">${T.n_matches||T.matches.length} match${(T.n_matches||T.matches.length)>1?"es":""} with at least 2 members on the same team. Latest: ${T.matches.slice(0,6).map(x=>`${MAPN(x.map||"?")} ${x.score?`${x.score.me}-${x.score.them}`:""}`).join(" · ")}.</p>`:""}
  ${T.collective.length?`<h3>Team goals</h3><div class="insights">${T.collective.map(c=>`<article class="card"><h3>${esc(c.title)}</h3><p>${esc(c.do)}</p>
    <p class="note">Team average percentile: ${c.avg_percentile} (${c.members.map(x=>`${esc(x.name)} ${x.percentile}`).join(" · ")}).</p></article>`).join("")}</div>`:""}
  <h3>Individual work for the team</h3>
  <div class="insights">${(T.individual||[]).map(x=>{const i=T.members.findIndex(m=>m.steamid===x.steamid),m=T.members[i];return `<article class="card"><h3 style="color:${TCOL[i]}">${esc(x.name)} · ${esc(x.t_role||"")}</h3>
    <p class="note">${esc(m.t_do||"")}</p><ol>${(x.priorities||[]).map(p=>`<li>${esc(p)}</li>`).join("")}</ol>${x.drill?`<p class="note">Warm-up: ${esc(x.drill)}</p>`:""}</article>`}).join("")}</div>
  ${T.party&&T.party[T.party_key]?`<h3>${esc(T.party[T.party_key].title)}</h3><article class="card"><ul>${T.party[T.party_key].items.map(t=>`<li>${esc(t)}</li>`).join("")}</ul>${srcLinks(T.party[T.party_key].src,true)}</article>`:""}
  ${D.local?`<div class="btns"><button type="button" id="tdel">Delete this plan</button></div>`:""}`;
  $$("[data-tmap]",host).forEach(b=>b.onclick=()=>{teamMap=b.dataset.tmap;teamLevel=null;teamExec=null;teamPlanView(host)});
  $$("[data-tside]",host).forEach(b=>b.onclick=()=>{teamSide=b.dataset.tside;teamLevel=null;teamPlanView(host)});
  $$("[data-tlevel]",host).forEach(b=>b.onclick=()=>{teamLevel=b.dataset.tlevel;teamPlanView(host)});
  const del=$("#tdel",host);if(del)del.onclick=async()=>{if(del.dataset.ok!=="1"){del.dataset.ok="1";del.textContent="Confirm deletion";return}
    try{await api("/api/team/delete",{sid:T.owner,id:T.id});teamPlan=null;teamId=null;await loadTeamIdx(true);renderTeam()}catch(e){}};
  if(!P)return;
  const TH=P.threats,s=x=>x==null?"—":x+" s",sites=P.site_px||{};
  const plays=P.t_plays||[];if(!teamExec||!plays.some(p=>p.key===teamExec))teamExec=plays[0]?plays[0].key:null;
  const PL=plays.find(p=>p.key===teamExec);
  const who=(sid,x)=>sid?col[sid]:GREY,dotN=x=>x.extra?(typeof x.extra==="number"?x.extra:""):"";
  const siteItems=L=>sites[L]?[{kind:"site",px:sites[L],level:TH&&TH.geo_sites&&TH.geo_sites[L]?TH.geo_sites[L].level:null,
    label:TH?`${L} · ${TH.sites[L].odds}% of attacks${TH.sites[L].rush?` · rush ${TH.sites[L].rush}%`:""}`:L}]:[];
  let items=[];
  if(teamSide==="CT"){
    if(TH)["A","B"].forEach(L=>{items.push(...siteItems(L));TH.sites[L].lanes.forEach(ln=>items.push({kind:"lane",px:ln.px,to:sites[L],level:ln.level,w:2+ln.odds/5,label:`${ln.name.split(" / ")[0]} ${ln.odds}%`,
      title:`${ln.name} → ${L}: used in ${ln.odds}% of the attacks${ln.rush?`, ${ln.rush}% of them rushes`:""}`}))});
    P.ct.forEach(sl=>{items.push({kind:"dot",px:sl.px,level:sl.level,color:who(sl.member),n:sl.member?"":sl.extra,ring:sl.yours,label:sl.member?nm[sl.member]:`Extra ${sl.extra}`,title:`${sl.label} · ${sl.zone}`});
      (sl.nades||[]).filter(n=>n.from_px&&n.to_px).slice(0,sl.member?3:1).forEach(n=>items.push({kind:"nade",type:n.type,px:n.from_px,to:n.to_px,level:n.level,color:who(sl.member),short:{smoke:"S",flash:"F",molotov:"M",he:"H"}[n.type],title:`${TYPE[n.type]} ${n.from} → ${n.to}`}))});
  }else if(PL){
    items.push(...siteItems(PL.site));
    PL.lanes.forEach((ln,i)=>items.push({kind:"lane",px:ln.px,to:PL.site_px,level:ln.level,w:i?5:8,label:ln.name}));
    const at={};PL.roles.forEach(r=>{if(!r.lane||!r.lane.px)return;const k=r.lane.px.join(),j=at[k]=(at[k]||0)+1;
      if(r.lane.lurk)items.push({kind:"lane",px:r.lane.px,to:sites[PL.site==="A"?"B":"A"],level:r.lane.level,w:3,dash:true,label:"lurk"});
      items.push({kind:"dot",px:[r.lane.px[0]+((j-1)%3-1)*26,r.lane.px[1]+28+Math.floor((j-1)/3)*26],level:r.lane.level,color:who(r.member),n:r.extra?r.name.replace(/\D/g,""):"",label:r.extra?"":r.name,title:`${r.name}: ${r.role_name}`})});
    PL.nades.filter(n=>n.from_px&&n.to_px).forEach(n=>items.push({kind:"nade",type:n.type,px:n.from_px,to:n.to_px,level:n.level,color:who(n.member),short:{smoke:"S",flash:"F",molotov:"M",he:"H"}[n.type],title:`${TYPE[n.type]} ${n.from} → ${n.to}: ${n.name}`}));
  }
  const cnt={};items.filter(x=>x.kind==="dot"||x.kind==="nade").map(x=>x.level).filter(Boolean).forEach(l=>cnt[l]=(cnt[l]||0)+1);
  const busiest=Object.keys(cnt).sort((a,b)=>cnt[b]-cnt[a])[0];
  const level=teamLevel||busiest||(P.levels&&P.levels[0]?P.levels[0].key:null);
  $$("[data-tlevel]",host).forEach(b=>{b.setAttribute("aria-pressed",b.dataset.tlevel===level);if(cnt[b.dataset.tlevel])b.textContent=`${b.textContent.replace(/ \(\d+\)$/,"")} (${cnt[b.dataset.tlevel]})`});
  const box=$(".radar-box",host),side=$("#tside",host);
  teamRadarDraw(box,teamMap,level,items);
  const nadeLi=n=>`<li><b>${TYPE[n.type]}</b> ${esc(n.from)} → ${esc(nTo(n,teamMap))}${n.role?` <span class="pill">${{anti_rush:"anti-rush",block:"blocks the lane",flash:"flash",damage:"damage"}[n.role]||esc(n.role)}</span>`:""}${n.timer?` <span class="note">around ${esc(n.timer)}</span>`:""}${n.yours?' <span class="pill strong">yours</span>':""}${n.setpos?` <span class="cmd"><code hidden>${esc(n.setpos)}</code><button type="button" title="${esc(n.setpos)}">Copy setpos</button></span>`:""}</li>`;
  if(teamSide==="CT"){
    $(".caption",box).innerHTML=`<span>Red arrows: where the Ts of the base attack from (share of the attacks). Discs: the setup, a ring when it's the player's own strong spot; grey numbers are extra players. Squares: their grenades.</span>`;
    const heavy=P.heavy_site,two=P.ct.filter(sl=>sl.site===heavy).length;
    side.innerHTML=`${TH?`<div class="tread"><b>Where the Ts attack</b> (${TH.rounds} rounds of the base): ${["A","B"].map(L=>`<b>${L}</b> ${TH.sites[L].odds}%${TH.sites[L].rush?` (rush ${TH.sites[L].rush}%)`:""}`).join(" · ")}.
       ${two>=2?`${two} players on ${heavy}, the most attacked site.`:""}</div>`:""}
      <ul class="pl-list">${P.ct.map(sl=>`<li style="border-left-color:${who(sl.member)}"><b>${esc(sl.label)} · ${esc(sl.zone)}</b>: ${sl.member?`<b>${esc(sl.name)}</b>`:`<b>extra player ${sl.extra}</b>`}${sl.why&&sl.why.length?` (${sl.why.map(esc).join(", ")})`:""}.
       ${sl.lane?`<br>Faces <b>${esc(sl.lane.name)}</b>: ${sl.lane.odds}% of the attacks${sl.lane.rush?`, ${sl.lane.rush}% of them rushes`:""}.`:""}
       ${sl.nades&&sl.nades.length?`<ul class="nlist">${sl.nades.slice(0,sl.member?3:2).map(nadeLi).join("")}</ul>`:""}
       <span class="note">${esc(sl.do)}${sl.base?` Base CTs on this spot: ${esc(sl.base)} in duels.`:""}${sl.base_zone?` (The base plays ${esc(sl.base_zone)} instead.)`:""}${sl.t_med?` First duel around ${clock(sl.t_med)}.`:""}</span></li>`).join("")}</ul>
      ${P.rotations.length?`<span class="lbl4" style="color:var(--muted)">Rotations once the bomb is down on the other site</span><ul>${P.rotations.map(r=>`<li><b>${esc(r.name)}</b> to ${r.to}: ${esc(r.route)} (${s(r.travel)}, ${r.died}% die on the way, ${r.n} ${r.who==="pro"?"pro":"base"} rotations)</li>`).join("")}</ul>`:""}`;
  }else{
    $(".caption",box).innerHTML=`<span>${PL?`${esc(PL.label)}: thick arrow = main lane, thin = second lane, dashed = the lurker's. Squares: the grenades (S smoke, F flash, M molotov).`:"No play with enough rounds in the base on this map."}</span>`;
    side.innerHTML=PL?`<div class="btns" role="group" aria-label="Play">${plays.map(p=>`<button type="button" data-texec="${p.key}" aria-pressed="${p.key===teamExec}">${esc(p.label)}</button>`).join("")}</div>
      <div class="tread">In the base: <b>${PL.t_win}%</b> of rounds won by the Ts over ${PL.n} rounds${TH.t_avg!=null?` (map average ${TH.t_avg}%)`:""}${PL.hit_t!=null?`, site taken around ${clock(PL.hit_t)}`:""}. ${PL.team_t&&PL.team_t.n?`You ran it ${PL.team_t.n} time${PL.team_t.n>1?"s":""} together: ${PL.team_t.won} won.`:"You haven't run it together yet."}</div>
      <ul class="pl-list">${PL.roles.map(r=>`<li style="border-left-color:${who(r.member)}"><b>${esc(r.name)} · ${esc(r.role_name)}</b>${r.lane?` · ${esc(r.lane.name)}`:""}<br><span class="note">${esc(r.do)}</span></li>`).join("")}</ul>
      ${PL.nades.length?`<span class="lbl4" style="color:var(--muted)">Grenades</span><div class="lineups">${PL.nades.map(it=>`<article class="lu" data-type="${it.type}" style="cursor:default"><div class="top"><span class="ty">${TYPE[it.type]} · ${esc(it.name)}</span><span class="pill ${it.known?"strong":""}">${it.known?"already thrown":"to learn"}</span></div>
        <div class="route">${esc(it.from)} → ${esc(nTo(it,teamMap))}${it.lane?` <span class="note">(${esc(it.lane)})</span>`:""}</div><div class="meta">${esc(it.how||"")}${it.t!=null?` · around ${clock(it.t)}`:""} · ${it.uses} throws in the base</div>
        ${it.setpos?`<div class="cmd"><code>${esc(it.setpos)}</code><button type="button">Copy</button></div>`:""}</article>`).join("")}</div>`:`<p class="note">Not enough grenades observed toward this site in the base.</p>`}`
      :`<p class="note">Not enough rounds of the base on this map to suggest plays.</p>`;
    $$("[data-texec]",side).forEach(b=>b.onclick=()=>{teamExec=b.dataset.texec;teamLevel=null;teamPlanView(host)});
  }
  copyBtn(side);
  // every play of the base, with the team's own rounds on both sides
  $("#tplays",host).innerHTML=TH&&TH.plays.length?`<h3>Plays of the base on ${MAPN(teamMap)}, and how you did</h3><div class="tbl"><table><thead><tr><th>Play</th><th class="n">Rounds of the base</th><th class="n">T win</th><th class="n">Site taken</th><th class="n">You as T (won)</th><th class="n">You as CT, against it (won)</th></tr></thead><tbody>
    ${TH.plays.map(p=>`<tr><td>${esc(p.label)}</td><td class="n">${p.odds}% <span class="note">(${p.n})</span></td><td class="n">${p.t_win}%</td><td class="n">${s(p.hit_t)}</td><td class="n">${rec(p.team_t)}</td><td class="n">${rec(p.team_ct)}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Plays learned from the paths of the Ts (lanes: the ways in each site). "You" counts the rounds where at least two of you were in the same team.</p>`:"";
  const V=P.vocab||[];
  $("#tcalls",host).innerHTML=`<article class="card"><h3>Shared vocabulary</h3><p class="note">The callouts used on FACEIT and by pros, grouped by area.</p>
    ${V.map(g=>`<p><b>${esc(g.title)}</b>: ${g.zones.map(esc).join(", ")}</p>`).join("")}</article>
   <article class="card"><h3>Everyone's calls</h3><ul>
    <li><b>Entry, anchor</b>: "how many, where, which grenades": "3 B, flash, molotov on box".</li>
    <li><b>Lurker</b>: the rotations heard: "one CT through connector, B is light".</li>
    <li><b>AWPer</b>: "pick mid" or "AWP repositioned", never the same angle twice.</li>
    <li><b>IGL</b>: the plan during buy time, the adjustment at 1:00, the call to save.</li>
    <li><b>Dead</b>: one useful piece of info, then silence.</li></ul></article>
   <article class="card"><h3>Triggers as ${teamSide}</h3><ul>${(T.playbook||[]).filter(x=>x.side===teamSide||isBoth(x)).slice(0,5).map(x=>`<li><b>If ${esc(lc(x.if))}</b> → ${esc(x.then)}</li>`).join("")}</ul>${P.videos&&P.videos.length?`<p class="note"></p>${srcLinks(P.videos,true,`Videos on ${MAPN(teamMap)}:`)}`:""}</article>`;
}
