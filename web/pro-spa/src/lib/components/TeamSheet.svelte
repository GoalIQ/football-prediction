<script lang="ts">
	/**
	 * Joukkuepaneeli sheetina (PRO-JOUKKUENAKYMA, Villen paatos 27.9.2026).
	 * Yksi instanssi AppShellissa, sama runko kuin PlayerSheetilla. Aukeaa
	 * seuran lyhenteesta (pelaajakortti, Teams, Clean sheets) ja goaliq.appin
	 * klubisivulta `?team=ARS`. Luvut: $lib/teamPanel (samat lukijat kuin
	 * muilla pinnoilla).
	 */
	import { onMount, tick } from 'svelte';
	import { capture } from '$lib/analytics';
	import { fetchFantasy, fetchXp, type FantasyResponse, type XpResponse } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import { teamPanel, teamParam } from '$lib/teamPanel';
	import {
		closeTeam,
		openTeam,
		teamOnTop,
		teamPlayerRowClick,
		teamSheet
	} from '$lib/teamSheet.svelte';
	import { playerSheet } from '$lib/playerSheet.svelte';
	import { teamColorByShort } from '$lib/teamColors';
	import TeamKit from './TeamKit.svelte';

	let closeBtn = $state<HTMLButtonElement | null>(null);
	let returnTo: HTMLElement | null = null;
	let fantasy = $state<FantasyResponse | null>(null);
	let xp = $state<XpResponse | null>(null);
	let failed = $state(false);
	let xpFailed = $state(false);

	onMount(() => {
		const url = new URL(window.location.href);
		const short = teamParam(url.searchParams.get('team'));
		if (!short) return;
		openTeam(short, 'club_page');
		// Parametri pois osoitteesta: paivitys ei avaa paneelia uudelleen
		// sen jalkeen kun lukija on sulkenut sen. Muut parametrit (ref) jaavat.
		url.searchParams.delete('team');
		history.replaceState(history.state, '', url.pathname + url.search + url.hash);
	});

	// Avaus: analytiikka, vieritys ja fokus. Riippuu VAIN paneelin seurasta,
	// jottei kirjautuminen kesken avauksen laukaise tapahtumaa uudelleen.
	$effect(() => {
		const short = teamSheet.short;
		if (short == null) return;
		capture('team_sheet_opened', { source: teamSheet.source, team: short });
		returnTo = document.activeElement as HTMLElement | null;
		const prev = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		void tick().then(() => closeBtn?.focus());
		return () => {
			// Pelaajakortti voi olla yha auki paneelin alla: se palauttaa
			// vierityksen itse kun se suljetaan.
			if (playerSheet.id == null) document.body.style.overflow = prev;
			returnTo?.focus?.();
		};
	});

	// Data: haetaan kun paneeli on auki. Premium-tila luetaan auth.sub:sta,
	// jotta kirjautuminen hakee maskaamattoman listan uudelleen (fetchXp
	// hoitaa valimuistin).
	$effect(() => {
		if (teamSheet.short == null) return;
		void auth.sub;
		failed = false;
		xpFailed = false;
		fetchFantasy().then(
			(d) => (fantasy = d),
			() => (failed = true)
		);
		fetchXp().then(
			(d) => (xp = d),
			() => (xpFailed = true)
		);
	});

	const panel = $derived(teamSheet.short ? teamPanel(fantasy, xp, teamSheet.short) : null);
	const kit = $derived(panel ? teamColorByShort(panel.short) : null);
	const anyFar = $derived(panel?.fixtures.some((g) => g.items.some((f) => f.cs == null)) ?? false);

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && teamOnTop()) closeTeam();
	}
</script>

<svelte:window onkeydown={onKey} />

