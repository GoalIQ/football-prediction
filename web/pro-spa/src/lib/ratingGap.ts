/**
 * Rate my teamin otsikkoluku: ero vertailujoukkueeseen xP:na.
 *
 * 🔴 MIKSI EI ENAA "88/100" (MP-09, 25.9.2026). `rating.rating` on oman XI:n
 * horisontti-xP jaettuna parhaan LOYDETYN 100.0m-joukkueen XI:n xP:lla,
 * leikattuna sataan. Se ei ole prosenttipiste eika arvosana, mutta '/100' ja
 * 90/75-varirajat saivat sen lukemaan arvosanalta. Mitattu livena 25.9
 * (GW6-GW11, vertailukohta 319.4 xP): FPL:n kokonaisrankingin ykkonen sai 88,
 * satunnaiset entry-ID:t 88-92 ja yksi 82. Asteikko ei erottele, ja vihrea
 * raja 90 osui keskelle joukkoa ilman perustetta. Sama ero xP:na on 25-59,
 * eli samat joukkueet erottuvat, ja luku on samassa yksikossa kuin rivin
 * muut luvut.
 *
 * Vertailu on AINA ilman kapteenin TUPLAUSTA molemmilla puolilla:
 * `team_xp_horizon_no_captain` vs `optimal_team_xp`. Kapteeni on summassa
 * kerran (julkaisutarkistaja 25.9: "captain left out" olisi antanut 243.5 eika
 * 282.6, eli tarkistusreitti katkeaa). Rivin "Next N GW" -luku sisaltaa
 * tuplauksen, joten perusterivi nimeaa molemmat summat.
 *
 * Yksi lukija kaikille pinnoille (CLAUDE.md 6a mekanismi 1): otsikkorivi,
 * perusterivi ja vertailunakyma lukevat taman, eika mikaan niista laske eroa
 * itse. `gap_to_optimal_xp` on backendissa leikattu nollaan, joten ylitys
 * luetaan summista eika siita kentasta.
 */

/** Sama raja kuin vanhalla "You are level with it." -lauseella. */
const LEVEL_XP = 0.05;

export interface RatingGapInput {
	team_xp_horizon_no_captain?: number | null;
	optimal_team_xp?: number | null;
	optimal_proven?: boolean | null;
}

export interface RatingGap {
	/** Oma XI ilman kapteenia. */
	mine: number;
	/** Vertailujoukkueen XI ilman kapteenia. */
	best: number;
	/** mine - best. Negatiivinen = jaljessa. Tasoissa tasan 0. */
	diff: number;
	/** "-36.8 xP" / "+2.6 xP" / "0.0 xP". ASCII-miinus kuten mobiilissa. */
	text: string;
	/** true vain kun backend TODISTI vertailukohdan optimiksi. Puuttuva lippu
	 *  = ei todistettu: tama teksti kulkee jakokuviin asti, joten fail-closed.
	 *  Nimi on payloadin oma, jotta optimaalisuusportti
	 *  (tests/test_optimality_claim_family.py) nakee lipun vaitteen vieressa. */
	optimal_proven: boolean;
}

function finite(v: unknown): v is number {
	return typeof v === 'number' && Number.isFinite(v);
}

/** null = vertailukohtaa ei ole (vanha API tai optimi 0). Silloin pinta ei
 *  nayta lukua eika perustetta: luku ilman vertailukohtaa on vaite ilman reittia. */
export function ratingGap(r: RatingGapInput | null | undefined): RatingGap | null {
	if (!r || !finite(r.team_xp_horizon_no_captain) || !finite(r.optimal_team_xp)) return null;
	if (r.optimal_team_xp <= 0) return null;
	const raw = r.team_xp_horizon_no_captain - r.optimal_team_xp;
	const diff = Math.abs(raw) <= LEVEL_XP ? 0 : raw;
	const sign = diff > 0 ? '+' : diff < 0 ? '-' : '';
	return {
		mine: r.team_xp_horizon_no_captain,
		best: r.optimal_team_xp,
		diff,
		text: `${sign}${Math.abs(diff).toFixed(1)} xP`,
		optimal_proven: r.optimal_proven === true
	};
}

/** Solun nimio. "found" pysyy niin kauan kuin haku ei ole todistettu:
 *  tuotannossa `optimal_xi_proven()` on False, ja mallin oma joukkue (entry
 *  116920) voitti vertailukohdan 25.9. */
export function ratingGapLabel(g: RatingGap): string {
	return g.optimal_proven ? 'vs best squad' : 'vs best found';
}

/** Nakyva perusterivi otsikkorivin alle. `over` = xpHorizon(meta).over,
 *  jotta ikkuna on sama kuin rivin horisonttisolussa. */
export function ratingGapBasis(g: RatingGap, over: string): string {
	const ref = g.optimal_proven
		? 'Best squad = the strongest squad the model can build inside the 100.0m budget.'
		: 'Best found = the strongest squad the model found inside the 100.0m budget.';
	return (
		`${ref} Its XI projects ${g.best.toFixed(1)} xP ${over} and yours ` +
		`${g.mine.toFixed(1)}, captain bonus left out on both sides.`
	);
}
