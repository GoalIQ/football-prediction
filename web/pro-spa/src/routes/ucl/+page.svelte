<script lang="ts">
	/**
	 * /ucl — UCL Fantasy expected points (21.9.2026, Villen paatos: PREMIUM).
	 *
	 * Data: /api/fantasy/xp?league=ucl (scripts/build_ucl_xp.py). Maski on
	 * PALVELIMELLA: ilmaiskayttaja saa 10 taytta rivia ja meta.masked=true,
	 * sivu ei paattele premium-tilaa itse. Sama sopimus kuin FPL:n xP:lla.
	 *
	 * Rehellisyys ([[honest-data-labels]]): seuroille joilla ei ole
	 * kotiliigan pelaajadataa (Porto, PSV, Sabah ...) osuus tulee pelkista
	 * UEFA-otteluista, ja MD1-takatestissa ne olivat yliennustettuja. Rivi
	 * merkitaan nakyvasti, eika sivulla ole yhtaan suorituskykyvaitetta jota
	 * lukija ei voisi tarkistaa.
	 */
	import { fetchUclXp, type UclXpPlayer, type UclXpResponse } from '$lib/api';
	import { xpHorizon } from '$lib/xpHorizon';
	import { capture } from '$lib/analytics';
	import { DISCLAIMER } from '$lib/config';
	import Paywall from '$lib/components/Paywall.svelte';
	// 22.9 (T6): otsikko ja kuvaus yhdesta lahteesta, jota myos buildin
	// ucl.html (link preview) lukee. Ks. $lib/routeHeads.
	import { UCL_HEAD } from '$lib/routeHeads';

	let xp = $state<UclXpResponse | null>(null);
	let err = $state<string | null>(null);

	$effect(() => {
		capture('ucl_xp_page_viewed');
		fetchUclXp().then(
			(d) => (xp = d),
			(e) => (err = String(e))
		);
	});

	type Pos = 'ALL' | 'GKP' | 'DEF' | 'MID' | 'FWD';
	let pos = $state<Pos>('ALL');
	let club = $state('ALL');
	let q = $state('');
	let maxPrice = $state<number | null>(null);
	let sortBy = $state<'total' | 'next'>('total');

	let md = $derived(xp?.meta?.deadline_gameweek ?? null);
	let mdCols = $derived(xp?.players?.[0]?.gameweeks?.map((g) => g.gw) ?? []);
	// Summan ikkuna YHDESTA LUKIJASTA ($lib/xpHorizon, 17.-18.9). Lukija
	// antaa luvun (count) ja luvan sanoa "next" (actionableOnly, vain kun
	// palvelin julkaisi horizon_total_from:n). Yksikko on matchday, joten
	// lukijan GW-muotoiltuja nimia (gws, range) ei kayteta.
	let hz = $derived(xpHorizon(xp?.meta));
	let clubs = $derived(
		[...new Set((xp?.players ?? []).map((p) => p.team_short))].sort((a, b) => a.localeCompare(b))
	);

	function norm(s: string): string {
		return s
			.normalize('NFKD')
			.replace(/[\u0300-\u036f]/g, '')
			.toLowerCase();
	}

	function next(p: UclXpPlayer): number {
		return p.gameweeks?.[0]?.xp ?? 0;
	}

	let rows = $derived(
		(xp?.players ?? [])
			.filter((p) => pos === 'ALL' || p.pos === pos)
			.filter((p) => club === 'ALL' || p.team_short === club)
			.filter((p) => maxPrice === null || p.price <= maxPrice)
			.filter(
				(p) =>
					!q.trim() ||
					norm(p.web_name).includes(norm(q.trim())) ||
					norm(p.full_name ?? '').includes(norm(q.trim())) ||
					norm(p.team).includes(norm(q.trim()))
			)
			.sort((a, b) => (sortBy === 'next' ? next(b) - next(a) : b.xp_horizon_total - a.xp_horizon_total))
	);

	function thin(p: UclXpPlayer): boolean {
		return p.data_basis === 'uefa_matches';
	}

	function noData(p: UclXpPlayer): boolean {
		return p.data_basis === 'no_history';
	}

	function deadlineText(iso: string | null | undefined): string {
		if (!iso) return '';
		const d = new Date(iso);
		if (Number.isNaN(d.getTime())) return '';
		return d.toLocaleString('en-GB', {
			weekday: 'short',
			day: 'numeric',
			month: 'short',
			hour: '2-digit',
			minute: '2-digit',
			timeZone: 'UTC'
		}) + ' UTC';
	}
