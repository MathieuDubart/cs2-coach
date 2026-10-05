
// ---------- full-screen side panel: visual only (a glance between two duels), filtered by side and by moment ----------
const vTone=v=>v==null?"":v>=60?"good":v>=45?"warn":"bad";
const vShort=s=>esc(String(s||"").split(" / ")[0].replace(/^Bombsite /,"").replace(/ Site$/,""));
const vLetter={smoke:"S",flash:"F",molotov:"M",he:"H"};
// the grenades you hold, each with the throw that fits this moment (same choice as the text panel), or none
function vNadePicks(p,g){const N=(p.advice.plan||{}).nades,E=N&&((N.maps||{})[g.map]||{})[g.side];if(!E)return [];
  const w=g.bomb==="planted"?"post":g.elapsed==null?null:g.elapsed<20?"debut":g.elapsed<40?"prise":g.elapsed<70?"action":"fin",el=g.elapsed;
  const MS=g.side==="CT"?mySite(g):null,GS=((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).geo,MSg=MS&&GS&&GS.sites?GS.sites[MS]:null;
  const atMine=x=>MSg&&x.to_px&&Math.hypot(x.to_px[0]-MSg.px[0],x.to_px[1]-MSg.px[1])<300&&(!x.land_level||!MSg.level||x.land_level===MSg.level);
  // a path pressed (T) or the site you play (CT): every lineup of the base for it, not only your usual zones'
  const src=t=>{const P=(E.pool||[]).filter(x=>x.type===t);if(focusN(g)&&P.length)return P;if(MSg&&P.length){const m=P.filter(atMine);if(m.length)return m}return E.types[t].picks||[]};
  const all=t=>[...src(t),...(E.types[t].post||[])].filter((x,i,a)=>a.indexOf(x)===i);
  // what a throw brings: rounds won when it's thrown vs the map's average (shrunk on few throws), else its own score
  const eff=x=>x.win!=null&&x.base_win!=null?((x.win*(x.n||0)+x.base_win*10)/((x.n||0)+10)-x.base_win)/100:(x.score||0)/4;
  // T side: the throws that serve your way (path 1 of the radar) come first, the ones landing on the other site last
  const W=g.side===attackSide(g.map)?(isHostage(g.map)?hostageRank(p,g):typeof winsRank==="function"?winsRank(p,g):null):null;
  const RF=W&&(W.rows.find(x=>x.rank===focusN(g))||W.rows[0]),R1=RF&&RF.route,pts=R1?R1.pts:null;   // the path you pressed, else path 1
  const GEO=((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).geo,end=pts?pts[pts.length-1]:null;
  // the level counts (Nuke: A is right above B): a throw is near a point only on the same level, when both are known
  const lvOK=(a,b)=>!a||!b||a===b,sk=RF?(RF.k.match(/[AB]$/)||RF.k.match(/^[AB]/)||[])[0]:null;
  const S1g=R1&&GEO&&GEO.sites&&sk?GEO.sites[sk]:null,S1=S1g?S1g.px:null;   // the site of that path
  const othG=GEO&&GEO.sites&&sk?GEO.sites[sk==="A"?"B":"A"]:null,oth=othG?othG.px:null;
  const near=(a,d,lv)=>a&&pts&&pts.some(q=>Math.hypot(q[0]-a[0],q[1]-a[1])<d&&lvOK(lv,q[2]));
  const way=x=>{if(!pts||!x.to_px)return null;const lv=x.land_level||x.level;
    if((end&&Math.hypot(x.to_px[0]-end[0],x.to_px[1]-end[1])<160&&lvOK(lv,end[2]))||(S1&&Math.hypot(x.to_px[0]-S1[0],x.to_px[1]-S1[1])<170&&lvOK(lv,S1g.level)))return "site";
    if(near(x.to_px,50,lv))return "way";
    if(oth&&Math.hypot(x.to_px[0]-oth[0],x.to_px[1]-oth[1])<160&&lvOK(lv,othG.level))return "off";
    return near(x.from_px,60,x.level)?"from":null};
  const bonus={site:.06,way:.04,from:.02,off:-.06};
  const eff0=eff,effW=x=>eff0(x)+(bonus[way(x)]||0)+(x.pop?.03:0),   // a pop flash: you peek behind it yourself
tag=x=>x&&Object.assign({},x,{way:way(x)});
  const FX=focusN(g),noOff=l=>l.filter(x=>FX?["site","way","from"].includes(way(x)):way(x)!=="off");   // a throw toward the other site only helps a fake: never shown; with a focus, only the throws of that path
  const picks=t=>{if(w==="post")return (E.types[t].post||[]).slice(0,2);
    if(el==null||!w){const L0=noOff(src(t).slice().sort((a,b)=>effW(b)-effW(a)));
      const rushL=RF&&/^rush/.test(RF.k)?L0.filter(x=>x.t_med!=null&&x.t_med<=28):[];   // a rush: the throws made in its first seconds
      return (rushL.length?rushL:L0).slice(0,2).map(tag)}   // buy time: the best ones of the round, for your way
    const fit=x=>x.best===w||x.usual===w||(x.t_med!=null&&x.t_med>=el-8&&x.t_med<=el+25);
    return noOff(all(t).filter(fit).sort((a,b)=>effW(b)-effW(a)||Math.abs((a.t_med??el)-el)-Math.abs((b.t_med??el)-el))).slice(0,2).map(tag)};
  return Object.entries(g.nades||{}).filter(([t,v])=>v>0&&E.types[t]).map(([t,v])=>{const ps=picks(t);return {type:t,n:v,x:ps[0]||null,alt:ps[1]||null,el:g.round_phase==="live"?el:null}})}
function vNades(list){if(!list.length)return "";
  const when=(x,el)=>x.t_med!=null&&el!=null&&x.t_med>el+3?clock(x.t_med):x.t_med!=null&&el==null?clock(x.t_med):"now";
  return `<div class="vnades">${list.map(o=>`<span class="vnade${o.x?(o.now?" now":""):" keep"}" style="--c:${NADE_C[o.type]||"#ccc"}"><i>${vLetter[o.type]||"?"}</i>${o.x?`${vShort(o.x.to||o.x.land)}${o.x.pop?" ↯":""}<small>${when(o.x,o.el)}</small>${o.alt?`<em>${vShort(o.alt.to||o.alt.land)} ${when(o.alt,o.el)}</em>`:""}`:"<small>keep</small>"}</span>`).join("")}</div>`}
// a rule as icons and two numbers: what your side wins when you do it / when you don't
const vRule=(icon,label,bad,good)=>`<div class="vrule"><i>${icon}</i><span>${label}</span><b class="bad">${bad}%</b><em>→</em><b class="good">${good}%</b></div>`;
// T side: the round as a strip from 1:55 to 0:00, each tempo window colored by how often the Ts win with it here;
// what is past fades, a cursor marks now
function vTimeline(p,g){const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[g.map],TP=(M&&M.tplan)||{},rt=advisedType(g);
  const tp=(TP.tempo||{})[rt==="pistol"?"pistol":rt]||(TP.tempo||{}).full||{},L=RLEN(),el=g.round_phase==="live"?(g.elapsed||0):0;
  const seg=[["rush",0,30],["exec",30,75],["late",75,L]].filter(s=>s[2]>s[1]);
  return vHead("ROUNDS WON · BY TEMPO")+`<div class="vtl">${seg.map(([k,a,b])=>{const v=(tp[k]||[])[1];
      return `<div class="vseg ${vTone(v)}${el>b?" past":""}" style="flex:${b-a}"><span>${k} ${a===0?`›${clock(b)}`:b>=L?`‹${clock(a)}`:`${clock(a)}-${clock(b)}`}</span>${v!=null?`<b>${v}%</b>`:""}</div>`}).join("")}
    ${g.round_phase==="live"?`<i class="vcur" style="left:${Math.min(100,100*el/L)}%"></i>`:""}</div>`}
// T: when to be on the site with your paths: rounds won by the moment the play is on the site (game clock, 1:55 on the
// left, 0:00 on the right), path 1 filled, paths 2 and 3 as dashed lines in their colors; the band is path 1's best
// window (its "on site" on the map), the white line is now. The same rounds as the window on the map
function vPathCurve(p,g){const W=typeof winsRank==="function"?winsRank(p,g):null;if(!W)return "";
  const rows=W.rows.slice(0,3).filter(r=>r.timing&&r.timing.curve&&r.timing.curve.length>=3);if(!rows.length||rows[0].rank!==1)return "";
  const site1=(rows[0].k.match(/[AB]$/)||rows[0].k.match(/^[AB]/)||[])[0],UW=((((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).util_war||{})[site1])||null;
  const ew=econW(p,g),wsh=u=>u.ctx&&Object.keys(u.ctx).length?Object.entries(ew).reduce((a,[c,w])=>a+w*(u.ctx[c]??u.share),0):u.share;
  const ub=((UW&&UW.util)||[]).map(u=>({...u,share:Math.round(wsh(u))})).filter(u=>u.share>=15).sort((a,b)=>b.share-a.share).slice(0,3);   // their usual blocking utility there, for their buy
  const Wd=320,H=86+ub.length*7,L=RLEN(),all=rows.flatMap(r=>r.timing.curve.map(c=>c[1])),lo=Math.min(...all)-4,hi=Math.max(...all)+6;
  const X=c=>Math.round(Wd*c/L),Y=v=>Math.round(6+(H-20)*(1-(v-lo)/Math.max(1,hi-lo)));
  const line=r=>r.timing.curve.map(([c,v],i)=>`${i?"L":"M"}${X(c)} ${Y(v)}`).join("");
  const r1=rows[0],c1=r1.timing.curve,t1=r1.timing,base=H-14-ub.length*7,area=`${line(r1)}L${X(c1[c1.length-1][0])} ${base}L${X(c1[0][0])} ${base}Z`;
  const now=g.round_phase==="live"?(g.elapsed||0):null,pk=c1.reduce((a,b)=>b[1]>a[1]?b:a);
  const ticks=[[25,"1:30"],[55,"1:00"],[85,"0:30"]].map(([c,t])=>`<line x1="${X(c)}" y1="${base}" x2="${X(c)}" y2="${base+4}" stroke="var(--muted)"/><text x="${X(c)}" y="${H-1}" text-anchor="middle" class="vct">${t}</text>`).join("");
  const svg=`<svg class="vcurve" viewBox="0 0 ${Wd} ${H}" width="100%" height="${H}" role="img" aria-label="Rounds won by the moment the play is on the site">
    <line x1="0" y1="${base}" x2="${Wd}" y2="${base}" stroke="var(--line)"/>
    ${t1.win-t1.mean>=3?`<rect x="${X(t1.lo)}" y="0" width="${Math.max(2,X(t1.hi)-X(t1.lo))}" height="${base}" fill="${r1.col}" fill-opacity=".2"/>`:""}
    <path d="${area}" fill="${r1.col}" fill-opacity=".22"/><path d="${line(r1)}" fill="none" stroke="${r1.col}" stroke-width="2.4" stroke-linejoin="round"/>
    ${rows.slice(1).map(r=>`<path d="${line(r)}" fill="none" stroke="${r.col}" stroke-width="1.6" stroke-dasharray="4 3" opacity=".85"/>`).join("")}
    <text x="${Math.min(Wd-14,Math.max(14,X(pk[0])))}" y="${Math.max(10,Y(pk[1])-4)}" text-anchor="middle" class="vcv">${pk[1]}%</text>
    ${ub.map((u,i)=>`<rect x="${X(u.t)}" y="${base+2+i*7}" width="${Math.max(3,X(u.end)-X(u.t))}" height="5" rx="2" fill="${u.type==="molotov"?"var(--molotov)":"var(--smoke)"}" opacity=".9"><title>Their ${u.type} ${u.land}: ${u.share}% of rounds, ${clock(u.t)} to ${clock(u.end)}</title></rect>`).join("")}
    ${ticks}${now!=null?`<line x1="${X(now)}" y1="0" x2="${X(now)}" y2="${base}" stroke="#fff" stroke-width="1.6"/>`:""}</svg>`;
  const hz=(UW&&UW.hits)||{},act=hz.active,aft=hz.spent||hz.kept,into=act&&aft&&aft[1]-act[1]>=5?vRule("⚠",`into their utility ${site1}`,act[1],aft[1]):"";
  return vHead(`ON THE SITE AT · ROUNDS WON · PATH${rows.length>1?`S 1-${rows.length}`:" 1"}`)+svg+(ub.length?`<div class="vleg">${ub.map(u=>`<span><i style="background:${u.type==="molotov"?"var(--molotov)":"var(--smoke)"}"></i>${u.type==="molotov"?"molly":"smoke"} ${esc(vShort(u.land||"?"))} ${clock(u.t)}-${clock(u.end)}</span>`).join("")}</div>`:"")+into}
// the other team's economy as weights over the kinds of round of the base: their pistol, eco or force ("low"), full
function econW(p,g){if(g.round===halfStart(g.round))return {pistol:1};const eb=enemyBuy(p,g)||{},lo=(eb.eco||0)+(eb.force||0),fu=eb.full||0,s=lo+fu;
  return s>0?{low:lo/s,full:fu/s}:{full:1}}
// CT: when the Ts are on each site for their buy (A and B, share of rounds around each moment, game clock), their
// smokes and mollies on that side before they come, the moment to throw the one you held (green:
// just before their usual arrival) and now
const UCOL={smoke:"var(--smoke)",flash:"var(--flash)",molotov:"var(--molotov)",he:"var(--he)"};
function vCTline(p,g,r){const M=(((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{},TT=M.t_timeline;if(!TT)return "";const ew=econW(p,g);
  const mix=site=>{const acc={};let any=false;for(const [c,w] of Object.entries(ew)){const X=TT[c]&&TT[c][site];if(!X||!w)continue;any=true;X.curve.forEach(([t,v])=>acc[t]=(acc[t]||0)+w*v)}
    return any?Object.entries(acc).map(([t,v])=>[+t,v]).sort((a,b)=>a[0]-b[0]):null};
  const A=mix("A"),B=mix("B");if(!A&&!B)return "";
  const site=r&&r.A!==r.B?(r.A>r.B?"A":"B"):((A||[]).reduce((s,x)=>s+x[1],0)>=(B||[]).reduce((s,x)=>s+x[1],0)?"A":"B");
  const UT={};for(const [c,w] of Object.entries(ew)){((TT[c]&&TT[c][site]&&TT[c][site].util)||[]).forEach(u=>{const k=u.type+"|"+u.land,o=UT[k]||(UT[k]={...u,share:0});o.share+=w*u.share})}
  const ut=Object.values(UT).filter(u=>u.share>=10&&(u.type==="smoke"||u.type==="molotov")&&u.t>=5).sort((a,b)=>b.share-a.share).slice(0,2);   // their smokes and mollies on that side, not the spawn ones
  const Wd=320,L=RLEN(),H=78+ut.length*7,base=H-14-ut.length*7,mx=Math.max(1,...(A||[]).map(x=>x[1]),...(B||[]).map(x=>x[1]));
  const X=t=>Math.round(Wd*t/L),Y=v=>Math.round(4+(base-6)*(1-v/mx));
  const path=c=>c.map(([t,v],i)=>`${i?"L":"M"}${X(t)} ${Y(v)}`).join(""),area=c=>`${path(c)}L${X(c[c.length-1][0])} ${base}L${X(c[0][0])} ${base}Z`;
  const S=site==="A"?A:B,pk=S?S.reduce((a,b)=>b[1]>a[1]?b:a):null,now=g.round_phase==="live"?(g.elapsed||0):null;
  const ticks=[[25,"1:30"],[55,"1:00"],[85,"0:30"]].map(([c,t])=>`<line x1="${X(c)}" y1="${base}" x2="${X(c)}" y2="${base+4}" stroke="var(--muted)"/><text x="${X(c)}" y="${H-1}" text-anchor="middle" class="vct">${t}</text>`).join("");
  const svg=`<svg class="vcurve" viewBox="0 0 ${Wd} ${H}" width="100%" height="${H}" role="img" aria-label="When the Ts are on each site">
    <line x1="0" y1="${base}" x2="${Wd}" y2="${base}" stroke="var(--line)"/>
    ${pk?`<rect x="${X(Math.max(0,pk[0]-6))}" y="0" width="${X(8)}" height="${base}" fill="var(--good)" fill-opacity=".22"/>`:""}
    ${[["B",B],["A",A]].filter(([,c])=>c).map(([s_,c])=>`<path d="${area(c)}" fill="${SITE_C[s_]}" fill-opacity="${s_===site?.28:.12}"/><path d="${path(c)}" fill="none" stroke="${SITE_C[s_]}" stroke-width="${s_===site?2.4:1.4}" stroke-linejoin="round" opacity="${s_===site?1:.7}"/>`).join("")}
    ${ut.map((u,i)=>`<rect x="${X(u.t)}" y="${base+2+i*7}" width="${Math.max(3,X(u.end)-X(u.t))}" height="5" rx="2" fill="${UCOL[u.type]||"#ccc"}"/>`).join("")}
    ${ticks}${now!=null?`<line x1="${X(now)}" y1="0" x2="${X(now)}" y2="${base}" stroke="#fff" stroke-width="1.6"/>`:""}</svg>`;
  // the one to hold (the hold card's best: your rounds won when it meets their hit, and when thrown early)
  // only the grenades you have (bought at the buy time: the best one to buy, marked so); none in the round: the window alone
  const held=["molotov","smoke","he"].filter(t=>((g.nades||{})[t]||0)>0),live_=g.round_phase==="live",NM={molotov:"molly",smoke:"smoke",he:"HE"};
  const UW=(M.util_war||{})[site],cand=((UW&&UW.util)||[]).filter(u=>u.met_t_won!=null&&(!held.length||held.includes(u.type))).sort((a,b)=>a.met_t_won-b.met_t_won);
  const h=held.length||!live_?cand[0]:null,sp=((UW&&UW.hits)||{}).spent,win=pk?`${clock(Math.max(0,pk[0]-6))}-${clock(pk[0]+2)}`:"";
  const what=h?`${NM[h.type]||h.type} ${esc(vShort(h.land||"?"))}${held.length?"":" (buy)"}`:held.length?held.map(t=>NM[t]).join("/"):"";
  const mine=what?`your ${what} ${win}${h?` · won ${100-h.met_t_won}%${sp?` vs ${100-sp[1]}% early`:""}`:""}`:`their arrival ${win}`;
  return vHead(`THEY'RE ON THE SITE · ${site} · OF ROUNDS`)+svg+`<div class="vleg"><span><i style="background:var(--good)"></i>${mine}</span>${ut.map(u=>`<span><i style="background:${UCOL[u.type]||"#ccc"}"></i>their ${u.type==="molotov"?"molly":u.type} ${esc(vShort(u.land||"?"))} ${clock(u.t)}</span>`).join("")}</div>`}
// CT: what to keep for their hit on the likely site: your rounds won when it meets their hit, and what thrown-early
// utility gives
function vHold(p,g,r){const M=(((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{},site=r&&r.A!==r.B?(r.A>r.B?"A":"B"):null,UW=site&&(M.util_war||{})[site];if(!UW)return "";
  const held=["molotov","smoke","he"].filter(t=>((g.nades||{})[t]||0)>0);
  const rows=(UW.util||[]).filter(u=>u.met_t_won!=null&&(!held.length||held.includes(u.type))).sort((a,b)=>a.met_t_won-b.met_t_won).slice(0,2);   // the grenades you have
  const sp=(UW.hits||{}).spent;if(!rows.length&&!sp)return "";
  return vHead(`⏳ HOLD FOR THEIR HIT · ${site} · WON`)+vRows([...rows.map(u=>({l:`${u.type==="molotov"?"molly":"smoke"} ${vShort(u.land||"?")}`,v:100-u.met_t_won,c:"var(--good)"})),
    ...(sp?[{l:"thrown early",v:100-sp[1],c:"var(--bad)",o:.7}]:[])])}
function vCTdots(p,g){const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[g.map],TP=(M&&M.tplan)||{},rt=advisedType(g);
  const su=(TP.setup||{})[rt==="pistol"?"pistol":rt]||(TP.setup||{}).all;if(!su||!su.top||!su.top.length)return "";const t=su.top[0];
  const dots=n=>"●".repeat(n)||"○";
  return vHead("CT SETUP · MOST USED")+`<div class="vdots"><span>A</span><b>${dots(t[0])}</b><em>|</em><span>B</span><b>${dots(t[1])}</b>${t[2]?`<em>|</em><span>mid</span><b>${dots(t[2])}</b>`:""}<small>${t[3]}% of rounds</small></div>`}
function vTchips(p,g){const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[g.map],TP=(M&&M.tplan)||{},P_=M&&M.plays,out=[];
  // a fake (first contact on one side, the hit on the other) against going straight: rounds won, both, always
  const fk=TP.fake||{};if(fk.switch&&fk.direct){const d=fk.switch[1]-fk.direct[1];out.push(`<span class="vchip ${d>=5?"good":d<=-5?"bad":""}">FAKE ${fk.switch[1]}% won <small>direct ${fk.direct[1]}%</small></span>`)}
  return out.length?`<div class="vchips">${out.join("")}</div>`:""}
// one option per line: the label, a bar (the longest is the most likely), the number. Fixed order for the sites,
// so the eye finds A and B at the same place every time
const SITE_C={A:"var(--siteA)",B:"var(--siteB)"};
const vHead=t=>`<div class="vhead">${t}</div>`;
function vRows(rows){const mx=Math.max(...rows.map(r=>r.v),1);
  return `<div class="vrows">${rows.map(r=>`<div class="vrow" style="--c:${r.c||"var(--ink)"}${r.o!=null&&r.o<1?`;opacity:${r.o}`:""}"><span>${r.l}</span><i><u style="width:${Math.max(4,Math.round(100*r.v/mx))}%"></u></i><b>${Math.round(r.v)}%</b></div>`).join("")}</div>`}
function vOdds(r,h){return vHead(h||"WHERE THEY GO · LIKELY")+`<div class="vodds">${vRows([{l:"A",v:r.A,c:SITE_C.A},{l:"B",v:r.B,c:SITE_C.B},{l:"?",v:r.none,c:"var(--muted)"}])}</div>`}
// a rush: how likely, and where it goes (the most likely in big, the second smaller and fainter)
function vRush(TS,g,r){const PLs=tsidePlays(TS,g.map,g,evFor(g),r);if(!PLs)return "";
  const rn=r.live?Math.round(100*calRush(PLs.rush)):r.rush,rs=(PLs.list||[]).filter(x=>/^rush/.test(x.p)).sort((a,b)=>b.v-a.v);
  if(rn<15||!rs.length)return "";
  const lab=x=>`${x.site} · ${vShort(String(x.label||"").replace(/^Rush [AB]( through )?/,""))}`;
  const lead=rs[0].v-((rs[1]||{}).v||0)>=.1;   // where it goes: only when one destination stands out (close numbers only overload)
  return `<div class="vbig ${rn>=40?"bad":"warn"}"><b>RUSH ${rn}%</b><span>likely · until ${clock(32)}${lead?` · ${esc(lab(rs[0]))}`:""}</span></div>`}
// where the fights are at this moment of the round (deaths of both sides in the base, on the likely site when the
// read leans one way): three zones, fainter as they get less likely
function vFights(M,g,r){const D=((M&&M.evidence)||{}).deaths;if(!D)return "";const w=WIN_OF(g.elapsed||0);
  const lean=r&&Math.abs(r.A-r.B)>=12?(r.A>r.B?"A":"B"):"all",acc={};let tot=0;
  for(const side of ["CT","T"]){const src=((D[side]||{})[lean]||{})[w]||((D[side]||{}).all||{})[w];if(!src)continue;
    src.zones.forEach(z=>{acc[z.zone]=(acc[z.zone]||0)+z.pct*src.n});tot+=src.n}
  const top=Object.entries(acc).sort((a,b)=>b[1]-a[1]).slice(0,3);if(!top.length||!tot)return "";
  return vHead("⚔ FIGHTS NOW · SHARE OF DUELS")+vRows(top.map(([z,v],i)=>({l:vShort(z),v:v/tot,c:"var(--ink)",o:[1,.75,.5][i]})))}
// before the round (CT): where the Ts come from, one entrance per line
function vEntries(TS,g,r){const PLs=tsidePlays(TS,g.map,g,evFor(g),r);if(!PLs)return "";
  const top=PLs.lanes.filter(L=>L.p>=0.05).sort((a,b)=>b.p-a.p);if(!top.length||top[0].p-((top[1]||{}).p||0)<.12)return "";   // one entrance stands out, or nothing
  return vHead("⇢ ENTRY · LIKELY")+vRows([{l:`${top[0].site} · ${vShort(top[0].name)}`,v:100*top[0].p,c:SITE_C[top[0].site]}])}
// the call you just made, as the coach understood it (it counts like a tap on the T read)
function vCall(g){const c=g&&g.call;if(!c||c.round!==g.round||Date.now()/1000-c.t>12)return "";
  const bits=[c.rush?"rush":"",c.n?String(c.n):"",c.site||"",c.zone?vShort(c.zone):"",c.bomb?"💣":""].filter(Boolean);
  return bits.length?`<span class="vchip good">🎙 ${esc(bits.join(" · "))}</span>`:""}
// your teammates' money, seen while you watched them last round: what they'll have now (≈: their kills not counted)
function vMates(g){const M=g.mates||{},prev=(g.round||0)-1;if(prev<1||halfStart(g.round)===g.round)return "";
  const R=((g.hist||{}).rounds||{})[prev]||{},won=R.win===g.side,L=g.losses||0,gain=won?ECON.win:ECON.bonus[Math.max(0,Math.min(L-1,4))],need=g.side==="CT"?3900:3700;
  const xs=Object.values(M).filter(m=>m.money!=null&&m.money_round===prev).map(m=>({n:m.name||"mate",v:Math.min(ECON.cap,m.money+gain)})).slice(0,3);
  return xs.map(x=>`<span class="vchip ${x.v>=need?"good":"bad"}">👥 ${esc(vShort(x.n))} ≈${kMoney(x.v)} ${x.v>=need?"✓":"✕"}</span>`).join("")}
// T: CTs pushing past a neutral zone, one line per zone (share of rounds, when); red: the push often gets a kill;
// once its moment is past, the line fades
// this match: the zones you called in the first 40 s of the rounds of this half, the ones seen in 2 rounds or more (the
// other team's habit: "they retake the banana every round"), share of the rounds of the half
function vEarlyMatch(g){const H=g.hist||{},Mk=H.marks||{},R=H.rounds||{},hs=halfStart(g.round||1),n=[];
  for(let r=hs;r<(g.round||0);r++)if((R[r]||{}).side===g.side||!(R[r]||{}).side)n.push(r);if(n.length<3)return "";
  const c={};n.forEach(r=>((Mk[r]||{}).early||[]).forEach(z=>c[z]=(c[z]||0)+1));
  const top=Object.entries(c).filter(([,k])=>k>=2).sort((a,b)=>b[1]-a[1]).slice(0,2);if(!top.length)return "";
  return vHead(`👁 THIS MATCH · EARLY CONTACT · ${n.length} ROUNDS`)+vRows(top.map(([z,k],i)=>({l:`${vShort(z)} · ${k}/${n.length}`,v:100*k/n.length,c:"var(--bad)",o:i?.75:1})))}
function vPush(p,g){const E=typeof ctPush==="function"?ctPush(p,g):null;if(!E||!E.gates.length)return "";const el=g.round_phase==="live"?(g.elapsed||0):0;
  const rows=E.gates.map((x,i)=>({l:`${vShort(x.gate||"?")} · ${clock(x.t)}`,v:x.share,c:x.kill>=30?"var(--bad)":"var(--ct)",o:el>x.t+6?.35:[1,.85,.7,.6][i]}));
  return vHead(`➜ CT PUSHES · ${E.label} · OF ROUNDS`)+vRows(rows)}
// after a frustrated moment (said "coach, énervé", a shout after your death or a lost round) or two rounds lost dead
// without a kill: one thing to do this round, from your own data (an early death: no dry peek; otherwise: the trade)
function resetWhy(g){if(g.round_phase!=="freezetime"||!g.hist)return null;const R=g.hist.rounds||{},Mk=g.hist.marks||{},cur=g.round,prev=cur-1;if(!(prev>=1))return null;
  const mk=n=>Mk[n]||{},frus=[prev,cur].some(n=>mk(n).mood==="frustration"||mk(n).heat),doubt=[prev,cur].some(n=>mk(n).mood==="doubt");
  const bad=n=>{const x=R[n]||{};return !!(x.win&&x.side&&x.win!==x.side&&x.dead!=null&&!(x.kills||[]).length)};
  const early=[prev,prev-1].some(n=>{const x=R[n]||{};return x.dead!=null&&x.dead<30});
  // the game before was a bad one, in the same session: the first rounds (2 to 5) are where it costs, from your matches
  const C=typeof P==="function"&&P()?(((P().advice||{}).plan||{}).carry):null,last=C&&C.last;
  const carry=last&&last.kind==="bad"&&g.round>=2&&g.round<=5&&halfStart(g.round)===1&&Date.now()-Date.parse(last.end)<3*3600e3&&C.bad.adr_first<C.bad.adr_rest-5;
  return frus?{k:"frus",early}:bad(prev)&&bad(prev-1)?{k:"bad",early}:doubt?{k:"doubt",early}:carry?{k:"carry",early:true,C}:null}
// the simple plan of the round: T, path 1 and when to be on the site; CT, your spot of the buy card
function simplePlan(p,g){if(g.side==="T"){const W=typeof winsRank==="function"?winsRank(p,g):null,r=W&&W.rows[0];if(!r)return null;
    const ps=pathShort(p,g,r),pts=(r.route||{}).pts,end=pts&&pts[pts.length-1],tm=r.timing,win=tm&&tm.win-tm.mean>=3;
    return {head:ps.head,via:ps.via,lo:win?tm.lo:null,hi:win?tm.hi:null,at:!win&&end&&end[3]!=null?end[3]:null}}
  const KB=(((((p.advice.plan||{}).buys||{}).maps||{})[g.map]||{})[g.side]||{}),k=KB[advisedType(g)]||KB.full||{};
  return k.zone?{spot:k.zone.key}:null}
function vReset(p,g){const w=resetWhy(g);if(!w)return "";
  if(w.k==="doubt"){const sp=simplePlan(p,g);if(!sp)return "";
    return `<div class="vreset plan"><b>PLAN</b><span>${sp.spot?`📍 ${vShort(sp.spot)} · molly for their arrival`:`${esc(sp.head)}${sp.via?` via ${esc(sp.via)}`:""} · ${sp.lo!=null?`on site ${clock(sp.lo)}-${clock(sp.hi)}`:sp.at!=null?`on site ~${clock(sp.at)}`:""}`}</span></div>`}
  if(w.k==="carry")return `<div class="vreset"><b>CALM START</b><span>👥 play the trade · ✕ no dry peek before ${clock(30)}</span><small>after a bad game · ADR rounds 2-5 ${w.C.bad.adr_first} vs ${w.C.bad.adr_rest} later</small></div>`;
  const MS=(p.advice.plan||{}).mood,A_=MS&&MS.after,O_=MS&&MS.other;   // what a tilt costs you: rounds won first, else damage
  const data=A_&&O_?(O_.won-A_.won>=3?`<small>after a tilt · won ${A_.won}% vs ${O_.won}%</small>`:O_.adr-A_.adr>=5?`<small>after a tilt · ADR ${A_.adr} vs ${O_.adr}</small>`:""):"";
  return `<div class="vreset"><b>RESET</b><span>${w.early?`✕ no dry peek before ${clock(30)}`:"👥 play the trade: next to a mate"}</span>${data}</div>`}
// ---------- the coach's voice at the buy time: a few seconds in French, once per round, when the reset or plan card
// shows. A local Windows voice only (Julie, Paul, Hortense: nothing leaves the PC); the browser lets a page speak only
// after one click on it ----------
const VOICE={said:null};
function voiceOn(){try{return localStorage.getItem("coach_voice")!=="off"}catch(e){return true}}
function frVoice(){const vs=(window.speechSynthesis&&speechSynthesis.getVoices())||[];
  return vs.find(v=>/^fr/i.test(v.lang)&&v.localService&&/Julie|Paul|Hortense/.test(v.name))||vs.find(v=>/^fr/i.test(v.lang)&&v.localService)||null}
function coachSay(t){if(!window.speechSynthesis)return false;const v=frVoice();if(!v)return false;
  const u=new SpeechSynthesisUtterance(t);u.voice=v;u.lang=v.lang;u.rate=1.08;speechSynthesis.cancel();speechSynthesis.speak(u);return true}
const sayClock=t=>{const c=clock(t).split(":");return +c[0]?`${c[0]} minute ${+c[1]}`:`${+c[1]} secondes`};
function coachVoice(p,g){if(!voiceOn()||!g||g.practice)return;const w=resetWhy(g);if(!w)return;const key=[g.map,g.round,w.k].join("|");if(VOICE.said===key)return;
  if(navigator.userActivation&&!navigator.userActivation.hasBeenActive)return;   // no click on the page yet: the browser would refuse
  const pick=a=>a[Math.floor(Math.random()*a.length)];
  const instr=w.early?`pas de peek sec avant ${sayClock(30)}`:"joue le trade, à côté d'un coéquipier";
  let t;
  if(w.k==="carry"){if(VOICE.carry===g.map)return;VOICE.carry=g.map;   // once per match
    if(coachSay(`Nouvelle partie. La dernière était dure : on démarre calme. Joue le trade, pas de peek sec avant ${sayClock(30)}.`))VOICE.said=key;return}
  if(w.k==="doubt"){const sp=simplePlan(p,g);if(!sp)return;
    t=sp.spot?`Plan simple : ton spot, ${String(sp.spot).split(" / ")[0]}, et ta molly pour leur arrivée.`
      :`Plan simple : ${sp.head}${sp.via?` par ${sp.via.replace(/ > /g,", ")}`:""}${sp.lo!=null?`, sur le site entre ${sayClock(sp.lo)} et ${sayClock(sp.hi)}`:sp.at!=null?`, sur le site vers ${sayClock(sp.at)}`:""}.`}
  else{const MS=(p.advice.plan||{}).mood,dw=MS&&MS.after&&MS.other?MS.other.won-MS.after.won:0,drop=MS&&MS.after&&MS.other&&MS.other.adr?Math.round(100*(1-MS.after.adr/MS.other.adr)):0;
    t=w.k==="frus"?pick([`Respire. Le round d'avant est fini. Ce round, ${instr}.`,`On reset. Une info utile, puis ${instr}.`])
      :pick([`Deux rounds compliqués, ça arrive. Ce round, ${instr}.`,`On repart simple : ${instr}.`]);
    if(VOICE.data!==g.map&&(dw>=3||drop>=10)){t+=dw>=3?` Après un tilt, tu gagnes ${dw} rounds sur cent de moins : joue simple.`:` Après un tilt, tes dégâts baissent de ${drop} pour cent : joue simple.`;VOICE.data=g.map}}
  if(VOICE.last&&VOICE.last.map===g.map&&w.k!=="doubt"&&g.round-VOICE.last.round<3){VOICE.said=key;return}   // a reset at most every 3 rounds: not a sermon each round
  if(coachSay(t)){VOICE.said=key;if(w.k!=="doubt")VOICE.last={map:g.map,round:g.round}}}
// T: the site left open by what you called in the last 25 s (two CTs or more on one side and none on the other, or a
// site said clear): where the bomb should go
function vOpen(g){if(g.side!=="T"||g.bomb==="planted"||!g.seen||g.seen.round!==g.round)return "";
  const now=Date.now()/1000,cs=(g.seen.calls||[]).filter(c=>now-c.t<=25);if(!cs.length)return "";
  const n={A:0,B:0},clear={A:false,B:false};
  cs.forEach(c=>{if(c.clear&&c.site){clear[c.site]=true;return}
    const regs=c.regs&&c.regs.length?c.regs:(c.site?[c.site]:[]);
    if(regs.length===1)n[regs[0]]+=c.n||1;else regs.forEach(x=>n[x]+=1)});
  const open=["A","B"].find(s=>{const o=s==="A"?"B":"A";return (clear[s]||(n[o]>=2&&n[s]===0))&&!clear[o]&&!n[s]});
  if(!open)return "";const o=open==="A"?"B":"A",age=Math.round(now-Math.max(...cs.map(c=>c.t)));
  return `<div class="vbig good"><b>${open} OPEN</b><span>go ${open} · ${n[o]?`${n[o]} seen ${o}`:`${open} clear`} · ${age}s ago</span></div>`}
// T: when the CTs push past a neutral zone, the Ts' rounds won by their answer (the site, fast or late), at equal
// economy. Buy time: the most likely push (15% of rounds or more); in the round: the zone you just called
function vPushAns(p,g,live){if(g.side!=="T")return "";const PA=((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).push_answers;if(!PA)return "";
  const called=(g.seen&&g.seen.round===g.round?g.seen.calls||[]:[]).map(c=>c.zone).filter(Boolean);
  let A=called.length?PA.find(a=>called.some(z=>z===a.gate||String(a.gate).includes(z)||String(z).includes(a.gate))):null;
  if(!A&&!live){const E=typeof ctPush==="function"?ctPush(p,g):null,top=E&&E.gates[0];if(top&&top.share>=15)A=PA.find(a=>a.gate===top.gate)}
  if(!A)return "";
  return vHead(`IF THEY PUSH ${vShort(A.gate)} · WON`)+vRows(A.answers.slice(0,2).map((a,i)=>({l:`${a.site} ${a.tempo==="fast"?`fast ›${clock(45)}`:`late ‹${clock(45)}`}`,v:a.won,c:SITE_C[a.site],o:i?.7:1})))}
// the zones to check on a path: the enemy spots within 90 px of its way (bomb maps: where the CTs stand and the angles
// they kill from at that moment; hostage maps: where the Ts hold and the spots they kill CTs from), kill spots first
function focusChecks(p,g,r){if(!r||!r.route||!r.route.pts)return [];const pts=r.route.pts,near=s=>s&&s.px&&pts.some(q=>Math.hypot(q[0]-s.px[0],q[1]-s.px[1])<90&&(!s.level||!q[2]||s.level===q[2]));
  let hold=[],dang=[];
  if(isHostage(g.map)){const H=((p.advice.plan||{}).hostage||{})[g.map]||{};hold=H.holds||[];dang=H.danger||[]}
  else{const CS=((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).ct_spots||{},el=g.round_phase==="live"?(g.elapsed||0):0,tt=Math.max(el+15,20),W=CS[tt<20?"early":tt<40?"setup":tt<70?"hit":"late"]||CS.setup||{};hold=W.hold||[];dang=W.danger||[]}
  const out=[],seen=new Set();
  [...dang.filter(near).map(s=>({zone:s.zone,d:true})),...hold.filter(near).map(s=>({zone:s.zone,d:false}))].forEach(z=>{if(z.zone&&!/spawn/i.test(z.zone)&&!seen.has(z.zone)){seen.add(z.zone);out.push(z)}});
  return out.slice(0,4)}
// the focus on the path you pressed: the path, when to be there, your grenades for it, the zones to check
function vFocus(p,g){const n=focusN(g);if(!n)return "";const H=isHostage(g.map),W=H?hostageRank(p,g):typeof winsRank==="function"?winsRank(p,g):null,r=W&&W.rows.find(x=>x.rank===n);if(!r)return "";
  let head,when;
  if(H){head=`Hostages via ${r.route.zones.slice(-2).join(" > ")}`;when=`there ~${clock(r.t_end)}`}
  else{const ps=pathShort(p,g,r),pts=(r.route||{}).pts,end=pts&&pts[pts.length-1];head=`${ps.head}${ps.via?` via ${ps.via}`:""}`;when=onSite(r.timing,end)}
  const nd=vNades(vNadePicks(p,g)),chk=focusChecks(p,g,r),ps=vPathStuff(p,g,r);
  return `<div class="vfocus" style="--c:${r.col}"><b>${n}</b><div><span>${esc(head)}</span><small>${esc(when||"")}${r.wr!=null?` · ${Math.round(r.wr)}% won`:""}</small></div><em title="numpad minus drops the focus">− off</em></div>
    ${nd}${ps}${chk.length?`<div class="vchips">${chk.map(z=>`<span class="vchip ${z.d?"bad":""}">${z.d?"⚠":"👁"} ${vShort(z.zone)}</span>`).join("")}</div>`:""}`}
// the path you pressed: every lineup of the base that lands on its site or along it, the best first (6 at most)
function vPathStuff(p,g,r){const E=((((p.advice.plan||{}).nades||{}).maps||{})[g.map]||{})[g.side],P=(E&&E.pool)||[];const pts=r&&r.route&&r.route.pts;if(!P.length||!pts)return "";
  const GEO=((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).geo,sk=(r.k.match(/[AB]$/)||r.k.match(/^[AB]/)||[])[0],S=GEO&&GEO.sites&&sk?GEO.sites[sk]:null,end=pts[pts.length-1];
  const lvOK=(a,b)=>!a||!b||a===b,near=(a,d,lv)=>a&&pts.some(q=>Math.hypot(q[0]-a[0],q[1]-a[1])<d&&lvOK(lv,q[2]));
  const fit=x=>{if(!x.to_px||x.post>=50)return 0;const lv=x.land_level||x.level;
    if((S&&Math.hypot(x.to_px[0]-S.px[0],x.to_px[1]-S.px[1])<190&&lvOK(lv,S.level))||(end&&Math.hypot(x.to_px[0]-end[0],x.to_px[1]-end[1])<170&&lvOK(lv,end[2])))return 2;
    return near(x.to_px,60,lv)&&near(x.from_px,140,x.level)?1:0};
  const L=P.map(x=>({x,f:fit(x)})).filter(o=>o.f).sort((a,b)=>b.f-a.f||b.x.score-a.x.score).slice(0,6).map(o=>o.x);if(!L.length)return "";
  return `<div class="vstuff">${L.map(x=>`<span style="--c:${NADE_C[x.type]||"#ccc"}"><i>${vLetter[x.type]||"?"}</i>${vShort(x.to)}<small>${esc(x.from||"")} · ${esc(x.how||"")}${x.timer?` · ${x.timer}`:""}</small></span>`).join("")}</div>`}
// hostage maps: the CTs' ways (attack: rounds won; defense: share of the CT walks, where they come from)
function vHostRoutes(p,g,def){const W=hostageRank(p,g);if(!W)return "";
  return vHead(def?"THEY COME FROM · OF CT WALKS":"YOUR WAYS · ROUNDS WON")+vRows(W.rows.map((r,i)=>({l:`${r.rank} · ${vShort(r.route.zones.slice(-2).join(" > "))} · ${clock(r.t_end)}`,v:def?r.share:r.wr,c:r.col,o:[1,.8,.65][i]})))}
// a lineup book of the map (made by a player: where to stand, where to aim): the lineups of the site you go to for the
// grenades you have (none yet at the buy time: the site's), two at most, as the aim picture and the title
function bookFor(p,g,r){const B=((p.advice.plan||{}).lineups||{})[g.map];if(!B||!(B.lineups||[]).length)return null;let sites=[];
  if(g.side==="T"){const W=typeof winsRank==="function"?winsRank(p,g):null,RF=W&&(W.rows.find(x=>x.rank===focusN(g))||W.rows[0]);
    const s=RF?(RF.k.match(/[AB]$/)||RF.k.match(/^[AB]/)||[])[0]:null;if(s)sites.push(s);if(RF&&((RF.route||{}).zones||[]).some(z=>/mid/i.test(z)))sites.push("Mid")}
  else{if(r&&r.A!==r.B)sites.push(r.A>r.B?"A":"B");else sites.push("A","B")}
  const held=Object.entries(g.nades||{}).filter(([t,v])=>v>0).map(([t])=>t);
  const L=B.lineups.filter(x=>x.side===g.side&&sites.includes(x.site)&&(!held.length||held.includes(x.type)));
  const pri=g.side==="CT"?["molotov","smoke","flash","he"]:["smoke","flash","molotov","he"];   // CT: the molly first (it buys time), T: the smoke
  return L.length?{book:B,list:L.sort((a,b)=>sites.indexOf(a.site)-sites.indexOf(b.site)||pri.indexOf(a.type)-pri.indexOf(b.type)).slice(0,2)}:null}
function vBook(p,g,r){const F=bookFor(p,g,r);if(!F)return "";
  return vHead(`📖 LINEUPS · ${esc(F.book.author)}`)+`<div class="vbook">${F.list.map(x=>`<a href="${esc(x.link)}" target="_blank" rel="noopener" title="${esc([x.position,x.aim].filter(Boolean).join(" · "))}"><img src="${esc(x.img_aim||x.img_position||"")}" alt="" loading="lazy"><span><b style="color:${NADE_C[x.type]||"#ccc"}">${vLetter[x.type]||"?"}</b> ${esc(x.title.replace(/\s*(smoke|flash|molly)$/i,""))}${x.throw?` <em>${esc(x.throw.toLowerCase())}</em>`:""}</span><small>${esc(x.position||"")}</small></a>`).join("")}</div>`}
// you just died: the info, now (where, how many, how hurt). Your rounds with a call before your death are won far
// more often; a few seconds of a big reminder, and the voice once per round (setting "Say 'info' when I die")
function deadAgo(g){const R=(((g.hist||{}).rounds||{})[g.round])||{};return g.round_phase==="live"&&R.dead!=null?(g.elapsed||0)-R.dead:null}
function calledSince(g,a){const c=g&&g.call;return !!(c&&c.round===g.round&&c.t>=Date.now()/1000-a-.5)}   // you gave an info after your death
// CT: numpad 7 (A) / 9 (B): the site you play this round
const mySite=g=>{const s=(((g.hist||{}).marks||{})[g.round]||{}).me_site;return s==="A"||s==="B"?s:null};
function vMySite(p,g){const s=mySite(g);if(!s)return "";const E=(((p.advice.plan||{}).nades||{}).maps||{})[g.map],C=E&&E.CT,L=(C&&C.lanes)||{};
  const TS=(p.advice.plan||{}).tside,M=((TS||{}).maps||{})[g.map]||{},GS=(M.geo||{}).sites||{},S=GS[s];
  // the stuff of the site, entrance by entrance (the grenades that close each entrance of the Ts)
  const st=[];Object.entries(L).filter(([k])=>k[0]===s).forEach(([k,o])=>["smoke","molotov","flash","he"].forEach(t=>{const x=o[t];if(x&&st.length<5&&!st.some(y=>y.to===x.to&&y.type===t))st.push({...x,type:t})}));
  const holds=(((M.ct_spots||{}).early||{}).hold||[]).filter(h=>S&&Math.hypot(h.px[0]-S.px[0],h.px[1]-S.px[1])<260&&(!h.level||!S.level||h.level===S.level)).slice(0,3);
  return `<div class="vfocus" style="--c:#5ab4ff"><b>${s}</b><div><span>You hold ${s}</span><small>numpad 7 A · 9 B</small></div></div>
   ${st.length?`<div class="vchips">${st.map(x=>`<span class="vchip" style="border-color:${NADE_C[x.type]||"#ccc"}">${vLetter[x.type]||"?"} ${vShort(x.to)} <small>${esc(x.from||"")}${x.timer?` · ${x.timer}`:""}</small></span>`).join("")}</div>`:""}
   ${holds.length?`<div class="vchips">${holds.map(h=>`<span class="vchip">🛡 ${vShort(h.zone)}</span>`).join("")}</div>`:""}`}
// the post-plant / retake grenades of a side that land on that site (the base's: every lineup thrown after a plant)
function postStuff(p,g,side,site){const E=((((p.advice.plan||{}).nades||{}).maps||{})[g.map]||{})[side],S=(((((p.advice.plan||{}).tside||{}).maps||{})[g.map]||{}).geo||{}).sites||{},c=S[site];
  if(!E||!c)return [];const at=x=>x.to_px&&Math.hypot(x.to_px[0]-c.px[0],x.to_px[1]-c.px[1])<230&&(!x.land_level||!c.level||x.land_level===c.level);
  const L=[];Object.entries(E.types||{}).forEach(([t,v])=>(v.post||[]).forEach(x=>L.push({...x,type:t})));(E.pool||[]).filter(x=>(x.post||0)>=30).forEach(x=>L.push(x));
  return L.filter(at).filter((x,i,a)=>a.findIndex(y=>y.type===x.type&&y.to===x.to&&y.from===x.from)===i).sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,3)}
// T after the plant on a site you gave (numpad 7 / 9, or said): where to hold, the post-plant stuff
function vPostPlant(p,g,site){const PP=((((((p.advice.plan||{}).tside||{}).maps||{})[g.map])||{}).postplant||{})[site];
  const post=postStuff(p,g,"T",site);
  const hs=((PP||{}).holds||[]).slice(0,3);if(!hs.length&&!post.length)return "";
  return `${vHead(`POST-PLANT ${site} · ROUNDS WON FROM THERE`)}${vRows(hs.map((h,i)=>({l:`${vShort(h.zone||"Hold")}${i?"":" ★"} · ${h.n}×`,v:h.win,c:"var(--good)",o:[1,.8,.65][i]})))}
   ${post.length?`<div class="vchips">${post.map(x=>`<span class="vchip" style="border-color:${NADE_C[x.type]||"#ccc"}">${vLetter[x.type]||"?"} ${vShort(x.to)} <small>${esc(x.from||"")}</small></span>`).join("")}</div>`:""}`}
// CT after the plant: the retake. The spots to check (where Ts hold after a plant there), the way from your site, the stuff
function vRetake(p,g,site){const TS=(p.advice.plan||{}).tside,M=((TS||{}).maps||{})[g.map]||{},PP=((M.postplant||{})[site]||{}).holds||[];
  const me=mySite(g),o=site==="A"?"B":"A",R=me&&me!==site&&typeof rotationFor==="function"?rotationFor(M,site,`${o} Site`,M.geo):null,rt=R&&R.routes&&R.routes[0];
  const post=postStuff(p,g,"CT",site);
  const zs=[...new Set(PP.slice(0,4).map(h=>h.zone).filter(Boolean))];
  return `<div class="vbig warn"><b>RETAKE ${site}</b><span>${rt?`from ${o}: ${rt.travel!=null?`${Math.round(rt.travel)} s · `:""}${rt.died}% die on the way · `:""}together, with utility</span></div>
   ${zs.length?`<div class="vchips">${zs.map(z=>`<span class="vchip bad">⚠ check ${vShort(z)}</span>`).join("")}</div>`:""}
   ${post.length?`<div class="vchips">${post.map(x=>`<span class="vchip" style="border-color:${NADE_C[x.type]||"#ccc"}">${vLetter[x.type]||"?"} ${vShort(x.to)} <small>${esc(x.from||"")}</small></span>`).join("")}</div>`:""}`}
// this match's peek timings: the zones you called at the same moment (±8 s) in two rounds or more of this half and side;
// el: now (live: only the ones still to come), null at the buy time
function vPeekTimes(g,el){const H=g.hist||{},Mk=H.marks||{},R=H.rounds||{},hs=halfStart(g.round||1),by={};
  for(let r=hs;r<(g.round||0);r++){if((R[r]||{}).side&&(R[r]||{}).side!==g.side)continue;((Mk[r]||{}).seen_t||[]).forEach(([z,e])=>{if(e!=null)(by[z]=by[z]||[]).push(e)})}
  const out=[];Object.entries(by).forEach(([z,ts])=>{ts.sort((a,b)=>a-b);let best=null;
    ts.forEach(t=>{const near=ts.filter(u=>Math.abs(u-t)<=8);if(near.length>=2&&(!best||near.length>best.n))best={n:near.length,t:near[Math.floor(near.length/2)]}});
    if(best&&(el==null||best.t>el-3))out.push({z,...best})});
  if(!out.length)return "";out.sort((a,b)=>a.t-b.t);
  return `<div class="vchips">${out.slice(0,3).map(o=>`<span class="vchip warn">⏱ ${vShort(o.z)} ~${clock(o.t)} ×${o.n}</span>`).join("")}</div>`}
// the round after this one, at the round's end: the buy the money calls for (the only look ahead of the panel, 05/10)
function nextBuy(p,g){if(!g||g.round==null||!g.side||g.practice)return null;const n=g.round+1;
  if(n===halfStart(n))return "pistol round";
  const pl=econPlan(p,Object.assign({},g,{round:n,round_phase:"freezetime"}));
  return pl&&pl.best?({eco:"eco",half:"half buy",force:"force buy",full:"full buy"}[pl.best.k]||esc(pl.best.k)):null}
function vInfo(g){const a=deadAgo(g);return a!=null&&a>=2.5&&a<=9&&!calledSince(g,a)?`<div class="vbig warn"><b>📣 INFO</b><span>where · how many · how hurt</span></div>`:""}
function infoOn(){try{return localStorage.getItem("coach_info")!=="off"}catch(e){return true}}
function coachInfo(g){if(!g||g.practice||!voiceOn()||!infoOn())return;const a=deadAgo(g);if(a==null||a<3||a>6||calledSince(g,a))return;const key=[g.map,g.round,"info"].join("|");   // 3 s after: the time to take your death in
  if(VOICE.info===key||(navigator.userActivation&&!navigator.userActivation.hasBeenActive))return;if(coachSay("L'info !"))VOICE.info=key}
const expOn=(p,t)=>(((((p||{}).advice||{}).plan||{}).experiments||{}).experiments||[]).some(e=>e.status==="active"&&e.template===t);
// the panel's slots, top to bottom. One slot per kind of info: the ones that never show together share it (before the
// plant your site, after it the retake; T plant timer / bomb down / CT rotation), the ones that can show together have
// their own (a call understood and "l'info")
const SLOTS=["call","info","alert","reset","key","focus","read","play","hold","book","peek","early","eco","evid","tchips"];
// the height each slot reached in this phase (buy time, live, end), for this map and side: kept the whole half, so after
// a round nothing moves any more
const SLOTH={key:"",h:{}};
const SLOT_EMPTY={call:"🎙 call",info:"📣 info",alert:"💣 bomb · rotation"};   // a reserved slot waiting: a faint frame
function slotted(g,P){const k=`${g.map}|${g.side}|${g.round_phase}`;if(SLOTH.key!==k){SLOTH.key=k;SLOTH.h={}}
  // live: the alerts keep their room from the start of the round (a call when the mic listens, l'info while alive)
  const R=g.round_phase==="live"?{alert:68,info:68,call:g.mic?40:0}:{};
  return SLOTS.map(s=>{const html=(P[s]||[]).filter(Boolean).join(""),mh=Math.max(SLOTH.h[s]||0,R[s]||0);
    if(!html&&!mh)return "";
    return `<div class="vslot${html?"":" wait"}" data-slot="${s}" style="min-height:${mh}px">${html?`<div class="vslot-in">${html}</div>`:SLOT_EMPTY[s]?`<span>${SLOT_EMPTY[s]}</span>`:""}</div>`}).join("")}
// after the page is drawn: each slot's height in this phase (its room for the next draws)
function slotMeasure(root){(root?root.querySelectorAll(".vslot:not(.wait)"):[]).forEach(el=>{const s=el.dataset.slot,h=el.firstElementChild?el.firstElementChild.offsetHeight:0;
  if(h>(SLOTH.h[s]||0))SLOTH.h[s]=h})}
function nowVisual(p,g,following){
  if(!following)return nowPanel(p,g,following,{noBuy:true});
  if(g.practice)return `<div class="vz"><div class="vsit"><span>PRACTICE</span></div></div>`;
  if(g.map_phase==="warmup"&&typeof briefVisual==="function")return briefVisual(p,g);   // the map loads: the 60-second brief
  const ph=g.round_phase,ct=g.side==="CT",P={},put=(s,...h)=>{(P[s]=P[s]||[]).push(...h)};
  const TS=(p.advice.plan||{}).tside,r=ct?tsidePredict(TS,g.map,g,evFor(g)):null;
  if(ph==="freezetime"){put("reset",vReset(p,g));put("key",vKey(p,g));
    if(voiceOn()&&navigator.userActivation&&!navigator.userActivation.hasBeenActive)put("call",`<span class="vchip">🔊 click this page once so I can talk</span>`);
    if(typeof antiEco==="function"&&antiEco(p,g))put("eco",`<span class="vchip bad">! eco kill spots on the map: clear them, no close duel</span>`);
    if(ct)put("focus",vMySite(p,g));
    put("peek",vPeekTimes(g,null));
    if(ct&&r){put("read",vOdds(r));put("play",vRush(TS,g,r)||vEntries(TS,g,r));put("hold",vCTline(p,g,r)||vHold(p,g,r));put("book",vBook(p,g,r))}
    const HM=isHostage(g.map);if(HM)put("focus",ct?(vFocus(p,g)||vHostRoutes(p,g,false)):vHostRoutes(p,g,true));
    if(!ct&&!HM){put("focus",vFocus(p,g)||vPathCurve(p,g)||vTimeline(p,g));put("book",vBook(p,g,null));put("early",vEarlyMatch(g));
      put("play",vPush(p,g));put("hold",vPushAns(p,g,false));put("tchips",vTchips(p,g))}}   // the plays and the grenades are on the map
  else if(ph==="live"){const el=g.elapsed||0,planted=g.bomb==="planted",dead=deadAgo(g)!=null;put("call",vCall(g));   // dead (05/10): what helps to call stays, your own path and spot go
    put("info",vInfo(g)||(dead&&!planted?`<div class="vsit dead"><span>YOU'RE OUT</span><b>call what your teammate can't see</b></div>`:""));
    if(planted){const left=g.phase_left!=null?g.phase_left:Math.max(0,40-(g.since_plant||0)),as=typeof autoSite==="function"?autoSite(p,g):null;
      put("alert",`<div class="vbig ${ct?"bad":"good"}"><b>💣 ${Math.ceil(left)}s</b><span>${ct?"retake together":"hold the bomb"}${as?` · ${as.site} site, ${as.said?"you said it":`${as.p}% sure`}`:" · numpad 7 A / 9 B"}</span></div>`);
      if(as&&(as.said||as.p>=70))put("focus",ct?vRetake(p,g,as.site):vPostPlant(p,g,as.site))}
    else if(isHostage(g.map))put("focus",ct?(vFocus(p,g)||(el<45?vHostRoutes(p,g,false):"")):(el<45?vHostRoutes(p,g,true):""));
    else if(ct){if(!dead)put("focus",vMySite(p,g));put("peek",vPeekTimes(g,el));if(r){put("read",vOdds(r));
        const M=TS&&TS.maps&&TS.maps[g.map];
        put("play",(el<32?vRush(TS,g,r):"")||vFights(M,g,r));
        if(el>=15&&el<=80&&Math.max(r.A,r.B)>=70&&typeof rotationFor==="function"){const X=r.A>r.B?"A":"B",o=X==="A"?"B":"A",R=rotationFor(M,X,`${o} Site`,M.geo),rt=R&&R.routes&&R.routes[0];
          const me=mySite(g);   // where you said you are this round (numpad 7 / 9, or said)
          if(rt&&me!==X)put("alert",`<div class="vbig warn"><b>${o} → ${X}</b><span>${me===o?`you're ${o}: rotate now`:`if you hold ${o}: rotate`} · ${rt.travel!=null?`${Math.round(rt.travel)} s · `:""}${rt.died}% die on the way</span></div>`)}   // the hit leans hard to one site
        if(el<75&&!dead)put("hold",vCTline(p,g,r)||(el<60?vHold(p,g,r):""));
        (r.evid||[]).filter(x=>/spot/.test(x)).slice(0,2).forEach(ev=>put("evid",`<span class="vchip ${/fight/.test(ev)?"bad":""}">● ${esc(ev)}</span>`))}}
    else{put("read",vOpen(g));put("peek",vPeekTimes(g,el));if(!dead)put("focus",vFocus(p,g)||vPathCurve(p,g)||vTimeline(p,g));
      put("play",(el<45&&!dead&&vPush(p,g))||vFights(TS&&TS.maps&&TS.maps[g.map],g,null));if(!dead)put("hold",el<50?vPushAns(p,g,true):"");
      const left=g.phase_left!=null?g.phase_left:Math.max(0,RLEN()-el);
      if(left<=45)put("alert",`<div class="vbig bad"><b>PLANT ${Math.floor(left/60)}:${String(Math.floor(left%60)).padStart(2,"0")}</b><span>${left>20?"commit now":"plant or save"}</span></div>`);
      else if(!dead)put("tchips",vTchips(p,g))}}
  else if(ph==="over"){const nx=nextBuy(p,g);put("call",`<div class="vsit"><span>ROUND ${g.round}</span>${g.win_team?`<b class="${g.win_team===g.side?"good":"bad"}">${g.win_team===g.side?"WON":"LOST"}</b>`:""}</div>${nx?`<div class="vnext">Next round · <b>${nx}</b></div>`:""}`)}
  const html=slotted(g,P);
  return `<div class="vz">${html||`<div class="vsit"><span>ROUND ${g.round||""}</span></div>`}</div>`}
// the buy notification of the full-screen view: one compact card, no paragraph, never scrolls
// the grenades to buy, for the two economies. CT: molly and smoke first (a hit that meets one still burning or
// standing costs the Ts 10 to 20 points of rounds won, every map together), the molly ahead when a rush is likely, with
// what it does to a rush; T against eco CTs: flash and molly first, for the close spots where they wait
function nadeCtx(p,g,E){if(!E||!E.order||!E.order.length)return {E,chip:""};
  const TS=(p.advice.plan||{}).tside||{},UE=TS.util_econ||{},ew=econW(p,g),low=(ew.pistol||0)+(ew.low||0);
  const re=first=>({...E,order:[...first.map(t=>E.order.find(o=>o.type===t)).filter(Boolean),...E.order.filter(o=>!first.includes(o.type))]});
  if(g.side==="CT"){const r=TS.maps?tsidePredict(TS,g.map,g,evFor(g)):null,rush=r?r.rush>=30:low>=.5,U=UE.rush;
    const chip=rush&&U&&U.active&&U.kept?`<span class="vchip good">🔥 molly/smoke on the rush · won ${100-U.active[1]}% · ${100-U.kept[1]}% without</span>`:"";
    return {E:re(rush?["molotov","smoke"]:["smoke","molotov"]),chip}}   // against a full buy, the hold card says when
  const ae=typeof antiEco==="function"&&antiEco(p,g);
  return {E:ae||(ew.low||0)>=.6?re(["flash","molotov"]):E,chip:""}}
function buyVisual(p,g){if(g.money==null||!g.side||g.practice)return "";const rt=advisedType(g),PL=p.advice.plan||{},N=PL.nades,NC=nadeCtx(p,g,N&&((N.maps||{})[g.map]||{})[g.side]),E=NC.E;
  const KB=((((PL.buys||{}).maps||{})[g.map]||{})[g.side]||{}),sk=sitKey(p,g),kit=(sk&&sk.endsWith("anti_eco")&&KB["anti-eco"])||KB[rt]||{};
  const full=g.side==="CT"?3900:3700,bonus=[1400,1900,2400,2900,3400][Math.min(g.losses||0,4)];
  const haveRifle=g.primary&&FULL_W.has(g.primary),tags=[];
  const plan=typeof econPlan==="function"?econPlan(p,g):null,bk=plan&&plan.best?plan.best.k:null;
  const ae=typeof antiEco==="function"&&antiEco(p,g);
  const RT=ae&&bk!=="eco"?"ANTI-ECO":(bk?{eco:"ECO · SAVE",half:"HALF BUY",force:"FORCE",full:"FULL BUY"}[bk]:{pistol:"PISTOL",eco:"ECO · SAVE",force:"FORCE",full:"FULL BUY"}[rt])||"BUY";
  // a key round: the card's weapon (the same as the key-round card of the panel), never another one
  const ks=typeof keySit==="function"?keySit(p,g):null,kw=ks?keyWeapons(p,g,ks):null,kp=kw&&kw.list.find(w=>!DEF_PISTOL.has(w.w)&&(W_PRICE[w.w]??99999)<=(ks==="force_full"?g.money:kw.budget));
  if(ks==="pistol"){const top=kw&&kw.list[0];tags.push(top&&!DEF_PISTOL.has(top.w)?`<span class="vtag">🔑 ${esc(W_SHORT[top.w]||top.w.toUpperCase())}</span>`:`<span class="vtag">kevlar</span>`)}
  else if(ks&&kp&&!haveRifle)tags.push(`<span class="vtag">🔑 ${esc(W_SHORT[kp.w]||kp.w.toUpperCase())}${kp.exp?" 🧪":""}</span>`,...(ks==="force_full"?[`<span class="vtag">kevlar</span>`]:[]));
  else if(bk==="eco")tags.push(`<span class="vtag">save: buy nothing</span>`);   // the plan says save: no weapon to tempt you
  else if(g.side==="CT"&&rt==="full"&&!haveRifle&&expOn(p,"full_rifle_ct"))tags.push(`<span class="vtag">M4 🧪</span><span class="vtag">kevlar + helmet</span>`);   // the experiment: no MAG-7 on a full buy
  else if(kit.kit&&!haveRifle)tags.push(...String(expSwapTxt(p,kit.kit.key)).split(" + ").filter(x=>!/grenade/i.test(x)).map(x=>`<span class="vtag">${esc(x)}</span>`));
  else if(rt==="full"&&!haveRifle)tags.push(`<span class="vtag">rifle</span><span class="vtag">kevlar + helmet</span>`);
  if(haveRifle)tags.push(`<span class="vtag got">${esc(g.primary)} ✓</span>`);
  let nd="",left=g.money;
  if(E&&E.order&&E.order.length&&rt!=="pistol"&&rt!=="eco"){const maxN=rt==="full"?4:2,main=rt==="full"&&!haveRifle?(g.side==="T"?2700:2900)+(g.helmet?0:g.armor>0?350:1000):0;
    const r=nadePlan(E,Math.max(0,g.money-main),g.nades||{},maxN);left=r.left;
    nd=r.plan.length?`<div class="vnades">${r.plan.map(o=>`<span class="vnade now" style="--c:${NADE_C[o.type]||"#ccc"}"><i>${vLetter[o.type]}</i><small>$${o.price}</small></span>`).join("")}</div>`:""}
  const next=(rt==="eco"?g.money:left)+bonus,okNext=next>=full;
  const T_=g.side==="T",spot=!T_&&kit.zone?`<span class="vchip">📍 ${vShort(kit.zone.key)}</span>`:"",avoid=!T_&&kit.avoid?`<span class="vchip bad">✕ ${vShort(kit.avoid.key)}</span>`:"";
  const awp=sk&&sk.endsWith("anti_eco")?`<span class="vchip bad">✕ AWP</span>`:"";
  const rows=econRows(plan);   // the plan already says what a loss leaves: no separate chip then
  return `<div class="vbuy"><div class="vbuy-h"><b>${RT}</b><span>${money(g.money)}</span></div>
    ${rows}${tags.length?`<div class="vtags">${tags.join("")}</div>`:""}${nd}
    <div class="vchips">${nd?NC.chip:""}${vMates(g)}${spot}${avoid}${awp}${rows?"":`<span class="vchip ${okNext?"good":"bad"}">lost → ${money(next)} ${okNext?"✓ full":"✕ no full"}</span>`}</div></div>`}
