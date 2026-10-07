const D=__DATA__;
// the local app's addresses (/player/…, /match/…) are not at its root: its files (index.json, players/…) are read from there
if(D.local){const f0=window.fetch.bind(window);window.fetch=(u,o)=>f0(typeof u==="string"&&!/^(\/|[a-z]+:)/i.test(u)?"/"+u:u,o)}
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const MAPN=m=>{if(m==="aim_map")return"Aim map";const n=m.replace(/^(de|cs|ar)_/,"");return n.charAt(0).toUpperCase()+n.slice(1)};
const fmtDate=t=>t?new Date(t).toLocaleString("en-US",{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}):"—";
const f1=v=>v==null?"—":String(v);
const TYPE={smoke:"Smoke",flash:"Flash",molotov:"Molotov",he:"HE"};
const RES={win:"Win",loss:"Loss",draw:"Draw"};
const roleOf=(m,s)=>m.startsWith("cs_")?(s==="T"?"defense":"attack"):(s==="T"?"attack":"defense");
const NS="http://www.w3.org/2000/svg";
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e}
function tip(e,s){const t=document.createElementNS(NS,"title");t.textContent=s;e.appendChild(t);return e}
function store(k,v){try{if(v===undefined)return JSON.parse(localStorage.getItem("cs2c:"+k));localStorage.setItem("cs2c:"+k,JSON.stringify(v))}catch(e){return null}}
// the theme: dark unless you chose light or your system's in Settings
function applyTheme(t){t=t||store("theme")||"dark";if(t==="system")delete document.documentElement.dataset.theme;else document.documentElement.dataset.theme=t}
applyTheme();
// ≈ HLTV Rating 2.0 (flashed.gg's regression, the same as context.rating)
const rating2=(k,d,a,adr,kast,r)=>{r=Math.max(r||0,1);const kpr=k/r,dpr=d/r,apr=a/r,imp=2.13*kpr+.42*apr-.41;return .0073*kast+.3591*kpr-.5329*dpr+.2372*imp+.0032*adr+.1587};
function press(scope,sel,b){$$(sel,scope).forEach(x=>x.setAttribute("aria-pressed",x===b))}
function copyBtn(root){$$(".cmd button",root).forEach(b=>b.onclick=e=>{e.stopPropagation();const code=$("code",b.parentNode);
  const sel=()=>{const r=document.createRange();r.selectNodeContents(code);const s=getSelection();s.removeAllRanges();s.addRange(r)};
  try{navigator.clipboard.writeText(code.textContent).then(()=>{b.textContent="Copied"},sel)}catch(err){sel()}})}
function tabs(host,key,items,cur){ // accessible tab bar; items [[key,label]]
  return `<div class="tabs" role="tablist" aria-label="${esc(key)}">${items.map(([k,t])=>`<button type="button" role="tab" data-tab="${key}:${k}" aria-selected="${k===cur}">${t}</button>`).join("")}</div>`}

// ---------- state ----------
const S={player:null,view:"ingame",map:null,side:"T",level:null,match:0,cmap:null};
const P=()=>D.players[S.player];
// hostage maps (cs_*) play differently (no bomb sites): after the bomb maps, under their own label
const HOST=m=>/^cs_/.test(m||"");
const bombFirst=(a,f=x=>x)=>[...a.filter(x=>!HOST(f(x))),...a.filter(x=>HOST(f(x)))];
const chipSep=(a,i,f=x=>x)=>HOST(f(a[i]))&&(i===0||!HOST(f(a[i-1])))?`<span class="chip-sep">Hostage maps</span>`:"";
function mapsOf(p){let c=(p.cross.maps||[]).map(m=>({map:m.map,n:m.matches}));
  const lb=(p.advice.leetify||{}).by_map||{};if(!c.length)c=Object.entries(lb).map(([map,b])=>({map,n:b.n}));
  if(!c.length)c=((p.advice.csstats||{}).maps||[]).map(m=>({map:m.map,n:m.wins}));return bombFirst(c.sort((a,b)=>b.n-a.n),x=>x.map)}
function extrasBlock(p,compact){const st=p.advice.steam,cs=p.advice.csstats;if(!st&&!cs)return "";
  const fmtR=v=>v==null?"—":v.toLocaleString("en-US");
  return `<div class="card"><div style="display:flex;gap:12px;align-items:center">${st&&st.avatar?`<img src="${esc(st.avatar)}" alt="" width="48" height="48" style="border-radius:3px">`:""}
    <div><h3>${compact?"Public rankings":"Public profile and rankings"}</h3><span class="note">${st?[st.member_since?`Steam account since ${esc(st.member_since)}`:"",st.location?esc(st.location):"",st.vac_banned?"<b class='bad'>VAC ban on record</b>":""].filter(Boolean).join(" · "):""}</span></div></div>
    ${cs&&cs.premier&&cs.premier.length?`<div class="tbl"><table><thead><tr><th>Premier</th><th class="n">Wins</th><th class="n">Current</th><th class="n">Best</th></tr></thead><tbody>${cs.premier.map(x=>`<tr><td>${esc(x.season)} · ${x.year}</td><td class="n">${esc(x.wins??"—")}</td><td class="n">${fmtR(x.current)}</td><td class="n">${fmtR(x.best)}</td></tr>`).join("")}</tbody></table></div>`:""}
    ${cs&&cs.competitive?`<p class="note">Competitive: ${esc(cs.competitive.current||"—")} (best ${esc(cs.competitive.best||"—")}) · ${cs.competitive.wins} wins · last match ${esc(cs.competitive.last_match)}</p>`:""}
    ${cs&&cs.maps&&cs.maps.length?`<div class="tbl"><table><thead><tr><th>Map</th><th>Competitive rank</th><th class="n">Wins</th></tr></thead><tbody>${cs.maps.map(m=>`<tr><td>${MAPN(m.map)}</td><td>${esc(m.rank_name)||'<span class="note">Unranked</span>'}</td><td class="n">${m.wins}</td></tr>`).join("")}</tbody></table></div>`:""}
    ${cs&&cs.crosshair?`<span class="lbl4" style="color:var(--muted)">Their crosshair</span><div class="cmd"><code>${esc(cs.crosshair)}</code><button type="button">Copy</button></div>`:""}
    <p class="note">Sources: ${st?`<a href="${esc(st.url)}" target="_blank" rel="noopener">Steam profile</a>`:""}${cs?` · <a href="${esc(cs.url)}" target="_blank" rel="noopener">csstats.gg</a>`:""}</p></div>`}
function leetMap(p,map){const b=((p.advice.leetify||{}).by_map||{})[map];if(!b)return "";
  return `<div class="card"><h3>${MAPN(map)} according to Leetify</h3><div class="stats"><div class="stat"><b class="num">${b.w}/${b.n}</b><span>matches won</span></div>
  <div class="stat"><b class="num">${(b.k/Math.max(b.d,1)).toFixed(2)}</b><span>K/D</span></div><div class="stat"><b class="num">${Math.round(b.dmg/Math.max(b.rounds,1))}</b><span>ADR</span></div></div>
  <p class="note">No recent demo of this player: no positions or grenades yet. FACEIT demos need a FACEIT API key. Matchmaking demos are fetched automatically while Valve keeps them (about 1 month).</p></div>`}
function leetBlock(p){const L=p.advice.leetify;if(!L)return "";const r=L.ratings||{},st=L.stats||{};
  const n=(v,d=0)=>v==null?"—":Number(v).toFixed(d);
  return `<h3>Leetify profile</h3><div class="stats">
   <div class="stat"><b class="num">${n(r.aim)}</b><span>aim rating</span></div><div class="stat"><b class="num">${n(r.positioning)}</b><span>positioning rating</span></div>
   <div class="stat"><b class="num">${n(r.utility)}</b><span>utility rating</span></div><div class="stat"><b class="num">${n(st.preaim,1)}°</b><span>crosshair offset</span></div>
   <div class="stat"><b class="num">${n(st.reaction_time_ms)} ms</b><span>reaction time</span></div><div class="stat"><b class="num">${n(st.counter_strafing_good_shots_ratio)}%</b><span>counter-strafed shots</span></div>
   <div class="stat"><b class="num">${n(st.traded_deaths_success_percentage)}%</b><span>tradable deaths traded</span></div><div class="stat"><b class="num">${n(L.total_matches)}</b><span>matches tracked</span></div></div>
  <div class="tbl"><table><thead><tr><th>Date</th><th>Source</th><th>Map</th><th>Score</th><th class="n">K-D-A</th><th class="n">ADR</th><th class="n">Rating</th></tr></thead><tbody>
  ${(L.recent||[]).map(m=>{const me=m.me||{};const won=me.rounds_won>me.rounds_lost,draw=me.rounds_won===me.rounds_lost;return `<tr><td>${fmtDate(m.time)}</td><td>${m.source==="faceit"?"FACEIT":"Matchmaking"}</td><td>${MAPN(m.map)}</td>
   <td><span class="res ${draw?"draw":won?"win":"loss"}">${me.rounds_won??"?"}-${me.rounds_lost??"?"}</span></td><td class="n">${me.total_kills??"—"}-${me.total_deaths??"—"}-${me.total_assists??"—"}</td>
   <td class="n">${me.dpr==null?"—":Math.round(me.dpr)}</td><td class="n">${me.leetify_rating==null?"—":(me.leetify_rating*100).toFixed(1)}</td></tr>`}).join("")}</tbody></table></div>`}
function crossMap(p,map){return (p.cross.maps||[]).find(m=>m.map===map)}

