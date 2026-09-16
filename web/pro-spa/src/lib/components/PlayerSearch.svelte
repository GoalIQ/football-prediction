<script lang="ts" module>
	// UX-palaute-erä (25.7): jaettu pelaajahaku-combobox (fit checker,
	// draft-picker, player card). Kohta 6 (a11y): nuolinäppäimet siirtävät
	// aktiivista riviä, Enter valitsee, Esc tyhjentää haun — fokus pysyy
	// kentässä (combobox-kaava, aria-activedescendant). Kohta 2: rivillä
	// hinta + owned% kun payload tuo ne (defensiivinen — vanha payload ei
	// tuo, rivi renderöityy silti).
	export type SearchItem = {
		id: number;
		web_name: string;
		team_short: string;
		pos: string;
		price?: number;
		owned_pct?: number;
		/** FPL:n virallinen status (a/d/i/s/u/n) — defensiivinen. */
		status?: string;
		/** false = ei mukana projektiossa. Tällaisia EI suodateta pois hausta:
		 * pelaaja pitää löytyä myös silloin kun hänelle ei lasketa xP:tä. */
		in_projection?: boolean;
	};
</script>

<script lang="ts" generics="T extends SearchItem">
	import { availabilityFlag } from '$lib/availabilityFlag';
	let {
		id,
		label,
		placeholder = 'Player or team (e.g. Haaland, ARS)',
		query = $bindable(''),
		items,
		onSelect
	}: {
		id: string;
		label: string;
		placeholder?: string;
		query?: string;
		items: T[];
		onSelect: (p: T) => void;
	} = $props();

	// Aktiivinen rivi seuraa tuloslistaa: uusi haku → valinta alkuun.
	let active = $state(0);
	$effect(() => {
		void items;
		active = 0;
	});

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			query = '';
			return;
		}
		if (items.length === 0) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			active = (active + 1) % items.length;
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			active = active <= 0 ? items.length - 1 : active - 1;
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const p = items[Math.min(active, items.length - 1)];
			if (p) onSelect(p);
		}
	}

	/* Saatavuusmerkki riville: pelaaja loytyy hausta vaikka han olisi ulkona,
	   mutta rivi kertoo sen heti.

	   16.9: merkki tuli ennen tasta funktiosta ja palautti `out` KAHDESTA eri
	   syysta (FPL:n lippu / ei projektiota). Ne eivat ole sama asia — mitattu
	   samana paivana: Lewis (MCI) ei ole projektiossa mutta FPL sanoo `a`, ja
	   rivi vaitti hanesta "out". Lisaksi `out` on kierrokseton, ja
	   julkaisuportti hylkasi juuri sen muodon korttisaatteelta. Nyt merkki
	   tulee jaetusta lukijasta joka erottaa nelja tapausta. */
	const flag = availabilityFlag;

	function stats(p: SearchItem): string {
		const parts: string[] = [];
		if (typeof p.price === 'number' && p.price > 0) parts.push(`${p.price.toFixed(1)}m`);
		if (typeof p.owned_pct === 'number') parts.push(`${p.owned_pct.toFixed(1)}% owned`);
		return parts.join(' · ');
	}
</script>

<label for={id}>{label}</label>
<input
	{id}
	type="search"
	role="combobox"
	autocomplete="off"
	aria-expanded={items.length > 0}
	aria-controls="{id}-listbox"
	aria-activedescendant={items.length > 0 ? `${id}-opt-${active}` : undefined}
	{placeholder}
	bind:value={query}
	onkeydown={onKeydown}
/>
{#if items.length > 0}
	<div class="results" id="{id}-listbox" role="listbox" aria-label="Matching players">
		{#each items as p, i (p.id)}
			<button
				type="button"
				id="{id}-opt-{i}"
				role="option"
				aria-selected={i === active}
				class="picker-row"
				class:kbd-active={i === active}
				onclick={() => onSelect(p)}
				onmousemove={() => (active = i)}
			>
				<strong>{p.web_name}</strong>
				<span class="muted">{p.team_short} · {p.pos}</span>
				{#if flag(p)}
					{@const f = flag(p)}
					{#if f}<span class="flag {f.tone}">{f.text}</span>{/if}
				{/if}
				{#if stats(p)}
					<span class="stats muted">{stats(p)}</span>
				{/if}
			</button>
		{/each}
	</div>
{/if}

<style>
	.picker-row {
		display: flex;
		gap: 8px;
		align-items: baseline;
		width: 100%;
		text-align: left;
		background: var(--surface-2);
		border: none;
		border-radius: var(--radius);
		padding: 8px 10px;
		margin-top: 4px;
		cursor: pointer;
	}
	/* Näppäimistöllä aktiivinen rivi: sama fokuskieli kuin :focus-visible
	   (fokus pysyy inputissa, joten rivi tarvitsee oman merkin). */
	.picker-row.kbd-active {
		outline: 2px solid var(--accent-strong);
		outline-offset: -2px;
	}
	.flag {
		font-size: var(--step--1);
		font-weight: 700;
		border-radius: var(--radius);
		padding: 0 8px;
		white-space: nowrap;
	}
	.flag.out {
		background: rgba(255, 138, 92, 0.12);
		color: var(--negative);
	}
	/* 16.9: "no xP" ei ole saatavuusvaite vaan tieto MEIDAN luvustamme, joten
	   se ei saa kantaa punaista/keltaista. Neutraali sävy erottaa sen. */
	.flag.muted {
		background: var(--surface-2);
		color: var(--text-muted);
	}
	.flag.warn {
		background: rgba(255, 201, 60, 0.2);
		color: var(--warn-text);
	}
	.stats {
		margin-left: auto;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
