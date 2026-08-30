/** Kierrosvalinta SPA:lle: yksi funktio, ei kuutta haaraa.
 *
 * 🔴 MIKSI: `meta.next_gameweek` on KESKEN oleva kierros heti kun kierroksen
 * ensimmainen ottelu on alkanut. 30.8.2026 mitattu: `next_gameweek` oli 2 ja
 * `deadline_gameweek` 3. Kaikki mihin lukija voi VIELA vaikuttaa - kapteeni,
 * xP-teaser, siirrot - kuuluu deadline-kierrokselle.
 *
 * WorkspaceBar korjasi taman itselleen 22.8 (palkki naytti "GAMEWEEK 1
 * DEADLINE Fri 28 Aug"), mutta korjaus jai yhteen komponenttiin ja viisi
 * muuta kayttokohtaa jai raa'an `next_gameweek`in varaan. Sama vikaluokka
 * jonka backendin `fpl_gameweek.py` dokumentoi viidesti. Nyt logiikka on
 * yhdessa paikassa, kuten backendissa `actionable_gameweek`.
 */
export function actionableGameweek(
	meta: { deadline_gameweek?: number | null; next_gameweek?: number | null } | null | undefined
): number | undefined {
	const m = meta ?? {};
	if (typeof m.deadline_gameweek === 'number') return m.deadline_gameweek;
	if (typeof m.next_gameweek === 'number') return m.next_gameweek;
	/* undefined eika null: kutsupaikat antavat taman eteenpain funktioille
	   joiden parametri on `number | undefined`. Nolla EI ole vaihtoehto -
	   se olisi kierros 0 (muisti: nolla-ei-ole-sama-kuin-ei-tietoa). */
	return undefined;
}
