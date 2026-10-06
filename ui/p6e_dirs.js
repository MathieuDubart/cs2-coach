// ---------- T side: the ways in (06/10, the user in a bot match: "je veux juste avoir des directions maintenant, des
// directions et depuis où", "un bind pour A, un pour mid, un pour B, un pour rush, un pour slow, un pour contrôle map").
// Every hit of the base by the doorway the Ts stepped on the site through (tdirs.py, /api/tdirs/<map>): A via Ramp,
// Mid → A (Connector)... Numpad 1-2-3 pick the way (A, mid, B), 4-5-6 the tempo; the panel then shows that way's odds
// this round, when to be on the site (the small timeline: rounds won by the moment the Ts get on the site, for the two
// buys) and the grenades thrown on that way, by stack (several from one spot). No play names, no times on the map.
const TDIRS={},TDIR_ASK={};
const tdirsLoading=map=>!!(map&&D.local&&TDIR_ASK[map]&&TDIRS[map]===undefined);
function tdirsOf(map){if(!map||!D.local)return null;if(TDIRS[map]!==undefined)return TDIRS[map];
  if(!TDIR_ASK[map]){TDIR_ASK[map]=1;fetch("/api/tdirs/"+encodeURIComponent(map)).then(r=>r.json()).then(j=>{TDIRS[map]=j&&j.dirs&&j.dirs.length?j:null;if(S.view==="ingame"&&typeof renderIngame==="function")renderIngame()}).catch(()=>{TDIRS[map]=null})}
  return null}
// the plan of this round: numpad 1-2-3 (or said to Wily) the way, 4-5-6 the tempo; a key after the round's end counts for the next
function tdirSel(g){const t=g&&g.tdir;return t&&t.round===g.round?{dir:t.dir||null,tempo:t.tempo||null,src:t.src||null}:{dir:null,tempo:null,src:null}}
const TEMPO_EN={rush:"RUSH",slow:"SLOW",control:"MAP CONTROL"},TEMPO_SAY={rush:"Rush",slow:"Slow",control:"Map control, then"};
const DIR_EN={A:"A",MID:"MID",B:"B"};
const lgt=p=>Math.log(p/(1-p)),sgm=x=>1/(1+Math.exp(-x)),clp=p=>Math.min(.97,Math.max(.03,p));
const shrinkTo=(nw,p0,k)=>nw&&nw[0]?(nw[1]+k*p0)/(nw[0]+k):p0;   // few rounds: closer to the way's own mean
// your buy this round in the base's words (the T table: pistol, eco, force, full)
function myBuyKey(g){const wb=typeof wilyBuy==="function"?wilyBuy(g):null;if(wb)return wb;if(g.round===halfStart(g.round))return "pistol";const rt=advisedType(g);return rt==="anti-eco"?"full":rt||"full"}
// a way's chance this round: its rounds won, moved by the two buys (theirs: the likely ones, weighted) and by the tempo
function dirOdds(p,g,d,tempo){const p0=clp(d.win/100),tb=myBuyKey(g);let pE=p0;
  if(tb==="pistol")pE=shrinkTo((d.econ||{})["pistol|pistol"],p0,15);
  else{const eb=(typeof enemyBuyW==="function"?enemyBuyW(p,g):enemyBuy(p,g))||{},W=[["eco",eb.eco||0],["force",eb.force||0],["full",eb.full||0]].filter(x=>x[1]>0),s=W.reduce((a,x)=>a+x[1],0);
    if(s)pE=W.reduce((a,[b,w])=>a+w*shrinkTo((d.econ||{})[`${tb}|${b}`],p0,15),0)/s}
  const pT=tempo?shrinkTo((d.tempo||{})[tempo],p0,15):p0,sh=(lgt(clp(pE))-lgt(p0))+(lgt(clp(pT))-lgt(p0));
  return {wr:Math.round(100*sgm(lgt(p0)+sh)),shift:sh,n:tempo&&(d.tempo||{})[tempo]?d.tempo[tempo][0]:d.n}}
