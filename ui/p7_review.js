
// ---------- view: review (after the session, or the next day) ----------
// what the In game page showed in your matches, checked against their demos (livecheck.py)
function liveCheckBlock(PL){const L=PL.livecheck,maps=Object.entries((L||{}).maps||{}).sort((a,b)=>b[1].matches-a[1].matches);
  if(!maps.length)return D.local?`<h3>Live check</h3><p class="note">After your next match with the In game page open, I compare what I showed you with what the demo says: the site read, the rushes, path 1, the buys, the site after the plant.</p>`:"";
  const c=(v,n,good=60)=>v==null?`<td class="note">—</td>`:`<td><b class="${v>=good?"good":v<good-15?"bad":""}">${v}%</b> <span class="note">${n}</span></td>`;
  const K=(L||{}).calib||{},cal=[K.site_n?`site read ${K.site_T>1.05?`was too sure of itself: its odds are flattened (×${K.site_T})`:K.site_T<.95?`was too shy: its odds are sharpened (×${K.site_T})`:"is right as it is"} · ${K.site_n} rounds`:"",
    K.rush_n&&(K.rush[0]!==1||K.rush[1]!==0)?`rush odds ${K.rush[1]>0?"raised":"lowered"} · ${K.rush_n} rounds`:"",K.plant_n&&Math.abs(K.plant_T-1)>.05?`site after the plant ${K.plant_T>1?"less":"more"} sure · ${K.plant_n} rounds`:"",
    K.path_n&&K.path_d?`paths' % ${K.path_d>0?"raised":"lowered"} · ${K.path_n} rounds`:""].filter(Boolean);
  return `<h3>Live check</h3><p class="note">What the In game page showed, round by round, against what the demo says. The more matches, the more it says about each map.</p>
   ${cal.length?`<p><b>Automatic calibration</b>: ${cal.map(esc).join(" · ")}. With few rounds the change stays small; it grows with your matches.</p>`:""}
   <div style="overflow-x:auto"><table class="lc"><thead><tr><th>Map</th><th>Matches</th><th>CT: site read right</th><th>CT: rush read right</th><th>T: path 1 played</th><th>T: won with path 1 / other</th><th>Buy like the advice</th><th>Site found after the plant</th></tr></thead>
   <tbody>${maps.map(([m,a])=>`<tr><td><b>${esc(MAPN(m))}</b></td><td>${a.matches}</td>${c(a.site_right,a.site_n,55)}${c(a.rush_right,a.rush_n,70)}${c(a.followed,a.t_n,40)}
     <td>${a.win_followed!=null||a.win_other!=null?`<b>${a.win_followed??"—"}%</b> / ${a.win_other??"—"}%`:`<span class="note">—</span>`}</td>${c(a.buy_same,a.buy_n,60)}${c(a.plant_right,a.plant_n,70)}</tr>`).join("")}</tbody></table></div>`}

function callsBlock(PL){const C=PL.calls||[];if(!C.length)return D.local?`<h3>Your calls</h3><p class="note">No recording yet: turn on "Your calls" in <a href="#settings" style="color:var(--ct)">Settings</a>, play, and I analyze your communication after the match.</p>`:"";
  const a=C[0],pct=(x,n)=>n?Math.round(100*x/n)+"%":"—";
  const src=((PL.phases||[]).flatMap(ph=>ph.items).find(i=>i.id==="info_calls")||{}).src;
  return `<h3>Your calls</h3>
   <p class="note">${a.map?MAPN(a.map):"Match"} · ${fmtDate(a.start)} · ${a.utterances} phrases, ${(a.speech_s||0)<60?`${Math.round(a.speech_s||0)} s`:`${Math.round(a.speech_s/60)} min`} of speech${a.match?"":" · match not analyzed yet: update your profile"}${a.aligned?"":" · without game detection, calls aren't lined up with rounds"}.</p>
   <div class="gauge">
    <div><b>${a.deaths?pct(a.deaths-a.silent_deaths,a.deaths):"—"}</b><span>of your deaths preceded by a call (10 s before)</span></div>
    <div><b>${a.info?a.complete_share+"%":"—"}</b><span>of your calls say where and how many</span></div>
    <div><b>${a.throws?pct(a.announced,a.throws):"—"}</b><span>of your grenades called</span></div>
    <div><b>${a.clutch_talk_rounds}</b><span>teammate clutch${a.clutch_talk_rounds===1?"":"es"} where you talked</span></div></div>
   <ul class="pl-list">${a.tips.map(t=>`<li class="coach">${esc(t)}</li>`).join("")}</ul>
   ${a.examples.length?`<p class="note">Your best calls: ${a.examples.map(x=>"“"+esc(x)+"”").join(" · ")}</p>`:""}
   ${heardBlock(C)}${teamCallsBlock(C)}
   ${a.rounds.length?`<details><summary style="cursor:pointer">Your calls round by round</summary><div class="tbl" style="margin-top:8px"><table><thead><tr><th class="n">Round</th><th>What you said (seconds into the round)</th><th class="n">Died at</th></tr></thead><tbody>
     ${a.rounds.map(r=>`<tr><td class="n">${r.round}</td><td class="wrap">${r.texts.length?r.texts.map(x=>`<span class="${x.kind==="tilt"?"bad":""}">${x.t} s: ${esc(x.text)}</span>`).join("<br>"):'<span class="note">nothing</span>'}</td><td class="n">${r.died_t==null?"alive":Math.round(r.died_t)+" s"}</td></tr>`).join("")}</tbody></table></div></details>`:""}
   ${srcLinks(src,true)}`}
