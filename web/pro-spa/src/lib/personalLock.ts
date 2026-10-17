/**
 * Henkilokohtaisten FPL-tyokalujen lukitus (17.10.2026, Villen paatos
 * "tyokalut taakse"; spec goaliq-app cos-reports/2026-10-17-tyokalut-maksumuuriin-spec.md).
 *
 * Kaikki tyokalut jotka lukevat KAYTTAJAN OMAA joukkuetta (rate my team,
 * This weekin paatoskortti, GW review, DefCon live, Beat the Model, mini-
 * liigan head-to-head, watchlist, fit checker, price watchin ja
 * differentialsin oman joukkueen merkinnat) ovat Premiumia. Julkiset listat
 * ja mallin oma kapteeni jaavat ilmaiseksi.
 *
 * SAANTO 6a KOHTA 1 (yksi lukija joka ei voi palauttaa vaaraa). Lukitus
 * ratkeaa TASSA, ei jokaisen komponentin omassa ehdossa. Lukittu on tosi kun
 *   1. kayttajalla ei ole Premiumia (`premium` = ToolsHomen
 *      `forcePremium || !!auth.sub`), TAI
 *   2. palvelin lukitsi vastauksen (`meta.locked_tool` on asetettu).
 * Kumpikaan ei yksin riita:
 *   - Ennen 21.10.2026 00 UTC palvelin antaa ilmaiskayttajalle yha taydet
 *     tiedot (api/premium.py PERSONAL_TOOLS_ENFORCE_FROM), joten SPA:n on
 *     lukittava itse. Ilman ehtoa 1 lukitus alkaisi vasta kytkimesta.
 *   - Kytkimen jalkeen palvelin on totuus (spec "Periaate" 2: klientti saa
 *     piilottaa lisaa, mutta ei koskaan nayttaa sita mita palvelin ei
 *     antanut). Ilman ehtoa 2 vanhentunut `auth.sub` nayttaisi tyhjiksi
 *     typistettyja kenttia nollina.
 *
 * 🔴 Tunniste on `meta.locked_tool`, EI `meta.masked`. Vanhoissa
 * esimakumaskeissa (rate-teamin siirtolista, kapteenirankkerin yksi rivi)
 * `masked` on tosi ilman `locked_tool`ia, ja ne ovat Premium-kayttajalle
 * mahdottomia mutta ilmaiselle normaali tila. Pelkka `masked` lukitsisi
 * ilmaisen esimaun koko nakymana.
 *
 * Portti `personalLock.gate.test.ts` kaataa buildin jos henkilokohtainen
 * komponentti ei kysy lukitusta tasta, tai jos uusi komponentti hakee
 * henkilokohtaista dataa ilman etta se on listalla (6a kohta 2).
 */

/** Analytiikan `paywall_shown`-lahde lukitusnakymalle. */
export const PERSONAL_LOCK_SOURCE = 'personal_lock';

/** Lukitusnakymien tunnisteet. Palvelimen slugit (`meta.locked_tool`) ja
 *  SPA:n omat pinnat joilla ei ole omaa endpointtia (Team 2 -vertailu, This
 *  weekin paatoskortti, Beat the Model, watchlist). */
export type PersonalSlug =
	| 'rate-my-team'
	| 'team-compare'
	| 'this-week'
	| 'gw-review'
	| 'defcon-live'
	| 'beat-the-model'
	| 'league'
	| 'watchlist'
	| 'fit-checker'
	| 'price-watch'
	| 'differentials';

/** Vastaus jonka metassa voi olla palvelimen lukitus. `meta` on tahallaan
 *  `unknown`: jokaisella endpointilla on oma meta-tyyppinsa, eika lukija saa
 *  vaatia niilta yhteista muotoa (lukitus luetaan varmistaen). */
export type LockablePayload = { meta?: unknown } | null | undefined;

/** Palvelimen lukitsema tyokalu (`meta.locked_tool`), tai null. Tyhja tai
 *  muu kuin merkkijono ei ole lukitus: se olisi vaite jota palvelin ei tehnyt. */
export function serverLockedTool(payload: LockablePayload): string | null {
	const meta = payload?.meta;
	if (meta == null || typeof meta !== 'object') return null;
	const v = (meta as { locked_tool?: unknown }).locked_tool;
	return typeof v === 'string' && v.trim() !== '' ? v : null;
}

/**
 * Onko henkilokohtainen nakyma lukittu.
 *
 * `payloads`: vastaukset joista nakyma piirretaan (ei mitaan = vain
 * kayttajan taso ratkaisee, esim. ennen hakua tai SPA:n oma lista). Yksikin
 * palvelimen lukitsema vastaus lukitsee nakyman.
 */
export function personalLock(premium: boolean, ...payloads: LockablePayload[]): boolean {
	if (!premium) return true;
	return payloads.some((p) => serverLockedTool(p) != null);
}