// ---------- radar (cross data) ----------
function crossRadar(box,m,side,st){
  const svg=$("svg",box),img=$("image",svg),ov=$("g",svg),cap=$(".caption",box);
  const Sd=m.sides[side];img.setAttribute("href",D.radars[`${m.map}:${st.level}`]||"");
  svg.setAttribute("viewBox",(D.viewboxes[m.map]||[0,0,1024,1024]).join(" "));ov.replaceChildren();
  if(!Sd){cap.innerHTML="<span>No data for this side.</span>";return}
  const zm=Object.fromEntries(m.zones_meta.map(z=>[z.key,z])),L=st.level,layers=st.layers;
  const legend=[];
  if(layers.includes("zones")){Sd.zones.forEach(z=>{const meta=zm[z.key];if(!meta||meta.level!==L)return;
    const col=z.verdict==="exploit"?"var(--good)":z.verdict==="avoid"?"var(--bad)":"#8a96a3",r=6+Math.sqrt(z.presence)*4.2;
    tip(el("circle",{cx:meta.px[0],cy:meta.px[1],r,style:`fill:${col};fill-opacity:.72;stroke:#fff;stroke-width:1.5`},ov),`${z.name}: ${Math.round(z.presence)}% of your time, you ${z.k}-${z.d}, others ${z.others_win??"—"}%`);
    el("text",{x:meta.px[0],y:meta.px[1]-r-3,"text-anchor":"middle",class:"zlabel"},ov).textContent=z.name;
    el("text",{x:meta.px[0],y:meta.px[1]+4,"text-anchor":"middle",class:"zsmall"},ov).textContent=`${z.k}-${z.d}`;});
    legend.push('<span><i style="background:var(--good)"></i>play it more</span><span><i style="background:var(--bad)"></i>avoid</span><span><i style="background:#8a96a3"></i>neutral</span><span>size = your time · number = your kills-deaths</span>')}
  if(layers.includes("duels")){Sd.duels.filter(d=>d.level===L).forEach(d=>{
      el("line",{x1:d.opp_px[0],y1:d.opp_px[1],x2:d.px[0],y2:d.px[1],style:`stroke:${d.won?"var(--good)":"var(--bad)"};stroke-width:1.6;stroke-opacity:.7;${d.won?"":"stroke-dasharray:4 3"}`},ov);
      if(d.won)el("circle",{cx:d.px[0],cy:d.px[1],r:5,style:"fill:var(--good);stroke:#fff"},ov);
      else el("path",{d:`M${d.px[0]-5} ${d.px[1]-5}L${d.px[0]+5} ${d.px[1]+5}M${d.px[0]+5} ${d.px[1]-5}L${d.px[0]-5} ${d.px[1]+5}`,style:"stroke:var(--bad);stroke-width:3;stroke-linecap:round"},ov);});
    legend.push('<span><i style="background:var(--good)"></i>duel won</span><span><i style="background:var(--bad)"></i>duel lost</span>')}
  if(layers.includes("best")){Sd.best_spots.filter(b=>b.level===L).forEach(b=>{const [x,y]=b.px;
      tip(el("path",{d:`M${x} ${y-10}L${x+3} ${y-3}L${x+10} ${y-3}L${x+4} ${y+2}L${x+6} ${y+9}L${x} ${y+5}L${x-6} ${y+9}L${x-4} ${y+2}L${x-10} ${y-3}L${x-3} ${y-3}Z`,style:"fill:#ffd24a;stroke:#000;stroke-width:1"},ov),
        `${b.zone}: ${b.k} kills for ${b.d} deaths by other players, ${b.hold_pct}% holding, around ${clock(b.t_med)}`);});
    if(Sd.best_spots.length)legend.push("<span>★ spot where other players win ≥ 65% of their duels</span>")}
  if(layers.includes("nades")){const idx=st.nades||Sd.lineups.map((_,i)=>i);
    idx.forEach(i=>{const l=Sd.lineups[i];if(!l||(l.level!==L&&l.land_level!==L))return;const col=`var(--${l.type})`,sel=st.sel===i,dim=st.sel!=null&&!sel;
      el("line",{x1:l.from_px[0],y1:l.from_px[1],x2:l.to_px[0],y2:l.to_px[1],style:`stroke:${col};stroke-width:${sel?3.5:2.2};stroke-opacity:${dim?.3:1};stroke-dasharray:6 4`},ov);
      el("circle",{cx:l.from_px[0],cy:l.from_px[1],r:sel?6:4,style:`fill:#fff;stroke:${col};stroke-width:2`},ov);
      tip(el("circle",{cx:l.to_px[0],cy:l.to_px[1],r:sel?11:8,style:`fill:${col};fill-opacity:${dim?.3:.85};stroke:#000`},ov),`${TYPE[l.type]} ${l.from_zone} → ${l.to_zone||"?"}`);});
    legend.push('<span><i style="background:var(--smoke)"></i>smoke</span><span><i style="background:var(--flash)"></i>flash</span><span><i style="background:var(--molotov)"></i>molotov</span><span><i style="background:var(--he)"></i>HE</span><span>white dot = thrower</span>')}
  cap.innerHTML=legend.join("");
}
function radarShell(extraBtns=""){return `<div class="radar-box">${extraBtns}<svg class="radar" viewBox="0 0 1024 1024" role="img" aria-label="Radar"><image x="0" y="0" width="1024" height="1024"></image><g></g></svg><div class="caption"></div></div>`}
// a grenade thrown and landing in the same big zone ("Outside → Outside"): which part, by the nearest other callout
// trait names of profiles analyzed before everything was in English
const TRAIT_EN={Solitaire:"Loner",Agressif:"Aggressive",Utilitaires:"Utility user",Ouvreur:"Opener","Duels longs":"Long duels"},tEN=l=>TRAIT_EN[l]||l;
function nTo(x,map){const from=x.from??x.from_zone,to=x.to??x.to_zone,px=x.to_px,lv=x.land_level||x.level;if(!to||to!==from||!px)return to;
  let pl=null;try{pl=P()}catch(e){}const M=((((pl||{}).advice||{}).plan||{}).tside||{}).maps,zs=M&&M[map]&&M[map].geo&&M[map].geo.zones;if(!zs)return to;
  let best=null,bd=1e9;for(const [n,z] of Object.entries(zs)){if(n===to||!z.px||(lv&&z.level&&z.level!==lv))continue;const d=Math.hypot(z.px[0]-px[0],z.px[1]-px[1]);if(d<bd){bd=d;best=n}}
  return best&&bd<140?`${to}, near ${best}`:to}
// the pro catalog (Daily CS Nades) lineups found in the base's real throws: exact aim and technique (04/10)
const NCAT={};
// the page's own errors, the last 20: a bug report can include them (05/10, the alpha)
const ERRS=[];
window.addEventListener("error",e=>{ERRS.push(`${e.message||"error"} @ ${(e.filename||"").split("/").pop()}:${e.lineno||0}`);if(ERRS.length>20)ERRS.shift()});
window.addEventListener("unhandledrejection",e=>{ERRS.push("promise: "+String((e.reason&&e.reason.message)||e.reason||"").slice(0,300));if(ERRS.length>20)ERRS.shift()});
async function nadeCat(mp){if(mp in NCAT)return NCAT[mp];try{const r=await fetch(`nadecat/${mp}.json`);NCAT[mp]=r.ok?await r.json():null}catch(e){NCAT[mp]=null}return NCAT[mp]}
// the lineups of the clips you sent, found in the base's demos (clips.py, /api/clips, 07/10): the local app only
let CLIPS=null;const clipsReady=D.local?fetch("/api/clips").then(r=>r.ok?r.json():{}).then(j=>CLIPS=j||{}).catch(()=>CLIPS={}):Promise.resolve(CLIPS={});
const clipsOf=(mp,side)=>((CLIPS||{})[mp]||[]).filter(c=>!side||c.side===side);
function clipHead(c){return `<p class="note"><b>${esc(c.title)}</b> · <a href="${esc(c.url)}" target="_blank" rel="noopener" style="color:var(--ct)">@${esc(c.handle)}'s clip</a> (${esc(c.date)}) · ${esc(c.seen)}${c.check?` · <em>${esc(c.check)}</em>`:""}</p>`}
function clipCards(c){return c.throws.map((x,i)=>`<article class="lu cat" data-type="${x.type}" data-clip="${esc(c.id)}" data-ci="${i}" tabindex="0"><div class="top"><span class="ty">${TYPE[x.type]}${c.throws.length>1?` · ${i+1} of ${c.throws.length}`:""}</span>${x.t!=null?`<span class="pill">${clock(x.t)}</span>`:""}</div>
  <div class="route">${esc(x.from_zone||"?")} → ${esc(x.to)}</div><div class="meta">${esc(x.how)} · ${esc(x.click)}${x.uses?` · ${x.uses} throw${x.uses>1?"s":""} in the base${x.pro_uses?`, ${x.pro_uses} by pros`:""}`:" · not in the base yet"}${(x.pros||[]).length?` · ${x.pros.slice(0,3).map(esc).join(", ")}`:""}</div>
  <div class="cmd"><code>${esc(x.setpos)}</code><button type="button">Copy</button></div></article>`).join("")}
function drawCat(box,l,level){const ov=$("g",$("svg",box));if((l.level||level)!==level&&(l.land_level||level)!==level)return;
  const col=l.type==="smoke"?"var(--smoke)":l.type==="flash"?"var(--flash)":l.type==="molotov"?"var(--molotov)":"var(--he)";
  el("line",{x1:l.px[0],y1:l.px[1],x2:l.land_px[0],y2:l.land_px[1],style:`stroke:${col};stroke-width:2.5;stroke-dasharray:6 4`},ov);
  el("circle",{cx:l.px[0],cy:l.px[1],r:6,style:`fill:${col};stroke:#fff;stroke-width:1.5`},ov);
  el("circle",{cx:l.land_px[0],cy:l.land_px[1],r:l.type==="smoke"?14:9,style:`fill:${col};fill-opacity:.45;stroke:${col}`},ov)}
function lineupCard(l,i){
  const res=l.type==="flash"?`${f1(l.enemies_blind_avg)} enemy(ies) flashed on avg.${l.mates_blind_avg?`, ${f1(l.mates_blind_avg)} teammate(s)`:""}${l.kills_after?`, ${l.kills_after} kill(s) after`:""}`:
    l.type==="smoke"?`seen ${l.uses} times, ${l.players} player(s)`:`${l.damage_avg} damage on avg.${l.damage_best?`, ${l.damage_best} at best`:""}`;
  return `<article class="lu" data-type="${l.type}" data-i="${i}" tabindex="0"><div class="top"><span class="ty">${TYPE[l.type]} · ${l.uses} throw${l.uses>1?"s":""}</span><span class="pill">${clock(l.t)}</span></div>
    <div class="route">${esc(l.from_zone)} → ${esc(nTo(l,S.cmap)||"?")}</div><div class="meta">${esc(l.how)} · ${res}</div>
    <div class="cmd"><code>${esc(l.setpos)}</code><button type="button">Copy</button></div></article>`}
function levelBtns(m,cur){const lv=(m.levels||[]);return lv.length>1?`<div class="btns" role="group" aria-label="Level">${lv.map(l=>`<button type="button" data-level="${l.key}" aria-pressed="${l.key===cur}">${esc(l.name)}</button>`).join("")}</div>`:""}

