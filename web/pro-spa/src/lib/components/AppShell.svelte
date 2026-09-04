<script lang="ts">
	/** Sivurunko, jota jokainen tyokalureitti kayttaa (/, /week, /players,
	 * /players/leaders, ...). Erotettu `+page.svelte`:sta 4.9.2026 kun
	 * tyokalut saivat omat reittinsa: runko oli ennen kopioitavissa vain
	 * kasin, ja kopioitu runko olisi tarkoittanut etta uusi reitti unohtaa
	 * hiljaa esim. footerin tai SPL-noston. */
	import { DISCLAIMER } from '$lib/config';
	import { pageTitle } from '$lib/tools';
	import Hero from './Hero.svelte';
	import ToolsHome from './ToolsHome.svelte';

	let {
		group = 'week',
		tool = null,
		all = false
	}: { group?: string; tool?: string | null; all?: boolean } = $props();

	let upgradeSignal = $state(0);
</script>

<svelte:head>
	<!-- Oma otsikko per nakyma: ennen 4.9 kaikilla 24 tyokalulla oli sama
	     "GoalIQ Premium | FPL tools", eli selaimen historia ja avoimet
	     valilehdet eivat erottaneet niita toisistaan. -->
	<title>{pageTitle(group, tool)}</title>
</svelte:head>

<div class="shell">
	<Hero onUpgrade={() => upgradeSignal++} />

	<main>
		<ToolsHome {upgradeSignal} {group} {tool} {all} />
	</main>

	<!-- SPL-nosto (7.8): footer-linkki ei riitä löydettävyyteen (sama oppi
	     kuin career-kortissa: haudattu linkki = ei käyttäjiä). Yksi hillitty
	     rivi — SPL-sisältö itse pysyy omalla reitillään.
	     4.9 (ylapinon budjetti): rivi siirtyi heron alta tyokalujen alle. Se
	     on yha oma laatikkonsa eika footerin tekstilinkki, eli 7.8:n oppi
	     patee; se ei vain enaa ole FPL-tyokalujen EDESSA. -->
	<p class="spl-note">
		New: <a href="/spl">Saudi Pro League fantasy tools</a>, completely free.
	</p>

	<footer>
		<hr />
		<p class="muted">
			One account, premium on web, iOS and Android. · {DISCLAIMER} ·
			<!-- SPL = oma osio (etiikkakehys 7.8): löydettävissä muttei FPL-feedin
			     seassa — SPL:stä kiinnostumaton ei törmää siihen työkaluissa. -->
			<a href="/spl">Saudi Pro League tools (free)</a> ·
			<a href="https://goaliq.app/privacy.html">Privacy</a> ·
			<a href="https://goaliq.app/faq.html">FAQ</a> ·
			<!-- Kohde on Google Form eika hello@: poistaa riippuvuuden DMARC-portista
			     (linjautumaton tukivastaus suodattuisi hiljaa). Perustelu kokonaan
			     commitissa ae9545d6. -->
			<a href="https://forms.gle/wTfsB3Kvuukodtd26" rel="noopener">Contact</a> · Built by an
			independent developer in Finland.
		</p>
	</footer>
</div>

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-4);
	}
	footer {
		margin-top: var(--s-12);
	}
	.spl-note {
		border: 1px solid var(--border);
		border-left: 3px solid var(--accent);
		padding: var(--s-2) var(--s-3);
		margin: var(--s-4) 0 0;
		font-size: 0.9em;
	}
	hr {
		border: none;
		border-top: 1px solid var(--border);
		margin-bottom: var(--s-4);
	}
</style>
