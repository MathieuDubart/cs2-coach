
// ---------- live radar: where to stand and what to throw (strong spots, multi-kill spots, grenades for now, rotation
// after the plant). The odds (sites, entrances, rush) live in the side panel only: the radar never repeats them ----------
const playSite=p=>p==="none"?"none":p.startsWith("rush")||p.startsWith("split")?p.slice(-1):p[0];
const isRushPlay=p=>p.startsWith("rush");
// odds of every play this round: the base's plays for this kind of round, the team's rushes, what you see in the
// round (clock, first contact), then scaled to the site reading (which also knows this team's habits)
function tsidePlays(TS,map,g,ev,r){const M=TS&&TS.maps&&TS.maps[map],P=M&&M.plays;if(!P||!r)return null;
  let pr={},w=0;
  for(const [c,k] of Object.entries(r.mix||{})){const x=P.prior[c]||P.prior.all;if(!x||!k)continue;for(const [p,v] of Object.entries(x))pr[p]=(pr[p]||0)+k*v;w+=k}
  if(!w)pr=Object.assign({},P.prior.all);
  let R0=0;for(const p in pr)if(isRushPlay(p))R0+=pr[p];
  const RP=r.rush/100;if(R0>0.005&&R0<0.995){const k1=RP/R0,k0=(1-RP)/(1-R0);for(const p in pr)pr[p]*=isRushPlay(p)?k1:k0}
  const t=g&&g.elapsed!=null?g.elapsed:0,ev0=ev||{};
  if(r.live&&!r.planted&&t>=5&&P.surv&&P.surv.t){const i=Math.min(P.surv.t.length-1,Math.round(t/5));for(const p in pr){const s=P.surv[p];if(s)pr[p]*=s[i]}}
  if(r.live&&!r.planted&&ev0.contact&&P.contact)for(const p in pr){const L=P.contact[p];if(L)pr[p]*=(L[ev0.contact]??L.other??1)}
  const tot={A:0,B:0,none:0},want={A:r.A/100,B:r.B/100,none:r.none/100};for(const p in pr)tot[playSite(p)]+=pr[p];
  for(const p in pr){const s=playSite(p);pr[p]=tot[s]>1e-9?pr[p]*want[s]/tot[s]:0}
  const sum=Object.values(pr).reduce((a,b)=>a+b,0)||1;for(const p in pr)pr[p]/=sum;
  // each entrance: chance it is used this round, chance it gets pushed in the next 15 s, the rushes through it
  const lanes=[];
  ["A","B"].forEach(s=>((P.lanes||{})[s]||[]).forEach((L,i)=>{let use=0,haz=0,rush=0;
    for(const p in pr){if(playSite(p)!==s)continue;const u=(P.use[p]||{})[i]||0;if(!u||!pr[p])continue;use+=pr[p]*u;if(isRushPlay(p))rush+=pr[p]*u;
      const sv=P.surv[p];if(sv){const i0=Math.min(sv.length-1,Math.floor(t/5)),i1=Math.min(sv.length-1,i0+3);if(sv[i0]>0.002)haz+=pr[p]*u*Math.max(0,(sv[i0]-sv[i1])/sv[i0])}}
    lanes.push(Object.assign({},L,{site:s,i,key:s+i,p:use,haz,rush}))}));
  const list=Object.entries(pr).map(([p,v])=>({p,v,label:P.label[p]||p,site:playSite(p)})).sort((a,b)=>b.v-a.v);
  return {list,lanes,rush:list.filter(x=>isRushPlay(x.p)).reduce((a,x)=>a+x.v,0),pr}}

// grenades worth throwing now, at the entrances (time-aware): anti-rush only while a rush is still possible,
// blocking when the base says the Ts usually push that entrance in the next seconds
function nadesNow(PL,map,g,PLs,live){const E=((((PL.nades||{}).maps||{})[map])||{}).CT,LP=E&&E.lanes;if(!LP||!PLs)return [];
  // a pistol round or a save: the buy card says kevlar / nothing, so only the grenades you have (none: none shown)
  const tight=!!g&&g.round_phase==="freezetime"&&["pistol","eco"].includes(advisedType(g));
  const t=live&&g&&g.elapsed!=null?g.elapsed:0,held=live&&g&&g.nades?g.nades:tight?(g.nades||{}):null,out=[];
  PLs.lanes.forEach(L=>{const picks=LP[L.key]||{};
    Object.entries(picks).forEach(([type,x])=>{if(held&&!(held[type]>0))return;
      let why=null,score=0;
      const nm=L.name.split(" / ")[0];
      if(x.role==="anti_rush"){if(t<=32&&L.rush>=0.05){why=`anti-rush on ${nm}: ${Math.round(100*L.rush)}% they rush through here`;score=L.rush*1.2}}
      else if(x.role==="block"){if(L.haz>=0.1||(!live&&L.p>=0.3&&type==="smoke")){why=live?`block ${nm}: ${Math.round(100*L.haz)}% they push it in the next 15 s`:`block ${nm} (${Math.round(100*L.p)}% of attacks use it)`;score=live?L.haz:L.p*0.5}}
      else if(x.role==="flash"){if(L.haz>=0.12){why=`flash ${nm} as they push: blinds an enemy ${x.blind}% of the time`;score=L.haz*0.7}}
      else if(L.haz>=0.12){why=`HE on ${nm} as they push`;score=L.haz*0.6}
      if(why)out.push(Object.assign({},x,{type,why,score,lane:L.key,laneName:L.name}))})});
  out.sort((a,b)=>b.score-a.score);
  const seen=new Set();return out.filter(x=>{const k=x.type+x.lane;if(seen.has(k))return false;seen.add(k);return true}).slice(0,4)}

// your live position on the radar (world units -> radar pixels), and the zone you are in
function worldPx(GEO,pos){const R=GEO&&GEO.radar;if(!R||!pos)return null;
  const px=[(pos[0]-R.pos_x)/R.scale*(R.f||1),(R.pos_y-pos[1])/R.scale*(R.f||1)];
  let lv=(R.levels[0]||{}).key;for(const L of R.levels){if(L.z_min!=null&&pos[2]<L.z_min)continue;if(L.z_max!=null&&pos[2]>=L.z_max)continue;lv=L.key;break}
  return {px,level:lv}}
function nearestZone(GEO,px,level){let best=null,bd=1e9;Object.entries((GEO&&GEO.zones)||{}).forEach(([n,z])=>{if(level&&z.level&&z.level!==level)return;const d=Math.hypot(z.px[0]-px[0],z.px[1]-px[1]);if(d<bd){bd=d;best=n}});return best}
// rotation to the bomb site from where you are (or your usual spot): the ways players of the base take
function rotationFor(M,site,from,GEO){const R=((M.rotations||{})[site])||{};if(!Object.keys(R).length||!from)return null;
  let k=R[from]?from:null;
  if(!k&&GEO&&GEO.zones&&GEO.zones[from]){const f=GEO.zones[from].px;k=Object.keys(R).filter(z=>GEO.zones[z]).sort((a,b)=>Math.hypot(GEO.zones[a].px[0]-f[0],GEO.zones[a].px[1]-f[1])-Math.hypot(GEO.zones[b].px[0]-f[0],GEO.zones[b].px[1]-f[1]))[0]}
  return k?{from:k,...R[k]}:null}

// ---------- radar drawing: one visual language per layer ----------
// strong spots: green shields · multi-kills: gold stars (yours), white stars (other players, on your spots) · your spots: thin rings ·
// grenades: dotted arcs ending on the grenade's own icon · rotation: route with a dark casing and chevrons ·
// plant: C4 tag · you: pulsing white dot
const PLACED=new WeakMap();   // labels already on a radar: a new one that would cover one moves down
function place(ov,x,y,w,h){let L=PLACED.get(ov);if(!L){L=[];PLACED.set(ov,L)}
  for(let k=0;k<6&&L.some(b=>Math.abs(b.x-x)<(b.w+w)/2+2&&Math.abs(b.y-y)<(b.h+h)/2);k++)y+=h+2;L.push({x,y,w,h});return y}
