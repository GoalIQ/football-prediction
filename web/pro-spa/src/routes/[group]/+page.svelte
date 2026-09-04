<script lang="ts">
	/** Ryhmasivu: /week /team /players /tools /prices /matches.
	 *
	 * Tuntematon ryhma ohjautuu juureen. Se on tarkoituksella hiljainen
	 * ohjaus eika virhesivu: tama reitti nappaa myos kirjoitusvirheet
	 * (/playerz), ja kayttajalle oikea vastaus on tyokalut, ei virheilmoitus.
	 */
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { groupById } from '$lib/tools';
	import AppShell from '$lib/components/AppShell.svelte';

	const group = $derived(page.params.group ?? 'week');
	const known = $derived(!!groupById(group));
	const all = $derived(page.url.searchParams.has('all'));

	onMount(() => {
		if (!known) void goto('/', { replaceState: true });
	});
</script>

{#if known}
	<AppShell {group} {all} />
{/if}
