<script lang="ts">
	// #50: mallin alkuperä-rivi FPL-työkalualueen yläreunassa (free + pro).
	// Live track record /api/accuracy:sta jos kentät ovat saatavilla;
	// ilman niitä rivi renderöityy silti (defensiivinen, ei kaadu).
	import { fetchAccuracy, type AccuracyResponse } from '$lib/api';

	let acc = $state<AccuracyResponse | null>(null);

	$effect(() => {
		fetchAccuracy().then((a) => (acc = a));
	});

	// 26.9 (PROVENANCE-SEURAMALLI-609): luku SEURAMALLIN lohkosta. Blended
	// headline-luku sisalsi 56 maajoukkuemallin MM-ennustetta (609 vs 553), eli
	// lause "the same match model" vaitti niista jotain mita ne eivat ole.
	// Fail-closed: ilman by_model-lohkoa (vanha accuracy.json) lause ilman lukua.
	let track = $derived.by(() => {
		const club = acc?.by_model?.club;
		if (club?.n && club?.pct_1x2) return { n: club.n, pct: club.pct_1x2 * 100 };
		return null;
	});
</script>

<!-- Tarkistusreitti: /predictions#record listaa jokaisen liigan omalla
     rivillaan (MM erikseen), eli seuraliigojen summa on luettavissa sielta. -->
<p class="provenance">
	Powered by the same match model behind our published, pre-match-logged club
	predictions{#if track}: {track.pct.toFixed(0)}% correct
		<abbr title="Match result: home win, draw or away win">1X2</abbr> across
		{track.n} logged club matches{/if}.
	<a href="https://goaliq.app/predictions#record">Track record</a>
</p>

<style>
	.provenance {
		font-size: var(--step--1);
		color: var(--text-muted);
		margin: var(--s-3) 0 0;
	}
</style>
