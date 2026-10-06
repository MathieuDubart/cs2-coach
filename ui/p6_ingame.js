
// ---------- view: in game (2nd screen, follows the game) ----------
let igToastOff=null,gsiLast=null,gsiTimer=null,gsiStatus=null,igManual=false,igEv={key:null,contact:null,site:null};
const money=x=>"$"+Math.round(x).toLocaleString("en-US");
const RT_EN={pistol:"Pistol round",eco:"Eco",force:"Force-buy",full:"Full buy","anti-eco":"Anti-eco"};
const FULL_W=new Set(["AK-47","M4A4","M4A1-S","AUG","SG 553","AWP","G3SG1","SCAR-20"]);
const gsiFresh=()=>gsiLast&&gsiLast.age!=null&&gsiLast.age<75&&gsiLast.map;
function buyTip(g,p){if(g.money==null||!g.side)return "";
  if(g.round===1||g.round===13){const ps=(((p.advice.plan||{}).weapons||{}).suggestions)||[];
    return ps.some(s=>s.kind==="pistol_strong")?"Your pistol duels are a strength: take the opening.":"Buy together and play grouped."}
  const full=g.side==="CT"?3900:3700,bonus=[1400,1900,2400,2900,3400][Math.min(g.losses||0,4)];
  if(g.primary&&FULL_W.has(g.primary)){const need=g.helmet?0:(g.armor>0?350:1000);
    return need?(g.money>=need?`You have the ${g.primary}: add ${g.armor>0?"the helmet":"kevlar + helmet"}, then your grenades.`:`You have the ${g.primary} but not enough for ${g.armor>0?"the helmet":"kevlar"} (${money(g.money)}): play it carefully.`)
      :`You have the ${g.primary} and your armor: complete your grenades (${money(g.money)}).`}
  const pl=typeof econPlan==="function"?econPlan(p,g):null;
  if(pl&&pl.opts.length>1){const b=pl.best,alt=pl.opts.filter(o=>o!==b).sort((x,y)=>y.v-x.v)[0],N={eco:"Save",half:"A half buy (pistol + kevlar)",force:"A force-buy",full:"A full buy"};
    return `${pl.close?`${N[b.k]} and ${N[pl.close.k].toLowerCase()} win about as much over the next ${pl.H} rounds (${b.pct}% vs ${pl.close.pct}%): take the one that keeps your next full buy.`:`${N[b.k]} wins the most over the next ${pl.H} round${pl.H>1?"s":""}: about ${b.pct}% of them, vs ${alt.pct}% with ${N[alt.k].toLowerCase()}.`} If you lose this round, you'll have ${money(b.lose)} next round${b.fullNext?", enough for a full buy":", not enough for a full buy"}.`}
  if((g.equip||0)+g.money>=full&&g.money<full)return `With your gear, this is a full buy: complete what's missing (${money(g.money)}).`;
  if(g.money>=full)return `Full buy possible (${money(g.money)}).`;
  if(g.money+bonus>=full)return `Eco advised: even if you lose this round, you'll have ${money(g.money+bonus)} next round.`;
  return `Force only if the whole team forces (${money(g.money)}).`}
function roundType(g){if(!g||!g.side||g.round==null)return null;if(g.round===1||g.round===13)return "pistol";if(g.money==null)return null;
  const full=g.side==="CT"?3900:3700,eq=g.equip||0,total=g.money+eq;
  if((g.primary&&FULL_W.has(g.primary))||eq>=3500||total>=full)return "full";   // saved or bought rifle, or enough to buy one
  return total<2000?"eco":"force"}
function buyRows(p,map,side,cur){const BB=((p.advice.plan||{}).buys)||{},B=(BB.maps||{})[map];const S_=B&&B[side];if(!S_)return `<p class="note">Not enough rounds on ${MAPN(map)} as ${side} yet.</p>`;
  const sw=s=>typeof expSwapTxt==="function"?expSwapTxt(p,s):s;   // a running "replace X with Y" experiment: Y
  const cell=(x,alts)=>x?`<b>${esc(sw(x.key))}</b><br><span class="note">${x.why.map(esc).join(" · ")}</span>${alts&&alts.length?`<br><span class="note">other options: ${alts.map(a=>esc(sw(a.key))).join(", ")}</span>`:""}`:'<span class="note">not enough rounds</span>';
  const rows=["pistol","eco","force","full","anti-eco"].filter(k=>S_[k]);if(!rows.length)return "";
  return `<p class="note">Adapted to you: your own rounds first, then players of your profile (${(BB.profile||[]).map(esc).join(", ")}: ${BB.n_peers||0} players of the base), then the whole base. Your duels in the zone and with the weapon adjust the ranking.</p>
   <div class="tbl"><table><thead><tr><th>Round</th><th>Where to play (${clock(15)}-${clock(25)})</th><th>What to buy</th><th>You</th></tr></thead><tbody>
   ${rows.map(k=>{const x=S_[k],on=k===cur;return `<tr${on?' style="outline:2px solid var(--flash)"':""}><td><b>${esc(x.label)}</b>${on?'<br><span class="pill" style="color:var(--flash)">this round</span>':""}<br><span class="note">rounds won: profile ${x.peer_win??"—"}%, base ${x.base_win??"—"}%</span></td>
     <td class="wrap">${cell(x.zone,x.zones)}${x.avoid?`<br><span class="note bad">avoid: ${esc(x.avoid.key)}</span>`:""}</td><td class="wrap">${cell(x.kit,x.kits)}</td>
     <td class="wrap">${x.n_me?`${x.n_me} round${x.n_me>1?"s":""}, ${x.my_win}% won`:'<span class="note">no round here</span>'}</td></tr>`}).join("")}</tbody></table></div>`}

// ---------- the T side (CT reading): odds of A / B from the base, the team's history and what happens in the round ----------
const halfStart=n=>n<=12?1:n<=24?13:25+3*Math.floor((n-25)/3);   // MR12, then overtime halves of 3 rounds
const sigm=z=>1/(1+Math.exp(-z)),logit=p=>Math.log(p/(1-p));
const WIN_OF=t=>t<20?"early":t<40?"setup":t<70?"hit":"late";
const WIN_EN={early:"start of the round (1:55-1:35)",setup:"info phase (1:35-1:15)",hit:"site attack (1:15-0:45)",late:"end of the round (after 0:45)"};
const WIN_SHORT={early:["start of the round","1:55-1:35"],setup:["info phase","1:35-1:15"],hit:["site attack","1:15-0:45"],late:["end of the round","after 0:45"]};
// the round's length: read from the game when it sends its clock (bot matches and other modes are longer), else 1:55
// CS2 doesn't send its clock to players: 1:55 (competitive, Premier); a bomb planted later than that this match means
// longer rounds (bot matches: 2:15), and the app adapts
const RLEN=()=>{const g=typeof gsiLast!=="undefined"?gsiLast:null;if(g&&g.round_len)return g.round_len;
  // a bomb down after 1:55, or a round that ran past 1:55 with no bomb: this match has longer rounds (bots: 2:15, 2:30)
  const R=((g&&g.hist)||{}).rounds||{},seen=Math.max(0,...Object.values(R).map(r=>Math.max(r&&r.plant||0,r&&r.plant==null&&r.end||0)));
  return seen<=117?115:seen<=137?135:seen<=152?150:Math.ceil(seen/5)*5};
const clock=t=>{const s=Math.max(0,RLEN()-t);return `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,"0")}`};
// what you marked survives a reload; a mark that arrives from the app (a call you made, a tap on another screen) is
// read as soon as it changes
function evFor(g){const key=`${g.map}|${g.round}`,H=g.hist||{},mk=(H.marks||{})[g.round]||{},s=(H.sites||{})[g.round],sig=JSON.stringify([mk,s||null,g.round_phase==="live"]);
  if(igEv.key!==key||igEv.sig!==sig)igEv={key,sig,contact:mk.contact||null,alone:mk.alone??null,site:g.round_phase==="live"&&(s==="A"||s==="B")?s:null};return igEv}
const DYN_EN={rush:"rush",fast:"fast push by 1-2 Ts",exec:"execute",late:"late hit",none:"no attack"},DYN_SHORT={rush:"rush",fast:"fast",exec:"exec",late:"late",none:""};
// the shape of a finished round: what you marked, or read from the clock (the bomb goes down about 7 s after the site is taken)
function roundDyn(TS,H,n){const R=(H.rounds||{})[n]||{},mk=(H.marks||{})[n]||{},site=(H.sites||{})[n],rs=(TS&&TS.rush_s)||30,ls=(TS&&TS.late_s)||75;
  if(mk.dyn)return {dyn:mk.dyn,how:"marked by you",lone:!!mk.lone};
  let c=null,how="";
  if(R.plant!=null){c=R.plant-7;how=`bomb down at ${clock(R.plant)}`}else if(mk.site_t!=null){c=mk.site_t;how=`seen on the site at ${clock(mk.site_t)}`}
  if(c==null)return site==="-"?{dyn:"none",how:"marked not clear",lone:!!mk.lone}:mk.lone?{dyn:null,how:"",lone:true}:null;
  return {dyn:c<=rs?"rush":c<=ls?"exec":"late",how,lone:!!mk.lone,auto:true}}
// where you usually stand on a map as CT: your time per zone (profile), summed by A side / B side / mid (spawns left out)
function habitRegions(map,SE){const p=typeof P==="function"?P():null,m=p&&((p.cross||{}).maps||[]).find(x=>x.map===map);
  const zs=((((m||{}).sides||{}).CT||{}).zones)||[],W={};let t=0;
  for(const z of zs){if(/spawn/i.test(z.name||"")||!z.presence)continue;const r=(SE.regions||{})[z.name]||"mid";W[r]=(W[r]||0)+z.presence;t+=z.presence}
  if(t<20)return null;for(const k in W)W[k]/=t;return W}
