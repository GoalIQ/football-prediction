<script lang="ts">
	/**
	 * Kauppailmoitus Stripe-nappien tilalle maissa joissa Premiumia ei myyda
	 * verkossa (23.9.2026: UK, ks. $lib/region). UK on suurin maksumuurimaa,
	 * joten tama ei saa olla umpikuja: molemmat kaupat, ja puhelimella
	 * laitteen oma kauppa ensin.
	 *
	 * `compact`: lyhyt muoto (lause + tekstilinkit) pinnoille joilla on jo oma
	 * CTA-rakenne, esim. etusivun ProductIntro. Muuten sama lause, samat
	 * linkit ja samat tapahtumat.
	 */
	import { onMount } from 'svelte';
	import { capture } from '$lib/analytics';
	import { STORE_URL, appCtaLabel, preferredStore, type AppStore } from '$lib/appHandoff';
	import { STORE_ONLY_ACCOUNT_NOTE, STORE_ONLY_COPY } from '$lib/region';

	let { source = 'pro_web', compact = false }: { source?: string; compact?: boolean } =
		$props();

	let first = $state<AppStore>('ios');
	const order = $derived<AppStore[]>(first === 'android' ? ['android', 'ios'] : ['ios', 'android']);

	onMount(() => {
		// `navigator` vasta mountissa (ei prerenderissa), kuten PremiumPreview.
		if (preferredStore(navigator?.userAgent) === 'android') first = 'android';
		capture(
			'app_handoff_shown',
			{ store: 'both', reason: 'region_store_only', source },
			`store_only_shown_${source}`
		);
	});
</script>

{#if compact}
	<p class="store-only compact" role="note">
		<span class="lead">{STORE_ONLY_COPY}</span>
		<span class="links">
			{#each order as store, i (store)}
				{#if i > 0}<span class="sep" aria-hidden="true">·</span>{/if}<a
					href={STORE_URL[store]}
					rel="noopener"
					onclick={() => capture('app_handoff_tapped', { store, reason: 'region_store_only', source })}
					>{appCtaLabel(store)}</a
				>
			{/each}
		</span>
	</p>
{:else}
<div class="store-only" role="note">
	<p class="lead">{STORE_ONLY_COPY}</p>
	<div class="stores">
		{#each order as store, i (store)}
			<a
				class={i === 0 ? 'btn-primary' : 'btn-secondary'}
				href={STORE_URL[store]}
				rel="noopener"
				onclick={() => capture('app_handoff_tapped', { store, reason: 'region_store_only', source })}
			>
				{appCtaLabel(store)}
			</a>
		{/each}
	</div>
	<p class="muted note">{STORE_ONLY_ACCOUNT_NOTE}</p>
</div>
{/if}

<style>
	.store-only {
		display: grid;
		gap: var(--s-3);
		margin: var(--s-4) 0;
		max-width: 36rem;
	}
	.lead {
		margin: 0;
		font-weight: 600;
	}
	.stores {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-3);
	}
	.note {
		margin: 0;
		font-size: var(--step--1);
	}
	.compact {
		display: grid;
		gap: var(--s-1);
		margin: 0 0 var(--s-3);
	}
	.compact .links {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--s-1) var(--s-2);
	}
	.compact .links a {
		font-weight: 600;
	}
	.compact .sep {
		color: var(--text-muted);
	}
</style>
