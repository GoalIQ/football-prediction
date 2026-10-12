// Jakokorttien esikatselu (12.10.2026): poistaa TS-tyypit kolmesta
// korttimoduulista -> selaimessa ajettavat ES-moduulit, ei riippuvuuksia
// (Node >= 22.13: node:module stripTypeScriptTypes).
// Kaytto: node build.mjs && <fp .venv python> run.py <out-dir>
import { stripTypeScriptTypes } from 'node:module';
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
const SRC = new URL('../../src/lib/', import.meta.url);
const OUT = new URL('./out/', import.meta.url);
mkdirSync(OUT, { recursive: true });
mkdirSync(new URL('./brand/', import.meta.url), { recursive: true });
copyFileSync(new URL('../../static/brand/goaliq-wordmark-teletext.png', import.meta.url),
  new URL('./brand/goaliq-wordmark-teletext.png', import.meta.url));
for (const n of ['shareCard', 'teamColors', 'teamKits']) {
  let js = stripTypeScriptTypes(readFileSync(new URL(n + '.ts', SRC), 'utf8'), { mode: 'transform' });
  js = js.replace(/from '\.\/(\w+)'/g, "from './$1.js'");
  writeFileSync(new URL(n + '.js', OUT), js);
}
console.log('built');
