
// ---------- navigation: two main moments (during the game, cold review) ----------
const GROUP={ingame:"ingame",review:"review",matches:"review",maps:"review",midround:"review",progress:"review",analysis:"review",routine:"review",team:"team",players:"players",pros:"players",settings:"settings"};
const SUB={review:[["review","Summary"],["matches","Matches"],["maps","Maps"],["midround","Mid-round"],["progress","Progress"],["analysis","Full analysis"],["routine","Routine"]],players:[["players","Players"],["pros","Pros"]]};
const PLAYER_VIEWS=["ingame","review","matches","maps","midround","progress","analysis","routine"];
// old French addresses keep working
const ALIAS={partie:"ingame",avant:"ingame",bilan:"review",matchs:"matches",cartes:"maps",mid:"midround",prog:"progress",synthese:"analysis",equipe:"team",joueurs:"players",steam:"settings"};
function navUpdate(view){const g=GROUP[view]||view;
  $$("nav a, .gear").forEach(a=>{if(a.dataset.view===g)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current")});
  const sn=$("#subnav"),items=SUB[g];sn.hidden=!items;
  if(items)sn.innerHTML=items.map(([k,t])=>`<a href="#${k}" ${k===view?'aria-current="page"':""}>${t}</a>`).join("");
  const w=$("#whochip"),p=S.player&&D.players[S.player];
  w.innerHTML=p&&PLAYER_VIEWS.includes(view)?`Profile: <b>${esc(p.name)}</b>${D.own&&S.player!==D.own&&IDX()[D.own]?` <button type="button" id="backme">Back to my profile</button>`:""}`:"";
  const bm=$("#backme");if(bm)bm.onclick=()=>setPlayer(D.own);
  document.body.classList.toggle("ingame",view==="ingame")}
function welcome(v){const own=D.own;
  v.innerHTML=`<div class="welcome"><h2>Welcome to CS2 Coach</h2>
   <p class="lede">The coach analyzes your CS2 matches and gives you two things:</p>
   <ul style="font-size:15px"><li><b>In game</b>: a sheet to keep on a 2nd screen that follows your match (what to buy, where the Ts are likely to go, your strengths on the map, what to avoid, your reflexes, your rotations).</li>
     <li><b>Review</b>: after your session or the next day, what changed, why, what you're testing and what you could test.</li></ul>
   ${D.local&&own?`<p><button type="button" class="primary" id="w-own">Analyze this PC's Steam account</button></p>`:""}
   <form class="search" id="w-form" autocomplete="off"><input id="w-q" type="search" placeholder="Your Steam profile link or SteamID64" aria-label="Your Steam profile link"><button type="submit">Analyze</button></form>
   <p class="note">${D.local?"The analysis runs on this PC (Steam open, CS2 closed to fetch your latest matches): a first preview in seconds, the full profile in a few minutes.":"The analysis runs in the local app: double-click Coach CS2.bat."} You can also look at any player in <a href="#players" style="color:var(--ct)">Explore</a>.</p></div>`;
  const wo=$("#w-own",v);if(wo)wo.onclick=()=>{partialShown=null;startAnalysis(own)};
  $("#w-form",v).onsubmit=e=>{e.preventDefault();const q=$("#w-q",v).value.trim();if(!q)return;$("#q").value=q;$("#search").requestSubmit()}}
