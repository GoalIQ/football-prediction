<script lang="ts">
	/** Sivurunko, jota jokainen tyokalureitti kayttaa (/, /week, /players,
	 * /players/leaders, ...). Erotettu `+page.svelte`:sta 4.9.2026 kun
	 * tyokalut saivat omat reittinsa: runko oli ennen kopioitavissa vain
	 * kasin, ja kopioitu runko olisi tarkoittanut etta uusi reitti unohtaa
	 * hiljaa esim. footerin tai SPL-noston. */
	import type { Snippet } from 'svelte';
	import { DISCLAIMER } from '$lib/config';
	import { pageTitle } from '$lib/tools';
	import { auth } from '$lib/auth.svelte';
	import { showsProductIntro } from '$lib/introGate';
	import Hero from './Hero.svelte';
	import BottomNav from './BottomNav.svelte';
	import PlayerSheet from './PlayerSheet.svelte';
	import ProductIntro from './ProductIntro.svelte';
	import ToolsHome from './ToolsHome.svelte';

	let {
		group = 'week',
		tool = null,
		all = false,
		children
	}: {
		group?: string;
		tool?: string | null;
		all?: boolean;
		/**
		 * 22.9 (web-audit T2, muisti appshell-korjaus-ei-kata-erillisreitteja):
		 * erillisreitit (/ucl, /spl) renderoivat oman sisaltonsa TAMAN rungon
		 * sisalla, jolloin ylapalkki, pelivalitsin, alapalkki ja paluu
		 * goaliq.appiin ovat niilla samat kuin FPL-reiteilla. Ennen 22.9 ne
		 * olivat erillisia sivuja ilman ylapalkkia, ja jokainen ylapalkin
		 * korjaus ohitti ne. Sivu tuo silloin oman otsikkonsa ja footerinsa.
		 */
		children?: Snippet;
	} = $props();

	let upgradeSignal = $state(0);
</script>

<svelte:head>
	<!-- Oma otsikko per nakyma: ennen 4.9 kaikilla 24 tyokalulla oli sama
	     "GoalIQ Premium | FPL tools", eli selaimen historia ja avoimet
	     valilehdet eivat erottaneet niita toisistaan. Erillisreitti tuo
	     oman otsikkonsa (UCL_HEAD / SPL_HEAD), ja prerenderoidussa /spl:ssa
	     toinen <title> kaataisi route-heads-jalkitarkistuksen. -->
	{#if !children}
		<title>{pageTitle(group, tool)}</title>
	{/if}
</svelte:head>

<!-- 11.9: Hero on sovelluksen ylapalkki (navi + kierros + tili) ja
     kulkee koko leveydella .shellin ULKOPUOLELLA; sisalto pysyy palstassa. -->
<Hero onUpgrade={() => upgradeSignal++} />

{#if children}
	{@render children()}
{:else}
<div class="shell">
	<main>
		<!-- TUOTE EDELLA (Ville 5.9): kirjautumaton kavija nakee juuressa
		     tuotteen, ei tyhjaa kuorta. Ehdot ovat tarkoituksella tiukat:

		     `sessionResolved` — ilman sita esittely valahtaisi hetkeksi myos
		     kirjautuneelle maksajalle joka avaa sivun. Sama vika on jo
		     olemassa ikkunabannerissa (auditointi 5.9, C3) eika sita saa
		     monistaa uuteen komponenttiin.

		     `group === 'week'` — vain juuri. Jos kavija on menossa suoraan
		     tyokaluun, han tietaa jo mita etsii, ja myyntipuhe sen edessa
		     olisi este eika esittely. -->
		{#if showsProductIntro(group, auth.sessionResolved, !!auth.user)}
			<ProductIntro onUpgrade={() => upgradeSignal++} />
		{/if}

		<ToolsHome {upgradeSignal} {group} {tool} {all} />
	</main>

	<!-- SPL-nosto (7.8): footer-linkki ei riitä löydettävyyteen (sama oppi
	     kuin career-kortissa: haudattu linkki = ei käyttäjiä). Yksi hillitty
	     rivi — SPL-sisältö itse pysyy omalla reitillään.
	     4.9 (ylapinon budjetti): rivi siirtyi heron alta tyokalujen alle. Se
	     on yha oma laatikkonsa eika footerin tekstilinkki, eli 7.8:n oppi
	     patee; se ei vain enaa ole FPL-tyokalujen EDESSA. -->
	<p class="spl-note">
		New: <a href="/ucl">UCL Fantasy expected points</a> for the league phase, every player, up to three matchdays ahead (Premium).
	</p>
	<p class="spl-note">
		<a href="/spl">Saudi Pro League fantasy tools</a>, completely free.
	</p>

	<footer>
		<hr />
		<p class="muted">
			One account, premium on web, iOS and Android. · {DISCLAIMER} ·
			<!-- SPL = oma osio (etiikkakehys 7.8): löydettävissä muttei FPL-feedin
			     seassa — SPL:stä kiinnostumaton ei törmää siihen työkaluissa. -->
			<a href="/spl">Saudi Pro League tools (free)</a> ·
			<!-- UCL: ilmainen datapinta goaliq.app/ucl + Premium-xP omalla
			     reitilla /ucl (21.9). Ei tools.ts-rekisteriin: oma osio kuten SPL. -->
			<a href="https://goaliq.app/ucl/">UCL Fantasy data (free)</a> ·
			<a href="/ucl">UCL Fantasy expected points (Premium)</a> ·
			<a href="https://goaliq.app">goaliq.app, the free tools</a> ·
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
{/if}

<!-- 22.9: pelaajakortti avautuu mista tahansa pelaajarivista (A3 2.3).
     Yksi instanssi koko sovellukselle; rivit kertovat vain pelaajan id:n. -->
<PlayerSheet />

<!-- 22.9 (web-audit T2): puhelimen alapalkki. Tila sen alla varataan, jotta
     sivun viimeinen rivi (footer) ei jaa palkin taakse. -->
<div class="bottom-spacer" aria-hidden="true"></div>
<BottomNav />

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-3) var(--s-4) var(--s-4);
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
	.bottom-spacer {
		display: none;
	}
	@media (max-width: 640px) {
		.bottom-spacer {
			display: block;
			height: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom, 0px));
		}
	}
</style>