// ---------- view: full analysis ----------
function findings(list){return (list||[]).map((f,i)=>`<article class="finding ${f.level||(i<2?"high":"mid")}"><div class="rank">${i+1}</div><div class="body">
  ${f.tags&&f.tags.length?`<div>${f.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div>`:""}
  <h3>${esc(f.title)}</h3>${f.evidence&&f.evidence.length?`<ul>${f.evidence.map(e=>`<li>${e}</li>`).join("")}</ul>`:""}
  ${f.standing?`<div class="standing"><span>${esc(f.standing)}</span>${benchExtra(f.bench)}${f.target?`<span class="tg">${esc(f.target)}</span>`:""}</div>`:""}
  ${f.fix&&f.fix.length?`<div class="fix"><h4>Fix</h4><ol>${f.fix.map(e=>`<li>${e}</li>`).join("")}</ol></div>`:""}
  ${f.drills&&f.drills.length?`<div class="fix"><h4>Drills</h4><ul class="drills">${f.drills.map(e=>`<li>${esc(e)}</li>`).join("")}</ul></div>`:""}
  ${f.sources&&f.sources.length?`<div class="srcs"><span class="note">Sources:</span>${f.sources.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>`).join("")}</div>`:""}</div></article>`).join("")}
const fmtU=(v,u)=>v==null?"—":((Math.abs(v)<10&&u!=="%")?v.toFixed(1):Math.round(v).toString())+(u==="%"?"%":u);
function benchExtra(bl){if(!bl||!bl.length)return "";const b=bl[0];const parts=[];
  if(b.same!=null)parts.push(`players of your rank ${fmtU(b.same,b.unit)}`);if(b.higher!=null)parts.push(`higher-ranked players ${fmtU(b.higher,b.unit)}`);
  return (parts.length?`<span>${parts.join(" · ")}</span>`:"")+bl.slice(1).map(x=>`<span>${esc(x.label)}: you ${fmtU(x.you,x.unit)} · median ${fmtU(x.median,x.unit)}</span>`).join("")}
const SKILL=["","Silver I","Silver II","Silver III","Silver IV","Silver Elite","Silver Elite Master","Gold Nova I","Gold Nova II","Gold Nova III","Gold Nova Master","Master Guardian I","Master Guardian II","Master Guardian Elite","Distinguished Master Guardian","Legendary Eagle","Legendary Eagle Master","Supreme","Global Elite"];
function benchSection(p){const B=p.advice.bench;if(!B||!B.metrics)return "";
  const rows=Object.entries(B.metrics).filter(([k,m])=>m.you!=null&&m.percentile!=null&&!(READ_BENCH.has(k)&&readsOf().all)).sort((a,b)=>a[1].percentile-b[1].percentile);
  const col=q=>q<30?"var(--bad)":q<60?"var(--warn)":"var(--good)";
  return `<h3>You against the reference base</h3>
  <p class="note">Base: ${B.n_players} players, ${B.n_rows} player-match records from ${B.n_matches} demos (your matches, searched players and randomly collected players).${B.my_rank?` Your median competitive rank: ${SKILL[B.my_rank]||B.my_rank} (${B.n_same} players of your level, ${B.n_higher} higher-ranked in the base).`:""} The bar shows your percentile: further right, you do better than most players. The line marks the median.</p>
  <div class="card bench">${rows.map(([k,m])=>`<div class="row"><span class="lb">${esc(m.label[0].toUpperCase()+m.label.slice(1))}</span>
    <div class="pbar" title="Better than ${Math.round(m.percentile)}% of players"><i style="width:${Math.max(2,m.percentile)}%;background:${col(m.percentile)}"></i><b></b></div>
    <span class="v">you ${fmtU(m.you,m.unit)} · med. ${fmtU(m.median,m.unit)}${m.higher_rank_median!=null?` · higher ranks ${fmtU(m.higher_rank_median,m.unit)}`:""}</span></div>`).join("")}</div>`}
const cls=(v,good,bad,higher=true)=>v==null?"":(higher?(v>=good?"good":v<=bad?"bad":""):(v<=good?"good":v>=bad?"bad":""));
// green / red against the base, match by match: in its best quarter / its worst quarter (fixed thresholds made
// nearly every match red on grenades, where the whole base is). Fixed thresholds only without base data.
function qcls(v,k,fb){if(v==null)return "";const m=(((P().advice||{}).bench||{}).metrics||{})[k];
  if(!m||m.p25==null||m.p75==null)return fb;return m.higher_better?(v>=m.p75?"good":v<=m.p25?"bad":""):(v<=m.p25?"good":v>=m.p75?"bad":"")}
function trendRows(ms,selIdx){return ms.map((m,i)=>{const s=m.sum,nr=typeof m.rounds==="number"?m.rounds:(m.per_round||[]).length,
  n24=s.nades_unused!=null&&nr?s.nades_unused*24/nr:null;return `<tr class="click" data-i="${i}" tabindex="0" aria-selected="${i===selIdx}">
  <td>${fmtDate(m.time)}</td><td>${MAPN(m.map)}</td><td>${esc(m.mode)}</td><td><span class="res ${m.result}">${m.score.me}-${m.score.them}</span></td>
  <td class="n">${nr&&s.kast!=null&&s.adr!=null?rtBadge(rating2(s.kills,s.deaths,s.assists,s.adr,s.kast,nr)):"—"}</td>
  <td class="n">${s.kills}-${s.deaths}-${s.assists}</td><td class="n ${qcls(s.adr,"adr",cls(s.adr,85,65))}">${f1(s.adr)}</td><td class="n ${qcls(s.hs,"hs_pct",cls(s.hs,55,35))}">${f1(s.hs)}</td>
  <td class="n ${cls(s.kast,72,62)}">${f1(s.kast)}</td><td class="n ${qcls(s.traded_pct,"traded_pct",cls(s.traded_pct,25,10))}">${s.traded_pct==null?"—":f1(s.traded_pct)+"%"}</td>
  <td class="n ${qcls(n24,"nades_unused_24",cls(s.nades_unused,4,10,false))}">${s.nades_unused}</td><td class="n ${qcls(s.first_bullet,"b1_hit",cls(s.first_bullet,30,20))}">${s.first_bullet==null?"—":f1(s.first_bullet)+"%"}</td>
  <td class="n ${qcls(s.pistol_moving,"pistol_moving",cls(s.pistol_moving,25,45,false))}">${s.pistol_moving==null?"—":f1(s.pistol_moving)+"%"}</td>
  <td class="n ${qcls(s.xhair,"xhair",cls(s.xhair,4,8,false))}">${s.xhair==null?"—":f1(s.xhair)+"°"}</td><td class="n">${s.open_won}-${s.open_lost}</td></tr>`}).join("")}
const TREND_HEAD=`<thead><tr><th>Date</th><th>Map</th><th>Mode</th><th>Score</th><th class="n" title="≈ HLTV 2.0: under 0.85 red, over 1.20 bright green">Rating</th><th class="n">K-D-A</th><th class="n">ADR</th><th class="n">HS %</th><th class="n">KAST</th><th class="n">Deaths<br>traded</th><th class="n">Grenades<br>wasted</th><th class="n">1st bullet<br>hits</th><th class="n">Pistol<br>moving</th><th class="n">Crosshair<br>offset</th><th class="n">Openings<br>W-L</th></tr></thead>`;
const WCOL={"rifles":"var(--t)","AWP":"var(--ct)","SMG":"var(--good)","shotguns":"var(--molotov)","pistols":"var(--muted)","fusils à pompe":"var(--molotov)","pistolets":"var(--muted)"};
function archCard(p){const A=p.advice.archetype;if(!A)return "";
  const mx=Math.max(...A.scores.map(x=>x.score),1);
  return `<article class="card arch"><div class="arch-h"><span class="ic" aria-hidden="true">${A.icon}</span><span class="nm">${esc(A.name)}</span>
    ${A.second?`<span class="note">secondary tendency: <b>${esc(A.second.name)}</b></span>`:""}
    <span class="eyebrow">Archetype over ${A.rounds} rounds · compared with ${A.n_ref.toLocaleString("en-US")} players of the base</span></div>
    ${A.traits.length?`<div class="traits">${A.traits.map(t=>`<span title="${esc(t.text)}">${esc(tEN(t.label))}</span>`).join("")}</div>`:""}
    <div class="arch-grid"><div style="display:grid;gap:12px;min-width:0">
      <ul class="desc">${A.description.map(d=>`<li>${esc(d)}</li>`).join("")}</ul>
      ${A.traits.length?`<ul class="desc note">${A.traits.map(t=>`<li><b>${esc(tEN(t.label))}</b>: ${esc(t.text)}</li>`).join("")}</ul>`:""}
      <div><span class="lbl4" style="color:var(--muted)">Weapons (share of kills)</span>
        <div class="wbar">${Object.entries(A.weapons.shares).filter(([k,v])=>v>0).map(([k,v])=>`<i style="width:${v}%;background:${WCOL[k]||"var(--muted)"}" title="${esc(k)} ${v}%"></i>`).join("")}</div>
        <div class="wleg">${Object.entries(A.weapons.shares).filter(([k,v])=>v>0).map(([k,v])=>`<span><b style="background:${WCOL[k]||"var(--muted)"}"></b>${esc(k)} ${v}%</span>`).join("")}</div></div>
    </div><div style="display:grid;gap:12px;align-content:start;min-width:0">
      <span class="lbl4" style="color:var(--muted)">Score per role</span>
      <div class="roles">${A.scores.map(x=>`<div class="row ${x.role===A.role?"main":""}"><span>${esc(x.name)}</span><div class="meter"><i style="width:${Math.round(x.score/mx*100)}%"></i></div><span class="num">${x.score}</span></div>`).join("")}</div>
    </div></div>
    ${A.peers.length?`<div class="tbl"><table><thead><tr><th>Role indicator</th><th class="n">You</th><th class="n">${esc(A.name)}s in the base</th><th class="n">The best of them</th></tr></thead><tbody>
      ${A.peers.map(x=>`<tr><td class="wrap">${esc(x.label)}</td><td class="n">${esc(x.you)}</td><td class="n">${esc(x.peers)}</td><td class="n">${esc(x.best)}</td></tr>`).join("")}</tbody></table></div>
      <p class="note">${A.n_peers} players of the base have this archetype. "The best": the quarter with the most kills per round.</p>`:""}
    <div class="fix"><h4>To play this role well</h4><ol>${A.tips.map(t=>`<li>${esc(t)}</li>`).join("")}</ol></div>
    <div class="srcs"><span class="note">Sources:</span>${A.sources.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>`).join("")}</div>
  </article>`}
function proCard(x,metric,label){return `<div class="pro"><div class="top"><b>${esc(x.name)}</b><span class="sim">${x[metric]}%</span></div>
  <span class="note">${esc(x.team||"")}${x.role_name?` · ${esc(x.role_name)}`:""}</span>
  ${x.traits&&x.traits.length?`<span>In common: ${x.traits.map(esc).join(", ")}.</span>`:""}
  ${x.zones?`<span class="note">Their zones: ${x.zones.map(z=>`${esc(z.zone)} ${z.share}%`).join(" · ")}</span>`:""}
  <span>${x.steamid?`<a href="#pros" data-openpro="${esc(x.steamid)}">Pro sheet</a> · `:""}${x.hltv?`<a href="${esc(x.hltv)}" target="_blank" rel="noopener">HLTV</a>`:""}</span></div>`}
document.addEventListener("click",e=>{const a=e.target.closest("[data-openpro]");if(a){e.preventDefault();openPro(a.dataset.openpro)}});
function prosBlock(p){const X=p.advice.pros;if(!X||!X.similar||!X.similar.length)return "";
  return `<article class="card"><h3>Pros who play like you</h3>
   <p class="note">${X.n_pros} pro players analyzed on ${X.n_maps} maps of recent matches (HLTV demos). Similarity = average closeness over 15 style indicators. Watch their demos or POVs to see your role played at the highest level.</p>
   <div class="pros">${X.similar.map(x=>proCard(x,"similarity")).join("")}</div>
   ${X.same_role.length?`<h3 style="margin-top:8px">Pros with the same archetype (${esc(X.role_name)})</h3><div class="pros">${X.same_role.map(x=>proCard(x,"similarity")).join("")}</div>`:""}</article>`}
function deepCard(p){const X=p.deep;if(!X)return "";const r=X.reaction,a=X.preaim,su=X.surprised;
  const fmtS=v=>v==null?"—":Math.round(v*1000)+" ms";
  return `<article class="card"><h3>Deep analysis</h3>
   <p class="note">From the visibility recorded in the demos (who sees whom, at every moment), over ${X.engagements} opened duels and ${X.deaths} deaths. Compared with the ${X.n_ref_players} other players of your matches.</p>
   <div class="gauge">
    <div><b>${fmtS(r.you)}</b><span>reaction time: from the enemy appearing to your first damage</span><span>others' median ${fmtS(r.median_others)} · faster than ${r.better_than_pct??"—"}% · ${r.share_under_350ms}% of your duels under 350 ms</span></div>
    <div><b>${a.you}°</b><span>crosshair offset when the enemy appears</span><span>others' median ${a.median_others}° · better than ${a.better_than_pct??"—"}%</span></div>
    <div><b>${su.you??"—"}%</b><span>of your deaths where the killer saw you first</span><span>others' median ${su.median_others}% · better than ${su.better_than_pct??"—"}% of players</span></div>
   </div>
   ${X.zones_vs_pros&&X.zones_vs_pros.length?`<h3 style="margin-top:6px">Your zones against pros</h3>
    <div class="tbl"><table><thead><tr><th>Map</th><th>Side</th><th>Zone</th><th class="n">Your duels</th><th class="n">You</th><th class="n">Pros</th><th class="n">Holding (you / pros)</th></tr></thead><tbody>
    ${(()=>{const row=z=>`<tr><td>${MAPN(z.map)}</td><td>${z.side}</td><td>${esc(z.zone)}</td><td class="n">${z.my_duels}</td><td class="n ${z.my_duels>=8?(z.my_win-z.pro_win>=8?"good":z.my_win-z.pro_win<=-10?"bad":""):""}">${z.my_win}%</td><td class="n">${z.pro_win}% <span class="note">(${z.pro_duels})</span></td><td class="n">${z.my_hold}% / ${z.pro_hold}%</td></tr>`,
      main=X.zones_vs_pros.filter(z=>z.my_duels>=6),rest=X.zones_vs_pros.filter(z=>z.my_duels<6);
      return main.map(row).join("")+(rest.length?`</tbody></table></div><details><summary>${rest.length} zones with under 6 duels of yours (too few to judge)</summary><div class="tbl"><table><tbody>${rest.map(row).join("")}`:"")})()}
    </tbody></table></div>${X.zones_vs_pros.some(z=>z.my_duels<6)?"</details>":""}<p class="note">Duels won in the zone, per side. Colored from 8 duels of yours. Pros come from the analyzed HLTV demos.</p>`:""}
   <p class="note">The 2D replay of every round is in the Matches tab. Pro grenades to add to your game are in the Maps tab.</p></article>`}
function midCard(p){const M0=(p.advice.plan||{}).mid;if(!M0)return "";const own=x=>!(READ_MID.has(x.id)&&readsOf().all),M={weak:M0.weak.filter(own),strong:M0.strong.filter(own)};
  if(!M.weak.length&&!M.strong.length)return "";
  return `<article class="card"><h3>Mid-round at a glance</h3><ul>${M.weak.slice(0,3).map(w=>`<li>${esc(w.text)}${w.fix?` <b>${esc(w.fix)}</b>`:""}</li>`).join("")}${M.strong.slice(0,2).map(s=>`<li class="good">${esc(s.text)}</li>`).join("")}</ul>
   <p><a href="#midround" style="color:var(--ct)">Rotation routes, positions by weapon and reflexes: Mid-round tab</a></p></article>`}
// a teammate's whole history (their matches without you too): their Steam history code, given by them
async function fillFollow(p){const box=$("#follow-card");if(!box)return;let st;
  try{st=await (await fetch(`/api/steam/status?sid=${p.steamid}`)).json()}catch(e){box.querySelector(".note").textContent="The local server doesn't answer.";return}
  const inp="font:14px var(--f-mono);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:5px 8px";
  box.innerHTML=`<h3>Follow ${esc(p.name)}'s matches ${st.has_auth?'<span class="pill" style="color:var(--good)">on</span>':""}</h3>
   <p>Only the matches already on this PC are analyzed for ${esc(p.name)}: the ones you played together. To find <b>every match ${esc(p.name)} plays, even without you</b>, they can give you two codes from <a href="${esc((st.links||{}).auth||"https://help.steampowered.com/en/wizard/HelpWithGameIssue/?appid=730&issueid=128")}" target="_blank" rel="noopener" style="color:var(--ct)">Steam's CS2 help page</a> (signed in to <b>their own</b> account): their authentication code, and the code of one of their matches. For a single match, they can also send you its share code (CSGO-…): paste it in the search bar.</p>
   ${st.has_key?"":`<p class="note">First add your own Steam API key in <a href="#settings" style="color:var(--ct)">Settings</a>: it is used to read everyone's history.</p>`}
   <div class="row"><input id="fo-auth" type="password" autocomplete="off" spellcheck="false" placeholder="${st.has_auth?"already saved":"Their authentication code XXXX-XXXXX-XXXX"}" style="width:270px;${inp}">
     <input id="fo-known" type="text" autocomplete="off" spellcheck="false" placeholder="Code of one of their matches CSGO-…" style="flex:1;min-width:240px;${inp}"></div>
   <div class="row"><button type="button" class="primary" id="fo-save" ${st.has_key?"":"disabled"}>Save and check</button>
     <button type="button" class="primary" id="fo-sync" ${st.has_auth?"":"disabled"}>Find their new matches</button>
     ${st.has_auth?`<button type="button" class="close" id="fo-forget">Stop following</button>`:""}<span class="note" id="fo-msg" role="status"></span></div>
   ${st.has_auth?`<p class="note">Checked automatically when the app starts, then every 30 minutes. Last check: ${st.last_sync?fmtDate(st.last_sync):"never"}${st.pending?` · ${st.pending} match(es) waiting (Steam must be open and CS2 closed)`:""}.</p>`:""}
   <p class="note">Their codes stay in <code>out/settings.json</code> on this PC (not versioned) and only go to Steam's official API. Ask them first: these codes let you read their match history.</p>`;
  const msg=$("#fo-msg",box),sid=p.steamid;
  $("#fo-save",box).onclick=async()=>{const b=$("#fo-save",box);b.disabled=true;msg.textContent="Checking with Steam…";
    try{const j=await api("/api/steam/credentials",{sid,auth_code:$("#fo-auth",box).value.trim(),known_code:$("#fo-known",box).value.trim()});
      msg.textContent=j.saved.length?`Saved: ${j.saved.join(" and ")}.`:"Nothing new to save.";setTimeout(()=>fillFollow(p),900)}
    catch(e){msg.textContent=e.message;b.disabled=false}};
  $("#fo-sync",box).onclick=async()=>{msg.textContent="";try{await api("/api/steam/sync",{sid});poll()}catch(e){msg.textContent=e.message}};
  const fg=$("#fo-forget",box);if(fg)fg.onclick=async()=>{if(fg.dataset.ok!=="1"){fg.dataset.ok="1";fg.textContent="Confirm: remove their codes";return}
    try{await api("/api/steam/forget",{sid});fillFollow(p)}catch(e){msg.textContent=e.message}}}
// parts of the plan that failed at the last analysis: said, instead of silently missing
function missNote(p){const a=p.advice||{},u=[...new Set(((a.plan||{}).unavailable)||[])];
  if(a.plan_error)return `<p class="miss" role="status">The coaching plan could not be updated at the last analysis (${esc(a.plan_error)}): what you see is the previous one. It is rebuilt at the next analysis.</p>`;
  return u.length?`<p class="miss" role="status">Not computed at the last analysis: ${u.map(esc).join(", ")}. These parts come back at the next analysis.</p>`:""}
// ---------- the analyst's reads (04/10): each match, Full analysis and the review's deep dive ----------
const READ_IDS=["repeek","untraded","flash","fake","clutch"],READ_BENCH=new Set(["untraded_pct","flash_used_pct","clutch_multi_pct","clutch_win_pct"]),READ_MID=new Set(["repeek","fake_pulled"]);
const readsOf=()=>((P().advice||{}).plan||{}).reads||{};
const readRef=k=>((((readsOf().all||{}).items)||[]).find(x=>x.id===k)||{}).ref||null;
const pc0=x=>x==null?"—":Math.round(x)+"%";
function rchips(rs,mid){return (rs||[]).length?`<span class="rchips">${rs.map(n=>`<button type="button" class="rchip" data-goround="${n}"${mid?` data-mid="${esc(mid)}"`:""} title="Round ${n}: open it in the 2D replay">R${n}</button>`).join("")}</span>`:""}
// against the base median: worse by 5 points or more, or as good as the base's best quarter
function readTone(k,pct,of){const r=readRef(k),hb=((readsOf().meta||{})[k]||{}).higher_better;if(!r||r.median==null||of<3)return "";
  const worse=hb?r.median-pct:pct-r.median;return worse>=5?"bad":r.good!=null&&(hb?pct>=r.good:pct<=r.good)?"good":""}
const READ_LINE={repeek:x=>`of ${x.of} rounds with a kill: dead within 8 s of it`,untraded:x=>`of ${x.of} deaths: no trade, no damage of yours before`,
  flash:x=>`of ${x.of} enemies you flashed hit by your team while blind`,fake:x=>`of ${x.of} hits on your site: you had left it`,
  clutch:x=>`of ${x.of} clutches 1v2+ (won ${x.won}): 2+ enemies saw you as you were hit`};
function matchReads(m){const R=m.reads;if(!R)return "";const M=readsOf().meta||{};
  const rows=READ_IDS.filter(k=>R[k]&&R[k].of).map(k=>{const x=R[k],t=readTone(k,100*x.value/x.of,x.of),ref=readRef(k);
    return `<li class="${t}"><span class="rd-t">${esc((M[k]||{}).title||k)}</span><span class="rd-v"><b>${x.value}</b> ${READ_LINE[k](x)}${ref&&ref.median!=null?`<span class="note"> · base ${pc0(ref.median)}</span>`:""}</span>${rchips(x.rounds)}</li>`});
  const sp=Object.entries(R.spots||{}).filter(([k,c])=>c>=2).slice(0,2).map(([k,c])=>`<li><span class="rd-t">Death spot</span><span class="rd-v"><b>${c}</b> deaths at ${esc(k)}</span></li>`);
  if(!rows.length&&!sp.length)return "";
  return `<section class="mreads"><h3>Analyst reads</h3><p class="note">What a team's analyst points at in this demo. A round opens it in the 2D replay below; "base" is the median player of the base.</p><ul class="rd-list">${rows.join("")}${sp.join("")}</ul></section>`}
// one read over several matches: you against the base, higher ranks and pros, the fix, where it happened, the sources
function readCard(i,M,bench){const mt=M[i.id]||{},ref=i.ref||{},hb=mt.higher_better,pct=i.pct;
  if(i.id==="spot")return `<article class="rd-card sev-medium"><div class="rd-h"><span class="tag">habit</span><h4>You keep dying at ${esc(i.place)} (${esc(MAPN(i.map))})</h4></div>
    <p class="fix"><b class="num">${i.value}</b> of your ${i.of} deaths on ${esc(MAPN(i.map))}: the enemies can expect you there. Change the angle or the timing.</p></article>`;
  const lab={high:"priority",medium:"watch",positive:"strength"}[i.severity]||"",mx=Math.max(pct,ref.median||0,ref.pro||0,ref.higher_rank||0,5)*1.25,w=x=>Math.min(100,100*x/mx);
  const cw=i.id==="clutch"&&bench&&bench.metrics&&bench.metrics.clutch_win_pct;
  const refs=[ref.median!=null?`base median ${pc0(ref.median)}`:null,ref.higher_rank!=null?`higher ranks ${pc0(ref.higher_rank)}`:null,ref.pro!=null?`pros ${pc0(ref.pro)}`:null].filter(Boolean);
  return `<article class="rd-card${i.severity?" sev-"+i.severity:""}"><div class="rd-h">${lab?`<span class="tag">${lab}</span>`:""}<h4>${esc(mt.title||i.id)}</h4></div>
   <div class="rd-num"><b class="num">${pct}%</b><span class="note">${i.value} of ${i.of}${i.enough?"":" · few cases yet"}</span></div>
   <div class="rd-bar" role="img" aria-label="You ${pct}%${ref.median!=null?", base median "+pc0(ref.median):""}${ref.pro!=null?", pros "+pc0(ref.pro):""}"><i style="width:${w(pct)}%"></i>${ref.median!=null?`<span class="mk" style="left:${w(ref.median)}%" title="base median ${pc0(ref.median)}"></span>`:""}${ref.pro!=null?`<span class="mk pro" style="left:${w(ref.pro)}%" title="pros ${pc0(ref.pro)}"></span>`:""}</div>
   <p class="note">${refs.join(" · ")||"no base reference yet"}${cw&&cw.you!=null?` · 1v2+ won: you ${pc0(cw.you)}, base ${pc0(cw.median)}`:""}</p>
   <p class="what">${esc(mt.what||"")}${hb?" (higher is better)":""}.</p>
   ${i.severity&&i.severity!=="positive"&&mt.fix?`<p class="fix"><b>Fix</b> ${esc(mt.fix)}</p>`:""}
   ${(i.where||[]).length?`<div class="where">${i.where.map(x=>`<span><span class="note">${esc(fmtDate(x.time).split(",").slice(0,2).join(","))} · ${esc(MAPN(x.map))}</span>${rchips(x.rounds.slice(0,6),x.id)}</span>`).join("")}</div>`:""}
   ${(mt.src||[]).length?`<p class="src">Sources: ${mt.src.map(x=>`<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>`).join(" · ")}</p>`:""}</article>`}
function readsSection(p,set,title,note){if(!set||!set.matches||!(set.items||[]).length)return "";const M=readsOf().meta||{};
  return `<h3>${title}</h3><p class="note">${note} On each bar: the black tick is the base median, the gold one the pros.</p><div class="rd-cards">${set.items.map(i=>readCard(i,M,p.advice.bench)).join("")}</div>`}
// a round button (R7): the match's 2D replay at that round (another match: opened first)
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("[data-goround]");if(!b)return;const n=+b.dataset.goround,mid=b.dataset.mid,p=P();if(!p)return;
  if(mid&&(S.view!=="matches"||((p.matches[S.match]||{}).id!==mid))){const i=p.matches.findIndex(x=>x.id===mid);if(i<0)return;S.match=i;S.mpin=true;S.goRound=n;go("matches");return}
  const rb=$(`#v-matches .rp-rounds [data-rn="${n}"]`);if(rb){rb.click();rb.closest(".radar-box").scrollIntoView({behavior:"smooth",block:"center"})}else S.goRound=n});
// ---------- the analyst's brief on top of each tab (04/10): the essentials first, the detail after ----------
// 05/10: what works here and what costs you here; the page's next step is folded into the second card ("to try
// here"): the one priority of the app is the focus of the week. BRIEF_CAP collects the briefs for the Profile.
let BRIEF_CAP=null;
function tabBrief(o){if(BRIEF_CAP){BRIEF_CAP.push(o);return ""}
  return "";   // 07/10: the detail pages open on their content; their brief is the Profile's card that leads to them (said once)
  const li=xs=>(xs||[]).filter(Boolean).slice(0,3).map(x=>`<li>${x}</li>`).join(""),w=li(o.works),fx=li(o.fix);
  return `<section class="brief3 brief2 tabbrief" id="${o.id||""}" aria-label="Brief">
   <article class="card b-good"><span class="eyebrow">What works here</span>${w?`<ul>${w}</ul>`:`<p class="note">${o.worksNone||"Nothing stands out above the base yet."}</p>`}</article>
   <article class="card b-bad"><span class="eyebrow">Costs you here</span>${fx?`<ul>${fx}</ul>`:`<p class="note">${o.fixNone||"Nothing slips below the base."}</p>`}${o.next?`<p class="try"><b>To try here:</b> ${o.next}</p>`:""}</article></section>`}
function briefOf(fn,...a){BRIEF_CAP=[];try{fn(...a)}catch(e){}const o=BRIEF_CAP[0]||null;BRIEF_CAP=null;return o}
function secNav(items){items=items.filter(Boolean);return items.length<2?"":`<nav class="tier-nav sec-nav" aria-label="Sections">${items.map(([id,t])=>`<a href="#${id}" data-sec="${id}">${t}</a>`).join("")}</nav>`}
const anchor=id=>`<span class="sec-anchor" id="${id}"></span>`;
document.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest("[data-sec]");if(!a)return;e.preventDefault();const t=document.getElementById(a.dataset.sec);if(t)t.scrollIntoView({behavior:"smooth",block:"start"})});   // not a #view link
const readTxt=i=>`${esc(((readsOf().meta||{})[i.id]||{}).title||i.id)}: <b>${i.pct}%</b>${i.ref&&i.ref.median!=null?` <span class="note">· base ${pc0(i.ref.median)}${i.ref.pro!=null?`, pros ${pc0(i.ref.pro)}`:""}</span>`:""}`;
const mRating=x=>{const s=x.sum,nr=typeof x.rounds==="number"?x.rounds:(x.per_round||[]).length;return nr&&s.kast!=null&&s.adr!=null?rating2(s.kills,s.deaths,s.assists,s.adr,s.kast,nr):null};
// Full analysis: the coach's first priority and the analyst's worst reads, your strengths and best reads
function analysisBrief(p,auto){const I=((readsOf().all||{}).items)||[],good=I.filter(i=>i.severity==="positive"),bad=I.filter(i=>(i.severity==="high"||i.severity==="medium")&&i.id!=="spot");
  const St=p.advice.strengths||[],nS=good.length?2:3,r0=auto[0];
  return tabBrief({id:"an-brief",works:[...St.slice(0,nS).map(esc),...good.slice(0,1).map(readTxt)],
    fix:[r0?`<b>${esc(r0.title)}</b>${r0.standing?` <span class="note">· ${esc(r0.standing)}</span>`:""}`:null,...bad.slice(0,2).map(readTxt)],
    next:r0&&r0.fix&&r0.fix.length?r0.fix[0]:null,nextLabel:"Work on"})+(St.length>nS?`<p class="note">Also: ${St.slice(nS).map(esc).join(" · ")}</p>`:"")}
