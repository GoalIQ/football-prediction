/** Fixture swing -luku nakyviin (12.9.2026).
 *
 * Swing on high xP miinus low xP, ja lista jarjestetaan sen mukaan
 * (`FixtureSwing.svelte`). Sarake naytti aiemmin suhdelukua (high / low),
 * joten jarjestys ja nakyva luku olivat kaksi eri lukua: 0.5 -> 1.5 nakyi
 * "3.0x" ja 3.0 -> 5.0 "1.7x", vaikka jalkimmainen oli listalla ylempana.
 * Sarake ja jakokortti kayttavat nyt tata samaa funktiota samasta kentasta.
 *
 * Etumerkki paatetaan pyoristetysta arvosta, jotta 0.04 ei nay "+0.0".
 * Portti: tests/test_fixture_swing_column.py */
export function formatSwing(swing: number): string {
	const s = swing.toFixed(1);
	return Number(s) > 0 ? `+${s}` : s;
}