// what your team could hear (the demos' sounds and everyone's positions) and what you called of it (04/10)
const SND={step:"running",shot:"shots",quiet:"silenced shots",throw:"a grenade's pin",reload:"a reload",scope:"a scope",plant:"the plant",defuse:"the defuse"};
const WHY={you_died:"you died right after",enemy_died:"it died right after",shared:"a teammate heard it too",far:"far",talking:"you were talking",none:"nothing in the way"};
const WHY_C={you_died:"var(--bad)",enemy_died:"var(--good)",shared:"var(--ct)",far:"var(--muted)",talking:"var(--flash)",none:"var(--t)"};
function heardBlock(C){const H=C.filter(a=>a.heard&&a.heard.heard);if(!H.length)return "";
  const pc=(x,n)=>n?Math.round(100*x/n)+"%":"—",S=k=>H.reduce((s,a)=>s+(a.heard[k]||0),0),SP=k=>H.reduce((s,a)=>[s[0]+((a.heard[k]||{}).n||0),s[1]+((a.heard[k]||{}).called||0)],[0,0]);
  const callable=S("callable"),called=S("called"),alone=SP("alone"),shared=SP("shared"),far=SP("far"),near=SP("near"),fights=SP("fights");
  const rs=H.map(a=>a.heard.react_s).filter(x=>x!=null).sort((x,y)=>x-y),react=rs.length?rs[Math.floor(rs.length/2)]:null;
  const why=Object.keys(WHY).map(k=>({k,v:H.reduce((s,a)=>s+((a.heard.why_not||{})[k]||0),0)})),kinds={};
  H.forEach(a=>Object.entries(a.heard.by_kind||{}).forEach(([k,v])=>{const o=kinds[k]||(kinds[k]=[0,0]);o[0]+=v.n;o[1]+=v.called}));
  const h=H[0].heard,L=(h.list||[]);
  return `<h3>What you heard, and what you called</h3>
   <p class="note">From the demos of your ${H.length} last recorded match${H.length>1?"es":""}: where everyone was, the enemies' shots, reloads, scopes, the bomb, and their running (faster than walking). Rough distances (a running enemy within about 1,100 units, a shot 2,000), walls not counted. Your own fights apart: ${fights[0]} sounds heard while you were shooting or being shot.</p>
   <div class="gauge">
    <div><b>${pc(called,callable)}</b><span>of the enemy sounds you heard called (${callable}, outside your fights)</span></div>
    <div><b>${pc(alone[1],alone[0])}</b><span>when only you could hear them (${alone[0]}) · ${pc(shared[1],shared[0])} when a teammate could too</span></div>
    <div><b>${react!=null?react+" s":"—"}</b><span>from hearing it to your call</span></div>
    <div><b>${pc(S("right"),called)}</b><span>of these calls name the place</span></div></div>
   <p>Close sounds: <b>${pc(near[1],near[0])}</b> called · far: <b>${pc(far[1],far[0])}</b> · ${Object.entries(kinds).sort((x,y)=>y[1][0]-x[1][0]).slice(0,3).map(([k,v])=>`${SND[k]||k}: <b>${pc(v[1],v[0])}</b> (${v[0]})`).join(" · ")}</p>
   ${callable-called?`<p class="note">The ones you did not call, and what was around them:</p>
   <div class="fbar">${why.filter(x=>x.v>0).map(x=>`<i style="flex:${x.v};background:${WHY_C[x.k]}"><title>${WHY[x.k]}: ${x.v}</title></i>`).join("")}</div>
   <div class="vleg">${why.filter(x=>x.v>0).map(x=>`<span><i style="background:${WHY_C[x.k]}"></i>${WHY[x.k]}: ${x.v}</span>`).join("")}</div>`:""}
   ${(h.mates||[]).length?`<p class="note">Who else heard them (${H[0].map?MAPN(H[0].map):"last match"}): ${h.mates.map(m=>`${esc(m.name)} ${m.heard}${m.only?` (only them: ${m.only})`:""}`).join(" · ")}${h.missed_by_you?` · ${h.missed_by_you} that you could not hear`:""}.</p>`:""}
   ${L.length?`<details><summary style="cursor:pointer">Sound by sound, ${H[0].map?MAPN(H[0].map):"last match"}</summary><div class="tbl" style="margin-top:8px"><table><thead><tr><th class="n">Round</th><th class="n">Time</th><th>Where</th><th>What</th><th>Who could hear it</th><th>You</th></tr></thead><tbody>
     ${L.map(x=>`<tr><td class="n">${x.round}</td><td class="n">${Math.round(x.t)} s</td><td>${esc(x.place||"—")}</td><td>${x.n>1?x.n+" enemies, ":""}${SND[x.kind]||esc(x.kind)}</td><td class="wrap">${x.who.map(esc).join(", ")}</td>
       <td class="wrap">${x.fight?'<span class="note">your fight</span>':x.called?`<span class="good">“${esc(x.called)}”</span> <span class="note">${x.react!=null?x.react+" s":""}</span>`:`<span class="note">not called: ${WHY[x.why]||"—"}</span>`}${x.team_called?' <span class="pill">your team called it</span>':""}</td></tr>`).join("")}</tbody></table></div></details>`:""}`}