// one match: its rating, the coach's priority, the reads that stand out against the base (with their rounds)
// one map: your record and rating there, your zones that work and the ones to change, a pro grenade to learn
function mapBrief(p,m){const ms=p.matches.filter(x=>x.map===m.map),w=ms.filter(x=>x.result==="win").length,l=ms.filter(x=>x.result==="loss").length;
  const rts=ms.map(mRating).filter(x=>x!=null),avg=rts.length?rts.reduce((a,b)=>a+b,0)/rts.length:null;
  const rec=ms.length?`${w}-${l} on ${esc(MAPN(m.map))}${avg!=null?`, rating ${rtBadge(avg)}`:""}`:null;
  const zs=[];Object.entries(m.sides).forEach(([sd,x])=>(x.zones||[]).forEach(z=>zs.push({...z,side:sd})));
  const zl=z=>`${z.side} · <b>${esc(z.name)}</b>: you ${z.k}-${z.d}${z.win!=null?` (${z.win}%)`:""} <span class="note">· others ${z.others_win??"—"}%</span>`;
  const GA=((p.deep||{}).grenades||{})[m.map],g=GA&&GA.missing&&GA.missing[0],note=Object.values((p.cross_notes||{})[m.map]||{})[0];
  return tabBrief({id:"mp-brief",works:[w>=l?rec:null,...zs.filter(z=>z.verdict==="exploit").slice(0,2).map(zl)],
    fix:[w<l?rec:null,...zs.filter(z=>z.verdict==="avoid").slice(0,2).map(zl)],
    next:g?`Learn this ${g.side} grenade: ${TYPE[g.type]} ${esc(g.from)} → ${esc(nTo(g,m.map)||"?")} <span class="note">(${g.pro_uses} pro throws)</span>`:(note&&note.plan&&note.plan[0])||null,
    nextLabel:`Next time on ${esc(MAPN(m.map))}`})}