// labels never cover each other: every icon is an obstacle, every label waits in a queue and is placed at the end of
// the drawing, right / left / above / below its icon, where it covers nothing (the most important ones first)
function obstacle(ov,x,y,w,h){let L=PLACED.get(ov);if(!L){L=[];PLACED.set(ov,L)}L.push({x,y,w,h})}
const LQ=new WeakMap(),FSZ={rbt:13,rtt:12,pbt:12,kwt:12,mkt:13,ptt:13,c4t:11};
function qLabel(ov,x,y,r,text,cls,prio,style){let q=LQ.get(ov);if(!q){q=[];LQ.set(ov,q)}q.push({x,y,r,text,cls,prio:prio||0,style})}
function qTag(ov,x,y,r,text,color,prio){let q=LQ.get(ov);if(!q){q=[];LQ.set(ov,q)}q.push({x,y,r,text,color,tag:true,prio:prio||0})}   // a grenade's tag, placed like a label
function uiObstacles(ov){try{const svg=ov.ownerSVGElement,box=svg&&svg.closest(".radar-box"),m=box&&svg.getScreenCTM();if(!m)return;const inv=m.inverse();
  box.querySelectorAll(":scope>.btns,:scope>.caption").forEach(b=>{const r=b.getBoundingClientRect();if(!r.width||!r.height)return;
    const a=new DOMPoint(r.left,r.top).matrixTransform(inv),c=new DOMPoint(r.right,r.bottom).matrixTransform(inv);obstacle(ov,(a.x+c.x)/2,(a.y+c.y)/2,Math.abs(c.x-a.x),Math.abs(c.y-a.y))})}catch(e){}}
function flushLabels(ov){const q=(LQ.get(ov)||[]).sort((a,b)=>b.prio-a.prio);LQ.delete(ov);uiObstacles(ov);let L=PLACED.get(ov);if(!L){L=[];PLACED.set(ov,L)}
  const hit=b=>L.some(o=>Math.abs(o.x-b.x)<(o.w+b.w)/2+1&&Math.abs(o.y-b.y)<(o.h+b.h)/2+1);
  q.forEach(l=>{const fs=l.tag?12:FSZ[String(l.cls).split(" ")[0]]||12,w=l.tag?6.6*l.text.length+18:l.text.length*fs*.62+4,h=l.tag?20:fs+3,r=l.r||8;
    const C=l.tag?[[l.x,l.y+r+h/2+2],[l.x,l.y-r-h/2-2],[l.x+r+w/2+2,l.y],[l.x-r-w/2-2,l.y],[l.x,l.y+r+1.5*h+4],[l.x,l.y-r-1.5*h-4],[l.x+w/2,l.y+r+h/2+2],[l.x-w/2,l.y+r+h/2+2],[l.x+w/2,l.y-r-h/2-2],[l.x-w/2,l.y-r-h/2-2],[l.x+r+w/2+2,l.y+h+2],[l.x-r-w/2-2,l.y+h+2],[l.x+r+w/2+2,l.y-h-2],[l.x-r-w/2-2,l.y-h-2]]:[[l.x+r+w/2+2,l.y],[l.x-r-w/2-2,l.y],[l.x,l.y-r-h/2-2],[l.x,l.y+r+h/2+2],[l.x+r+w/2+2,l.y-h-1],[l.x+r+w/2+2,l.y+h+1],[l.x-r-w/2-2,l.y-h-1],[l.x-r-w/2-2,l.y+h+1],[l.x,l.y-r-1.5*h-4],[l.x,l.y+r+1.5*h+4],[l.x+r+w/2+2,l.y-2*h-2],[l.x-r-w/2-2,l.y-2*h-2],[l.x+r+w/2+2,l.y+2*h+2],[l.x-r-w/2-2,l.y+2*h+2],[l.x,l.y-r-2.5*h-6],[l.x,l.y+r+2.5*h+6]];
    // no free place: the one that covers the least
    const area=(cx,cy)=>L.reduce((s_,o)=>s_+Math.max(0,Math.min(o.x+o.w/2,cx+w/2)-Math.max(o.x-o.w/2,cx-w/2))*Math.max(0,Math.min(o.y+o.h/2,cy+h/2)-Math.max(o.y-o.h/2,cy-h/2)),0);
    const c=C.find(([cx,cy])=>!hit({x:cx,y:cy,w,h}))||C.reduce((b_,q)=>area(q[0],q[1])<area(b_[0],b_[1])?q:b_,C[0]);L.push({x:c[0],y:c[1],w,h});
    if(l.tag){const gg=el("g",{class:"rt nd"},ov);el("rect",{x:c[0]-w/2,y:c[1]-10,width:w,height:20,rx:3,style:"fill:#0b0f14;fill-opacity:.88;stroke:#ffffff33;stroke-width:1"},gg);
      el("rect",{x:c[0]-w/2,y:c[1]-10,width:4,height:20,rx:1.5,style:`fill:${l.color}`},gg);el("text",{x:c[0]+2,y:c[1]+4,"text-anchor":"middle",class:"rtt"},gg).textContent=l.text;return}
    const t=el("text",{x:c[0],y:c[1]+fs*.36,"text-anchor":"middle",class:l.cls},ov);if(l.style)t.setAttribute("style",l.style);t.textContent=l.text})}
// pill: entrances and sites (rounded, filled with the site's color)
function rbadge(ov,x,y,text,fill,cls){const w=7.2*text.length+14;y=place(ov,x,y,w,22);const gg=el("g",{class:"rb"+(cls?" "+cls:"")},ov);
  el("rect",{x:x-w/2,y:y-11,width:w,height:22,rx:11,style:`fill:${fill};stroke:#0b0f14;stroke-width:1.5`},gg);
  el("text",{x,y:y+4.5,"text-anchor":"middle",class:"rbt"},gg).textContent=text;return gg}
// tag: grenades and rotations (square, dark, a color bar on the left)
function rtag(ov,x,y,text,color,cls){const w=6.6*text.length+18;y=place(ov,x,y,w,20);const gg=el("g",{class:"rt "+(cls||"")},ov);
  el("rect",{x:x-w/2,y:y-10,width:w,height:20,rx:3,style:"fill:#0b0f14;fill-opacity:.88;stroke:#ffffff33;stroke-width:1"},gg);
  el("rect",{x:x-w/2,y:y-10,width:4,height:20,rx:1.5,style:`fill:${color}`},gg);
  el("text",{x:x+2,y:y+4,"text-anchor":"middle",class:"rtt"},gg).textContent=text;return gg}
function starPath(x,y,R,r,n){let d="";for(let i=0;i<2*n;i++){const a=-Math.PI/2+i*Math.PI/n,q=i%2?r:R;d+=(i?"L":"M")+(x+q*Math.cos(a)).toFixed(1)+" "+(y+q*Math.sin(a)).toFixed(1)}return d+"Z"}
// gold star with the number of multi-kill rounds (your spots)
function mkStar(ov,x,y,s){const g=el("g",{class:"mkstar"},ov);
  el("path",{d:starPath(x,y,11,4.6,5),style:"fill:#ffd24a;stroke:#5a4100;stroke-width:1.4"},g);
  el("text",{x:x+14,y:y+4.5,class:"mkt"},g).textContent=`×${s.multi2}${s.best>=3?` · ${s.best}K`:""}`;
  return tip(g,`${s.name}: ${s.multi2} round${s.multi2>1?"s":""} with 2+ kills from here (best: ${s.best} kills)`)}
