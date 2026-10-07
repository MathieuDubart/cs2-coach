// ---------- how it went: after a warm-up, after a match with the In game page (07/10, the closed alpha) ----------
// The user: "pour encourager les feedback, à chaque fin d'entraînement et à chaque fin de session live avec Wily, une
// popup de feedback en expliquant que c'est une alpha fermée". The app says what to ask (/api/feedback/pending: once
// each, never during a match); a face, a few tags, a sentence if you like; "Not now" and Escape count as an answer.
const FB_TAGS={training:["Aim","Prefire","Defense","Stuff","Situations","Bots","Lines & zones","Connection","Too long","Too short"],
  live:["Calls","Radar","Economy","Reminders","Numpad keys","Too much on screen","Missed something","Too slow","Useful"]};
const FB_FACES=[["😖","Bad"],["😕","Meh"],["😐","OK"],["🙂","Good"],["🤩","Great"]];
let FB=null,fbTimer=null;
function openFeedback(p){const d=$("#fbdlg");if(!d||d.open||!p||!p.id)return;FB={...p,rating:0,tags:new Set()};
  $("#fb-h").textContent=p.title||"How was it?";$("#fb-sum").textContent=p.summary||"";
  $("#fb-rate").innerHTML=FB_FACES.map(([f,t],i)=>`<button type="button" data-fbr="${i+1}" aria-pressed="false" aria-label="${t}" title="${t}">${f}</button>`).join("");
  $("#fb-tags").innerHTML=(FB_TAGS[p.kind]||[]).map(t=>`<button type="button" class="chip" data-fbt="${esc(t)}" aria-pressed="false">${esc(t)}</button>`).join("");
  $("#fb-text").value="";$("#fb-msg").textContent="";$("#fb-stop").checked=false;$("#fb-send").disabled=false;
  $("#fb-hint").hidden=p.kind!=="training";
  $$("[data-fbr]",d).forEach(b=>b.onclick=()=>{FB.rating=+b.dataset.fbr;$$("[data-fbr]",d).forEach(x=>x.setAttribute("aria-pressed",String(x===b)))});
  $$("[data-fbt]",d).forEach(b=>b.onclick=()=>{const t=b.dataset.fbt,on=!FB.tags.has(t);on?FB.tags.add(t):FB.tags.delete(t);b.setAttribute("aria-pressed",String(on))});
  if(typeof d.showModal==="function")d.showModal();else d.setAttribute("open","")}
async function fbDismiss(){const d=$("#fbdlg");if(!FB)return;const id=FB.id,stop=$("#fb-stop").checked;FB=null;if(d&&d.open)d.close();
  try{await api("/api/feedback/dismiss",{id,stop})}catch(e){}}
function wireFeedback(){const d=$("#fbdlg");if(!d||d.dataset.wired)return;d.dataset.wired="1";
  $("#fb-later").onclick=fbDismiss;
  d.addEventListener("cancel",e=>{e.preventDefault();fbDismiss()});   // Escape: not now
  $("#fb-send").onclick=async()=>{if(!FB)return;const m=$("#fb-msg"),t=$("#fb-text").value.trim();
    if(!FB.rating&&!FB.tags.size&&!t){m.textContent="A face, a tag or a few words first.";return}
    const b=$("#fb-send");b.disabled=true;m.textContent="Sending…";
    try{const r=await api("/api/feedback/send",{kind:FB.kind,id:FB.id,rating:FB.rating||null,tags:[...FB.tags],text:t,summary:FB.summary||""});
      if($("#fb-stop").checked)try{await api("/api/app/options",{feedback_prompts:false})}catch(e){}
      m.textContent=r.ok?"Thank you: it goes straight to the author.":"The site can't be reached right now: kept on this PC, sent as soon as it can.";
      FB=null;setTimeout(()=>{if(d.open)d.close()},1800)}
    catch(e){m.textContent=e.message;b.disabled=false}}}
// asked every 20 s while the page is in front of you (the app decides when: a warm-up just over, a match just over)
async function fbPoll(){clearTimeout(fbTimer);fbTimer=setTimeout(fbPoll,20000);
  if(!D.local||document.visibilityState!=="visible"||FB)return;
  try{const p=await (await fetch("/api/feedback/pending")).json();if(p&&p.id)openFeedback(p)}catch(e){}}
