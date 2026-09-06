<script lang="ts">
	/**
	 * ProjectionsPanel (6.9, Villen tilaus Solio-kuvan perusteella) — kompakti
	 * projektiotaulukko oman kentan VIEREEN: nimi, seura, hinta, Avg ja
	 * kierrossarakkeet lampokartalla. Oma runko korostettuna, jotta silma
	 * loytaa omat pelaajat listasta ilman hakua.
	 *
	 * Presentationaalinen: saa saman XpResponse-datan jonka ToolsHome hakee
	 * (ei uutta kutsua), ja lukee kierroksen xP:n samasta `gwXp`-lukijasta
	 * kuin XpTable ja jakokortit. Sortti klikkaamalla otsikkoa; oletus Avg
	 * (xp_per_gw) laskevaan, tasapeli horisontin summa.
	 *
	 * Maskattu vastaus (free): backend antaa 10 rivia ja meta.masked; paneeli
	 * nayttaa ne ja sanoo etta koko lista on Premiumia. Ei omaa gatea.
	 */
	import type { XpResponse, XpPlayer } from '$lib/api';
	import { gwXp } from '$lib/api';

	let {
		data,
		ownIds = new Set<number>(),
		onUpgrade,
		defaultGw = null
	}: {
		data: XpResponse;
		/** Oman rungon pelaaja-id:t (korostus). */
		ownIds?: Set<number>;
		onUpgrade?: () => void;
		/** Naytettava kierros kentalla; sarake korostetaan. */
		defaultGw?: number | null;
	} = $props();

	const POSITIONS = ['All', 'GKP', 'DEF', 'MID', 'FWD'] as const;
	let pos = $state<(typeof POSITIONS)[number]>('All');
	let search = $state('');
	let sortKey = $state<string>('avg');
	let sortDesc = $state(true);
	let showAll = $state(false);
	let ownOnly = $state(false);
	// Koko lista rullaa paneelin sisalla (6.9): ei katkaisua.
	const COLLAPSED = 1000;

	const gwCols = $derived(data.players[0]?.gameweeks?.map((g) => g.gw) ?? []);
	const masked = $derived(!!data.meta?.masked);

	function normSearch(s: string): string {
		return s
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase()
			.replace(/['’ʼ]/g, '')
			.replace(/[-.]/g, ' ')
			.replace(/\s+/g, ' ')
			.trim();
	}
	function valueOf(p: XpPlayer, key: string): number {
		if (key === 'avg') return p.xp_per_gw;
		if (key === 'price') return p.price ?? -1;
		if (key === 'total') return p.xp_horizon_total;
		const m = /^gw(\d+)$/.exec(key);
		return m ? gwXp(p, Number(m[1])) : p.xp_per_gw;
	}
	function sortBy(key: string) {
		if (sortKey === key) sortDesc = !sortDesc;
		else {
			sortKey = key;
			sortDesc = key !== 'price';
		}
	}
	const rows = $derived.by(() => {
		const q = normSearch(search);
		const dir = sortDesc ? -1 : 1;
		return data.players
			.filter((p) => pos === 'All' || p.pos === pos)
			.filter((p) => !ownOnly || ownIds.has(p.id))
			.filter((p) => !q || normSearch(p.web_name).includes(q) || normSearch(p.team_short).includes(q))
			.slice()
			.sort(
				(a, b) =>
					dir * (valueOf(a, sortKey) - valueOf(b, sortKey)) ||
					b.xp_horizon_total - a.xp_horizon_total ||
					a.id - b.id
			);
	});
	const visible = $derived(showAll ? rows : rows.slice(0, COLLAPSED));
	// Lampokartta: skaala nakyvien rivien kierrosluvuista, ei koko poolista,
	// jotta suodatettu lista ei ole yksivarinen.
	const heatMax = $derived.by(() => {
		let m = 0;
		for (const p of visible) for (const g of gwCols) m = Math.max(m, gwXp(p, g));
		return m;
	});
	function heat(v: number): string {
		if (!heatMax || v <= 0) return '';
		const t = Math.min(1, v / heatMax);
		return `background-color: rgba(245,197,66,${(t * 0.32).toFixed(3)})`;
	}
	const hasPrice = $derived(data.players.some((p) => typeof p.price === 'number'));
</script>

<div class="panel" class:short={masked}>
	<div class="head">
		<p class="label">Projections</p>
		<span class="muted small">xP per gameweek, GoalIQ model</span>
	</div>
	<div class="controls">
		{#each POSITIONS as pp (pp)}
			<button type="button" class="chip" class:on={pos === pp} onclick={() => (pos = pp)}>{pp}</button>
		{/each}
		{#if ownIds.size > 0}
			<button type="button" class="chip" class:on={ownOnly} onclick={() => (ownOnly = !ownOnly)}
				>My squad</button
			>
		{/if}
		<input type="search" placeholder="Search" bind:value={search} aria-label="Search players" />
	</div>
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>Player</th>
					{#if hasPrice}
						<th class="num m-hide">
							<button type="button" class="sortbtn" onclick={() => sortBy('price')}>Price</button>
						</th>
					{/if}
					<th class="num avg" class:sortcol={sortKey === 'avg'}>
						<button type="button" class="sortbtn" onclick={() => sortBy('avg')}
							><abbr title="Average expected points per gameweek over the model horizon">Avg</abbr
							>{#if sortKey === 'avg'}<span class="dir">{sortDesc ? '↓' : '↑'}</span>{/if}</button
						>
					</th>
					{#each gwCols as gw (gw)}
						<th class="num" class:sortcol={sortKey === `gw${gw}`} class:cur={gw === defaultGw}>
							<button type="button" class="sortbtn" onclick={() => sortBy(`gw${gw}`)}
								>GW{gw}{#if sortKey === `gw${gw}`}<span class="dir">{sortDesc ? '↓' : '↑'}</span
									>{/if}</button
							>
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each visible as p (p.id)}
					<tr class:own={ownIds.has(p.id)}>
						<td class="name">
							{p.web_name}
							<span class="team muted">{p.team_short}</span>
							{#if ownIds.has(p.id)}<span class="own-dot" title="In your squad">●</span>{/if}
						</td>
						{#if hasPrice}
							<td class="num m-hide">{typeof p.price === 'number' ? p.price.toFixed(1) : '-'}</td>
						{/if}
						<td class="num avg" class:sortcol={sortKey === 'avg'}>{p.xp_per_gw.toFixed(2)}</td>
						{#each gwCols as gw (gw)}
							<td
								class="num"
								class:sortcol={sortKey === `gw${gw}`}
								class:cur={gw === defaultGw}
								style={heat(gwXp(p, gw))}>{gwXp(p, gw).toFixed(2)}</td
							>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if !showAll && rows.length > COLLAPSED}
		<button type="button" class="chip more" onclick={() => (showAll = true)}>Show all {rows.length}</button>
	{/if}
	{#if masked}
		<p class="muted small lock">
			Free preview: the top {data.players.length} by horizon xP. The full projection for every player
			is part of GoalIQ Premium.
			{#if onUpgrade}<button type="button" class="linkbtn" onclick={onUpgrade}>See Premium</button>{/if}
		</p>
	{/if}
</div>

<style>
	/* 6.9 (Villen tarkennus): paneeli on sarakkeen korkuinen ja taulukko
	   rullaa sen sisalla, jotta se asettuu kentan viereen Solion tapaan. */
	.panel {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		padding: var(--s-3);
		min-width: 0;
		height: 100%;
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
	}
	/* Maskattu 10 rivin esikatselu ei venytetä paneelia sarakkeen korkuiseksi:
	   tyhja laatikko lukisi rikkinaiselta. */
	.panel.short {
		height: auto;
	}
	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--s-2);
		flex-wrap: wrap;
		margin-bottom: var(--s-2);
	}
	.label {
		margin: 0;
		font-size: var(--step--1);
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.small {
		font-size: var(--step--1);
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		margin-bottom: var(--s-2);
	}
	.controls input {
		flex: 1 1 110px;
		min-width: 90px;
		font: inherit;
		font-size: var(--step--1);
		padding: 4px 8px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--bg);
		color: inherit;
	}
	.chip {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text-muted);
		font-weight: 700;
		font-size: var(--step--1);
		padding: 3px 9px;
		cursor: pointer;
	}
	.chip.on {
		background: transparent;
		border-color: var(--accent);
		color: var(--accent-strong);
	}
	.chip.more {
		margin-top: var(--s-2);
	}
	.table-wrap {
		flex: 1 1 auto;
		min-height: 0;
		max-height: 70vh;
		overflow: auto;
	}
	@media (min-width: 1280px) {
		.table-wrap {
			max-height: none;
		}
	}
	table {
		font-size: var(--step--1);
		width: 100%;
	}
	thead th {
		position: sticky;
		top: 0;
		background: var(--surface);
		z-index: 1;
	}
	td,
	th {
		padding: 5px 4px;
		white-space: nowrap;
	}
	td.name {
		font-weight: 700;
		max-width: 142px;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.team {
		font-size: 0.8em;
		font-weight: 400;
		margin-left: 4px;
	}
	.own td {
		background: rgba(46, 214, 194, 0.08);
	}
	.own td.name {
		color: var(--teal, #2ed6c2);
	}
	.own-dot {
		color: var(--teal, #2ed6c2);
		font-size: 0.7em;
		margin-left: 4px;
	}
	.sortbtn {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		cursor: pointer;
	}
	.sortbtn abbr {
		text-decoration: none;
	}
	.dir {
		margin-left: 2px;
		font-size: 0.8em;
	}
	.sortcol {
		background: color-mix(in srgb, var(--accent) 12%, transparent);
	}
	th.cur,
	td.cur {
		box-shadow: inset 2px 0 0 var(--teal, #2ed6c2);
	}
	td.avg {
		font-weight: 700;
	}
	.lock {
		margin: var(--s-2) 0 0;
	}
	.linkbtn {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: var(--accent-strong);
		cursor: pointer;
		text-decoration: underline;
	}
</style>
