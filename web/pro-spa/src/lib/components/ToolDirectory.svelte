<script lang="ts">
	/** Ryhman tyokaluhakemisto: nimi + kysymys + tasomerkki, jokainen kortti
	 * oma URL.
	 *
	 * 🔴 MITATTU 4.9.2026: `/players` oli pinottuna **21 173 px** pitka
	 * (yksitoista tyokalua peräkkäin). Villen havainto 3.9 oli sama sanoin:
	 * "vähemmän tavaraa per sivu". Ryhman etusivu on nyt hakemisto, ja
	 * pinottu nakyma on yha saatavilla "All on one page" -linkista — se on
	 * valinta eika oletus.
	 *
	 * Kaava on FPLRoguen `/tools`-hakemistosta ja Fantasy Football Hubin
	 * "Select a tool" -sivulta (auditointi `2026-09-04-kilpailija-ui-auditointi.md`),
	 * meidan teemalla: ei uusia vareja, ei uutta typografiaa.
	 */
	import { capture } from '$lib/analytics';
	import type { Tool } from '$lib/tools';

	let {
		tools,
		premium = false,
		onLocked
	}: { tools: Tool[]; premium?: boolean; onLocked: (slug: string) => void } = $props();
</script>

<div class="tools-grid">
	{#each tools as t (t.slug)}
		{#if t.tier === 'premium' && !premium}
			<button type="button" class="tool-card-btn" onclick={() => onLocked(t.slug)}>
				<span class="tool-card-head">
					<span class="tool-card-title">{t.title}</span>
					<span class="tool-lock">Premium</span>
				</span>
				<span class="tool-card-desc muted">{t.question}</span>
			</button>
		{:else}
			<a
				class="tool-card-btn"
				href="/{t.group}/{t.slug}"
				onclick={() => capture('fantasy_tool_opened', { tool: t.slug })}
			>
				<span class="tool-card-head">
					<span class="tool-card-title">{t.title}</span>
				</span>
				<span class="tool-card-desc muted">{t.question}</span>
			</a>
		{/if}
	{/each}
</div>

<style>
	.tools-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
		gap: var(--s-3);
	}
	.tool-card-btn {
		/* Kortti on joko <a> (auki) tai <button> (lukittu) — sama kaava. */
		text-decoration: none;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--s-1);
		text-align: left;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-4);
		font: inherit;
		color: var(--text);
		cursor: pointer;
	}
	.tool-card-btn:hover {
		border-color: var(--accent);
	}
	.tool-card-head {
		display: flex;
		align-items: center;
		gap: var(--s-2);
	}
	.tool-card-title {
		font-weight: 700;
	}
	.tool-lock {
		font-size: var(--step--1);
		color: var(--text-muted);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0 0.6em;
	}
	.tool-card-desc {
		font-size: var(--step--1);
		line-height: 1.45;
	}
	.muted {
		color: var(--text-muted);
	}
</style>
