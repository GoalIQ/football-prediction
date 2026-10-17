<script lang="ts">
	/**
	 * Paatoskortti (22.9.2026, UX-uudistus A3 2.1 + kilpailija-malli K1).
	 *
	 * This week -sivun ensimmainen asia: kenet kapteeniksi, mita siirretaan,
	 * mita chippia. Yksi kortti, kolme valilehtea, ei uutta nakymaa (A2
	 * saanto 16). Ennen tata sama tieto oli kolmessa lohkossa allekkain ja
	 * kapteeni luki lauseen keskella ("Captain suggestion: ...").
	 *
	 * KAIKKI LUVUT OVAT PALVELIMEN: kortti lukee joko kayttajan oman joukkueen
	 * rate-team-vastauksen (`card`) tai mallin kapteenin
	 * (`model` = `modelCaptainCard(/api/fantasy/model-captain)`, $lib/weekRows).
	 * Kapteeni, lahin vaihtoehto, siirto ja hold-kanta tulevat backendista;
	 * klientti ei lajittele eika laske. Lahin vaihtoehto naytetaan vain kun
	 * palvelin antaa sen (`captain.alternative`: se tulee vain kun ero on pieni).
	 *
	 * Premium-raja on palvelimen: ilmaisvastauksessa siirtoehdotuksia ei ole
	 * (`mask_rate_team_payload`), joten kortti ei voi naytta niita vaikka
	 * haara olisi vaarin. Mallin kortti ei kanna siirtoja lainkaan.
	 *
	 * 17.10.2026 (tyokalut taakse, spec rivit 3-4): OMAN joukkueen kapteeni,
	 * siirto, chipit ja hold-verdikti ovat Premiumia kokonaan. Lukitus tulee
	 * $lib/personalLock-lukijasta (`ownLocked`): ei Premiumia TAI palvelin
	 * lukitsi rate-team-vastauksen. Lukittuna kortti nayttaa MALLIN kapteenin
	 * (`model`, /api/fantasy/model-captain, sisaltoa) ja lukon omille
	 * paatoksille. Ennen 17.10 ilmainen naki oman kapteenin ja hold-verdiktin,
	 * ja vain siirtopari oli lukittu (`decision_transfer_lock`).
	 */
	import type { RateTeamResponse } from '$lib/fantasyTools';
	import { personalLock } from '$lib/personalLock';
	import PersonalLock from './PersonalLock.svelte';
	import { CHIP_NAMES } from '$lib/fantasyTools';
	import { modelSourceLine, NO_FIXTURE, type ModelCaptainCard } from '$lib/weekRows';
	import { xpHorizon } from '$lib/xpHorizon';
	import { openPlayer } from '$lib/playerSheet.svelte';
	import { transferTag } from '$lib/transferLabel';
	import { capture } from '$lib/analytics';
	import WeeklyActions, { type WeeklyAction } from './WeeklyActions.svelte';
	import HoldVerdictCard from './HoldVerdictCard.svelte';

	type Tab = 'captain' | 'transfer' | 'chip';

	let {
		card = null,
		model = null,
		premium = false,
		onUpgrade,
		deadlineUtc = null,
		actions = [],
		onFollowTransfer,
		refreshToken = 0
	}: {
		/** Kayttajan oma joukkue (rate-team). Annettuna voittaa mallin kortin. */
		card?: RateTeamResponse | null;
		/** Mallin kapteeni ilman omaa joukkuetta (/api/fantasy/model-captain). */
		model?: ModelCaptainCard | null;
		premium?: boolean;
		/** Avaa upgrade-nakyman. Ei kirjaa tapahtumaa: PersonalLock kirjaa
		 *  `upgrade_tapped {source: 'personal_lock_this-week'}`. */
		onUpgrade?: () => void;
		deadlineUtc?: string | null;
		/** Kirjattavat paatokset (vain omalle joukkueelle). */
		actions?: WeeklyAction[];
		onFollowTransfer?: (choice: Record<string, unknown>) => boolean;
		refreshToken?: number;
	} = $props();

	/** 17.10: oma joukkue on annettu mutta sen paatokset ovat lukittuja. */
	const ownLocked = $derived(card != null && personalLock(premium, card));
	/** Oma joukkue jonka paatokset saa nayttaa, tai null (mallin kortti). */
	const mine = $derived(ownLocked ? null : card);
	/** true = kayttajan oma joukkue, false = mallin kortti. */
	const own = $derived(mine != null);

	let tab = $state<Tab>('captain');
	function pick(t: Tab) {
		tab = t;
		capture('decision_tab_opened', { tab: t, own, locked: ownLocked });
	}

	/** Kierros jolle kapteeni on laskettu (kesken kierroksen deadline-GW). */
	const capGw = $derived(
		mine
			? (mine.meta.captain_gw ?? (mine.meta.gw_in_progress === true ? null : mine.meta.gw))
			: (model?.gw ?? null)
	);
	const cap = $derived(mine ? (mine.captain?.pick ?? null) : (model?.captain ?? null));
	const alt = $derived(mine ? (mine.captain?.alternative ?? null) : (model?.alt ?? null));
	/** Kapteenin vastustaja(t): oma kortti rungon pelaajarivista, mallin kortti
	 *  lukijalta (`captain.opponents`: [] = ei ottelua, null = ei rivia). */
	const capOpp = $derived.by(() => {
		if (!mine) return model?.opp ?? null;
		if (!cap || capGw == null) return null;
		const row = mine.team?.players?.find((p) => p.id === cap.id);
		const g = row?.gameweeks?.find((x) => x.gw === capGw);
		if (!g) return null;
		if (g.opponents.length === 0) return NO_FIXTURE;
		return g.opponents.map((o) => `${o.opp} (${o.venue})`).join(', ');
	});
	/** Mallin kortin tarkistusreitti: lahde palvelimen `meta.source`sta. */
	const src = $derived(
		!mine && model
			? modelSourceLine(model.source)
			: null
	);

	const sug = $derived(mine?.transfers?.suggestions?.[0] ?? null);
	const verdict = $derived(mine?.transfers?.hold_verdict ?? null);
	const span = $derived.by(() => {
		const n = verdict?.horizon_gws ?? mine?.meta.transfer_horizon_gw;
		return typeof n === 'number' ? `${n}-GW horizon` : xpHorizon(mine?.meta).span;
	});

	const chips = $derived(mine?.meta?.chips ?? null);
	const chipsNow = $derived((chips?.remaining ?? []).filter((c) => c.available_now));
	const chipsLater = $derived((chips?.remaining ?? []).filter((c) => !c.available_now));
	const chipName = (c: string) => CHIP_NAMES[c] ?? c;

	const actionFor = (k: 'captain' | 'transfer') => actions.filter((a) => a.kind === k);
