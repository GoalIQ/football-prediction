// Ajaa fpl/stats.html:n taulukon RENDER-logiikan (paint()/draw()) oikeasti,
// ei greppaa lahdetta. Ks. muisti `portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa`.
//
// TAUSTA (8.9.2026, jono STATS-LEFT-MERKINTA): status `u` (pelaaja ei enaa
// Valioliigan seurassa) ei tuottanut mitaan merkkia taulukon riville, vaikka
// sarake on datassa (build_fpl_stats.py:n `status`). Rivi olisi nayttanyt
// aktiiviselta.
//
// Kaytto: node stats_table_harness.js <stats.html> <payload.json>
// Tulostaa JSON:in { tbodyHTML, countText }.
const fs = require('fs');

const html = fs.readFileSync(process.argv[2], 'utf8');
const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

// Poimi SE script-lohko jossa rows()/draw() on. Jos poiminta epaonnistuu,
// kaadutaan - hiljainen tyhja ajo olisi fail-open (muisti:
// `kontrolli-lapaisi-tyhjana`).
const blocks = [...html.matchAll(/<script>\r?\n([\s\S]*?)<\/script>/g)].map(m => m[1]);
const src = blocks.find(b => b.includes('function rows(){'));
if (!src) {
  console.error('rows()-lohkoa ei loytynyt stats.html:sta');
  process.exit(2);
}

const elements = {};
function makeEl() {
  return {
    _innerHTML: '',
    get innerHTML() { return this._innerHTML; },
    set innerHTML(v) { this._innerHTML = v; },
    textContent: '',
    value: '',
    style: {},
    onclick: null, onchange: null, oninput: null,
    getAttribute() { return null; },
    setAttribute() {},
    querySelectorAll() { return []; },
    appendChild() {}, removeChild() {},
    closest() { return null; },
  };
}
function getElementById(id) {
  if (!elements[id]) elements[id] = makeEl();
  return elements[id];
}
global.document = {
  getElementById,
  createElement: () => makeEl(),
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener() {},
  body: makeEl(),
  documentElement: makeEl(),
};
global.window = { __ST__: payload, addEventListener() {}, devicePixelRatio: 1 };
global.location = { hostname: 'goaliq.app', search: '' };
global.fetch = () => new Promise(() => {});
global.URLSearchParams = URLSearchParams;
global.navigator = { userAgent: 'node' };
global.Blob = function Blob() {};
global.URL = { createObjectURL: () => '', revokeObjectURL: () => {} };
global.setTimeout = () => {};

try {
  // eslint-disable-next-line no-eval
  eval(src);
} catch (e) {
  console.error('harness eval kaatui: ' + ((e && e.stack) || e));
  process.exit(2);
}

console.log(JSON.stringify({
  tbodyHTML: getElementById('stb').innerHTML,
  countText: getElementById('stc').textContent,
}));