{#if teamSheet.short != null}
	<div class="backdrop" class:above={teamSheet.above} aria-hidden="true" onclick={closeTeam}></div>
	<div class="sheet" class:above={teamSheet.above} role="dialog" aria-modal="true" aria-label="Club">
		<div class="sheet-head">
			<span class="sheet-title">Club</span>
			<button type="button" class="sheet-close" bind:this={closeBtn} onclick={closeTeam}>Close</button>
		</div>
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="sheet-body" onclick={teamPlayerRowClick}>
			{#if failed}
				<p class="banner error">Could not load club data right now. Please try again shortly.</p>
			{:else if !fantasy}
				<p class="muted">Loading…</p>
			{:else if !fantasy.meta?.available}
				<!-- Datakatko (empty_phase0) EI ole "seuraa ei ole" (tarkistaja 27.9 B3). -->
				<p class="muted">Club data is not available right now. Please try again shortly.</p>
			{:else if !panel}
				<p class="muted">No Premier League club with the code {teamSheet.short} this season.</p>
			{:else}
				<div class="club-head">
					{#if kit}
						<TeamKit color={kit.color} textColor={kit.textColor} label={panel.short} size={40} />
					{/if}
					<h2>{panel.name}</h2>
				</div>

				<h3>Fixtures</h3>
				{#if panel.avgCs != null && panel.avgRange}
					<p class="muted small">
						Average clean sheet chance, {panel.avgRange}: {Math.round(panel.avgCs)}%
					</p>
				{/if}
				{#if panel.fixtures.length === 0}
					<p class="muted">No fixtures left this season.</p>
				{/if}
				<table class="fx">
					<tbody>
						{#each panel.fixtures as g (g.gw)}
							{#if g.items.length === 0}
								<tr><td class="gw">GW{g.gw}</td><td class="muted">Blank</td><td></td></tr>
							{:else}
								{#each g.items as f, i (g.gw + '-' + i)}
									<tr>
										<td class="gw">GW{g.gw}</td>
										<td><abbr title={f.opponentName}>{f.opponent}</abbr> ({f.venue})</td>
										<td class="num">{f.cs != null ? `${Math.round(f.cs)}% CS` : ''}</td>
									</tr>
								{/each}
							{/if}
						{/each}
					</tbody>
				</table>
				<!-- EI meta.far_basis_label: se lupaa vaikeusluvun ("Fixture
				     difficulty only"), jota paneeli ei nayta (tarkistaja 27.9 B2). -->
				{#if anyFar}
					<p class="muted small">
						Rows without a number: clean sheet % appears as each gameweek moves closer.
					</p>
				{/if}

				<h3>Players by projected points, {panel.window}</h3>
				{#if panel.players}
					<table class="squad">
						<thead>
							<tr>
								<th>Player</th>
								<th>Pos</th>
								<th class="num">Price</th>
								<th class="num"><abbr title="Our projected chance of starting, not a lineup leak">Start</abbr></th>
								<th class="num">xP</th>
							</tr>
						</thead>
						<tbody>
							{#each panel.players as p (p.id)}
								<tr data-player-id={p.id}>
									<td>{p.name}</td>
									<td>{p.pos}</td>
									<td class="num">{p.price != null ? p.price.toFixed(1) : '–'}</td>
									<td class="num">{p.start != null ? `${p.start}%` : '–'}</td>
									<td class="num">{p.xp.toFixed(1)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else if xpFailed}
					<p class="muted">Could not load projections right now. Please try again shortly.</p>
				{:else if panel.masked}
					<p>
						The {panel.name} squad by projected points, with start chances, is in
						<a href="/?tab=premium" data-sveltekit-reload>Premium</a>.
					</p>
				{:else}
					<p class="muted">Loading…</p>
				{/if}

				{#if panel.clubUrl}
					<p class="small">
						Set-piece takers and a predicted XI are on the free
						<a href={panel.clubUrl} target="_blank" rel="noopener">{panel.name} page</a>.
					</p>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 48;
		background: rgba(11, 10, 9, 0.66);
	}
	.sheet {
		position: fixed;
		z-index: 49;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(460px, 100vw);
		display: flex;
		flex-direction: column;
		background: var(--bg);
		border-left: 1px solid var(--border-strong);
	}
	/* Avattu pelaajakortin paalle (PlayerSheet z 50/51). */
	.backdrop.above {
		z-index: 52;
	}
	.sheet.above {
		z-index: 53;
	}
	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--s-3);
		padding: var(--s-3) var(--s-4);
		border-bottom: 1px solid var(--border);
	}
	.sheet-title {
		font-family: var(--font-mono);
		font-size: 11.5px;
		font-weight: 700;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	.sheet-close {
		min-height: 40px;
		font-size: 13px;
	}
	.sheet-body {
		flex: 1;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding: var(--s-4);
	}
	.club-head {
		display: flex;
		align-items: center;
		gap: var(--s-3);
	}
	.club-head h2 {
		margin: 0;
	}
	h3 {
		margin: var(--s-4) 0 var(--s-2);
		font-size: 14px;
	}
	.small {
		font-size: 13px;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 14px;
	}
	td,
	th {
		padding: 6px 4px;
		border-bottom: 1px solid var(--border);
		text-align: left;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.gw {
		width: 52px;
		color: var(--text-muted);
	}
	.squad tbody tr {
		cursor: pointer;
	}
	@media (max-width: 640px) {
		.sheet {
			top: auto;
			left: 0;
			width: 100vw;
			max-height: 88vh;
			border-left: 0;
			border-top: 1px solid var(--border-strong);
		}
	}
</style>
