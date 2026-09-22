<script lang="ts">
	/**
	 * Pelivalitsin ylapalkissa (22.9.2026, UX-uudistus A3 luku 1).
	 *
	 * "FPL ▾" -> FPL / UCL Fantasy / RSL Fantasy. Ennen tata UCL oli navin
	 * toinen kohta ja SPL vain sivun alaosan rivilla ja footerissa, eli
	 * kolme eri pelia kolmella eri tavalla loydettavissa. Mobiiliapissa sama
	 * valitsin on otsikkorivilla (pinta-pariteetti).
	 *
	 * Valikon viimeinen rivi on paluu goaliq.appiin: puhelimessa ylapalkissa
	 * ei ole tilaa erilliselle linkille, ja 11.9:n oppi (paluulinkki katosi
	 * kirjautumattomalta) patee edelleen. Tyopoydalla sama linkki on myos
	 * navin lopussa.
	 *
	 * Pelit tulevat rekisterista (`GAMES`), ei tasta tiedostosta.
	 */
	import { page } from '$app/state';
	import { capture } from '$lib/analytics';
	import { GAMES, gameOf } from '$lib/tools';

	const current = $derived(gameOf(page.url.pathname));
	let open = $state(false);
	let root = $state<HTMLElement | null>(null);

	function outside(e: PointerEvent) {
		if (open && root && !root.contains(e.target as Node)) open = false;
	}
	function esc(e: KeyboardEvent) {
		if (open && e.key === 'Escape') open = false;
	}
</script>

<svelte:window onpointerdown={outside} onkeydown={esc} />

<div class="game" bind:this={root}>
	<button
		type="button"
		class="game-btn"
		aria-haspopup="true"
		aria-expanded={open}
		aria-label="Game: {current.label}. Switch game"
		onclick={() => (open = !open)}
	>
		<span class="game-name full">{current.label}</span>
		<span class="game-name short" aria-hidden="true">{current.short}</span>
		<svg class="caret" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
			<path d="M1 3l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" />
		</svg>
	</button>
	{#if open}
		<ul class="game-menu" aria-label="Switch game">
			{#each GAMES as g (g.id)}
				<li>
					<a
						href={g.href}
						aria-current={g.id === current.id ? 'page' : undefined}
						class:on={g.id === current.id}
						data-cta="pro-game-{g.id}"
						onclick={() => {
							open = false;
							capture('game_switched', { to: g.id, from: current.id });
						}}>{g.label}</a
					>
				</li>
			{/each}
			<li class="sep">
				<a href="https://goaliq.app" data-cta="pro-home">goaliq.app</a>
			</li>
		</ul>
	{/if}
</div>

<style>
	.game {
		position: relative;
		flex: 0 0 auto;
	}
	.game-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-height: 34px;
		padding: 0.25em 0.7em;
		font: inherit;
		font-size: 13px;
		font-weight: 700;
		color: var(--text);
		background: transparent;
		border: 1px solid var(--border-strong);
		border-radius: var(--radius);
		cursor: pointer;
		white-space: nowrap;
	}
	.game-btn:hover,
	.game-btn[aria-expanded='true'] {
		border-color: var(--accent);
	}
	.caret {
		color: var(--text-muted);
	}
	.short {
		display: none;
	}
	@media (max-width: 640px) {
		.full {
			display: none;
		}
		.short {
			display: inline;
		}
	}
	.game-menu {
		position: absolute;
		top: calc(100% + 8px);
		left: 0;
		z-index: 40;
		min-width: 200px;
		margin: 0;
		padding: var(--s-1) 0;
		list-style: none;
		background: var(--giq-paper);
		border: 1px solid var(--border-strong);
	}
	.game-menu a {
		display: block;
		padding: 10px var(--s-4);
		color: var(--giq-cream);
		font-size: 14px;
		font-weight: 600;
		text-decoration: none;
	}
	.game-menu a:hover {
		background: rgba(243, 242, 242, 0.06);
	}
	.game-menu a.on {
		color: var(--accent);
	}
	.game-menu .sep {
		border-top: 1px solid rgba(243, 242, 242, 0.24);
		margin-top: var(--s-1);
	}
	.game-menu .sep a {
		font-family: var(--font-mono);
		font-size: 12px;
		font-weight: 400;
		color: var(--giq-muted);
	}
</style>
