<script lang="ts">
	/**
	 * WildcardPlan — kannattaako wildcard, MIHIN joukkueeseen ja MIKSI.
	 * Villen ohje 25.8: "jos se ehdottaa nii pitää perustella miksi ja mihin
	 * joukkueeseen (ottaen huomioon pitemmän aikavälin pelit kans)".
	 *
	 * Tämä paneeli on olemassa koska ChipEv antoi pelkän luvun, ja se luku oli
	 * lisäksi vertailukelvoton rivien välillä (GW2 38,00 vs GW7 10,37 — eri
	 * pituiset ikkunat esitettynä ajoitusvertailuna).
	 *
	 * REHELLISYYS (nämä eivät ole tyylivalintoja):
	 *  - KUSTANNUS ENNEN HYÖTYÄ. `changes N of your 15` renderöidään ensin ja
	 *    yhtä näkyvästi kuin EV. Paneeli joka avaa omalla voitollaan on mainos.
	 *  - `timing`-varaus renderöidään LUVUN VIERESSÄ, ei alaviitteeksi. Varaus
	 *    joka on eri paikassa kuin luku ei ole kerrottu.
	 *  - `long_view` on ERI PERUSTA (joukkuetason FDR, ei pelaajien xP) ja se
	 *    merkitään omalla otsikollaan. Sitä ei koskaan summata xP-lukuun.
	 *  - "hold" näytetään yhtä isolla kuin suositus. Työkalu joka ei osaa sanoa
	 *    ei, ei sano kyllääkään mitään.
	 *  - klientti EI laske mitään. Kaikki luvut tulevat endpointilta.
	 */
	import {
		fetchWildcardPlan,
		type WildcardPlanResponse,
		type WildcardRow
	} from '$lib/fantasyTools';
	import { capture } from '$lib/analytics';
	import { fplEntry } from '$lib/fplEntry.svelte';
	import MethodNote from './MethodNote.svelte';

	let loading = $state(false);
	let error = $state<string | null>(null);
	let data = $state<WildcardPlanResponse | null>(null);
	let viewedFired = false;

	let entryValid = $derived(/^\d{1,10}$/.test(fplEntry.entry.trim()));

	async function load() {
		if (loading) return;
		loading = true;
		error = null;
		try {
			data = await fetchWildcardPlan(entryValid ? Number(fplEntry.entry.trim()) : null);
			if (!viewedFired) {
				viewedFired = true;
				capture('wildcard_plan_viewed', {
					recommend: data.plan?.recommend ?? null,
					gw: data.plan?.gw ?? null
				});
			}
		} catch (err) {
			data = null;
			error = err instanceof Error ? err.message : String(err);
		} finally {
			loading = false;
		}
	}

	const plan = $derived(data?.plan ?? null);
	const reason = (code: string) => plan?.reasons?.find((r) => r.code === code)?.text ?? null;

	function fmtRow(r: WildcardRow) {
		// 🔴 Em dash on kova saanto (0 osumaa) ja se koskee myos
		// tallaista fallbackia. Puuttuva lyhenne jatetaan pois kokonaan.
		const osat = [r.pos, r.team_short, `£${r.price.toFixed(1)}m`];
		return osat.filter(Boolean).join(' · ');
	}
</script>

