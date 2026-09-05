<script lang="ts">
	/**
	 * GwReview — post-GW-katsaus: mitä malli sanoi, mitä tapahtui, mitä nyt.
	 * Team Manager / FM-silmukka, vaihe 1 (Villen päätös 26.7).
	 * Mobiilin components/GwReview.tsx -vastine; säännöt ja copy identtiset.
	 *
	 * Teesi: FPL:n oma sovellus on transaktiotyökalu. Kukaan ei omista hetkeä
	 * "peliviikko meni, mitä nyt" — se on kalenteriongelma eikä taito-ongelma.
	 *
	 * REHELLISYYS (nämä eivät ole tyylivalintoja):
	 *  - `worst_call` renderöidään YHTÄ NÄKYVÄSTI kuin `best_call`, ja ENNEN
	 *    sitä. Huti piilotettuna on sama asia kuin ei hutia, ja paneeli joka
	 *    avaa omalla onnistumisellaan on mainos.
	 *  - `players_compared` kertoo kattavuuden. Vajaa kattavuus täytenä
	 *    esitettynä on sama valhe kuin nolla puuttuvan tilalla.
	 *  - provisionaalinen kierros merkitään näkyvästi, ei tooltipiin:
	 *    kosketuslaitteella hoveria ei ole.
	 *  - klientti EI laske mitään. Kaikki luvut tulevat endpointilta, joka
	 *    lukee kierroksen deadline-freezen.
	 */
	import { fetchGwReview, type GwReviewResponse } from '$lib/api';
	import { capture } from '$lib/analytics';
	import { fplEntry } from '$lib/fplEntry.svelte';

	/** 5.9: My team nayttaa vain "Before the next deadline" -lohkon kentan
	 *  alla (Villen pyynto: oman tiimin essentials nopeasti). Sama haku, sama
	 *  data, eri leikkaus. */
	let { flagsOnly = false }: { flagsOnly?: boolean } = $props();

	let data = $state<GwReviewResponse | null>(null);
	let failed = $state(false);
	let loadedKey = $state<string | null>(null);
	let viewedFired = false;

	$effect(() => {
		const raw = (fplEntry.entry || fplEntry.savedEntry || '').trim();
		const entry = /^\d{1,10}$/.test(raw) ? Number(raw) : null;
		const key = String(entry ?? '-');
		if (loadedKey === key) return;
		loadedKey = key;
		failed = false;
		data = null;
		if (entry == null) return;
		fetchGwReview(entry)
			.then((r) => {
				data = r;
				if (!viewedFired && r.meta.available) {
					viewedFired = true;
					capture('gw_review_viewed', { gw: r.meta.reviewed_gw });
				}
			})
			.catch(() => (failed = true));
	});

	const sign = (n: number) => (n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1));
</script>