// after your team's calls naming a place (your team's sound, recorded when every teammate agreed): where you went
function teamCallsBlock(C){const T=C.filter(a=>a.team_calls&&a.team_calls.calls);if(!T.length)return "";
  const S=k=>T.reduce((s,a)=>s+(a.team_calls[k]||0),0),n=S("calls"),pc=x=>n?Math.round(100*x/n)+"%":"—",t=T[0].team_calls;
  const W={toward:"went toward it",away:"went the other way",stayed:"stayed",there:"already there",died:"died"};
  return `<h3>After your team's calls</h3>
   <p class="note">Your teammates' calls that name a place (${n}, in ${T.length} match${T.length>1?"es":""} where they agreed to be recorded), and where you went in the next 8 seconds.</p>
   <div class="gauge"><div><b>${pc(S("toward"))}</b><span>you went toward the place called</span></div><div><b>${pc(S("stayed"))}</b><span>you stayed where you were</span></div>
    <div><b>${pc(S("away"))}</b><span>you went the other way</span></div><div><b>${t.react_s!=null?t.react_s+" s":"—"}</b><span>from their call to your move</span></div></div>
   <details><summary style="cursor:pointer">Call by call, ${T[0].map?MAPN(T[0].map):"last match"}</summary><div class="tbl" style="margin-top:8px"><table><thead><tr><th class="n">Round</th><th class="n">Time</th><th>Your team said</th><th>You</th></tr></thead><tbody>
     ${t.list.map(x=>`<tr><td class="n">${x.round}</td><td class="n">${Math.round(x.t)} s</td><td class="wrap">“${esc(x.text)}”</td><td>${W[x.went]||esc(x.went)}${x.react!=null?` <span class="note">after ${x.react} s</span>`:""}</td></tr>`).join("")}</tbody></table></div></details>`}