</script>

<svelte:head>
	<title>{UCL_HEAD.title}</title>
	<meta name="description" content={UCL_HEAD.description} />
</svelte:head>

<div class="shell">
	<p class="crumb muted">
		<a href="https://goaliq.app" data-cta="pro-home">goaliq.app</a> / <a href="/">GoalIQ tools</a> / UCL
		Fantasy
	</p>
	<h1>UCL Fantasy <span class="accent">expected points</span></h1>
	<p class="lede">
		Projected points for players in the official UEFA Champions League Fantasy game during the
		league phase{#if hz.count && hz.actionableOnly && !xp?.meta?.deadline_passed}, for the next
			{hz.count === 1 ? 'matchday' : `${hz.count} matchdays`}{:else if hz.count}, over
			{hz.count === 1 ? 'one matchday' : `${hz.count} matchdays`}{/if}, using the game's own scoring.
		{#if md && xp?.meta?.deadline_utc && !xp.meta.deadline_passed}
			<span class="deadline">Matchday {md} deadline: {deadlineText(xp.meta.deadline_utc)}.</span>
		{/if}
	</p>

	{#if err}
		<p class="error">Could not reach the API. {err}</p>
	{:else if !xp}
		<p class="muted">Loading…</p>
	{:else if !xp.meta.available && xp.meta.reason === 'league_phase_over'}
		<p class="muted">
			The league phase is over. GoalIQ's UCL Fantasy projections cover the league phase only.
		</p>
	{:else if !xp.meta.available || !xp.players.length}
		<p class="muted">UCL Fantasy projections are not published yet. Check back soon.</p>
	{:else}
		<div class="controls">
			<div class="posrow">
				{#each ['ALL', 'GKP', 'DEF', 'MID', 'FWD'] as pf (pf)}
					<button class:active={pos === pf} onclick={() => (pos = pf as Pos)}>{pf}</button>
				{/each}
			</div>
			<label
				>Club
				<select bind:value={club}>
					<option value="ALL">All clubs</option>
					{#each clubs as c (c)}
						<option value={c}>{c}</option>
					{/each}
				</select>
			</label>
			<label
				>Max price
				<select bind:value={maxPrice}>
					<option value={null}>Any</option>
					{#each [4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 9.0, 10.0] as m (m)}
						<option value={m}>{m.toFixed(1)}m</option>
					{/each}
				</select>
			</label>
			<label
				>Sort
				<select bind:value={sortBy}>
					<option value="total"
						>{hz.count && hz.actionableOnly && !xp?.meta?.deadline_passed
							? `Next ${hz.count === 1 ? 'matchday' : `${hz.count} matchdays`}`
							: hz.count
								? `Over ${hz.count === 1 ? 'one matchday' : `${hz.count} matchdays`}`
								: 'Total'}</option
					>
					<option value="next">Matchday {md ?? ''} only</option>
				</select>
			</label>
			<input type="search" placeholder="Search player or club" bind:value={q} />
		</div>

		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>Player</th>
						<th>Club</th>
						<th>Pos</th>
						<th class="num"><abbr title="Price in the official UCL Fantasy game">Price</abbr></th>
						<th class="num m-hide"
							><abbr title="Share of UCL Fantasy managers who own the player (official game data)"
								>Owned</abbr
							></th
						>
						<th class="num m-hide"><abbr title="Expected minutes in the next matchday">xMins</abbr></th>
						{#each mdCols as g (g)}
							<th class="num">MD{g}</th>
						{/each}
						<th class="num"
							><abbr
								title={hz.count
									? `Sum of expected points over ${hz.count === 1 ? 'the next matchday' : `${hz.count} matchdays`}`
									: 'Sum of expected points over the coming matchdays'}>Total</abbr
							></th
						>
					</tr>
				</thead>
				<tbody>
					{#each rows as p (p.id)}
						<tr>
							<td>
								{p.web_name}{#if thin(p)}<span
										class="thin"
										title="Thin data: the share of the club's goals comes from UEFA matches only, because the club plays outside the five leagues we have player data for. Treat the number with more caution."
										>thin data</span
									>{:else if noData(p)}<span
										class="thin"
										title="No match data for this player in our sources, so the number rests on a default squad role."
										>no data</span
									>{/if}{#if p.status !== 'a'}<span class="flag" title={p.news || 'Availability flag from the official game'}
										>{p.status === 'd' ? 'doubt' : p.status === 'u' ? 'not in squad' : 'out'}</span
									>{/if}
							</td>
							<td>{p.team_short}</td>
							<td>{p.pos}</td>
							<td class="num">{p.price.toFixed(1)}</td>
							<td class="num m-hide">{p.owned_pct.toFixed(0)}%</td>
							<td class="num m-hide">{p.xmins.toFixed(0)}</td>
							{#each p.gameweeks as g (g.gw)}
								<td class="num">
									<span class="opp">{g.opponents.map((o) => `${o.opp} ${o.venue}`).join(', ')}</span>
									{g.xp.toFixed(1)}
								</td>
							{/each}
							<td class="num strong">{p.xp_horizon_total.toFixed(1)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if xp.meta.masked}
			{#if rows.length === 0}
				<p class="muted small">
					No player in the free top 10 matches this filter. GoalIQ Premium shows every player in the
					game.
				</p>
			{:else}
				<p class="muted small">Showing the top 10. GoalIQ Premium shows every player in the game.</p>
			{/if}
			<Paywall teaser={false} />
		{/if}

		<section class="method">
			<h2>How the number is built</h2>
			<ul>
				<li>
					Each club's expected goals for and against in the match come from GoalIQ's Champions
					League model, which rates all 36 clubs on one scale.
				</li>
				<li>
					A player's share of those goals and assists comes from his expected goals and assists per
					90 minutes in his domestic league, for clubs in the Premier League, La Liga, Bundesliga,
					Serie A and Ligue 1. For the other clubs the goal share comes from goals and starting
					line-ups in UEFA matches, assists use the average for the position, and those rows are
					marked <span class="thin">thin data</span>. A player with no match data in our sources is marked
					<span class="thin">no data</span>.
				</li>
				<li>
					Points use the official UCL Fantasy scoring. Availability flags come from the official
					game and apply in full to the next matchday.
				</li>
			</ul>
			<p class="muted small">
				These are GoalIQ model projections, not the game's own figures. Prices, ownership and
				squad status are the official game's data. The free UCL Fantasy data pages are at
				<a href="https://goaliq.app/ucl/">goaliq.app/ucl</a>. GoalIQ is an independent data tool and
				is not affiliated with UEFA. {DISCLAIMER}
			</p>
		</section>
	{/if}
</div>

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-4);
	}
	.crumb {
		margin-bottom: var(--s-2);
	}
	h1 {
		margin: 0 0 var(--s-2);
	}
	.accent {
		color: var(--accent);
	}
	.lede {
		max-width: 60ch;
	}
	.deadline {
		font-weight: 600;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2);
		align-items: center;
		margin: var(--s-4) 0 var(--s-2);
	}
	.controls select,
	.controls input {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		padding: var(--s-1);
		max-width: 100%;
	}
	.posrow {
		display: flex;
		gap: var(--s-1);
	}
	.posrow button {
		background: none;
		border: 1px solid var(--border);
		border-radius: 3px;
		padding: var(--s-1) var(--s-2);
		cursor: pointer;
		color: inherit;
	}
	.posrow button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		border-collapse: collapse;
		width: 100%;
	}
	th,
	td {
		text-align: left;
		padding: var(--s-1) var(--s-2);
		border-bottom: 1px solid var(--border);
		white-space: nowrap;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.strong {
		font-weight: 700;
	}
	.opp {
		opacity: 0.65;
		font-size: 0.8em;
		margin-right: 4px;
	}
	.thin,
	.flag {
		display: inline-block;
		border: 1px solid var(--border);
		border-radius: 3px;
		padding: 0 4px;
		margin-left: 6px;
		font-size: 0.75em;
		opacity: 0.8;
	}
	.flag {
		border-color: var(--bad, #c62828);
	}
	.method {
		margin-top: var(--s-8);
		max-width: 70ch;
	}
	.small {
		font-size: 0.85em;
	}
	@media (max-width: 640px) {
		.m-hide {
			display: none;
		}
	}
</style>