{#if flagsOnly}
	{#if data?.meta.available && (data.flags.availability.length || data.flags.price.length)}
		<section class="wrap squad-news">
			<h3>Your squad before the deadline</h3>
			<div class="flags">
				<ul>
					{#each data.flags.availability as f (f.id)}
						<li>
							<strong>{f.web_name}</strong>
							{#if f.chance_next != null}{f.chance_next}% to play{/if}
							{#if f.news}<span class="muted">{f.news}</span>{/if}
						</li>
					{/each}
					{#each data.flags.price as f (f.id)}
						<li>
							<strong>{f.web_name}</strong>
							{f.progress_pct != null ? `${Math.round(f.progress_pct)}%` : ''} of the way
							to a price {f.direction}
						</li>
					{/each}
				</ul>
			</div>
		</section>
	{/if}
{:else}
<section class="wrap">
	<h3>Gameweek review</h3>

	{#if failed}
		<p class="muted">Could not reach the API. Try again in a moment.</p>
	{:else if !data}
		<p class="muted">Add your FPL team ID above to see your gameweek review.</p>
	{:else if !data.meta.available}
		<p class="muted">{data.meta.note}</p>
	{:else}
		{@const rv = data.review!}
		<div class="head">
			<span class="gw">GW{data.meta.reviewed_gw}</span>
			{#if data.meta.provisional}
				<!-- Näkyvä merkki, ei tooltip: kosketuslaitteella hoveria ei ole. -->
				<span class="prov">provisional</span>
			{/if}
			{#if data.meta.players_compared != null && data.meta.players_compared < 15}
				<!-- Kattavuus kerrotaan. Vajaa otos täytenä on valhe. -->
				<span class="muted small">{data.meta.players_compared} of 15 compared</span>
			{/if}
		</div>

		{#if rv.projected != null && rv.actual != null}
			<p class="total">
				<strong>{rv.actual}</strong> scored against
				<strong>{rv.projected.toFixed(1)}</strong> projected
				{#if rv.diff != null}<span
						class="d"
						class:ahead={rv.diff > 0}
						class:behind={rv.diff < 0}>{sign(rv.diff)}</span
					>{/if}
			</p>
		{/if}

		<!-- 🔴 HUTI ENNEN OSUMAA. Järjestys on tarkoituksellinen. -->
		{#if rv.worst_call}
			<div class="call worst">
				<span class="lbl">Model's worst call</span>
				<span class="who">{rv.worst_call.web_name}</span>
				<span class="num"
					>{rv.worst_call.projected.toFixed(1)} → {rv.worst_call.actual}</span
				>
			</div>
		{/if}
		{#if rv.best_call}
			<div class="call best">
				<span class="lbl">Biggest underestimate</span>
				<span class="who">{rv.best_call.web_name}</span>
				<span class="num"
					>{rv.best_call.projected.toFixed(1)} → {rv.best_call.actual}</span
				>
			</div>
		{/if}

		{#if data.model_says?.length}
			<ul class="says">
				{#each data.model_says as l (l.code + l.text)}
					<li>{l.text}</li>
				{/each}
			</ul>
		{/if}

		{#if data.flags.availability.length || data.flags.price.length}
			<div class="flags">
				<span class="lbl">Before the next deadline</span>
				<ul>
					{#each data.flags.availability as f (f.id)}
						<li>
							<strong>{f.web_name}</strong>
							{#if f.chance_next != null}{f.chance_next}% to play{/if}
							{#if f.news}<span class="muted">{f.news}</span>{/if}
						</li>
					{/each}
					{#each data.flags.price as f (f.id)}
						<li>
							<strong>{f.web_name}</strong>
							{f.progress_pct != null ? `${Math.round(f.progress_pct)}%` : ''} of the way
							to a price {f.direction}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<p class="muted small basis">{data.meta.basis}</p>
	{/if}
</section>
{/if}

<style>
	.wrap {
		margin: 18px 0;
	}
	h3 {
		font-size: 1rem;
		margin: 0 0 8px;
	}
	.head {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin-bottom: 6px;
	}
	.gw {
		font-weight: 700;
	}
	.prov {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		opacity: 0.7;
		border: 1px solid currentColor;
		border-radius: 0;
		padding: 0 4px;
		white-space: nowrap;
	}
	.total {
		margin: 4px 0 12px;
		font-size: 1.05rem;
	}
	.d {
		margin-left: 6px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.ahead {
		color: var(--ok, #2e7d32);
	}
	.behind {
		color: var(--bad, #b3261e);
	}
	.call {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 6px 0;
		border-top: 1px solid rgba(128, 128, 128, 0.25);
		font-size: 0.9rem;
	}
	.lbl {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.65;
	}
	.who {
		font-weight: 600;
		flex: 1;
	}
	.num {
		font-variant-numeric: tabular-nums;
		opacity: 0.85;
	}
	.says {
		margin: 12px 0 0;
		padding-left: 18px;
		font-size: 0.9rem;
		line-height: 1.5;
	}
	.flags {
		margin-top: 14px;
	}
	.flags ul {
		margin: 6px 0 0;
		padding-left: 18px;
		font-size: 0.9rem;
		line-height: 1.5;
	}
	.muted {
		opacity: 0.7;
	}
	.small {
		font-size: 0.78rem;
	}
	.basis {
		margin-top: 12px;
	}
</style>
