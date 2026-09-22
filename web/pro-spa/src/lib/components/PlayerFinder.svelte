<script lang="ts">
	/**
	 * Players-ryhman haku ylimpana (22.9.2026, A3 2.3: "haku ylimpana, 1 tap
	 * mista tahansa"). Valinta avaa pelaajakortin sheetina samalle sivulle.
	 *
	 * 🔴 MITATTU A1: pelaajan loytaminen nimella vaati mobiilissa 4 napautusta
	 * + kirjoituksen, koska haku oli vain Player card -tyokalun sisalla.
	 *
	 * Pooli haetaan vasta kun kenttaan tullaan (focusin): /players-sivun
	 * muut nakymat eivat tarvitse sita, ja maksaja saa 555 kB:n vastauksen.
	 * Sama `fetchXp`-lupaus kuin muilla tyokaluilla, joten toista hakua ei
	 * synny jos tyokalu on jo hakenut sen.
	 */
	import { fetchXp, draftPool, type CardPlayer, type XpPoolPlayer } from '$lib/api';
	import { openPlayer } from '$lib/playerSheet.svelte';
	import PlayerSearch from './PlayerSearch.svelte';

	type Row = XpPoolPlayer | CardPlayer;
	let pool = $state<Row[]>([]);
	let loading = false;
	let failed = $state(false);
	let query = $state('');

	function load() {
		if (loading || pool.length > 0) return;
		loading = true;
		fetchXp().then(
			(d) => {
				// Projektiorivit ensin (taydet), sitten kevyet valitsinrivit ja
				// projektiosta poissuljetut, jotta kaikki FPL:n pelaajat loytyvat.
				const rows: Row[] = draftPool(d);
				const seen = new Set(rows.map((p) => p.id));
				for (const p of d.excluded ?? []) if (!seen.has(p.id)) rows.push(p);
				pool = rows;
				loading = false;
			},
			() => {
				failed = true;
				loading = false;
			}
		);
	}

	// Sama normalisointi kuin PlayerCard/FitChecker-haussa (#145/#147).
	function norm(s: string): string {
		return s
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase()
			.replace(/ø/g, 'o')
			.replace(/['’ʼ]/g, '')
			.replace(/[-.]/g, ' ')
			.trim();
	}
	const matches = $derived.by(() => {
		const q = norm(query);
		if (q.length < 2) return [];
		return pool
			.filter(
				(p) =>
					norm(p.web_name).includes(q) ||
					(p.full_name ? norm(p.full_name).includes(q) : false) ||
					norm(p.team_short).includes(q)
			)
			.slice(0, 8);
	});
</script>

<div class="finder" onfocusin={load}>
	<PlayerSearch
		id="players-finder"
		label="Search players"
		placeholder="Name or team (e.g. Haaland, ARS)"
		bind:query
		items={matches}
		onSelect={(p) => {
			query = '';
			openPlayer(p.id, 'players_search');
		}}
	/>
	{#if failed}
		<p class="muted small">Could not load the player list right now. Please try again shortly.</p>
	{/if}
</div>

<style>
	.finder {
		margin: 0 0 var(--s-3);
	}
	.finder :global(label) {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	.finder :global(input) {
		width: 100%;
		min-height: 44px;
	}
	.small {
		font-size: var(--step--1);
		margin: var(--s-1) 0 0;
	}
</style>