// the grenade's own icon where it lands
function nadeIcon(ov,type,x,y,title){const g=el("g",{class:"nicon"},ov);
  if(type==="smoke"){el("circle",{cx:x,cy:y,r:17,style:"fill:#c9d1d9;fill-opacity:.5;stroke:#eef2f6;stroke-width:2;stroke-dasharray:4 3"},g);
    [[-6,-2,7],[5,-4,8],[0,5,7]].forEach(([dx,dy,r])=>el("circle",{cx:x+dx,cy:y+dy,r,style:"fill:#e9eef3;fill-opacity:.85"},g))}
  else if(type==="molotov")el("path",{d:`M${x} ${y-15}C${x+11} ${y-3} ${x+9} ${y+10} ${x} ${y+10}C${x-9} ${y+10} ${x-11} ${y-3} ${x-3} ${y-8}C${x-2} ${y-2} ${x+2} ${y-3} ${x} ${y-15}Z`,style:"fill:#ff7a1a;stroke:#4a1600;stroke-width:1.6"},g);
  else if(type==="flash")el("path",{d:starPath(x,y,15,6,8),style:"fill:#fff3a0;stroke:#7a6a00;stroke-width:1.4"},g);
  else{el("circle",{cx:x,cy:y,r:12,style:"fill:#6abf69;stroke:#0b0f14;stroke-width:1.6"},g);el("text",{x,y:y+4,"text-anchor":"middle",class:"het"},g).textContent="HE"}
  return tip(g,title)}
// dotted arc from where you throw to where it lands
function nadeArc(ov,x1,y1,x2,y2,type){const dx=x2-x1,dy=y2-y1,d=Math.hypot(dx,dy)||1,cx=(x1+x2)/2-dy/d*d*0.18,cy=(y1+y2)/2+dx/d*d*0.18;
  el("path",{d:`M${x1} ${y1}Q${cx} ${cy} ${x2} ${y2}`,style:`fill:none;stroke:var(--${type});stroke-width:2.6;stroke-dasharray:1.5 5;stroke-linecap:round`},ov);
  el("circle",{cx:x1,cy:y1,r:4.5,style:`fill:#fff;stroke:var(--${type});stroke-width:2.2`},ov)}
// a wedge from an entrance toward its site: wide where the Ts come from, pointed at the site
function laneWedge(gl,x1,y1,x2,y2,w,col){const d=Math.hypot(x2-x1,y2-y1)||1,ux=(x2-x1)/d,uy=(y2-y1)/d,ex=x2-ux*36,ey=y2-uy*36,h=w/2;
  el("path",{d:`M${x1-uy*h} ${y1+ux*h}L${ex-uy*3} ${ey+ux*3}L${ex+ux*12} ${ey+uy*12}L${ex+uy*3} ${ey-ux*3}L${x1+uy*h} ${y1-ux*h}Z`,style:`fill:${col};fill-opacity:.32;stroke:${col};stroke-width:1.6;stroke-opacity:.9`},gl)}
// a route: dark casing, colored core, chevrons showing the way
function rotPath(lay,pts,col,main,level){let seg=[];const segs=[];
  pts.forEach(q=>{if(!level||!q[2]||q[2]===level)seg.push(q);else{if(seg.length>1)segs.push(seg);seg=[]}});if(seg.length>1)segs.push(seg);
  segs.forEach(sg=>{const s=sg.map(q=>q[0]+","+q[1]).join(" ");
    el("polyline",{points:s,style:"fill:none;stroke:#0b0f14;stroke-width:5.5;stroke-opacity:.7;stroke-linejoin:round;stroke-linecap:round"},lay);
    el("polyline",{points:s,style:`fill:none;stroke:${col};stroke-width:${main?2.8:2};stroke-linejoin:round;stroke-linecap:round${main?"":";stroke-dasharray:7 5"}`},lay);
    let acc=0;for(let i=0;i<sg.length-1;i++){const a=sg[i],b=sg[i+1],d=Math.hypot(b[0]-a[0],b[1]-a[1]);acc+=d;if(acc<110||d<4)continue;acc=0;
      const ux=(b[0]-a[0])/d,uy=(b[1]-a[1])/d,mx=b[0],my=b[1];
      el("path",{d:`M${mx-ux*5-uy*5} ${my-uy*5+ux*5}L${mx+ux*3} ${my+uy*3}L${mx-ux*5+uy*5} ${my-uy*5-ux*5}`,style:`fill:none;stroke:${col};stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round`},lay)}});
  return segs}
function routeLine(ov,pts,col,main){const s=pts.map(p=>p.join(",")).join(" ");
  el("polyline",{points:s,style:`fill:none;stroke:#0b0f14;stroke-width:${main?10:7};stroke-opacity:.75;stroke-linejoin:round;stroke-linecap:round`},ov);
  el("polyline",{points:s,style:`fill:none;stroke:${col};stroke-width:${main?5.5:3.5};stroke-linejoin:round;stroke-linecap:round${main?"":";stroke-dasharray:9 6"}`},ov);
  if(main)for(let i=0;i<pts.length-1;i++){const [a,b]=[pts[i],pts[i+1]],mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2,d=Math.hypot(b[0]-a[0],b[1]-a[1]);if(d<40)continue;
    const ux=(b[0]-a[0])/d,uy=(b[1]-a[1])/d;el("path",{d:`M${mx-ux*5-uy*6} ${my-uy*5+ux*6}L${mx+ux*5} ${my+uy*5}L${mx-ux*5+uy*6} ${my-uy*5-ux*6}`,style:"fill:none;stroke:#fff;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round"},ov)}}
// your spots: a thin ring, colored by the duels you win there
function spotDisc(ov,s,side){const r=8+Math.sqrt(s.presence||1)*2.6,col=s.win==null?"#8a96a3":s.win>=58?"var(--good)":s.win<=42?"var(--bad)":"#c9a227";
  tip(el("circle",{cx:s.px[0],cy:s.px[1],r,style:`fill:none;stroke:${col};stroke-width:2.5;stroke-opacity:.7`},ov),
    `${s.name}: ${Math.round(s.presence)}% of your time as ${side}, you ${s.k}-${s.d}${s.win!=null?` (${s.win}% of duels won, others ${s.others_win??"—"}%)`:""}`);
  return r}
const SW={lane:`<svg width="26" height="12" aria-hidden="true"><path d="M1 2L20 5L25 6L20 7L1 10Z" style="fill:var(--siteA);fill-opacity:.4;stroke:var(--siteA)"/></svg>`,
  spot:`<svg width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="6" style="fill:none;stroke:var(--good);stroke-width:3"/></svg>`,
  star:`<svg width="16" height="16" aria-hidden="true"><path d="${starPath(8,8,7,3,5)}" style="fill:#ffd24a;stroke:#5a4100"/></svg>`,
  wstar:`<svg width="16" height="16" aria-hidden="true"><path d="${starPath(8,8,6,2.6,5)}" style="fill:#f2f5f8;stroke:#0b0f14"/></svg>`,
  key:`<svg width="18" height="18" aria-hidden="true"><path d="M9 1L16 5V13L9 17L2 13V5Z" style="fill:var(--good);stroke:#0b0f14"/></svg>`,
  eco:`<svg width="18" height="16" aria-hidden="true"><path d="M9 1L17 15H1Z" style="fill:var(--warn);stroke:#0b0f14"/></svg>`,
  ctpos:`<svg width="16" height="16" aria-hidden="true"><circle cx="8" cy="8" r="6" style="fill:var(--ct);fill-opacity:.32;stroke:var(--ct);stroke-width:2"/></svg>`,
  push:`<svg width="26" height="12" aria-hidden="true"><circle cx="4" cy="6" r="3" style="fill:#fff;stroke:#0b0f14"/><path d="M6 6H21" style="stroke:var(--ct);stroke-width:2.5"/><path d="M19 2L25 6L19 10Z" style="fill:var(--ct)"/></svg>`,
  danger:`<svg width="18" height="18" aria-hidden="true"><circle cx="9" cy="9" r="5" style="fill:none;stroke:var(--bad);stroke-width:2"/><path d="M1 9H4M14 9H17M9 1V4M9 14V17" style="stroke:var(--bad);stroke-width:2"/></svg>`,
  tpath:`<svg width="26" height="12" aria-hidden="true"><path d="M1 6H25" style="stroke:#0b0f14;stroke-width:5"/><path d="M1 6H25" style="stroke:#ffb347;stroke-width:2.5"/></svg>`,
  shield:`<svg width="16" height="18" aria-hidden="true"><path d="M8 1L15 4L14 10Q12 15 8 17Q4 15 2 10L1 4Z" style="fill:var(--good);stroke:#0b0f14"/></svg>`,
  nade:`<svg width="26" height="14" aria-hidden="true"><path d="M2 12Q13 0 22 8" style="fill:none;stroke:var(--smoke);stroke-width:2.4;stroke-dasharray:1.5 4;stroke-linecap:round"/></svg>`,
  route:`<svg width="26" height="12" aria-hidden="true"><path d="M1 6H25" style="stroke:#0b0f14;stroke-width:8"/><path d="M1 6H25" style="stroke:var(--good);stroke-width:4"/></svg>`,
  c4:`<svg width="20" height="14" aria-hidden="true"><rect x="1" y="1" width="18" height="12" rx="2" style="fill:var(--bad)"/></svg>`};