/** Lukitusnakyman CTA:n `upgrade_tapped`-lahde. Ei kayta billing.ts:n
 *  startCheckoutia (sen muoto {source, plan, price} on kassan oma). */
export function lockUpgradeSource(slug: PersonalSlug): string {
	return `${PERSONAL_LOCK_SOURCE}_${slug}`;
}

/**
 * Lukitusnakyman teksti. YKSI TAULU, jotta julkaisutarkistaja lukee kaikki
 * lukkolauseet yhdesta paikasta eika yksikaan pinta keksi omaansa.
 * Englanti, ei em dashia, ei hintoja (hinta on maksumuurissa).
 */
export const LOCK_COPY: Record<PersonalSlug, { title: string; body: string }> = {
	'rate-my-team': {
		title: 'The full analysis is part of GoalIQ Premium',
		body: "Premium adds the weak spot in your XI, the captain pick for your squad, the hold or transfer call with the move itself, your chips, the pitch with each player's projection, squad news and your season against the projection."
	},
	'team-compare': {
		title: 'Comparing two squads is part of GoalIQ Premium',
		body: "Premium rates a second squad next to yours, or loads the model's own 15 so you can try to beat it."
	},
	'this-week': {
		title: 'Your own captain, transfer and chip call is part of GoalIQ Premium',
		body: "Premium checks this gameweek's decisions for your squad: the captain for your XI, whether to hold or which move to make, and which chips you still have."
	},
	'gw-review': {
		title: 'Your gameweek review is part of GoalIQ Premium',
		body: 'Premium lines up what the model projected for your players against what they scored, with its worst call and its biggest underestimate.'
	},
	'defcon-live': {
		title: 'DefCon live for your squad is part of GoalIQ Premium',
		body: "Premium follows your players' defensive contributions against the threshold while the gameweek is being played."
	},
	'beat-the-model': {
		title: 'Logging your calls against the model is part of GoalIQ Premium',
		body: "Premium logs your captain and transfer calls next to the model's and grades both once FPL has scored the gameweek, with a season scoreboard and a decision journal."
	},
	league: {
		title: 'Head-to-head win probability is part of GoalIQ Premium',
		body: "Premium gives the model's win probability for the next gameweek between any two managers in your league, from each XI's projected points."
	},
	watchlist: {
		title: 'The watchlist is part of GoalIQ Premium',
		body: 'Premium tracks the players you are deciding on, with price moves and availability flags at a glance.'
	},
	'fit-checker': {
		title: 'The fit checker is part of GoalIQ Premium',
		body: 'Premium searches for the strongest 15 it can find around up to three players you lock in, and shows what locking them costs.'
	},
	'price-watch': {
		title: 'Marking your own players is part of GoalIQ Premium',
		body: 'Premium marks which of your 15 are about to rise or fall, and when.'
	},
	differentials: {
		title: 'Filtering by your squad is part of GoalIQ Premium',
		body: 'Premium leaves out the players you already own and lists the template players you are missing.'
	}
};

/** Rate my teamin ilmainen esimaku: arvosana. Palvelin jattaa nama kentat
 *  oikeiksi myos lukittuun vastaukseen (RATE_TEAM_PREVIEW_RATING_FIELDS),
 *  joten esimaku on sama ennen ja jalkeen kytkimen. */
export interface RatingPreviewInput {
	rating?: number | null;
	percentile?: number | null;
	beats_benchmark?: boolean | null;
}

/**
 * Esimaun lause. `rating` = oman XI:n horisontti-xP prosentteina parhaan
 * LOYDETYN 100.0m-joukkueen XI:sta, kapteenin tuplaus pois molemmilta
 * (fpl_rate_team.py: raw_pct, leikattu sataan). 🔴 Ei "88/100" eika vareja:
 * MP-09 (25.9) mittasi etta arvosanamuoto luki arvosanalta ilman perustetta
 * ($lib/ratingGap). Prosentti ja lause nimeavat mita vasten mitataan.
 *
 * null = palvelin ei antanut lukua -> ei lausetta (luku ilman lahdetta olisi
 * keksitty). `over` = xpHorizon(meta).over, sama ikkuna kuin muualla.
 */
export function ratingPreview(
	r: RatingPreviewInput | null | undefined,
	over: string
): { pct: number | null; text: string } | null {
	if (!r) return null;
	const tail = ` the strongest squad the model found inside the 100.0m budget, ${over}. Captain bonus left out on both sides.`;
	if (r.beats_benchmark === true) {
		return { pct: null, text: `Your XI projects more points than${tail}` };
	}
	const raw =
		typeof r.rating === 'number' && Number.isFinite(r.rating)
			? r.rating
			: typeof r.percentile === 'number' && Number.isFinite(r.percentile)
				? Math.round(r.percentile)
				: null;
	if (raw == null) return null;
	const pct = Math.max(0, Math.min(100, Math.round(raw)));
	return { pct, text: `Your XI projects ${pct}% of the points of${tail}` };
}
