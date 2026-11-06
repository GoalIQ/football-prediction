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
		lockCopy,
		PERSONAL_LOCK_SOURCE,
		lockUpgradeSource,
		type PersonalSlug
	} from '$lib/personalLock';

	let {
		tool,
		onUpgrade,
		compact = false,
		captainOpen = false,
		hidden = null
	}: {
		tool: PersonalSlug;
		/** WP8 / B1: lukon ylla nakyy kayttajan oman XI:n kapteeni
		 *  (personalLock.thisWeekOpenCaptain). Teksti ei silloin lupaa kapteenia
		 *  Premiumiin (lockCopy valitsee "kapteeni auki" -muodon). */
		captainOpen?: boolean;
		/** WP8 / B1: lukon maararivi (personalLock.lockHiddenLine), tai null. */
		hidden?: string | null;
		/** Avaa upgrade-nakyman. Ei kirjaa tapahtumaa itse. */
		onUpgrade?: () => void;
		/** Yhden kappaleen muoto julkisen listan sisaan (price watch, differentials). */
		compact?: boolean;
	} = $props();

	const copy = $derived(lockCopy(tool, { captainOpen }));
	/** Haara analytiikkaan (auditoinnin mittari "lock_view -> lock_tap
	 *  haaroittain"): lukko jonka ylla on kayttajan oma tulos vs ilman.
	 *  Sama kentta kuin sovelluksessa (lock_variant). */
	const variant = $derived(captainOpen ? 'own_result' : 'generic');

	onMount(() => {
		capture(
			'paywall_shown',
			{ source: PERSONAL_LOCK_SOURCE, tool, lock_variant: variant },
			`paywall_shown_${PERSONAL_LOCK_SOURCE}_${tool}`
		);
	});

	function open() {
		capture('upgrade_tapped', { source: lockUpgradeSource(tool), tool, lock_variant: variant });
		onUpgrade?.();
	}
</script>

{#if compact}
	<p class="plock-line" data-personal-lock={tool}>
		<strong>{copy.title}.</strong>
		{copy.body}
		{#if hidden}<strong>{hidden}</strong>{/if}
		<button type="button" class="giq-link" onclick={open}>See Premium</button>
	</p>
{:else}
	<div class="giq-lock plock" data-personal-lock={tool}>
		<p class="plock-title">
			<strong>{copy.title}</strong>
			<span class="giq-tag" aria-hidden="true">Premium</span>
		</p>
		<p class="muted plock-body">{copy.body}</p>
		{#if hidden}<p class="plock-count">{hidden}</p>{/if}
		<button type="button" class="giq-btn giq-btn--primary" onclick={open}>See Premium</button>
	</div>
{/if}

<style>
	.plock {
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
	.plock-count {
		margin: calc(-1 * var(--s-2)) 0 var(--s-3);
		font-size: var(--step--1);
		font-weight: 700;
	}
	.plock-line {
		font-size: var(--step--1);
		margin: var(--s-2) 0;
	}
</style>
