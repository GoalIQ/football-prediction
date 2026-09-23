<script lang="ts">
	import { onMount } from 'svelte';
	import { PLANS, type PlanKey } from '$lib/billing';
	import { openCheckout, webCheckoutBlocked } from '$lib/pricing.svelte';
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
		void go('checkout_route');
	});
</script>

<div class="shell">
	<h2>GoalIQ Premium</h2>
	{#if busy}
		<p>Opening secure checkout ({PLANS[plan].label}) via Stripe…</p>
		<!-- #102: sama rehellinen muotoilu kuin PremiumPreview (ei em-dashia) -->
		<p class="muted">
			Skip the signup: pay with Stripe and we'll set up your account and email you a
			sign-in link for the web and the GoalIQ app.
		</p>
	{:else if webCheckoutBlocked()}
		<StoreOnlyNotice source="checkout_route" />
	{:else if error}
		<p class="banner error">{error}</p>
		<button class="primary" onclick={() => void go('checkout_route_retry')}>Try again</button>
	{/if}
	<Provenance />
	<p class="muted">
		{#if webCheckoutBlocked()}
			<a href="/">Back to GoalIQ on the web</a>
		{:else}
			<a href="/">Back to GoalIQ Premium on the web</a> · Cancel anytime from the Account menu. One
			subscription covers web, iOS and Android.
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
