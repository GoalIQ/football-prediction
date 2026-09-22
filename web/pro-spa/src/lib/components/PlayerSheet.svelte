<script lang="ts">
	/**
	 * Pelaajakortti sheetina (22.9.2026, A3 2.3). Yksi instanssi AppShellissa.
	 * Puhelimessa alhaalta nouseva paneeli, tyopoydalla oikean reunan paneeli.
	 * Sisalto on sama PlayerCard jota /players/player-card kayttaa, joten
	 * kortin tasot ja maskit ovat samat kuin tyokalussa.
	 */
	import { tick } from 'svelte';
	import { auth } from '$lib/auth.svelte';
	import { capture } from '$lib/analytics';
	import { closePlayer, playerSheet } from '$lib/playerSheet.svelte';
	import PlayerCard from './PlayerCard.svelte';

	let closeBtn = $state<HTMLButtonElement | null>(null);
	let returnTo: HTMLElement | null = null;

	$effect(() => {
		const id = playerSheet.id;
		if (id == null) return;
		capture('player_sheet_opened', { source: playerSheet.source });
		returnTo = document.activeElement as HTMLElement | null;
		const prev = document.body.style.overflow;
		document.body.style.overflow = 'hidden';
		void tick().then(() => closeBtn?.focus());
		return () => {
			document.body.style.overflow = prev;
			returnTo?.focus?.();
		};
	});

	function onKey(e: KeyboardEvent) {
		if (playerSheet.id != null && e.key === 'Escape') closePlayer();
	}
</script>

<svelte:window onkeydown={onKey} />

{#if playerSheet.id != null}
	<div class="backdrop" aria-hidden="true" onclick={closePlayer}></div>
	<div class="sheet" role="dialog" aria-modal="true" aria-label="Player card">
		<div class="sheet-head">
			<span class="sheet-title">Player card</span>
			<button type="button" class="sheet-close" bind:this={closeBtn} onclick={closePlayer}>
				Close
			</button>
		</div>
		<div class="sheet-body">
			{#key playerSheet.id}
				<PlayerCard premium={!!auth.sub} playerId={playerSheet.id} embedded />
			{/key}
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 50;
		background: rgba(11, 10, 9, 0.66);
	}
	.sheet {
		position: fixed;
		z-index: 51;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(460px, 100vw);
		display: flex;
		flex-direction: column;
		background: var(--bg);
		border-left: 1px solid var(--border-strong);
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
