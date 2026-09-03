<script lang="ts">
	/**
	 * Value (#127) — web-pariteetti mobiilin #114:lle: xP/£-value-ranking +
	 * GK rotation pairs. Sama gate kuin mobiilissa: free = top-3 + lukko,
	 * premium = koko lista + GK-parit. Source fantasy_value (identtinen
	 * paywall_shown/upgrade_tapped, #85-oppi). Korttikieli #124 Leadersin
	 * mukainen, paletti #108.
	 */
	import { capture } from '$lib/analytics';
	import { fetchValue, type ValueResponse } from '$lib/fantasyTools';
	import { canShareToApps, shareCard, shareButtonLabel} from '$lib/shareCard';
	import { currentEntryId } from '$lib/fplEntry.svelte';

	let { premium = false, onUpgrade }: { premium?: boolean; onUpgrade?: () => void } = $props();

	const FREE_ROWS = 3;
	const SWING_LABEL: Record<string, string> = {
		steady: 'Steady fixtures',
		moderate: 'Moderate swing',
		swingy: 'Swingy fixtures'
	};

	let data = $state<ValueResponse | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	// 4.8: suodattimet + sortaus. NAMA OVAT PREMIUM-ONLY EIVATKA KOSMETIIKKAA --
	// free nakee top-3, ja jos free saisi pelipaikka-/joukkuesuodattimen, han
	// kavisi listan lapi 3 rivia kerrallaan ja nakisi kaytannossa koko
	// rankingin. Sama vikaluokka kuin 3.8. captain/differentials-vuoto.
	type SortKey = 'value' | 'xp' | 'price';
	let posFilter = $state('');
	let teamFilter = $state('');
	let sortKey = $state<SortKey>('value');
	let sharing = $state(false);

	// MY-TEAM-CONTEXT (3.9): jaettu entry (Rate my team -kenttä / tallennettu)
	// kulkee mukaan. Efekti lukee sen, joten kentän muutos hakee uudelleen.
	$effect(() => {
		const entry = currentEntryId();
		loading = true;
		fetchValue(entry)
			.then((d) => (data = d))
			.catch((e) => (error = e instanceof Error ? e.message : String(e)))
			.finally(() => (loading = false));
	});

	$effect(() => {
		if (!premium && (data?.players?.length ?? 0) > 0) {
			capture('paywall_shown', { source: 'fantasy_value' }, 'paywall_shown_fantasy_value');
		}
	});

	const players = $derived(data?.players ?? []);

	/** Joukkuevaihtoehdot datasta, ei kovakoodattuna (nousijat seuraavat itse). */
	const teamOptions = $derived([...new Set(players.map((p) => p.team_short))].sort());

	/** Tiebreak aina value desc, jotta listan identiteetti sailyy sortista
	 *  riippumatta (sama kaava kuin Leadersissa). */
	const visible = $derived.by(() => {
		if (!premium) return players.slice(0, FREE_ROWS);
		const v = (p: (typeof players)[number]) =>
			sortKey === 'price' ? p.price : sortKey === 'xp' ? p.xp_horizon_total : p.value;
		return players
			.filter((p) => (!posFilter || p.pos === posFilter) && (!teamFilter || p.team_short === teamFilter))
			.sort((a, b) => v(b) - v(a) || b.value - a.value);
	});
	const pairs = $derived(data?.gk?.pairs ?? []);
	const ownPair = $derived(data?.gk?.own_pair ?? null);
	const reachablePair = $derived(data?.gk?.reachable_pair ?? null);
	const affordablePair = $derived(data?.gk?.affordable_pair ?? null);
	/** 🔴 3.9 ILTA (Villen toinen havainto): kaksi PROOSARIVIA eivat riittaneet.
	 *  Kayttaja lukee taulukon, ja taulukon karki oli yha globaali paras pari
	 *  (11.5 M, kaksi siirtoa) vaikka hanen budjettinsa on 9.4 M. Kun entry on
	 *  luettu, taulukko nayttaa OLETUKSENA vain ne parit joihin raha riittaa
	 *  (`for_you`); koko lista on chipin takana eika katoa. */
	const forYou = $derived(data?.gk?.for_you ?? null);
	let gkScope = $state<'you' | 'all'>('you');
	const gkRows = $derived(
		forYou && forYou.length > 0 && gkScope === 'you' ? forYou : pairs
	);
	const squad = $derived(data?.gk?.meta?.squad ?? data?.meta?.squad ?? null);
	const hasSquad = $derived(squad?.available === true);

	function transfersLabel(n: number | undefined): string {
		if (n === 0) return 'your pair';
		if (n === 1) return 'needs 1 transfer';
		if (n === 2) return 'needs 2 transfers';
		return '';
	}

	function unlock() {
		capture('upgrade_tapped', { source: 'fantasy_value' });
		onUpgrade?.();
	}

	// 4.8: Value oli ainoa premium-lista ILMAN jakokorttia (CaptainRanker,
	// Leaders, CleanSheets, PriceWatch ja pitch saivat sen 31.7-2.8). Jakaa
	// NAKYVAN nakyman top 10 -- aktiiviset suodattimet mukana alaotsikossa,
	// muuten kortti vaittaisi olevansa koko listan karki.
	const SORT_LABEL: Record<SortKey, string> = {
		value: 'xP per million',
		xp: 'projected xP',
		price: 'price'
	};
	async function share() {
		if (sharing) return;
		sharing = true;
		try {
			const sub = [
				`next ${data?.meta?.horizon_gw ?? 6} gameweeks`,
				`by ${SORT_LABEL[sortKey]}`,
				...(posFilter ? [posFilter] : []),
				...(teamFilter ? [teamFilter] : [])
			].join(', ');
			const method = await shareCard({
				title: 'TOP VALUE PICKS',
				subtitle: `${sub}, GoalIQ model`,
				midLabel: 'PRICE',
				// 🔴 3.9 (audit): arvosarake oli kovakoodattu xP/£m vaikka
				// alaotsikko sanoi "by projected xP". Kortti vaitti olevansa
				// jarjestetty luvulla jota siina ei nakynyt, eli ainoa nakyva
				// sarake luki kohinana. Nyt luku on se jolla lista on jarjestetty.
				// Hinta on jo `mid`-sarakkeessa, joten hintasortissa arvosarake
				// nayttaa xP:n eika toista hintaa kahdesti.
				valueLabel: sortKey === 'value' ? 'xP/£m' : 'xP',
				fileName: 'goaliq_value.png',
				footNote: 'xP from the GoalIQ model, price from FPL',
				rows: visible.slice(0, 10).map((p, i) => ({
					rank: i + 1,
					name: p.web_name,
					tag: p.pos,
					team: p.team_short,
					mid: p.price.toFixed(1),
					value:
						sortKey === 'value'
							? p.value.toFixed(2)
							: p.xp_horizon_total.toFixed(1)
				}))
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'value', method });
		} finally {
			sharing = false;
		}
	}