function renderAnalysis(){
  const p=P(),v=$("#v-analysis"),ms=p.matches;const rec={win:0,draw:0,loss:0};ms.forEach(m=>rec[m.result]++);
  const auto=p.advice.rules.map((r,i)=>({level:i<2?"high":"mid",title:r.title,evidence:r.why,fix:r.do,standing:r.standing,target:r.target,bench:r.bench,drills:r.drills,sources:r.sources}));
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)} · ${ms.length} matches analyzed</span><h2>Full analysis</h2></div>
    <div class="record"><span>${rec.win}<small>wins</small></span><span>${rec.draw}<small>draws</small></span><span>${rec.loss}<small>losses</small></span></div></div>
    ${missNote(p)}
    ${secNav([["an-brief","Brief"],["an-coach","Coach"],readsOf().all?["an-reads","Analyst reads"]:null,p.advice.bench?["an-base","Vs the base"]:null,["an-role","Role and deep analysis"],p.advice.pros?["an-pros","Pros like you"]:null,ms.length?["an-matches","Matches"]:null])}
    ${analysisBrief(p,auto)}
    ${D.local&&p.steamid!==D.own?`<article class="card form" id="follow-card"><h3>Follow ${esc(p.name)}'s matches</h3><p class="note">Loading…</p></article>`:""}
    ${anchor("an-coach")}${auto.length?`<h3>What I see · ${ms.length} matches</h3>`:""}
    ${findings(auto)}
    ${anchor("an-reads")}${readsSection(p,readsOf().all,`What an analyst points at · ${ms.length} matches`,"Read in your demos like a team's analyst would, each against the base (its median player, the players ranked above you) and pros when their demos tell. A round opens the match's 2D replay.")}
    ${p.overall?`<details class="old-notes"><summary style="cursor:pointer;font-family:var(--f-display);font-size:18px;font-weight:600">Earlier hand-written analysis${p.overall.scope?` · ${esc(p.overall.scope)}`:""}</summary>
      <p class="note" style="margin:8px 0">Written from those matches only: its numbers are from that time. The list above covers all your matches and is the one to follow.</p>
      <p style="max-width:75ch">${p.overall.summary}</p>${findings(p.overall.priorities)}</details>`:""}
    ${anchor("an-base")}${benchSection(p)}
    ${anchor("an-role")}${archCard(p)}
    ${midCard(p)}
    ${deepCard(p)}
    ${anchor("an-pros")}${prosBlock(p)}
    ${extrasBlock(p)}
    ${anchor("an-matches")}${ms.length?`<h3>Match by match</h3><div class="tbl"><table>${TREND_HEAD}<tbody>${trendRows(ms,-1)}</tbody></table></div>`:""}
    ${leetBlock(p)}`;
  $$("tr.click",v).forEach(r=>{r.onclick=()=>{S.match=+r.dataset.i;S.mpin=true;go("matches")};r.onkeydown=e=>{if(e.key==="Enter")r.click()}});
  copyBtn(v);
  fillFollow(p);
}

// ---------- view: matches ----------
const CAPS={control:["Size = number of duels in the zone. Color = side that wins them.",'<span><i style="background:var(--t)"></i>Ts win ≥ 60%</span><span><i style="background:var(--ct)"></i>CTs win ≥ 60%</span><span><i style="background:#8a96a3"></i>contested</span>'],
 mine:["Green dot = your position when you kill. Red cross = your position when you die, dashed from your killer. Number = round.",'<span><i style="background:var(--good)"></i>kill</span><span><i style="background:var(--bad)"></i>death</span>'],
 heatT:["Your presence as T.",'<span><i style="background:var(--t)"></i>presence</span>'],heatCT:["Your presence as CT.",'<span><i style="background:var(--ct)"></i>presence</span>'],
 open:["First kill of each round, all players.",'<span><i style="background:var(--t)"></i>T opening</span><span><i style="background:var(--ct)"></i>CT opening</span>']};
// round by round from the demo: where the Ts went and how fast, who died where and when
function storyBlock(m){const side={};m.per_round.forEach(r=>side[r.round]=r.side);
  const rows=m.story.filter(s=>side[s.r]),ct=rows.filter(s=>side[s.r]==="CT"),tt=rows.filter(s=>side[s.r]==="T");
  const lone=s=>s.td.filter(d=>d[2]&&d[1]<(s.at??60)).length;
  const pl=(k,w,ws)=>`${k} ${k===1?w:ws}`;
  const sum=(xs,who)=>{if(!xs.length)return "";const c=k=>xs.filter(s=>s.dyn===k).length,A=xs.filter(s=>s.site==="A").length,B=xs.filter(s=>s.site==="B").length,L=xs.filter(s=>lone(s)).length;
    const parts=[pl(c("rush"),"rush","rushes"),pl(c("exec"),"execute","executes"),pl(c("late"),"late hit","late hits")];if(c("fast"))parts.push(pl(c("fast"),"fast push by 1-2 Ts","fast pushes by 1-2 Ts"));if(c("none"))parts.push(pl(c("none"),"round without a real attack","rounds without a real attack"));
    const pc={};xs.forEach(s=>{if(s.play_name&&s.play!=="none")pc[s.play_name]=(pc[s.play_name]||0)+1});
    const top=Object.entries(pc).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([k,n])=>`${esc(k)} ×${n}`).join(", ");
    return `<li><b>${who}</b>: ${parts.join(", ")} in ${xs.length} rounds. A ${A}, B ${B}. A T lost alone before the attack in ${pl(L,"round","rounds")}.${top?` Most used: ${top}.`:""}</li>`};
  const feed=s=>[...s.td.map(d=>({t:d[1],h:`<span class="kt${d[2]?" alone":""}">T</span> ${esc(d[0])} ${clock(d[1])}${d[2]?" <i>alone</i>":""}`})),...s.cd.map(d=>({t:d[1],h:`<span class="kc">CT</span> ${esc(d[0])} ${clock(d[1])}`}))].sort((a,b)=>a.t-b.t).map(e=>e.h).join(" · ")||"—";
  const att=s=>{if(s.site!=="A"&&s.site!=="B")return "<b>No clear attack</b>";
    const b=[s.play_name?`<b>${esc(s.play_name)}</b>${/^Rush/.test(s.play_name)?"":` · ${esc(DYN_EN[s.dyn]||"")}`}`:`<b>${s.site} · ${esc(DYN_EN[s.dyn]||"")}</b>`];
    if(s.at!=null)b.push(`${s.in?"on the site":"stopped"} at ${clock(s.at)}${s.grp?`, ${pl(s.grp,"T","Ts")}`:""}`);if(s.plant)b.push(`bomb ${clock(s.plant[1])}`);if(s.lurk)b.push("a T stayed near the other site");if(s.bunch)b.push(`3 Ts down in 10 s at ${esc(s.bunch[0])}`);return b.join("<br>")};
  return `<h3>How each round went</h3><p class="note">From the demo: where the Ts went and how fast, who died where and when. A T killed with no teammate close (about 25 m) and not traded is marked <i>alone</i>. Clock times as in game.</p>
   <ul class="big-list">${sum(ct,"The Ts you faced")}${sum(tt,"Your team as T")}</ul>
   <div class="tbl"><table class="story"><thead><tr><th>Round</th><th>The Ts</th><th>Who died where</th><th>Won by</th></tr></thead><tbody>
   ${rows.map(s=>`<tr><td><b>${s.r}</b><br><span class="note">you ${side[s.r]}</span></td><td class="wrap">${att(s)}</td><td class="wrap feed">${feed(s)}</td><td>${s.tw?"Ts":"CTs"}</td></tr>`).join("")}</tbody></table></div>`}
function renderMatches(){
  const p=P(),v=$("#v-matches"),ms=p.matches;if(S.match>=ms.length){S.match=0;S.mpin=false}
  const m=ms[S.match];
  if(!m){v.innerHTML=p.advice.leetify?`<div class="empty">No analyzed demo for this player. Here are their recent matches according to Leetify.</div>${leetBlock(p)}`:`<div class="empty">No analyzed match yet.</div>`;return}
  const s=m.sum,md=m.map_data;const st={layer:"control",level:md.levels[0].key,side:"all"},lim=S.mall||S.match>=10?ms.length:10;
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${ms.length} matches · pick one below</span><h2>Matches</h2></div></div>
  <div class="tbl"><table>${TREND_HEAD}<tbody>${trendRows(ms.slice(0,lim),S.match)}</tbody></table></div>${ms.length>lim?`<button type="button" class="more-btn" id="mall">All ${ms.length} matches</button>`:""}
  <div class="head" id="mhead"><div style="display:grid;gap:4px"><span class="eyebrow">${fmtDate(m.time)} · ${m.rounds} rounds · ${RES[m.result]}${s.clutches?` · ${s.clutches_won}/${s.clutches} clutches won`:""}${m.hostage?" · hostage map: CTs attack":""}</span>
    <h2>${MAPN(m.map)} · ${esc(m.mode)}</h2></div><div class="record"><span>${m.score.me}-${m.score.them}</span></div>
    ${D.local?`<button type="button" class="close" id="reanalyze" title="Extract this match again from its demo, then update your profile and plan (a minute or two)">Re-analyze this match</button>`:""}</div>
  ${secNav([m.notes?["m-coach","Coach"]:null,m.reads?["m-reads","Analyst reads"]:null,["m-rounds","Rounds"],["m-zones","Zones"],["m-replay","2D replay"]])}
  ${anchor("m-coach")}${m.notes?findings(m.notes.priorities):""}
  ${anchor("m-reads")}${matchReads(m)}
  ${anchor("m-rounds")}${m.story&&m.story.length?storyBlock(m):""}
  <h3>Your rounds</h3><div class="timeline-wrap"><div class="timeline">${m.per_round.map(r=>`<div class="rd ${r.side}" title="Round ${r.round} (${r.side}, ${roleOf(m.map,r.side)}): ${r.won?"won":"lost"}, ${r.kills} kill(s), ${r.deaths} death(s), your buy ${r.my_buy} / team ${r.team_buy}"><span>${r.round}</span><span class="${r.won?"w":"l"}">${r.won?"W":"L"}</span><span>${r.kills}-${r.deaths}</span></div>`).join("")}</div></div>
  ${anchor("m-zones")}<div class="stage"><div class="radar-box">
      <div class="btns" role="group" aria-label="Layer">${[["control","Zone control"],["mine","Your kills and deaths"],["heatT","Your T presence"],["heatCT","Your CT presence"],["open","Opening duels"]].map(([k,t])=>`<button type="button" data-layer="${k}" aria-pressed="${k==="control"}">${t}</button>`).join("")}</div>
      ${levelBtns(md,st.level)}
      <svg class="radar" viewBox="${(D.viewboxes[m.map]||[0,0,1024,1024]).join(" ")}" role="img" aria-label="Radar"><image x="0" y="0" width="1024" height="1024"></image><g></g></svg><div class="caption"></div></div>
    <div style="display:grid;gap:10px;min-width:0"><h3>Zones of the match</h3><div class="tbl"><table><thead><tr><th>Zone</th><th class="n">Duels</th><th class="n">K/D T</th><th class="n">K/D CT</th><th class="n">You</th></tr></thead><tbody id="mzt"></tbody></table></div></div></div>`;
  $$("tr.click",v).forEach(r=>{r.onclick=()=>{S.match=+r.dataset.i;S.mpin=true;syncUrl();renderMatches();$("#mhead").scrollIntoView({behavior:"smooth"})};r.onkeydown=e=>{if(e.key==="Enter")r.click()}});
  const ma=$("#mall",v);if(ma)ma.onclick=()=>{S.mall=true;renderMatches()};
  const rb=$("#reanalyze",v);if(rb)rb.onclick=async()=>{rb.disabled=true;rb.textContent="Re-analysis running…";
    jobFrom=S.view;try{const r=await fetch("/api/reanalyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sid:p.steamid,mid:m.id})});const j=await r.json();
      if(!r.ok){jobPanel(`<b>${esc(j.error||"Error")}</b>${j.query?` (${esc(j.query)})`:""}`,"err");rb.disabled=false;rb.textContent="Re-analyze this match";if(r.status===409)poll();return}
      poll()}catch(e){jobPanel(`<b>The local server doesn't answer.</b> Restart "Wily.bat" and I'll be back.`,"err");rb.disabled=false;rb.textContent="Re-analyze this match"}};
  const box=$(".radar-box",v),ov=$("g",box);
  function draw(){
    $("image",box).setAttribute("href",D.radars[`${m.map}:${st.level}`]||"");ov.replaceChildren();const L=st.level;
    $(".caption",box).innerHTML=`<span>${CAPS[st.layer][0]}</span>${CAPS[st.layer][1]}`;
    const zones=md.zones.filter(z=>z.level===L);
    if(st.layer==="control")zones.forEach(z=>{const g=md.general[z.key];if(!g||!g.duels)return;const r=6+Math.sqrt(g.duels)*4,tw=g.t_win_pct,col=tw>=60?"var(--t)":tw<=40?"var(--ct)":"#8a96a3";
      tip(el("circle",{cx:z.px[0],cy:z.px[1],r,style:`fill:${col};fill-opacity:.72;stroke:#fff;stroke-width:1.5`},ov),`${z.name}: ${g.duels} duels, Ts win ${tw}%`);
      el("text",{x:z.px[0],y:z.px[1]-r-3,"text-anchor":"middle",class:"zlabel"},ov).textContent=z.name;});
    if(st.layer==="heatT"||st.layer==="heatCT"){const cells=(md.heat[st.layer==="heatT"?"me_T":"me_CT"]||{})[L]||[],col=st.layer==="heatT"?"var(--t)":"var(--ct)";
      cells.forEach(([x,y,val])=>el("rect",{x,y,width:24,height:24,style:`fill:${col};fill-opacity:${(0.12+0.8*Math.sqrt(val)).toFixed(2)}`},ov));
      zones.forEach(z=>el("text",{x:z.px[0],y:z.px[1]+4,"text-anchor":"middle",class:"zsmall"},ov).textContent=z.name)}
    if(st.layer==="open")md.openings.filter(k=>(k.a_level||L)===L||(k.v_level||L)===L).forEach(k=>{const col=k.side==="T"?"var(--t)":"var(--ct)";
      el("line",{x1:k.a[0],y1:k.a[1],x2:k.v[0],y2:k.v[1],style:`stroke:${col};stroke-width:2.5`},ov);el("circle",{cx:k.a[0],cy:k.a[1],r:5,style:`fill:${col};stroke:#fff`},ov);el("circle",{cx:k.v[0],cy:k.v[1],r:3,style:"fill:#fff"},ov)});
    if(st.layer==="mine"){md.my_kills.filter(k=>(k.level||L)===L).forEach(k=>{el("line",{x1:k.px[0],y1:k.px[1],x2:k.victim_px[0],y2:k.victim_px[1],style:"stroke:var(--good);stroke-width:2"},ov);
        tip(el("circle",{cx:k.px[0],cy:k.px[1],r:7,style:"fill:var(--good);stroke:#fff;stroke-width:1.5"},ov),`Round ${k.round} (${k.side}): kill from ${k.zone} at ${k.t} s`);el("text",{x:k.px[0]+9,y:k.px[1]+4,class:"zsmall"},ov).textContent=k.round});
      md.my_deaths.filter(k=>(k.level||L)===L).forEach(k=>{el("line",{x1:k.killer_px[0],y1:k.killer_px[1],x2:k.px[0],y2:k.px[1],style:"stroke:var(--bad);stroke-width:2;stroke-dasharray:5 4"},ov);
        const g=tip(el("g",{},ov),`Round ${k.round} (${k.side}): died at ${k.zone} at ${k.t} s, killed from ${k.killer_zone} (${k.weapon})`);
        el("path",{d:`M${k.px[0]-6} ${k.px[1]-6}L${k.px[0]+6} ${k.px[1]+6}M${k.px[0]+6} ${k.px[1]-6}L${k.px[0]-6} ${k.px[1]+6}`,style:"stroke:var(--bad);stroke-width:3.5;stroke-linecap:round"},g);el("text",{x:k.px[0]+9,y:k.px[1]+4,class:"zsmall",style:"fill:#ffb3ae"},ov).textContent=k.round})}
  }
  $$("[data-layer]",box).forEach(b=>b.onclick=()=>{st.layer=b.dataset.layer;press(box,"[data-layer]",b);draw()});
  $$("[data-level]",box).forEach(b=>b.onclick=()=>{st.level=b.dataset.level;press(box,"[data-level]",b);draw()});
  const myZ={};["T","CT"].forEach(sd=>Object.entries(md.me[sd]?.zones||{}).forEach(([k,z])=>{const o=myZ[k]||(myZ[k]={k:0,d:0});o.k+=z.kills;o.d+=z.deaths}));
  const kd=x=>x==null?"—":x.toFixed(2),pill=x=>x==null?"":x>=1.4?' <span class="pill strong">strong</span>':x<=0.75?' <span class="pill weak">weak</span>':"";
  $("#mzt").innerHTML=md.zones.map(z=>({z,g:md.general[z.key]})).filter(x=>x.g&&x.g.duels).sort((a,b)=>b.g.duels-a.g.duels).slice(0,16)
    .map(({z,g})=>`<tr><td>${esc(z.name)}</td><td class="n">${g.duels}</td><td class="n">${kd(g.T.kd)}${pill(g.T.kd)}</td><td class="n">${kd(g.CT.kd)}${pill(g.CT.kd)}</td><td class="n">${myZ[z.key]?myZ[z.key].k+"-"+myZ[z.key].d:"—"}</td></tr>`).join("");
  draw();
  const rh=document.createElement("section");rh.id="m-replay";rh.style.cssText="display:grid;gap:10px;scroll-margin-top:150px";rh.innerHTML=`<h3>2D replay</h3><p class="note">Every round replayed on the radar (every 0.5 s): your dot has a white ring, crosses are deaths, colored circles are grenades.</p><div class="rp-host"></div>`;
  v.appendChild(rh);replayBlock($(".rp-host",rh),p,m);
}

