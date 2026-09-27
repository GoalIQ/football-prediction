/**
 * $lib/whatIfStart - WHATIF-ALKUTILA (Villen paatos 27.9.2026, CC:n
 * suosituksen mukaan). Mobiilin vastine: goaliq-app lib/whatIfStart.ts
 * (sama saanto; mobiilin portti lib/whatIfStart.test.ts ajaa
 * molemmat samoilla syotteilla).
 *
 * TAUSTA (julkaisutarkistaja 22.9): Premiumin what-if alkoi mallin XI:sta
 * (`in_xi`) mutta KAYTTAJAN kapteenista (`is_captain`), ja `is_captain` on
 * viime kierroksen (GW5) FPL:n kapteeni: kayttajan GW6-kokoonpano ei ole
 * julkinen ennen deadlinea. Sama sekoitus meni vertailulukuun ("vs your
 * loaded lineup") ja jakokortille.
 *
 * SAANTO: alkutila = mallin XI + mallin kapteeni kentan kierrokselle; oma
 * tallennettu kapteeni voittaa (kayttajan tuorein paatos). Vertailuluku on
 * mallin XI + mallin kapteeni. Kun kayttaja muuttaa XI:ta tai kapteenia,
 * nakyma ei ole enaa mallin XI, ja otsikko sanoo sen.
 */
import { modelCaptainFor, type ModelCaptain } from './pitchLineup';

type RosterPlayer = { id: number; in_xi?: boolean; is_captain?: boolean };

/** Mallin kapteeni kierrokselle `gw` jos han on rungossa, muuten viimeisen
 *  kierroksen FPL-kapteeni (vanha kaytos, kun mallin kutsua ei ole). */
export function whatIfDefaultCaptain(
	players: readonly RosterPlayer[],
	modelCaptain: ModelCaptain | null | undefined,
	gw: number | null
): number | null {
	const ids = new Set(players.map((p) => p.id));
	const mc = modelCaptainFor(modelCaptain, gw);
	if (mc != null && ids.has(mc)) return mc;
	return players.find((p) => p.is_captain)?.id ?? null;
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

/** Onko nakyma yha mallin XI mallin kapteenilla (ei kayttajan muutoksia). */
export function isModelLineup(
	players: readonly RosterPlayer[],
	xiIds: readonly number[],
	captainId: number | null,
	defaultCaptain: number | null
): boolean {
	const malli = players.filter((p) => p.in_xi).map((p) => p.id);
	if (malli.length !== xiIds.length) return false;
	const xi = new Set(xiIds);
	return malli.every((id) => xi.has(id)) && captainId === defaultCaptain;
}
