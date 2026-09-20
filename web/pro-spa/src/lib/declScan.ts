/**
 * SIJOITUSTEN RIVIVALIT lahdeporteille (17.9.2026, XP-HORIZON-ALKANUT-KIERROS).
 *
 * MIKSI TAMA ON OMA TIEDOSTO: `sourceScan.ts` vastaa kysymykseen "mika rivi
 * osuu", tama kysymykseen "mika NIMI tuottaa tuon rivin tekstin". Portti joka
 * osaa vain rivin ei voi erottaa kahta vierekkaista vaitetta toisistaan:
 * XpTablen `colsLabel` (mita taulukko NAYTTAA) ja `horizonLabel` (mita summa
 * KATTAA) ovat molemmat "GW4-GW9"-muotoisia, mutta vain toinen saa tulla
 * sarakkeista. Kun portti tuntee rivivalin, sallittu poikkeus voidaan sitoa
 * NIMEEN eika muotoon - muuten sama muoto toisessa nimessa lipuu lapi
 * (muisti: portti-kirjoitetaan-nahdylle-muodolle).
 *
 * Fail-closed: tunnistamaton muoto ei ole sijoitus, joten sen rivit jaavat
 * sijoituksettomiksi ja portti arvioi ne suoraan. Portti voi olla liian
 * tiukka, ei koskaan liian loysa.
 */
import { blankComments } from './sourceScan';

/** Sijoitus: nimi + lausekkeen rivivali + lauseke kommentitta. */
export interface Decl {
	name: string;
	/** 1-pohjainen rivi jolla sijoitus alkaa. */
	from: number;
	/** 1-pohjainen rivi jolla lauseke paattyy (`from` yksirivisella). */
	to: number;
	/** Sijoitettu lauseke, kommentit pyyhittyina. */
	rhs: string;
}

const IDENT = '[A-Za-z_$][\\w$]*';

/** Ohita merkkijono/template alkaen `i`:sta (`src[i]` on lainausmerkki).
 *  Palauttaa indeksin sulkevan merkin jalkeen. Template-lausekkeita
 *  (dollari-aaltosulku) ei ohiteta erikseen: portin kannalta ne ovat osa
 *  lauseketta, ja sulkulaskenta jatkuu kun template sulkeutuu. */
function skipQuoted(src: string, i: number): number {
	const q = src[i];
	let j = i + 1;
	while (j < src.length) {
		if (src[j] === '\\') {
			j += 2;
			continue;
		}
		if (src[j] === q) return j + 1;
		if (q !== '`' && src[j] === '\n') return j;
		j += 1;
	}
	return j;
}

/** Sulkevan parin indeksi: `src[i]` on avaava `(`/`[`/`{`, palautus on sen
 *  parin sulkevan merkin indeksi (tai viimeinen indeksi jos pari ei sulkeudu).
 *  Merkkijonot ohitetaan. */
function matchDelims(src: string, i: number): number {
	let depth = 0;
	let j = i;
	while (j < src.length) {
		const c = src[j];
		if (c === '"' || c === "'" || c === '`') {
			j = skipQuoted(src, j);
			continue;
		}
		if (c === '(' || c === '[' || c === '{') depth += 1;
		else if (c === ')' || c === ']' || c === '}') {
			depth -= 1;
			if (depth === 0) return j;
		}
		j += 1;
	}
	return src.length - 1;
}

/** Rivinumero (1-pohjainen) jokaiselle indeksille. */
function lineIndex(code: string): number[] {
	const out: number[] = new Array(code.length + 1);
	let line = 1;
	for (let i = 0; i < code.length; i += 1) {
		out[i] = line;
		if (code[i] === '\n') line += 1;
	}
	out[code.length] = line;
	return out;
}

/**
 * Kaikki sijoitukset: `let`/`const`/`var`, Svelten aaltosulku-const, paljas
 * `nimi = ...` rivin alussa, ja `function nimi(...)`. Lausekkeen loppu
 * etsitaan sulkusyvyytta laskien ja merkkijonot ohittaen, joten `;` tai
 * rivinvaihto lausekkeen SISALLA ei katkaise sita: monirivinen `$derived(...)`
 * on yksi vaite.
 */
export function declarations(src: string): Decl[] {
	const code = blankComments(src);
	const lineOf = lineIndex(code);
	const starts: { name: string; eq: number; inBrace: boolean; fn?: boolean }[] = [];
	const add = (name: string, eq: number, inBrace: boolean, fn = false) =>
		starts.push({ name, eq, inBrace, fn });

	for (const m of code.matchAll(
		new RegExp(`\\b(?:let|const|var)\\s+(${IDENT})\\s*(?::[^=;\\n]*)?=(?!=)`, 'g')
	))
		add(m[1], m.index + m[0].length - 1, false);
	for (const m of code.matchAll(new RegExp(`\\{@const\\s+(${IDENT})\\s*=(?!=)`, 'g')))
		add(m[1], m.index + m[0].length - 1, true);
	for (const m of code.matchAll(
		new RegExp(`(?:^|[;\\n])[ \\t]*(${IDENT})\\s*=(?!=)`, 'gm')
	))
		add(m[1], m.index + m[0].length - 1, false);
	for (const m of code.matchAll(new RegExp(`\\bfunction\\s+(${IDENT})\\s*\\(`, 'g')))
		add(m[1], m.index + m[0].length - 1, false, true);

	const out: Decl[] = [];
	for (const { name, eq, inBrace, fn } of starts) {
		/* Funktiomaarittelyn rhs on parametrit JA RUNKO. Ilman runkoa apuri
		   joka rakentaa otsikon rivilistasta jaisi porteilta nakymatta:
		   `function winLabel(h) { return gwCols.length ? ... : h.label; }`
		   nayttaisi puhtaalta, ja kutsupaikka perisi siita vain lukijanimen. */
		if (fn) {
			let b = matchDelims(code, eq) + 1;
			while (b < code.length && code[b] !== '{' && code[b] !== ';') b += 1;
			const end = code[b] === '{' ? matchDelims(code, b) : b;
			out.push({
				name,
				from: lineOf[Math.min(eq, code.length)],
				to: lineOf[Math.min(end, code.length)],
				rhs: code.slice(eq, Math.min(end + 1, code.length))
			});
			continue;
		}
		let depth = 0;
		let i = eq + 1;
		let end = code.length;
		while (i < code.length) {
			const c = code[i];
			if (c === '"' || c === "'" || c === '`') {
				i = skipQuoted(code, i);
				continue;
			}
			if (c === '(' || c === '[' || c === '{') {
				depth += 1;
				i += 1;
				continue;
			}
			if (c === ')' || c === ']' || c === '}') {
				if (depth === 0) {
					end = i;
					break;
				}
				depth -= 1;
				i += 1;
				if (inBrace && depth === 0) {
					end = i;
					break;
				}
				continue;
			}
			if (depth === 0 && (c === ';' || c === '\n' || c === ',')) {
				end = i;
				break;
			}
			i += 1;
		}
		out.push({
			name,
			from: lineOf[Math.min(eq, code.length)],
			to: lineOf[Math.min(end, code.length)],
			rhs: code.slice(eq + 1, end)
		});
	}
	return out;
}

/** Sijoitukset jotka kattavat rivin `n` (sisakkaiset mukana, ulommasta
 *  sisimpaan). Tyhja = rivi ei ole minkaan tunnistetun sijoituksen sisalla. */
export function declsAtLine(decls: Decl[], n: number): Decl[] {
	return decls.filter((d) => d.from <= n && n <= d.to);
}
