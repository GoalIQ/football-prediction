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
	import AppShell from '$lib/components/AppShell.svelte';
	import { fetchUclXp, type UclXpPlayer, type UclXpResponse } from '$lib/api';
	import { xpHorizon } from '$lib/xpHorizon';
	import { capture } from '$lib/analytics';
	import { DISCLAIMER } from '$lib/config';
	import Paywall from '$lib/components/Paywall.svelte';
	// 22.9 (T6): otsikko ja kuvaus yhdesta lahteesta, jota myos buildin
	// ucl.html (link preview) lukee. Ks. $lib/routeHeads.
	import { UCL_HEAD } from '$lib/routeHeads';
	// 23.9 (UCL-LAAJENNUS-FPL-TYYLIIN vaihe 1): Captain / Value / Differentials
	// samasta vastauksesta, FPL:n Players-esiasetusten kaava. Listat laskee
	// YKSI lukija ($lib/uclPicks), sama kuin mobiilissa.
	import {
		UCL_DIFF_MAX_OWNED,
		uclPicks,
		type UclView
	} from '$lib/uclPicks';
	// 23.9 (UCL-MENUT, Villen valinta "sama rakenne kuin FPL/RSL"): osiot
	// Players | Teams ovat palkissa, osion sisalla FPL:n esiasetukset.
	import GameViewNav from '$lib/components/GameViewNav.svelte';
	import { gameViewState } from '$lib/gameView.svelte';
	import type { UclPageView } from '$lib/tools';

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
	let includeThin = $state(false);

	/* Nakyma hashista yhden lukijan kautta ($lib/gameView.svelte, sama kuin
	   /spl). Sama analytiikkatapahtuma kuin 23.9 vaihe 1:n valilehdilla. */
	const gv = gameViewState<UclPageView>('ucl', 'ucl_view_changed');
	let view = $derived(gv.view);
	/** Sivun nakyma -> uclPicksin lista. 'xp' on kaikkien pelaajien lista. */
	const PICK_VIEWS: Partial<Record<UclPageView, Exclude<UclView, 'all'>>> = {
		captain: 'captain',
		value: 'value',
		differentials: 'differentials'
	};
	let pickView = $derived(PICK_VIEWS[view] ?? null);
	let playersList = $derived(view === 'xp' || pickView !== null);
	let picks = $derived(
		pickView ? uclPicks(xp?.players, xp?.meta, pickView, { pos, includeThin }) : null
	);

	/* Compare two players (Players > More). Valinta koko listasta; maskattu
	   (ilmainen) vastaus on vain kymmenen karki, joten nakyma on lukossa. */
	let cmpA = $state<number | null>(null);
	let cmpB = $state<number | null>(null);
	let cmpPool = $derived(
		[...(xp?.players ?? [])].sort((a, b) => a.web_name.localeCompare(b.web_name))
	);
	let cmpPlayers = $derived(
		[cmpA, cmpB]
			.map((id) => (xp?.players ?? []).find((p) => p.id === id))
			.filter((p): p is UclXpPlayer => !!p)
	);

	/* Teams: joukkueiden clean sheet % kierroksittain (artefaktin `teams`,
	   sama CL-malli kuin puolustajien xP). Keskiarvo lasketaan riveista. */
	let teams = $derived(
		(xp?.teams ?? []).map((t) => ({
			t,
			avg: t.fixtures.length
				? t.fixtures.reduce((a, f) => a + f.cs_pct, 0) / t.fixtures.length
				: null
		}))
	);

	let md = $derived(xp?.meta?.deadline_gameweek ?? null);
	let mdCols = $derived(xp?.players?.[0]?.gameweeks?.map((g) => g.gw) ?? []);
	// Summan ikkuna YHDESTA LUKIJASTA ($lib/xpHorizon, 17.-18.9). Lukija
	// antaa luvun (count) ja luvan sanoa "next" (actionableOnly, vain kun
	// palvelin julkaisi horizon_total_from:n). Yksikko on matchday, joten
	// lukijan GW-muotoiltuja nimia (gws, range) ei kayteta.
	let hz = $derived(xpHorizon(xp?.meta));
	/* Summan ikkuna samasta lukijasta kuin taulukon otsikko: "next" vain
	   kun palvelin antoi luvan (hz.actionableOnly) eika deadline ole mennyt. */
	let windowText = $derived(
		hz.count && hz.actionableOnly && !xp?.meta?.deadline_passed
			? hz.count === 1
				? 'the next matchday'
				: `the next ${hz.count} matchdays`
			: hz.count
				? hz.count === 1
					? 'one matchday'
					: `${hz.count} matchdays`
				: 'the coming matchdays'
	);
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

