/**
 * Lahdekoodin skannausapurit lahdeporteille (17.9.2026).
 *
 * Portti joka lukee lahdetiedostoa ei saa osua kommenttiin: juuri
 * kommenteissa selitetaan miksi vanha muoto poistettiin, ja 29.8 merkkijono-
 * portti osui omaan perustelukommenttiinsa (cc-report 12.9, luku 9).
 * `blankComments` korvaa kommentit valilyonneilla ja SAILYTTAA rivinvaihdot,
 * joten rivinumerot pysyvat ja osuma voidaan nimeta tiedosto:rivi.
 *
 * Suunta on fail-closed: merkkijonoliteraalit kopioidaan sellaisenaan (niita
 * ei koskaan piiloteta), ja jos jokin kommentti jaa tunnistamatta, sen teksti
 * SKANNATAAN eli portti voi olla liian tiukka, ei koskaan liian loysa.
 */

/** Korvaa rivi-, lohko- ja HTML-kommentit valilyonneilla rivinvaihdot
 *  sailyttaen. Merkkijonot (' " `) ohitetaan, jotta 'https://x' ei ala
 *  kommenttia. Yksinkertainen lainausmerkki, joka ei sulkeudu rivilla
 *  (apostrofi markupissa: "it's"), katkeaa rivinvaihtoon. */
export function blankComments(src: string): string {
	let out = '';
	let i = 0;
	const n = src.length;
	const keepNewlines = (s: string) => s.replace(/[^\n]/g, ' ');
	while (i < n) {
		const c = src[i];
		const c2 = src[i + 1];
		if (c === '"' || c === "'" || c === '`') {
			let j = i + 1;
			while (j < n) {
				if (src[j] === '\\') {
					j += 2;
					continue;
				}
				if (src[j] === c) {
					j += 1;
					break;
				}
				if (c !== '`' && src[j] === '\n') break;
				j += 1;
			}
			out += src.slice(i, j);
			i = j;
			continue;
		}
		if (c === '/' && c2 === '/') {
			let j = src.indexOf('\n', i);
			if (j === -1) j = n;
			out += ' '.repeat(j - i);
			i = j;
			continue;
		}
		if (c === '/' && c2 === '*') {
			let j = src.indexOf('*/', i + 2);
			j = j === -1 ? n : j + 2;
			out += keepNewlines(src.slice(i, j));
			i = j;
			continue;
		}
		if (src.startsWith('<!--', i)) {
			let j = src.indexOf('-->', i + 4);
			j = j === -1 ? n : j + 3;
			out += keepNewlines(src.slice(i, j));
			i = j;
			continue;
		}
		out += c;
		i += 1;
	}
	return out;
}

export interface CodeLine {
	/** 1-pohjainen rivinumero alkuperaisessa tiedostossa. */
	n: number;
	text: string;
}

/** Koodirivit ilman kommentteja; tyhjat rivit pudotetaan. */
export function codeLines(src: string): CodeLine[] {
	return blankComments(src)
		.split('\n')
		.map((text, i) => ({ n: i + 1, text }))
		.filter((l) => l.text.trim().length > 0);
}

/** Rivit joilla `pattern` osuu koodiin (ei kommentteihin). */
export function findInCode(src: string, pattern: RegExp): CodeLine[] {
	const re = new RegExp(pattern.source, pattern.flags.replace('g', ''));
	return codeLines(src).filter((l) => re.test(l.text));
}

/** Yksi mustache-lauseke rivilta. */
export interface Interp {
	/** Lausekkeen teksti aaltosulkujen sisalta. */
	text: string;
	/** true = Svelten lohkotagi (`{#if}`, `{:else}`, `{/if}`, `{@const}`).
	 *  Ne eivat renderoi tekstia, joten julkisen VAITTEEN tarkistus ohittaa
	 *  ne; sijoitukset (`{@const}`) tarkistetaan sijoituksena (declScan). */
	block: boolean;
}

/**
 * Rivin mustache-lausekkeet: markupin `{...}` ja template-literaalin
 * `${...}`. Sulkulaskenta ohittaa merkkijonot, joten `{p.n.toFixed(1)}` ja
 * `{a ? '}' : b}` eivat katkea vaaraan paikkaan.
 *
 * Fail-closed: rivilla alkava mutta sulkeutumaton lauseke palautetaan rivin
 * loppuun asti. Se voi antaa liikaa tekstia (portti liian tiukka), ei koskaan
 * liian vahan: kutsupaikan tunnisteet tulevat silti tarkistetuiksi.
 */
export function interpolations(line: string): Interp[] {
	const out: Interp[] = [];
	let i = 0;
	while (i < line.length) {
		if (line[i] !== '{') {
			i += 1;
			continue;
		}
		let depth = 0;
		let j = i;
		let end = -1;
		while (j < line.length) {
			const c = line[j];
			if (c === '"' || c === "'" || c === '`') {
				const q = c;
				j += 1;
				while (j < line.length) {
					if (line[j] === '\\') {
						j += 2;
						continue;
					}
					if (line[j] === q) break;
					j += 1;
				}
				j += 1;
				continue;
			}
			if (c === '{') depth += 1;
			else if (c === '}') {
				depth -= 1;
				if (depth === 0) {
					end = j;
					break;
				}
			}
			j += 1;
		}
		const text = line.slice(i + 1, end === -1 ? line.length : end);
		out.push({ text, block: /^\s*[#:/@]/.test(text) });
		i = end === -1 ? line.length : end + 1;
	}
	return out;
}
