/**
 * whatIfStart.ts - WHATIF-ALKUTILA (Villen paatos 27.9.2026, CC:n
 * suosituksen mukaan). Mobiilin vastine: goaliq-app lib/whatIfStart.ts (sama
 * saanto; mobiilin portti lib/whatIfStart.test.ts ajaa molemmat samoilla
 * syotteilla).
 *
 * TAUSTA (julkaisutarkistaja 22.9): Premiumin what-if alkoi mallin XI:sta
 * (`in_xi`) mutta KAYTTAJAN kapteenista (`is_captain`), ja `is_captain` on
 * viime kierroksen (GW5) FPL:n kapteeni: kayttajan GW6-kokoonpano ei ole
 * julkinen ennen deadlinea. Sama sekoitus meni vertailulukuun ("vs your
 * loaded lineup") ja jakokortille.
 *
 * SAANTO: alkutila = mallin XI + mallin kapteeni; oma tallennettu kapteeni
 * voittaa (kayttajan tuorein paatos). Vertailuluku ("vs the model's XI") on
 * mallin XI + mallin kapteeni KENTAN kierrokselle, luettuna rungosta jonka
 * malli arvioi (ei siirtojen jalkeisesta rungosta, jonka `in_xi` on peritty
 * lahtevalta pelaajalta).
 *
 * MALLIN KAPTEENI KIERROKSELLE (julkaisutarkistaja 27.9, B1): backendin kutsu
 * (`captain.pick` + `meta.captain_gw`) on yhdelle kierrokselle. Deadlinen
 * jalkeen kierroksen loppuun asti `captain_gw = gw + 1`, joten kentan
 * kierrokselle kutsua ei ole joka viikko. Silloin kaytetaan mallin omaa
 * saantoa (`fpl_rate_team.captain_suggestion`): mallin XI:n suurin kierroksen
 * xP. EI `is_captain`ia: se on kayttajan oma, ei mallin.
 */
import { modelCaptainFor, type ModelCaptain } from './pitchLineup';

type RosterPlayer = {
	id: number;
	in_xi?: boolean;
	is_captain?: boolean;
	xp_per_gw?: number;
	gameweeks?: readonly { gw: number; xp: number }[];
};

/** Kierroksen xP samalla tavalla kuin kentan `xpOf`: kierrosrivi jos
 *  kierros on valittu ja riveja on, puuttuva rivi = tyhja kierros = 0,
 *  muuten horisontin keskiarvo. */
export function roundXp(p: RosterPlayer, gw: number | null): number {
	if (gw != null && p.gameweeks && p.gameweeks.length > 0) {
		const g = p.gameweeks.find((x) => x.gw === gw);
		return g ? g.xp : 0;
	}
	return p.xp_per_gw ?? 0;
}

/** Mallin kapteeni kierrokselle `gw`: backendin kutsu jos se koskee tata
 *  kierrosta ja pelaaja on rungossa, muuten mallin saanto (XI:n suurin
 *  kierroksen xP). Tasapelissa rungon jarjestyksessa ensimmainen; backend
 *  ratkaisee tasapelin XI:n omassa jarjestyksessa pyoristamattomilla
 *  luvuilla, mutta saantoa kaytetaan vain kierroksilla joille backend ei
 *  anna kutsua, joten ne eivat voi nayttaa eri kapteenia samalle
 *  kierrokselle. null vain kun rungossa ei ole mallin XI:ta. */
export function whatIfDefaultCaptain<P extends RosterPlayer>(
	players: readonly P[],
	modelCaptain: ModelCaptain | null | undefined,
	gw: number | null,
	xp: (p: P) => number = (p) => roundXp(p, gw)
): number | null {
	const mc = modelCaptainFor(modelCaptain, gw);
	if (mc != null && players.some((p) => p.id === mc)) return mc;
	let best: number | null = null;
	let bestXp = -Infinity;
	for (const p of players) {
		if (!p.in_xi) continue;
		const v = xp(p);
		if (v > bestXp) {
			best = p.id;
			bestXp = v;
		}
	}
	return best;
}

/** Alkukapteeni: tallennettu oma (jos rungossa) voittaa oletuksen. */
export function whatIfInitialCaptain(
	players: readonly RosterPlayer[],
	saved: number | null | undefined,
	modelCaptain: ModelCaptain | null | undefined,
	gw: number | null
): number | null {
	if (saved != null && players.some((p) => p.id === saved)) return saved;
	return whatIfDefaultCaptain(players, modelCaptain, gw);
}

/** Onko nakyma yha mallin XI mallin kapteenilla: sama runko kuin mallin
 *  arvioima (siirto tekee siita eri joukkueen), sama XI ja sama kapteeni. */
export function isModelLineup(
	modelPlayers: readonly RosterPlayer[],
	rosterIds: readonly number[],
	xiIds: readonly number[],
	captainId: number | null,
	modelCaptainId: number | null
): boolean {
	const malli = new Set(modelPlayers.map((p) => p.id));
	if (rosterIds.length !== malli.size || !rosterIds.every((id) => malli.has(id))) return false;
	const xi = modelPlayers.filter((p) => p.in_xi).map((p) => p.id);
	if (xi.length !== xiIds.length) return false;
	const valittu = new Set(xiIds);
	return xi.every((id) => valittu.has(id)) && captainId === modelCaptainId;
}

/** Vertailuluku: mallin XI + mallin kapteeni kentan kierrokselle, arvioidusta
 *  rungosta. `xp` = kentan oma arvofunktio, jotta vertailu ja kentta laskevat
 *  saman kierroksen samalla tavalla. */
export function modelBaselineXp<P extends RosterPlayer>(
	modelPlayers: readonly P[],
	modelCaptain: ModelCaptain | null | undefined,
	gw: number | null,
	xp: (p: P) => number
): number {
	const cap = whatIfDefaultCaptain(modelPlayers, modelCaptain, gw, xp);
	let s = 0;
	for (const p of modelPlayers) {
		if (!p.in_xi) continue;
		s += xp(p) * (p.id === cap ? 2 : 1);
	}
	return s;
}
