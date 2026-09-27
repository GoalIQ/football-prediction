/**
 * Pelaajakortin hakujoukko (27.9.2026, julkaisutarkistajan loydos).
 *
 * VIKA: kortin oma hakukentta haki maskatusta /api/fantasy/xp-joukosta
 * (`players + excluded`), joka kirjautumattomalle on 10 + 184 pelaajaa 667:sta.
 * Ylahaku (PlayerFinder, `draftPool`) loysi kaikki, joten sama sivu vastasi
 * kahteen kenttaan eri tavalla: Cherki, Barry, Semenyo -> 0 osumaa kortissa.
 *
 * YKSI LUKIJA (saanto 6a): taydet rivit ensin (niissa on `full_name` ja
 * mallidata), sitten kevyet `pool`-rivit joita taysissa ei ole - sama
 * yhdistamissaanto kuin `draftPool`. Portti vaatii etta kortin haku kattaa
 * `draftPool`in joka tilassa (maskattu / premium / vanha API ilman poolia).
 */
import type { CardPlayer, XpPoolPlayer } from './api';

export type CardSearchItem =
	| (CardPlayer & { light?: false })
	| (XpPoolPlayer & { light: true });

export function cardSearchPool(full: CardPlayer[], light: XpPoolPlayer[]): CardSearchItem[] {
	const rows: CardSearchItem[] = full.map((p) => ({ ...p, light: false as const }));
	const seen = new Set(full.map((p) => p.id));
	for (const p of light) {
		if (!seen.has(p.id)) {
			seen.add(p.id);
			rows.push({ ...p, light: true as const });
		}
	}
	return rows;
}

/** Kevyt rivi kortin muotoon. Ei mallilukuja: kortti nayttaa FPL-faktat ja
 *  `lightOnly` pitaa sen poissa "not in the projections" -haarasta. */
export function cardFromLight(light: XpPoolPlayer): CardPlayer {
	return {
		id: light.id,
		web_name: light.web_name,
		full_name: light.full_name,
		team: light.team_short,
		team_short: light.team_short,
		pos: light.pos,
		price: light.price,
		status: light.status,
		news: light.news
	} as CardPlayer;
}
