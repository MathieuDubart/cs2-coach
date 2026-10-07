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
function tdirSel(g){const t=g&&g.tdir;return t&&t.round===g.round?{dir:t.dir||null,via:t.via||null,tempo:t.tempo||null,src:t.src||null}:{dir:null,via:null,tempo:null,src:null}}
const TEMPO_EN={rush:"RUSH",slow:"SLOW",control:"MAP CONTROL"},TEMPO_SAY={rush:"Rush",slow:"Slow",control:"Map control"};
const DIR_EN={A:"A",MID:"MID",B:"B"};
// the map's middle as the players call it (07/10, the user: "nuke, c'est outside et pas forcément mid"): numpad 2
const MID_NAME={de_nuke:"Outside"};
const midName=map=>((TDIRS[map]||{}).mid_name)||MID_NAME[map]||"Mid";
const dirName=(d,map)=>d==="MID"?midName(map).toUpperCase():DIR_EN[d]||"";
// what the card waits for (07/10, the user: "tu me demandes dans l'interface live... c'est juste pour avoir un retour
// visuel et que l'utilisateur comprenne qu'on attend quelque chose de lui"): the keys to press next, framed until pressed
const keyAsk=(q,keys)=>`<div class="vkeyask"><span>${q}</span>${keys.map(([k,l])=>`<em><kbd>${k}</kbd> ${l}</em>`).join("")}</div>`;
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
// the ways to show: the picked way's own (A: the ways straight onto A, the ones through mid only when there is no
// other, 06/10: "je ne choisis pas le mid to A, je choisis le A tout court"; MID: the ways through mid), the way said
// to Wily first ("A from Ramp": A via Ramp, "mid to A": Mid → A), else the three that win most this round (a small
// sample doesn't win: the lower bound of its rounds won)
function dirRank(p,g,TD){if(!TD)return null;const sel=tdirSel(g),lb=(w,n)=>{const z=1.28,ph=w/100;return n?(ph+z*z/(2*n)-z*Math.sqrt(ph*(1-ph)/n+z*z/(4*n*n)))/(1+z*z/n):0};
  let ds=TD.dirs.filter(d=>d.n>=(d.split?40:25)),nomid=false;   // a split needs more rounds to be read
  if(sel.dir==="MID"){const m=ds.filter(d=>d.mid);nomid=!m.length;if(m.length)ds=m}
  else if(sel.dir){const on=ds.filter(d=>d.site===sel.dir),direct=on.filter(d=>!d.mid);ds=sel.via&&/^mid$/i.test(sel.via)?on.filter(d=>d.mid):(direct.length?direct:on);if(!ds.length)ds=on}
  const via=sel.via&&!/^mid$/i.test(sel.via)?String(sel.via).toLowerCase():null,said=d=>via&&String(d.label||"").toLowerCase().includes(via)?(d.split?1:2):0;
  const rows=ds.map(d=>{const o=dirOdds(p,g,d,sel.tempo);return {...d,wr:o.wr,shift:o.shift,ns:o.n,s:lb(o.wr,Math.min(o.n,d.n))}}).sort((a,b)=>(said(b)-said(a))||(b.s-a.s)).slice(0,sel.dir&&!nomid?2:3);
  rows.forEach((r,i)=>{r.rank=i+1;r.col=DIR_C[i]});return {rows,sel,mid:TD.mid||null,gates:TD.gates||[],nomid}}
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
// a lineup's keys: the training's (practiced) and the photo's (lineshots.py lid())
const pracKey=(side,u)=>`${side}:${u.type}:${u.from_key}>${u.to_key}`;
const shotId=(side,u)=>`${side}_${u.type}_${u.from_key||u.from||""}_${u.to_key||u.to||""}`.replace(/[^A-Za-z0-9_>-]/g,"").replace(/>/g,"-");
// the stuff (08/10, the user after his games: "j'ai eu très peu souvent des stuff en rapport avec les destinations que
// je cochais... propose-moi des stuff qui s'envoient à peu près depuis le même endroit, et surtout pour l'endroit où je
// vais, dans le timing que je choisis"). Every lineup of the base on this map and side (tdirs.lineups_page, nades.py's:
// thrown from one zone onto another 8 times or more, its usual spot, where it lands, how many throws in each window of
// the round), kept when
//  - it lands where you go: T, on that site or along the base's walks onto it (80 px, their half near the site; mid: the
//    middle of the walks through mid); CT, along the Ts' walks onto your site (mid ones too); never on the other site.
//    A site's size is its own (1.15 times its farthest doorway from its middle: Nuke's A is small and above B);
//  - it is thrown from where you can be: T, not from inside a site (that's after you got in); CT, from inside your site
//    (same level), or in mid from around mid's doorways (not from a site);
//  - it counts as much as the way it lands on is taken at that tempo (CT B on Mirage: the apartments' rushes before the
//    short's), the site itself fully (T);
//  - it is thrown at the tempo said: a rush, the round's first 40 s; map control, 20 to 40 s; slow, after 40 s; none
//    said, any time before the plant: 6 throws or more then, by 3 players or more (sure: not one player's habit), or
//    one you practiced in training (3 throws then);
//  - it is one of the grenades you hold, as many as you hold (none yet at the buy time: the ones to buy, said so);
// then ONE place to throw them from (the base's spots within 55 px of each other on the radar, same level): the one that
// covers the most of your grenades (T: on the way you take, whenever one there has something; CT: on your site first);
// a second place only for what the first can't throw
const TEMPO_W={rush:[0,1],control:[1],slow:[2,3]};   // nades.py's windows: 0-20 s, 20-40 s, 40-70 s, after 70 s (then after the plant)
const NADE_ORDER="smoke molotov flash he";   // the order to throw them: the smoke, then the flash over it
const comboDir=(r,sel)=>sel.dir&&!(sel.dir==="MID"&&!r.mid)?sel.dir:(r.mid?"MID":r.site);
const nearPts=(p_,lv,P,d)=>!!p_&&P.some(q=>Math.hypot(q[0]-p_[0],q[1]-p_[1])<d&&(!lv||!q[2]||lv===q[2]));
// the base's ways of a direction, each with its walks' part near the site (mid: their middle) and its rounds at that tempo
function dirWays(TD,dir,side,tempo){return (TD.dirs||[]).filter(d=>dir==="MID"?d.mid:(d.site===dir&&(side==="CT"||!d.mid))).map(d=>{const pts=[];
    (d.routes||[]).forEach(r=>{const q=r.pts||[],n=q.length;q.slice(Math.floor(n*(dir==="MID"?.25:.45)),dir==="MID"?Math.ceil(n*.9):n).forEach(x=>pts.push(x))});
    return {c:tempo&&d.tempo&&d.tempo[tempo]?d.tempo[tempo][0]:d.n,pts}}).filter(w=>w.c>0&&w.pts.length)}
