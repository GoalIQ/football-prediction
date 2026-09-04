<script lang="ts">
	/** Tyokalusivu: /players/leaders, /tools/chip-timing, /matches/table, ...
	 *
	 * Tuntematon tyokalu ohjautuu ryhmaansa (ei juureen): jos linkki oli
	 * /players/jotain, kayttaja halusi pelaajatyokaluja. */
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { findTool, groupById } from '$lib/tools';
	import AppShell from '$lib/components/AppShell.svelte';

	const group = $derived(page.params.group ?? 'week');
	const slug = $derived(page.params.tool ?? null);
	const tool = $derived(findTool(group, slug));

	onMount(() => {
		if (!tool) void goto(groupById(group) ? `/${group}` : '/', { replaceState: true });
	});
</script>

{#if tool}
	<AppShell {group} tool={tool.slug} />
{/if}
