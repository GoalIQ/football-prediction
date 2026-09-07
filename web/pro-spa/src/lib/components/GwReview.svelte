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
	import { gwReviewCardSpec, reviewTotals } from '$lib/gwReviewCard';
	import { shareCard, shareButtonLabel } from '$lib/shareCard';

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

	// 6.9 (Villen tilaus): katsaus kuvana. Sisalto tulee gwReviewCard.ts:sta
	// (sama lukija mobiilissa); tama vain valittaa sen listakortille.
	// Sama joukko kuin kortilla: pelanneet rivit (multiplier > 0).
	let totals = $derived(
		(() => {
			const xi = (data?.review?.players ?? []).filter((p) => p.in_xi && p.multiplier > 0);
			return xi.length ? reviewTotals(xi) : null;
		})()
	);
	let cardSpec = $derived(data && data.meta.available ? gwReviewCardSpec(data) : null);
	let sharing = $state(false);
	async function shareReview() {
		if (!cardSpec || sharing) return;
		sharing = true;
		try {
			const method = await shareCard(cardSpec);
			if (method !== 'aborted' && method !== 'too_few_rows') {
				capture('gw_review_shared', { gw: data?.meta.reviewed_gw ?? null, method });
			}
		} finally {
			sharing = false;
		}
	}
</script>

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
			<!-- U3 (7.9): nimittaja tulee payloadista, ei kovakoodattuna. Kortti
			     sanoo saman lauseen samoista luvuista. -->
			{#if data.meta.players_compared != null && data.meta.total_picks != null && data.meta.players_compared < data.meta.total_picks}
				<span class="muted small"
					>{data.meta.players_compared} of {data.meta.total_picks} picks compared</span
				>
			{/if}
			{#if cardSpec}
				<button type="button" class="share-chip" onclick={shareReview} disabled={sharing}>
					{sharing ? 'Preparing…' : shareButtonLabel()}
				</button>
			{/if}
		</div>

		<!-- 🔴 U2 (7.9): PANEELI JA KORTTI SAMASTA LUKIJASTA. Paneeli renderoi
		     ennen payloadin `diff`in (0.85 -> "+0.9") ja kortti laski naytetyista
		     luvuista (71.2 ja 72 -> "+0.8"). Jakonappi on SAMASSA otsikkorivissa,
		     joten lukija naki molemmat yhta aikaa. Nyt molemmat lukevat
		     `reviewTotals`in eika kahta lukua voi olla. -->
		<!-- B6 (7.9, portti): paneeli naytti saman luvun ja vain sanan
		     "provisional" samalla kun kortti selittaa eron. Sama luku, sama
		     lukija, toinen pinta selittaa ja toinen ei. -->
		{#if data.meta.provisional || (data.meta.fpl_points != null && totals && data.meta.fpl_points !== totals.actual)}
			<p class="muted small prov-note">
				<!-- 🔴 C2 (portin 4. kierros): EMME NIMEA SYYTA. Aiempi lause sanoi
				     eron johtuvan vahvistamattomasta bonuksesta, mutta mitattu 7.9:
				     XI-summa 72, kerroinpainotettu bonus 15, siis ilman bonusta 57 -
				     ja FPL sanoo 58. Lukija joka laskee 58 + 15 ei paase 72:een. Ja
				     `entry_history.points` on NETTO siirtorangaistuksista, joten -4:n
				     viikolla syy ei olisi bonus lainkaan. Sanomme kumpi luku on kumpi. -->
				{#if data.meta.fpl_points != null && totals && data.meta.fpl_points !== totals.actual}
					<!-- D3: mutabiliteettilause VAIN kesken olevalle kierrokselle.
					     Lopullisella FPL on lopettanut pisteytyksen, mutta ero voi silti
					     olla (siirtorangaistus, autosub, pudonnut rivi). -->
					{#if data.meta.provisional}
						FPL's own total for GW{data.meta.reviewed_gw} is {data.meta.fpl_points}. Ours
						adds up the live scores for those same {totals.rows} picks that had a multiplier,
						and it can move until FPL finishes scoring.
					{:else}
						FPL's own total for GW{data.meta.reviewed_gw} is {data.meta.fpl_points}. Ours
						adds up the {totals.rows} picks that had a multiplier.
					{/if}
				{:else}
					GW{data.meta.reviewed_gw} is still being scored, so these totals can move.
				{/if}
			</p>
		{/if}

		<!-- B3 (9. kierros): FPL:n `points` on netto siirtorangaistuksista. -->
		{#if data.meta.transfer_cost}
			<p class="muted small prov-note">
				FPL's total is after a {data.meta.transfer_cost} point transfer hit.
			</p>
		{/if}

		{#if totals}
			<p class="total">
				<strong>{totals.actual}</strong> scored against
				<strong>{totals.projectedText}</strong> projected
				<span class="d" class:ahead={totals.diff > 0} class:behind={totals.diff < 0}
					>{sign(totals.diff)}</span
				>
			</p>
		{/if}

		<!-- 🔴 HUTI ENNEN OSUMAA. Järjestys on tarkoituksellinen. -->
		<!-- 🔴 Portin 8. kierros, kaksi vikaa samassa lohkossa:
		     (1) rivit nayttivat KERROINPAINOTETUT luvut vaikka valinta tulee
		         raakaerosta ja proosa raakaluvuista - kolme lukuparia samasta
		         pelaajasta samassa lohkossa.
		     (2) `best_call` on aina `max(...)`, joten viikolla jossa jokainen
		         aloittaja alisuoriutui otsikko sanoi "Biggest underestimate"
		         pelaajasta joka JAI projektiosta. Proosalla oli
		         etumerkkivartija, rivilla ei. -->
		{#if rv.worst_call && (rv.worst_call.diff_raw ?? rv.worst_call.diff) < 0}
			<div class="call worst">
				<span class="lbl">Model's worst call</span>
				<span class="who"
					>{rv.worst_call.web_name}{rv.worst_call.multiplier >= 3
						? ' TC'
						: rv.worst_call.multiplier >= 2
							? ' C'
							: ''}</span
				>
				<span class="num"
					>{(rv.worst_call.projected_raw ?? rv.worst_call.projected).toFixed(1)} → {rv
						.worst_call.actual_raw ?? rv.worst_call.actual}</span
				>
			</div>
		{/if}
		{#if rv.best_call && (rv.best_call.diff_raw ?? rv.best_call.diff) > 0}
			<div class="call best">
				<span class="lbl">Biggest underestimate</span>
				<span class="who"
					>{rv.best_call.web_name}{rv.best_call.multiplier >= 3
						? ' TC'
						: rv.best_call.multiplier >= 2
							? ' C'
							: ''}</span
				>
				<span class="num"
					>{(rv.best_call.projected_raw ?? rv.best_call.projected).toFixed(1)} → {rv
						.best_call.actual_raw ?? rv.best_call.actual}</span
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
	.share-chip {
		margin-left: auto;
		font: inherit;
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0.2em 0.6em;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: transparent;
		color: var(--text-muted);
		cursor: pointer;
	}
	.share-chip:disabled {
		opacity: 0.6;
		cursor: default;
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
	.prov-note {
		margin: 4px 0 2px;
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
