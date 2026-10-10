// anonymous usage counters (05/10, the alpha): which views players open and how long (only while the page is seen),
// which buttons they use (a key made of the view and the element's id or data attribute, never a text nor an id
// number), the page's errors, the time Live runs during a match. Sent to the local server every minute and when the
// page closes; it adds them up per day and sends a finished day, anonymous, to the coach's site (usage.py).
const USE={view:null,views:{},actions:{},errors:0,live:0,seenErrs:0};
const useOn=()=>D.local&&D.role==="client"&&!!(D.usage&&D.usage.on);
function usageView(v){if(!useOn()||!v)return;if(v!==USE.view){USE.view=v;const x=USE.views[v]||(USE.views[v]={visits:0,seconds:0});x.visits++}}
function usageKey(el){
  let k=el.id&&!/\d{5,}/.test(el.id)?"#"+el.id:"";
  if(!k)for(const a of el.attributes){if(!a.name.startsWith("data-"))continue;const val=a.value;
    k=`[${a.name.slice(5)}${/^[a-z0-9_-]{1,24}$/i.test(val)&&!/\d{5,}/.test(val)?"="+val:""}]`;break}
  if(!k&&el.tagName==="A"){const h=el.getAttribute("href")||"";k=/^https?:/i.test(h)?"a:external":"a:"+h.replace(/\d{5,}/g,"#").replace(/[^A-Za-z0-9_.:#=\/-]/g,"").slice(0,30)}
  if(!k)k=el.tagName.toLowerCase()+(typeof el.className==="string"&&el.className?"."+el.className.split(/\s+/)[0]:"");
  return `${USE.view||"?"}:${k}`.replace(/[^A-Za-z0-9_.:#=\[\]\/-]/g,"").slice(0,80)}
document.addEventListener("click",e=>{if(!useOn())return;const el=e.target.closest("button,a,summary,[role=button],input[type=checkbox],input[type=radio],select");
  if(!el||el.closest("#bugdlg"))return;const k=usageKey(el);USE.actions[k]=(USE.actions[k]||0)+1},true);
setInterval(()=>{if(!useOn()||document.visibilityState!=="visible"||!USE.view)return;
  USE.views[USE.view].seconds+=5;
  if(USE.view==="ingame"&&typeof gsiFresh==="function"&&gsiFresh())USE.live+=5;
  if(typeof ERRS!=="undefined"&&ERRS.length!==USE.seenErrs){USE.errors+=Math.max(0,ERRS.length-USE.seenErrs);USE.seenErrs=ERRS.length}},5000);
function usageScreen(){const w=window.innerWidth;return w<700?"phone":w<1100?"tablet":w<1500?"laptop":w<2200?"desktop":"wide"}
function usageFlush(beacon){if(!useOn())return;
  const views={};for(const [k,v] of Object.entries(USE.views))if(v.visits||v.seconds)views[k]={visits:v.visits,seconds:v.seconds};
  if(!Object.keys(views).length&&!Object.keys(USE.actions).length&&!USE.errors&&!USE.live)return;
  const body=JSON.stringify({views,actions:USE.actions,errors:USE.errors,live:USE.live,screen:usageScreen()});
  for(const v of Object.values(USE.views)){v.visits=0;v.seconds=0}USE.actions={};USE.errors=0;USE.live=0;
  try{if(beacon&&navigator.sendBeacon)navigator.sendBeacon("/api/usage",new Blob([body],{type:"application/json"}));
    else fetch("/api/usage",{method:"POST",headers:{"Content-Type":"application/json"},body,keepalive:true}).catch(()=>{})}catch(e){}}
setInterval(()=>usageFlush(false),60000);
addEventListener("pagehide",()=>usageFlush(true));
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="hidden")usageFlush(true)});
// the first time: what is counted, and the switch (Settings has it too)
// (10/10: the anonymized matches too, on by default on a player's copy; "Turn both off" stops both)
function usageNotice(){const n=$("#usage-note");if(!n||!D.local||D.role!=="client"||!D.usage||D.usage.noticed)return;
  n.hidden=false;
  const done=async on=>{n.hidden=true;try{const r=await api("/api/usage/set",{noticed:true,...(on===false?{on:false}:{})});D.usage={on:r.on,noticed:true};
    if(on===false)await api("/api/contrib/set",{on:false})}catch(e){}};
  $("#un-ok",n).onclick=()=>done();$("#un-off",n).onclick=()=>done(false);$("#un-more",n).onclick=()=>{done();go("settings")}}