function stuffPlan(p,g,side,dir,tempo,way,max){const TD=tdirsOf(g.map)||{},L=(TD.lineups||{})[side]||[];if(!dir||!L.length)return null;
  const held=g.nades||{},any=Object.values(held).some(v=>v>0),buy=!any&&g.round_phase==="freezetime";if(!any&&!buy)return null;
  const SS=(((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).geo||{}).sites||{},S=dir!=="MID"?SS[dir]:null,O=dir!=="MID"?SS[dir==="A"?"B":"A"]:null;
  const WY=dirWays(TD,dir,side,tempo),tot=WY.reduce((a,w)=>a+w.c,0)||1,P=WY.flatMap(w=>w.pts),PR=new Set(TD.practiced||[]),SH=TD.shots||{},prac=u=>PR.has(pracKey(side,u));
  const inS=(xy,lv,s_,d)=>!!s_&&Math.hypot(xy[0]-s_.px[0],xy[1]-s_.px[1])<d&&(!lv||!s_.level||lv===s_.level);
  const radOf=(k,s_)=>s_?1.15*Math.max(60,...(TD.gates||[]).filter(x=>x.site===k&&!x.mid&&(!x.level||!s_.level||x.level===s_.level)).map(x=>Math.hypot(x.px[0]-s_.px[0],x.px[1]-s_.px[1]))):0;
  const RS=radOf(dir,S),RO=radOf(dir==="A"?"B":"A",O),MG=(TD.gates||[]).filter(x=>x.mid).map(x=>[x.px[0],x.px[1],x.level]);
  const wt=u=>{if(inS(u.to_px,u.land_level,O,RO*1.2))return 0;let m=side==="T"&&inS(u.to_px,u.land_level,S,RS*1.3)?1:0;
    WY.forEach(w=>{if(w.c/tot>m&&nearPts(u.to_px,u.land_level,w.pts,80))m=w.c/tot});return m};   // where it lands, as much as that way is taken
  const bomb=u=>/^Bombsite/.test(u.from_key||"");   // thrown from a bomb site's own zone
  const from=u=>side==="T"?!bomb(u)&&!inS(u.from_px,u.level,S,RS*.6):dir==="MID"?!bomb(u)&&(MG.length?nearPts(u.from_px,u.level,MG,110):nearPts(u.from_px,u.level,P,100)):inS(u.from_px,u.level,S,RS);
  const W=tempo?TEMPO_W[tempo]:[0,1,2,3],nt=u=>W.reduce((a,i)=>a+((u.w||[])[i]||0),0);
  const C=L.filter(u=>u.from_px&&u.to_px&&from(u)).map(u=>{const k=nt(u),w=wt(u);return {...u,nt:k,wt:w,s:Math.min(k,300)*(.25+.75*w)}})
    .filter(u=>u.wt>0&&(prac(u)?u.nt>=3:u.nt>=6&&(u.players||0)>=3));
  if(!C.length)return {stacks:[],why:"none sure in the base"};
  const want=buy?(side==="T"?{smoke:1,flash:2,molotov:1}:{molotov:1,smoke:1,flash:1,he:1}):{smoke:held.smoke||0,flash:held.flash||0,molotov:held.molotov||0,he:held.he||0};
  const rank=(a,b)=>(prac(b)-prac(a))||(b.s-a.s)||((b.eff||0)-(a.eff||0));
  const A=[];C.sort(rank).forEach(u=>{const a=A.find(x=>x.lv===(u.level||null)&&Math.hypot(x.c[0]-u.from_px[0],x.c[1]-u.from_px[1])<55);if(a)a.L.push(u);else A.push({c:u.from_px,lv:u.level||null,L:[u]})});
  const pick=(a,w)=>{const left={...w},out=[];a.L.forEach(u=>{if((left[u.type]||0)>0&&!out.some(x=>x.type===u.type&&x.to_key===u.to_key)){left[u.type]--;out.push(u)}});return {out,left}};
  const onWay=a=>!!(way&&way.length&&nearPts(a.c,a.lv,way,70)),here=a=>side==="T"?(onWay(a)?1:0):(inS(a.c,a.lv,S,RS*.7)?1:0);
  const val=(a,w)=>{const r=pick(a,w);return r.out.length*1000+here(a)*400+r.out.reduce((s_,u)=>s_+u.s,0)};
  let B=A.sort((a,b)=>val(b,want)-val(a,want));
  if(side==="T"&&B.some(a=>onWay(a)&&pick(a,want).out.length))B=B.filter(onWay);   // T: from the way you take
  const first=B[0]?pick(B[0],want):null;
  if(!first||!first.out.length)return {stacks:[],why:"none for your grenades"};
  const ord=s_=>s_.sort((a,b)=>NADE_ORDER.indexOf(a.type)-NADE_ORDER.indexOf(b.type)),stacks=[ord(first.out)];
  if((max||2)>1&&Object.values(first.left).some(v=>v>0)){const nx=B.slice(1).map(a=>({a,r:pick(a,first.left)})).filter(x=>x.r.out.length).sort((x,y)=>val(y.a,first.left)-val(x.a,first.left))[0];
    if(nx){if(fromOf(nx.r.out)===fromOf(stacks[0])){stacks[0].push(...nx.r.out);ord(stacks[0])}else stacks.push(ord(nx.r.out))}}   // the same callout: one place
  return {stacks,buy,prac,SH,side}}
const fromOf=st=>{const c={};st.forEach(u=>c[u.from]=(c[u.from]||0)+1);return Object.entries(c).sort((a,b)=>b[1]-a[1])[0][0]};   // the place's name: its throws' most common zone
function vStuff(P,title){if(!P)return "";if(!P.stacks.length)return `<div class="vhead">${title} · <span class="vnone">${P.why}</span></div>`;const {stacks,buy,prac,SH,side}=P;
  return `<div class="vhead">${title}${buy?" · TO BUY":""}</div><div class="vstacks">${stacks.map(st=>{const sh=st.map(u=>SH[shotId(side,u)]).find(Boolean);
    return `<div class="vstack${sh?" shot":""}">${sh?`<img class="vshot" src="${esc(sh)}" alt="Where to aim" loading="lazy">`:""}<div class="vst-in"><span class="from">${esc(vShort(fromOf(st)||"?"))}${st.length>1?` <small>×${st.length}</small>`:""}</span>${st.map(u=>`<span class="vnd${prac(u)?" prac":""}"><i style="background:${NADE_C[u.type]||"#ccc"}">${NADE_L[u.type]||"?"}</i>${esc(vShort(u.to||"?"))}${prac(u)?`<b title="practiced in training">✓</b>`:""}${HOW_S(u.how)?`<small>${esc(HOW_S(u.how))}</small>`:""}</span>`).join("")}</div></div>`}).join("")}</div>`}
// the panel's way card: the plan picked (or Wily's pick), the ways with their odds this round, then the timeline and the stuff of the top one
function vDir(p,g,opt){if(g.side!=="T"||isHostage(g.map))return "";const more=opt&&opt.stuff;const TD=tdirsOf(g.map),R=dirRank(p,g,TD);if(!R||!R.rows.length)return "";
  const sel=R.sel,top=R.rows[0],dead=typeof deadAgo==="function"&&deadAgo(g)!=null,mn=midName(g.map).toLowerCase(),live=g.round_phase==="live",el=live?(g.elapsed||0):0;
  const head=sel.dir?`<b>${dirName(sel.dir,g.map)}${sel.tempo?` · ${TEMPO_EN[sel.tempo]}`:""}</b>${R.nomid?` <small>no way through ${esc(mn)} here: the best ways</small>`:""}`
    :sel.tempo?`<b>${TEMPO_EN[sel.tempo]}</b>`:`<b>WILY'S PICK</b> · 1&nbsp;A · 2&nbsp;${esc(mn)} · 3&nbsp;B · 4&nbsp;rush · 5&nbsp;slow · 6&nbsp;control`;
  // a way without a tempo: the tempo is asked; a tempo without a way: the way (until 15 s into the round)
  const ask=dead||el>15?"":sel.dir&&!sel.tempo?keyAsk("TEMPO?",[["4","rush"],["5","slow"],["6","control"]]):!sel.dir&&sel.tempo?keyAsk("WHERE?",[["1","A"],["2",esc(mn)],["3","B"]]):"";
  const mx=Math.max(...R.rows.map(r=>r.wr),1);
  const late=live&&el>(sel.tempo==="slow"||sel.tempo==="control"?95:Math.max(50,(top.hit_med||35)+15));   // the stuff stays until the way's usual hit (a slow round: until 0:20)
  const way=(top.routes||[]).flatMap(r=>r.pts||[]),dn=comboDir(top,sel);   // the way you take (a split: both): the place you throw from is on it first
  const stuff=dead||(!more&&late)?"":vStuff(stuffPlan(p,g,"T",dn,sel.tempo,way,more||2),`STUFF · ${dirName(dn,g.map)}${sel.tempo?` · ${TEMPO_EN[sel.tempo]}`:""}`);
  return `<div class="vdir"><div class="vdir-h">${head}</div>${ask}<div class="vrows">${R.rows.map((r,i)=>`<div class="vrow" style="--c:${r.col}${i?`;opacity:${[1,.82,.68][i]}`:""}"><span>${i===0?"★ ":""}${esc(r.label)}</span><i><u style="width:${Math.max(4,Math.round(100*r.wr/mx))}%"></u></i><b>${r.wr}%</b></div>`).join("")}</div>
    ${dead?"":vDirCurve(p,g,top)}${stuff}</div>`}
// CT (07/10, the user: "en CT, quand je fais 1, 2 ou 3, tu me donnes le pourcentage de chance que les terroristes
// avancent en fonction du temps, et pareil les stuff par rapport à ce que je te dis... parfois des zones de boost que
// j'ai travaillé à l'échauffement... pas forcément des zones de wallbang"): numpad 1-2-3 where you play, 4-5-6 the
// tempo you expect from them; the chance they hit your site around each moment, your stuff against that tempo, a
// boost you trained there (at the buy time)
function ctDirStuff(p,g){const sel=tdirSel(g);if(g.side!=="CT"||!sel.dir)return null;return stuffPlan(p,g,"CT",sel.dir,sel.tempo,null,2)}
// the chance they hit your site around each moment of the round: the base's rounds for their buy (every 5 s), scaled to
// this round's read of that site; the tempo said shaded; under it the same in three windows (a rush, the middle of the
// round, late), the tempo's framed, the past ones faded
function vArrive(p,g,site,tempo,r){const M=(((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{},TT=M.t_timeline;if(!TT)return "";const ew=econW(p,g),acc={};let sh=0,ws=0;
  for(const [c,w] of Object.entries(ew)){const X=TT[c]&&TT[c][site];if(!X||!w)continue;ws+=w;sh+=w*X.share;X.curve.forEach(([t,v])=>acc[t]=(acc[t]||0)+w*v)}
  if(!ws)return "";const pts=Object.entries(acc).map(([t,v])=>[+t,v/ws]).sort((a,b)=>a[0]-b[0]),tot=pts.reduce((a,q)=>a+q[1],0);if(!tot||pts.length<3)return "";
  const k=(r&&r[site]!=null?r[site]:sh/ws)/tot,L=RLEN(),W=300,H=46,x=t=>6+(W-12)*Math.min(1,Math.max(0,t/L)),mx=Math.max(...pts.map(q=>q[1])),y=v=>H-4-(H-8)*v/mx;
  const band=tempo==="rush"?[0,30]:tempo==="slow"?[60,L]:tempo==="control"?[35,L]:null,el=g.round_phase==="live"?(g.elapsed||0):null,pk=pts.reduce((a,q)=>q[1]>a[1]?q:a);
  const WN=[[0,30,`›${clock(30)}`],[30,60,`${clock(30)}-${clock(60)}`],[60,L,`‹${clock(60)}`]].map(([a,b,l])=>({a,b,l,v:Math.round(k*pts.filter(q=>q[0]>a&&q[0]<=b).reduce((s_,q)=>s_+q[1],0)),on:!!band&&band[0]<b&&band[1]>a}));
  const line=pts.map(q=>`${x(q[0]).toFixed(1)},${y(q[1]).toFixed(1)}`).join(" "),c=SITE_C[site]||"var(--ct)";
  return `<div class="vhead">THEY HIT ${site} · WHEN</div><svg class="vdcurve" viewBox="0 0 ${W} ${H}" role="img" aria-label="When the Ts hit ${site}">
    ${band?`<rect x="${x(band[0])}" y="0" width="${x(band[1])-x(band[0])}" height="${H}" class="band ct"/>`:""}<line x1="6" x2="${W-6}" y1="${H-1}" y2="${H-1}" class="base"/>
    <polygon points="${x(pts[0][0]).toFixed(1)},${H-1} ${line} ${x(pts[pts.length-1][0]).toFixed(1)},${H-1}" style="fill:${c};fill-opacity:.22"/><polyline points="${line}" style="fill:none;stroke:${c};stroke-width:2.6;stroke-linejoin:round"/>
    <circle cx="${x(pk[0])}" cy="${y(pk[1])}" r="3.5" style="fill:${c}"/>${el!=null?`<line x1="${x(el)}" x2="${x(el)}" y1="0" y2="${H}" class="now"/>`:""}</svg>
    <div class="vwin" style="--c:${c}">${WN.map(w=>`<span class="${w.on?"on":""}${el!=null&&el>w.b?" past":""}">${w.l}<b>${w.v}%</b></span>`).join("")}</div>`}
// a boost you trained (Prepare's warm-up), CT, near your site: the one that killed most up there
function ctBoostPick(p,g,site){const B=((tdirsOf(g.map)||{}).boosts||[]).filter(b=>b.side==="CT");if(!B.length)return null;
  const GEO=((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).geo,S=site!=="MID"&&GEO&&GEO.sites?GEO.sites[site]:null;
  const at=b=>{const w=GEO&&typeof worldPx==="function"?worldPx(GEO,b.pos):null;return {...b,px:w?w.px:null,level:w?w.level:null}};
  const near=b=>!S||(b.victims||[]).some(v=>String(v).startsWith(site+" "))||(b.px&&Math.hypot(b.px[0]-S.px[0],b.px[1]-S.px[1])<380);
  return B.map(at).filter(near).sort((a,b)=>b.kills-a.kills)[0]||null}
function vCTDir(p,g,r){if(g.side!=="CT"||isHostage(g.map))return "";const sel=tdirSel(g);if(!sel.dir)return "";
  const site=sel.dir,mn=midName(g.map),live=g.round_phase==="live",el=live?(g.elapsed||0):0,dead=typeof deadAgo==="function"&&deadAgo(g)!=null;
  const head=`<b>${dirName(site,g.map)}${sel.tempo?` · VS ${TEMPO_EN[sel.tempo]}`:""}</b>`;
  const ask=dead||el>15||sel.tempo?"":keyAsk("THEIR TEMPO?",[["4","rush"],["5","slow"],["6","control"]]);
  const curve=site==="MID"||dead?"":vArrive(p,g,site,sel.tempo,r);   // mid: both sites' arrivals stay on the CT timeline
  const st=dead?"":vStuff(ctDirStuff(p,g),`STUFF · ${site==="MID"?esc(mn.toUpperCase()):site}${sel.tempo?` · VS ${TEMPO_EN[sel.tempo]}`:""}`);
  const b=live?null:ctBoostPick(p,g,site);
  const bo=b?`<div class="vchips"><span class="vchip good">⤴ BOOST ${esc(vShort(b.place||"?"))} ✓ <small>trained · ${b.kills} kill${b.kills>1?"s":""} up there in the base</small></span></div>`:"";
  return `<div class="vdir ct"><div class="vdir-h">${head}</div>${ask}${curve}${st}${bo}</div>`}
// after the plant (07/10, the user: "si je t'ai dit avant que j'allais dans le mid et qu'ensuite je te donne l'info de
// post-plant en B, tu me donnes les chemins de rota depuis le mid pour le B"): the way said this round (numpad 1-2-3)
// is where you come from, the base's rotations from there to the bomb's site
function rotFromDir(M,site,dir,map){if(!M||!site||!dir||dir===site||typeof rotationFor!=="function")return null;const R=(M.rotations||{})[site]||{},GEO=M.geo;
  let from=dir==="A"||dir==="B"?`${dir} Site`:null;
  if(dir==="MID"){from=[midName(map),"Mid","Top Mid","Middle"].find(z=>R[z])||null;
    const G=((TDIRS[map]||{}).gates||[]).filter(x=>x.mid);
    if(!from&&G.length&&GEO&&GEO.zones){const c=[G.reduce((a,x)=>a+x.px[0],0)/G.length,G.reduce((a,x)=>a+x.px[1],0)/G.length],d=z=>Math.hypot(GEO.zones[z].px[0]-c[0],GEO.zones[z].px[1]-c[1]);
      from=Object.keys(R).filter(z=>GEO.zones[z]).sort((a,b)=>d(a)-d(b))[0]||null}}
  const X=from?rotationFor(M,site,from,GEO):null;return X&&X.routes&&X.routes.length?X:null}
function vRotLine(X,dir,site,map){const rt=X&&X.routes[0];if(!rt)return "";
  return `<div class="vrotl"><b>${dirName(dir,map)} → ${site}</b><span>${rt.travel!=null?`${Math.round(rt.travel)} s · `:""}${rt.died}% die on the way${(rt.route||[]).length?` · via ${esc(rt.route.slice(0,2).map(z=>vShort(z)).join(" › "))}`:""}</span></div>`}
// the team chat lines of numpad 1-6 for this round (T): the best way onto A, mid, B for the tempo picked, the tempo with the way picked
// what the keys say in the team chat (07/10, the user: "si la touche veut dire A tu ne peux pas écrire A from Ramp: les
// seules infos que tu envoies c'est les combos A/B/mid avec rush/slow/map control"): your direction and your tempo, the
// last of each you pressed this round, nothing the app picked (the way in stays on your screen, in Live)
const DIR_SAY={A:"A",MID:"mid",B:"B"};
function sayCombo(dir,tempo,map){const d=dir==="MID"&&map?midName(map).toLowerCase():DIR_SAY[dir]||"";if(!tempo)return d?d.charAt(0).toUpperCase()+d.slice(1):"";
  return tempo==="control"?`Map control${d?", then "+d:""}`:`${TEMPO_SAY[tempo]}${d?" "+d:""}`}
function dirTexts(p,g){const TD=tdirsOf(g.map);if(!TD||g.side!=="T"||isHostage(g.map))return null;const sel=tdirSel(g);
  return {paths:[{rank:1,site:"A",text:sayCombo("A",sel.tempo,g.map)},{rank:2,site:null,text:sayCombo("MID",sel.tempo,g.map)},{rank:3,site:"B",text:sayCombo("B",sel.tempo,g.map)}],
    tempo:{rush:sayCombo(sel.dir,"rush",g.map),slow:sayCombo(sel.dir,"slow",g.map),ctrl:sayCombo(sel.dir,"control",g.map)}}}
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
  el("text",{x:pt[0],y:pt[1]-20,"text-anchor":"middle",class:"ping-t"},gg).textContent=dirName(P_.what,g.map)||P_.what}
// the map's way lines: the ways of the panel, each with its odds this round, no times (06/10: the times stay in the panel's timeline)
function dirPaths(Lrot,Ltop,R,level){R.rows.slice().reverse().forEach(r=>(r.routes||[]).forEach((rt,j)=>{if(!rt.pts||rt.pts.length<2)return;
  tPathLabel(Lrot,Ltop,rt.pts,r.col,level,j===0?`${r.rank===1?"★ ":""}${r.label} · ${r.wr}%`:null)}))}
// the picked way's stuff on the map (06/10: "où je dois me mettre"): an arc from where you stand to where it lands, the
// first of each stack (the practiced ones first), five at most
function dirNades(Lnades,Ltop,R,level,TD,g,p){const r=R.rows[0];if(!r||!R.sel.dir||!g||!p)return 0;return stuffArcs(Lnades,Ltop,stuffPlan(p,g,"T",comboDir(r,R.sel),R.sel.tempo,(r.routes||[]).flatMap(q=>q.pts||[]),2),level)}
function stuffArcs(Lnades,Ltop,P,level){let n=0;if(!P||!P.stacks.length)return 0;
  P.stacks.flat().forEach(u=>{if(!u.from_px||!u.to_px||(u.level&&level&&u.level!==level))return;n++;
    nadeArc(Lnades,u.from_px[0],u.from_px[1],u.to_px[0],u.to_px[1],u.type);nadeIcon(Ltop,u.type,u.to_px[0],u.to_px[1],`${u.type} from ${u.from} onto ${u.to}${u.how&&u.how!=="standing still"?" ("+u.how+")":""}`)});
  return n}
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
