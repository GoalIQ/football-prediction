<script lang="ts">
	import type { XpWhy } from '$lib/api';
	import { whyDriverRows } from '$lib/whyDrivers';

	// WHY-THIS-PICK (14.8). Nostettu XpTablesta omaksi komponentiksi 19.8
	// (Rowanin palaute): selitys oli vain xP-taulukon avatussa rivissa, eli
	// "kuka" ja "miksi" olivat eri nakymissa. Ajurilista elaa $lib/whyDrivers
	// -moduulissa eika kutsujassa — komponenttiin haudattu lista korjaa vain
	// yhden nayton.
	//
	// 20.8 (Rowanin palaute jaettuun korttiin): ajurit olivat tasa-arvoisia
	// chippeja ilman lukua, eli ne kertoivat MITKA syyt mutta eivat kuinka
	// isoja. Nyt jokainen ajuri on rivi jolla on backendin antama todisteluku
	// ("83 mins a game") — sama esitys kuin jaettavalla kortilla, jotta sivu
	// ja kuva nayttavat saman asian samannakoisena.
	//
	// LAHDE NAKYY AINA. `template` ei ole vika vaan tarkka mutta tylsa lause;
	// sen piilottaminen tekisi provenienssilupauksesta valikoivan. Kumpaakaan
	// lahdetta EI kutsuta "malliksi": tassa tuotteessa se sana tarkoittaa
	// ottelumallia, ja lauseen kirjoittajan kutsuminen malliksi siirtaisi
	// ottelumallin uskottavuuden sille. Sama saanto mobiilissa.

	let { why }: { why: XpWhy | undefined } = $props();

	const rows = $derived(whyDriverRows(why));
</script>

{#if why?.sentence}
	<div class="why">
		<p class="why-title">Why this projection</p>
		{#if rows.length}
			<ul class="why-drivers">
				{#each rows as d (d.key)}
					<li class="why-driver">
						<span class="why-driver-label">{d.label}</span>
						{#if d.value}<span class="why-driver-value">{d.value}</span>{/if}
					</li>
				{/each}
			</ul>
		{/if}
		<p class="why-text">{why.sentence}</p>
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
		margin: 0 0 8px;
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted, #a8a29a);
	}
	/* Ajurit ENNEN lausetta ja omina riveinaan: lause on tarkka mutta se
	   luetaan sanasta sanaan, kun taas kolme riviä lukuineen luetaan
	   silmayksella. Rowanin vaatimus oli tasan se ("within a second or two"). */
	.why-drivers {
		list-style: none;
		margin: 0 0 10px;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.why-driver {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
		border-left: 3px solid var(--giq-gold, #f5c542);
		padding: 3px 0 3px 8px;
	}
	.why-driver-label {
		font-size: 12.5px;
		font-weight: 700;
		color: var(--giq-cream, #f3f2f2);
	}
	.why-driver-value {
		font-size: 12.5px;
		font-weight: 700;
		color: var(--giq-gold, #f5c542);
		text-align: right;
		white-space: nowrap;
	}
	.why-text {
		margin: 0;
		font-size: 13px;
		line-height: 1.5;
		color: var(--muted, #a8a29a);
	}
	.why-source {
		margin: 6px 0 0;
		font-size: 11px;
		color: var(--muted, #a8a29a);
	}
</style>
