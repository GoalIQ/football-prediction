<script lang="ts">
	/** Ryhman sisainen navigaatio: valitsin + tyokalut (22.9.2026, A3).
	 *
	 * 4.9 tama korvasi "On this page:" -ankkuririvin (jokainen kohde oma URL).
	 * 22.9 rivi sai ryhmakohtaisen rakenteen rekisterista:
	 *   - My team:  ( Squad | Transfers | Chips ) + osion tyokalut
	 *   - Players:  haku ylimpana, ( Players | Teams ), esiasetukset
	 *               Captain / xP / Value / Differentials / Price change,
	 *               loput pelaajatyokalut "More player tools" -avattavassa
	 *   - Matches:  ( Fixtures | Predict | Table )
	 *
	 * 🔴 MIKSI: 22.9 mitattu 390 px:lla Players-ryhman kaksitoista linkkia
	 * veivat ~250 px ennen sisaltoa (w-spa.md T3-mittaus), ja My teamin
	 * kahdeksan tyokalua olivat yhta tasoa. Valitsimessa on enintaan kolme
	 * segmenttia (A2 saanto 5), ja harvemmin kaytetyt ovat yhden napautuksen
	 * paassa samassa nakymassa (A2 saanto 8, progressive disclosure).
	 *
	 * Kaikki kohteet ovat tyokalujen omia reitteja: esiasetus on linkki, joten
	 * paluunappi ja jaettu URL toimivat. Rakenne tulee rekisterista
	 * (`sectionsFor`, `PLAYER_PRESETS`); tama komponentti ei maarittele omaa.
	 */
	import {
		PLAYER_PRESETS,
		findTool,
		primaryTool,
		sectionOf,
		sectionsFor,
		toolPath,
		type Tool
	} from '$lib/tools';
	import { xpHorizon, type HorizonMeta } from '$lib/xpHorizon';
	import PlayerFinder from './PlayerFinder.svelte';

	let {
		tools,
		group,
		active = null,
		all = false,
		premium = false,
		horizonMeta = null
	}: {
		tools: Tool[];
		group: string;
		active?: string | null;
		/** ?all=1 aktiivisena: pinottu nakyma. */
		all?: boolean;
		premium?: boolean;
		/** xP-vastauksen meta esiasetuksen nimeen ("xP 6 GWs"). */
		horizonMeta?: HorizonMeta | null;
	} = $props();

	const sections = $derived(sectionsFor(group));
	const section = $derived(sectionOf(group, all ? null : active));
	/** Ryhman paatyokalun kanoninen osoite on ryhman juuri (/team, /players). */
	function hrefFor(slug: string): string {
		const t = findTool(group, slug);
		if (!t) return `/${group}`;
		return primaryTool(group)?.slug === slug ? `/${group}` : toolPath(t);
	}
	function locked(slug: string): boolean {
		return !premium && findTool(group, slug)?.tier === 'premium';
	}
	const presetSlugs = new Set(PLAYER_PRESETS.map((p) => p.slug));
	const showPresets = $derived(group === 'players' && section?.id === 'players');
	/** Osion tyokalut valitsimen alla (esiasetukset eivat toistu tassa). */
	const sectionTools = $derived(
		(section?.tools ?? [])
			.filter((s) => !(showPresets && presetSlugs.has(s)))
			.map((s) => findTool(group, s))
			.filter((t): t is Tool => !!t)
	);
	const moreOpen = $derived(showPresets && !!active && !presetSlugs.has(active) && !all);
	const hz = $derived(xpHorizon(horizonMeta));
	function presetLabel(label: string, horizon?: boolean): string {
		return horizon && hz.count != null && hz.count > 0 ? `${label} ${hz.gws}` : label;
	}
</script>

