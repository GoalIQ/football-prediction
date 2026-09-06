<script lang="ts">
	/**
	 * Stats (6.9, Villen tilaus) — FPL:n omat pelaajatilastot ja GoalIQ:n
	 * deadline-freezen xP samalla rivilla, ikkunoitavissa kierroksittain.
	 *
	 * Kysymys johon tama vastaa: "mita pelaaja sai OIKEASTI, ja mita malli
	 * odotti ennen deadlinea". Vertailukohta on immutable freeze, ei elava
	 * projektio (22.8-oppi rate-teamissa: elava luku liikkuu kohti toteumaa).
	 *
	 * Raja (Villen paatos 8.8): raakaluvut ovat ilmaisia, malli maksaa.
	 * Menneiden kierrosten freeze-vertailu on julkista track recordia ja
	 * nakyy kaikille. Vain eteenpain katsova xP (seuraava kierros, horisontti)
	 * on premiumin takana, ja backend maskaa sen (meta.masked).
	 *
	 * Data-rajoitukset ensiluokkaisena: basis-kausi, ikkuna ja vertaillut
	 * kierrokset lukevat aina otsikon alla. FPL:n xG on Optan luku, ei meidan.
	 */
	import { capture } from '$lib/analytics';
	import {
		fetchPlayerStats,
		type PlayerStatsResponse,
		type PlayerStatsRow,
		type PlayerStatsWindow
	} from '$lib/fantasyTools';
	import { canShareToApps, shareCard, shareButtonLabel } from '$lib/shareCard';

	let { premium = false, onUpgrade }: { premium?: boolean; onUpgrade?: () => void } = $props();

	const WINDOWS: { key: PlayerStatsWindow; label: string }[] = [
		{ key: 'season', label: 'Season' },
		{ key: 'last3', label: 'Last 3' },
		{ key: 'last5', label: 'Last 5' },
		{ key: 'last10', label: 'Last 10' }
	];
	const POSITIONS = ['', 'GKP', 'DEF', 'MID', 'FWD'] as const;

	/** Sarakeryhmat. Avain = sortti-avain, `get` = rivin luku, `fmt` = esitys.
	 *  Yksi lukija: sama `get` jarjestaa, renderoi solun ja tulostaa kortin. */
	type Col = {
		key: string;
		label: string;
		title: string;
		get: (p: PlayerStatsRow) => number | null;
		digits?: number;
		signed?: boolean;
		premium?: boolean;
	};
	const num = (v: number | null | undefined) => (typeof v === 'number' ? v : null);
	const GROUPS: { id: string; label: string; cols: Col[] }[] = [
		{
			id: 'key',
			label: 'Key',
			cols: [
				{ key: 'pts', label: 'Pts', title: 'FPL points in the window', get: (p) => num(p.fpl.pts) },
				{ key: 'ppg', label: 'PPG', title: 'Points per gameweek played in the window', get: (p) => num(p.fpl.ppg), digits: 1 },
				{ key: 'mins', label: 'Mins', title: 'Minutes played', get: (p) => num(p.fpl.mins) },
				{ key: 'starts', label: 'Starts', title: 'Starts', get: (p) => num(p.fpl.starts) },
				{ key: 'g', label: 'G', title: 'Goals', get: (p) => num(p.fpl.g) },
				{ key: 'a', label: 'A', title: 'Assists', get: (p) => num(p.fpl.a) },
				{ key: 'xgi', label: 'xGI', title: 'Expected goal involvements (FPL, Opta)', get: (p) => num(p.fpl.xgi), digits: 2 },
				{ key: 'bonus', label: 'Bonus', title: 'Bonus points', get: (p) => num(p.fpl.bonus) }
			]
		},
		{
			id: 'attack',
			label: 'Attack',
			cols: [
				{ key: 'g', label: 'G', title: 'Goals', get: (p) => num(p.fpl.g) },
				{ key: 'xg', label: 'xG', title: 'Expected goals (FPL, Opta)', get: (p) => num(p.fpl.xg), digits: 2 },
				{ key: 'a', label: 'A', title: 'Assists', get: (p) => num(p.fpl.a) },
				{ key: 'xa', label: 'xA', title: 'Expected assists (FPL, Opta)', get: (p) => num(p.fpl.xa), digits: 2 },
				{ key: 'xgi', label: 'xGI', title: 'Expected goal involvements (FPL, Opta)', get: (p) => num(p.fpl.xgi), digits: 2 },
				{ key: 'ict', label: 'ICT', title: 'FPL ICT index', get: (p) => num(p.fpl.ict), digits: 1 },
				{ key: 'bps', label: 'BPS', title: 'Bonus points system score', get: (p) => num(p.fpl.bps) },
				{ key: 'bonus', label: 'Bonus', title: 'Bonus points', get: (p) => num(p.fpl.bonus) }
			]
		},
		{
			id: 'defence',
			label: 'Defence',
			cols: [
				{ key: 'cs', label: 'CS', title: 'Clean sheets', get: (p) => num(p.fpl.cs) },
				{ key: 'gc', label: 'GC', title: 'Goals conceded', get: (p) => num(p.fpl.gc) },
				{ key: 'xgc', label: 'xGC', title: 'Expected goals conceded (FPL, Opta)', get: (p) => num(p.fpl.xgc), digits: 2 },
				{ key: 'saves', label: 'Saves', title: 'Saves', get: (p) => num(p.fpl.saves) },
				{ key: 'dc', label: 'DC', title: 'Defensive contribution (FPL count)', get: (p) => num(p.fpl.dc) },
				{ key: 'tkl', label: 'Tkl', title: 'Tackles', get: (p) => num(p.fpl.tkl) },
				{ key: 'cbi', label: 'CBI', title: 'Clearances, blocks and interceptions', get: (p) => num(p.fpl.cbi) },
				{ key: 'rec', label: 'Rec', title: 'Recoveries', get: (p) => num(p.fpl.rec) }
			]
		},
		{
			id: 'model',
			label: 'vs model',
			cols: [
				{ key: 'pts_compared', label: 'Pts', title: 'FPL points on the compared gameweeks (those with a deadline freeze)', get: (p) => num(p.goaliq.pts_compared) },
				{ key: 'xp_frozen', label: 'xP', title: 'GoalIQ expected points, frozen before each deadline, same gameweeks', get: (p) => num(p.goaliq.xp_frozen), digits: 1 },
				{ key: 'diff', label: 'Diff', title: 'Points minus frozen xP. Positive = beat the model', get: (p) => num(p.goaliq.diff), digits: 1, signed: true },
				{ key: 'n_compared', label: 'GWs', title: 'Gameweeks compared', get: (p) => num(p.goaliq.n_compared) },
				{ key: 'next_gw_xp', label: 'Next xP', title: 'GoalIQ expected points for the next gameweek (Premium)', get: (p) => num(p.goaliq.next_gw_xp), digits: 1, premium: true },
				{ key: 'xp_horizon_total', label: 'Horizon xP', title: 'GoalIQ expected points over the model horizon (Premium)', get: (p) => num(p.goaliq.xp_horizon_total), digits: 1, premium: true }
			]
		}
	];

	let data = $state<PlayerStatsResponse | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let win = $state<PlayerStatsWindow>('season');
	let group = $state<string>('key');
	let posFilter = $state<string>('');
	let teamFilter = $state('');
	let search = $state('');
	let sortKey = $state<string>('pts');
	let sortDesc = $state(true);
	let showAll = $state(false);
	let expanded = $state<number | null>(null);
	let sharing = $state(false);
	const COLLAPSED_ROWS = 25;

	// Ikkunan vaihto hakee uudelleen: aggregaatti lasketaan backendissa
	// riveista, jotta season ja lastN ovat samasta lahteesta.
	$effect(() => {
		const w = win;
		loading = true;
		error = null;
		fetchPlayerStats(w)
			.then((d) => {
				data = d;
				capture('player_stats_viewed', { window: w });
			})
			.catch((e) => (error = e instanceof Error ? e.message : String(e)))
			.finally(() => (loading = false));
	});

	const activeGroup = $derived(GROUPS.find((g) => g.id === group) ?? GROUPS[0]);
	const allCols = $derived(GROUPS.flatMap((g) => g.cols));
	const sortCol = $derived(allCols.find((c) => c.key === sortKey) ?? GROUPS[0].cols[0]);
	const rows = $derived(data?.players ?? []);
	const teams = $derived([...new Set(rows.map((p) => p.team_short))].sort());
	const masked = $derived(!!data?.meta?.masked);
	/** Vertaillut kierrokset joukkona: nauhan "beat"-vari vain naille, ei
	 *  kesken olevalle kierrokselle (portti 6.9: Mukiele GW3 korostui). */
	const comparedSet = $derived(new Set(data?.meta?.compared_gws ?? []));
	const MODEL_KEYS = new Set(['pts_compared', 'xp_frozen', 'diff', 'n_compared', 'next_gw_xp', 'xp_horizon_total']);
	const CARD_LABEL: Record<string, string> = { pts_compared: 'PTS CMP', xp_frozen: 'XP FROZEN', diff: 'DIFF', n_compared: 'GWS CMP' };

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

	const filtered = $derived.by(() => {
		const q = normSearch(search);
		const v = sortCol.get;
		const dir = sortDesc ? -1 : 1;
		return rows
			.filter((p) => !posFilter || p.pos === posFilter)
			.filter((p) => !teamFilter || p.team_short === teamFilter)
			.filter((p) => !q || normSearch(p.web_name).includes(q) || normSearch(p.team_short).includes(q))
			.slice()
			.sort((a, b) => {
				const av = v(a);
				const bv = v(b);
				// Puuttuva luku hantaan kumpaankin suuntaan: null ei ole nolla.
				if (av == null && bv == null) return (b.fpl.pts ?? 0) - (a.fpl.pts ?? 0);
				if (av == null) return 1;
				if (bv == null) return -1;
				return dir * (av - bv) || (b.fpl.pts ?? 0) - (a.fpl.pts ?? 0) || a.id - b.id;
			});
	});
	const visible = $derived(showAll ? filtered : filtered.slice(0, COLLAPSED_ROWS));

	function sortBy(key: string) {
		if (sortKey === key) sortDesc = !sortDesc;
		else {
			sortKey = key;
			sortDesc = true;
		}
		pickGroupForSort(key);
	}
	/** Ryhman vaihto: jos sortti ei ole ryhmassa, sortti ryhman 1. sarakkeeseen,
	 *  jotta jarjestys on aina nakyvissa. (Ensimmainen versio teki taman
	 *  efektina joka luki myos `group`in ja palautti ryhman heti takaisin.) */
	function setGroup(id: string) {
		group = id;
		const g = GROUPS.find((gr) => gr.id === id);
		if (g && !g.cols.some((c) => c.key === sortKey)) {
			sortKey = g.cols[0].key;
			sortDesc = true;
		}
	}
	function fmt(c: Col, v: number | null): string {
		if (v == null) return '-';
		const s = v.toFixed(c.digits ?? 0);
		return c.signed && v > 0 ? `+${s}` : s;
	}
	function pickGroupForSort(key: string) {
		// Sortti sarakkeella joka ei ole nakyvassa ryhmassa vaihtaa ryhman,
		// muuten jarjestys olisi lukijalle nakymaton.
		const g = GROUPS.find((gr) => gr.cols.some((c) => c.key === key));
		if (g && g.id !== group) group = g.id;
	}

	const windowText = $derived.by(() => {
		const w = data?.meta?.window;
		if (!w) return '';
		return w.kind === 'season' ? `GW${w.from}-GW${w.to}, season to date` : `GW${w.from}-GW${w.to}, last ${w.n}`;
	});
	const comparedText = $derived.by(() => {
		const c = data?.meta?.compared_gws ?? [];
		if (c.length === 0) return 'No finished gameweek with a deadline freeze yet, so the model columns are empty.';
		return `Model columns compare GW${c[0]}-GW${c[c.length - 1]}: finished gameweeks with a deadline freeze. Per player only the gameweeks with both a freeze and an FPL row count, so GWs can be lower than that span.`;
	});

	async function share() {
		if (sharing || visible.length === 0) return;
		sharing = true;
		try {
			// Portti 6.9: mallisorteilla ikkuna on VERTAILLUT kierrokset, ei
			// tilastoikkuna, ja PTS-sarake ei saa toistua kahdella nimella.
			const c = data?.meta?.compared_gws ?? [];
			const modelSort = MODEL_KEYS.has(sortCol.key);
			const cmpSpan = c.length ? `GW${c[0]}-GW${c[c.length - 1]} compared` : 'no gameweek compared yet';
			const sub = [
				modelSort ? cmpSpan : windowText,
				`by ${CARD_LABEL[sortCol.key] ?? sortCol.label}`,
				...(posFilter ? [posFilter] : []),
				...(teamFilter ? [teamFilter] : [])
			].join(', ');
			const method = await shareCard({
				title: 'PLAYER STATS TOP 10',
				subtitle: `${sub}, FPL data`,
				midLabel: 'PTS',
				valueLabel: CARD_LABEL[sortCol.key] ?? sortCol.label.toUpperCase(),
				fileName: 'goaliq_player_stats.png',
				footNote: modelSort
					? 'PTS = window points from the official FPL API, model columns on compared gameweeks only'
					: 'From the official FPL API',
				rows: visible.slice(0, 10).map((p, i) => ({
					rank: i + 1,
					name: p.web_name,
					tag: p.pos,
					team: p.team_short,
					mid: String(p.fpl.pts ?? '-'),
					value: fmt(sortCol, sortCol.get(p))
				}))
			});
			if (method !== 'aborted') capture('player_stats_shared', { method, sort: sortKey });
		} finally {
			sharing = false;
		}
	}
