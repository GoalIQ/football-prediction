<script lang="ts">
	import type { XpWhy } from '$lib/api';

	// WHY-THIS-PICK (14.8). Nostettu XpTablesta omaksi komponentiksi 19.8
	// (Rowanin palaute): selitys oli vain xP-taulukon avatussa rivissa, eli
	// "kuka" ja "miksi" olivat eri nakymissa. Ajurilista elaa TASSA eika
	// kutsujassa — komponenttiin haudattu lista korjaa vain yhden naytto.
	//
	// LAHDE NAKYY AINA. `template` ei ole vika vaan tarkka mutta tylsa lause;
	// sen piilottaminen tekisi provenienssilupauksesta valikoivan. Kumpaakaan
	// lahdetta EI kutsuta "malliksi": tassa tuotteessa se sana tarkoittaa
	// ottelumallia, ja lauseen kirjoittajan kutsuminen malliksi siirtaisi
	// ottelumallin uskottavuuden sille. Sama saanto mobiilissa.
	const WHY_DRIVER_LABEL: Record<string, string> = {
		minutes: 'Minutes',
		attacking_output: 'Attacking output',
		fixtures: 'Fixtures',
		clean_sheets: 'Clean sheets',
		set_pieces: 'Set pieces',
		bonus: 'Bonus',
		price: 'Price',
		differential: 'Differential'
	};

	let { why }: { why: XpWhy | undefined } = $props();
</script>

{#if why?.sentence}
	<div class="why">
		<p class="why-title">Why this projection</p>
		<p class="why-text">{why.sentence}</p>
		{#if why.drivers?.length}
			<div class="why-chips">
				{#each why.drivers as d (d)}
					<span class="why-chip">{WHY_DRIVER_LABEL[d] ?? d}</span>
				{/each}
			</div>
		{/if}
		<p class="why-source">
			{why.source === 'model'
				? "Written by an AI from the model's own numbers"
				: "Auto-generated from the model's own numbers"}
		</p>
	</div>
{/if}

<style>
	.why {
		background: var(--surface-alt, #1f1d1a);
		border-left: 2px solid var(--teal, #2ed6c2);
		border-radius: 2px;
		padding: 10px 12px;
		margin: 12px 0;
	}
	.why-title {
		margin: 0 0 4px;
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted, #a8a29a);
	}
	.why-text {
		margin: 0;
		font-size: 13px;
		line-height: 1.5;
	}
	.why-source {
		margin: 6px 0 0;
		font-size: 11px;
		color: var(--muted, #a8a29a);
	}
	.why-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 8px;
	}
	.why-chip {
		font-size: 11px;
		font-weight: 600;
		color: var(--teal, #2ed6c2);
		background: var(--surface, #141311);
		border-radius: 2px;
		padding: 3px 7px;
	}
</style>