// the mood of each recorded match: one column per round (background: won or lost; bar: your damage), dots above for
// what you felt (said with "coach <word>": ringed), a line where the sides change; and what a frustrated moment costs
const MOOD_C={frustration:"var(--bad)",doubt:"var(--flash)",suspicion:"#b07ce8",positive:"var(--good)",note:"var(--muted)"};
function moodBlock(PL){const C=(PL.calls||[]).filter(a=>a.aligned&&(a.rounds||[]).some(r=>r.dmg!=null));if(!C.length)return "";const MS=PL.mood;
  const strip=a=>{const rs=a.rounds,n=rs.length,W=1000,H=70,cw=W/n;
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:1100px;display:block" role="img" aria-label="Rounds and feelings">${rs.map((r,i)=>{const x=i*cw,h=Math.round(30*Math.min(1,(r.dmg||0)/200)),col=r.won?"var(--good)":"var(--bad)";
      const ms=(r.moods||[]).filter(m=>MOOD_C[m.kind]).slice(0,2),sw=i&&rs[i-1].side&&r.side&&rs[i-1].side!==r.side;
      return `${sw?`<line x1="${x}" y1="0" x2="${x}" y2="${H-12}" stroke="var(--muted)" stroke-dasharray="3 3"/>`:""}
        <rect x="${x+1}" y="20" width="${cw-2}" height="36" rx="2" fill="${r.won==null?"var(--line)":col}" fill-opacity=".16"/>
        <rect x="${x+cw*.25}" y="${56-h}" width="${cw*.5}" height="${h}" rx="1" fill="${r.won==null?"var(--muted)":col}" opacity=".85"/>
        ${ms.map((m,j)=>`<circle cx="${x+cw/2}" cy="${14-j*8}" r="3.6" fill="${MOOD_C[m.kind]}"${m.coach?` stroke="var(--ink)" stroke-width="1.4"`:""}><title>${esc(m.word||m.kind)}</title></circle>`).join("")}
        <text x="${x+cw/2}" y="${H-1}" text-anchor="middle" class="vct">${r.round}</text>`}).join("")}</svg>`};
  const cnt=a=>Object.entries(a.moods||{}).filter(([k,v])=>v&&MOOD_C[k]).map(([k,v])=>`<span class="vchip" style="color:${MOOD_C[k]}">● ${v}</span>`).join("");
  return `<h3>Your mood, match by match</h3>
   <div class="vleg"><span><i style="background:var(--bad)"></i>frustration</span><span><i style="background:var(--flash)"></i>doubt</span><span><i style="background:#b07ce8"></i>suspicion</span><span><i style="background:var(--good)"></i>positive</span><span><i style="background:var(--muted)"></i>a note</span><span>ringed: said with "coach …"</span><span>bar: your damage · background: round won / lost</span></div>
   ${MS&&MS.after&&MS.other?`<div class="gauge"><div><b>${MS.after.adr} <small>vs ${MS.other.adr}</small></b><span>ADR in the 3 rounds after a frustrated moment (${MS.after.n} rounds) vs the others</span></div><div><b>${MS.after.won}% <small>vs ${MS.other.won}%</small></b><span>rounds won after it vs the others</span></div></div>`:""}
   ${C.slice(0,4).map(a=>`<div class="mood-row"><div class="mood-h"><b>${a.map?MAPN(a.map):"Match"}</b><span class="note">${fmtDate(a.start)}</span>${cnt(a)}</div>${strip(a)}</div>`).join("")}`}
// what the demos say about the frustrations of the game: blocks both ways, how your flashes are played, team flashes,
// and the enemies whose kills look odd or who got banned (indicators, not proof)
function factsBlock(PL){const F=PL.facts;if(!F||!F.matches)return "";const fy=F.flashes.yours,pm=x=>(x/F.matches).toFixed(1),pc=(x,n)=>n?Math.round(100*x/n)+"%":"—";
  const bar=parts=>`<div class="fbar">${parts.filter(x=>x.v>0).map(x=>`<i style="flex:${x.v};background:${x.c}"><title>${esc(x.l)}: ${x.v}</title></i>`).join("")}</div>`;
  const S=F.suspects||[];
  return `<h3>What the demos say · your last ${F.matches} matches</h3>
   <div class="gauge">
    <div><b>${pm(F.blocks.by_n)} <small>vs ${pm(F.blocks.on_n)}</small></b><span>blocks per match: a teammate blocks you vs you block a teammate${F.blocks.by.length?` (most: ${F.blocks.by.slice(0,2).map(x=>esc(x.name)).join(", ")})`:""}</span></div>
    <div><b>${pc(fy.mate_used,fy.n)}</b><span>of your flashes that blind (${fy.n}): a teammate shoots behind within 2.5 s</span></div>
    <div><b>${pc(fy.mate_early,fy.n)}</b><span>a teammate peeked and got hit before your flash popped</span></div>
    <div><b>${pm(F.teamflash.by_n)} <small>vs ${pm(F.teamflash.on_n)}</small></b><span>team flashes per match: on you vs by you</span></div></div>
   ${fy.n?`${bar([{v:fy.mate_used,c:"var(--good)",l:"a teammate shot behind"},{v:fy.self_used,c:"var(--ct)",l:"only you shot"},{v:fy.unused,c:"var(--muted)",l:"nobody shot"}])}
   <div class="vleg"><span><i style="background:var(--good)"></i>a teammate shoots behind</span><span><i style="background:var(--ct)"></i>only you</span><span><i style="background:var(--muted)"></i>nobody: say "flash" before throwing</span></div>`:""}
   ${S.length?`<h3>Enemies worth a look</h3>
   <div class="tbl"><table><thead><tr><th>Player</th><th>Match</th><th class="n">Kills</th><th class="n" title="kills on a player the killer never saw in the 3 s before">👁 unseen</th><th class="n" title="through smoke">🌫 smoke</th><th class="n" title="first hits under 0.15 s after first seeing">⚡ fast</th><th>Bans</th></tr></thead><tbody>
    ${S.map(x=>`<tr><td><a href="https://steamcommunity.com/profiles/${esc(x.steamid)}" target="_blank" rel="noopener" style="color:var(--ct)">${esc(x.name)}</a>${x.flag?' <span class="pill weak">odd</span>':""}</td><td>${MAPN(x.map)} · ${fmtDate(x.time)}</td><td class="n">${x.kills}</td>
      <td class="n">${x.unseen+x.wallbang_unseen}</td><td class="n">${x.thrusmoke}</td><td class="n">${x.fast==null?"—":x.fast+"%"}</td>
      <td>${x.vac||x.game?`<span class="pill ${x.ban_after?"weak":""}">${x.vac?`VAC ${x.vac}`:""}${x.vac&&x.game?" · ":""}${x.game?`game ${x.game}`:""} · ${x.ban_after?"since this match":`${x.ban_days} days ago`}</span>`:'<span class="note">none</span>'}</td></tr>`).join("")}</tbody></table></div>
   <p class="note">Indicators from the demo, not proof: the lobby's usual share of odd kills is high (smokes, prefires). A ban "since this match" says more than anything else. Report in Overwatch rather than during the game.${F.bans_checked?"":" Steam bans not checked: no API key."}</p>`:`<p class="note">No enemy stands out in these matches${F.bans_checked?", and none of them is banned":""}.</p>`}`}
// the review as plan.py builds it; a plan written in the "pro review" format (quick_brief, map_briefs, deep_dive) keeps it
// whole under raw (04/10: a plan written by a server still running that format crashed this page)
const reviewOf=PL=>{const R=PL.review;return R&&!R.session&&R.raw&&R.raw.session?R.raw:R&&R.session?R:null};
// HLTV's rating colors: under 0.85, 0.85-0.95, 0.95-1.05, 1.05-1.20, over 1.20
const rtCls=r=>r==null?"":r>=1.2?"rt-elite":r>=1.05?"rt-good":r>=.95?"rt-avg":r>=.85?"rt-low":"rt-bad";
const rtBadge=r=>r==null?`<span class="note">—</span>`:`<span class="rt ${rtCls(r)}">${(+r).toFixed(2)}</span>`;
// the rating match by match: a dot per match (green won, red lost), the session's bright on a band, the line at 1.00
function ratingSpark(T){if(!T||T.length<2)return "";const W=640,H=120,pad=12,rs=T.map(x=>x.rating),lo=Math.min(.4,...rs),hi=Math.max(1.8,...rs);
  const X=i=>pad+i*(W-2*pad)/(T.length-1),Y=r=>H-pad-(r-lo)/(hi-lo)*(H-2*pad),first=T.findIndex(x=>x.recent),bx=first>0?(X(first-1)+X(first))/2:pad;
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rating match by match">
   <rect x="${bx}" y="0" width="${W-bx}" height="${H}" rx="6" fill="var(--ct)" opacity=".08"/>
   <line x1="${pad}" x2="${W-pad}" y1="${Y(1)}" y2="${Y(1)}" stroke="var(--muted)" stroke-dasharray="4 4" opacity=".55"/>
   <text x="${pad}" y="${Y(1)-5}" class="vct">1.00</text>
   <polyline points="${T.map((x,i)=>`${X(i).toFixed(1)},${Y(x.rating).toFixed(1)}`).join(" ")}" fill="none" stroke="var(--ink)" stroke-opacity=".3" stroke-width="1.5"/>
   ${T.map((x,i)=>`<circle cx="${X(i).toFixed(1)}" cy="${Y(x.rating).toFixed(1)}" r="${x.recent?5:3.2}" fill="${x.result==="win"?"var(--good)":x.result==="loss"?"var(--bad)":"var(--muted)"}" opacity="${x.recent?1:.45}"><title>${esc(MAPN(x.map))} · ${esc(fmtDate(x.time))} · ${x.rating}</title></circle>`).join("")}</svg>`}