</script>

<div class="head-row">
	<h2>Player value: xP per million</h2>
	{#if premium && players.length > 0}
		<!-- 4.8: jaettava kortti nakyvasta nakymasta (premium) -->
		<button type="button" class="window-chip" onclick={share} disabled={sharing}>
			{sharing ? 'Rendering…' : shareButtonLabel()}
		</button>
	{/if}
</div>
<p class="muted">
	Projected points per million spent over the next {data?.meta?.horizon_gw ?? 6} gameweeks, with a
	fixture-swing flag.
</p>

{#if loading}
	<p class="muted">Loading value ranking…</p>
{:else if error}
	<p class="banner error">{error}</p>
{:else}
	{#if premium && players.length > 0}
		<!-- Suodattimet ovat premium-only, ks. script-lohkon kommentti. -->
		<div class="window-row">
			<span class="muted">Sort:</span>
			<button type="button" class="window-chip" class:on={sortKey === 'value'} onclick={() => (sortKey = 'value')}>Value</button>
			<button type="button" class="window-chip" class:on={sortKey === 'xp'} onclick={() => (sortKey = 'xp')}>xP</button>
			<button type="button" class="window-chip" class:on={sortKey === 'price'} onclick={() => (sortKey = 'price')}>Price</button>
			<span class="muted">Pos:</span>
			{#each ['', 'GKP', 'DEF', 'MID', 'FWD'] as pp (pp)}
				<button type="button" class="window-chip" class:on={posFilter === pp} onclick={() => (posFilter = pp)}>
					{pp === '' ? 'All' : pp}
				</button>
			{/each}
			{#if teamOptions.length > 1}
				<span class="muted">Team:</span>
				<select bind:value={teamFilter} aria-label="Filter by team">
					<option value="">All</option>
					{#each teamOptions as ts (ts)}
						<option value={ts}>{ts}</option>
					{/each}
				</select>
			{/if}
		</div>
	{/if}
	{#if players.length === 0}
		<p class="muted">No data yet.</p>
	{:else if visible.length === 0}
		<p class="muted">No players match these filters.</p>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>#</th>
						<th>Player</th>
						<th class="m-hide">Pos</th>
						<th class="num m-hide">Price</th>
						<th class="num"><abbr title="Projected xP per million over the horizon">Value</abbr></th>
						<th class="num"><abbr title="Total projected points over the horizon">xP</abbr></th>
						<th class="num m-hide"
							><abbr title="Projected points if the player completes a full 90 minutes. This is the rate, not the return: read it next to Mins, which is what the model actually expects him to play."
								>xP/90</abbr
							></th
						>
						<th class="num m-hide"
							><abbr title="Expected minutes per gameweek. A high rate on low minutes is a bench risk, not a bargain."
								>Mins</abbr
							></th
						>
						<th class="m-hide">Fixtures</th>
						<th class="num m-hide">Owned</th>
					</tr>
				</thead>
				<tbody>
					{#each visible as p, i (p.id)}
						<tr>
							<td class="muted">{i + 1}</td>
							<td
								>{p.web_name} <span class="muted">({p.team_short})</span>{#if p.owned}
									<span class="own-badge" title="In your squad">owned</span>{/if}</td
							>
							<td class="m-hide">{p.pos}</td>
							<td class="num m-hide">{p.price.toFixed(1)}</td>
							<td class="num strong">{p.value.toFixed(2)}</td>
							<td class="num">{p.xp_horizon_total.toFixed(1)}</td>
							<td class="num m-hide">
								{#if p.xp_per_90 == null}
									<span class="muted" title="Too few expected minutes for a rate to mean anything"
										>-</span
									>
								{:else}
									{p.xp_per_90.toFixed(2)}
								{/if}
							</td>
							<td class="num m-hide">
								{#if p.xmins == null}
									<span class="muted">-</span>
								{:else}
									{Math.round(p.xmins)}
								{/if}
							</td>
							<td class="m-hide">{SWING_LABEL[p.swing_label] ?? p.swing_label}</td>
							<td class="num m-hide">{p.owned_pct.toFixed(1)}%</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="muted note">
			Fixture swing measures calendar difficulty variation over the horizon, not point variance.
			xP/90 is the rate over a full 90 minutes and Mins is how much of a gameweek the model
			expects the player to play. They are shown separately on purpose: xP already multiplies them
			together, which hides the assumption most likely to break.
		</p>
	{/if}

	{#if premium}
		{#if pairs.length > 0}
			<h2 class="gk-title">GK rotation pairs</h2>
			<p class="muted">
				Two budget keepers whose fixtures alternate: start whichever has the better clean-sheet
				chance each week. Pairs are ranked by that average scaled by how many of the next
				{data?.gk?.meta?.horizon_gw ?? 6} gameweeks both clubs have a projection for.
			</p>
			{#if hasSquad}
				<!-- MY-TEAM-CONTEXT (3.9): oma pari vertailuriviksi samalla kaavalla -->
				{#if ownPair}
					<p class="own-line">
						Your pair: {ownPair.gk_a.web_name} + {ownPair.gk_b.web_name},
						<strong>{ownPair.avg_best_cs_pct.toFixed(1)}%</strong>
						<span class="muted"
							>(rank {ownPair.rank} of {ownPair.of}{#if data?.gk?.meta?.own_budget != null},
								{data.gk.meta.own_budget.toFixed(1)}m to spend on two keepers{/if})</span
						>
					</p>
				{:else if data?.gk?.meta?.own_pair_note}
					<p class="muted">{data.gk.meta.own_pair_note}</p>
				{/if}
				<!-- 3.9 ilta (Villen havainto): kun omaa paria ei voi pisteyttaa,
				     lista yksin on vastaus JOHON KAYTTAJA EI YLLA — sen karki
				     vaatii kaksi siirtoa ja enemman rahaa kuin hanella on. Nama
				     kaksi rivia ovat sama lista rajattuna siihen mihin han
				     ylttaa, ja molemmat kertovat sijoituksensa jotta huono
				     vaihtoehto nakyy huonona. -->
				{#if reachablePair && data?.gk?.meta?.reachable_note}
					<p class="own-line">
						{data.gk.meta.reachable_note}
						<strong>{reachablePair.avg_best_cs_pct.toFixed(1)}%</strong>
						<span class="muted">(rank {reachablePair.rank} of {reachablePair.of})</span>
					</p>
				{/if}
				{#if affordablePair && data?.gk?.meta?.affordable_note && affordablePair.transfers_needed !== 1}
					<p class="own-line">
						{data.gk.meta.affordable_note}
						<strong>{affordablePair.avg_best_cs_pct.toFixed(1)}%</strong>
						<span class="muted">(rank {affordablePair.rank} of {affordablePair.of})</span>
					</p>
				{/if}
			{:else if squad && !squad.available && squad.note}
				<p class="muted">Your squad was not read: {squad.note}</p>
			{:else}
				<!-- 🔴 3.9 ILTA (Villen kolmas havainto samasta asiasta): ilman
				     entrya osio nayttti globaalin listan JA OLI HILJAA. Lukija ei
				     voi erottaa "tyokalu ei valita joukkueestani" ja "en ole
				     antanut sille joukkuettani talla pinnalla" — ja Ville luki sen
				     ensimmaisella tavalla, kahdesti. Puuttuva tieto sanotaan. -->
				<p class="muted">
					This list does not know your squad yet, so it is the best pairs in the game
					rather than the ones you can buy. Put your FPL entry ID into Rate my team
					under My team, and this section narrows to your two keepers plus your bank.
				</p>
			{/if}
			{#if forYou && forYou.length > 0}
				<div class="gk-scope">
					<button
						type="button"
						class="window-chip"
						class:on={gkScope === 'you'}
						onclick={() => (gkScope = 'you')}>Ones you can afford</button
					>
					<button
						type="button"
						class="window-chip"
						class:on={gkScope === 'all'}
						onclick={() => (gkScope = 'all')}>All pairs</button
					>
				</div>
				{#if gkScope === 'you' && data?.gk?.meta?.for_you_note}
					<p class="muted small">{data.gk.meta.for_you_note}</p>
				{/if}
			{:else if hasSquad && data?.gk?.meta?.for_you_note}
				<p class="muted small">{data.gk.meta.for_you_note}</p>
			{/if}
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Pair</th>
							<th class="num"><abbr title="Combined price of both keepers">Cost</abbr></th>
							<th class="num"
								><abbr title="Average of the better keeper's clean-sheet chance each gameweek"
									>Avg best CS%</abbr
								></th
							>
							{#if hasSquad}
								<th
									><abbr title="How many of the two you do not own, and whether the pair fits your two keepers plus bank"
										>For you</abbr
									></th
								>
							{/if}
							<th class="m-hide">Start plan</th>
						</tr>
					</thead>
					<tbody>
						{#each gkRows.slice(0, 5) as pair (pair.gk_a.id + '-' + pair.gk_b.id)}
							<tr class:own-row={pair.transfers_needed === 0}>
								<td>
									{pair.gk_a.web_name} <span class="muted">({pair.gk_a.team_short})</span> +
									{pair.gk_b.web_name} <span class="muted">({pair.gk_b.team_short})</span>
									{#if pair.common_gws != null}
										<span class="muted small"
											>({pair.common_gws} of {data?.gk?.meta?.horizon_gw ?? '?'} GWs)</span
										>
									{/if}
								</td>
								<td class="num">{pair.combined_price.toFixed(1)}</td>
								<td class="num strong">{pair.avg_best_cs_pct.toFixed(1)}%</td>
								{#if hasSquad}
									<td class="small">
										{transfersLabel(pair.transfers_needed)}{#if pair.transfers_needed && pair.affordable === false},
											<span class="over">over budget</span>{/if}
									</td>
								{/if}
								<td class="muted plan-cells m-hide">
									{pair.gw_split.map((s) => `GW${s.gw} ${s.team_short}`).join(' · ')}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if hasSquad && data?.gk?.meta?.own_note}
				<p class="muted note">{data.gk.meta.own_note}</p>
			{/if}
		{/if}
	{:else if (data?.players?.length ?? 0) > FREE_ROWS}
		<!-- 🔒 sama gate kuin mobiili #114: top-3 free, loput + GK-parit premium -->
		<button type="button" class="teaser-row" onclick={unlock}>
			<span>
				Top 50 value ranking, position and team filters, and GK rotation pairs. Save your
				FPL ID and the pair list narrows to the ones your bank can actually pay for, with
				your own pair ranked on the same formula
				<span class="muted">(top 3 shown free)</span>
			</span>
			<span class="locked" aria-label="Locked">•.••</span>
			<span class="cta">Unlock with Premium</span>
		</button>
	{/if}
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
	/* Sama kontrollikieli kuin Leadersissa (window-row/-chip) */
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
	.gk-scope {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin: 10px 0 6px;
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
	.window-chip:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.window-row select {
		flex: 0 0 auto;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		font-weight: 600;
		font-size: var(--step--1);
		padding: 4px 10px;
		line-height: 1.4;
	}
	.strong {
		font-weight: 800;
		color: var(--giq-rust);
	}
	.gk-title {
		margin-top: var(--s-5);
	}
	.note {
		font-size: var(--step--1);
	}
	.plan-cells {
		font-size: var(--step--1);
		white-space: nowrap;
	}
	.small {
		font-size: var(--step--1);
	}
	.own-line {
		margin: 0 0 var(--s-2);
	}
	.own-row td {
		background: rgba(46, 214, 194, 0.08);
	}
	.over {
		color: var(--negative);
	}
	.own-badge {
		display: inline-block;
		margin-left: 6px;
		padding: 0 6px;
		border-radius: var(--radius);
		border: 1px solid rgba(0, 148, 130, 0.4);
		color: var(--positive);
		font-size: var(--step--1);
		font-weight: 700;
	}
	.teaser-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-2);
		width: 100%;
		margin-top: var(--s-3);
		background: rgba(255, 138, 92, 0.1);
		border: 1px solid rgba(255, 138, 92, 0.35);
		border-radius: var(--radius);
		padding: var(--s-2) var(--s-3);
		color: var(--text);
		font-weight: 600;
		font-size: var(--step--1);
		cursor: pointer;
		text-align: left;
	}
	.teaser-row .cta {
		margin-left: auto;
		color: var(--positive);
		font-weight: 700;
	}
	.locked {
		letter-spacing: 2px;
		color: var(--text-muted);
	}
</style>