</script>

<div class="head-row">
	<h2>Player stats</h2>
	{#if canShareToApps() || visible.length > 0}
		<button type="button" class="share" onclick={share} disabled={sharing || visible.length === 0}>
			{sharing ? 'Preparing…' : shareButtonLabel()}
		</button>
	{/if}
</div>
<p class="muted lede">
	What each player actually scored, next to what the GoalIQ model expected before each deadline.
	FPL numbers come from the official FPL API (xG, xA, xGI and xGC are FPL's Opta figures). A
	player with no gameweek row yet is not in the table. xP is the deadline freeze, never the live
	projection.
</p>

<div class="window-row">
	<span class="muted">Window:</span>
	{#each WINDOWS as w (w.key)}
		<button type="button" class="window-chip" class:on={win === w.key} onclick={() => (win = w.key)}
			>{w.label}</button
		>
	{/each}
	<span class="muted">Columns:</span>
	{#each GROUPS as g (g.id)}
		<button type="button" class="window-chip" class:on={group === g.id} onclick={() => setGroup(g.id)}
			>{g.label}</button
		>
	{/each}
</div>
<div class="window-row">
	<span class="muted">Pos:</span>
	{#each POSITIONS as pp (pp)}
		<button type="button" class="window-chip" class:on={posFilter === pp} onclick={() => (posFilter = pp)}
			>{pp === '' ? 'All' : pp}</button
		>
	{/each}
	<select bind:value={teamFilter} aria-label="Filter by team">
		<option value="">All teams</option>
		{#each teams as tt (tt)}<option value={tt}>{tt}</option>{/each}
	</select>
	<input type="search" placeholder="Player or team" bind:value={search} aria-label="Search players" />
</div>

{#if data?.meta}
	<p class="basis">
		{data.meta.basis_season ?? ''}{windowText ? ` · ${windowText}` : ''}. {comparedText}
	</p>
{/if}

{#if loading && !data}
	<p class="muted">Loading player stats…</p>
{:else if error}
	<p class="banner error">{error}</p>
{:else if data && !data.meta.available}
	<p class="banner">{data.meta.reason ?? 'Player stats are not available right now.'}</p>
{:else if filtered.length === 0}
	<p class="muted">No players match.</p>
{:else}
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>#</th>
					<th>Player</th>
					<th class="m-hide">Pos</th>
					<th class="num m-hide"><abbr title="Current FPL price">Price</abbr></th>
					{#each activeGroup.cols as c (c.key)}
						<th class="num" class:sortcol={sortKey === c.key}>
							<button type="button" class="sortbtn" onclick={() => sortBy(c.key)}>
								<abbr title={c.title}>{c.label}</abbr>{#if sortKey === c.key}<span class="dir"
										>{sortDesc ? '↓' : '↑'}</span
									>{/if}
							</button>
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each visible as p, i (p.id)}
					<tr class:open={expanded === p.id}>
						<td>{i + 1}</td>
						<td>
							<button
								type="button"
								class="name-btn"
								onclick={() => (expanded = expanded === p.id ? null : p.id)}
								title="Show the gameweek strip"
							>
								{p.web_name}
								<span class="muted small">{p.team_short}</span>
							</button>
						</td>
						<td class="m-hide">{p.pos}</td>
						<td class="num m-hide">{typeof p.price === 'number' ? p.price.toFixed(1) : '-'}</td>
						{#each activeGroup.cols as c (c.key)}
							<td class="num" class:sortcol={sortKey === c.key}>
								{#if c.premium && masked}
									<span class="muted" title="GoalIQ Premium">🔒</span>
								{:else}
									{fmt(c, c.get(p))}
								{/if}
							</td>
						{/each}
					</tr>
					{#if expanded === p.id}
						<tr class="gw-row">
							<td colspan={4 + activeGroup.cols.length}>
								<div class="gw-strip">
									{#each p.goaliq.gws as g (g.gw)}
										<span class="gw-chip" class:beat={comparedSet.has(g.gw) && g.pts != null && g.xp_frozen != null && g.pts > g.xp_frozen}>
											<span class="gw-n">GW{g.gw}</span>
											<span>{g.pts ?? '-'} pts</span>
											<span class="muted">xP {g.xp_frozen != null ? g.xp_frozen.toFixed(1) : '-'}</span>
										</span>
									{/each}
									{#if p.goaliq.gws.length === 0}
										<span class="muted">No gameweek rows in this window.</span>
									{/if}
								</div>
								<p class="gw-note muted">
									pts = official FPL points for the gameweek. xP = GoalIQ projection frozen before that
									deadline. "-" means no row: the player was not in the freeze or did not have a gameweek
									entry, and that gameweek is not counted in the model columns above. An unfinished gameweek
									shows here but is not compared.
								</p>
							</td>
						</tr>
					{/if}
				{/each}
			</tbody>
		</table>
	</div>
	{#if !showAll && filtered.length > COLLAPSED_ROWS}
		<button type="button" class="window-chip more" onclick={() => (showAll = true)}>
			Show all {filtered.length} players
		</button>
	{/if}
	{#if masked && group === 'model'}
		<div class="locked">
			<p>
				Next-gameweek and horizon xP are part of GoalIQ Premium. The frozen xP and the points on
				the same gameweeks are free for everyone.
			</p>
			{#if onUpgrade}
				<button type="button" class="primary" onclick={onUpgrade}>See Premium</button>
			{/if}
		</div>
	{/if}
	<p class="count muted">
		Showing {visible.length} of {filtered.length} players
		{#if data?.meta?.generated_at}, data from {data.meta.generated_at.slice(0, 10)}{/if}.
	</p>
{/if}

<style>
	.head-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--s-2);
		flex-wrap: wrap;
	}
	.head-row h2 {
		margin: 0;
	}
	.lede {
		margin: var(--s-1) 0 var(--s-3);
		font-size: var(--step--1);
	}
	.window-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-2);
		row-gap: var(--s-2);
		margin: 0 0 var(--s-2);
		font-size: var(--step--1);
	}
	.window-row > span {
		flex: 0 0 auto;
	}
	.window-row input[type='search'] {
		flex: 1 1 140px;
		min-width: 120px;
		font: inherit;
		padding: 4px 8px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: inherit;
	}
	.window-chip {
		flex: 0 0 auto;
		min-width: 36px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text-muted);
		font-weight: 700;
		font-size: var(--step--1);
		padding: 4px 12px;
		cursor: pointer;
		text-align: center;
		white-space: nowrap;
		line-height: 1.4;
	}
	.window-chip.on {
		background: transparent;
		border-color: var(--accent);
		color: var(--accent-strong);
	}
	.window-chip.more {
		margin-top: var(--s-2);
	}
	.basis {
		font-size: var(--step--1);
		margin: 0 0 var(--s-2);
		border-left: 3px solid var(--accent, #f5c542);
		padding-left: var(--s-2);
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
	.name-btn {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: inherit;
		cursor: pointer;
		text-align: left;
	}
	.small {
		font-size: 0.8em;
		margin-left: 4px;
	}
	.gw-row td {
		background: var(--surface, transparent);
	}
	.gw-strip {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		padding: var(--s-2) 0 var(--s-1);
	}
	.gw-chip {
		display: inline-flex;
		align-items: baseline;
		gap: 5px;
		border: 1px solid var(--border);
		padding: 2px 6px;
		font-size: var(--step--1);
		font-variant-numeric: tabular-nums;
	}
	.gw-chip.beat {
		border-color: var(--teal, #2ed6c2);
	}
	.gw-chip .gw-n {
		font-size: 0.72em;
		opacity: 0.7;
	}
	.gw-note {
		font-size: var(--step--1);
		margin: 0 0 var(--s-2);
	}
	.count {
		font-size: var(--step--1);
		margin: var(--s-2) 0 0;
	}
	.locked {
		margin-top: var(--s-3);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-3);
	}
	.locked p {
		margin: 0 0 var(--s-2);
	}
	.share {
		font: inherit;
		font-size: var(--step--1);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: inherit;
		padding: 4px 10px;
		cursor: pointer;
	}
</style>