const DIR_C=["var(--t)","#58a6ff","#a371f7"];
// the ways to show: the picked way's own (A: every way onto A, mid ones included; MID: the ways through mid), else the
// three that win most this round (a small sample doesn't win: the lower bound of its rounds won)
function dirRank(p,g,TD){if(!TD)return null;const sel=tdirSel(g),lb=(w,n)=>{const z=1.28,ph=w/100;return n?(ph+z*z/(2*n)-z*Math.sqrt(ph*(1-ph)/n+z*z/(4*n*n)))/(1+z*z/n):0};
  let ds=TD.dirs.filter(d=>d.n>=(d.split?40:25));   // a split needs more rounds to be read
  if(sel.dir==="MID")ds=ds.filter(d=>d.mid);else if(sel.dir)ds=ds.filter(d=>d.site===sel.dir);
  const rows=ds.map(d=>{const o=dirOdds(p,g,d,sel.tempo);return {...d,wr:o.wr,shift:o.shift,ns:o.n,s:lb(o.wr,Math.min(o.n,d.n))}}).sort((a,b)=>b.s-a.s).slice(0,3);
  rows.forEach((r,i)=>{r.rank=i+1;r.col=DIR_C[i]});return {rows,sel,mid:TD.mid||null,gates:TD.gates||[]}}
// the small timeline (06/10: "si je rush B j'ai 75 %, si j'arrive à 1:10 70 %, à 0:45 30 %, à 0:10 50 %"): the way's
// rounds won by the moment the Ts get on the site (at equal numbers, like the plays' curves), moved like its odds this
// round; x is the game clock, the tempo picked is shaded, the dashed line is now; under it, the same read at 1:25,
// 1:10, 0:45 and 0:10 (and now), the best one in green
function vDirCurve(p,g,r){const T_=r.timing||{},TM=(g.round===halfStart(g.round)&&T_.pistol)||T_.other||T_.pistol;
  if(!TM||!TM.curve||TM.curve.length<3)return "";const L=RLEN(),W=300,H=46,x=t=>6+(W-12)*Math.min(1,Math.max(0,t/L)),sh=r.shift||0;
  const pts=TM.curve.map(([t,w])=>[t,Math.round(100*sgm(lgt(clp(w/100))+sh))]),lo=Math.min(...pts.map(q=>q[1]))-3,hi=Math.max(...pts.map(q=>q[1]))+3,y=w=>H-4-(H-8)*(w-lo)/Math.max(1,hi-lo);
  const sel=tdirSel(g),band=sel.tempo==="rush"?[0,30]:sel.tempo==="slow"?[60,L]:sel.tempo==="control"?[35,L]:null;
  const at=t=>{const q=pts.reduce((a,z)=>Math.abs(z[0]-t)<Math.abs(a[0]-t)?z:a,pts[0]);return Math.abs(q[0]-t)<=8?q[1]:null};
  const el=g.round_phase==="live"?(g.elapsed||0):null,ahead=el!=null?pts.filter(q=>q[0]>=el-3):pts,best=(ahead.length?ahead:pts).reduce((a,q)=>q[1]>a[1]?q:a,(ahead.length?ahead:pts)[0]);   // live: the best moment still to come
  const reads=[30,45,70,105].map(t=>[t,at(t)]).filter(q=>q[1]!=null&&(el==null||q[0]>=el-3));
  return `<div class="vhead">ON THE SITE AT · ROUNDS WON</div><svg class="vdcurve" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rounds won by when you get on the site">
    ${band?`<rect x="${x(band[0])}" y="0" width="${x(band[1])-x(band[0])}" height="${H}" class="band"/>`:""}<line x1="6" x2="${W-6}" y1="${H-1}" y2="${H-1}" class="base"/>
    <polyline points="${pts.map(q=>`${x(q[0]).toFixed(1)},${y(q[1]).toFixed(1)}`).join(" ")}" style="fill:none;stroke:${r.col};stroke-width:2.6;stroke-linejoin:round"/>
    <circle cx="${x(best[0])}" cy="${y(best[1])}" r="3.5" style="fill:var(--good)"/>${el!=null?`<line x1="${x(el)}" x2="${x(el)}" y1="0" y2="${H}" class="now"/>`:""}</svg>
    <div class="vdtimes">${el!=null&&at(el)!=null?`<span class="now">now <b>${at(el)}%</b></span>`:""}${reads.map(([t,w])=>`<span${Math.abs(t-best[0])<=8?' class="best"':""}>${clock(t)} <b>${w}%</b></span>`).join("")}${reads.some(([t])=>Math.abs(t-best[0])<=8)?"":`<span class="best">${clock(best[0])} <b>${best[1]}%</b></span>`}</div>`}
