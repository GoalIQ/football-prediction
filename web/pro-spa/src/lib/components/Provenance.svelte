<script lang="ts">
	// #50: mallin alkuperä-rivi FPL-työkalualueen yläreunassa (free + pro).
	//
	// 26.9 (PROVENANCE-LUKU-SIVULLE, julkaisutarkistajan versio A): luku
	// SEURAMALLIN lohkosta, samassa muodossa kuin goaliq.app/predictions#record
	// -sivun "All club matches" -summarivi. Blended all-time sisaltaa MM-kisojen
	// maajoukkuemallin rivit, eika sita saa kayttaa lauseessa joka vaittaa
	// "the same match model".
	//
	// WP2 (1.11.2026): luku tulee /api/accuracy:n `headline`-kentasta, jonka
	// backend laskee samalla funktiolla kuin hub-sivujen luvut
	// (src/models/accuracy.public_headline). SPA ei valitse rajausta eika
	// muotoile prosenttia itse: `pct_text` naytetaan sellaisenaan. Lauseen
	// "the same match model" -vaite on tosi vain seuramallille, joten luku
	// naytetaan vain kun `scope === 'club'`.
	// Fail-closed: ilman headlinea lause ilman lukua.
	// Portti: tests/test_track_record_one_number.py + tests/test_accuracy_by_model.py.
	import { fetchAccuracy, type AccuracyResponse } from '$lib/api';

	/** /api/accuracy:n `headline` (WP2). Tyyppi tassa, koska api.ts:n
	 *  AccuracyResponse sallii lisakentat (`[key: string]: unknown`). */
	type Headline = { scope: 'club' | 'all'; n: number; pct_text: string };

	let acc = $state<AccuracyResponse | null>(null);

	$effect(() => {
		fetchAccuracy()
			.then((a) => (acc = a))
			.catch(() => (acc = null));
	});

	let track = $derived.by(() => {
		const h = acc?.headline as Headline | null | undefined;
		if (h && h.scope === 'club' && h.n && h.pct_text) return { n: h.n, pct: h.pct_text };
		return null;
	});
</script>

<!-- Tarkistusreitti: /predictions#record, ensimmainen rivi "All club matches"
     samasta lahteesta (headline = by_model.club). MM erikseen omalla rivillaan. -->
<p class="provenance">
	Powered by the same match model behind our published, pre-match-logged club
	predictions{#if track}: {track.pct} correct
		<abbr title="Match result: home win, draw or away win">1X2</abbr> across
		{track.n} graded club matches{/if}.
	<a href="https://goaliq.app/predictions#record">Track record</a>
</p>

<style>
	.provenance {
		font-size: var(--step--1);
		color: var(--text-muted);
		margin: var(--s-3) 0 0;
	}
</style>