{#if group === 'players'}
	<PlayerFinder />
{/if}

{#if sections && tools.length > 1}
	<nav class="seg" aria-label="Views">
		{#each sections as s (s.id)}
			<a
				href={hrefFor(s.lead)}
				class:active={section?.id === s.id && !all}
				aria-current={section?.id === s.id && !all ? 'page' : undefined}>{s.label}</a
			>
		{/each}
	</nav>
{/if}

{#if showPresets}
	<nav class="presets" aria-label="Sort players">
		<span class="presets-lbl" aria-hidden="true">Sort</span>
		{#each PLAYER_PRESETS as p (p.slug)}
			<a
				href={hrefFor(p.slug)}
				class="chip"
				class:hz={p.horizon}
				class:active={active === p.slug && !all}
				aria-current={active === p.slug && !all ? 'page' : undefined}
				>{presetLabel(p.label, p.horizon)}{#if locked(p.slug)}<span
						class="lock"
						aria-label="Premium">Premium</span
					>{/if}</a
			>
		{/each}
	</nav>
	<details class="more" open={moreOpen}>
		<summary>More player tools</summary>
		<nav class="tool-row" aria-label="More player tools">
			{#each sectionTools as t (t.slug)}
				<a href={hrefFor(t.slug)} class:active={active === t.slug && !all}>
					{t.title}{#if locked(t.slug)}<span class="lock" aria-label="Premium">Premium</span>{/if}
				</a>
			{/each}
			<!-- 11.9: pinottu nakyma viimeisena ja lyhyella nimella; se on
			     poikkeus, ei ensimmainen vaihtoehto. -->
			<a href="/{group}?all=1" class="all" class:active={all} title="Every tool in this group on one long page">All</a>
		</nav>
	</details>
{:else if sectionTools.length > 1}
	<nav class="tool-row" aria-label="Tools in this view">
		{#each sectionTools as t (t.slug)}
			<a href={hrefFor(t.slug)} class:active={active === t.slug && !all}>
				{t.title}{#if locked(t.slug)}<span class="lock" aria-label="Premium">Premium</span>{/if}
			</a>
		{/each}
		<a href="/{group}?all=1" class="all" class:active={all} title="Every tool in this group on one long page">All</a>
	</nav>
{/if}

<style>
	/* Segmentoitu valitsin: yksi rivi, tasalevyiset kohdat. */
	.seg {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: minmax(0, 1fr);
		border: 1px solid var(--border-strong);
		margin: 0 0 var(--s-3);
	}
	.seg a {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 40px;
		padding: 0 var(--s-2);
		color: var(--text-muted);
		font-size: 14px;
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}
	.seg a + a {
		border-left: 1px solid var(--border-strong);
	}
	.seg a:hover {
		color: var(--text);
		text-decoration: none;
	}
	.seg a.active {
		color: var(--accent-contrast);
		background: var(--accent);
	}

	.presets {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-2);
		margin: 0 0 var(--s-2);
	}
	.presets-lbl {
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--faint);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		min-height: 34px;
		padding: 0 10px;
		border: 1px solid var(--border-strong);
		color: var(--text-muted);
		font-size: var(--step--1);
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}
	/* Varaa leveys "xP 6 GWs" -nimelle, jotta nimen taydentyminen metan
	   saapuessa ei siirra rivin muita kohtia. */
	.chip.hz {
		min-width: 10ch;
		justify-content: center;
	}
	.chip:hover {
		color: var(--text);
		border-color: var(--accent);
		text-decoration: none;
	}
	.chip.active {
		color: var(--accent-strong);
		border-color: var(--accent);
	}

	.more {
		margin: 0 0 var(--s-4);
		padding-bottom: var(--s-3);
		border-bottom: 1px solid var(--border);
	}
	.more summary {
		cursor: pointer;
		color: var(--text-muted);
		font-size: var(--step--1);
		font-weight: 600;
		padding: 4px 0;
	}
	.more .tool-row {
		margin: var(--s-2) 0 0;
		padding: 0;
		border: 0;
	}

	.tool-row {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2);
		margin: 0 0 var(--s-4);
		padding-bottom: var(--s-3);
		border-bottom: 1px solid var(--border);
	}
	.tool-row a {
		display: inline-flex;
		align-items: center;
		gap: 0.4ch;
		color: var(--text-muted);
		font-size: var(--step--1);
		text-decoration: none;
		padding: 4px 10px;
		border: 1px solid transparent;
		border-radius: var(--radius);
	}
	.tool-row a:hover {
		color: var(--text);
		border-color: var(--border);
	}
	.tool-row a.active {
		color: var(--accent-strong);
		border-color: var(--accent);
	}
	.tool-row a.all {
		margin-left: auto;
		font-family: var(--font-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	/* 5.9: oli varillinen emoji-lukko. Tekstitunniste lukee samana
	   paletissa, monolla ja ruudunlukijalla (aria-label sailyi). opacity
	   0.8 pudotti kontrastin AA:n alle pienessa koossa -> vari suoraan. */
	.lock {
		font-family: var(--font-mono);
		font-size: 0.7em;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--accent);
		border: 1px solid var(--accent);
		padding: 0.1em 0.35em;
		margin-left: 0.4em;
		vertical-align: 0.08em;
	}
	/* Puhelimessa pinottu "All" on harvinainen reitti; se ei vie rivia. */
	@media (max-width: 640px) {
		.tool-row a.all {
			display: none;
		}
	}
</style>