// 1 · the brief: the session in 2 minutes
function reviewBrief(R,f){const T=R.trend||[],rec=T.filter(x=>x.recent),bef=T.filter(x=>!x.recent),avg=a=>a.length?a.reduce((s,x)=>s+x.rating,0)/a.length:null;
  const ra=avg(rec),rb=avg(bef),M=R.maps||[],ng=M.reduce((s,m)=>s+m.games,0),adr=ng?M.reduce((s,m)=>s+m.adr*m.games,0)/ng:null,PI=(R.pro||{}).items||[];
  // a read's name: the analyst reads carry an id (named in readsOf().meta, as the deep dive does), the older insights a title (05/10: the bullets were empty)
  const RM=readsOf().meta||{},rdT=i=>i.title||(i.id==="spot"?`Deaths at ${i.place} (${MAPN(i.map)})`:(RM[i.id]||{}).title||i.id);
  const works=[...R.changes.filter(c=>c.better).slice(0,2).map(c=>`${esc(c.label)}: ${f(c.before,c.unit)} → <b>${f(c.after,c.unit)}</b>`),
    ...PI.filter(i=>i.severity==="positive").map(i=>`${esc(rdT(i))} <span class="note">(${i.value} of ${i.of})</span>`),
    ...(()=>{const top=M.filter(m=>m.rating>=1.2).sort((a,b)=>b.rating-a.rating).slice(0,3);   // the maps you played well
      return top.length?[`Strong on ${top.map(m=>`${esc(MAPN(m.map))} ${rtBadge(m.rating)}`).join(", ")}`]:[]})()].slice(0,3);
  const watch=[...R.changes.filter(c=>!c.better).slice(0,2).map(c=>`${esc(c.label)}: ${f(c.before,c.unit)} → <b>${f(c.after,c.unit)}</b>`),
    ...PI.filter(i=>i.severity!=="positive").map(i=>`${esc(rdT(i))} <span class="note">(${i.value} of ${i.of})</span>`)].slice(0,3);
  const a0=(R.axes||[])[0],li=xs=>xs.length?`<ul>${xs.map(x=>`<li>${x}</li>`).join("")}</ul>`:"";
  return `<section class="tier" id="tier1"><div class="tier-h"><b>1</b><h3>Quick brief</h3><span class="note">the session in 2 minutes</span></div>
   <div class="brief">
    <div class="tiles">
     <div class="tile"><span class="eyebrow">Record</span><b class="num big">${R.session.wins}-${R.session.losses}</b><span class="note">${R.session.games} game${R.session.games>1?"s":""}</span></div>
     <div class="tile"><span class="eyebrow">Rating</span><b class="big">${rtBadge(ra)}</b><span class="note">${rb!=null&&ra!=null?`<span class="${ra>=rb?"good":"bad"}">${ra>=rb?"+":"−"}${Math.abs(ra-rb).toFixed(2)}</span> vs ${rb.toFixed(2)} before`:""}</span></div>
     <div class="tile"><span class="eyebrow">ADR</span><b class="num big">${adr==null?"—":adr.toFixed(1)}</b><span class="note">damage per round</span></div>
     <div class="tile"><span class="eyebrow">Maps</span><b class="num big">${M.length}</b><span class="note">${M.map(m=>esc(MAPN(m.map))).join(" · ")}</span></div>
    </div>
    <div class="spark-box">${ratingSpark(T)}<span class="note">Your rating match by match: this session on the band, the ${bef.length} matches before dimmed. Green won, red lost.</span></div>
   </div>
   <div class="brief3">
    <article class="card b-good"><span class="eyebrow">What works</span>${li(works)||`<p class="note">Nothing stands out above your usual level.</p>`}</article>
    <article class="card b-bad"><span class="eyebrow">Watch out</span>${li(watch)||`<p class="note">Nothing slips: your numbers hold.</p>`}</article>
    ${focusCard(P(),R.next&&/^Fix what is slipping/.test(R.next)?`<p class="note">Also this session: ${esc(R.next)}</p>`:"")}
   </div></section>`}
