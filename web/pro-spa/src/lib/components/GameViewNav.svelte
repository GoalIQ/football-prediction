<script lang="ts">
	/** Muiden pelien (RSL /spl, UCL /ucl) nakymavalitsin: sama rakenne ja
	 *  ulkoasu kuin FPL:n `ToolRow` (23.9, Villen pyynnot "RSL fantasyn vois
	 *  kans jasennella noilla menuilla" ja UCL:lle "sama rakenne").
	 *
	 *  Osiot ( Players | Teams | ... ) ovat sovelluksen palkissa (Villen
	 *  valinta B: palkki pelin mukaan, `navItems`), joten tama rivi kantaa
	 *  vain osion sisaisen valinnan:
	 *    Players: esiasetukset Captain / xP / Value / Differentials,
	 *             loput "More player tools" -avattavassa
	 *    muut:    osion nakymat rivina, jos niita on useampi
	 *
	 *  Rakenne tulee rekisterista (`GAME_VIEWS`); tama komponentti ei
	 *  maarittele omaa. Kohteet ovat hash-linkkeja (/spl#value), koska /spl
	 *  on prerenderoitu: linkki on jaettava ja paluunappi toimii.
	 */
	import { GAME_VIEWS, gameSectionOf, type GameId, type GameViews } from '$lib/tools';
	import { xpHorizon, type HorizonMeta } from '$lib/xpHorizon';

	let {
		game,
		view,
		horizonMeta = null,
		locked = []
	}: {
		game: GameId;
		view: string;
		horizonMeta?: HorizonMeta | null;
		/** Nakymat jotka ovat talle kayttajalle Premiumia (merkki kuten FPL:n
		 *  ToolRow'ssa). Sivu paattaa tason palvelimen maskista. */
		locked?: string[];
	} = $props();

	const def = $derived(GAME_VIEWS[game] as GameViews);
	const section = $derived(gameSectionOf(game, view));
	const more = $derived(def.more[section.id] ?? []);
	const presetViews = $derived(new Set<string>(def.presets.map((p) => p.view)));
	const moreOpen = $derived(section.id === 'players' && !presetViews.has(view));
	const hz = $derived(xpHorizon(horizonMeta));
	function presetLabel(label: string, horizon?: boolean): string {
		return horizon && hz.count != null && hz.count > 0 ? `${label} ${hz.gws}` : label;
	}
</script>

{#if section.id === 'players'}
	<nav class="presets" aria-label="Sort players">
		<span class="presets-lbl" aria-hidden="true">Sort</span>
		{#each def.presets as p (p.view)}
			<a
				href="#{p.view}"
				class="chip"
				class:hz={p.horizon}
				class:active={view === p.view}
				aria-current={view === p.view ? 'page' : undefined}
				>{presetLabel(p.label, p.horizon)}{#if locked.includes(p.view)}<span
						class="lock"
						aria-label="Premium">Premium</span
					>{/if}</a
			>
		{/each}
	</nav>
	<details class="more" open={moreOpen}>
		<summary>More player tools</summary>
		<nav class="tool-row" aria-label="More player tools">
			{#each more as m (m.view)}
				<a href="#{m.view}" class:active={view === m.view}
					>{m.label}{#if locked.includes(m.view)}<span class="lock" aria-label="Premium"
							>Premium</span
						>{/if}</a
				>
			{/each}
		</nav>
	</details>
{:else if more.length > 1}
	<nav class="tool-row" aria-label="Tools in this view">
		{#each more as m (m.view)}
			<a href="#{m.view}" class:active={view === m.view}>{m.label}</a>
		{/each}
	</nav>
{/if}

<style>
	/* Sama ulkoasu kuin ToolRow.sveltessa (FPL): kayttaja siirtyy pelista
	   toiseen pelivalitsimella ja nakee saman valitsimen. */
	.presets {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-2);
		margin: var(--s-4) 0 var(--s-2);
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
		margin: var(--s-4) 0;
		padding-bottom: var(--s-3);
		border-bottom: 1px solid var(--border);
	}
	.tool-row a {
		display: inline-flex;
		align-items: center;
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
	/* Sama kuin ToolRow.svelten .lock. */
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
</style>