</script>

<section class="decision" aria-label="This week's decisions">
	<div class="tabs" role="tablist" aria-label="Decision">
		{#each [['captain', 'Captain'], ['transfer', 'Transfer'], ['chip', 'Chip']] as [id, label] (id)}
			<button
				type="button"
				role="tab"
				id="dc-tab-{id}"
				aria-selected={tab === id}
				aria-controls="dc-panel"
				class:on={tab === id}
				onclick={() => pick(id as Tab)}>{label}</button
			>
		{/each}
	</div>

	<div class="panel" id="dc-panel" role="tabpanel" aria-labelledby="dc-tab-{tab}">
		{#if tab === 'captain'}
			{#if cap}
				<p class="k">
					{own ? 'Suggested captain' : "The model's captain"}{#if capGw != null}, GW{capGw}{/if}
				</p>
				<p class="pick">
					<button type="button" class="name" onclick={() => openPlayer(cap.id, 'decision_card')}
						>{cap.web_name}</button
					>
					<span class="team">{cap.team_short}</span>
					{#if cap.gw_xp != null}<span class="xp"
							>{cap.gw_xp.toFixed(1)} <abbr title="Expected points from the GoalIQ match model">xP</abbr></span
						>{/if}
				</p>
				{#if capOpp}<p class="opp muted">{capOpp === NO_FIXTURE ? 'No fixture this gameweek' : `vs ${capOpp}`}</p>{/if}
				{#if src}
					<!-- Tarkistusreitti (22.9). Lahde on palvelimen `meta.source`:
					     entry_picks = FPL:n julkaisemat pickit (linkki FPL:n entry-
					     sivulle), frozen = mallin jaadytetty runko (linkki
					     goaliq.app/fpl#gw-calls, jossa sama kapteeni on lokissa).
					     Teksti tulee lukijalta `modelSourceLine` ($lib/weekRows). -->
					<p class="src-line muted">
						{src.before}{#if src.href}<a href={src.href} rel="noopener" target="_blank">{src.link}</a
							>{:else}{src.link}{/if}{src.after}
					</p>
				{/if}
				{#if alt}
					<p class="next">
						Next:
						<button type="button" class="name small" onclick={() => openPlayer(alt.id, 'decision_card')}
							>{alt.web_name}</button
						>
						<span class="muted">{alt.team_short}</span>
						{#if alt.gw_xp != null}{alt.gw_xp.toFixed(1)} xP.{/if} Close call.
					</p>
				{/if}
				{#if own}
					<WeeklyActions
						bare
						gw={capGw}
						{deadlineUtc}
						actions={actionFor('captain')}
						{onFollowTransfer}
						{refreshToken}
					/>
				{/if}
			{:else if !ownLocked}
				<p class="muted">No captain projection for this gameweek yet.</p>
			{/if}
			{#if ownLocked}
				<!-- 17.10: mallin kapteeni ylla on sisaltoa; oman XI:n kapteeni on
				     Premiumia (palvelin: captain null lukitussa rate-teamissa). -->
				<PersonalLock tool="this-week" {onUpgrade} compact />
			{/if}
		{:else if tab === 'transfer'}
			{#if ownLocked}
				<p class="k">Transfer</p>
				<PersonalLock tool="this-week" {onUpgrade} compact />
			{:else if !mine}
				<p class="k">Transfer</p>
				<p>Add your FPL team ID below and the model checks transfers for your own squad.</p>
			{:else if premium && sug && !mine.transfers.hold}
				<p class="k">Transfer</p>
				<p class="move">
					<span class="muted">Out</span>
					<button type="button" class="name small" onclick={() => openPlayer(sug.out.id, 'decision_card')}
						>{sug.out.web_name}</button
					>
					<span class="team">{transferTag(sug.pos, sug.out.team_short)}</span>
					<span class="arrow" aria-hidden="true">→</span>
					<span class="muted">In</span>
					<button type="button" class="name small" onclick={() => openPlayer(sug.in.id, 'decision_card')}
						>{sug.in.web_name}</button
					>
					<span class="team">{transferTag(sug.pos, sug.in.team_short)}</span>
				</p>
				<p class="muted">
					{sug.delta_xp_horizon >= 0 ? '+' : ''}{sug.delta_xp_horizon.toFixed(1)} xP over the {span},
					{sug.delta_cost >= 0 ? '+' : ''}{sug.delta_cost.toFixed(1)}m.
				</p>
				<WeeklyActions
					bare
					gw={capGw}
					{deadlineUtc}
					actions={actionFor('transfer')}
					{onFollowTransfer}
					{refreshToken}
				/>
			{:else if verdict}
				<HoldVerdictCard {verdict} surface="this_week" />
			{:else}
				<p class="muted">No transfer call for this squad yet.</p>
			{/if}
			<p class="more-link">
				<a href="/team/transfer-planner">Plan several gameweeks: Transfer planner</a>{#if !premium}<span
						class="lock"
						aria-label="Premium">Premium</span
					>{/if}
			</p>
		{:else}
			<p class="k">Chip</p>
			{#if ownLocked}
				<PersonalLock tool="this-week" {onUpgrade} compact />
			{:else if !mine}
				<p>Add your FPL team ID below to see which chips you still have.</p>
			{:else if chips}
				{#if chipsNow.length}
					<p>Available this gameweek: <strong>{chipsNow.map((c) => chipName(c.name)).join(', ')}</strong>.</p>
				{:else}
					<p>No chip is available this gameweek.</p>
				{/if}
				{#if chipsLater.length}
					<p class="muted">
						Later: {chipsLater.map((c) => `${chipName(c.name)} from GW${c.from_gw}`).join(', ')}.
					</p>
				{/if}
				{#if chips.played.length}
					<p class="muted">
						Played: {chips.played.map((c) => `${chipName(c.name)} GW${c.gw}`).join(', ')}.
					</p>
				{/if}
			{:else}
				<p class="muted">Chip status is not available for this squad.</p>
			{/if}
			<p class="more-link">
				<a href="/team/chip-timing">Best windows to play them: Chip timing</a>{#if !premium}<span
						class="lock"
						aria-label="Premium">Premium</span
					>{/if}
			</p>
		{/if}
	</div>
</section>

<style>
	.decision {
		border: 1px solid var(--border-strong);
		border-left: 3px solid var(--accent);
		background: var(--surface);
		margin: 0 0 var(--s-3);
	}
	.tabs {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		border-bottom: 1px solid var(--border);
	}
	.tabs button {
		min-height: 44px;
		font: inherit;
		font-size: 14px;
		font-weight: 600;
		color: var(--text-muted);
		background: transparent;
		border: 0;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		cursor: pointer;
	}
	.tabs button.on {
		color: var(--text);
		border-bottom-color: var(--accent);
	}
	.panel {
		padding: var(--s-3) var(--s-4) var(--s-4);
		/* Valilehden vaihto ei saa siirtaa alla olevia riveja paljon: varattu
		   korkeus kattaa kapteenin (yleisin) kokonaan. */
		min-height: 166px;
	}
	.panel p {
		margin: 0 0 var(--s-2);
	}
	.k {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	.pick {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--s-2);
	}
	.name {
		font: inherit;
		font-size: var(--step-2);
		font-weight: 700;
		color: var(--text);
		background: none;
		border: 0;
		padding: 0;
		min-height: 0;
		cursor: pointer;
		text-decoration: underline;
		text-decoration-color: var(--border-strong);
		text-underline-offset: 4px;
	}
	.name.small {
		font-size: inherit;
	}
	.team {
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	.xp {
		margin-left: auto;
		font-size: var(--step-2);
		font-weight: 700;
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}
	.xp abbr {
		font-size: 0.6em;
		text-decoration: none;
	}
	.opp {
		font-size: var(--step--1);
	}
	.src-line {
		font-size: var(--step--1);
	}
	.move {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--s-2);
	}
	.arrow {
		color: var(--accent);
	}
	.more-link {
		margin-top: var(--s-3) !important;
		font-size: var(--step--1);
	}
	.lock {
		font-family: var(--font-mono);
		font-size: 0.75em;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--accent);
		border: 1px solid var(--accent);
		padding: 0.1em 0.35em;
		margin-left: 0.5em;
	}
</style>
