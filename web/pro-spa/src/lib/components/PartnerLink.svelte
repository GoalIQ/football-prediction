<script lang="ts">
	/**
	 * Kumppanilinkki xP-listan alle (26.9.2026, FPL Demon). Nimi ja URL
	 * $lib/partners:sta, ei kasin. Merkitty kumppaniksi: lukija nakee etta
	 * linkki on sovittu, ei riippumaton suositus.
	 */
	import { capture } from '$lib/analytics';
	import { partnerActive, type Partner } from '$lib/partners';

	let { partner, surface }: { partner: Partner; surface: string } = $props();
</script>

{#if partnerActive(partner)}
<p class="partner">
	<span class="tag">Partner</span>
	{partner.name}'s planner and solver run on these projections.
	<a
		href={partner.url}
		target="_blank"
		rel="noopener"
		onclick={() => capture('partner_link_clicked', { partner: partner.id, surface })}
		>Plan your transfers there</a
	>
</p>
{/if}

<style>
	.partner {
		font-size: var(--step--1);
		color: var(--text-muted);
		margin: var(--s-2) 0 var(--s-4);
	}
	.tag {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		border: 1px solid currentColor;
		padding: 0 4px;
		margin-right: 6px;
	}
</style>