function tsidePredict(TS,map,g,ev){const M=TS&&TS.maps&&TS.maps[map];if(!M||!g||g.round==null)return null;
  const H=g.hist||{},R=H.rounds||{},SI=H.sites||{},cur=g.round_phase==="over"?g.round+1:g.round;
  if(g.round_phase==="over"&&halfStart(cur)===cur)return null;   // the sides swap: this team will not attack any more
  const half=[];for(let n=halfStart(cur);n<cur;n++)half.push(n);
  const rih=half.length+1,C=M.ctx;let mix,econ=null;
  if(rih===1)mix={pistol:1};
  else if(rih===2){const w=(R[half[0]]||{}).win;mix=w?{[w==="T"?"r2_win":"r2_loss"]:1}:{r2_win:.5,r2_loss:.5}}
  else{const last=R[half[half.length-1]]||{};let losses=0;for(let i=half.length-1;i>=0;i--){if((R[half[i]]||{}).win==="CT")losses++;else break}
    const key=last.win==="T"?"won":last.win==="CT"?(losses>=3?"lost3":"lost"+losses):null;econ=key&&TS.econ[key];
    mix=econ?{eco:econ.eco/100,force:econ.force/100,full:econ.full/100}:{full:.6,force:.35,eco:.05}}
  const rOf=x=>x.rush_p??(x.rush_all!=null?x.rush_all/100:null)??M.rush_p??((x.rush??M.all.rush??0)/100);   // share of rounds that are rushes
  let pA=0,none=0,rush=0,w=0;
  for(const [c,k] of Object.entries(mix)){const x=C[c];if(!x||!k)continue;pA+=k*x.pA_hit;none+=k*x.none/100;rush+=k*rOf(x);w+=k}
  if(w){pA/=w;none/=w;rush/=w}else{pA=M.pA_hit;none=M.all.none/100;rush=rOf(M.all)}
  pA=Math.min(.97,Math.max(.03,pA));
  const main=Object.entries(mix).sort((a,b)=>b[1]-a[1])[0][0],X=C[main]||M.all,CTX=TS.ctx_fr||{};
  const why=[];
  if(rih<=2)why.push(`${CTX[main]||main} on ${MAPN(map)}: A ${X.A}%, B ${X.B}%, no clear hit ${X.none}% (${X.n} rounds of the base).`);
  else if(econ)why.push(`Likely T buy, given their last rounds: full buy ${econ.full}%, force ${econ.force}%, eco ${econ.eco}%. On ${MAPN(map)}, that gives A ${Math.round(100*pA*(1-none))}%, B ${Math.round(100*(1-pA)*(1-none))}%.`);
  else why.push(`On ${MAPN(map)}, all situations: A ${M.all.A}%, B ${M.all.B}% (${M.n_rounds} rounds of the base).`);
  // what this team did in the half
  const seq=half.map(n=>({n,site:SI[n]||null,won:(R[n]||{}).win==="T",known:!!(R[n]||{}).win}));
  const B_=(TS.model||{}).beta||{},x={};const last=seq[seq.length-1];
  if(last&&(last.site==="A"||last.site==="B")&&last.known){const sg=last.site==="A"?1:-1;if(last.won)x.repeat_won=sg;else x.repeat_lost=sg;
    let k=0;for(let i=seq.length-1;i>=0&&seq[i].site===last.site;i--)k++;if(k>=2)x.streak2=sg}
  const nA=seq.filter(q=>q.site==="A").length,nB=seq.filter(q=>q.site==="B").length;if(nA+nB)x.pref=(nA-nB)/Math.sqrt(nA+nB);
  // the tempo: a team that rushes keeps rushing, above all after a rush that worked (model fit on the base)
  const dyns=half.map(n=>roundDyn(TS,H,n)),TB=((TS.tempo||{}).beta)||{},whyT=[],rush0=rush;let zr=logit(Math.min(.95,Math.max(.02,rush)));
  const lastDy=dyns[dyns.length-1];
  if(TB.rush_won&&last&&last.known&&last.won&&lastDy&&lastDy.dyn==="rush"){zr+=TB.rush_won;whyT.push("they rushed and won the last round, and teams often do it again")}
  const kn=dyns.filter(d=>d&&d.dyn),nR=kn.filter(d=>d.dyn==="rush").length;
  if(TB.half_excess&&kn.length>=2){const ex=(nR-kn.length*(M.rush_p??.2))/Math.sqrt(kn.length);if(Math.abs(ex)>.3){zr+=TB.half_excess*ex;whyT.push(nR?`${nR} rush${nR>1?"es":""} in the ${kn.length} rounds you know of this half`:`no rush in the ${kn.length} rounds you know of this half`)}}
  const RC=TS.rush_ct||{},ob=g.side==="CT"&&rih>=3?roundType(g):null;   // your buy: Ts rush far more into an eco
  if(ob&&RC[ob]){zr+=RC[ob];whyT.push(ob==="eco"?"you're on an eco: Ts rush more into it":`your ${ob} buy`)}
  rush=sigm(zr);
  let z=logit(pA);
  for(const k of ["repeat_lost","repeat_won","streak2","pref"]){if(!x[k]||!B_[k])continue;const z2=z+B_[k]*x[k],d=Math.round(100*(sigm(z2)-sigm(z))*(1-none));z=z2;if(!d)continue;
    const pts=`+${Math.abs(d)} pts for ${d>0?"A":"B"}`;
    if(k==="repeat_lost")why.push(`They lost their last attack on ${last.site}: a team that loses on a site goes back less often (${pts}).`);
    else if(k==="pref")why.push(`This half: A ${nA} time${nA===1?"":"s"}, B ${nB} time${nB===1?"":"s"}. Teams keep their favorite site (${pts}).`);
    else why.push(`${(TS.model.fr||{})[k]||k} (${pts}).`)}
  if(whyT.length)why.push(`Rush this round: ${Math.round(100*rush)}% (usually ${Math.round(100*rush0)}% here): ${whyT.join("; ")}.`);
  let a=sigm(z)*(1-none),b=(1-sigm(z))*(1-none),n=none;
  // in the round: what you can see changes the odds (likelihoods measured in the base)
  const E=M.evidence||{},live=g.round_phase==="live"&&cur===g.round,planted=live&&g.bomb==="planted",ev0=ev||{};
  const norm=()=>{const s=a+b+n;if(s>0){a/=s;b/=s;n/=s}};
  const shift=(label,fa,fb,fn)=>{const a0=a;a*=fa;b*=fb;n*=fn;norm();const d=Math.round(100*(a-a0));why.push(`${label} (${d>=0?"+":"−"}${Math.abs(d)} pts for A).`)};
  let evid=[];
  if(live&&ev0.site){a=ev0.site==="A"?1:0;b=ev0.site==="B"?1:0;n=0;evid.push(`you saw them on ${ev0.site}`)}
  else if(live){
    if(planted){n=0;norm();evid.push("the bomb is down")}
    else if(g.elapsed!=null&&g.elapsed>=15&&E.survival&&E.survival.A&&E.survival.B){const S_=E.survival,i=Math.min(S_.t.length-1,Math.round(g.elapsed/5));
      shift(`${Math.round(g.elapsed)} s in and no site taken yet: late attacks go ${S_.A[i]<S_.B[i]?"B":"A"} more often`,S_.A[i],S_.B[i],(S_.none||[])[i]||.5);evid.push(`${clock(g.elapsed)} on the clock, no site taken`)}
    if(!planted&&ev0.contact&&E.contact&&E.contact.lik){const zc=ev0.contact,G=E.contact.lik_g&&E.contact.lik_g.A&&E.contact.lik_g.B?E.contact.lik_g:null,gm=(TS.alone||{}).gamma;
      const L=ev0.alone!=null&&G?G:E.contact.lik,g_=(o)=>((L[o]||{})[zc]??(L[o]||{}).other);
      let la=g_("A"),lb=g_("B"),ln=g_("none")??((la+lb)/2);
      if(la&&lb){if(ev0.alone===true&&gm!=null){const q=Math.pow(la/lb,gm/2);   // a lone T: the zone's usual lean, turned around (measured in the base, A against B only)
          shift(`One T alone at ${zc}: a lone T is often a lurker or an info player, the others tend to be on the other side`,q,1/q,1);evid.push(`one T alone at ${zc}`)}
        else{shift(`First contact at ${zc}${ev0.alone===false?" with 2+ Ts":""}: in the base, first duels there come before ${la>lb?"A":"B"} attacks ${Math.round(100*Math.max(la,lb)/(la+lb))}% of the time`,la,lb,ln);evid.push(`first contact at ${zc}${ev0.alone===false?", 2+ Ts":""}`)}}}
    // your own spot, no click: where you stood until 20 s, and a fight there (damage taken, a kill, your death) or
    // nothing yet. Measured on every CT of the base: a quiet B 30 s in tilts toward A, a fight at B toward B
    const SE=M.self,Rc=R[cur]||{},GEO=M.geo;
    if(!planted&&SE&&SE.lik&&g.elapsed!=null&&g.elapsed>=SE.t[0]){
      // where you stand: your position when the game gives it (it doesn't in a normal match), else where you usually
      // stand on this map as CT (your profile), as weights over A side / B side / mid
      let W=null,zn=null;
      if(Rc.pos15&&GEO){const w=worldPx(GEO,Rc.pos15);zn=w&&nearestZone(GEO,w.px,w.level);W={[(zn&&SE.regions[zn])||"mid"]:1}}
      else W=habitRegions(map,SE);
      const tk=[...SE.t].reverse().find(t=>t<=g.elapsed);
      const tc=Math.min(...[Rc.hurt,Rc.dead,Rc.util,Rc.hit,...(Rc.kills||[])].filter(x=>x!=null)),fought=isFinite(tc)&&tc<=tk;   // damage, a kill, a flash or a molotov on you, a hit
      if(W){const o={A:0,B:0,none:0};let tot=0;
        for(const [reg,wt] of Object.entries(W)){const L=(SE.lik[reg]||{})[String(tk)];if(!L)continue;tot+=wt;
          for(const k of ["A","B","none"])o[k]+=wt*L[fought?"contact":"quiet"][k]}
        if(tot){const top=Object.entries(W).sort((a,b)=>b[1]-a[1])[0],spot=zn?`${zn}, ${top[0]==="mid"?"mid":top[0]+" side"}`
            :`usually ${top[0]==="mid"?"mid":top[0]+" side"}, ${Math.round(100*top[1])}% of your CT time here`;
          shift(fought?`A fight at your spot (${spot}) before ${clock(tk)}: attacks come your way more often`
                      :`Nothing at your spot (${spot}) by ${clock(tk)}: the attack tends to go elsewhere`,o.A/tot,o.B/tot,o.none/tot);
          evid.push(fought?"a fight at your spot":"quiet at your spot")}}
      const MT=((((typeof P==="function"&&P())||{}).advice||{}).plan||{}).mates||{};
      for(const [sid,mr] of Object.entries(Rc.mates||{})){const MW=((MT[sid]||{}).maps||{})[map];if(!MW||mr.seen==null||mr.seen>tk)continue;
        const f2=[mr.hurt,mr.dead,mr.util,mr.hit].some(x=>x!=null&&x<=tk),o={A:0,B:0,none:0};let tot=0;
        for(const [reg,wt] of Object.entries(MW)){const L=(SE.lik[reg]||{})[String(tk)];if(!L)continue;tot+=wt;for(const k of ["A","B","none"])o[k]+=wt*L[f2?"contact":"quiet"][k]}
        if(!tot)continue;const top=Object.entries(MW).sort((x,y)=>y[1]-x[1])[0],nm=(MT[sid]||{}).name||"your teammate",spot=`usually ${top[0]==="mid"?"mid":top[0]+" side"}`;
        shift(f2?`A fight at ${nm}'s spot (${spot}) before ${clock(tk)}`:`Nothing at ${nm}'s spot (${spot}) by ${clock(tk)}`,o.A/tot,o.B/tot,o.none/tot);
        evid.push(f2?`a fight at ${nm}'s spot`:`quiet at ${nm}'s spot`)}}}
  if(!half.length&&!evid.length)why.push("First round of the half: the numbers come from the base.");
  const raw={A:Math.round(100*a),B:Math.round(100*b),none:Math.round(100*n),rush:Math.round(100*rush)};
  if(typeof calSite==="function"){if(!(live&&ev0.site))[a,b,n]=calSite(map,a,b,n);rush=calRush(rush)}
  return {A:Math.round(100*a),B:Math.round(100*b),none:Math.round(100*n),rush:Math.round(100*rush),raw,rush0:Math.round(100*rush0),dyns,ctx:main,mix,X,why,seq,rih,cur,evid,live,planted,E}}
function askDyn(TS,H,n){const d=roundDyn(TS,H,n)||{},R=(H.rounds||{})[n]||{},mk=(H.marks||{})[n]||{};
  const hint=!d.dyn&&R.win==="CT"&&R.plant==null&&R.end!=null&&R.end<=35?`All the Ts were dead at ${clock(R.end)}: a rush?`:d.auto?`Read from the clock (${d.how}). Fix it if you saw otherwise.`:"";
  return `<div class="ask sm" role="group" aria-label="How the Ts played round ${n}"><b>How?</b>
    ${["rush","fast","exec","late"].map(k=>`<button type="button" data-dyn="${k}" data-round="${n}" aria-pressed="${mk.dyn===k}"${d.auto&&d.dyn===k?' class="auto" title="Read from the clock"':""}>${k==="fast"?"1-2 Ts early":DYN_EN[k][0].toUpperCase()+DYN_EN[k].slice(1)}</button>`).join("")}
    <button type="button" data-lone="${n}" aria-pressed="${!!mk.lone}" title="A T died with no teammate close, and was not traded, before their attack">They lost a T alone</button>
    ${hint?`<span class="note">${esc(hint)}</span>`:""}</div>`}
function roundDetail(TS,H,n){const R=(H.rounds||{})[n]||{},mk=(H.marks||{})[n]||{},d=roundDyn(TS,H,n),bits=[];
  if(d&&d.dyn)bits.push(`${DYN_EN[d.dyn]} (${d.how})`);
  if(mk.contact)bits.push(`first contact ${mk.contact}${mk.alone===true?", 1 T alone":mk.alone===false?", 2+ Ts":""}${mk.contact_t!=null?` at ${clock(mk.contact_t)}`:""}`);
  if(d&&d.lone)bits.push("they lost a T alone");
  if(R.dead!=null)bits.push(`you died at ${clock(R.dead)}`);if((R.kills||[]).length)bits.push(`your kills at ${R.kills.map(clock).join(", ")}`);
  if(R.end!=null)bits.push(`round over at ${clock(R.end)}`);return bits.join(" · ")}
function oddsBar(r){return `<div class="obar" role="img" aria-label="A ${r.A}%, B ${r.B}%, no clear hit ${r.none}%"><i class="A" style="width:${r.A}%">${r.A>=12?`A ${r.A}%`:""}</i><i class="B" style="width:${r.B}%">${r.B>=12?`B ${r.B}%`:""}</i><i class="N" style="width:${r.none}%">${r.none>=10?`${r.none}%`:""}</i></div>
  <div class="olegend"><span>A ${r.A}%</span><span>B ${r.B}%</span><span>no clear hit ${r.none}%</span><span>rush ${r.rushNow!=null?r.rushNow:r.rush}%</span></div>`}
function dangerNow(E,side,site,t){const D_=((E||{}).deaths||{})[side];if(!D_)return "";const w=WIN_OF(t||0),src=(site&&D_[site]&&D_[site][w])||(D_.all||{})[w];
  if(!src||!src.zones.length)return "";const [nm,rg]=WIN_SHORT[w];return `<p class="danger">${nm[0].toUpperCase()+nm.slice(1)} (${rg}): ${side}s die most at <b>${src.zones.map(z=>`${esc(z.zone)}</b> ${z.pct}%`).join(", <b>")}.</p>`}