// the grenades of the way, by stack: thrown from one spot (the smoke, then the flash over it), the most used first
const NADE_L={smoke:"S",flash:"F",molotov:"M",he:"H"},HOW_S=h=>String(h||"").replace("standing still","").replace("jumpthrow","jump").replace("running","run").replace("walking","walk").replace("crouching","crouch").replace(/ \+ /g,"+");
function vDirUtil(p,g,r,max){const U=(r.util||[]).filter(u=>u.share>=3);if(!U.length)return "";const by=new Map();
  U.forEach(u=>{if(!by.has(u.stack))by.set(u.stack,[]);by.get(u.stack).push(u)});
  const stacks=[...by.values()].sort((a,b)=>b.length-a.length||b[0].n-a[0].n).slice(0,max||3);
  return `<div class="vhead">STUFF · ${esc(r.label)}</div><div class="vstacks">${stacks.map(st=>`<div class="vstack"><span class="from">${esc(vShort(st[0].from||"?"))}${st.length>1?` <small>×${st.length}</small>`:""}</span>${st.slice(0,3).sort((a,b)=>a.t_med-b.t_med).map(u=>`<span class="vnd"><i style="background:${NADE_C[u.type]||"#ccc"}">${NADE_L[u.type]||"?"}</i>${esc(vShort(u.to||"?"))}${HOW_S(u.how)?`<small>${esc(HOW_S(u.how))}</small>`:""}</span>`).join("")}</div>`).join("")}</div>`}
// the panel's way card: the plan picked (or Wily's pick), the ways with their odds this round, then the timeline and the stuff of the top one
function vDir(p,g,opt){if(g.side!=="T"||isHostage(g.map))return "";const more=opt&&opt.stuff;const TD=tdirsOf(g.map),R=dirRank(p,g,TD);if(!R||!R.rows.length)return "";
  const sel=R.sel,top=R.rows[0],dead=typeof deadAgo==="function"&&deadAgo(g)!=null;
  const head=sel.dir?`<b>${DIR_EN[sel.dir]}</b>${sel.tempo?` · ${TEMPO_EN[sel.tempo]}`:""}`:sel.tempo?`<b>${TEMPO_EN[sel.tempo]}</b> · pick a way: 1&nbsp;A · 2&nbsp;mid · 3&nbsp;B`:`<b>WILY'S PICK</b> · 1&nbsp;A · 2&nbsp;mid · 3&nbsp;B · 4&nbsp;rush · 5&nbsp;slow · 6&nbsp;control`;
  const mx=Math.max(...R.rows.map(r=>r.wr),1);
  return `<div class="vdir"><div class="vdir-h">${head}</div><div class="vrows">${R.rows.map((r,i)=>`<div class="vrow" style="--c:${r.col}${i?`;opacity:${[1,.82,.68][i]}`:""}"><span>${i===0?"★ ":""}${esc(r.label)}</span><i><u style="width:${Math.max(4,Math.round(100*r.wr/mx))}%"></u></i><b>${r.wr}%</b></div>`).join("")}</div>
    ${dead?"":vDirCurve(p,g,top)}${dead||!more&&g.round_phase==="live"&&(g.elapsed||0)>(sel.tempo==="slow"||sel.tempo==="control"?95:Math.max(50,(top.hit_med||35)+15))?"":vDirUtil(p,g,top,more||(g.round_phase==="live"?2:3))}</div>`}   // the stuff stays until the way's usual hit (a slow round: until 0:20)
