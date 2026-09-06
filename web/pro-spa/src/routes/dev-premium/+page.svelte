<script lang="ts">
	// DEV-ONLY premium-esikatselu (ei auth-gatea) - renderöityy VAIN vite dev
	// -moodissa; tuotantobuildissa reitti näyttää ohjeen eikä dataa (ei
	// paywall-ohitusta, data on silti julkisesta API:sta).
	// Web P1 (30.7): ProTools poistui → esikatselu on ToolsHome forcePremiumilla.
	import ToolsHome from '$lib/components/ToolsHome.svelte';
	import { page } from '$app/state';

	const isDev = import.meta.env.DEV;
	// 6.9: ryhma ja tyokalu query-parametreista (?group=players&tool=player-xp),
	// jotta esikatselu ei putoa forcePremiumista segmenttilinkkia klikatessa.
	const group = $derived(page.url.searchParams.get('group') ?? 'week');
	const tool = $derived(page.url.searchParams.get('tool'));
</script>

<div class="shell">
	{#if !isDev}
		<p class="muted">Dev preview only. Use the app at <a href="/">/</a>.</p>
	{:else}
		<p class="banner success">DEV PREVIEW: premium-näkymät ilman auth-gatea</p>
		<ToolsHome forcePremium {group} {tool} />
	{/if}
</div>

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-4);
	}
</style>