// T side: the multi-kill stars on top of your zones
function spotStars(box,spots,level){const ov=$("g",box);PLACED.set(ov,[]);(spots||[]).filter(s=>s.multi2&&s.px&&(!s.level||!level||s.level===level)).forEach(s=>mkStar(ov,s.px[0]-6,s.px[1]-24,s))}
const RLAYERS=[["key","Key rounds"],["post","After the plant"],["paths","T paths"],["ctpos","CT spots"],["danger","CT kill angles"],["strong","Strong spots"],["multi","Multi-kills"],["nades","Grenades"],["spots","Your spots"],["rot","Rotation"]];
function liveLayers(){let L=store("rlayers6");if(!Array.isArray(L))L=RLAYERS.map(x=>x[0]);return L}
// the moment the radar is about: now in a live round, the setup during freeze time, none when you browse
function radarT(g,o){return !o.following||!g?null:g.round_phase==="live"?(g.elapsed||0):g.round_phase==="freezetime"?0:null}
// the spots that fit this moment (from a bit before now to a bit after), or the nearest ones in time
function nearT(list,t,before,after,min){if(t==null)return list;const w=list.filter(x=>x.t_med==null||(x.t_med>=t-before&&x.t_med<=t+after));
  return w.length>=min?w:list.slice().sort((a,b)=>Math.abs((a.t_med??t)-t)-Math.abs((b.t_med??t)-t)).slice(0,min)}
// a T path: a thin line with a dark casing, chevrons for the way, the play's number where it ends; on a map with
// levels, only the parts on the level shown; the first one also tells when to be at the site's door
function tPath(lay,top,pts,col,ranks,level,first,pct,rot,tm){const on=q=>!q[2]||!level||q[2]===level;let seg=[];const segs=[];
  pts.forEach(q=>{if(on(q))seg.push(q);else{if(seg.length>1)segs.push(seg);seg=[]}});if(seg.length>1)segs.push(seg);
  segs.forEach(sg=>{const s=sg.map(q=>q[0]+","+q[1]).join(" ");
    el("polyline",{points:s,style:"fill:none;stroke:#0b0f14;stroke-width:5.5;stroke-opacity:.7;stroke-linejoin:round;stroke-linecap:round"},lay);
    el("polyline",{points:s,style:`fill:none;stroke:${col};stroke-width:2.6;stroke-linejoin:round;stroke-linecap:round`},lay);
    let acc=0;for(let i=0;i<sg.length-1;i++){const a=sg[i],b=sg[i+1],d=Math.hypot(b[0]-a[0],b[1]-a[1]);acc+=d;if(acc<110||d<4)continue;acc=0;   // a chevron every ~110 px
      const ux=(b[0]-a[0])/d,uy=(b[1]-a[1])/d,mx=b[0],my=b[1];
      el("path",{d:`M${mx-ux*5-uy*5} ${my-uy*5+ux*5}L${mx+ux*3} ${my+uy*3}L${mx-ux*5+uy*5} ${my-uy*5-ux*5}`,style:`fill:none;stroke:${col};stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round`},lay)}});
  const end=pts[pts.length-1];if(on(end)){const t=ranks.join("·")+(rot?" ↻":"")+(pct!=null?` · ${pct}% won`:""),w=7.4*t.length+12,y=place(top,end[0],end[1]-21,w,18),gg=el("g",{},top);
    el("rect",{x:end[0]-w/2,y:y-9,width:w,height:18,rx:9,style:`fill:${col};stroke:#0b0f14;stroke-width:1.5`},gg);
    el("text",{x:end[0],y:y+4,"text-anchor":"middle",class:"pbt"},gg).textContent=t;
    const os_=onSite(tm,end);if(os_)qLabel(top,end[0],y,w/2,os_,"ptt",first?5:4)}   // when to be on the site to win the most (game clock)
  return segs.length}
// a strong spot: a green shield with a tick, more opaque where more duels are won
function strongMark(ov,s){const [x,y]=s.px;obstacle(ov,x,y,22,28);const g=el("g",{class:"strong",style:`opacity:${s.win>=75?1:s.win>=68?.85:.7}`},ov);
  el("path",{d:`M${x} ${y-13}L${x+11} ${y-8}L${x+10} ${y+2}Q${x+8} ${y+10} ${x} ${y+14}Q${x-8} ${y+10} ${x-10} ${y+2}L${x-11} ${y-8}Z`,style:"fill:var(--good);stroke:#0b0f14;stroke-width:1.8"},g);
  el("path",{d:`M${x-5} ${y}L${x-1} ${y+4}L${x+5} ${y-4}`,style:"fill:none;stroke:#0b0f14;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round"},g);
  return tip(g,`${s.zone}: players win ${s.win}% of their duels from here (${s.k} kills, ${s.d} deaths)${s.t_med!=null?`, around ${clock(s.t_med)}`:""}`)}
// a multi-kill spot: a gold star for yours (with your best round there: 3K, 4K), a smaller white one for the other
// players (with how many rounds)
function mkMark(ov,s,mine,dim){const [x,y]=s.px,R=mine?13:9,g=el("g",{class:"mkstar",style:dim?"opacity:.45":""},ov);
  el("path",{d:starPath(x,y,R,R*.42,5),style:mine?"fill:#ffd24a;stroke:#5a4100;stroke-width:1.5":"fill:#f2f5f8;stroke:#0b0f14;stroke-width:1.3"},g);
  const t=mine?(s.best>=2?`${s.best}K`:""):(s.n>=2?`×${s.n}`:"");
  obstacle(ov,x,y,2*R,2*R);if(t)qLabel(ov,x,y,R,t,"mkt"+(mine?"":" o"),mine?2:1);
  return tip(g,mine?`${s.zone}: you got ${s.best} kills from here in one round${s.n>1?` (${s.n} rounds)`:""}`:`${s.zone}: ${s.n} rounds where a player got 2+ kills from here (best ${s.best})`)}