<!-- 22.9 (web-audit T2, muisti appshell-korjaus-ei-kata-erillisreitteja):
     sivu renderoityy AppShellin sisalla, joten ylapalkki, pelivalitsin ja
     puhelimen alapalkki ovat samat kuin FPL-reiteilla. Ennen 22.9 taman
     reitin ylapalkki puuttui kokonaan. -->
<AppShell>
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

	<!-- Maskatulle (ilmainen) listat ja vertailu ovat Premiumia: sama merkki kuin
	     FPL:n lukituissa esiasetuksissa (julkaisutarkistaja 23.9). -->
	<GameViewNav
		game="ucl"
		{view}
		horizonMeta={xp?.meta ?? null}
		locked={xp?.meta?.masked ? ['captain', 'value', 'differentials', 'compare'] : []}
	/>

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
		{#if playersList}
		<div class="controls">
			<div class="posrow">
				{#each ['ALL', 'GKP', 'DEF', 'MID', 'FWD'] as pf (pf)}
					<button class:active={pos === pf} onclick={() => (pos = pf as Pos)}>{pf}</button>
				{/each}
			</div>
			{#if view === 'xp'}
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
			{:else if picks?.state === 'rows'}
				<label class="thin-toggle">
					<input type="checkbox" bind:checked={includeThin} /> Show players with thin or no data
				</label>
			{/if}
		</div>

		{#if picks}
			{#if picks.state === 'locked'}
				<p class="muted">
					This list is part of GoalIQ Premium. The free view shows the top 10 by expected points under
					xP.
				</p>
				<Paywall teaser={false} />
			{:else if picks.state === 'no_matchday'}
				<p class="muted">
					Captain picks return when projections for the next matchday are published.
				</p>
			{:else if picks.state === 'rows'}
				<p class="muted small view-lede">
					{#if view === 'captain'}
						Players ranked by expected points on matchday {picks.md} only.
					{:else if view === 'value'}
						Expected points over {windowText} per million of price. Only players with no availability
						flag are listed.
					{:else}
						Players owned by {UCL_DIFF_MAX_OWNED}% or fewer of UCL Fantasy managers, ranked by expected
						points over {windowText}. Only players with no availability flag are listed.
					{/if}
					{#if !includeThin && picks.hiddenThin > 0}
						{picks.hiddenThin === 1
							? 'One player with thin or no data would rank here and is hidden.'
							: `${picks.hiddenThin} players with thin or no data would rank here and are hidden.`}
					{/if}
				</p>
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>#</th>
								<th>Player</th>
								<th>Club</th>
								<th>Pos</th>
								<th class="num">Price</th>
								<th class="num">Owned</th>
								{#if view === 'captain'}
									<th class="num">MD{picks.md}</th>
								{:else}
									<th class="num"
										><abbr title={`Sum of expected points over ${windowText}`}>Total</abbr></th
									>
									{#if view === 'value'}
										<th class="num"><abbr title="Expected points per million of price">xP per m</abbr></th>
									{/if}
								{/if}
							</tr>
						</thead>
						<tbody>
							{#each picks.rows as r, i (r.player.id)}
								{@const p = r.player}
								{@const g = p.gameweeks.find((x) => x.gw === picks.md)}
								<tr>
									<td class="muted">{i + 1}</td>
									<td>
										{p.web_name}{#if thin(p)}<span class="thin">thin data</span>{:else if noData(p)}<span
												class="thin">no data</span
											>{/if}{#if p.status !== 'a'}<span class="flag" title={p.news || 'Availability flag from the official game'}
												>{p.status === 'd' ? 'doubt' : p.status === 'u' ? 'not in squad' : 'out'}</span
											>{/if}
									</td>
									<td>{p.team_short}</td>
									<td>{p.pos}</td>
									<td class="num">{p.price.toFixed(1)}</td>
									<td class="num">{p.owned_pct.toFixed(0)}%</td>
									{#if view === 'captain'}
										<td class="num strong">
											{#if g}<span class="opp"
													>{g.opponents.map((o) => `${o.opp} ${o.venue}`).join(', ')}</span
												>{/if}{r.score.toFixed(1)}
										</td>
									{:else}
										<td class="num" class:strong={view === 'differentials'}
											>{p.xp_horizon_total.toFixed(1)}</td
										>
										{#if view === 'value'}
											<td class="num strong">{r.score.toFixed(2)}</td>
										{/if}
									{/if}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				{#if picks.rows.length === 0}
					<p class="muted small">No player matches this filter.</p>
				{/if}
			{/if}
		{:else}

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
		{/if}
		{:else if view === 'compare'}
			<h2>Compare two players</h2>
			{#if xp.meta.masked}
				<p class="muted">
					Comparing players is part of GoalIQ Premium. The free view shows the top 10 by expected
					points under xP.
				</p>
				<Paywall teaser={false} />
			{:else}
				<div class="cmp-row">
					{#each [0, 1] as slot (slot)}
						<select
							value={(slot === 0 ? cmpA : cmpB) ?? ''}
							onchange={(e) => {
								const v = Number((e.target as HTMLSelectElement).value) || null;
								if (slot === 0) cmpA = v;
								else cmpB = v;
								if (cmpA && cmpB) capture('ucl_compare_used');
							}}
						>
							<option value="">Pick player {slot + 1}…</option>
							{#each cmpPool as p (p.id)}
								<option value={p.id}>{p.web_name} ({p.team_short}, {p.pos})</option>
							{/each}
						</select>
					{/each}
				</div>
				{#if cmpPlayers.length === 2}
					<div class="table-wrap">
						<table>
							<thead>
								<tr><th></th>{#each cmpPlayers as p (p.id)}<th>{p.web_name} ({p.team_short})</th>{/each}</tr>
							</thead>
							<tbody>
								<tr><td>Price</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.price.toFixed(1)}</td>{/each}</tr>
								<tr><td>Owned</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.owned_pct.toFixed(0)}%</td>{/each}</tr>
								<tr><td>{md ? `Expected minutes, MD${md}` : 'Expected minutes, next matchday'}</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.xmins.toFixed(0)}</td>{/each}</tr>
								{#each mdCols as g (g)}
									<tr>
										<td>MD{g}</td>
										{#each cmpPlayers as p (p.id)}
											{@const m = p.gameweeks.find((x) => x.gw === g)}
											<td class="num">
												{#if m}<span class="opp">{m.opponents.map((o) => `${o.opp} ${o.venue}`).join(', ')}</span>{m.xp.toFixed(1)}{:else}–{/if}
											</td>
										{/each}
									</tr>
								{/each}
								<tr><td>Total, {windowText}</td>{#each cmpPlayers as p (p.id)}<td class="num strong">{p.xp_horizon_total.toFixed(1)}</td>{/each}</tr>
								<tr>
									<td>Data</td>
									{#each cmpPlayers as p (p.id)}
										<td class="num">{thin(p) ? 'thin data' : noData(p) ? 'no data' : 'domestic league'}</td>
									{/each}
								</tr>
							</tbody>
						</table>
					</div>
				{/if}
			{/if}
		{:else if view === 'clean-sheets'}
			<h2>Clean sheet % by matchday</h2>
			{#if !teams.length}
				<p class="muted">Clean sheet chances by club are not published yet. Check back soon.</p>
			{:else}
				<p class="muted small view-lede">
					The chance each club keeps a clean sheet in its matches over {windowText}, from
					GoalIQ's Champions League model. The same number is behind the clean sheet points in the
					xP list.
				</p>
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>Club</th>
								<th class="num">avg CS%</th>
								{#each mdCols as g (g)}
									<th class="num">MD{g}</th>
								{/each}
							</tr>
						</thead>
						<tbody>
							{#each teams as { t, avg } (t.id)}
								<tr>
									<td>{t.name} <span class="muted">{t.short}</span></td>
									<td class="num strong">{avg == null ? '–' : `${avg.toFixed(1)}%`}</td>
									{#each mdCols as g (g)}
										{@const f = t.fixtures.find((x) => x.gw === g)}
										<td class="num">
											{#if f}<span class="opp">{f.opp} {f.venue}</span>{Math.round(f.cs_pct)}%{:else}–{/if}
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
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
</AppShell>

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
	.cmp-row {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2);
		margin: var(--s-2) 0 var(--s-3);
	}
	.cmp-row select {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		padding: var(--s-1);
		max-width: 100%;
	}
	.view-lede {
		max-width: 70ch;
	}
	.thin-toggle {
		display: inline-flex;
		align-items: center;
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