// ---------- 2D replay ----------
const RP={};
async function replayBlock(host,p,m){
  host.innerHTML=`<div class="radar-box"><div class="rp-rounds" role="group" aria-label="Round"></div>
    <div class="rp-ctl"><button type="button" class="rp-play" style="font:600 13px var(--f-body);padding:5px 12px;border:1px solid var(--ink);background:var(--ink);color:var(--bg);border-radius:3px;cursor:pointer">Play</button>
      <input type="range" class="rp-t" min="0" max="100" step="0.5" value="0" aria-label="Round time"><span class="rp-time">0.0 s</span>
      <select class="rp-speed" aria-label="Speed" style="font:13px var(--f-body);background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:3px;padding:3px"><option value="1">×1</option><option value="2" selected>×2</option><option value="4">×4</option></select></div>
    <svg class="radar" viewBox="${(D.viewboxes[m.map]||[0,0,1024,1024]).join(" ")}" role="img" aria-label="2D replay"><image x="0" y="0" width="1024" height="1024"></image><g></g></svg>
    <div class="rp-feed"></div></div>`;
  let R=RP[`${p.steamid}:${m.id}`];
  if(!R){try{const r=await fetch(`replays/${p.steamid}/${m.id}.json`);R=r.ok?await r.json():null}catch(e){R=null}RP[`${p.steamid}:${m.id}`]=R}
  if(!R){host.innerHTML=`<div class="empty">No 2D replay for this match: its demo was not extracted in detail.</div>`;return}
  const me=R.players.findIndex(x=>x.steamid===p.steamid);const box=$(".radar-box",host),svg=$("svg",box),ov=$("g",svg),img=$("image",svg);
  let ri=0,t=0,timer=null;const lv0=m.map_data.levels[0].key;img.setAttribute("href",D.radars[`${m.map}:${lv0}`]||"");
  const rb=$(".rp-rounds",box);rb.innerHTML=R.rounds.map((r,i)=>{const pr=m.per_round.find(x=>x.round===r.n);return `<button type="button" class="${pr?pr.side:""}" data-ri="${i}" data-rn="${r.n}" aria-pressed="${i===0}" title="${pr?(pr.won?"won":"lost"):""}">${r.n}</button>`}).join("");
  const slider=$(".rp-t",box),lab=$(".rp-time",box),feed=$(".rp-feed",box);
  function frameAt(r,tt){let f=r.frames[0];for(const x of r.frames){if(x[0]<=tt)f=x;else break}return f}
  function draw(){const r=R.rounds[ri];if(!r)return;ov.replaceChildren();const f=frameAt(r,t);
    r.nades.filter(n=>n[0]<=t&&n[0]>t-15).forEach(n=>{const col=n[1]==="smoke"?"var(--smoke)":n[1]==="flash"?"var(--flash)":n[1]==="molotov"?"var(--molotov)":"var(--he)";
      el("circle",{cx:n[2],cy:n[3],r:n[1]==="smoke"?16:n[1]==="molotov"?12:8,style:`fill:${col};fill-opacity:${n[1]==="smoke"?.55:.45};stroke:${col}`},ov)});
    r.kills.filter(k=>k[0]<=t).forEach(k=>{el("path",{d:`M${k[3]-5} ${k[4]-5}L${k[3]+5} ${k[4]+5}M${k[3]+5} ${k[4]-5}L${k[3]-5} ${k[4]+5}`,style:`stroke:${k[2]===me?"#ff4d4d":"#bbb"};stroke-width:2.5;stroke-linecap:round;opacity:.9`},ov)});
    if(f)f[1].forEach(([pi,x,y,sd])=>{const mine=pi===me;el("circle",{cx:x,cy:y,r:mine?9:6.5,style:`fill:${sd?"var(--ct)":"var(--t)"};stroke:${mine?"#fff":"#000"};stroke-width:${mine?3:1.2}`},ov);
      el("text",{x:x+9,y:y-7,class:"pname"},ov).textContent=(R.players[pi]||{}).name||""});
    lab.textContent=`${t.toFixed(1)} s`;slider.value=t;
    feed.innerHTML=r.kills.filter(k=>k[0]<=t).map(k=>`<span>${k[0].toFixed(1)} s · <b${k[1]===me?' class="good"':""}>${esc((R.players[k[1]]||{}).name||"?")}</b> → <b${k[2]===me?' class="bad"':""}>${esc((R.players[k[2]]||{}).name||"?")}</b> (${esc(k[5])})</span>`).join("")||`<span class="note">No kill yet.</span>`}
  function setRound(i){ri=i;t=0;const r=R.rounds[i];slider.max=r.frames.length?r.frames[r.frames.length-1][0]:100;press(box,"[data-ri]",$(`[data-ri="${i}"]`,box));draw()}
  $$("[data-ri]",box).forEach(b=>b.onclick=()=>{stop();setRound(+b.dataset.ri)});
  slider.oninput=()=>{t=+slider.value;draw()};
  function stop(){clearInterval(timer);timer=null;$(".rp-play",box).textContent="Play"}
  $(".rp-play",box).onclick=()=>{if(timer){stop();return}$(".rp-play",box).textContent="Pause";
    timer=setInterval(()=>{t+=0.25*(+$(".rp-speed",box).value);if(t>=+slider.max){t=+slider.max;draw();stop();return}draw()},125)};
  setRound(0);
  if(S.goRound){const i=R.rounds.findIndex(r=>r.n===S.goRound);S.goRound=null;if(i>=0){setRound(i);box.scrollIntoView({behavior:"smooth",block:"center"})}}
}

