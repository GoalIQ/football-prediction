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
	const span = $derived(nMoves > 1 ? '' : ` over ${verdict.horizon_gws} GWs`);
	const planLabel = $derived(
		nMoves > 1
			? `Best available plan (${nMoves} moves across ${verdict.horizon_gws} GWs)`
			: 'Best available move'
	);
	const goLabel = $derived(
		nMoves > 1 ? `Best plan (${nMoves} moves across ${verdict.horizon_gws} GWs) nets` : 'Best move nets'
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
			{#if gainText === null}
				No available move improves your projected xP over the next {verdict.horizon_gws} GWs.
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
