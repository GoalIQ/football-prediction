<script lang="ts">
	/**
	 * This week (22.9.2026, UX-uudistus A3 2.1, Villen GO).
	 *
	 * Ensimmainen ruutu vastaa yhteen kysymykseen: "mita teen ennen
	 * deadlinea?". Jarjestys:
	 *   1. deadline-rivi (kierros, aika lukijan vyohykkeella, jaljella)
	 *   2. paatoskortti: Captain / Transfer / Chip (DecisionCard)
	 *   3. Last call: edellinen kierros, malli vs sina vs FPL:n keskiarvo
	 *   4. kierroksen clean sheet -rivi
	 *   5. sina vs malli, kausi
	 *   6. Beat the Model
	 * Rivit 3-6 ovat yhden lauseen tiivistelmia; koko nakyma (GW review,
	 * kausikisa, kirjatut paatokset) avautuu samaan kohtaan (A2 saanto 8).
	 *
	 * 🔴 ENNEN (mitattu 22.9, a1-mobiiliaudit + web): ilman joukkuetta sivu
	 * sanoi "Set up your team first" eika nayttanyt mitaan, ja tauolla
	 * paasisalto oli tyhja lista. Nyt ilman joukkuetta kortti nayttaa MALLIN
	 * rungon kapteenin (sama rate-team-lukija), ja tauolla kortti nayttaa
	 * seuraavan deadline-kierroksen, koska projektiot ovat jo olemassa.
	 *
	 * Vain olemassa olevaa dataa: rate-team, model-squad, model-race ja
	 * /api/fantasy. Ei uusia endpointteja, ei klientin laskemia lukuja.
	 */
	import { auth } from '$lib/auth.svelte';
	import { fetchFantasy, fetchModelRace, type FantasyResponse, type ModelRaceResponse } from '$lib/api';
	import { fetchModelCard, type RateTeamResponse } from '$lib/fantasyTools';
	import { currentEntryId, fplEntry } from '$lib/fplEntry.svelte';
	import { countdownText, formatDeadline, weekPhase } from '$lib/gameweek';
	import { gwCleanSheets, lastCall, seasonLine } from '$lib/weekRows';
	import DecisionCard from './DecisionCard.svelte';
	import GwReview from './GwReview.svelte';
	import SeasonRace from './SeasonRace.svelte';
	import BeatTheModel from './BeatTheModel.svelte';
	import DefConLive from './DefConLive.svelte';
	import type { WeeklyAction } from './WeeklyActions.svelte';

	let {
		data = null,
		loading = false,
		error = null,
		picksNotPublished = false,
		premium = false,
		onUpgrade,
		deadlineUtc = null,
		actions = [],
		onFollowTransfer,
		refreshToken = 0,
		onEntry,
		rank = null,
		rankChange = null,
		rankGw = null
	}: {
		data?: RateTeamResponse | null;
		loading?: boolean;
		error?: string | null;
		picksNotPublished?: boolean;
		premium?: boolean;
		onUpgrade?: () => void;
		deadlineUtc?: string | null;
		actions?: WeeklyAction[];
		onFollowTransfer?: (choice: Record<string, unknown>) => boolean;
		refreshToken?: number;
		/** Kayttaja antoi FPL-ID:n tassa: RateTeam hakee joukkueen. */
		onEntry?: (id: string) => void;
		rank?: number | null;
		rankChange?: number | null;
		rankGw?: number | null;
	} = $props();

	/* ---------------- deadline-rivi ---------------- */
	let fantasy = $state<FantasyResponse | null>(null);
	let now = $state(Date.now());
	$effect(() => {
		fetchFantasy().then(
			(d) => (fantasy = d),
			() => (fantasy = null)
		);
		const id = setInterval(() => (now = Date.now()), 60_000);
		return () => clearInterval(id);
	});
	const phase = $derived(weekPhase(fantasy?.meta, now));
	const dl = $derived(phase?.deadline ? formatDeadline(phase.deadline) : null);
	const left = $derived(countdownText(phase?.hoursLeft ?? null));
	const cs = $derived(gwCleanSheets(fantasy));

	/* ---------------- kortti: oma joukkue tai mallin runko ----------------
	   Mallin korttia ei haeta ennen kuin tiedetaan, onko kayttajalla joukkue:
	   kirjautuneen profiili luetaan ensin, muuten tallennetun joukkueen
	   kayttaja naki hetken mallin kortin ja sitten oman. */
	const entryId = $derived(currentEntryId());
	const entryKnown = $derived(
		auth.sessionResolved && (!auth.user || fplEntry.profileChecked === auth.user.id)
	);
	const needModel = $derived(
		entryKnown && !data && !loading && (entryId == null || !!error || picksNotPublished)
	);
	let model = $state<RateTeamResponse | null>(null);
	let modelFailed = $state(false);
	$effect(() => {
		if (!needModel || model || modelFailed) return;
		fetchModelCard().then(
			(d) => (model = d),
			() => (modelFailed = true)
		);
	});
	const card = $derived(data ?? (needModel ? model : null));
	const own = $derived(!!data);

	let entryInput = $state('');
	const entryInputValid = $derived(/^\d{1,10}$/.test(entryInput.trim()));
	function submitEntry(e: SubmitEvent) {
		e.preventDefault();
		if (!entryInputValid) return;
		onEntry?.(entryInput.trim());
	}

	/* ---------------- rivit: model-race ---------------- */
	let race = $state<ModelRaceResponse | null>(null);
	let raceKey: string | null = null;
	$effect(() => {
		const key = String(entryId ?? '-');
		if (raceKey === key) return;
		raceKey = key;
		fetchModelRace(entryId).then(
			(r) => {
				if (raceKey === key) race = r;
			},
			() => {
				if (raceKey === key) race = null;
			}
		);
	});
	const last = $derived(lastCall(race));
	const season = $derived(seasonLine(race));

	let reviewOpen = $state(false);
	let raceOpen = $state(false);
	let beatOpen = $state(false);

	const signed = (n: number) => (n > 0 ? `+${n}` : String(n));