function tsideLive(p,g){const TS=(p.advice.plan||{}).tside,ev=evFor(g),r=tsidePredict(TS,g.map,g,ev);if(!r)return "";
  const PLs=tsidePlays(TS,g.map,g,ev,r),NN=PLs&&!r.planted?nadesNow(p.advice.plan||{},g.map,g,PLs,r.live):[];
  if(PLs&&r.live)r.rushNow=Math.round(100*PLs.rush);   // a rush is less and less likely as the clock runs
  const top=r.A>=r.B?"A":"B",pt=Math.max(r.A,r.B),X=r.X,det=X[top+"_detail"],E=r.E||{};
  const tips=[];
  if(r.live&&(ev.site||r.planted)){}
  else if(pt>=55)tips.push(`<b>${top} likely</b>: get your rotation and a grenade ready toward ${top}, but don't leave your spot before the info (${100-pt}% it goes elsewhere).`);
  else if(pt-Math.min(r.A,r.B)>=12)tips.push(`<b>Leaning ${top}</b> (${pt}% vs ${Math.min(r.A,r.B)}%): keep your default position, with a grenade for ${top} ready.`);
  else tips.push("<b>No clear favorite</b>: play your default position and wait for the info.");
  if(!r.live&&r.rush>=30)tips.push(`<b>Rush likely (${r.rush}%)</b>${r.rush>=r.rush0+5?`, more than usual here (${r.rush0}%)`:""}: no dry peek in the first 30 s, keep a grenade for the entrance, listen.`);
  if(det&&det.from.length&&!(r.live&&ev.site))tips.push(`They enter ${top} through <b>${det.from.map(f=>esc(f.zone)).join("</b> or <b>")}</b>, median around ${det.timer}.`);
  if(X.first&&X.first.length&&!r.live)tips.push(`Most common first contact: <b>${esc(X.first[0].zone)}</b> (${X.first[0].pct}%), around ${X.first_timer}.`);
  if(NN.length)tips.push(`<b>${r.live?"Grenade now":"Grenade plan"}</b>: ${NN.slice(0,2).map(x=>`${nadeName(x.type,"CT")} ${esc(x.from)} → ${esc(nTo(x,S.map))} (${esc(x.why)})`).join("; ")}. It's on the radar.`);
  const H=g.hist||{},SI=H.sites||{},R=H.rounds||{},done=r.cur-1;
  const asked=(g.round_phase==="over"||g.round_phase==="freezetime")&&done>=halfStart(r.cur)?done:null;
  const res=n=>{const w=(R[n]||{}).win;return w?(w==="CT"?"won":"lost"):""};   // seen from your side (CT)
  const lbl=n=>{const s=SI[n],w=res(n),d=roundDyn(TS,H,n);return `R${n} ${s==="-"?"–":s||"?"}${d&&d.dyn&&DYN_SHORT[d.dyn]?` ${DYN_SHORT[d.dyn]}`:""}${d&&d.lone?" ·1":""}${w?` ${w==="won"?"✓":"✗"}`:""}`};
  const zones=((E.contact||{}).zones)||[];
  return `<div class="tread" aria-live="polite"><h3><span>T read · round ${r.cur}</span><small>${esc((TS.ctx_fr||{})[r.ctx]||"")}</small></h3>
    ${oddsBar(r)}
    ${PLs&&PLs.list.length?`<div class="plays" aria-label="Likely plays">${PLs.list.filter(x=>x.v>=0.03).slice(0,5).map(x=>`<div class="pl s-${x.site}"><b>${Math.round(100*x.v)}%</b><span>${esc(x.label)}</span></div>`).join("")}</div>`:""}
    ${r.live?`<div class="ev" role="group" aria-label="They are on"><span class="l">They're on</span>${["A","B"].map(s=>`<button type="button" class="site-${s}" data-evsite="${s}" aria-pressed="${ev.site===s}">${s}</button>`).join("")}</div>
     ${zones.length&&!ev.site&&!r.planted?`<div class="ev" role="group" aria-label="First contact"><span class="l">First contact</span>${zones.map(z=>`<button type="button" data-evz="${esc(z)}" aria-pressed="${ev.contact===z}">${esc(z)}</button>`).join("")}</div>
      ${ev.contact?`<div class="ev" role="group" aria-label="How many Ts at the first contact"><span class="l">How many</span><button type="button" data-evalone="1" aria-pressed="${ev.alone===true}">1 T alone</button><button type="button" data-evalone="0" aria-pressed="${ev.alone===false}">2+ Ts</button></div>`:""}`:""}`:""}
    ${tips.length?`<ul class="big-list">${tips.map(t=>`<li class="ct">${t}</li>`).join("")}</ul>`:""}
    ${r.live&&!ev.site&&!r.planted?dangerNow(E,"CT",null,g.elapsed):""}
    <details${r.live?"":" open"}><summary class="mini" style="cursor:pointer">Why these odds</summary><ul class="why">${r.why.map(w=>`<li>${esc(w)}</li>`).join("")}</ul></details>
    ${asked?`<div class="ask" role="group" aria-label="Where the Ts hit in round ${asked}"><b>Round ${asked}: where did they hit?</b>
      ${["A","B","-"].map(v=>`<button type="button" data-site="${v}" data-round="${asked}" aria-pressed="${SI[asked]===v}"${v!=="-"?` class="site-${v}"`:""}>${v==="-"?"Not clear":v}</button>`).join("")}</div>
     ${askDyn(TS,H,asked)}`:""}
    ${r.seq.length?`<div class="marks" role="group" aria-label="T attacks this half"><span class="note">This half (click to fix):</span>
      ${r.seq.map(q=>q.n).map(n=>{const dt=roundDetail(TS,H,n);return `<button type="button" class="mk ${res(n)}" data-cycle="${n}" title="${res(n)?`Round ${res(n)==="won"?"won":"lost"} by your team. `:""}${dt?esc(dt)+". ":""}Click: A, then B, then not clear, then clear.">${lbl(n)}</button>`}).join("")}</div>`:""}
    </div>`}
function retakeCard(p,g,site){const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[g.map];if(!M)return "";const E=M.evidence||{},PL=(E.plants||{})[site];
  const ct=g.side==="CT",own=(E.retakes||{})[site]||[],all=TS.retake_all||[];
  // this map's numbers when a situation has at least 20 retakes, all maps otherwise
  const pick=[[1,1],[1,2],[2,1],[2,2],[2,3],[3,2],[3,3],[4,3],[3,4]].map(([c,t])=>{const a=own.find(x=>x.ct===c&&x.t===t);return a&&a.n>=20?{...a,here:true}:all.find(x=>x.ct===c&&x.t===t)}).filter(Boolean);
  const spots=PL&&PL.spots.length?PL.spots.map(s=>`<b>${esc(s.where==="center"?"middle of the site":s.where+" part of the site")}</b> ${s.share}% (Ts then win ${s.t_win}%)`).join(" · "):"";
  return `<div class="tread" style="border-left-color:var(--bad)"><h3><span>${ct?"Retake":"Post-plant"} · ${site} site</span><small>${PL?`${PL.n} plants in the base, median ${PL.timer}`:""}</small></h3>
   ${spots?`<p>Where the bomb usually goes: ${spots}. The spots are on the radar.</p>`:""}
   ${pick.length?`<p class="mini">${ct?"Your team's chances to win the retake":"The CTs' chances to win the retake"}, by players alive when the bomb went down (CTs v Ts, number of retakes; ${pick.some(x=>x.here)?`${MAPN(g.map)} when it has 20+, all maps otherwise`:"all maps"}):</p>
    <div class="rt">${pick.map(x=>`<div class="${x.ct_win>=55?"hi":x.ct_win<=20?"lo":""}"><b>${x.ct_win}%</b><span>${x.ct}v${x.t} · ${x.n}${x.here?" · here":""}</span></div>`).join("")}</div>
    <p class="note">${ct?"Under 20%: save your weapon unless the clock or a kit changes the math. Over 55%: go together on one flash.":"The fewer CTs alive, the more you should hold crossfires and let the clock work."}</p>`:""}
   ${dangerNow(E,ct?"CT":"T",site,70)}</div>`}
