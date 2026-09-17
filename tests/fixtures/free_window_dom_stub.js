'use strict';
// Minimal DOM stub for running src.free_window.INLINE_SCRIPT_TMPL under Node.
//
// Why a stub and not jsdom: the repo has no jsdom (0 EUR, no new deps for a
// Python test). The stub implements exactly the DOM surface the inline script
// touches: querySelector on template[attr="v"], template.content, importNode,
// parentNode/nextSibling/removeChild/insertBefore (with DocumentFragment
// move semantics), getAttribute. Date.now and setTimeout are faked so the
// test can drive the clock past the deadline and fire the revert timer.
//
// Usage: node free_window_dom_stub.js '<json config>'
//   config = { script, key, until, untilMs, nowMs, openMarker, closedMarker }
// Prints JSON: { afterLoad, timers, atDeadline }
//   afterLoad  = visible text right after the inline script ran
//   timers     = delays (ms) the script scheduled
//   atDeadline = visible text after the clock is set to `untilMs` and every
//                scheduled timer has fired

const cfg = JSON.parse(process.argv[2]);

class N {
  constructor(tag, attrs, text) {
    this.tag = tag; this.attrs = attrs || {}; this.text = text || '';
    this.childNodes = []; this.parentNode = null;
  }
  getAttribute(k) {
    return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null;
  }
  get nextSibling() {
    if (!this.parentNode) return null;
    const s = this.parentNode.childNodes; const i = s.indexOf(this);
    return (i >= 0 && i + 1 < s.length) ? s[i + 1] : null;
  }
  appendChild(c) {
    if (c.parentNode) c.parentNode.removeChild(c);
    this.childNodes.push(c); c.parentNode = this; return c;
  }
  removeChild(c) {
    const i = this.childNodes.indexOf(c);
    if (i < 0) throw new Error('removeChild: not a child');
    this.childNodes.splice(i, 1); c.parentNode = null; return c;
  }
  insertBefore(n, ref) {
    const nodes = n.isFragment ? n.childNodes.slice() : [n];
    for (const x of nodes) if (x.parentNode) x.parentNode.removeChild(x);
    if (n.isFragment) n.childNodes = [];
    let i = ref ? this.childNodes.indexOf(ref) : this.childNodes.length;
    if (ref && i < 0) throw new Error('insertBefore: ref not a child');
    for (const x of nodes) { this.childNodes.splice(i++, 0, x); x.parentNode = this; }
    return n;
  }
  clone() {
    const c = new N(this.tag, Object.assign({}, this.attrs), this.text);
    for (const k of this.childNodes) c.appendChild(k.clone());
    return c;
  }
  // Text a reader would see: <template> content is inert and never shown.
  textAll() {
    if (this.tag === 'template') return '';
    return this.text + this.childNodes.map(k => k.textAll()).join('');
  }
}
class Frag extends N { constructor() { super('#fragment'); this.isFragment = true; } }

// Mirror of the rendered block: open template, whitespace, closed nodes,
// whitespace, end template. The script lives after the end template.
const body = new N('body');
const openT = new N('template', { 'data-free-window-open': cfg.key, 'data-until': cfg.until });
openT.content = new Frag();
openT.content.appendChild(new N('div', {}, cfg.openMarker));
const closed = new N('a', {}, cfg.closedMarker);
const endT = new N('template', { 'data-free-window-end': cfg.key });
body.appendChild(openT);
body.appendChild(new N('#text', {}, '\n'));
body.appendChild(closed);
body.appendChild(new N('#text', {}, '\n'));
body.appendChild(endT);

function matchSel(sel) {
  const m = /^template\[([\w-]+)="([^"]*)"\]$/.exec(sel);
  if (!m) throw new Error('unsupported selector ' + sel);
  return n => n.tag === 'template' && n.getAttribute(m[1]) === m[2];
}
function walk(n, f, out) { if (f(n)) out.push(n); for (const k of n.childNodes) walk(k, f, out); return out; }
const document = {
  querySelector(sel) { return walk(body, matchSel(sel), [])[0] || null; },
  querySelectorAll(sel) { return walk(body, matchSel(sel), []); },
  importNode(frag, _deep) { const f = new Frag(); for (const k of frag.childNodes) f.appendChild(k.clone()); return f; },
};

let now = cfg.nowMs;
const timers = [];
const FakeDate = { parse: Date.parse, now: () => now };
function fakeSetTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; }

// Run the inline script with our globals shadowing the real ones.
new Function('document', 'Date', 'setTimeout', cfg.script)(document, FakeDate, fakeSetTimeout);

const out = { afterLoad: body.textAll(), timers: timers.map(t => t.ms) };
now = cfg.untilMs;            // exactly the deadline: window is closed
// Bounded drain. The clock is frozen at the deadline, so a script whose
// predicate is still true there (e.g. the `<=` mutant) re-arms a 0 ms
// timer forever. In a browser the millisecond would tick over; here it
// never does, and an unbounded loop hung the mutation test at 60 s
// (measured 17.9). 64 firings is far more than the correct script needs
// (exactly one), and `timersAfter > 0` exposes a script that never settles.
let fired = 0;
while (timers.length && fired < 64) { const t = timers.shift(); t.fn(); fired++; }
out.atDeadline = body.textAll();
out.timersAfter = timers.length;
out.fired = fired;
console.log(JSON.stringify(out));
