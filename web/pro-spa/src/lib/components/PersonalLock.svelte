<script lang="ts">
	/**
	 * Henkilokohtaisen tyokalun lukitusnakyma (17.10.2026, "tyokalut taakse").
	 *
	 * YKSI KOMPONENTTI kaikille henkilokohtaisille lukoille, kuten
	 * LockedToolPreview on rekisterin premium-tyokaluille. Paatos lukituksesta
	 * tulee $lib/personalLock-lukijasta (`personalLock`), teksti sen
	 * `LOCK_COPY`-taulusta: tama komponentti ei keksi lausetta eika ehtoa.
	 *
	 * Analytiikka (spec "Mittari": maksumuurin nakijat -> kassan aloitus):
	 *   - nakyma: `paywall_shown` {source: 'personal_lock', tool}, kerran per
	 *     sivulataus per tyokalu (sama once-avaimen kaava kuin muilla lukoilla)
	 *   - CTA: `upgrade_tapped` {source: 'personal_lock_<tool>'}, sitten
	 *     `onUpgrade` avaa saman upgrade-nakyman kuin muut lukot (ToolsHome
	 *     goUpgrade: PremiumPreview + LoginBox tai Paywall). `onUpgrade` EI saa
	 *     itse kirjata upgrade_tappedia, muuten klikkaus laskettaisiin kahdesti.
	 */
	import { onMount } from 'svelte';
	import { capture } from '$lib/analytics';
	import {
		LOCK_COPY,
		PERSONAL_LOCK_SOURCE,
		lockUpgradeSource,
		type PersonalSlug
	} from '$lib/personalLock';

	let {
		tool,
		onUpgrade,
		compact = false
	}: {
		tool: PersonalSlug;
		/** Avaa upgrade-nakyman. Ei kirjaa tapahtumaa itse. */
		onUpgrade?: () => void;
		/** Yhden kappaleen muoto julkisen listan sisaan (price watch, differentials). */
		compact?: boolean;
	} = $props();

	const copy = $derived(LOCK_COPY[tool]);

	onMount(() => {
		capture(
			'paywall_shown',
			{ source: PERSONAL_LOCK_SOURCE, tool },
			`paywall_shown_${PERSONAL_LOCK_SOURCE}_${tool}`
		);
	});

	function open() {
		capture('upgrade_tapped', { source: lockUpgradeSource(tool) });
		onUpgrade?.();
	}
</script>

{#if compact}
	<p class="plock-line" data-personal-lock={tool}>
		<strong>{copy.title}.</strong>
		{copy.body}
		<button type="button" class="linklike" onclick={open}>See Premium</button>
	</p>
{:else}
	<div class="plock" data-personal-lock={tool}>
		<p class="plock-title">
			<strong>{copy.title}</strong>
			<span class="tag" aria-hidden="true">Premium</span>
		</p>
		<p class="muted plock-body">{copy.body}</p>
		<button type="button" class="secondary" onclick={open}>See Premium</button>
	</div>
{/if}

<style>
	.plock {
		border: 1px solid var(--border);
		border-left: 3px solid var(--accent);
		border-radius: var(--radius);
		background: var(--surface);
		padding: var(--s-3) var(--s-4);
		margin: var(--s-3) 0;
		max-width: 680px;
	}
	.plock-title {
		margin: 0 0 var(--s-1);
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--s-1) var(--s-2);
	}
	.plock-body {
		margin: 0 0 var(--s-3);
		font-size: var(--step--1);
		max-width: 60ch;
	}
	.tag {
		font-family: var(--font-mono);
		font-size: 0.75em;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--accent);
		border: 1px solid var(--accent);
		padding: 0.1em 0.35em;
	}
	.plock-line {
		font-size: var(--step--1);
		margin: var(--s-2) 0;
	}
	.linklike {
		background: none;
		border: none;
		padding: 0;
		min-height: 0;
		color: var(--accent);
		font: inherit;
		font-weight: 700;
		text-decoration: underline;
		cursor: pointer;
	}
</style>