// the layers under one control (05/10): with all of them on, the map shows what fits the moment of the round (your
// paths and their spots during the buy and the first 45 s, the key rounds' spots, the post-plant once the bomb is
// down, the kill angles of the moment); open it between two rounds to hide some
let RL_OPEN=false;
function layerBtns(){const L=liveLayers(),H=typeof isHostage==="function"&&isHostage(S.map),HN={paths:"Your ways",ctpos:"T spots",danger:"T kill angles"};   // hostage maps: the CTs attack
  const ks=RLAYERS.filter(([k])=>!H||!["key","post"].includes(k)),all=ks.every(([k])=>L.includes(k));
  return `<details class="rlayers"${RL_OPEN?" open":""}><summary title="The map shows what fits the moment of the round by itself">Layers · ${all?"auto":`${ks.filter(([k])=>L.includes(k)).length} of ${ks.length}`}</summary>
   <div class="btns" role="group" aria-label="What the radar shows">${ks.map(([k,t])=>`<button type="button" data-rlayer="${k}" aria-pressed="${L.includes(k)}">${H&&HN[k]||t}</button>`).join("")}${all?"":`<button type="button" data-rlayer-auto>Auto: all, by moment</button>`}</div></details>`}

function liveRadar(box,p,map,level,g,o){
  const dead=!!(o.following&&g&&typeof deadAgo==="function"&&deadAgo(g)!=null);   // dead (05/10): the enemies' layers stay, your own go
  const PL=p.advice.plan||{},TS=PL.tside,M=TS&&TS.maps&&TS.maps[map],GEO=M&&M.geo,ct=o.side==="CT",HMAP=isHostage(map),att=HMAP?ct:!ct,on=k=>o.layers.includes(k)&&!(dead&&["paths","key","spots","multi"].includes(k))&&(att?!["strong","multi","spots"].includes(k):!["paths","ctpos","danger"].includes(k))&&!(ct&&!HMAP&&["multi","spots"].includes(k));   // the attack (T, or CT on a hostage map): the enemies, not your own spots; CT: no static layer (06/10)
  const svg=$("svg",box),img=$("image",svg),ov=$("g",svg),cap=$(".caption",box);
  img.setAttribute("href",D.radars[`${map}:${level}`]||"");svg.setAttribute("viewBox",(D.viewboxes[map]||[0,0,1024,1024]).join(" "));ov.replaceChildren();PLACED.set(ov,[]);
  const here=x=>x&&x.px&&(!x.level||!level||x.level===level),legend=[];
  const live=o.following&&g&&g.round_phase==="live",planted=live&&g.bomb==="planted",site=o.site,t=radarT(g,o);
  const layer=n=>el("g",{class:"ly-"+n},ov);   // one group per layer, drawn in this order
  const Lspots=layer("spots"),Lstrong=layer("strong"),Lrot=layer("rot"),Lnades=layer("nades"),Ltop=layer("top");
  // your spots: thin rings
  const SP=((PL.spots||{})[map]||{})[o.side]||[];
  if(on("spots")&&SP.length){SP.filter(here).forEach(s=>spotDisc(Lspots,s,o.side));
    legend.push(`<span>${SW.spot}your spots (green = you win your duels there, red = you lose them)</span>`)}
  // strong spots: where the players of your matches win most of their duels, at this moment of the round
  const CM=typeof crossMap==="function"?crossMap(p,map):null,BS=(((CM||{}).sides||{})[o.side]||{}).best_spots||[];
  if(on("strong")&&BS.length){const pick=nearT(BS.filter(here),t,15,25,2).sort((a,b)=>b.win*Math.sqrt(b.k)-a.win*Math.sqrt(a.k)).slice(0,planted?3:5);
    if(ct)pick.splice(3);   // CT: three at most (06/10: less static noise)
    pick.forEach(s=>strongMark(Lstrong,s));if(pick.length)legend.push(`<span>${SW.shield}strong spot${t!=null?" now":""}: players win most of their duels from there</span>`)}
  // multi-kill spots: yours (exact), and the other players' on the spots you play
  if(on("multi")){const mine=(((PL.multi||{})[map]||{})[o.side]||[]).filter(here),zones=new Set(SP.map(s=>s.name));
    const base=((((M||{}).evidence||{}).multi||{})[o.side]||[]).filter(s=>here(s)&&zones.has(s.zone)&&!mine.some(m=>Math.hypot(m.px[0]-s.px[0],m.px[1]-s.px[1])<24));
    const others=typeof keySit==="function"&&o.following&&g&&keySit(p,g)?[]:nearT(base,t,15,30,2).slice(0,4);
    others.forEach(s=>mkMark(Ltop,s,false));mine.forEach(s=>mkMark(Ltop,s,true,t!=null&&s.t_med!=null&&Math.abs(s.t_med-t)>35));
    if(mine.length||others.length)legend.push(`<span>${SW.star}your multi-kills (2+ kills from that spot in a round)</span>${others.length?`<span>${SW.wstar}other players' multi-kills on your spots</span>`:""}`)}
  // key rounds (pistol, eco or force against a full buy): the spots that pay for your weapon, a plant that wins more
  if(on("key")&&o.following&&g&&!planted&&(g.round_phase==="freezetime"||(live&&(g.elapsed||0)<45))&&typeof keyRadar==="function"){keyRadar(p,g,map,level,Lstrong,Ltop,legend,here);antiEcoRadar(p,g,map,level,Ltop,legend,here)}
  if(on("post")&&planted&&site&&typeof postplantRadar==="function")postplantRadar(p,g,map,level,Ltop,legend,here,site,ct);
  // T side, before the hit: the way from the spawn of the plays that win most (numbered like the side panel's lines)
  const FN=o.following&&g?focusN(g):0;   // the path you pressed: the only one drawn
  const TDR=!HMAP&&att&&o.following&&g&&typeof tdirsOf==="function"&&tdirsOf(map)?dirRank(p,g,tdirsOf(map)):null;   // 06/10: the ways in (A via Ramp...)
  const planOn=!!(TDR&&(TDR.sel.dir||TDR.sel.tempo));   // a way or a tempo said: its ways stay until the plant (09/10)
  if(TDR&&on("paths")&&!planted&&(g.round_phase==="freezetime"||(live&&((g.elapsed||0)<45||planOn)))&&TDR.rows.length){dirPaths(Lrot,Ltop,TDR,level);
    if(!dead&&dirNades(Lnades,Ltop,TDR,level,tdirsOf(map),g,p))legend.push(`<span>the way's stuff: thrown from the white dot, lands on the icon</span>`);
    legend.push(`<span>${SW.tpath}the way in from the spawn, % = rounds won by it this round (your buy and theirs${TDR.sel.tempo?`, ${TEMPO_EN[TDR.sel.tempo].toLowerCase()}`:""}); numpad 1-2-3 = A / mid / B, 4-5-6 = rush / slow / map control, minus drops them</span>`)}
  const TDx=!HMAP&&o.following&&g&&typeof tdirsOf==="function"?tdirsOf(map):null;if(TDx)pingMark(Ltop,g,TDR,level,TDx);   // A, B or mid pressed or said: a ping
  if(TDx&&typeof wilyRadar==="function")wilyRadar(p,g,level,Lnades,Ltop,legend);   // what you asked Wily, on the map
  else if(att&&on("paths")&&o.following&&g&&!planted&&(g.round_phase==="freezetime"||(live&&(g.elapsed||0)<45))){const W0=HMAP?hostageRank(p,g):winsRank(p,g),W=W0&&FN&&W0.rows.some(r=>r.rank===FN)?{...W0,rows:W0.rows.filter(r=>r.rank===FN)}:W0;
    if(W){const seen=new Map();W.rows.slice(0,3).forEach(r=>{if(!r.route)return;const k=r.route.zones.join(">");if(seen.has(k)){seen.get(k).push(r.rank);return}seen.set(k,[r.rank]);r._k=k});
      W.rows.slice(0,3).filter(r=>r._k).reverse().forEach(r=>tPath(Lrot,Ltop,r.route.pts,r.col,seen.get(r._k),level,r.rank===1,r.wr,r.rot,r.timing));   // the play's chance this round (a route alone is biased: only the ones who got there alive count)
      if(seen.size&&W.rows.some(r=>r.rot))legend.push(`<span>${SW.tpath}↻ ranked ahead of a better %: that one lost this half or was played too often, they read you too</span>`);
      if(seen.size&&HMAP)legend.push(`<span>${SW.tpath}your way out of the spawn toward the hostages, % won = the CTs' rounds won when one takes it, "there ~1:41": when they get to its end (game clock); numpad 1-2-3 = ${esc(W.rows.slice().sort((a,b)=>a.rank-b.rank).map(r=>r.name||r.rank).join(" / "))} (left to right from your spawn), 4-5-6 = rush / slow / map control: one line in the team chat; 7 / 9 = 1st / 2nd hostage taken (Wily only); minus drops them</span>`);
      else if(seen.size)legend.push(`<span>${SW.tpath}your way from the spawn, % won = rounds won by its play in this situation; "on site 1:31-1:21": be on the site between these times of the game clock, when this play wins the most rounds at equal numbers alive (a fast arrival in an easy round doesn't count for more; ~1:17: no moment wins more, the usual time); numpad 1-2-3 say the path in the team chat (${esc(RT_EN[W.rt]||W.rt)}${W.eb&&W.eb.full>=.5?" vs their full buy":W.eb&&W.eb.eco>=.5?" vs their eco":""}, ${RUN_EN[W.run]})</span>`)}}
  // T side: where the CTs stand when you get there, and the angles they kill from (! = a spot they kill a lot from for the
  // little time they spend there: the angle the Ts forget)
  // T, the first moments (buy time, then up to 1:10): CTs pushing past a neutral zone, for their buy this round: an
  // arrow from the neutral zone (where both sides arrive at the same time) to where the pushing CT gets
  let earlyDone=false;
  if(!ct&&on("ctpos")&&o.following&&g&&!planted&&(g.round_phase==="freezetime"||(live&&(g.elapsed||0)<45))&&typeof ctPush==="function"){const CP=ctPush(p,g);
    if(CP&&CP.gates.length){CP.gates.filter(x=>here({px:x.from,level:x.level})).forEach(x=>{const [x0,y0]=x.from,[x1,y1]=x.to,d=Math.hypot(x1-x0,y1-y0)||1,ux=(x1-x0)/d,uy=(y1-y0)/d;
        const hot=x.kill>=30,w=1.8+Math.min(2.4,x.share/6),gg=el("g",{style:(live&&(g.elapsed||0)>x.t+6)?"opacity:.35":""},Ltop),col=hot?"var(--bad)":"var(--ct)";
        el("line",{x1:x0,y1:y0,x2:x1-ux*7,y2:y1-uy*7,style:`stroke:#0b0f14;stroke-width:${w+3};stroke-opacity:.6;stroke-linecap:round`},gg);
        el("line",{x1:x0,y1:y0,x2:x1-ux*7,y2:y1-uy*7,style:`stroke:${col};stroke-width:${w};stroke-linecap:round`},gg);
        el("path",{d:`M${x1} ${y1}L${x1-ux*11-uy*6} ${y1-uy*11+ux*6}L${x1-ux*11+uy*6} ${y1-uy*11-ux*6}Z`,style:`fill:${col};stroke:#0b0f14;stroke-width:1`},gg);
        el("circle",{cx:x0,cy:y0,r:4.5,style:"fill:#fff;stroke:#0b0f14;stroke-width:1.5"},gg);obstacle(Ltop,x1,y1,16,16);
        qLabel(Ltop,x1,y1,9,clock(x.t),"kwt",3);
        tip(gg,`${x.gate||"Neutral zone"}: a CT pushes past it in ${Math.round(x.share)}% of rounds (${CP.label.toLowerCase()}), around ${clock(x.t)}; the pushing CT gets a kill ${x.kill}% of the time`)});
      legend.push(`<span>${SW.push}a CT pushing past a neutral zone (white dot: where both sides arrive at the same time), for their buy this round; the time is when, red: the push often gets a kill</span>`);earlyDone=true}}
  const FR=FN&&!HMAP?((winsRank(p,g)||{rows:[]}).rows.find(r=>r.rank===FN)||{}).route:null,nearF=s=>!FR||FR.pts.some(q=>Math.hypot(q[0]-s.px[0],q[1]-s.px[1])<90);   // focus: only the spots along your path
  // hostage maps, CT: where the Ts hold 20 to 40 s in, and the spots they kill CTs from (along the path you pressed)
  const HS=HMAP&&ct?((PL.hostage||{})[map]):null;
  if(HS&&o.following&&g&&(g.round_phase==="freezetime"||(live&&(g.elapsed||0)<60))){const FRh=FN?((hostageRank(p,g)||{rows:[]}).rows.find(r=>r.rank===FN)||{}).route:null,nr=s=>!FRh||FRh.pts.some(q=>Math.hypot(q[0]-s.px[0],q[1]-s.px[1])<90);
    if(on("ctpos")){const hs=(HS.holds||[]).filter(h=>here(h)&&nr(h)&&!/spawn/i.test(h.zone||"")).slice(0,6),mx=Math.max(...hs.map(h=>h.share),1);
      hs.forEach(h=>tip(el("circle",{cx:h.px[0],cy:h.px[1],r:7+9*h.share/mx,style:"fill:var(--t);fill-opacity:.32;stroke:var(--t);stroke-width:2;stroke-opacity:.8"},Lstrong),`${h.zone||"T spot"}: ${h.share}% of the Ts' time 20 to 40 s in`));
      if(hs.length)legend.push(`<span>${SW.ctpos}where the Ts hold 20 to 40 s in (bigger = more often)</span>`)}
    if(on("danger")){const ds=(HS.danger||[]).filter(h=>here(h)&&nr(h)).slice(0,5);
      ds.forEach(z=>{const gg=el("g",{},Ltop),r=8+Math.min(6,z.share/3);
        el("circle",{cx:z.px[0],cy:z.px[1],r,style:"fill:none;stroke:var(--bad);stroke-width:2.4"},gg);
        el("path",{d:`M${z.px[0]-r-4} ${z.px[1]}H${z.px[0]-r+4}M${z.px[0]+r-4} ${z.px[1]}H${z.px[0]+r+4}M${z.px[0]} ${z.px[1]-r-4}V${z.px[1]-r+4}M${z.px[0]} ${z.px[1]+r-4}V${z.px[1]+r+4}`,style:"stroke:var(--bad);stroke-width:2.4;stroke-linecap:round"},gg);
        tip(gg,`${z.zone||"T angle"}: ${z.kills} CTs killed from here in the first minute`)});
      if(ds.length)legend.push(`<span>${SW.danger}spots the Ts kill CTs from in the first minute</span>`)}}
  // hostage maps, a hostage taken (numpad 7 / 9, 10/10): the way back to the rescue (CT: from where you pressed) and
  // where the Ts cut it, with when on the game clock; both sides
  const HC=HMAP&&o.following&&g&&live&&typeof hostageCarry==="function"?hostageCarry(p,g):null;
  if(HC&&HC.rows.length){const col=ct?"var(--ct)":"var(--t)";
    HC.rows.forEach(s=>{tPathLabel(Lrot,Ltop,s.pts,col,level,`${s.to||"rescue"}${s.back!=null?` ~${clock(s.back)}`:` ~${Math.round(s.s)} s`}`);
      s.cut.forEach(c=>{const q=s.pts.find(q=>q[3]>=c.after)||s.pts[s.pts.length-1];if(!here({px:q,level:q[2]}))return;const gg=el("g",{},Ltop);
        el("circle",{cx:q[0],cy:q[1],r:10,style:"fill:none;stroke:var(--bad);stroke-width:2.6;stroke-dasharray:4 3"},gg);
        if(c.by!=null)qLabel(Ltop,q[0],q[1],10,clock(c.by),"kwt",3);
        tip(gg,`${c.zone}: ${c.share}% of the ways back from ${s.zone} cross it, ${Math.round(c.after)} s after the pick-up${c.by!=null?` (here ~${clock(c.by)})`:""}`)})});
    legend.push(ct?`<span>${SW.tpath}hostage ${HC.n} taken: your way back to the rescue from ${esc(HC.rows[0].zone)} (~${Math.round(HC.rows[0].s)} s carrying), dashed: where the Ts cut it and when you get there - smoke or clear it first</span>`
      :`<span>${SW.tpath}hostage ${HC.n} taken: their ways back to the rescue, dashed: where to cut them, the time is when the carrier gets there - be there before</span>`)}
  // hostage maps, T (the defense, 10/10: as the CT of a bomb map): the CTs' ways, numpad 1-2-3 the one you play against
  // (Wily only), and along it the spots the Ts kill CTs from in the first minute
  const HT=HMAP&&!ct&&!HC?((PL.hostage||{})[map]):null;
  if(HT&&o.following&&g&&(g.round_phase==="freezetime"||(live&&(g.elapsed||0)<60))){const f=g.focus&&g.focus.round===g.round?g.focus.n:0,W=hostageRank(p,g);
    if(W){const rows=W.rows.filter(r=>!f||r.rank===f),FRt=f&&rows[0]?rows[0].route:null,nr=s=>!FRt||FRt.pts.some(q=>Math.hypot(q[0]-s.px[0],q[1]-s.px[1])<90);
      rows.forEach(r=>tPathLabel(Lrot,Ltop,r.route.pts,"var(--ct)",level,`${r.rank} ${r.name||""} ~${clock(r.t_end)}`.trim()));
      const ds=(HT.danger||[]).filter(h=>here(h)&&nr(h)).slice(0,4);
      ds.forEach(h=>tip(el("circle",{cx:h.px[0],cy:h.px[1],r:8+Math.min(6,h.share/3),style:"fill:var(--t);fill-opacity:.3;stroke:var(--t);stroke-width:2.4"},Lstrong),`${h.zone||"T spot"}: ${h.kills} CTs killed from here in the first minute`));
      legend.push(`<span>${SW.tpath}the CTs' ways toward the hostages (numpad 1-2-3: the one you play against, left to right from their spawn; the time: when they get to its end)${ds.length?", filled: the spots the Ts kill CTs from in the first minute":""}; 7 / 9 = 1st / 2nd hostage taken</span>`)}}
  const CS=!ct&&M&&M.ct_spots;
  if(CS&&!earlyDone&&(on("ctpos")||on("danger"))){const tt=t==null?25:Math.max(t+15,20),wn=tt<20?"early":tt<40?"setup":tt<70?"hit":"late",W_=CS[wn]||CS.setup;
    if(W_&&on("ctpos")){const hs=W_.hold.filter(h=>here(h)&&nearF(h)&&h.zone!=="CT Spawn").slice(0,6),mx=Math.max(...hs.map(h=>h.share),1);
      hs.forEach(h=>tip(el("circle",{cx:h.px[0],cy:h.px[1],r:7+9*h.share/mx,style:"fill:var(--ct);fill-opacity:.32;stroke:var(--ct);stroke-width:2;stroke-opacity:.8"},Lstrong),`${h.zone||"CT spot"}: ${h.share}% of the CTs' time at this moment`));
      if(hs.length)legend.push(`<span>${SW.ctpos}where the CTs stand when you get there (bigger = more often)</span>`)}
    if(W_&&on("danger")){const ds=W_.danger.filter(z=>here(z)&&nearF(z)).slice(0,5);
      ds.forEach(z=>{const gg=el("g",{},Ltop),r=8+Math.min(6,z.share/3);
        el("circle",{cx:z.px[0],cy:z.px[1],r,style:"fill:none;stroke:var(--bad);stroke-width:2.4"},gg);
        el("path",{d:`M${z.px[0]-r-4} ${z.px[1]}H${z.px[0]-r+4}M${z.px[0]+r-4} ${z.px[1]}H${z.px[0]+r+4}M${z.px[0]} ${z.px[1]-r-4}V${z.px[1]-r+4}M${z.px[0]} ${z.px[1]+r-4}V${z.px[1]+r+4}`,style:"stroke:var(--bad);stroke-width:2.4;stroke-linecap:round"},gg);
        if(z.sneaky){const L_=PLACED.get(Ltop)||[],free=(x,y)=>!L_.some(q=>Math.abs(q.x-x)<(q.w+14)/2+1&&Math.abs(q.y-y)<(q.h+14)/2+1);   // the "!" goes on a free corner, never on a label
          const spot=[[r+3,-r-3],[-r-3,-r-3],[r+3,r+3],[-r-3,r+3]].map(([dx,dy])=>[z.px[0]+dx,z.px[1]+dy]).find(([x,y])=>free(x,y));
          if(spot){const [bx,by]=spot;   // no free corner: the target stays, the "!" goes (a label is never covered)
            el("circle",{cx:bx,cy:by,r:7,style:"fill:var(--bad);stroke:#0b0f14;stroke-width:1.2"},gg);el("text",{x:bx,y:by+4,"text-anchor":"middle",class:"pbt",style:"fill:#fff"},gg).textContent="!";obstacle(Ltop,bx,by,14,14)}}
        tip(gg,`${z.zone||"CT angle"}: ${z.kills} T killed from here at this moment of the round${z.sneaky?" — they kill a lot from here for the little time they spend there: check it":""}`)});
      if(ds.length)legend.push(`<span>${SW.danger}angles the CTs kill from (! = often forgotten)</span>`)}}
  // the Ts' plays (CT): not drawn, the side panel shows the odds; they choose the grenades below
  let PLs=null;
  if(ct&&M&&M.plays&&!planted){const ev=o.following?evFor(g):{},r=o.read||(o.following?tsidePredict(TS,map,g,ev):{A:M.all.A,B:M.all.B,none:M.all.none,rush:Math.round(100*(M.rush_p??.2)),live:false});PLs=r&&tsidePlays(TS,map,o.following?g:{},ev,r)}
  const PLT=site&&M&&M.evidence&&M.evidence.plants&&M.evidence.plants[site];
  if(PLT&&planted){(PLT.spots||[]).filter(s=>!s.level||s.level===level).forEach(s=>{const gg=el("g",{},Ltop);obstacle(Ltop,s.px[0],s.px[1],26,18);
      el("rect",{x:s.px[0]-13,y:s.px[1]-9,width:26,height:18,rx:3,style:"fill:var(--bad);stroke:#fff;stroke-width:1.6"},gg);
      el("text",{x:s.px[0],y:s.px[1]+4,"text-anchor":"middle",class:"c4t"},gg).textContent="C4";tip(gg,`Plant spot: ${s.share}% of plants, Ts win ${s.t_win}% after it`)});
    legend.push(`<span>${SW.c4}where the bomb usually is</span>`)}
  // grenades: now (live), the plan (before the round), the retake ones (after the plant)
  const landed=[];   // grenades landing on the same spot: icons side by side
  const drawNade=(x,label,title)=>{if(!x.to_px||!x.from_px)return;if(!here({px:x.to_px,level:x.land_level||x.level})&&!here({px:x.from_px,level:x.level}))return;
    const k=landed.filter(q=>Math.hypot(q[0]-x.to_px[0],q[1]-x.to_px[1])<18).length;landed.push(x.to_px);
    const tx=x.to_px[0]+k*34,ty=x.to_px[1];
    nadeArc(Lnades,x.from_px[0],x.from_px[1],tx,ty,x.type);obstacle(Ltop,tx,ty,34,34);nadeIcon(Ltop,x.type,tx,ty,title);
    qTag(Ltop,tx,ty,17,label,`var(--${x.type})`,4)};
  if(on("nades")&&planted&&site&&o.following&&g&&typeof postPlan==="function"){const RX=ct&&M?rotFromDir(M,site,tdirSel(g).dir||mySite(g),map):null;
    if(stuffArcs(Lnades,Ltop,postPlan(p,g,ct?"CT":"T",site,RX&&RX.routes[0]?RX.routes[0].pts:null),level))legend.push(`<span>${SW.nade}${ct?"retake":"post-plant"} grenade you hold: from the white dot to its icon</span>`)}
  const CDs_=ct&&!planted&&o.following&&g&&typeof ctDirStuff==="function"?(tdirSel(g).dir||(typeof ctLikely==="function"?ctLikely(o.read||(M&&M.plays?tsidePredict(TS,map,g,evFor(g)):null)):null)):null;
  const CDP=CDs_?ctDirStuff(p,g,CDs_):null;   // a site said (numpad 1-3, 07/10), else the likely one (09/10): the card's stuff
  if(CDP&&on("nades")&&stuffArcs(Lnades,Ltop,CDP,level))legend.push(`<span>${SW.nade}your stuff for ${tdirSel(g).dir?"the site you said":"the likely site"}: from the white dot to its icon</span>`);
  if(ct&&!planted&&o.following&&g&&g.round_phase==="freezetime"&&tdirSel(g).dir&&typeof ctBoostPick==="function"){const b=ctBoostPick(p,g,tdirSel(g).dir);
    if(b&&b.px&&(!b.level||!level||b.level===level)){const gg=el("g",{},Ltop);el("circle",{cx:b.px[0],cy:b.px[1],r:11,style:"fill:var(--good);fill-opacity:.35;stroke:var(--good);stroke-width:2.4"},gg);
      el("text",{x:b.px[0],y:b.px[1]+5,"text-anchor":"middle",class:"pbt"},gg).textContent="⤴";obstacle(Ltop,b.px[0],b.px[1],24,24);
      tip(gg,`Boost ${b.place||""}: you trained it; ${b.kills} kills from up there in the base`);legend.push(`<span>⤴ a boost you trained</span>`)}}
  if(ct&&on("nades")&&PLs&&!CDP){const NN=nadesNow(PL,map,g,PLs,live);
    NN.forEach(x=>drawNade(x,`${nadeName(x.type,"CT")} → ${vShort(x.to||"?")}${/jump|run/i.test(x.how||"")?` · ${String(x.how).match(/jump|run/i)[0].toLowerCase()}`:""}${x.role==="anti_rush"?" · anti-rush":x.role==="block"?" · block":x.role==="flash"?" · as they push":""}`,
      `${nadeName(x.type,"CT")} ${x.from} → ${x.to}: ${x.why}. ${x.how||""}${x.click?`, ${x.click} click`:""}${x.yours?"":" (from a spot you don't play)"}`));
    o.nadesOut&&o.nadesOut(NN);
    if(NN.length)legend.push(`<span>${SW.nade}grenade worth throwing ${live?"now":"this round"}: from the white dot to its icon (cloud smoke, flame molotov, burst flash, HE)</span>`)}
  if(att&&on("nades")&&o.following&&typeof vNadePicks==="function"&&!(TDR&&TDR.rows.length)){const NP=vNadePicks(p,g).filter(x=>x.x);   // the ways' card draws its own stuff
    NP.forEach(n=>drawNade({...n.x,type:n.type},`${nadeName(n.type,"T")} → ${vShort(n.x.to||"?")}${n.x.pop?" · pop":""}`+(/jump|run/i.test(n.x.how||"")?` · ${String(n.x.how).match(/jump|run/i)[0].toLowerCase()}`:"")+({site:` · site ${FN||1}`,way:` · path ${FN||1}`}[n.x.way]||""),`${nadeName(n.type,"T")} ${n.x.from} → ${n.x.to}${n.x.how?`. ${n.x.how}`:""}`));
    NP.filter(n=>n.alt&&n.alt.to_px&&n.alt.from_px&&here({px:n.alt.to_px,level:n.alt.land_level||n.alt.level})).forEach(n=>{const a=n.alt,gg=el("g",{style:"opacity:.45"},Lnades);   // the other good throw, faint
      nadeArc(gg,a.from_px[0],a.from_px[1],a.to_px[0],a.to_px[1],n.type);tip(el("circle",{cx:a.to_px[0],cy:a.to_px[1],r:9,style:`fill:var(--${n.type});fill-opacity:.6;stroke:#0b0f14`},gg),`Other ${nadeName(n.type,"T")}: ${a.from} → ${a.to}`)});
    if(NP.length)legend.push(`<span>${SW.nade}your grenades for this moment: from the white dot to its icon</span>`)}
  // after the plant: the way to the site from where you are, and where the bomb usually is
  const you=o.following&&g&&g.pos&&GEO?worldPx(GEO,g.pos):null;
  // before the plant, when the read leans hard to one site (70%+): the rotation from the other one (you may be holding it)
  let rotSite=planted?site:null,rotFrom=null,said=false;
  // after the plant, a way said this round (numpad 1-2-3, 07/10: "tu me donnes les chemins de rota depuis le mid pour le B"): from there, both sides
  const SD=ct&&planted&&site&&o.following&&g&&typeof tdirSel==="function"?tdirSel(g).dir:null,SX=SD&&M?rotFromDir(M,site,SD,map):null;   // CT only (09/10: no use on T)
  if(SX){rotFrom=SX.from;said=true}
  if(ct&&!planted&&live&&o.following&&g&&(g.elapsed||0)>=15&&(g.elapsed||0)<=80&&M&&M.plays){const r_=tsidePredict(TS,map,g,evFor(g));
    if(r_&&Math.max(r_.A,r_.B)>=70){rotSite=r_.A>r_.B?"A":"B";rotFrom=`${rotSite==="A"?"B":"A"} Site`}}
  if((ct||said)&&on("rot")&&rotSite&&M&&GEO){const site=rotSite,from=rotFrom||(you?nearestZone(GEO,you.px,you.level):(SP[0]||{}).name),R=rotationFor(M,site,from,GEO);
    if(R&&R.routes){R.routes.slice().reverse().forEach((rt,j)=>{const i=R.routes.length-1-j,col=rt.died>=40?"var(--bad)":rt.died>=20?"#e0a526":"var(--good)";let m_;
        if(rt.pts&&rt.pts.length>2){   // the walk of the base (the corridors)
          const w=you&&i===0&&you.level===level&&!said?[[you.px[0],you.px[1],you.level],...rt.pts]:rt.pts,sg=rotPath(Lrot,w,col,i===0,level);if(!sg.length)return;
          const lng=sg.reduce((a,b)=>b.length>a.length?b:a);m_=lng[Math.floor(lng.length/2)]}
        else{const pts=[GEO.zones[R.from],...rt.route.map(z=>GEO.zones[z]),GEO.sites[site]].filter(Boolean).map(z=>z.px);
          if(you&&i===0&&!said)pts.unshift(you.px);if(pts.length<2)return;rotPath(Lrot,pts.map(q=>[q[0],q[1],null]),col,i===0,null);m_=pts[Math.floor(pts.length/2)]}
        tip(rtag(Ltop,m_[0],m_[1]-18,`⏱ ${rt.travel!=null?`${Math.round(rt.travel)} s · `:""}${rt.died}% die`,col,"rot"),`From ${R.from} to ${site}: ${rt.route.join(" > ")} (${rt.n} rotations in the base, ${rt.died}% died on the way)`)});
      legend.push(`<span>${SW.route}rotation to ${site} from ${esc(R.from)} (green = safe, red = players often die on the way; dashed = the other way)</span>`)}}
  cap.innerHTML=legend.join("");flushLabels(Ltop);   // the legend first: its box is known when the labels are placed
  if(you&&you.level===level){el("circle",{cx:you.px[0],cy:you.px[1],r:16,class:"you-pulse",style:"fill:none;stroke:#fff;stroke-width:2"},Ltop);
    el("circle",{cx:you.px[0],cy:you.px[1],r:7,style:"fill:#fff;stroke:#0b0f14;stroke-width:2"},Ltop)}
  return PLs}
