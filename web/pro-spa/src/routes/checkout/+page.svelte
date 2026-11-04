<script lang="ts">
	import { onMount } from 'svelte';
	import { isAlreadyPremiumMessage, type PlanKey } from '$lib/billing';
	import {
		loadPricing,
		openCheckout,
		planLabel,
		seasonPassEnd,
		webCheckoutBlocked
	} from '$lib/pricing.svelte';
	import { planTerms } from '$lib/seasonPass';
	import Provenance from '$lib/components/Provenance.svelte';
	import StoreOnlyNotice from '$lib/components/StoreOnlyNotice.svelte';

	// #101: suora ostopolku — goaliq.app-etusivun hinta-CTA:t laskeutuvat
	// tänne (?plan=monthly|annual|season) ja jatkavat HETI Stripe
	// Checkoutiin. Ei login-seinää: kirjautumaton menee guest-checkoutiin
	// (tili luodaan maksun jälkeen webhookissa), kirjautunut authed-polkuun.
	let plan = $state<PlanKey>('season');
	let error = $state<string | null>(null);
	let busy = $state(true);

	function resolvePlan(): PlanKey {
		const p = new URLSearchParams(window.location.search).get('plan') ?? '';
		return p === 'monthly' ? 'monthly' : 'season'; // annual/season/tuntematon → season
	}

	async function go(source: string) {
		busy = true;
		// 23.9: UK-kavijan maa selviaa vasta taman kutsun vastauksesta (403
		// region_app_store_only), jolloin nakyma kaantyy kauppailmoitukseksi.
		error = await openCheckout(plan, source);
		busy = false;
	}

	onMount(() => {
		plan = resolvePlan();
		// WP6 (4.11.2026): ehtolause ja napin teksti lukevat saman hintavastauksen
		// kuin muut ostopinnat ($lib/seasonPass). Fail-soft: ilman vastausta tilausteksti.
		void loadPricing();
		void go('checkout_route');
	});
</script>

<div class="shell">
	<h2>GoalIQ Premium</h2>
	{#if busy}
		<p>Opening secure checkout ({planLabel(plan)}) via Stripe…</p>
		<!-- #102: sama rehellinen muotoilu kuin PremiumPreview (ei em-dashia) -->
		<p class="muted">
			Skip the signup: pay with Stripe and we'll set up your account and email you a
			sign-in link for the web and the GoalIQ app.
		</p>
	{:else if webCheckoutBlocked()}
		<StoreOnlyNotice source="checkout_route" />
	{:else if error}
		<p class="banner error">{error}</p>
		<!-- 2.11 (WP6): Premium-tilin passiesto ei muutu uudella yrityksella. -->
		{#if !isAlreadyPremiumMessage(error)}
			<button class="primary" onclick={() => void go('checkout_route_retry')}>Try again</button>
		{/if}
	{/if}
	<Provenance />
	<p class="muted">
		{#if webCheckoutBlocked()}
			<a href="/">Back to GoalIQ on the web</a>
		{:else}
			<a href="/">Back to GoalIQ Premium on the web</a> · {planTerms(seasonPassEnd())}
		{/if}
	</p>
</div>

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-8) var(--s-4);
		display: grid;
		gap: var(--s-4);
		justify-items: start;
	}
</style>