// ---------- view: maps and grenades ----------
function renderMaps(){
  const p=P(),v=$("#v-maps"),c=p.cross,maps=mapsOf(p);
  if(!c||!c.contexts){v.innerHTML=`<div class="empty">Positions and grenades need demos. No demo is available for this player yet: it takes their recent share codes (matchmaking), or a FACEIT API key for their FACEIT matches.</div>`;return}
  const ctx=Object.fromEntries(c.contexts.map(x=>[x.name,x.rows])),row=(g,i)=>(ctx[g]||[])[i]||{};
  const cmp=(rows,meOnly)=>`<div class="cmp">${rows.map(([lb,r])=>`<div class="row"><span class="lb">${lb} · you</span><div class="meter ${r.win<45?"low":""}"><i style="width:${r.win||0}%"></i></div><span class="v">${r.win??"—"}%</span></div>
    ${meOnly?"":`<div class="row"><span class="lb">${lb} · others</span><div class="meter oth"><i style="width:${r.others_win||0}%"></i></div><span class="v">${r.others_win??"—"}%</span></div>`}`).join("")}</div>`;
  const INS=[["Holding or peeking",[["Holding",row("Movement at the start of the duel",0)],["Peeking",row("Movement at the start of the duel",1)]]],
    ["Long range or close",[["Over 20 m",row("Distance",2)],["Under 10 m",row("Distance",0)]]],
    ["Healthy or hurt",[["Over 80 HP",row("Health at the start of the duel",0)],["Under 50 HP",row("Health at the start of the duel",1)]]],
    ["Balance of power",[["Advantage",row("Balance of power",0)],["Outnumbered",row("Balance of power",2)]]]];
  const rp=c.repeek||{moved:{},stayed:{}};
  const TECH=[["Jiggle-peek for info","One step to the side then straight back (A-D) to see the angle without exposing yourself. You force the enemy to peek at you."],
    (()=>{const mv=rp.moved.win,st=rp.stayed.win,txt=`Next duel after a kill: ${mv??"—"}% won when you change position, ${st??"—"}% when you stay in the same spot`;
      return mv!=null&&st!=null&&mv-st<3?["After a kill: no gain from moving yet",`${txt}: no clear difference for you. Repositioning still keeps you unpredictable; re-peek only with a teammate ready to trade.`]:["Move after a kill",`${txt}.`]})(),
    ["Grenade ready before the contact","Each map sheet gives the time of the first contact in your zones. Have your molotov or flash in hand 3 seconds before."],
    ["Hurt: fall back","Under 50 HP, call your HP, fall back one angle and cover a healthy teammate's trade."],
    ["Shot next to you = move","If a teammate dies near you, back off a meter: the enemy pre-aims the standard angle."],
    ["Play the advantage","At 5v4, move up with your team to take space. Don't hold alone."]];
  if(!S.cmap||!maps.some(x=>x.map===S.cmap))S.cmap=maps[0]?.map;
  v.innerHTML=`<div class="head"><div style="display:grid;gap:4px"><span class="eyebrow">${esc(p.name)} · ${c.totals.my_duels} duels compared with ${c.totals.others_duels} duels of other players</span><h2>Maps and grenades</h2></div></div>
  ${secNav([["mp-brief","Brief"],["mp-sheet","Map sheet"],["lus","Lineups"],["mp-duels","Your duels"],["mp-tech","Techniques"]])}
  <div class="chips" role="group" aria-label="Map">${maps.map((x,i)=>`${chipSep(maps,i,y=>y.map)}<button type="button" data-cmap="${x.map}" aria-pressed="${x.map===S.cmap}">${MAPN(x.map)}<small>${x.n}</small></button>`).join("")}</div>
  <div id="cmap"></div>
  ${anchor("mp-duels")}<h3>How your duels go</h3>
  <div class="insights">${INS.map(([t,r])=>`<article class="card"><h3>${t}</h3>${cmp(r)}</article>`).join("")}</div>
  ${anchor("mp-tech")}<h3>Techniques to use during the round</h3><div class="tech">${TECH.map(([a,b])=>`<div><b>${a}</b>${b}</div>`).join("")}</div>
  <details><summary style="cursor:pointer;font-family:var(--f-display);font-size:20px;font-weight:600">Every duel context</summary>
    <div class="tbl" style="margin-top:10px"><table><thead><tr><th>Situation</th><th class="n">Your duels</th><th class="n">You</th><th class="n">Others</th></tr></thead><tbody>${c.contexts.map(g=>`<tr><td class="grp" colspan="4">${esc(g.name)}</td></tr>`+g.rows.map(r=>{const d=(r.win??0)-(r.others_win??0),k=r.n>=15?(d>=8?"good":d<=-8?"bad":""):"";return `<tr><td class="wrap">${esc(r.label)}</td><td class="n">${r.n}</td><td class="n ${k}">${r.win==null?"—":r.win+"%"}</td><td class="n">${r.others_win==null?"—":r.others_win+"%"}</td></tr>`}).join("")).join("")}</tbody></table></div></details>
  <p class="note">General zones, best spots and lineups come from every demo of the map in the base. Your zones come from your matches only.</p>`;
  $$("[data-cmap]",v).forEach(b=>b.onclick=()=>{S.cmap=b.dataset.cmap;press(v,"[data-cmap]",b);mapSheet()});
  mapSheet();
  function mapSheet(){
    const m=crossMap(p,S.cmap),host=$("#cmap",v);if(!m){host.innerHTML="";return}
    const sides=Object.keys(m.sides);const st={side:sides.includes(S.side)?S.side:sides[0],level:m.levels[0].key,layers:["zones"],sel:null};
    host.innerHTML=`<div style="display:grid;gap:14px"><span class="eyebrow">${m.matches} of your matches · ${m.pool||m.matches} demos of ${MAPN(m.map)} in the base</span>${mapBrief(p,m)}${anchor("mp-sheet")}<div class="btns side big" role="group" aria-label="Side">${sides.map(s=>`<button type="button" data-side="${s}" aria-pressed="${s===st.side}">${s} · ${roleOf(m.map,s)}</button>`).join("")}</div>
      <div class="stage">${radarShell(`<div class="btns" role="group" aria-label="Layer">${[["zones","Your zones"],["duels","Your duels"],["best","Others' spots"],["nades","Grenades"]].map(([k,t])=>`<button type="button" data-layer="${k}" aria-pressed="${k==="zones"}">${t}</button>`).join("")}</div>${levelBtns(m,st.level)}`)}
        <div style="display:grid;gap:14px;min-width:0" id="zl"></div></div>
      <h3>Lineups of the zones you play, the most effective first</h3><div class="lineups" id="lus"></div></div>`;
    const box=$(".radar-box",host);
    const redraw=()=>crossRadar(box,m,st.side,st);
    function panel(){const Sd=m.sides[st.side],note=((p.cross_notes||{})[m.map]||{})[st.side];
      const ex=Sd.zones.filter(z=>z.verdict==="exploit"),av=Sd.zones.filter(z=>z.verdict==="avoid"),fr=Sd.zones.slice(0,6);
      const li=z=>`<li><b>${esc(z.name)}</b> · you ${z.k}-${z.d}${z.win!=null?` (${z.win}%)`:""} · others ${z.others_win??"—"}%${z.killed_from.length&&z.d?` · killed from ${z.killed_from.map(k=>esc(k.zone)+(k.n>1?` ×${k.n}`:"")).join(", ")}`:""}</li>`;
      $("#zl",host).innerHTML=`${note?`<div class="card"><h3>${esc(note.title)}</h3><ul>${note.plan.map(t=>`<li>${t}</li>`).join("")}</ul></div>`:""}
        ${ex.length?`<div class="zl ex"><h4>Play these more</h4><ul>${ex.map(li).join("")}</ul></div>`:""}
        ${av.length?`<div class="zl av"><h4>Avoid, or play them differently</h4><ul>${av.map(li).join("")}</ul></div>`:""}
        <div class="zl fr"><h4>Your most played zones</h4><ul>${fr.map(z=>`<li><b>${esc(z.name)}</b> · ${Math.round(z.presence)}% of your time · ${z.k}-${z.d} · 1st contact around ${z.early_contact_s==null?"—":clock(z.early_contact_s)}</li>`).join("")}</ul></div>
        ${(Sd.pool_zones||[]).length?`<div><h4 class="lbl4" style="color:var(--muted);margin-bottom:6px">What works for ${st.side}s on ${MAPN(m.map)} · base of ${m.pool||m.matches} demos</h4>
          <div class="tbl"><table><thead><tr><th>Zone</th><th class="n">Duels won</th><th class="n">Duels</th><th class="n">Players' time</th><th class="n">Holding</th><th class="n">Moment</th><th class="n">You</th></tr></thead><tbody>
          ${Sd.pool_zones.filter(z=>z.k+z.d>=20).map(z=>`<tr><td>${esc(z.name)}</td><td class="n ${z.win>=56?"good":z.win<=42?"bad":""}">${z.win}%</td><td class="n">${z.k+z.d}</td><td class="n">${Math.round(z.others_presence)}%</td><td class="n">${z.hold_pct==null?"—":z.hold_pct+"%"}</td><td class="n">${clock(z.t_med)}</td><td class="n">${Math.round(z.my_presence)}%</td></tr>`).join("")}
          </tbody></table></div><p class="note">"Duels won": duels won by ${st.side}s standing in the zone. "Holding": share of those duels started without moving. "Moment": the game clock at the duel (median). Zones with at least 20 duels.</p></div>`:""}`;
      const GA=((p.deep||{}).grenades||{})[m.map],miss=GA?GA.missing.filter(x=>x.side===st.side):[];
      $("#zl",host).insertAdjacentHTML("beforeend",miss.length?`<div><h4 class="lbl4" style="color:var(--muted);margin-bottom:6px">Pro grenades to add to your ${st.side} game</h4>
        <p class="note">Thrown by pros from the zones you play, to spots you never throw at.</p>
        <div class="lineups">${miss.map(x=>`<article class="lu" data-type="${x.type}"><div class="top"><span class="ty">${TYPE[x.type]} · ${x.pro_uses} pro throws</span><span class="pill">${clock(x.t)}</span></div>
          <div class="route">${esc(x.from)} → ${esc(nTo(x,S.cmap)||"?")}</div><div class="meta">${esc(x.how)} · seen from ${esc(x.by)}</div>
          <div class="cmd"><code>${esc(x.setpos)}</code><button type="button">Copy</button></div></article>`).join("")}</div></div>`:"");
      const clipHost=document.createElement("div");$("#zl",host).appendChild(clipHost);
      clipsReady.then(()=>{const cs=clipsOf(m.map,st.side);if(!cs.length||!clipHost.isConnected)return;
        clipHost.innerHTML=`<h4 class="lbl4" style="color:var(--muted);margin-bottom:6px">From the clips you sent</h4>
          <p class="note">Each clip's grenades found in the base's demos: the exact spot, aim and technique. They come up in your warm-ups on ${esc(MAPN(m.map))}, one after the other. A card draws it on the radar.</p>
          ${cs.map(c=>clipHead(c)+`<div class="lineups">${clipCards(c)}</div>`).join("")}`;
        $$(".lu.cat",clipHost).forEach(cd=>{cd.onclick=e=>{if(e.target.closest("button"))return;const c=cs.find(y=>y.id===cd.dataset.clip),x=c&&c.throws[+cd.dataset.ci];if(!x||!x.px)return;
          st.layers=["nades"];st.sel=null;press(box,"[data-layer]",$('[data-layer="nades"]',box));
          if(x.level&&x.level!==st.level&&m.levels.some(y=>y.key===x.level)){st.level=x.level;const b=$(`[data-level="${x.level}"]`,box);if(b)press(box,"[data-level]",b)}
          redraw();c.throws.forEach(y=>y.px&&drawCat(box,y,st.level));$$(".lu",host).forEach(y=>y.classList.toggle("sel",y===cd));box.scrollIntoView({behavior:"smooth",block:"nearest"})};
          cd.onkeydown=e=>{if(e.key==="Enter")cd.click()}});
        copyBtn(clipHost)});
      const catHost=document.createElement("div");$("#zl",host).appendChild(catHost);
      nadeCat(m.map).then(C=>{if(!C||!catHost.isConnected)return;const xs=C.lineups.filter(x=>x.side===st.side).slice(0,9);if(!xs.length)return;
        catHost.innerHTML=`<h4 class="lbl4" style="color:var(--muted);margin-bottom:6px">Pro catalog lineups, verified in the demos</h4>
          <p class="note">Of the ${C.n_catalog} lineups of <a href="${esc(C.source.url)}" target="_blank" rel="noopener" style="color:var(--ct)">${esc(C.source.label)}</a> on ${esc(MAPN(m.map))}, the ${C.found} found in the base's real throws: their exact aim and technique. The most thrown first; a card draws it on the radar.</p>
          <div class="lineups">${xs.map((x,i)=>`<article class="lu cat" data-type="${x.type}" data-ci="${i}" tabindex="0"><div class="top"><span class="ty">${TYPE[x.type]} · ${x.uses} throws${x.pro_uses?`, ${x.pro_uses} by pros`:""}</span></div>
            <div class="route">${esc(x.from_zone||"?")} → ${esc(x.to_zone||"?")}</div><div class="meta">${esc(x.how)}${x.click&&x.click!=="None"?` · ${esc(x.click)} click`:""}${x.pros.length?` · ${x.pros.slice(0,3).map(esc).join(", ")}`:""}</div>
            <div class="cmd"><code>${esc(x.setpos)}</code><button type="button">Copy</button></div></article>`).join("")}</div>`;
        $$(".lu.cat",catHost).forEach(cd=>{cd.onclick=e=>{if(e.target.closest("button"))return;const x=xs[+cd.dataset.ci];st.layers=["nades"];st.sel=null;press(box,"[data-layer]",$('[data-layer="nades"]',box));
          if(x.level&&x.level!==st.level&&m.levels.some(y=>y.key===x.level)){st.level=x.level;const b=$(`[data-level="${x.level}"]`,box);if(b)press(box,"[data-level]",b)}
          redraw();drawCat(box,x,st.level);$$(".lu",host).forEach(y=>y.classList.toggle("sel",y===cd));box.scrollIntoView({behavior:"smooth",block:"nearest"})};
          cd.onkeydown=e=>{if(e.key==="Enter")cd.click()}});
        copyBtn(catHost)});
      const PZ=((p.advice.pros||{}).maps||{})[m.map]||{},pz=PZ[st.side];
      $("#zl",host).insertAdjacentHTML("beforeend",pz?`<div><h4 class="lbl4" style="color:var(--muted);margin-bottom:6px">Pros who play your zones as ${st.side}</h4>
        <p class="note">Your zones: ${pz.mine.map(z=>`${esc(z.zone)} ${z.share}%`).join(" · ")}. The percentage is the share of time spent in the same zones as you.</p>
        <div class="pros">${pz.pros.map(x=>proCard(x,"overlap")).join("")}</div></div>`:"");
      const eff=l=>l.type==="flash"?(l.enemies_blind_avg||0)+(l.kills_after||0)/Math.max(1,l.uses):l.type==="smoke"?(l.uses||0)/100:(l.damage_avg||0)/20,
        low=l=>(l.type==="he"&&(l.damage_avg||0)<5)||(l.type==="flash"&&(l.enemies_blind_avg||0)<.15),TO={smoke:0,flash:1,molotov:2,he:3};
      const LU=Sd.lineups.map((l,i)=>[l,i]).sort((a,b)=>(TO[a[0].type]??9)-(TO[b[0].type]??9)||eff(b[0])-eff(a[0])),okL=LU.filter(([l])=>!low(l)),lowL=LU.filter(([l])=>low(l));
      $("#lus",host).innerHTML=Sd.lineups.length?okL.map(([l,i])=>lineupCard(l,i)).join("")+(lowL.length?`<details style="grid-column:1/-1"><summary>${lowL.length} lineup${lowL.length>1?"s":""} with almost no effect (under 5 damage, or almost nobody flashed)</summary><div class="lineups">${lowL.map(([l,i])=>lineupCard(l,i)).join("")}</div></details>`:""):`<p class="note">Not enough grenades observed.</p>`;
      $$(".lu",host).forEach(cd=>{cd.onclick=()=>{st.sel=+cd.dataset.i;st.layers=["nades"];press(box,"[data-layer]",$('[data-layer="nades"]',box));const l=Sd.lineups[st.sel];
        if(l.level!==st.level&&m.levels.some(x=>x.key===l.level)){st.level=l.level;const b=$(`[data-level="${l.level}"]`,box);if(b)press(box,"[data-level]",b)}
        $$(".lu",host).forEach(x=>x.classList.toggle("sel",x===cd));redraw();box.scrollIntoView({behavior:"smooth",block:"nearest"})};cd.onkeydown=e=>{if(e.key==="Enter")cd.click()}});
      copyBtn(host)}
    $$("[data-side]",host).forEach(b=>b.onclick=()=>{st.side=b.dataset.side;st.sel=null;press(host,"[data-side]",b);panel();redraw()});
    $$("[data-layer]",box).forEach(b=>b.onclick=()=>{st.layers=[b.dataset.layer];st.sel=null;press(box,"[data-layer]",b);redraw()});
    $$("[data-level]",box).forEach(b=>b.onclick=()=>{st.level=b.dataset.level;press(box,"[data-level]",b);redraw()});
    panel();redraw();
  }
}
