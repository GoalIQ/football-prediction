import type { XpPoolPlayer, XpResponse } from './api';

/** Draft-/lukitusvalitsimen pooli: täydet rivit ensin, sitten kevyet rivit
 *  niille joita täysissä ei ole (14.8).
 *
 *  MIKSI YHDISTETÄÄN eikä korvata: täydet rivit kantavat `full_name`-haun,
 *  joten pelkkä kevyen listan käyttö veisi koko nimellä hakemisen myös
 *  premium-käyttäjältä. Yhdistäminen antaa free-käyttäjälle täytettävän
 *  valitsimen ilman että premium-pinta menettää mitään.
 *
 *  Fallback `players` on tarkoituksellinen: jos backend ei vielä tuo poolia
 *  (vanha deploy), käytös on tasan entinen eikä valitsin kaadu. */
export function draftPool(d: XpResponse): XpPoolPlayer[] {
	const rows: XpPoolPlayer[] = [...(d.players ?? [])];
	const seen = new Set(rows.map((p) => p.id));
	for (const p of d.pool ?? []) {
		if (!seen.has(p.id)) rows.push(p);
	}
	return rows;
}
