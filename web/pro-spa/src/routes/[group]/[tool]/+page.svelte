<script lang="ts">
	/** Tyokalusivu: /players/leaders, /tools/chip-timing, /matches/table, ...
	 *
	 * Tuntematon tyokalu ohjautuu ryhmaansa (ei juureen): jos linkki oli
	 * /players/jotain, kayttaja halusi pelaajatyokaluja. */
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { findTool, findToolAnywhere, groupById, toolPath } from '$lib/tools';
	import AppShell from '$lib/components/AppShell.svelte';

	const group = $derived(page.params.group ?? 'week');
	const slug = $derived(page.params.tool ?? null);
	const tool = $derived(findTool(group, slug));

	onMount(() => {
		if (tool) return;
		// 11.9: tyokalu on voinut vaihtaa ryhmaa (Tools-ryhma purettiin).
		// Vanha linkki loytaa uuden kodin slugilla eika pudota juureen.
		const moved = findToolAnywhere(slug);
		if (moved) return void goto(toolPath(moved), { replaceState: true });
		void goto(groupById(group) ? `/${group}` : '/', { replaceState: true });
	});
</script>

{#if tool}
	<AppShell {group} tool={tool.slug} />
{/if}
