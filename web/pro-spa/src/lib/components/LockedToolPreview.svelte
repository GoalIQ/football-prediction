<script lang="ts">
	/**
	 * Lukitun premium-tyokalun nakyma ei-maksajalle (22.9, web-audit T3).
	 *
	 * YKSI KOMPONENTTI kaikille premium-tyokaluille, ei jokaiselle omaa:
	 * ToolsHome valitsee taman `lockedToolFor`-lukijalla ($lib/lockPreview),
	 * joten uusi premium-tyokalu saa naytteen ja hinnan ilman omaa haaraa.
	 * Ennen tata kuusi yhdeksasta premium-URLista avasi ei-maksajalle tyhjan
	 * nakyman ja kolme tekstilaatikon ilman yhtaan rivia.
	 *
	 * Malli on `/ucl`:n: palvelimen ilmainen naytte, sumennettu loppu, hinta
	 * ja ostonappi SAMASSA laatikossa. Kauppanappi on toissijainen linkki
	 * ostonappien jalkeen, koska se katkaisee webin attribuution.
	 *
	 * Asettelu ei hyppaa datan saapuessa: taulukko renderoidaan heti oikealla
	 * rivimaaralla tyhjina riveina (ei keksittyja lukuja, sama periaate kuin
	 * app.html:n boot-rungossa), ja ostolaatikko on sen alla samalla kohdalla
	 * ennen ja jalkeen haun. Vrt. T1: /spl:n CLS 0,65-0,74 syntyi juuri
	 * nakyvissa olevan sisallon siirtymisesta datan saapuessa.
	 */
	import { onMount } from 'svelte';
	import { fetchXp, type XpResponse } from '$lib/api';
	import { capture } from '$lib/analytics';
	import { PLANS, planApprox, startCheckout, type PlanKey } from '$lib/billing';
	import { loadPricing, planLabel, showApprox } from '$lib/pricing.svelte';
	import { preferredStore, appCtaLabel, STORE_URL, type AppStore } from '$lib/appHandoff';
	import { actionableGameweek } from '$lib/gameweek';
	import { xpHorizon } from '$lib/xpHorizon';
	import { PREVIEW_ROWS, gwCell, previewRows, valueCell } from '$lib/lockPreview';
	import { findTool, type Tool } from '$lib/tools';

	let { tool, onUpgrade }: { tool: Tool; onUpgrade: () => void } = $props();

	let xp = $state<XpResponse | null>(null);
	let failed = $state(false);
	let busy = $state<PlanKey | null>(null);
	let buyError = $state<string | null>(null);
	let appStore = $state<AppStore | null>(null);

	onMount(() => {
		void loadPricing();
		// Sama funneli-event kuin Paywall ja PremiumPreview; source erottaa
		// tyokalun lukon upgrade-nakymasta, tool kertoo mika lukko.
		capture(
			'paywall_shown',
			{ source: 'pro_web_tool_lock', tool: tool.slug },
			`paywall_shown_lock_${tool.slug}`
		);
		// `navigator` vasta mountissa (ei prerenderissa), kuten PremiumPreview.
		appStore = preferredStore(navigator?.userAgent);
		// Sama moduulitason cache kuin ToolsHomen xP-haulla: kirjautuneelle
		// tama on jo matkalla, kirjautumattomalle palvelin antaa maskatun
		// kymmenikon (`mask_xp_payload`).
		fetchXp().then(
			(d) => (xp = d),
			() => (failed = true)
		);
	});

	const rows = $derived(previewRows(xp));
	// Naytteen lahde nimetaan rekisterista (sama nimi kuin navissa).
	const SOURCE_TOOL = findTool('players', 'player-xp')?.title ?? 'Player xP';
	const gw = $derived(actionableGameweek(xp?.meta));
	const hz = $derived(xpHorizon(xp?.meta));
	/** Tyhjat rivit haun ajaksi, jotta ostolaatikko ei siirry kun data tulee. */
	const loading = $derived(!xp && !failed);
	const noData = $derived(!loading && rows.length === 0);

	async function buy(plan: PlanKey) {
		busy = plan;
		buyError = await startCheckout(plan, `pro_web_lock_${tool.slug}`);
		busy = null;
	}
</script>

