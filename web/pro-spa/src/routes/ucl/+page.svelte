<script lang="ts">
	/**
	 * /ucl: UCL Fantasy lopetettu 3.10.2026 (Villen paatos). Reitti jaa ilmoitukseksi, jotta kirjanmerkit ja
	 * asennetut linkit eivat paady tyhjaan nakymaan. Ei API-kutsuja.
	 * Portti: tests/test_no_uefa_fetch.py (fp) + uclClosed.gate.test.ts.
	 */
	import AppShell from '$lib/components/AppShell.svelte';
	import { UCL_HEAD } from '$lib/routeHeads';
</script>

<svelte:head>
	<title>{UCL_HEAD.title}</title>
	<meta name="description" content={UCL_HEAD.description} />
</svelte:head>

<AppShell>
	<div class="shell">
		<h1>UCL Fantasy</h1>
		<p class="lede">{UCL_HEAD.description}</p>
		<p><a class="go" href="/" data-cta="ucl-closed-fpl">Open the FPL tools</a></p>
	</div>
</AppShell>

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-4);
	}
	h1 {
		margin: 0 0 var(--s-2);
	}
	.lede {
		max-width: 60ch;
	}
	.go {
		display: inline-block;
		margin-top: var(--s-2);
		padding: var(--s-2) var(--s-3);
		border: 1px solid var(--accent);
		color: var(--accent);
		font-weight: 600;
		text-decoration: none;
	}
</style>
