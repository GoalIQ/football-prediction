<script lang="ts">
	import { capture } from '$lib/analytics';
	import type { HoldVerdict } from '$lib/fantasyTools';

	// #63: jaettu hero-verdikti rate-teamille + plannerille. Verdikti tulee
	// backendin hold_verdict-lohkosta (hit-tietoinen netto vs kynnys) - UI ei
	// laske omaa kantaa, vain nostaa mallin kannan keskiöön xP-matikan kera.
	let { verdict, surface }: { verdict: HoldVerdict; surface: 'rate_team' | 'planner' } = $props();

	$effect(() => {
		// Mittaa kuinka usein malli sanoo "hold" (mobiilipariteetti: sama
		// eventtinimi + kentät). Ei PII:tä - entry-ID ei mene eventtiin.
		capture('hold_verdict_shown', {
			verdict: verdict.verdict,
			best_move_gain_xp: verdict.best_move_gain_xp,
			surface
		});
	});

	const gainText = $derived(
		verdict.best_move_gain_xp === null
			? null
			: `${verdict.best_move_gain_xp >= 0 ? '+' : ''}${verdict.best_move_gain_xp.toFixed(2)}`
	);
	// HOLD-VERDICT-BEST-PLAN-COPY (29.8): best_move_gain_xp on KOKO suunnitelman
	// netto (plan_total - baseline_total, fpl_planner.py), ei yhden siirron.
	// Kun suunnitelmassa on useampi siirto, lause sanoo sen ja siirrot ovat
	// koko horisontin siirtoja ("across N GWs"), ei "nyt". Hitit: plannerin
	// hits_taken (maara), rate-teamin hit_applied_xp on aina yksi hitti.
	const nMoves = $derived(verdict.transfers_planned ?? 1);
	const hits = $derived(verdict.hits_taken ?? (verdict.hit_applied_xp ? 1 : 0));
	const hitNote = $derived(
		hits === 0 ? '' : hits === 1 ? ' after a -4 hit' : ` after ${hits} hits (-${hits * 4} xP)`
	);
	// 29.8 julkaisuportti k2: otsikko skooppasi ("nothing the model checked")
	// mutta mathrivi ei. "available" on sama kattavuusvaite pienoiskoossa:
	// rate-team hakee vain yksittaisia siirtoja ja plannerin oma
	// heuristiikkateksti sanoo "it doesn't try every possible plan".
	// "{n}-GW horizon" kestaa myos arvon 1, toisin kuin "over the next 1 GWs".
	// 29.8 portti k7: copy nimeaa kierrokset, ei kierrosmaaraa. Samalla
	// ruudulla on kaksi eri horisonttia (arvosana 6, siirrot 5) ja pelkka luku
	// ei kertonut kummasta on kyse. Vanha payload ilman rajoja -> maara.
	const gwSpan = $derived(
		verdict.gw_from != null && verdict.gw_to != null
			? verdict.gw_from === verdict.gw_to
				? `GW${verdict.gw_from}`
				: `GW${verdict.gw_from}-GW${verdict.gw_to}`
			: `the ${verdict.horizon_gws}-GW horizon`
	);
	const span = $derived(nMoves > 1 ? '' : ` over ${gwSpan}`);
	// 3.9 (siirtokynnys, kohta 4 + julkaisuportti B5/B6): hold-haaran mathrivi
	// KORVATAAN per-kierros-lauseella kun backend lahettaa paatosluvun ja
	// SOVELLETUN riman. Ei lisata viidetta sanamuotoa samalle kortille: sama
	// vaite eli 29.8 seitsemalla renderointipolulla ja portti loysi joka
	// kierroksella yhden lisaa. Luku ja rima tulevat samasta lohkosta kuin
	// vertailu (`best_move_case`), joten kortti ei voi vaittaa vertailua jota
	// ei tehty. Rate-team ei laheta naita kenttia -> vanha rivi, kuten ennen.
	const perGw = $derived(verdict.best_move_gain_xp_per_gw);
	const perGwBar = $derived(verdict.applied_bar_xp_per_gw);
	const bestCase = $derived(verdict.best_move_case ?? null);
	const bestWindow = $derived(
		verdict.best_move_window_gws && verdict.best_move_window_gws.length > 0
			? verdict.best_move_window_gws.length > 1
				? `GW${verdict.best_move_window_gws[0]}-GW${verdict.best_move_window_gws[verdict.best_move_window_gws.length - 1]}`
				: `GW${verdict.best_move_window_gws[0]}`
			: gwSpan
	);
	const planLabel = $derived(
		nMoves > 1
			? `Best plan the model checked (${nMoves} moves across ${gwSpan})`
			: 'Best move the model checked'
	);
	const goLabel = $derived(
		nMoves > 1
			? `Best plan the model checked (${nMoves} moves across ${gwSpan}) nets`
			: 'Best move the model checked nets'
	);