// 2 · map by map: each map of the session
function reviewMaps(R){const M=R.maps||[];if(!M.length)return "";
  const side=(m,s)=>{const x=m.sides[s],pc=x.of?Math.round(100*x.won/x.of):null;
    return `<div class="mc-side"><span class="side-tag ${s}">${s}</span><div class="mc-bar"><i style="width:${pc||0}%;background:var(--${s==="T"?"t":"ct"})"></i></div><b class="num">${pc==null?"—":pc+"%"}</b><span class="note">${x.won}/${x.of} rounds</span></div>
     ${x.play?`<p class="mc-note"><span class="good">▲</span> ${x.play}</p>`:""}${x.avoid?`<p class="mc-note"><span class="bad">▼</span> ${x.avoid}</p>`:""}`};
  return `<section class="tier" id="tier2"><div class="tier-h"><b>2</b><h3>Map by map</h3><span class="note">this session · round wins per side, what to play and to avoid there</span></div>
   <div class="mapcards">${M.map(m=>`<article class="mapcard"><div class="mc-h"><b>${esc(MAPN(m.map))}</b><span class="res ${m.wins>m.losses?"win":m.wins<m.losses?"loss":"draw"}">${m.wins}-${m.losses}</span>
     ${rtBadge(m.rating)}<span class="note num">ADR ${m.adr}</span></div>${side(m,"T")}${side(m,"CT")}
     <button type="button" class="mc-prep" data-prepmap="${esc(m.map)}">Prepare this map →</button></article>`).join("")}</div></section>`}
