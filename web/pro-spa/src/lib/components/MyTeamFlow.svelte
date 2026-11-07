<script lang="ts">
	/**
	 * My teamin paatosvirta (WP16). Yksi kysymys kerrallaan: otsikkorivi nayttaa
	 * jokaisen vastauksen yhdella silmayksella, paneeli avaa yhden. Sisalto
	 * tulee kutsujalta snippeteina, joten tama komponentti ei tunne lukuja eika
	 * voi muotoilla niita eri tavalla kuin muut pinnat. Askeleet: $lib/myTeamFlow.
	 *
	 * Paneelit pysyvat DOM:ssa (`hidden`), koska uutispaneeli hakee omat rivinsa
	 * ja kertoo niiden maaran otsikkoriville ennen kuin kukaan avaa sita.
	 */
	import { tick, type Snippet } from 'svelte';
	import { capture } from '$lib/analytics';
	import { activeStepId, nextStep, type FlowStep, type FlowStepId } from '$lib/myTeamFlow';
	import type { RateTeamResponse } from '$lib/fantasyTools';

	let {
		data,
		steps,
		panels
	}: {
		/** Vain valitetaan paneeleille, jotta niissa `data` ei ole null. */
		data: RateTeamResponse;
		steps: FlowStep[];
		panels: Record<FlowStepId, Snippet<[RateTeamResponse]>>;
	} = $props();

	let chosen = $state<FlowStepId | null>(null);
	let root = $state<HTMLElement | null>(null);
	const active = $derived(activeStepId(steps, chosen));
	const next = $derived(nextStep(steps, active));

	function open(id: FlowStepId, via: 'tab' | 'next') {
		chosen = id;
		capture('my_team_step_opened', { step: id, via });
	}

	/** Pitkan paneelin alareunasta seuraava voi olla lyhyempi, jolloin ruutu
	 *  jaisi keskelle sivua. Vierita vain Seuraava-napista: valilehden
	 *  napautuksessa otsikkorivi on jo nakyvissa. */
	async function goNext() {
		if (!next) return;
		open(next.id, 'next');
		await tick();
		root?.scrollIntoView({ block: 'start' });
	}
</script>

{#if steps.length > 0}
	<section class="flow" bind:this={root} aria-label="Your decisions">
		<div class="steps" role="tablist" aria-label="Decisions" style="--n: {steps.length}">
			{#each steps as s (s.id)}
				<button
					type="button"
					role="tab"
					id="flow-tab-{s.id}"
					aria-selected={active === s.id}
					aria-controls="flow-panel-{s.id}"
					class:on={active === s.id}
					onclick={() => open(s.id, 'tab')}
				>
					<span class="lbl">{s.label}</span>
					{#if s.answer}<span class="ans">{s.answer}</span>{/if}
				</button>
			{/each}
		</div>
		{#each steps as s (s.id)}
			<div
				class="panel"
				role="tabpanel"
				id="flow-panel-{s.id}"
				aria-labelledby="flow-tab-{s.id}"
				hidden={active !== s.id}
			>
				<h3 class="q">{s.question}</h3>
				{@render panels[s.id](data)}
			</div>
		{/each}
		{#if next}
			<div class="foot">
				<button type="button" class="giq-btn giq-btn--ghost" onclick={goNext}>
					Next: {next.label}
				</button>
			</div>
		{/if}
	</section>
{/if}

<style>
	.flow {
		container: flow / inline-size;
		margin: var(--s-3) 0;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		scroll-margin-top: var(--s-3);
	}
	.steps {
		display: grid;
		grid-template-columns: repeat(var(--n), minmax(0, 1fr));
		border-bottom: 1px solid var(--border);
	}
	.steps button {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 2px;
		min-width: 0;
		min-height: 56px;
		padding: var(--s-2) var(--s-1);
		font: inherit;
		text-align: center;
		color: var(--text-muted);
		background: transparent;
		border: 0;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		cursor: pointer;
	}
	.steps button.on {
		color: var(--text);
		border-bottom-color: var(--accent);
	}
	.lbl {
		font-size: 12px;
		font-weight: 600;
	}
	.ans {
		overflow: hidden;
		font-size: 13px;
		font-weight: 700;
		color: var(--text);
		white-space: nowrap;
		text-overflow: ellipsis;
	}
	.panel {
		padding: var(--s-3) var(--s-4) var(--s-4);
	}
	.q {
		margin: 0 0 var(--s-3);
		font-size: 17px;
		font-weight: 700;
		letter-spacing: 0;
		text-transform: none;
		color: var(--text);
	}
	.foot {
		display: flex;
		justify-content: flex-end;
		padding: 0 var(--s-4) var(--s-4);
	}
</style>