</script>

{#if verdict.verdict === 'hold'}
	<div class="verdict-hero hold" role="status">
		<!-- HOLD-TITLE-HORISONTTI (29.8): otsikko sanoi "this GW" vaikka verdikti
		     lasketaan koko horisontilta ja hold voi syntya kun suunnitelmassa ON
		     siirtoja mutta netto jaa kynnyksen alle ("Best available plan (3 moves
		     across 6 GWs): +1.20 xP"). Otsikko ja mathrivi vetivat eri suuntaan.
		     "beats" olisi yha vaara: suunnitelma voittaa, mutta ei tarpeeksi. -->
		<p class="title">Hold - nothing the model checked gains enough</p>
		<p class="math">
			{#if bestCase === 'below_bar' && perGw != null && perGwBar != null}
				Best move the model checked: {perGw >= 0 ? '+' : ''}{perGw.toFixed(2)} xP per gameweek over
				{bestWindow}, under your {perGwBar.toFixed(2)} threshold. Hold and bank the transfer.
			{:else if bestCase === 'later'}
				Best move the model checked pays off later than {bestWindow}. Hold and bank the transfer,
				you can still buy him then.
			{:else if gainText === null}
				Nothing the model checked improves your projected xP over {gwSpan}.
			{:else}
				{planLabel}: {gainText} xP{span}{hitNote}, below the {verdict.threshold_xp.toFixed(1)} xP
				threshold.
			{/if}
		</p>
	</div>
{:else}
	<div class="verdict-hero go" role="status">
		<!-- Portti 29.8 k2: otsikko klientista samalla luvulla kuin mathrivi (backendin
		     message pyoristaa 1 desimaaliin -> sama luku kahdella tarkkuudella), ei
		     sisakkaisia sulkuja; sama lause kuin mobiilin go_title/go_line. -->
		<p class="title">Recommended: {nMoves} transfer{nMoves === 1 ? '' : 's'} ({gainText} xP net)</p>
		<p class="math">
			{goLabel} {gainText} xP{span}{hitNote}, clears the {verdict.threshold_xp.toFixed(1)} xP
			threshold.
		</p>
	</div>
{/if}

<style>
	.verdict-hero {
		max-width: 640px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-4);
		margin: var(--s-4) 0 0;
		background: var(--surface);
	}
	.verdict-hero.hold {
		border-color: rgba(46, 214, 194, 0.5);
		border-left: 4px solid var(--positive);
		background: linear-gradient(160deg, rgba(46, 214, 194, 0.08), transparent 60%), var(--surface);
	}
	.verdict-hero.go {
		border-left: 4px solid var(--giq-rust);
	}
	.title {
		margin: 0 0 var(--s-1);
		font-weight: 700;
		font-size: var(--step-0);
	}
	.verdict-hero.hold .title {
		color: var(--positive);
	}
	.math {
		margin: 0;
		color: var(--text-muted);
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums;
	}
</style>
