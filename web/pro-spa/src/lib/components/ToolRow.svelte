<script lang="ts">
	/** Ryhman tyokalurivi: pysyva tyokalunvaihtaja tyokalun SISALLA.
	 *
	 * Korvaa vanhan "On this page:" -ankkuririvin. Ero ei ole kosmeettinen:
	 * ankkuririvi vieritti pitkaa sivua (ja oli itsessaan todiste siita etta
	 * sivu oli liian pitka), tama vaihtaa nakymaa ja jokainen kohde on oma
	 * URL. Sama kaava kuin Fantasy Football Hubin toisella navirivilla ja
	 * FPLRoguen tyokalusivuilla (auditointi 4.9.2026).
	 *
	 * "All" pitaa vanhan kayttaytymisen tallella: ryhman kaikki tyokalut
	 * pinossa, kuten ennen 4.9.
	 */
	import type { Tool } from '$lib/tools';

	let {
		tools,
		group,
		active = null,
		all = false,
		premium = false
	}: {
		tools: Tool[];
		group: string;
		active?: string | null;
		/** ?all=1 aktiivisena: pinottu nakyma. */
		all?: boolean;
		premium?: boolean;
	} = $props();
</script>

{#if tools.length > 1}
	<nav class="tool-row" aria-label="Tools in this group">
		<!-- Pinottu nakyma on yha saatavilla, mutta se on valinta eika oletus:
		     `/players` oli pinottuna 21 173 px pitka (mitattu 4.9). -->
		<a href="/{group}?all=1" class:active={all}>All on one page</a>
		{#each tools as t (t.slug)}
			<a href="/{group}/{t.slug}" class:active={active === t.slug && !all}>
				{t.title}
				{#if t.tier === 'premium' && !premium}<span class="lock" aria-label="Premium">🔒</span
					>{/if}
			</a>
		{/each}
	</nav>
{/if}

<style>
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
	.lock {
		font-size: 0.85em;
		opacity: 0.8;
	}
</style>