// the team chat lines of numpad 1-6 for this round (T): the best way onto A, mid, B for the tempo picked, the tempo with the way picked
function dirTexts(p,g){const TD=tdirsOf(g.map);if(!TD||g.side!=="T"||isHostage(g.map))return null;const sel=tdirSel(g);
  const best=f=>{const ds=TD.dirs.filter(d=>d.n>=25&&f(d)).map(d=>({...d,wr:dirOdds(p,g,d,sel.tempo).wr})).sort((a,b)=>b.wr-a.wr);return ds[0]||null};
  const a=best(d=>d.site==="A"),b=best(d=>d.site==="B"),m=best(d=>d.mid),pre=sel.tempo&&sel.tempo!=="control"?TEMPO_SAY[sel.tempo]+" ":"";
  const pick=sel.dir==="A"?a:sel.dir==="B"?b:sel.dir==="MID"?m:null,say=d=>d?d.label.replace("Mid → ","mid to "):"";
  return {paths:[{rank:1,site:"A",text:a?pre+say(a):"A"},{rank:2,site:null,text:m?`${pre}Mid control - ${say(m)}`:"Mid"},{rank:3,site:"B",text:b?pre+say(b):"B"}],
    tempo:{rush:`Rush${pick?" "+say(pick):""}`,slow:`Slow${pick?" "+say(pick):", default"}`,ctrl:`Map control first${pick?", then "+say(pick):""}`}}}
// their money (06/10: "au début du round, l'argent des joueurs en face"): the game never sends it to a player. Rebuilt
// from the rounds of this half with CS2's rules ($800 at the pistol, $3,250 a win, $3,500 by the bomb, a loss $1,400
// + $500 a loss in a row up to $3,400, one step down after a win, the half starting one step up; $800 to the Ts when
// their bomb was planted) and what they likely bought each round (a full buy when they had it, a force after two
// losses, else a save): an estimate per player, a few hundred off at most when they saved weapons
function theirCash(g){if(!g||g.round==null||!g.side)return null;const H=(g.hist||{}).rounds||{},n=g.round,hs=halfStart(n),ot=hs>24;
  let cash=ot?12500:800,lc=ot?1:1;if(n===hs)return {cash,buy:ot?"full":"pistol"};
  for(let r=hs;r<n;r++){const R=H[r];if(!R||!R.win)return null;const mine=R.side||g.side,their=mine==="T"?"CT":"T",full=their==="CT"?4700:4400;
    const spend=r===hs&&!ot?cash:cash>=full?full:(lc>=3&&cash>=2000)?Math.min(cash,2600):Math.min(cash,250);
    cash-=spend;
    if(R.win===their){cash+=/bomb/.test(R.reason||"")?3500:3250;lc=Math.max(0,lc-1)}
    else{lc=Math.min(5,lc+1);cash+=Math.min(3400,1400+500*(lc-2>0?lc-2:0)+(lc>=2?500:0));if(their==="T"&&R.plant!=null)cash+=800}
    cash=Math.min(16000,cash+300)}   // about one kill each a round ($300 a rifle kill)
  const c=Math.round(cash/50)*50;return {cash:c,buy:c>=(g.side==="T"?4700:4400)?"full":c>=2200?"force":"eco"}}
// the ping (06/10: "quand je te dis A, B ou mid, ça me ping comme le ping in game, avec le son"): a mark on the map where
// the way goes and a short sound, once per key or call
const PING={t:0};
function pingSound(){try{const A=window.AudioContext||window.webkitAudioContext;if(!A)return;const ac=PING.ac||(PING.ac=new A());if(ac.state==="suspended")ac.resume();
  [[0,1046],[0.09,1568]].forEach(([d,f])=>{const o=ac.createOscillator(),gn=ac.createGain(),t0=ac.currentTime+d;o.type="sine";o.frequency.value=f;gn.gain.setValueAtTime(0.0001,t0);gn.gain.exponentialRampToValueAtTime(0.22,t0+0.012);gn.gain.exponentialRampToValueAtTime(0.0001,t0+0.16);o.connect(gn).connect(ac.destination);o.start(t0);o.stop(t0+0.18)})}catch(e){}}