function tsideTable(p,map){const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[map];if(!M)return `<p class="note">Not enough demos of ${MAPN(map)} in the base yet.</p>`;
  const C=M.ctx,rows=["pistol","r2_win","r2_loss","eco","force","full"].filter(c=>C[c]),E=M.evidence||{},CTX=TS.ctx_fr||{};
  const from=x=>["A","B"].map(L=>{const d=x[L+"_detail"];return d&&d.from.length?`${L} through ${d.from.map(f=>`${esc(f.zone)} (${f.pct}%)`).join(", ")}`:""}).filter(Boolean).join("<br>");
  const deaths=(side)=>{const D_=((E.deaths||{})[side]||{}).all||{};return ["early","setup","hit","late"].filter(w=>D_[w]).map(w=>`<tr><td>${WIN_EN[w]}</td><td class="wrap">${D_[w].zones.map(z=>`${esc(z.zone)} ${z.pct}%`).join(", ")}</td><td class="n">${D_[w].n}</td></tr>`).join("")};
  const sv=E.survival,DA=TS.dyn_after,AL=TS.alone,G=(E.contact||{}).lik_g;
  return `<p class="note">${M.n_rounds} rounds from ${M.n_matches} matches of the base. An attack stopped before the site counts for the site it was going to. Rush: 3+ Ts on a site in the first 30 seconds (clock above 1:25).${M.n_matches<10?" Few matches on this map: take the numbers as indications.":""}</p>
   <h3>Where they attack, by kind of round</h3>
   <div class="tbl"><table><thead><tr><th>Round</th><th class="n">A</th><th class="n">B</th><th class="n">No clear hit</th><th class="n">Rush</th><th>Site taken</th><th>Through</th><th>First contact</th></tr></thead><tbody>
   ${rows.map(c=>{const x=C[c];return `<tr><td><b>${esc(CTX[c]||c)}</b><br><span class="note">${x.n} rounds</span></td><td class="n">${x.A}%</td><td class="n">${x.B}%</td><td class="n">${x.none}%</td><td class="n">${x.rush_all!=null?x.rush_all+"%":x.rush!=null?x.rush+"%":"—"}</td>
     <td>${x.hit_timer?"around "+x.hit_timer:"—"}</td><td class="wrap">${from(x)||"—"}</td><td class="wrap">${(x.first||[]).slice(0,2).map(f=>`${esc(f.zone)} (${f.pct}%)`).join(", ")||"—"}</td></tr>`}).join("")}</tbody></table></div>
   ${M.plays&&M.plays.prior?(()=>{const P=M.plays,cs=["all",...rows.filter(c=>P.prior[c])],ps=Object.keys(P.prior.all).sort((a,b)=>P.prior.all[b]-P.prior.all[a]);
     return `<h3>Plays and entrances</h3><p class="note">The play of every round of the base: a rush (3+ Ts on a site in the first 30 s), a split (two entrances of the site at once), or one entrance. An entrance is where the Ts of the push stood a few seconds before the site was taken; "mid" when it comes from mid. As CT, the odds of each entrance update during the round in the live panel (the radar keeps the spots and grenades).</p>
     <div class="cols3">${["A","B"].filter(s=>(P.lanes[s]||[]).length).map(s=>`<article class="card"><h3>Entrances of ${s}</h3><ul>${P.lanes[s].map(L=>`<li><b>${esc(L.name)}</b>${L.mid?" (mid)":L.main?" (main)":""}: used in ${L.share??"—"}% of the ${s} attacks<br><span class="note">${esc((L.zones||[]).join(", "))}</span></li>`).join("")}</ul></article>`).join("")}</div>
     <div class="tbl"><table><thead><tr><th>Play</th>${cs.map(c=>`<th class="n">${c==="all"?"All rounds":esc(CTX[c]||c)}</th>`).join("")}</tr></thead><tbody>
     ${ps.map(p=>`<tr><td>${esc(P.label[p]||p)}</td>${cs.map(c=>`<td class="n">${P.prior[c]&&P.prior[c][p]!=null?Math.round(100*P.prior[c][p])+"%":"—"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`})():""}
   ${rows.some(c=>C[c].dyn)?`<h3>How they attack</h3><p class="note">Share of rounds, by kind of round. Execute: site taken between 1:25 and 0:40 on the clock. Late hit: after 0:40. Lost a T alone: a T died with no teammate close (about 25 m) and was not traded, before their attack.</p>
    <div class="tbl"><table><thead><tr><th>Round</th><th class="n">Rush</th><th class="n">1-2 Ts early</th><th class="n">Execute</th><th class="n">Late hit</th><th class="n">No attack</th><th class="n">Lost a T alone</th></tr></thead><tbody>
    ${rows.filter(c=>C[c].dyn).map(c=>{const x=C[c],d=x.dyn;return `<tr><td><b>${esc(CTX[c]||c)}</b></td><td class="n">${d.rush}%</td><td class="n">${d.fast}%</td><td class="n">${d.exec}%</td><td class="n">${d.late}%</td><td class="n">${d.none}%</td><td class="n">${x.lone!=null?x.lone+"%":"—"}</td></tr>`}).join("")}</tbody></table></div>`:""}
   ${DA&&DA.rows&&DA.rows.length?`<h3>After each kind of attack</h3><p class="note">What the same team does on the next round, all maps together (${DA.base_rush}% of rounds are rushes). The shape of an attack says little about the next site, but a team that rushes keeps rushing, above all after a rush that worked. Mark the shape of each round on the T read (or let the clock do it): the rush odds follow.</p>
    <div class="tbl"><table><thead><tr><th>Their last round</th><th class="n">Rush next</th><th class="n">Same site next</th><th class="n">Other site next</th><th class="n">Cases</th></tr></thead><tbody>
    ${DA.rows.filter(a=>a.dyn!=="none").map(a=>`<tr><td>${esc(DYN_EN[a.dyn][0].toUpperCase()+DYN_EN[a.dyn].slice(1))}, ${a.won?"won":"lost"} by the Ts</td><td class="n">${a.rush}%</td><td class="n">${a.same!=null?a.same+"%":"—"}</td><td class="n">${a.other!=null?a.other+"%":"—"}</td><td class="n">${a.n}</td></tr>`).join("")}
    ${(DA.lone||[]).filter(a=>a.lone).map(a=>`<tr><td>Lost, after losing a T alone before their attack</td><td class="n">${a.rush}%</td><td class="n">${a.same}%</td><td class="n">—</td><td class="n">${a.n}</td></tr>`).join("")}</tbody></table></div>`:""}
   ${AL&&AL.gamma<0&&G&&G.A&&G.B&&E.contact.zones?`<h3>One T alone, or several?</h3><p class="note">At the first duel, a T with no teammate within about 25 m is often a lurker or an info player, and the others tend to be on the other side (${AL.share}% of first duels are like that, ${AL.n} in the base). During the round, tap the zone, then "1 T alone" or "2+ Ts". Odds of A or B from the zone of the first duel:</p>
    <div class="tbl"><table><thead><tr><th>First duel at</th><th class="n">2+ Ts: A</th><th class="n">2+ Ts: B</th><th class="n">1 T alone: A</th><th class="n">1 T alone: B</th></tr></thead><tbody>
    ${E.contact.zones.map(z=>{const la=G.A[z]??G.A.other,lb=G.B[z]??G.B.other,o0=(M.all.A||50)/(M.all.B||50),o1=o0*la/lb,o2=o0*Math.pow(la/lb,AL.gamma),p1=Math.round(100*o1/(1+o1)),p2=Math.round(100*o2/(1+o2));
      return `<tr><td>${esc(z)}</td><td class="n">${p1}%</td><td class="n">${100-p1}%</td><td class="n">${p2}%</td><td class="n">${100-p2}%</td></tr>`}).join("")}</tbody></table></div>`:""}
   ${(M.after||[]).length?`<h3>After their attack</h3><p class="note">Where the same team's next attack goes, depending on the previous one.</p>
    <div class="tbl"><table><thead><tr><th>Previous round</th><th class="n">Then A</th><th class="n">Then B</th><th class="n">No clear hit</th><th class="n">Cases</th></tr></thead><tbody>
    ${M.after.map(a=>`<tr><td>${a.twice?`${a.last} 2+ times in a row, the last one ${a.won?"won":"lost"}`:`${a.last} ${a.won?"won":"lost"}`} by the Ts</td><td class="n">${a.A}%</td><td class="n">${a.B}%</td><td class="n">${a.none}%</td><td class="n">${a.n}</td></tr>`).join("")}</tbody></table></div>`:""}
   ${sv&&sv.A&&sv.B?`<h3>When nothing happens</h3><p class="note">Share of attacks still to come at each moment: a quiet round tilts toward the side that is hit late.</p>
    <div class="tbl"><table><thead><tr><th>Clock</th><th class="n">A attacks still to come</th><th class="n">B attacks still to come</th></tr></thead><tbody>
    ${[4,6,8,10,12].filter(i=>i<sv.t.length).map(i=>`<tr><td>${clock(sv.t[i])}</td><td class="n">${Math.round(100*sv.A[i])}%</td><td class="n">${Math.round(100*sv.B[i])}%</td></tr>`).join("")}</tbody></table></div>`:""}
   ${E.contact&&E.contact.zones?`<h3>First duel of the round</h3><p class="note">Where the first duel happens, for each attack. Tap the zone on the T read during the round: the odds update.</p>
    <div class="tbl"><table><thead><tr><th>Zone</th><th class="n">Before an A attack</th><th class="n">Before a B attack</th><th>Usually around</th></tr></thead><tbody>
    ${E.contact.zones.map(z=>`<tr><td>${esc(z)}</td><td class="n">${Math.round(100*((E.contact.lik.A||{})[z]||0))}%</td><td class="n">${Math.round(100*((E.contact.lik.B||{})[z]||0))}%</td><td>${E.contact.t[z]||"—"}</td></tr>`).join("")}</tbody></table></div>`:""}
   ${E.plants?`<h3>Plants and retakes</h3><div class="cols3">${["A","B"].filter(s=>E.plants[s]).map(s=>{const x=E.plants[s];return `<article class="card"><h3>${s} site · ${x.n} plants</h3>
     <p>Median plant ${x.timer}, Ts win ${x.t_win}% after planting.</p><ul>${x.spots.map(sp=>`<li>${esc(sp.where==="center"?"middle of the site":sp.where+" part")}: ${sp.share}% of plants, Ts win ${sp.t_win}%</li>`).join("")}</ul></article>`}).join("")}</div>`:""}
   ${(E.deaths||{}).CT?`<h3>Where each side dies, by moment</h3><div class="cols3"><article class="card"><h3>CTs</h3><div class="tbl"><table><tbody>${deaths("CT")}</tbody></table></div></article><article class="card"><h3>Ts</h3><div class="tbl"><table><tbody>${deaths("T")}</tbody></table></div></article></div>`:""}`}

// ---------- grenades: what to buy with your money, where and when to throw what you hold ----------
const NADE_EN={flash:"flash",smoke:"smoke",he:"HE",molotov:"molotov"},NADE_C={flash:"var(--flash)",smoke:"var(--smoke)",he:"var(--he)",molotov:"var(--molotov)"};
const nadeName=(t,side)=>t==="molotov"&&side==="CT"?"incendiary":NADE_EN[t];
function nadeWin(N,side,w){const W=((N&&N.windows)||{})[w];return W&&typeof W==="object"?W[side]:W||""}
function nadeEff(x,t){
  if(t==="flash")return `flashes an enemy ${x.blind}% of the time${x.kill>=10?`, kill within 3 s ${x.kill}%`:""}${x.team>=25?` (careful: flashes a teammate ${x.team}%)`:""}`;
  if(t==="he")return `${x.dmg} damage on average, hits ${x.hit}% of the time`;
  if(t==="molotov")return `blocks ${esc(x.to)} (thrown in ${Math.round(x.per100)} rounds out of 100)${x.dmg>=5?`, ${x.dmg} damage on average`:""}`;
  return `common smoke (${Math.round(x.per100)} rounds out of 100)${x.win!=null?`, rounds won ${x.win}% when it's used (${x.base_win}% on average)`:""}`}
function nadeLine(N,side,t,x,now,post){return `<span class="nd-t" style="color:${NADE_C[t]}">${nadeName(t,side)}</span> ${esc(x.from)} → <b>${esc(nTo(x,S.map))}</b>, ${post?esc(nadeWin(N,side,"post")):`around ${x.t_med!=null?clock(x.t_med):x.timer}${x.best&&x.best!==x.usual&&t!=="smoke"?` (best moment: ${esc(nadeWin(N,side,x.best))})`:""}`}${now?' <span class="pill" style="color:var(--flash)">now</span>':""}<br><span class="note">${nadeEff(x,t)} · ${esc(x.how)}${x.click?`, ${esc(x.click)} click`:""}</span>`}
function nadePlan(E,cash,held,maxN){const H=Object.assign({},held||{}),plan=[];let n=Object.entries(H).filter(([t])=>t!=="decoy").reduce((a,[,v])=>a+v,0),left=cash;
  const want=E.order.map(o=>o.type),fl=E.order.find(o=>o.type==="flash");if(fl&&fl.strong)want.push("flash");   // a 2nd flash when they blind from your zones
  for(const t of want){if(n>=maxN)break;const o=E.order.find(x=>x.type===t),cap=t==="flash"?2:1;if(!o||(H[t]||0)>=cap||o.price>left)continue;plan.push(o);left-=o.price;H[t]=(H[t]||0)+1;n++}
  return {plan,left,n}}
// the round type the card advises (the same decision as buyTip): with money for a force but a full buy assured next
// round even after a loss, the advice is an eco, and the kit and grenades shown follow it
function advisedType(g){const rt=roundType(g);if(rt==null||rt==="pistol")return rt;
  const pl=typeof econPlan==="function"&&typeof P==="function"&&P()?econPlan(P(),g):null;   // the buy that wins most over the next rounds
  if(pl&&pl.best)return pl.best.k==="half"?"eco":pl.best.k;
  if(rt!=="force")return rt;
  const full=g.side==="CT"?3900:3700,bonus=[1400,1900,2400,2900,3400][Math.min(g.losses||0,4)];
  return g.money+bonus>=full?"eco":"force"}
function buyCard(p,g){if(g.money==null||!g.side||g.practice)return "";const rt=advisedType(g),PL=p.advice.plan||{},N=PL.nades,E=nadeCtx(p,g,N&&((N.maps||{})[g.map]||{})[g.side]).E;
  const KB=((((PL.buys||{}).maps||{})[g.map]||{})[g.side]||{}),sk=sitKey(p,g);
  let kit=(sk&&sk.endsWith("anti_eco")&&KB["anti-eco"])||KB[rt];
  const pl_=typeof econPlan==="function"?econPlan(p,g):null;if(kit&&pl_&&pl_.best&&pl_.best.k==="eco")kit=Object.assign({},kit,{kit:null});   // a save: no weapon to buy
  const C=((N||{}).payoff||{}).count||{},wr=(k,n)=>((C[k]||{})[n]||{}).win;
  let nd="";
  if(E&&E.order.length&&rt&&rt!=="pistol"){
    if(rt==="eco")nd=`<p><b>No grenade this round.</b> ${wr("eco",0)!=null&&wr("eco",2)!=null?`In the base, an eco with 2 grenades wins ${wr("eco",2)}% of rounds vs ${wr("eco",0)}% without: too little to cut into your next buy.`:"Keep your money for the next buy."}</p>`;
    else{const full=rt!=="force",maxN=full?4:2,held=g.nades||{};let cash=g.money,pre="";
      if(full&&!(g.primary&&FULL_W.has(g.primary))){const main=(g.side==="T"?2700:2900)+(g.helmet?0:g.armor>0?350:1000);cash=Math.max(0,g.money-main);pre=`After your rifle and armor (${money(main)}), you'll have ${money(cash)} left. `}
      else if(!full&&!(g.armor>0))pre="Weapon and kevlar first, grenades after. ";
      const {plan,left,n}=nadePlan(E,cash,held,maxN),cost=plan.reduce((a,o)=>a+o.price,0);
      const bonus=[1400,1900,2400,2900,3400][Math.min(g.losses||0,4)],next=left+bonus,need=g.side==="CT"?3900:3700,last=plan[plan.length-1];
      const proof=full?(wr("full",4)!=null?`In the base, a full buy with 4 grenades wins ${wr("full",4)}% of rounds, ${wr("full",0)}% without.`:""):(wr("force",3)!=null?`On a force-buy, 3+ grenades: ${wr("force",3)}% of rounds won, ${wr("force",0)}% without.`:"");
      const tail=next>=need||!plan.length?"":last&&next+last.price>=need?` If you lose this round, you'll have about ${money(next)} next round; without the ${nadeName(last.type,g.side)} ($${last.price}) you'd have ${money(next+last.price)}, enough to full buy again.`:` If you lose this round, you'll have about ${money(next)} next round.`;
      const have=Object.entries(held).filter(([t,v])=>v>0&&NADE_EN[t]).map(([t,v])=>`${v>1?v+" ":""}${nadeName(t,g.side)}${v>1?"es":""}`).join(", ");
      const where=plan.filter((o,i)=>plan.findIndex(x=>x.type===o.type)===i).map(o=>{const x=((E.types[o.type]||{}).picks||[])[0];return x?`<li class="ct">${nadeLine(N,g.side,o.type,x,false)}</li>`:""}).join("");
      nd=`${have?`<p class="note">You already have: ${esc(have)}.</p>`:""}<p>${esc(pre)}${plan.length?"<b>Grenades, in this order:</b>":n>=maxN?"<b>You already have enough grenades for this round.</b>":"<b>Not enough money for a useful grenade.</b>"}</p>
       ${plan.length?`<div class="nd-plan">${plan.map(o=>`<span style="border-color:${NADE_C[o.type]}">${nadeName(o.type,g.side)} $${o.price}</span>`).join("")}<span>total ${money(cost)}</span></div>`:""}
       ${where?`<ul class="big-list">${where}</ul>`:""}<p class="note">${esc(proof)}${tail}</p>`}}
  return `<div class="tread nd"><h3><span>Buy · ${esc(RT_EN[rt]||"round")}</span><small>${money(g.money)}</small></h3>
   <p style="font-size:16px">${esc(buyTip(g,p))}</p>
   ${kit&&(kit.kit||kit.zone)?`<ul class="big-list">${kit.kit?`<li class="exploit"><b>Buy: ${esc(expSwapTxt(p,kit.kit.key))}</b><br><span class="note">${kit.kit.why.map(esc).join(" · ")}</span></li>`:""}${kit.zone?`<li class="exploit"><b>Play: ${esc(kit.zone.key)}</b><br><span class="note">${kit.zone.why.map(esc).join(" · ")}</span></li>`:""}${kit.avoid?`<li class="avoid">Avoid ${esc(kit.avoid.key)} this kind of round</li>`:""}</ul>`:""}
   ${nd}</div>`}
function nadeLive(p,g){const N=(p.advice.plan||{}).nades,E=N&&((N.maps||{})[g.map]||{})[g.side];if(!E||g.health===0)return "";
  const w=g.bomb==="planted"?"post":g.elapsed==null?null:g.elapsed<20?"debut":g.elapsed<40?"prise":g.elapsed<70?"action":"fin";
  // only the throws that fit the time left: thrown now or within the next 25 s (or in this window of the round),
  // after the plant the post-plant ones; a throw whose moment has passed is not proposed any more
  const el=g.elapsed,all=t=>[...(E.types[t].picks||[]),...(E.types[t].post||[])].filter((x,i,a)=>a.indexOf(x)===i);
  const list=t=>{if(w==="post")return (E.types[t].post||[]).slice(0,2);if(el==null||!w)return (E.types[t].picks||[]).slice(0,2);
    const fit=x=>x.best===w||x.usual===w||(x.t_med!=null&&x.t_med>=el-8&&x.t_med<=el+25);
    return all(t).filter(fit).sort((a,b)=>Math.abs((a.t_med??el)-el)-Math.abs((b.t_med??el)-el)).slice(0,2)};
  const held=Object.entries(g.nades||{}).filter(([t,v])=>v>0&&E.types[t]);if(!held.length)return "";
  const KEEP={T:{flash:"pop it for your next peek or for the entry",smoke:"keep it to cut the CTs' view when you plant",
      molotov:"keep it for the post-plant: on the bomb to stop the defuse",he:"keep it for the post-plant, or for the CT who holds the plant"},
    CT:{flash:"keep it for the retake: flash before you go in",smoke:"keep it for the retake: cut one T angle",
      molotov:"keep it for the retake: clear a corner, or stop a plant",he:"keep it for the retake: damage the Ts holding the bomb"}};
  const keep=t=>`no standard throw at this moment: ${(KEEP[g.side]||KEEP.T)[t]||"keep it"}`;
  const rank=t=>{const i=E.order.findIndex(o=>o.type===t);return i<0?9:i};
  const rows=held.sort((a,b)=>rank(a[0])-rank(b[0])).map(([t,v])=>{const ps=list(t);
    return `<li class="ct"><b>${v>1?v+" ":""}${nadeName(t,g.side)}${v>1?"es":""}</b><br>${ps.length?ps.map(x=>nadeLine(N,g.side,t,x,!!w&&(w==="post"||x.best===w||x.usual===w||(x.t_med!=null&&Math.abs(x.t_med-el)<=8)),w==="post"&&(E.types[t].post||[]).includes(x))).join("<br>"):`<span class="note">${keep(t)}</span>`}</li>`}).join("");
  const warn=N.unused_per_death>=0.6?`<p class="note">In your last matches, you die with ${N.unused_per_death} grenade in hand on average: throw it before taking a risky duel.</p>`:"";
  return `<div class="tread nd"><h3><span>Your grenades</span><small>${w?esc(nadeWin(N,g.side,w)):"in play"}</small></h3><ul class="big-list">${rows}</ul>${warn}</div>`}
// the map's lineup book (a player's), your side: every lineup with where to stand, where to aim and where it lands
function bookBlock(p,map,side){const B=((p.advice.plan||{}).lineups||{})[map];if(!B)return "";const L=(B.lineups||[]).filter(x=>x.side===side);if(!L.length)return "";
  const im=(u,a)=>u?`<img src="${esc(u)}" alt="${a}" loading="lazy">`:"";
  return `<h3>Lineup book · ${esc(B.author)}</h3><p class="note">By ${esc(B.author)}, from <a href="${esc(B.repo)}" target="_blank" rel="noopener" style="color:var(--ct)">their GitHub repository</a> (pictures loaded from it): position, aim, landing.</p>
   <div class="book">${["A","Mid","B"].map(s=>L.filter(x=>x.site===s)).filter(l=>l.length).map(l=>l.map(x=>`<article><h4><span class="nd-t" style="color:${NADE_C[x.type]}">${nadeName(x.type,side)}</span> ${esc(x.title)}${x.throw?` <em>${esc(x.throw)}</em>`:""}</h4>
     <div class="shots">${im(x.img_position,"position")}${im(x.img_aim,"aim")}${im(x.img_aim2,"aim, second picture")}${im(x.img_landing,"landing")}</div>
     <p>${x.position?`<b>Stand:</b> ${esc(x.position)} `:""}${x.aim?`<b>Aim:</b> ${esc(x.aim)}`:""}</p></article>`).join("")).join("")}</div>`}
function nadeTable(p,map,side){const N=(p.advice.plan||{}).nades,E=N&&((N.maps||{})[map]||{})[side];if(!E)return `<p class="note">Not enough grenade data on ${MAPN(map)} as ${side}.</p>`;
  const types=[...E.order.map(o=>o.type),...["smoke","flash","molotov","he"].filter(t=>!E.order.some(o=>o.type===t)&&E.types[t])].filter(t=>(E.types[t].picks||[]).length);
  if(!types.length)return "";
  const o0=E.order[0];
  return `<p class="note">${E.personal?`Effective throws from your positions (${E.zones.map(esc).join(", ")}).`:"No match of yours here yet: the most useful throws of this side in the base."}
    Buying order when money is short: ${E.order.map(o=>`${nadeName(o.type,side)} ($${o.price})`).join(" › ")}.${o0&&o0.alone&&E.none?` Bought alone, the ${nadeName(o0.type,side)} wins ${o0.alone.win}% of rounds, vs ${E.none.win}% with no grenade (base).`:""}</p>
   <div class="tbl"><table><thead><tr><th>Grenade</th><th>From → to</th><th>When</th><th>Effect in the base</th><th>How</th><th class="n">Your throws</th></tr></thead><tbody>
   ${types.map(t=>(E.types[t].picks||[]).map(x=>`<tr><td><span class="nd-t" style="color:${NADE_C[t]}">${nadeName(t,side)}</span>${E.types[t].elsewhere?'<br><span class="note">elsewhere on the map</span>':""}</td><td>${esc(x.from)} → <b>${esc(nTo(x,S.map))}</b></td>
     <td>around ${x.t_med!=null?clock(x.t_med):x.timer}${x.best&&x.best!==x.usual&&t!=="smoke"?`<br><span class="note">best: ${esc(nadeWin(N,side,x.best))}</span>`:""}</td><td class="wrap">${nadeEff(x,t)}</td>
     <td class="wrap">${esc(x.how)}${x.click?`, ${esc(x.click)} click`:""}<div class="cmd"><code>${esc(x.setpos)}</code><button type="button">Copy</button></div></td><td class="n">${x.mine||"—"}</td></tr>`).join("")).join("")}</tbody></table></div>
   ${N.unused_per_death!=null?`<p class="note">In your last matches, ${N.unused_per_death} grenade still in hand per death (${(N.unused_last||[]).map(u=>`${MAPN(u.map)}: ${u.unused}`).join(", ")}). Paste the position in the console of a practice server (sv_cheats 1).</p>`:""}`}

// ---------- live bar, polling ----------
function micBtn(){const g=gsiLast||{};if(!D.local)return "";
  // what you hear (your teammates' voices, the game): only once every teammate said yes, for this match only (04/10)
  const team=!g.map||g.practice?"":g.team_rec==="on"?`<button type="button" class="close teamchip on" data-team="off" title="What you hear (your teammates' voices and the game) is recorded for this match: your team agreed. Click to stop.">● Team</button>`
    :g.team_rec==="pending"?`<button type="button" class="close teamchip" data-team="off" title="Your team agreed: what you hear is recorded with your microphone from the start of the match. Click to cancel.">● Team · at the start</button>`
    :`<button type="button" class="close teamchip" data-team="on" title="My team agreed: record what I hear. Only once every teammate said yes: their voices are recorded too (France, art. 226-1), for this match only, to see after it what you did after their calls. Numpad / in game does the same (exec coach_binds once).">Team ○</button>`;
  if(g.mic)return `${g.mic_silent?`<span class="pill weak" title="No sound for a minute">● Mic silent: <a href="#settings" style="color:inherit">check the microphone</a></span>`:`<span class="pill weak" title="Your microphone is recorded to analyze your calls">● Mic</span>`}${g.mic_auto?"":`<button type="button" class="close" data-mic="stop">Stop recording</button>`}${team}`;
  return (g.mic_auto?"":`<button type="button" class="close" data-mic="start" title="Records your microphone to analyze your calls after the match">Record my calls</button>`)+team}
// the focus of the week, small in the live bar: what you work on, never more than one line (05/10)
function liveFocus(){const F=S.player===D.own?focusOf(P()):null;return F?`<span class="lfocus" title="Your focus of the week">Focus · ${esc(F.short)}</span>`:""}
function liveBar(){if(!D.local)return "";const g=gsiLast,focus=document.body.classList.contains("focus");
  const fb=`<button type="button" class="close" id="focus">${focus?"Exit 2nd screen":"2nd screen mode"}</button>`;
  if(gsiFresh())return `<div class="live on" role="status"><span class="dot" aria-hidden="true"></span><b>${MAPN(g.map)}</b><span>${g.side?`${g.side} · ${roleOf(g.map,g.side)}`:"spectating"}</span>
    <span>Round ${g.round??"—"}${g.score_ct!=null?` · CT ${g.score_ct} - ${g.score_t} T`:""}</span>${g.money!=null?`<span>${money(g.money)}</span>`:""}${liveFocus()}
    ${g.round_phase==="over"?`<span class="tip">5 s: why did this round go that way? Then one long exhale.</span>`:""}<span class="sp">${igManual?`<button type="button" class="close" id="follow">Follow the game</button>`:""}${micBtn()}${fb}</span></div>`;
  const st=gsiStatus;
  return `<div class="live"><span class="dot" aria-hidden="true"></span>${st&&st.installed?"<span>I'm ready. Launch your match: I'll follow it from here.</span>"
    :`<span>Pick your map and side, or <a href="#settings" style="color:var(--ct)">turn on game detection</a> and I'll follow your match by myself.</span>`}<span class="sp">${micBtn()}${fb}</span></div>`}
async function gsiPoll(){clearTimeout(gsiTimer);if(!D.local||S.view!=="ingame")return;
  try{const g=await (await fetch("/api/gsi/state")).json();const sig=x=>x?[x.map,x.side,x.round,x.round_phase,x.money,x.bomb,x.age!=null&&x.age<75,JSON.stringify(x.hist||{}),JSON.stringify(x.nades||{}),x.health===0,x.elapsed==null?"":Math.floor(x.elapsed/5),x.pos?x.pos.map(c=>Math.round(c/100)).join(","):"",x.call?x.call.t:"",x.tdir?[x.tdir.round,x.tdir.dir,x.tdir.via,x.tdir.tempo].join(","):"",x.ping?x.ping.t:"",x.wily?x.wily.t:"",JSON.stringify(x.wily_match||{})].join("|"):"";
    const before=sig(gsiLast)+(gsiLast&&gsiLast.mic);gsiLast=g&&Object.keys(g).length?g:null;
    if(gsiLast&&S.player&&D.players[S.player]&&typeof liveLog==="function")liveLog(D.players[S.player],gsiLast);   // checked after the match
    if(gsiLast&&S.player===D.own&&D.players[S.player]&&typeof pathCalls==="function")pathCalls(D.players[S.player],gsiLast);   // numpad 1-2-3
    if(gsiLast&&S.player===D.own&&D.players[S.player]&&typeof coachVoice==="function")coachVoice(D.players[S.player],gsiLast);   // the coach's voice at the buy time
    if(gsiLast&&S.player===D.own&&typeof coachInfo==="function")coachInfo(gsiLast);   // "l'info !" when you die
    if(gsiLast&&S.player===D.own&&typeof wilyVoice==="function")wilyVoice(gsiLast);   // Wily answers what you asked it (06/10)
    if(sig(gsiLast)+(gsiLast&&gsiLast.mic)!==before&&S.view==="ingame"&&S.player&&D.players[S.player])renderIngame()}catch(e){}
  gsiTimer=setTimeout(gsiPoll,1000)}   // the game sends every 0.25 s

// ---------- the page ----------
// a map plan's material for any map and side (the In game page: the map and side on screen; Prepare's map sheets: each
// map you picked, both sides)
function planData(p,m,R0,MAP=S.map,SIDE=S.side){const PL=p.advice.plan||{};
  const plan=((p.advice.maps||{})[MAP]||{})[SIDE],coach=((p.cross_notes||{})[MAP]||{})[SIDE],bl=plan?plan.bullets:[];
  const isAv=(c,t,i)=>c.kinds?c.kinds[i]==="avoid":/[ée]vite|avoid/i.test(t),cAvoid=coach?coach.plan.filter((t,i)=>isAv(coach,t,i)):[],cGood=coach?coach.plan.filter((t,i)=>!isAv(coach,t,i)):[];
  // a zone already covered by a coach note: its generic bullet is not repeated
  const zkey=x=>{let s=String(x).replace(/<[^>]+>/g,"").trim().toLowerCase();s=s.replace(/^(worth a try|à essayer) ?: /,"").replace(/^(play|joue plus) (souvent )?/,"");
    return s.split(/ ?: | \(|\.|,| more/)[0].trim().replace(/^bombsite (\w)/,"$1 site").replace(/^site (\w)/,"$1 site")},coachZ=new Set((coach?coach.plan:[]).map(zkey));
  const good=bl.filter(b=>b.kind==="exploit"&&!coachZ.has(zkey(b.text))),bad=bl.filter(b=>b.kind==="avoid"&&!coachZ.has(zkey(b.text))),tries=bl.filter(b=>b.kind==="try"&&!coachZ.has(zkey(b.text))),times=bl.filter(b=>b.kind==="timing");
  const avZ=new Set([...bad.map(b=>zkey(b.text)),...cAvoid.map(zkey)]),timesOk=times.filter(b=>!avZ.has(zkey(b.text)));
  const strong=((PL.mid||{}).strong||[]).slice(0,2),rules=(p.advice.rules||[]).slice(0,2);
  const reflex=(PL.playbook||[]).filter(x=>x.side===SIDE||x.side==="both"||x.side==="tous").slice().sort((a,b)=>(b.prio||0)-(a.prio||0)).slice(0,3);
  const rot=SIDE==="CT"?Object.entries((PL.routes||{})[MAP]||{}).sort().map(([s,r])=>{const b=[r.pro.best,r.base.best].find(x=>x&&x.travel>=3);return b?{site:s,route:b.route,travel:b.travel,died:b.died,who:r.pro.best?"pros":"players of the base"}:null}).filter(Boolean):[];
  const exps=((PL.experiments||{}).experiments||[]).filter(e=>e.status==="active"),recs=((PL.context||{}).recs||[]).filter(r=>r.kind==="stop"||r.kind==="tilt");
  const pos=R0?((R0.positions||{})[SIDE]||{}):{},rifle=((pos.rifle||{}).zones||[]).filter(z=>z.duel_win!=null&&z.share>=4);
  const goodZ=rifle.filter(z=>z.duel_win>=53).sort((a,b)=>b.duel_win-a.duel_win).slice(0,3),badZ=rifle.filter(z=>z.duel_win<=47).sort((a,b)=>a.duel_win-b.duel_win).slice(0,2);
  const awpZ=((pos.awp||{}).zones||[]).filter(z=>z.duel_win!=null&&(z.duels||0)>=15).sort((a,b)=>b.duel_win-a.duel_win)[0],proAwp=((pos.pro_awp||{}).zones||[]).slice(0,2);
  const pl=(R0&&R0.plants)||{},baseGood=[],baseBad=[];
  if(R0){
    if(pl.A&&pl.B){const hi=pl.A.t_win>=pl.B.t_win?"A":"B",lo=hi==="A"?"B":"A",most=pl.A.share>=pl.B.share?"A":"B";
      baseGood.push(SIDE==="T"?`<b>Plant ${hi} rather</b>: Ts win ${pl[hi].t_win}% of the rounds where they plant ${hi}, ${pl[lo].t_win}% on ${lo}. Median plant around ${clock(pl[hi].plant_t)}.`
        :`<b>Most attacked site: ${most}</b> (${pl[most].share}% of plants in the base): the extra player goes there.`)}
    goodZ.forEach(z=>baseGood.push(`<b>${esc(z.name)}</b>: ${z.duel_win}% of duels won by ${SIDE}s of the base (${z.share}% of them play there).`));
    if(awpZ)baseGood.push(`<b>With the AWP: ${esc(awpZ.name)}</b> (${awpZ.duel_win}% of duels won)${proAwp.length?`. Pro AWPers: ${proAwp.map(z=>esc(z.name)).join(", ")}`:""}.`);
    badZ.forEach(z=>baseBad.push(`<b>${esc(z.name)}</b>: only ${z.duel_win}% of duels won in the base (${z.share}% of ${SIDE}s play there). Not dry: with a flash or in pairs.`))}
  const Sd=m?m.sides[SIDE]:null;
  return {PL,plan,coach,good,bad,tries,times,timesOk,cGood,cAvoid,strong,rules,reflex,rot,exps,recs,rifle,proAwp,baseGood,baseBad,Sd}}
function planColumns(p,m,R0){const {plan,good,bad,tries,timesOk,cGood,cAvoid,strong,rules,reflex,rot,exps,recs,rifle,proAwp,baseGood,baseBad,Sd}=planData(p,m,R0);
  return {rifle,proAwp,plan,Sd,html:`${R0?`<p class="note">No match of yours on ${MAPN(S.map)} yet: this sheet comes from ${R0.rounds||"—"} rounds of the base and pro demos. It becomes personal after your first matches here.</p>`:""}
   <div class="cols3 guide">
    <div class="igcol"><h3 class="good">Your strengths here</h3>
     <ul class="big-list">${[...baseGood.map(t=>`<li class="exploit">${t}</li>`),...cGood.map(t=>`<li class="coach">${t}</li>`),...good.map(b=>`<li class="exploit">${b.text}</li>`),
       ...tries.slice(0,1).map(b=>`<li class="try">${b.text}</li>`),...strong.map(s=>`<li class="good">${esc(s.text)}</li>`)].join("")
       ||`<li>Not enough matches ${S.map?`on ${MAPN(S.map)} `:""}as ${S.side} yet: lean on your reminders below.</li>`}</ul>
     ${Sd&&plan&&plan.key_nades.length?`<h3>Key grenades</h3><ul class="big-list">${plan.key_nades.slice(0,3).map(i=>{const l=Sd.lineups[i];return `<li class="ct"><b>${TYPE[l.type]}</b> ${esc(l.from_zone)} → ${esc(nTo(l,S.map)||"?")} · ${esc(l.how)}${l.t!=null?` · ${clock(l.t)}`:""}</li>`}).join("")}</ul>`:""}</div>
    <div class="igcol"><h3 class="bad">Avoid</h3>
     <ul class="big-list">${[...baseBad.map(t=>`<li class="avoid">${t}</li>`),...cAvoid.map(t=>`<li class="avoid">${t}</li>`),...bad.map(b=>`<li class="avoid">${b.text}</li>`),...rules.map(r=>`<li class="bad"><b>${esc(r.short)}</b>${r.standing?`<br><span class="note">${esc(r.standing)}</span>`:""}</li>`)].join("")||"<li>Nothing flagged yet.</li>"}</ul></div>
    <div class="igcol">${reflex.length?`<h3 class="warn">Reflexes</h3><ul class="big-list">${reflex.map(x=>`<li class="timing"><b>If ${esc(lc(x.if))}</b> → ${esc(x.then)}</li>`).join("")}</ul>`:""}
     ${timesOk.length?`<h3 class="warn">Timings</h3><ul class="big-list">${timesOk.slice(0,2).map(b=>`<li class="timing">${b.text}</li>`).join("")}</ul>`:""}
     ${rot.length?`<h3>Rotations</h3><ul class="big-list">${rot.map(r=>`<li class="ct">To ${r.site}: <b>${esc(r.route)}</b> (${r.travel} s, ${r.died}% deaths on the way among ${r.who})</li>`).join("")}</ul>`:""}</div>
   </div>
   <div class="reminders">
    ${exps.map(e=>`<div><b>Running experiment</b>${esc(e.title)}</div>`).join("")}
    <div><b>Session rule</b>${recs.length?esc(recs[0].text):"A 10-15 min break after a loss, stop after 2 losses in a row."}</div>
    <div><b>Economy</b>We buy together. Force only if everyone can still full buy next round ($3,700 T, $3,900 CT).</div>
    ${D.local?`<div><b>Before the 1st game</b><a href="#prepare" style="color:var(--flash)">Prepare: warm-up, journal, map sheets</a></div>`:""}
   </div>`}}
// T side: what to run (the plays that win on this map for your kind of round, small samples pulled toward the map's
// average) early in the round, and the clock when no bomb is down (commit, plant, save)
function tPlanLive(p,g){const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[g.map],P_=M&&M.plays;if(!P_||!P_.win)return "";
  const el=g.elapsed,out=[];
  if(g.round_phase==="freezetime"||(el!=null&&el<35)){
    const rt=advisedType(g),C=((P_.win_ctx||{})[rt==="pistol"?"pistol":rt])||{},avg=(M.all&&M.all.t_win)||45;
    const lb=(w,n)=>{const z=1.28,ph=w/100;return n?(ph+z*z/(2*n)-z*Math.sqrt(ph*(1-ph)/n+z*z/(4*n*n)))/(1+z*z/n):0};   // same ranking as the full-screen panel: a small sample doesn't win
    const rows=Object.entries(P_.win).filter(([k])=>k!=="none").map(([k,w])=>{const c=C[k],use=c&&c[0]>=8,n=use?c[0]:(P_.n||{})[k]||0,wr=use?c[1]:w;
      return {k,n,wr,use,won:Math.round(n*wr/100),score:lb(wr,n)}}).filter(r=>r.n>=8).sort((a,b)=>b.score-a.score).slice(0,3);
    if(rows.length)out.push(`<p><b>Plays that win here</b> (${rows.some(r=>r.use)?`${esc(RT_EN[rt]||rt)} rounds`:"all rounds"}, won / played): ${rows.map(r=>`${esc((P_.label||{})[r.k]||r.k)} <b>${r.wr}%</b> <span class="note">(${r.won}/${r.n})</span>`).join(" · ")}</p>`);
    const TP=M.tplan||{},ck=rt==="pistol"?"pistol":rt,tp=(TP.tempo||{})[ck]||{},DN={rush:"rush",fast:"1-2 Ts early",exec:"execute",late:"late hit"};
    const tps=Object.entries(tp).sort((a,b)=>b[1][1]-a[1][1]);
    if(tps.length)out.push(`<p><b>Tempo</b>: ${tps.map(([k,v])=>`${DN[k]} <b>${v[1]}%</b> <span class="note">(${v[0]})</span>`).join(" · ")}${tp.late&&tp.late[1]<40?". Hit before 0:45: late hits lose.":""}</p>`);
    const su=(TP.setup||{})[ck]||(TP.setup||{}).all;
    if(su&&su.top&&su.top.length){const t0=su.top[0],lt=["A","B"].filter(L=>(su.light||{})[L]>=50);
      out.push(`<p><b>CTs 20 s in</b>: most often ${t0[0]} on the A side, ${t0[1]} on B${t0[2]?`, ${t0[2]} mid`:""} (${t0[3]}% of rounds).${lt.map(L=>` ${L} is held by 1 CT or none ${su.light[L]}% of the time.`).join("")}</p>`)}
    const fk=TP.fake||{};if(fk.switch&&fk.direct&&fk.switch[0]>=20&&fk.switch[1]-fk.direct[1]>=5)
      out.push(`<p><b>Fake</b>: showing on one site first, then hitting the other, wins <b>${fk.switch[1]}%</b> <span class="note">(${fk.switch[0]})</span> vs ${fk.direct[1]}% straight in.</p>`);
    const ro=TP.rotation||{};if(ro.A||ro.B)out.push(`<p><b>After your hit</b>: CTs from the other site reach you ${["A","B"].filter(L=>ro[L]).map(L=>`on ${L} after ~${Math.round(ro[L].med)} s`).join(", ")} (1 in 4 much faster): plant and set your crossfires right away.</p>`);
    const sm=TP.smokes||{};const sl=["A","B"].filter(L=>(sm[L]||[]).length).map(L=>`${L}: ${sm[L].slice(0,2).map(x=>`${esc(x.from)} → ${esc(nTo(x,S.map))} <b>${x.win}%</b> <span class="note">(${x.n}, ~${esc(x.timer)})</span>`).join(" · ")}`);
    if(sl.length)out.push(`<p><b>Smokes in won rounds</b> (vs ${(sm.A||sm.B)[0].base_win}% on average): ${sl.join(" — ")}</p>`)}
  if(g.round_phase==="live"&&g.bomb!=="planted"&&el!=null&&el>=35&&el<70){const tp=(((M.tplan||{}).tempo)||{})[advisedType(g)]||{};
    out.push(`<p><b>Execute window</b>: ${tp.exec?`executes win ${tp.exec[1]}% here`:"go together"}${tp.late?`, late hits ${tp.late[1]}%`:""}. Throw your smokes and flashes, then go in together.</p>`)}
  const left=g.round_phase==="live"&&g.phase_left!=null&&g.bomb!=="planted"?g.phase_left:el!=null?Math.max(0,RLEN()-el):null;
  if(g.round_phase==="live"&&g.bomb!=="planted"&&left!=null&&left<=45){
    out.push(`<p class="danger"><b>${Math.floor(left/60)}:${String(Math.floor(left%60)).padStart(2,"0")} left, no bomb down:</b> ${left>40?"commit to a site now: late hits lose most of their rounds.":left>20?"go now: plant at the closest safe spot while the others hold the angles.":"plant now if you're on the site, otherwise save your weapon."}</p>`)}
  return out.length?`<div class="tread" style="border-left-color:var(--t)"><h3><span>Your T plan</span><small>${el!=null?clock(el):""}</small></h3>${out.join("")}</div>`:""}
// the other side's money, read from the rounds of the half: right after a lost pistol they're on eco; after that, the
// base's table of buys by losses in a row (TS.econ) gives eco / force / full
function enemyBuy(p,g){const TS=(p.advice.plan||{}).tside,R=((g.hist||{}).rounds)||{},E=(TS||{}).econ||{};
  if(g.round==null||!g.side)return null;const hs=halfStart(g.round);if(g.round===hs)return {pistol:1};
  let streak=0,last=null;
  for(let n=g.round-1;n>=hs;n--){const w=(R[n]||{}).win;if(!w)break;if(last===null)last=w;if(w===g.side)streak++;else break}
  if(last===null)return null;
  if(g.round===hs+1&&last===g.side)return {eco:.9,force:.1,full:0};   // they lost the pistol
  if(g.round===hs+1)return {eco:0,force:.6,full:.4};   // they won it: SMGs and upgrades, rifles for the ones with kills
  const x=E[last!==g.side?"won":streak>=3?"lost3":"lost"+streak];
  return x?{eco:x.eco/100,force:x.force/100,full:x.full/100}:null}
// the economic situation of the round: your buy against theirs, and the card measured for it in the base
function sitKey(p,g){const mine=advisedType(g),eb=enemyBuy(p,g)||{},eco=(eb.eco||0)>=.6,full=(eb.full||0)>=.5;
  if(mine==="pistol")return null;
  if(mine==="full"&&eco)return g.side==="CT"?"ct_anti_eco":"t_anti_eco";
  if(mine==="full"&&full)return "full_full";
  if(mine==="force"&&full)return g.side==="CT"?"ct_force":"t_force";
  if(mine==="eco"&&full&&g.side==="T")return "t_eco";
  return null}
const SIT_T={ct_anti_eco:"Anti-eco: they're likely on eco",t_anti_eco:"Anti-eco: they're likely on eco",full_full:"Full buy vs full buy",
  ct_force:"Your force vs their full buy",t_force:"Your force vs their full buy",t_eco:"Your eco vs their full buy"};
function situationCard(p,g){const SI=(((p.advice.plan||{}).tside)||{}).situations||{},k=sitKey(p,g),c=k&&SI[k];if(!c)return "";
  const ct=g.side==="CT",win=ct?100-c.t_win:c.t_win,e=c[`early_${g.side}`],DN={rush:"rush",fast:"1-2 Ts early",exec:"execute",late:"late hit"};
  const tp=Object.entries(c.tempo||{}).sort((a,b)=>b[1][1]-a[1][1]).map(([d,v])=>`${DN[d]||d} ${ct?100-v[1]:v[1]}%`).join(" · ");
  const tips=[];
  if(e)tips.push(`<li class="exploit"><b>No free duel before 20 s</b>: your side wins <b>${e[0]}%</b> with nobody dead by 20 s, ${e[1]}% when one of you dies early (${e[2]} rounds).</li>`);
  if(k.endsWith("anti_eco"))tips.push(`<li class="exploit"><b>No AWP this round</b>: $100 per kill and they come close. A rifle ($300 per kill) or an SMG ($600) pays more. Hold together, don't chase.</li>`);
  if(k==="t_force"||k==="ct_force")tips.push(`<li>${ct?"On a force, stack and play for the retake or the crossfire: don't take long duels.":"On a force, go together: executes win the most, 1-2 Ts early almost never."}</li>`);
  if(k==="t_eco")tips.push(`<li>On an eco: stack one site and go together, or save. Trading kills with pistols at close range is your only chance.</li>`);
  return `<div class="tread" style="border-left-color:var(--flash)"><h3><span>${esc(SIT_T[k])}</span><small>${win}% won by your side</small></h3>
   <ul class="big-list">${tips.join("")}</ul>${tp?`<p class="note">${ct?"Your win rate":"T win rate"} by the Ts' tempo: ${tp}${ct?` · they rush ${c.rush}% of these rounds`:""}.</p>`:""}
   <p class="note">${c.n} rounds of the base in this situation, all maps.</p></div>`}
// pistol as CT: what wins against the pistol rush (measured on every map of the base), with this map's rush odds
function pistolCT(p,g){const TS=(p.advice.plan||{}).tside,SI=((TS||{}).situations||{}).pistol_ct,M=TS&&TS.maps&&TS.maps[g.map];if(!SI||!M)return "";
  const pr=((M.plays||{}).prior||{}).pistol||{},rA=Math.round(100*(pr.rushA||0)),rB=Math.round(100*(pr.rushB||0)),R=SI.rush||{},c=(o,k)=>(o||{})[k];
  const k0=c(R.kevlar,"0-2"),k5=c(R.kevlar,"5")||c(R.kevlar,"3-4"),s1=c(R.on_site,"1"),s2=c(R.on_site,"2+"),n0=c(R.nades,"0-1"),n2=c(R.nades,"2+");
  const top=rA>=rB?["A",rA]:["B",rB];
  return `<div class="tread" style="border-left-color:var(--ct)"><h3><span>Pistol round · CT</span><small>${MAPN(g.map)}</small></h3>
   <p>Ts rush <b>${rA+rB}%</b> of pistols here (rush A ${rA}%, rush B ${rB}%; ${SI.rush_share}% on every map).</p>
   <ul class="big-list">
    ${k0&&k5?`<li class="exploit"><b>Buy kevlar</b>: against a rush, CTs win <b>${k5[1]}%</b> with ${c(R.kevlar,"5")?"5 kevlars":"3-4 kevlars"} vs ${k0[1]}% with 2 or fewer.</li>`:""}
    ${n0&&n2?`<li>Grenades: no gain measured against the rush (${n2[1]}% with 2+ vs ${n0[1]}% with 0-1). Kevlar first.</li>`:""}
    ${s1&&s2?`<li class="exploit"><b>Two on the rushed site</b>: ${s2[1]}% won with 2+ CTs there vs ${s1[1]}% alone. Here, ${top[0]} gets the most rushes (${top[1]}%).</li>`:""}
   </ul><p class="note">${SI.n} pistol rounds of the base, all maps.</p></div>`}
function nowPanel(p,g,following,opt){const noBuy=opt&&opt.noBuy;
  if(!following){const TS=(p.advice.plan||{}).tside,M=S.side==="CT"&&TS&&TS.maps&&TS.maps[S.map];
    return `<div class="now-empty"><b>${gsiFresh()?"You picked a map by hand":"Waiting for your match"}</b>
     <span class="mini">${gsiFresh()?"This page shows your pick, not the live game.":"As soon as CS2 sends the round, this panel shows what matters now: what to buy, where the Ts are likely to go, what to do with your grenades."}</span>
     ${M?`<span class="mini">Ts on ${MAPN(S.map)}: pistol round A ${(M.ctx.pistol||M.all).A}% / B ${(M.ctx.pistol||M.all).B}%, full buys A ${(M.ctx.full||M.all).A}% / B ${(M.ctx.full||M.all).B}%. More in the "T habits" tab.</span>`:""}</div>`}
  const ph=g.round_phase,ct=g.side==="CT",ev=evFor(g),out=[];
  if(g.practice)return `<div class="now-empty"><b>Practice server</b><span class="mini">More money or a longer round than a real match allows: the live advice (buys, T read) and the automatic recording are off here. The radar, your positions and grenades still work: pick them below.</span></div>`;
  if(ph==="freezetime"){if(!noBuy)out.push(buyCard(p,g));if(ct&&(g.round===1||g.round===13))out.push(pistolCT(p,g));out.push(situationCard(p,g));if(ct)out.push(tsideLive(p,g));else out.push(vDir(p,g)||tPlanLive(p,g))}
  else if(ph==="live"){
    if(g.bomb==="planted"){const site=ev.site||((typeof autoSite==="function"&&autoSite(p,g))||{}).site||null;
      if(site)out.push(retakeCard(p,g,site));
      else out.push(`<div class="tread" style="border-left-color:var(--bad)"><h3><span>Bomb planted</span></h3><div class="ev" role="group" aria-label="Site"><span class="l">On</span>${["A","B"].map(s=>`<button type="button" class="site-${s}" data-evsite="${s}" aria-pressed="false">${s} site</button>`).join("")}</div><p class="mini">Pick the site: plant spots, ${ct?"retake":"post-plant"} odds and danger zones show up.</p></div>`);
      out.push(nadeLive(p,g))}
    else{if(ct)out.push(tsideLive(p,g));else{out.push(vDir(p,g)||tPlanLive(p,g));const TS=(p.advice.plan||{}).tside,M=TS&&TS.maps&&TS.maps[g.map];if(M)out.push(`<div class="tread" style="border-left-color:var(--t)"><h3><span>Round ${g.round}</span><small>${g.elapsed!=null?clock(g.elapsed):""}</small></h3>${dangerNow(M.evidence,"T",null,g.elapsed)||'<p class="mini">Play your role; the danger zones show up when there is enough data.</p>'}</div>`)}
      out.push(nadeLive(p,g))}}
  else if(ph==="over"&&ct)out.push(tsideLive(p,g));
  return out.filter(Boolean).join("")||`<div class="now-empty"><b>Round ${g.round}</b><span class="mini">${ph==="over"?"5 s: why did this round go that way? Then one long exhale.":"Nothing to flag right now."}</span></div>`}
function renderIngame(){
  const p=P(),v=$("#v-ingame"),PL=p.advice.plan||{},live=gsiFresh(),refs=PL.map_refs||{},mine=mapsOf(p);
  const maps=bombFirst([...mine,...Object.keys(refs).filter(k=>!mine.some(x=>x.map===k)).sort().map(k=>({map:k,n:0}))],x=>x.map);
  if(live&&!igManual){S.map=gsiLast.map;if(gsiLast.side)S.side=gsiLast.side}
  if(!S.map||(!maps.some(m=>m.map===S.map)&&!(live&&!igManual)))S.map=maps[0]?.map||null;
  const m=S.map?crossMap(p,S.map):null;
  if(m&&!m.levels.some(l=>l.key===S.level))S.level=m.levels[0].key;
  {const TS_=PL.tside,M_=TS_&&TS_.maps&&TS_.maps[S.map],site_=live&&!igManual&&gsiLast.map===S.map&&igEv.key===`${gsiLast.map}|${gsiLast.round}`&&igEv.site;   // show the plant spots' level
   const sp_=site_&&M_&&(((M_.evidence||{}).plants||{})[site_]||{}).spots;if(m&&sp_&&sp_.length&&sp_[0].level&&m.levels.some(l=>l.key===sp_[0].level))S.level=sp_[0].level}
  const R0=!m?refs[S.map]:null,following=!!(live&&!igManual&&gsiLast.map===S.map&&gsiLast.side===S.side),focus=document.body.classList.contains("focus");
  const TSm=PL.tside&&PL.tside.maps&&PL.tside.maps[S.map],GEOm=TSm&&TSm.geo,liveR=!!((TSm&&GEOm&&GEOm.radar&&(S.side==="CT"?TSm.plays&&GEOm.sites:following))||(following&&typeof isHostage==="function"&&isHostage(S.map)&&(PL.hostage||{})[S.map]));   // live radar: CT always, T while following the game; hostage maps while following
  const LVs=(m&&m.levels)||(R0&&R0.levels)||((GEOm&&GEOm.radar&&GEOm.radar.levels)||[]).map(l=>({key:l.key,name:l.key==="lower"?"Lower level":l.key==="upper"?"Main level":"Map"}));
  if(liveR&&LVs.length&&!LVs.some(l=>l.key===S.level))S.level=LVs[0].key;
  const TABS=[["plan","Game plan"],["buys","Buys"],["nades","Grenades"],...(S.side==="CT"?[["t","T habits"]]:[])];
  let tab=store("igtab")||"plan";if(!TABS.some(t=>t[0]===tab))tab="plan";
  const cols=planColumns(p,m,R0);
  const body={plan:()=>cols.html,buys:()=>S.map?buyRows(p,S.map,S.side,following?roundType(gsiLast):null):"",nades:()=>S.map?nadeTable(p,S.map,S.side)+bookBlock(p,S.map,S.side):"",t:()=>S.map?tsideTable(p,S.map):""}[tab]();
  const radarHTML=liveR?radarShell(layerBtns()+levelBtns({levels:LVs},S.level)):m?radarShell(levelBtns(m,S.level)):R0?radarShell((R0.levels||[]).length>1?`<div class="btns" role="group" aria-label="Level">${R0.levels.map(l=>`<button type="button" data-blevel="${l.key}">${esc(l.name)}</button>`).join("")}</div>`:""):`<div class="empty">No radar for this map yet.</div>`;
  const full=!!(following&&store("igfull")!==false),tkey=gsiLast?`${gsiLast.map}|${gsiLast.round}`:"";
  document.body.classList.toggle("igfull",full);
  if(full){const ph=gsiLast.round_phase,buy=ph==="freezetime"&&igToastOff!==tkey?buyVisual(p,gsiLast):"";
    const side=store("igside")!==false,toast=buy?`<div class="ig-toast" role="status" aria-live="polite"><button type="button" class="close tx" id="toastx" aria-label="Hide the buy advice">✕</button>${buy}</div>`:"";
    v.innerHTML=`<div class="ig-full${side?"":" noside"}">
     <div class="ig-map">${radarHTML}</div>
     <div class="ig-hud">${liveBar()}<span class="hudbtns"><button type="button" class="close" id="sidebtn" aria-pressed="${side}">${side?"◀ Hide panel":"▶ Show panel"}</button><button type="button" class="close" id="fsbtn">${document.fullscreenElement?"Exit full screen":"⛶ Full screen"}</button><button type="button" class="close" id="igfull">Normal view</button></span></div>
     ${side?"":toast}
     <div class="now ig-side" id="now">${side?toast:""}${nowVisual(p,gsiLast,following)}</div></div>`}
  else v.innerHTML=`${liveBar()}
   ${following?"":missNote(p)}
   ${following&&focus?"":`<div class="ig-top">
    <div class="chips" role="group" aria-label="Map">${maps.map((x,i)=>`${chipSep(maps,i,y=>y.map)}<button type="button" data-map="${x.map}" aria-pressed="${x.map===S.map}">${MAPN(x.map)}<small>${x.n||"base"}</small></button>`).join("")}${S.map&&!maps.some(x=>x.map===S.map)?`<button type="button" aria-pressed="true">${MAPN(S.map)}<small>0</small></button>`:""}</div>
    <div class="btns side big" role="group" aria-label="Side"><button type="button" data-side="T" aria-pressed="${S.side==="T"}">T · ${S.map?roleOf(S.map,"T"):"attack"}</button><button type="button" data-side="CT" aria-pressed="${S.side==="CT"}">CT · ${S.map?roleOf(S.map,"CT"):"defense"}</button></div>
    ${D.local?"":`<button type="button" class="close" id="focus">${focus?"Exit 2nd screen":"2nd screen mode"}</button>`}
   </div>`}
   ${following?`<div class="ig-fullbtn"><button type="button" class="close" id="igfull">⛶ Full map</button></div>`:""}
   <div class="ig2"><div class="now" id="now">${nowPanel(p,gsiLast,following)}</div>
    <div class="igcol ig-radar">${radarHTML}</div></div>
   ${tabs(v,"Map guide",TABS,tab)}
   <div class="tabpanel" role="tabpanel">${body}</div>`;
  copyBtn(v);
  if(typeof slotMeasure==="function")slotMeasure($("#now",v));   // the panel's slots keep their room
  const fbt=$("#igfull",v);if(fbt)fbt.onclick=()=>{store("igfull",!full);renderIngame()};
  const fsb=$("#fsbtn",v);if(fsb)fsb.onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch(e){}renderIngame()};
  const sbt=$("#sidebtn",v);if(sbt)sbt.onclick=()=>{store("igside",store("igside")===false);renderIngame()};
  const tx=$("#toastx",v);if(tx)tx.onclick=()=>{igToastOff=tkey;tx.parentElement.remove()};
  $$("[data-tab]",v).forEach(b=>b.onclick=()=>{store("igtab",b.dataset.tab.split(":")[1]);renderIngame()});
  $$("[data-map]",v).forEach(b=>b.onclick=()=>{S.map=b.dataset.map;S.level=null;igManual=true;store("map",S.map);renderIngame()});
  $$("[data-side]",v).forEach(b=>b.onclick=()=>{S.side=b.dataset.side;igManual=true;store("side",S.side);renderIngame()});
  $$("[data-level]",v).forEach(b=>b.onclick=()=>{S.level=b.dataset.level;renderIngame()});
  const fb=$("#focus",v);if(fb)fb.onclick=()=>{document.body.classList.toggle("focus");store("focus",document.body.classList.contains("focus"));renderIngame()};
  const fl=$("#follow",v);if(fl)fl.onclick=()=>{igManual=false;renderIngame()};
  const post=async body=>{try{const g=await api("/api/gsi/site",body);if(g&&g.map)gsiLast=Object.assign(gsiLast||{},{hist:g.hist})}catch(e){}};
  const mark=async(n,site,extra)=>{await post(Object.assign({round:n,site},extra||{}));renderIngame()};
  const here=()=>following&&gsiLast.round?gsiLast.round:null,el_=()=>gsiLast.elapsed!=null?gsiLast.elapsed:null;
  $$("[data-site]",v).forEach(b=>b.onclick=()=>mark(+b.dataset.round,b.getAttribute("aria-pressed")==="true"?null:b.dataset.site));
  $$("[data-cycle]",v).forEach(b=>b.onclick=()=>{const n=+b.dataset.cycle,cur=((gsiLast.hist||{}).sites||{})[n]||null,nx={null:"A",A:"B",B:"-","-":null}[cur];mark(n,nx)});
  $$("[data-evz]",v).forEach(b=>b.onclick=()=>{const z=igEv.contact===b.dataset.evz?null:b.dataset.evz;igEv.contact=z;if(!z)igEv.alone=null;renderIngame();
    if(here())post(z?{round:here(),contact:z,contact_t:el_()}:{round:here(),contact:null,contact_t:null,alone:null})});   // kept with the round
  $$("[data-evalone]",v).forEach(b=>b.onclick=()=>{const a=b.dataset.evalone==="1";igEv.alone=igEv.alone===a?null:a;renderIngame();if(here())post({round:here(),alone:igEv.alone})});
  $$("[data-dyn]",v).forEach(b=>b.onclick=async()=>{await post({round:+b.dataset.round,dyn:b.getAttribute("aria-pressed")==="true"?null:b.dataset.dyn});renderIngame()});
  $$("[data-lone]",v).forEach(b=>b.onclick=async()=>{await post({round:+b.dataset.lone,lone:b.getAttribute("aria-pressed")==="true"?null:true});renderIngame()});
  $$("[data-evsite]",v).forEach(b=>b.onclick=()=>{const s=b.dataset.evsite,on=igEv.site===s;igEv.site=on?null:s;
    if(following&&gsiLast.side==="CT"&&gsiLast.round)mark(gsiLast.round,on?null:s,{site_t:on?null:el_()});else renderIngame()});   // also marks the round for the history
  $$("[data-mic]",v).forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api("/api/voice/"+b.dataset.mic,{sid:p.steamid});gsiLast=Object.assign(gsiLast||{},{mic:b.dataset.mic==="start"});renderIngame()}catch(e){b.textContent=e.message}});
  $$("[data-team]",v).forEach(b=>b.onclick=async()=>{b.disabled=true;try{const t=(await api("/api/voice/team",{on:b.dataset.team==="on"})).team||{};gsiLast=Object.assign(gsiLast||{},{team_rec:t.on?"on":t.pending?"pending":null});renderIngame()}catch(e){b.textContent=e.message}});
  // radar: your data, or the base's positions; plant spots when the bomb site is known
  const plantSpots=()=>{const TS=PL.tside,M=TS&&TS.maps&&TS.maps[S.map],site=following&&(igEv.site||null);if(!M||!site||!(M.evidence||{}).plants)return [];
    return (((M.evidence.plants||{})[site]||{}).spots||[]).map(s=>({px:s.px,level:s.level,label:`plant ${s.share}%`,color:"var(--bad)",title:`Plant spot on ${site}: ${s.share}% of plants, Ts win ${s.t_win}% after it`}))};
  if(liveR){const draw=()=>{const box=$(".radar-box",v);if(!box||S.view!=="ingame")return;
      const gR=following&&gsiLast&&gsiLast.map_phase==="warmup"&&typeof briefState==="function"?briefState(gsiLast):gsiLast;
      liveRadar(box,p,S.map,S.level,gR,{side:S.side,layers:liveLayers(),following,site:following?(igEv.site||((typeof autoSite==="function"&&autoSite(p,gsiLast))||{}).site||null):null})};
    if(D.viewboxes[S.map])draw();else loadRadar(S.map).then(draw);
    $$("[data-rlayer]",v).forEach(b=>b.onclick=()=>{const k=b.dataset.rlayer,L=liveLayers();store("rlayers6",L.includes(k)?L.filter(x=>x!==k):[...L,k]);renderIngame()});   // the key liveLayers reads
    const ra=$("[data-rlayer-auto]",v);if(ra)ra.onclick=()=>{store("rlayers6",RLAYERS.map(x=>x[0]));renderIngame()};
    const rd=$("details.rlayers",v);if(rd)rd.ontoggle=()=>{RL_OPEN=rd.open}}
  else if(m){const st={level:S.level,layers:["zones","best","nades"],nades:cols.plan?cols.plan.key_nades:[],sel:null},box=$(".radar-box",v);crossRadar(box,m,S.side,st);
    spotStars(box,((PL.spots||{})[S.map]||{})[S.side],S.level);
    const ps=plantSpots().filter(x=>!x.level||x.level===S.level);if(ps.length){const g_=$("g",box);ps.forEach(it=>{tip(el("rect",{x:it.px[0]-9,y:it.px[1]-9,width:18,height:18,rx:3,style:"fill:var(--bad);stroke:#fff;stroke-width:2"},g_),it.title);el("text",{x:it.px[0],y:it.px[1]-13,"text-anchor":"middle",class:"zlabel"},g_).textContent=it.label})}}
  if(R0&&!liveR){const items=[...cols.rifle.map(z=>({px:z.px,level:z.level,label:`${z.name} ${z.duel_win}%`,color:z.duel_win>=53?"var(--good)":z.duel_win<=47?"var(--bad)":"#8a96a3",title:`${z.name}: ${z.duel_win}% of duels won`})),
      ...cols.proAwp.map(z=>({px:z.px,level:z.level,label:`Pro AWP · ${z.name}`,color:"var(--ct)",title:"Pro AWPers' position"})),...plantSpots()].filter(x=>x.px);
    const cnt={};items.forEach(x=>{if(x.level)cnt[x.level]=(cnt[x.level]||0)+1});
    const lv=(S.blevel&&cnt[S.blevel]?S.blevel:null)||Object.keys(cnt).sort((a,b)=>cnt[b]-cnt[a])[0]||((R0.levels||[])[0]||{}).key;
    loadRadar(S.map).then(()=>{const box=$(".radar-box",v);if(!box||S.view!=="ingame")return;teamRadarDraw(box,S.map,lv,items);
      $(".caption",box).innerHTML=`<span>Positions of ${S.side}s in the base: green = duels often won, red = often lost. Blue: pro AWPers.</span>`;
      $$("[data-blevel]",box).forEach(b=>{b.setAttribute("aria-pressed",b.dataset.blevel===lv);b.onclick=()=>{S.blevel=b.dataset.blevel;renderIngame()}})})}
}
