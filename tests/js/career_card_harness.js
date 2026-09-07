// Ajaa career.html:n KORTTIPIIRTOA oikeasti, ei greppaa lahdetta.
//
// TAUSTA (7.9.2026, portin 17. kierros). Korttihaarat olivat vartioimatta
// merkkijonotesteilla, ja neljä mutaatiota selvisi 3 200 testista. Kortti on
// tuotteen JULKISIN pinta - kuva irtoaa sovelluksesta - joten sen haarat on
// mitattava ajamalla, kuten backendin luvut. Ks. muisti
// `portti-joka-etsii-merkkijonoa-ei-mittaa-arvoa`.
//
// Kaytto: node career_card_harness.js <career.html> <payload.json>
// Tulostaa JSON:in { blocks: [{label, value}], text: [...] }.
const fs = require('fs');

const html = fs.readFileSync(process.argv[2], 'utf8');
const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));

// Poimi SE script-lohko jossa drawCard on. Jos poiminta epaonnistuu,
// kaadutaan - hiljainen tyhja ajo olisi fail-open (muisti:
// `kontrolli-lapaisi-tyhjana`).
const blocks = [...html.matchAll(/<script>\r?\n([\s\S]*?)<\/script>/g)].map(m => m[1]);
const src = blocks.find(b => b.includes('function drawCard('));
if (!src) { console.error('drawCard-lohkoa ei loytynyt career.html:sta'); process.exit(2); }

const calls = [], texts = [];
// 🔴 Portin 21. kierros: `measureText` oli VAKIO (length * 12) fonttikoosta
// riippumatta, joten `fitText` ei tehnyt harnessissa mitaan - portti "mittasi"
// mekanismia jota se ei ajanut. Leveys lasketaan nyt asetetusta fontista:
// IBM Plex Mono, advance ~0.6 em.
let fontPx = 26;
const ctx = new Proxy({}, {
  get: (_t, k) => {
    if (k === 'font') return `${fontPx}px mono`;
    if (k === 'measureText') return (s) => ({ width: String(s).length * fontPx * 0.6 });
    if (k === 'fillText') return (s) => { texts.push(String(s)); };
    if (k === 'createLinearGradient') return () => ({ addColorStop() {} });
    return () => {};
  },
  set: (_t, k, v) => {
    if (k === 'font') {
      const m = /(\d+(?:\.\d+)?)px/.exec(String(v));
      if (m) fontPx = parseFloat(m[1]);
    }
    return true;
  },
});
const el = new Proxy({ style: {}, classList: { add() {}, remove() {} } }, {
  get: (t, k) => (k in t ? t[k] : (k === 'getContext' ? () => ctx : () => {})),
  set: (t, k, v) => { t[k] = v; return true; },
});
global.document = { getElementById: () => el, createElement: () => el,
  querySelector: () => el, querySelectorAll: () => [], addEventListener() {},
  body: el, documentElement: el };
global.window = { addEventListener() {}, devicePixelRatio: 1 };
global.location = { hostname: 'goaliq.app', search: '' };
global.fetch = () => new Promise(() => {});
global.URLSearchParams = URLSearchParams;
global.navigator = { userAgent: 'node' };

// Vie drawCard ulos IIFE:sta ja kaari statBlock niin etta naemme mita
// kortille TODELLA kirjoitetaan.
let js = src.replace(/\}\)\(\);\s*$/, `
  var __orig = statBlock;
  statBlock = function (x, y, label, value, vs, mw) {
    __CALLS.push({ label: String(label), value: String(value) });
    return __orig(x, y, label, value, vs, mw);
  };
  __EXPORT.drawCard = drawCard;
})();
`);
if (js === src) { console.error('IIFE:n loppua ei tunnistettu'); process.exit(2); }

// Kortti raportoi labelin VALITUN koon, jotta testi voi mitata piirretyn
// leveyden eika luottaa siihen etta fittaus riittaa.
const labelFits = [];
global.__LABEL_FIT = (text, size, maxW) => {
  labelFits.push({ text, size, maxW, width: text.length * size * 0.6 });
};
global.__CALLS = calls;
global.__EXPORT = {};
new Function(js)();
if (typeof global.__EXPORT.drawCard !== 'function') {
  console.error('drawCard ei paatynyt exportiin'); process.exit(2);
}
global.__EXPORT.drawCard(payload);
console.log(JSON.stringify({ blocks: calls, text: texts, labelFits }));