function pingNow(g){const P_=g&&g.ping;if(!P_||P_.round!==g.round)return null;const age=Date.now()/1000-P_.t;if(age>3||age<-2)return null;
  if(P_.t!==PING.t){PING.t=P_.t;pingSound()}return P_}
// on the map: where the pinged way goes (T: the doorway of the picked way, or the mid way's middle; CT: the site's
// doorways, or mid's), a pulse that fades
function pingMark(ov,g,R,level,TD){const P_=pingNow(g);if(!P_)return;let pt=null;
  const r=R&&R.rows[0];if(r&&r.routes&&r.routes.length&&(P_.what==="MID"?r.mid:r.site===P_.what)){const pts=r.routes[0].pts;pt=P_.what==="MID"?pts[Math.floor(pts.length*.55)]:pts[pts.length-1]}
  else if(TD&&TD.gates){const G=TD.gates.filter(x=>P_.what==="MID"?x.mid:x.site===P_.what);if(G.length){const n=G.reduce((a,x)=>a+x.steps,0);pt=[G.reduce((a,x)=>a+x.px[0]*x.steps,0)/n,G.reduce((a,x)=>a+x.px[1]*x.steps,0)/n,G[0].level]}}
  if(!pt||(pt[2]&&level&&pt[2]!==level))return;const gg=el("g",{class:"ping"},ov);
  [0,1].forEach(i=>el("circle",{cx:pt[0],cy:pt[1],r:14,class:"ping-r"+i},gg));
  el("circle",{cx:pt[0],cy:pt[1],r:6,class:"ping-c"},gg);
  el("text",{x:pt[0],y:pt[1]-20,"text-anchor":"middle",class:"ping-t"},gg).textContent=DIR_EN[P_.what]||P_.what}
// the map's way lines: the ways of the panel, each with its odds this round, no times (06/10: the times stay in the panel's timeline)
function dirPaths(Lrot,Ltop,R,level){R.rows.slice().reverse().forEach(r=>(r.routes||[]).forEach((rt,j)=>{if(!rt.pts||rt.pts.length<2)return;
  tPathLabel(Lrot,Ltop,rt.pts,r.col,level,j===0?`${r.rank===1?"★ ":""}${r.label} · ${r.wr}%`:null)}))}
function tPathLabel(lay,top,pts,col,level,text){const on=q=>!q[2]||!level||q[2]===level;let seg=[];const segs=[];
  pts.forEach(q=>{if(on(q))seg.push(q);else{if(seg.length>1)segs.push(seg);seg=[]}});if(seg.length>1)segs.push(seg);
  segs.forEach(sg=>{const s=sg.map(q=>q[0]+","+q[1]).join(" ");
    el("polyline",{points:s,style:"fill:none;stroke:#0b0f14;stroke-width:5.5;stroke-opacity:.7;stroke-linejoin:round;stroke-linecap:round"},lay);
    el("polyline",{points:s,style:`fill:none;stroke:${col};stroke-width:2.6;stroke-linejoin:round;stroke-linecap:round`},lay);
    let acc=0;for(let i=0;i<sg.length-1;i++){const a=sg[i],b=sg[i+1],d=Math.hypot(b[0]-a[0],b[1]-a[1]);acc+=d;if(acc<110||d<4)continue;acc=0;
      const ux=(b[0]-a[0])/d,uy=(b[1]-a[1])/d,mx=b[0],my=b[1];
      el("path",{d:`M${mx-ux*5-uy*5} ${my-uy*5+ux*5}L${mx+ux*3} ${my+uy*3}L${mx-ux*5+uy*5} ${my-uy*5-ux*5}`,style:`fill:none;stroke:${col};stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round`},lay)}});
  const end=pts[pts.length-1];if(text&&on(end)){const w=7.2*text.length+14,y=place(top,end[0],end[1]-21,w,18),gg=el("g",{},top);
    el("rect",{x:end[0]-w/2,y:y-9,width:w,height:18,rx:9,style:`fill:${col};stroke:#0b0f14;stroke-width:1.5`},gg);
    el("text",{x:end[0],y:y+4,"text-anchor":"middle",class:"pbt"},gg).textContent=text}
  return segs.length}