<section class="wrap">
	<h2>Wildcard: is it worth it, and into what?</h2>

	{#if !data && !loading}
		<button type="button" class="window-chip" onclick={load}>
			{entryValid ? 'Check my wildcard' : 'Check the model squad'}
		</button>
	{/if}

	{#if loading}
		<p class="muted">Rebuilding a full 15 and scoring every switch point...</p>
	{:else if error}
		<p class="muted">Could not reach the API. Try again in a moment.</p>
	{:else if plan && !plan.available}
		<p class="muted">{plan.note}</p>
	{:else if plan}
		<!-- 🔴 KUSTANNUS ENSIN. Järjestys on tarkoituksellinen. -->
		{#if reason('cost')}
			<p class="cost">{reason('cost')}</p>
		{/if}

		<div class="verdict" class:go={plan.recommend} class:hold={!plan.recommend}>
			<span class="lbl">{plan.recommend ? `Play it in GW${plan.gw}` : 'Hold the chip'}</span>
			{#if plan.ev_per_gw != null}
				<span class="num">{plan.ev_per_gw > 0 ? '+' : ''}{plan.ev_per_gw.toFixed(2)}</span>
				<span class="unit">pts / gameweek</span>
			{/if}
		</div>

		<!-- CHIP-EV-CHIPS-USED (3.9): chip jo pelattu talla puolikkaalla ->
		     sanotaan VERDIKTIN VIERESSA, ei MethodNoten suljetun <details>-
		     lohkon takana (varaus eri paikassa kuin luku ei ole kerrottu). -->
		{#if data?.meta?.wildcard_chip?.history_loaded && data.meta.wildcard_chip.available_now === false}
			{@const wc = data.meta.wildcard_chip}
			{@const next = wc.windows.find((w) => w.available)}
			<p class="line chip-gone">
				{#if wc.played_gws.length}Entry {data.meta.entry} already played its Wildcard in GW{wc.played_gws.at(-1)}.{:else}No Wildcard left in this half.{/if}
				{#if next}The next one opens in GW{next.start_gw}.{:else}No Wildcard window left this season.{/if}
				The plan shows what a fresh 15 would gain.
			</p>
		{/if}
		{#if reason('ev')}<p class="line">{reason('ev')}</p>{/if}
		{#if reason('hold')}<p class="line">{reason('hold')}</p>{/if}
		{#if reason('flags')}<p class="line">{reason('flags')}</p>{/if}

		<!-- 🔴 Menetelmävaraus LUVUN VIERESSÄ, ei alaviitteenä. -->
		{#if reason('timing')}
			<p class="caveat">{reason('timing')}</p>
		{/if}

		{#if plan.out?.length && plan.in?.length}
			<h3>What it changes</h3>
			<div class="swap">
				<div>
					<span class="lbl">Out</span>
					<ul>
						{#each plan.out.slice(0, 6) as r (r.id)}
							<li>
								<strong>{r.web_name}</strong>
								<span class="muted small">{fmtRow(r)}</span>
								<span class="xp">{r.xp_per_gw.toFixed(2)}</span>
							</li>
						{/each}
					</ul>
				</div>
				<div>
					<span class="lbl">In</span>
					<ul>
						{#each plan.in.slice(0, 6) as r (r.id)}
							<li>
								<strong>{r.web_name}</strong>
								<span class="muted small">{fmtRow(r)}</span>
								<span class="xp">{r.xp_per_gw.toFixed(2)}</span>
							</li>
						{/each}
					</ul>
				</div>
			</div>
			<p class="muted small">
				Points per gameweek over GW{plan.gw} to {(plan.gw ?? 0) + (plan.window_gws ?? 1) - 1}.
			</p>
		{/if}

		{#if plan.squad}
			<h3>The squad it builds</h3>
			<ul class="squad">
				{#each plan.squad.xi as r (r.id)}
					<li><strong>{r.web_name}</strong> <span class="muted small">{fmtRow(r)}</span></li>
				{/each}
			</ul>
			<span class="lbl">Bench</span>
			<ul class="squad bench">
				{#each plan.squad.bench as r (r.id)}
					<li><strong>{r.web_name}</strong> <span class="muted small">{fmtRow(r)}</span></li>
				{/each}
			</ul>
		{/if}

		{#if plan.long_view && reason('long_view')}
			<!-- 🔴 ERI PERUSTA, OMA OTSIKKO. Ei koskaan summattu xP-lukuun. -->
			<h3>Past the projection horizon</h3>
			<!-- 🔴 `plan.long_view.note` EI renderoidy: se oli kolmas kopio
			     samasta varauksesta samassa nakymassa. Varaus on nyt tasan
			     yhdessa paikassa, ja se paikka on LUVUN ALLA muutama rivi
			     alempana — EI MethodNotessa, joka on suljettu <details>. -->
			<p class="line">{reason('long_view')}</p>
			<!-- 🔴 VARAUS TASSA, EI MethodNotessa. `MethodNote` on <details>
			     ilman `open`-attribuuttia, eli se on oletuksena KIINNI. Varaus
			     suljetun lohkon takana samalla kun luku on nakyvissa on sama
			     asia kuin ei varausta. -->
			<p class="muted small">
				Different basis from xP, so it sits beside that number and is never added to it.
			</p>
		{/if}

		{#if plan.candidates?.length}
			<h3>Every switch point</h3>
			<table class="cands">
				<thead>
					<tr><th>GW</th><th>Gain</th><th>Per GW</th><th>Rounds</th></tr>
				</thead>
				<tbody>
					{#each plan.candidates as c (c.gw)}
						<tr class:best={c.gw === plan.gw}>
							<td>GW{c.gw}</td>
							<td>{c.ev_total.toFixed(2)}</td>
							<td>{c.ev_per_gw.toFixed(2)}</td>
							<td>{c.window_gws}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}

		{#if data?.meta?.masked}
			<p class="muted small">{data.meta.mask}</p>
		{/if}

		<MethodNote summary="How the wildcard call is made (and its limits)">
			<ul>
				{#each data?.meta?.notes ?? [] as n (n)}
					<li>{n}</li>
				{/each}
			</ul>
		</MethodNote>
	{/if}
</section>

<style>
	.wrap {
		margin: 18px 0;
	}
	h2 {
		font-size: 1.05rem;
		margin: 0 0 10px;
	}
	h3 {
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.7;
		margin: 18px 0 6px;
	}
	.cost {
		margin: 0 0 8px;
		font-weight: 600;
	}
	.verdict {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 8px 10px;
		border: 1px solid currentColor;
	}
	.verdict.go {
		color: var(--ok, #2e7d32);
	}
	.verdict.hold {
		color: var(--text-muted);
	}
	.verdict .lbl {
		font-weight: 700;
		flex: 1;
	}
	.verdict .num {
		font-size: 1.3rem;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}
	.verdict .unit {
		font-size: 0.75rem;
		opacity: 0.8;
	}
	.line {
		margin: 8px 0 0;
		font-size: 0.92rem;
		line-height: 1.5;
	}
	.caveat {
		margin: 8px 0 0;
		padding-left: 10px;
		border-left: 2px solid currentColor;
		font-size: 0.85rem;
		line-height: 1.5;
		opacity: 0.85;
	}
	.swap {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 14px;
	}
	@media (max-width: 520px) {
		.swap {
			grid-template-columns: 1fr;
		}
	}
	.swap ul,
	.squad {
		list-style: none;
		margin: 4px 0 0;
		padding: 0;
		font-size: 0.9rem;
	}
	.swap li,
	.squad li {
		display: flex;
		align-items: baseline;
		gap: 6px;
		padding: 3px 0;
		border-top: 1px solid rgba(128, 128, 128, 0.2);
	}
	.swap .muted,
	.squad .muted {
		flex: 1;
	}
	.xp {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	.bench {
		opacity: 0.75;
	}
	.lbl {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.65;
	}
	.cands {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.88rem;
		font-variant-numeric: tabular-nums;
	}
	.cands th,
	.cands td {
		text-align: right;
		padding: 3px 6px;
		border-top: 1px solid rgba(128, 128, 128, 0.2);
	}
	.cands th:first-child,
	.cands td:first-child {
		text-align: left;
	}
	.cands tr.best {
		font-weight: 700;
	}
	.muted {
		opacity: 0.7;
	}
	.small {
		font-size: 0.78rem;
	}
</style>
