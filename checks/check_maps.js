// Regression check of the In game page on every map of the base: the page's own code (taken from the template) runs
// the key moments of a match on both sides (pistol, round 2 eco, eco and force against a full buy, full buys, live,
// after the plant, anti-eco, warm-up brief, last round of a half) and checks what must always hold.
// Usage: node checks/check_maps.js [template.html] [steamid]      exit code 1 when a check fails
const fs = require("fs"), vm = require("vm"), path = require("path");
const ROOT = path.join(__dirname, "..");
const tpl = fs.readFileSync(process.argv[2] || path.join(ROOT, "app_template.html"), "utf8");
// the SteamID is read as text: as a JSON number, 64 bits don't fit in a JavaScript number
const settings = (() => { try { return fs.readFileSync(path.join(ROOT, "out", "settings.json"), "utf8") } catch (e) { return "" } })();
const sid = process.argv[3] || ((settings.match(/"own_steamid"\s*:\s*"?(\d+)/) || [])[1] || "");
const player = JSON.parse(fs.readFileSync(path.join(ROOT, "out", "site", "players", `${sid}.json`), "utf8"));
const js = [...tpl.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join("\n")
  .replace(/__DATA__/g, '{"index":[],"players":{},"viewboxes":{},"radars":{}}');   // the page's start-up runs on empty data

// a tiny DOM: SVG elements the radar draws into, and nothing else
class N {constructor(t){this.tag=t;this.attrs={};this.kids=[];this.text=""}
  setAttribute(k,v){this.attrs[k]=String(v)} getAttribute(k){return this.attrs[k]} appendChild(c){this.kids.push(c);return c}
  replaceChildren(){this.kids=[]} set textContent(v){this.text=String(v)} get textContent(){return this.text}
  set innerHTML(v){this.html=v} get innerHTML(){return this.html||""}
  toString(){return `<${this.tag}>${this.text}${this.kids.join("")}</${this.tag}>`}}
const stub = new Proxy(function () {}, { get: (t, k) => k === Symbol.toPrimitive ? () => "" : k === "length" ? 0 : stub, apply: () => stub, construct: () => stub });
const doc = new Proxy({ createElementNS: (ns, t) => new N(t) }, { get: (t, k) => k in t ? t[k] : stub });
const ctx = { console: { log() {}, warn() {}, error() {} }, Math, JSON, Date, Object, Array, Number, String, Set, Map, WeakMap, Promise, isFinite, parseInt, parseFloat,
  setTimeout: () => 0, clearTimeout: () => 0, setInterval: () => 0, clearInterval: () => 0, document: doc, window: stub, navigator: stub,
  location: { hash: "", search: "", pathname: "/" }, localStorage: { getItem: () => null, setItem: () => {} }, history: stub,
  fetch: () => new Promise(() => {}), requestAnimationFrame: () => 0, matchMedia: () => ({ matches: false, addEventListener() {} }), addEventListener() {}, EventSource: function () {} };
vm.createContext(ctx);
vm.runInContext(js, ctx);
ctx.__p = player;
vm.runInContext("Object.assign(D,{own:__p.steamid,players:{},local:true,radars:D.radars||{},viewboxes:D.viewboxes||{}});D.players[D.own]=__p;S.player=D.own", ctx);
const J = c => vm.runInContext(c, ctx);

const H = list => ({ rounds: Object.fromEntries(list.map(([n, w]) => [n, { win: w }])) });
const base = (map, side, extra) => Object.assign({ map, side, round_phase: "freezetime", health: 100, armor: 0, helmet: false, nades: {}, equip: 200, losses: 0, hist: { rounds: {} } }, extra);
const lost = s => s === "T" ? "CT" : "T";
const scenarios = side => [
  ["pistol", { round: side === "T" ? 1 : 13, money: 800 }],
  ["round 2 eco", { round: side === "T" ? 2 : 14, money: 1850, losses: 1, hist: H([[side === "T" ? 1 : 13, lost(side)]]) }],
  ["anti-eco", { round: side === "T" ? 2 : 14, money: 4300, hist: H([[side === "T" ? 1 : 13, side]]) }],
  ["force vs full", { round: side === "T" ? 4 : 16, money: 3500, losses: 3, hist: H([1, 2, 3].map(i => [i + (side === "T" ? 0 : 12), lost(side)])) }],
  ["eco vs full", { round: side === "T" ? 3 : 15, money: 2200, losses: 2, hist: H([1, 2].map(i => [i + (side === "T" ? 0 : 12), lost(side)])) }],
  ["full buy", { round: side === "T" ? 5 : 17, money: 6000, primary: side === "T" ? "AK-47" : "M4A1-S", armor: 100, helmet: true,
    nades: { smoke: 1, flash: 1, molotov: 1 }, hist: H([[side === "T" ? 1 : 13, lost(side)], [side === "T" ? 2 : 14, lost(side)], [side === "T" ? 3 : 15, side], [side === "T" ? 4 : 16, side]]) }],
  ["last round of the half", { round: side === "T" ? 12 : 24, money: 3000, losses: 1, hist: H([[side === "T" ? 11 : 23, lost(side)]]) }],
];
const fails = [], warns = [];
const fail = (map, what) => fails.push(`${map}: ${what}`), warn = (map, what) => warns.push(`${map}: ${what}`);
const maps = Object.keys(player.advice.plan.tside.maps || {}).filter(m => fs.existsSync(path.join(ROOT, "out", "site", "radars", `${m}.json`)));
for (const map of maps) {
  const R = JSON.parse(fs.readFileSync(path.join(ROOT, "out", "site", "radars", `${map}.json`), "utf8")), LVS = Object.keys(R.levels);
  ctx.__vb = R.viewbox; J(`D.viewboxes[${JSON.stringify(map)}]=__vb;${LVS.map(l => `D.radars[${JSON.stringify(map + ":" + l)}]=''`).join(";")}`);
  const radar = (g, lv) => {
    const svg = new N("svg"), img = new N("image"), ov = new N("g"), cap = new N("div");
    svg.kids.push(img, ov);
    ctx.__box = { querySelector: s => s === "svg" ? svg : s === ".caption" ? cap : null };
    svg.querySelector = s => s === "image" ? img : s === "g" ? ov : null;
    ctx.__g = g; ctx.__lv = lv;
    J(`liveRadar(__box,__p,__g.map,__lv,__g,{side:__g.side,layers:liveLayers(),following:true,site:((__g.bomb==="planted"&&autoSite(__p,__g))||{}).site||null})`);
    return String(svg);
  };
  const run = (label, g, fn) => { try { ctx.__g = g; return fn() } catch (e) { fail(map, `${label}: ${e.message}`); return null } };
  for (const side of ["T", "CT"]) {
    for (const [name, extra] of scenarios(side)) {
      const g = base(map, side, extra), label = `${side} ${name}`;
      run(label, g, () => { J("buyVisual(__p,__g)"); J("nowVisual(__p,__g,true)"); LVS.forEach(l => radar(g, l)) });
      const ks = run(label, g, () => J("keySit(__p,__g)"));
      const want = { pistol: "pistol", "round 2 eco": "eco_force", "force vs full": "force_full", "eco vs full": "eco_full" }[name];
      if (want && ks !== want && !(name === "force vs full" && ks === "eco_full") && !(name === "eco vs full" && ks === "force_full")) fail(map, `${label}: key round "${ks}" instead of "${want}"`);
      if (ks && ks !== "pistol") {
        const kw = run(label, g, () => J(`keyWeapons(__p,__g,${JSON.stringify(ks)})`));
        if (kw && !kw.list.length) warn(map, `${label}: no weapon to suggest`);
        if (kw && kw.list.some(w => !J(`canBuy(${JSON.stringify(side)},${JSON.stringify(w.w)})`))) fail(map, `${label}: a weapon your side can't buy is suggested`);
        const sp = run(label, g, () => J(`keySpots(__p,__g,__g.map,${JSON.stringify(ks)},W_GRP(((keyWeapons(__p,__g,${JSON.stringify(ks)}).list[0])||{}).w||""))`));
        if (sp && !sp.length) warn(map, `${label}: no key-round spot`);
      }
      if (name === "anti-eco" && !run(label, g, () => J("antiEco(__p,__g)"))) fail(map, `${label}: anti-eco not detected`);
      if (name === "last round of the half") { const pl = run(label, g, () => J("econPlan(__p,__g)")); if (pl && pl.best.k === "eco") fail(map, `${label}: saves on the last round of the half`) }
      if (name === "full buy") {
        const pl = run(label, g, () => J("econPlan(__p,__g)")); if (pl && pl.best.k !== "full") fail(map, `${label}: a rifle in hand and $6,000 but not a full buy`);
        if (side === "T") {
          const W = run(label, g, () => J("winsRank(__p,__g)"));
          if (!W || !W.rows.length) fail(map, `${label}: no path`); else if (!W.rows[0].route) warn(map, `${label}: path 1 has no drawn way`);
          const NP = run(label, g, () => J("vNadePicks(__p,__g)")) || [];
          if (NP.some(n => n.x && n.x.way === "off")) fail(map, `${label}: a grenade toward the other site`);
          if (NP.length && !NP.some(n => n.x && (n.x.way === "site" || n.x.way === "way"))) warn(map, `${label}: no grenade on path 1`);
        }
        // live, then after the plant: the site found without a click, the post-plant / retake drawn
        const live = Object.assign({}, g, { round_phase: "live", elapsed: 14 });
        run(`${label} live`, live, () => { J("nowVisual(__p,__g,true)"); LVS.forEach(l => radar(live, l)) });
        const planted = Object.assign({}, g, { round_phase: "live", elapsed: 62, bomb: "planted", since_plant: 12 });
        const as = run(`${label} planted`, planted, () => J("autoSite(__p,__g)"));
        if (!as || !["A", "B"].includes(as.site)) fail(map, `${label} planted: no site found`);
        run(`${label} planted`, planted, () => { J("nowVisual(__p,__g,true)"); LVS.forEach(l => radar(planted, l)) });
        // 10/10: where you stood when it went down (you carried it) gives its site; 7 / 9 before the plant is the bomb's site
        const SS = (((player.advice.plan.tside.maps[map] || {}).geo || {}).sites) || {};
        for (const k of ["A", "B"].filter(k => SS[k] && SS[k].c)) {
          const pg = Object.assign({}, planted, { plant_pos: SS[k].c, plant_mine: true });
          const a2 = run(`${label} planted on ${k}`, pg, () => J("autoSite(__p,__g)"));
          if (!a2 || a2.site !== k) fail(map, `${label} planted from ${k}'s middle: site ${a2 && a2.site}`);
          const mg = Object.assign({}, live, { hist: { rounds: g.hist.rounds, marks: { [g.round]: { bomb_site: k } } } });
          const ts = run(`${label} said ${k}`, mg, () => J("tdirSel(__g)"));
          if (side === "T" && (!ts || ts.dir !== k)) fail(map, `${label}: numpad ${k === "A" ? 7 : 9} before the plant not followed`);
        }
      }
    }
    const warm = base(map, side, { round: null, money: 800, map_phase: "warmup", round_phase: null });
    const brief = run(`${side} warm-up`, warm, () => J("nowVisual(__p,__g,true)"));
    if (brief != null && !/BRIEF/.test(brief)) fail(map, `${side} warm-up: no brief`);
  }
  const M = player.advice.plan.tside.maps[map] || {};
  if ((M.n_rounds || 0) < 300) warn(map, `${M.n_rounds} T rounds only: thin data`);
}
console.log(`${maps.length} maps checked: ${fails.length} failure${fails.length === 1 ? "" : "s"}, ${warns.length} warning${warns.length === 1 ? "" : "s"}`);
fails.forEach(f => console.log("  FAIL", f));
warns.forEach(w => console.log("  warn", w));
process.exit(fails.length ? 1 : 0);