<section class="lock" aria-labelledby="lock-title">
	<h1 id="lock-title">{tool.title}</h1>
	<p class="question">{tool.question}</p>

	<div class="lock-card">
		{#if failed}
			<p class="muted no-data">Could not load xP projections right now. Please try again shortly.</p>
		{:else if noData}
			<p class="muted no-data">xP projections are not available for this gameweek yet.</p>
		{:else}
			<!-- 22.9 (julkaisutarkistaja): tagi nimeaa datan lahteen. Nayte on
			     Player xP -listaa, ei lukitun tyokalun omaa dataa (esim. Captain
			     ranker jarjestaa seuraavan GW:n mukaan). -->
			<p class="tag">Free from {SOURCE_TOOL}: top {rows.length || PREVIEW_ROWS}</p>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th class="num">#</th>
							<th>Player</th>
							<th class="num"
								><abbr title="Expected points from the GoalIQ match model"
									>GW{gw ?? ''}</abbr
								></th
							>
							<th class="num"><abbr title={hz.totalTitle}>Total</abbr></th>
						</tr>
					</thead>
					<tbody>
						{#if loading}
							{#each Array.from({ length: PREVIEW_ROWS }, (_, i) => i) as i (i)}
								<tr class="pending" aria-hidden="true">
									<td class="num">&nbsp;</td><td>&nbsp;</td><td class="num">&nbsp;</td><td
										class="num">&nbsp;</td
									>
								</tr>
							{/each}
						{:else}
							{#each rows as p, i (p.id)}
								<tr data-player-id={p.id}>
									<td class="num">{i + 1}</td>
									<td class="player">{p.web_name} <span class="muted">{p.team_short}, {p.pos}</span></td>
									<td class="num">{gwCell(p, gw)}</td>
									<td class="num strong">{valueCell(p.xp_horizon_total)}</td>
								</tr>
							{/each}
						{/if}
					</tbody>
				</table>
			</div>
			<!-- Sumennettu loppu: palkkeja, ei nimia eika lukuja. Palvelin ei anna
			     loppuja riveja ei-maksajalle, joten niita ei myoskaan esiteta. -->
			<div class="ghost" aria-hidden="true">
				{#each [0, 1] as g (g)}
					<div class="ghost-row"><i></i><i></i><i></i></div>
				{/each}
			</div>
		{/if}

		<div class="buy">
			<p class="buy-head"><strong>{tool.title}</strong> is part of GoalIQ Premium.</p>
			<div class="plans">
				{#each Object.entries(PLANS) as [key, plan] (key)}
					{@const approx = showApprox(key as PlanKey) ? planApprox(key as PlanKey) : null}
					<!-- Nappi ennen vihjetta: mitattu 390x844, vihje napin ylapuolella
					     vei ensimmaisen ostonapin ruudun alle Players-ryhmassa. -->
					<div class="plan">
						<button
							type="button"
							class={key === 'season' ? 'primary' : 'secondary'}
							disabled={busy !== null}
							onclick={() => void buy(key as PlanKey)}
						>
							{busy === key ? 'Opening checkout…' : `Get Premium: ${planLabel(key as PlanKey)}`}
						</button>
						<span class="muted">{plan.hint}{approx ? ` · ${approx}` : ''}</span>
					</div>
				{/each}
			</div>
			{#if buyError}
				<p class="banner error">{buyError}</p>
			{/if}
			<p class="muted small">
				Already subscribed in the GoalIQ app? Sign in with the same account and Premium is already
				active here.
			</p>
			<p class="more">
				<button type="button" class="linkish" onclick={onUpgrade}>See Premium</button>
				{#if appStore}
					<a
						class="app-link"
						href={STORE_URL[appStore]}
						rel="noopener"
						onclick={() => capture('app_handoff_tapped', { store: appStore, source: 'tool_lock' })}
						>{appCtaLabel(appStore)}</a
					>
				{/if}
			</p>
		</div>
	</div>
</section>

<style>
	.lock h1 {
		margin: 0 0 var(--s-1);
		font-size: var(--step-2);
		line-height: 1.15;
	}
	.question {
		margin: 0 0 var(--s-3);
		color: var(--text-muted);
		max-width: 60ch;
	}
	/* Nayte + hinta + ostonappi yhtena laatikkona (T3: "samassa laatikossa"). */
	.lock-card {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		padding: var(--s-3);
		margin-bottom: var(--s-4);
	}
	.tag {
		margin: 0 0 var(--s-2);
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	.lock-card table td.strong {
		font-weight: 700;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	/* Tyhja rivi haun ajan: sama korkeus kuin tekstirivilla (&nbsp;). Nimi
	   ei rivity (theme.css sallii rivityksen kapealla), jotta tayttynyt rivi
	   on yhta korkea kuin tyhja eika ostolaatikko siirry datan tullessa. */
	tr.pending td {
		color: transparent;
	}
	td.player {
		white-space: nowrap;
	}
	.ghost {
		display: grid;
		gap: 10px;
		padding: var(--s-2) var(--s-2) 0;
		filter: blur(2px);
		opacity: 0.55;
		-webkit-mask-image: linear-gradient(to bottom, #000 0%, transparent 100%);
		mask-image: linear-gradient(to bottom, #000 0%, transparent 100%);
	}
	.ghost-row {
		display: grid;
		grid-template-columns: 1fr 3.5rem 3.5rem;
		gap: var(--s-3);
	}
	.ghost-row i {
		display: block;
		height: 10px;
		background: var(--border-strong);
	}
	.no-data {
		margin: 0 0 var(--s-3);
	}
	.buy {
		border-top: 1px solid var(--border);
		margin-top: var(--s-3);
		padding-top: var(--s-3);
	}
	.buy-head {
		margin: 0 0 var(--s-2);
	}
	/* align-items: flex-start, muuten lyhyemman vihjeen sarake venyy ja
	   sen nappi kasvaa korkeammaksi kuin viereinen (mitattu 1280 px). */
	.plans {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		gap: var(--s-4);
	}
	.plan {
		display: grid;
		gap: var(--s-1);
		justify-items: start;
		align-content: start;
		max-width: 22rem;
	}
	.buy > .small {
		margin: var(--s-3) 0 0;
	}
	/* Jarjestysnumero kapeaksi myos leveassa taulukossa. */
	.lock-card th:first-child,
	.lock-card td:first-child {
		width: 3ch;
	}
	.more {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-2) var(--s-4);
		margin: var(--s-2) 0 0;
	}
	/* Toissijaiset: tekstin nakoisia, eivat kilpaile ostonappien kanssa. */
	.linkish {
		background: none;
		border: none;
		min-height: 44px;
		padding: 0;
		color: var(--text);
		font: inherit;
		font-weight: 600;
		text-decoration: underline;
		text-underline-offset: 3px;
		cursor: pointer;
	}
	.app-link {
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	.small {
		font-size: 0.85em;
	}
</style>