// 3 · the analyst's reads of the session (from the demos), against the base and the pros
function reviewInsights(R){const X=R.pro||{},I=X.items||[];if(!X.matches)return "";
  if(!I.length||I[0].ref!==undefined||I[0].title===undefined)return readsSection(P(),X,"Analyst reads",`What a team's analyst points at in the demos of this session's ${X.matches} match${X.matches>1?"es":""}, against the base and the pros.`)||
    `<h3>Analyst reads</h3><p>Nothing to say yet on this session's matches.</p>`;
  const P0=X;
  const lab={high:"priority",medium:"watch",positive:"strength"};
  return `<h3>Pro insights</h3><p class="note">What an analyst points at in the demos of this session's ${P0.matches} match${P0.matches>1?"es":""}, with enough cases to say it.</p>
   ${I.length?`<div class="ins">${I.map(i=>`<article class="ins-${i.severity}"><span class="eyebrow">${lab[i.severity]}</span><h4>${esc(i.title)}</h4><p>${esc(i.detail)}</p>
     <div class="pbar"><i style="width:${Math.round(100*i.value/Math.max(1,i.of))}%"></i></div><span class="note num">${i.value} of ${i.of}</span></article>`).join("")}</div>`
     :`<p>Nothing stands out: no re-peek after your kills, deaths without impact, unused flashes or death spot above the usual.</p>`}`}
