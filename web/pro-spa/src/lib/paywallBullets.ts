/** Web-maksumuurin hyotylista (ulkoasu WP8 / B2, Villen paatos 1.11.2026
 * "paywall lyhyeksi ja napautettuun ominaisuuteen keskitetyksi").
 *
 * Ennen Paywall listasi FPL-hyodyt yhtena 60 sanan kappaleena ja ottelumallin
 * toisena, ennen hintaa. Nyt nakyy nelja riviä, loput "See all" -avauksen
 * takana: yksikaan myyty ominaisuus ei katoa, se siirtyy alemmas.
 *
 * Rivit ovat sovelluksen paywall.bullet_*-tekstit (goaliq-app lib/i18n/en.ts,
 * julkaisutarkistaja k2 1.11), ja jokainen on tosi myos webissa: Team 2
 * -vertailu (team-compare), This week + DefCon live, Transfer planner + plan
 * chains, mini-liigan H2H + fit checker + price watch + differentials ovat
 * kaikki SPA:n lukkoja ($lib/personalLock LOCK_COPY).
 *
 * Kapteeni EI ole listalla: oman XI:n kapteeni on 1.11 alkaen ilmainen
 * (fp api/premium.py RATE_TEAM_FREE_OPEN). Portti: paywallBullets.gate.test.ts. */
export const PAYWALL_TOP: readonly string[] = [
	"Rate my team in full: the weak spot in your XI, the hold or transfer call, your chips, the pitch with each player's projection and a second squad to compare",
	'This week for your squad: transfer and chip calls, and DefCon live for your players while the matches are played',
	'Multi-gameweek transfer planner and plan chains',
	'Mini-league head-to-head win probability, the fit checker, and your own players marked in price watch and differentials'
];
