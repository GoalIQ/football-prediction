<script lang="ts">
	// #50: mallin alkuperä-rivi FPL-työkalualueen yläreunassa (free + pro).
	//
	// 26.9 (PROVENANCE-LUKU-SIVULLE, julkaisutarkistajan versio A): luku
	// SEURAMALLIN lohkosta (by_model.club), samassa muodossa kuin
	// goaliq.app/predictions#record -sivun "All club matches" -summarivi
	// (fmt_pct / fmtPct), jotta lukija loytaa sen linkin takaa sellaisenaan.
	// Blended all-time sisaltaa MM-kisojen maajoukkuemallin rivit, eika sita
	// saa kayttaa lauseessa joka vaittaa "the same match model".
	// Fail-closed: ilman by_model-lohkoa lause ilman lukua.
	// Portti: tests/test_accuracy_by_model.py + fmt.test.ts.
	import { fetchAccuracy, type AccuracyResponse } from '$lib/api';
	import { fmtPct } from '$lib/fmt';

	let acc = $state<AccuracyResponse | null>(null);

	$effect(() => {
		fetchAccuracy()
			.then((a) => (acc = a))
			.catch(() => (acc = null));
	});

	let track = $derived.by(() => {
		const club = acc?.by_model?.club;
		if (club?.n && club?.pct_1x2 != null) return { n: club.n, pct: fmtPct(club.pct_1x2 * 100) };
		return null;
	});
</script>

<!-- Tarkistusreitti: /predictions#record, ensimmainen rivi "All club matches"
     samasta lahteesta (by_model.club). MM erikseen omalla rivillaan. -->
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