function renderReview(){const p=P(),v=$("#v-review"),PL=p.advice.plan||{},R=reviewOf(PL),X=PL.experiments||{};
  const head=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)}${R?` · ${esc(R.label)}, compared with your previous ${R.n_before} matches`:""}</span><h2>Review</h2></div>
    ${R?`<div class="record"><span>${R.session.wins}<small>wins</small></span><span>${R.session.losses}<small>losses</small></span></div>`:""}</div>`;
  if(!R){v.innerHTML=head+`<div class="empty">The review compares your latest matches with the previous ones: it takes at least 3 matches analyzed with their demo.${p.light?" This profile has no demo yet.":""}</div>
    ${(p.advice.rules||[]).length?`<h3>Your focus areas</h3>${findings(p.advice.rules.slice(0,3).map((r,i)=>({level:i<1?"high":"mid",title:r.title,evidence:r.why,fix:r.do,drills:r.drills,sources:r.sources})))}`:""}`;return}
  const f=(x,u)=>fmtU(x,u),TREND={better:"strong",worse:"weak",mieux:"strong","moins bien":"weak"};
  v.innerHTML=head+`
   <nav class="tier-nav" aria-label="Review tiers"><a href="#tier1" data-tier="tier1">1 · The session</a><a href="#tier2" data-tier="tier2">2 · Map by map</a><a href="#tier3" data-tier="tier3">3 · The details</a><a href="#profile">Your profile →</a></nav>
   ${reviewBrief(R,f)}
   ${reviewMaps(R)}
   <section class="tier" id="tier3"><div class="tier-h"><b>3</b><h3>Deep dive</h3><span class="note">every change and its possible reasons, the demos' insights, your matches</span></div>
   <h3>What changed</h3>
   ${R.changes.length?`<div class="chg">${R.changes.map(c=>`<article class="${c.better?"better":"worse"}"><span class="eyebrow">${esc(c.label)}</span>
     <span class="ba">${f(c.before,c.unit)}<span class="arrow" aria-hidden="true">→</span><span class="${c.better?"good":"bad"}">${f(c.after,c.unit)}</span> <span class="lvl ${c.level==="clear"||c.level==="net"?"clear":"trend"}">${c.level==="clear"||c.level==="net"?"clear gap":"trend"}</span></span>
     <span>${c.better?"Improving":"Slipping"} over ${esc(R.label)} against the ${c.n_before} matches before.</span>
     ${c.why.length?`<details><summary class="mini" style="cursor:pointer">Possible reasons (to check over the next matches)</summary><ul class="why">${c.why.map(w=>`<li>${esc(w)}</li>`).join("")}</ul></details>`:`<span class="note">${c.better?"No single cause in your data: keep doing what you did in these games.":"No obvious explanation in your data: keep an eye on it."}</span>`}</article>`).join("")}</div>`
     :`<p>Nothing moved clearly: your numbers are stable.</p>`}
   ${R.stable.length?`<p class="note">Stable: ${R.stable.map(esc).join(" · ")}.</p>`:""}
   ${reviewInsights(R)}
   <div class="cols3" style="grid-template-columns:repeat(auto-fit,minmax(340px,1fr))">
    <div style="display:grid;gap:10px;align-content:start"><h3>Your last session</h3>
     <div class="tbl"><table><thead><tr><th>Date</th><th>Map</th><th>Score</th><th class="n">Rating</th></tr></thead><tbody>${R.session.matches.map(x=>`<tr class="click" data-mid="${x.id}" tabindex="0"><td>${fmtDate(x.time)}</td><td>${MAPN(x.map)}</td><td><span class="res ${x.result}">${x.score.me}-${x.score.them}</span></td><td class="n">${rtBadge(x.rating)}</td></tr>`).join("")}</tbody></table></div>
     <p class="note">Click a match to open it.</p></div>
    <div style="display:grid;gap:10px;align-content:start"><h3>Your focus areas</h3>
     <div class="axes">${R.axes.map(a=>`<article class="card"><h3>${esc(a.short||a.title)}</h3><p class="note">${esc(a.title)}</p>
       ${a.kpi&&a.before!=null?`<p>${esc(a.kpi_label)}: ${f(a.before,a.unit)} → <b>${f(a.after,a.unit)}</b> ${a.trend&&a.trend!=="stable"?`<span class="pill ${TREND[a.trend]||""}">${a.trend==="mieux"?"better":a.trend==="moins bien"?"worse":esc(a.trend)}</span>`:""}</p>`:""}
       ${a.do.length?`<ul>${a.do.map(d=>`<li>${esc(d)}</li>`).join("")}</ul>`:""}${a.drills.length?`<p class="note">Drill: ${esc(a.drills[0])}</p>`:""}${srcLinks(a.sources,true)}</article>`).join("")}</div></div>
   </div>
   ${callsBlock(PL)}
   ${moodBlock(PL)}
   ${factsBlock(PL)}
   ${liveCheckBlock(PL)}
   ${R.tests.active.length?`<p class="note">Running test${R.tests.active.length>1?"s":""}: ${R.tests.active.map(e=>esc(e.title)).join(" · ")}. Your tests and the ones worth starting are in <a href="#profile" style="color:var(--ct)">Profile</a>.</p>`:""}
   ${R.tests.done.length?`<details><summary style="cursor:pointer">Finished experiments (${R.tests.done.length})</summary><div class="exps" style="margin-top:10px">${R.tests.done.map(expCard).join("")}</div></details>`:""}
   <p class="note" id="xmsg" role="status"></p>
   <div class="linkrow"><a href="#profile">Your profile: strengths, axes, evidence</a><a href="#matches">Every match</a></div>
   </section>`;
  wireExp(v,X,p);wireFocus(v,p,renderReview);
  $$("[data-prepmap]",v).forEach(b=>b.onclick=()=>{const st=prepState();st.maps=[b.dataset.prepmap];st.step=1;st.done={};st.cur=null;prepSave(st);go("prepare")});   // Prepare with this map
  $$("[data-tier]",v).forEach(a=>a.onclick=e=>{e.preventDefault();const t=$("#"+a.dataset.tier,v);if(t)t.scrollIntoView({behavior:"smooth",block:"start"})});   // not a #view link
  $$("tr[data-mid]",v).forEach(r=>{r.onclick=()=>{const i=p.matches.findIndex(x=>x.id===r.dataset.mid);S.match=i<0?0:i;S.mpin=i>=0;go("matches")};r.onkeydown=e=>{if(e.key==="Enter")r.click()}});
}
