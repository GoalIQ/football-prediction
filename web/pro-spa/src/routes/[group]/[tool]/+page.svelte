<script lang="ts">
	/** Tyokalusivu: /players/leaders, /team/chip-timing, /matches/table, ...
	 *
	 * 22.9 (A3): polku kulkee `resolvePath`in lapi. Tyokalu joka vaihtoi
	 * ryhmaa (/tools/chip-timing 11.9, /prices/price-watch 22.9) loytaa
	 * uuden kotinsa slugilla; tuntematon tyokalu ohjautuu ryhmaansa (ei
	 * juureen): jos linkki oli /players/jotain, kayttaja halusi
	 * pelaajatyokaluja. Query-parametrit kulkevat mukana. $effect eika
	 * onMount, ks. ryhmasivun kommentti. */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { findTool, resolvePath, toolPath } from '$lib/tools';
	import AppShell from '$lib/components/AppShell.svelte';

	const group = $derived(page.params.group ?? 'week');
	const slug = $derived(page.params.tool ?? null);
	const tool = $derived(findTool(group, slug));
	const target = $derived(resolvePath(page.url.pathname));
	const here = $derived(!!tool && target === toolPath(tool));

	$effect(() => {
		if (!here) void goto(`${target ?? '/'}${page.url.search}${page.url.hash}`, { replaceState: true });
	});
</script>

{#if here && tool}
	<AppShell {group} tool={tool.slug} />
{/if}
