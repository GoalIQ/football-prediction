<script lang="ts">
	/** Ryhmasivu: /week /team /players /matches.
	 *
	 * 22.9 (A3): polku kulkee ENSIN `resolvePath`in lapi. Purettu ryhma
	 * (/prices, /tools) ohjautuu uuteen paikkaansa, tuntematon (/playerz)
	 * juureen. Ohjaus on tarkoituksella hiljainen eika virhesivu: tama reitti
	 * nappaa myos kirjoitusvirheet, ja kayttajalle oikea vastaus on tyokalut.
	 * Query-parametrit (?entry=, ?src=, ?tab=) kulkevat mukana, jotta
	 * luovutus goaliq.appista ei katkea ohjauksessa.
	 *
	 * $effect eika onMount: SvelteKit kayttaa saman sivukomponentin uudelleen
	 * kun navigoidaan reitin sisalla (/team -> /prices), jolloin onMount ei
	 * ajaisi ohjausta toista kertaa ja sivu jaisi tyhjaksi.
	 */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { resolvePath } from '$lib/tools';
	import AppShell from '$lib/components/AppShell.svelte';

	const group = $derived(page.params.group ?? 'week');
	const target = $derived(resolvePath(page.url.pathname));
	const here = $derived(target === `/${group}`);
	const all = $derived(page.url.searchParams.has('all'));

	$effect(() => {
		if (!here) void goto(`${target ?? '/'}${page.url.search}${page.url.hash}`, { replaceState: true });
	});
</script>

{#if here}
	<AppShell {group} {all} />
{/if}