</script>

<section class="week">
	<h2 class="visually-hidden">This week</h2>

	<p class="gw-line">
		{#if phase}
			{#if phase.liveGw != null}
				<span class="live">GW{phase.liveGw} in progress.</span>
				Next deadline: <b>GW{phase.gw}</b>{#if dl}, {dl.when}{dl.tz ? ` ${dl.tz}` : ''}{/if}
			{:else}
				<b>GW{phase.gw}</b> deadline{#if dl}{' '}<span class="when"
						>{dl.when}{dl.tz ? ` ${dl.tz}` : ''}</span
					>{/if}{#if left}{' '}<span class="left">· {left}</span>{/if}
			{/if}
		{:else}
			&nbsp;
		{/if}
	</p>

	<!-- DefCon-live vain kesken kierroksen (A3 5: tauolla se nayttaa
	     paattynytta kierrosta paatosten edella). Komponentti on sama. -->
	{#if phase?.liveGw != null}
		<DefConLive />
	{/if}

	{#if card}
		<DecisionCard
			{card}
			{own}
			{premium}
			{onUpgrade}
			{deadlineUtc}
			{actions}
			{onFollowTransfer}
			{refreshToken}
		/>
	{:else if modelFailed && !loading}
		<div class="decision-skel">
			<p class="muted">Could not load this gameweek's picks right now. Please try again shortly.</p>
		</div>
	{:else}
		<div class="decision-skel" aria-busy="true">
			<p class="muted">{loading ? 'Loading your squad…' : 'Loading this gameweek…'}</p>
		</div>
	{/if}

	{#if own && data}
		<p class="team-line muted">
			{#if fplEntry.savedEntry}Team {fplEntry.savedEntry}{:else if entryId}Team {entryId}{:else}Your draft{/if}
			· <a href="/team">My team</a>
		</p>
	{:else if entryKnown && !loading}
		<form class="entry" onsubmit={submitEntry}>
			<label for="tw-entry">Add your FPL team ID</label>
			<div class="entry-row">
				<input
					id="tw-entry"
					inputmode="numeric"
					autocomplete="off"
					placeholder="e.g. 1234567"
					bind:value={entryInput}
				/>
				<button class="primary" type="submit" disabled={!entryInputValid}>Show my team</button>
			</div>
			{#if error}
				<p class="err">{error}</p>
			{:else if picksNotPublished}
				<p class="muted small">
					FPL has not published this gameweek's squads yet. The model's picks are shown above.
				</p>
			{:else}
				<p class="muted small">
					The number in your FPL Points page address (fantasy.premierleague.com/entry/<strong
						>YOUR-ID</strong
					>/event/...). No login needed.
				</p>
			{/if}
		</form>
	{/if}

	<ul class="rows">
		<!-- Last call: viimeisin kierros mallin sarjassa. -->
		{#if last}
			<li>
				<details bind:open={reviewOpen}>
					<summary><span class="sum">
						<span class="lbl">Last call, GW{last.gw}</span>
						{#if last.kind === 'scored'}
							<span class="vals">
								Model <b>{last.model ?? '–'}</b>{#if last.beforeHits}<span class="tag">before hits</span>{/if}
								{#if last.you != null}· You <b>{last.you}</b>{/if}
								{#if last.average != null}· FPL average <b>{last.average}</b>{/if}
								{#if last.provisional}<span class="tag">provisional</span>{/if}
							</span>
						{:else}
							<span class="vals muted">Not scored for the model</span>
						{/if}
					</span></summary>
					<div class="row-body">
						{#if last.kind === 'unscored'}
							<p class="muted">{last.text}</p>
						{/if}
						{#if reviewOpen}
							{#if entryId != null}
								<GwReview />
							{:else}
								<p class="muted">Add your FPL team ID above for your own gameweek review.</p>
							{/if}
						{/if}
					</div>
				</details>
			</li>
		{/if}

		<!-- Kierroksen clean sheet -rivi: ottelu kerrallaan, ei FDR:aa. -->
		{#if cs && cs.rows.length}
			<li class="plain">
				<a class="row-link" href="/players/clean-sheets">
					<span class="lbl">GW{cs.gw} clean sheets</span>
					<span class="cs">
						{#each cs.rows as r (`${r.team}-${r.opponent}`)}
							<span class="cs-item" title="{r.team} vs {r.opponent} ({r.venue})">
								<b>{r.team}</b> {Math.round(r.cs)}%
								<span class="bar" style="width: {Math.max(4, Math.round(r.cs))}%" aria-hidden="true"></span>
							</span>
						{/each}
					</span>
					<span class="go">All teams ›</span>
				</a>
			</li>
		{/if}

		<!-- Kausi: sina vs malli (tai malli vs keskiarvo ilman joukkuetta). -->
		{#if season}
			<li>
				<details bind:open={raceOpen}>
					<summary><span class="sum">
						{#if season.kind === 'you'}
							<span class="lbl">You vs the model</span>
							<span class="vals"
								><b>{signed(season.diff)}</b> over {season.gameweeks} gameweek{season.gameweeks === 1
									? ''
									: 's'}</span
							>
						{:else}
							<span class="lbl">The model's season</span>
							<span class="vals">{season.text}</span>
						{/if}
					</span></summary>
					<div class="row-body">
						{#if raceOpen}<SeasonRace />{/if}
					</div>
				</details>
			</li>
		{/if}

		<!-- Beat the Model: kirjatut paatokset + mini-liiga. -->
		<li>
			<details bind:open={beatOpen}>
				<summary><span class="sum">
					<span class="lbl">Beat the Model</span>
					<span class="vals">Log your calls against the model's</span>
				</span></summary>
				<div class="row-body">
					{#if beatOpen}
						{#if auth.user}
							<BeatTheModel {rank} {rankChange} {rankGw} />
						{:else}
							<p class="muted">Sign in to log your captain and transfer calls and see who comes out ahead.</p>
						{/if}
						<p><a href="/team/league">Beat the Model league</a></p>
					{/if}
				</div>
			</details>
		</li>
	</ul>
</section>

<style>
	.week {
		margin: 0 0 var(--s-4);
	}
	.visually-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	.gw-line {
		margin: 0 0 var(--s-3);
		font-family: var(--font-mono);
		font-size: 13px;
		color: var(--text-muted);
		min-height: 1.5em;
	}
	.gw-line b {
		color: var(--text);
	}
	.gw-line .when {
		color: var(--accent);
		font-weight: 600;
	}
	.gw-line .live {
		color: var(--positive);
		font-weight: 600;
	}
	.decision-skel {
		border: 1px solid var(--border);
		border-left: 3px solid var(--border-strong);
		min-height: 196px;
		padding: var(--s-4);
		margin: 0 0 var(--s-3);
	}
	.team-line {
		font-size: var(--step--1);
		margin: 0 0 var(--s-3);
	}
	.entry {
		margin: 0 0 var(--s-3);
	}
	.entry label {
		display: block;
		font-size: var(--step--1);
		font-weight: 700;
		margin-bottom: var(--s-1);
	}
	.entry-row {
		display: flex;
		gap: var(--s-2);
	}
	.entry-row input {
		flex: 1;
		min-width: 0;
		min-height: 44px;
	}
	.entry-row button {
		min-height: 44px;
		white-space: nowrap;
	}
	.small {
		font-size: var(--step--1);
		margin: var(--s-1) 0 0;
	}
	.err {
		color: var(--negative);
		font-size: var(--step--1);
		margin: var(--s-1) 0 0;
	}

	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: 1px solid var(--border);
	}
	.rows > li {
		border-bottom: 1px solid var(--border);
	}
	summary,
	.row-link {
		display: flex;
		flex-wrap: nowrap;
		align-items: center;
		gap: 2px var(--s-3);
		padding: var(--s-3) 0;
		min-height: 48px;
		box-sizing: border-box;
		cursor: pointer;
		color: var(--text);
		text-decoration: none;
	}
	summary {
		list-style: none;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary::after,
	.row-link .go {
		margin-left: auto;
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	summary::after {
		content: '›';
		transition: transform 0.15s;
	}
	details[open] > summary::after {
		transform: rotate(90deg);
	}
	.sum {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 2px var(--s-3);
	}
	.row-link {
		flex-wrap: wrap;
	}
	.lbl {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-muted);
		flex: 0 0 auto;
	}
	.vals {
		font-size: var(--step--1);
	}
	.vals b {
		font-variant-numeric: tabular-nums;
	}
	.tag {
		font-family: var(--font-mono);
		font-size: 10px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
		border: 1px solid var(--border);
		padding: 0 4px;
		margin-left: 4px;
	}
	.row-body {
		padding: 0 0 var(--s-3);
	}
	.cs {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-1) var(--s-4);
		font-size: var(--step--1);
		flex: 1 1 60%;
	}
	.cs-item {
		display: inline-flex;
		flex-direction: column;
		min-width: 5.5em;
		font-variant-numeric: tabular-nums;
	}
	.bar {
		display: block;
		height: 3px;
		margin-top: 2px;
		background: var(--accent);
	}
	@media (prefers-reduced-motion: reduce) {
		summary::after {
			transition: none;
		}
	}
</style>
