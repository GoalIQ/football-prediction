<script module lang="ts">
	// SVG-id:t ovat dokumenttikohtaisia ja komponentti-instansseja voi olla
	// sivulla monta — moduulitason laskuri pitää clip-id:t uniikkeina.
	let instances = 0;
</script>

<script lang="ts">
	/**
	 * TeamKit (#113) — web-vastine mobiilin components/TeamKit.tsx:lle,
	 * kuviot 21.8 (Villen tilaus 20.8: "vähä ku seurojen oikeet paidat
	 * mutta logo ei tarkka").
	 *
	 * IP-RAJA (ei-neuvoteltava): EI krestejä, EI sponsoreita, EI valmistaja-
	 * logoja — ne ovat tavaramerkkejä ja se raja oikeasti kantaa. Kuviotyypit
	 * (raita, puolikas, vinokaista, kontrastihihat...) ovat jalkapallopaidan
	 * yleistä muotokieltä jota kymmenet klubit jakavat, eivät yhdenkään
	 * klubin omaisuutta. Kuvio + kakkosväri tulevat jaetusta kuratoidusta
	 * taulusta ($lib/teamKits — SANATARKASTI sama tiedosto mobiilirepossa),
	 * avaimena label joka on lyhytkoodi kaikilla kutsupaikoilla.
	 *
	 * SAMA JERSEY_PATH ja piirtojärjestys kuin mobiilissa (1:1): runko →
	 * kuvio (leikattu runkoon) → hihat kuvion PÄÄLLE (hiha on oma paneelinsa
	 * kuten oikeassa paidassa) → kaulus → ääriviiva → lyhenne halolla.
	 */
	import { kitByShort, kitLayers } from '$lib/teamKits';

	let {
		color,
		textColor,
		label,
		size = 44
	}: { color: string; textColor: string; label: string; size?: number } = $props();

	const JERSEY_PATH =
		'M 31 14 L 40 10 C 44 20 56 20 60 10 L 69 14 L 88 26 L 82 44 L 69 39 ' +
		'L 70 88 Q 70 92 66 92 L 34 92 Q 30 92 30 88 L 31 39 L 18 44 L 12 26 Z';

	// #126: hihat kaksivärisyyteen (sama geometria + darken-johto kuin mobiili)
	const SLEEVE_LEFT = 'M 31 14 L 12 26 L 18 44 L 31 39 Z';
	const SLEEVE_RIGHT = 'M 69 14 L 88 26 L 82 44 L 69 39 Z';
	// 2.9 PAITAPAIVITYS: hihansuut omina paneeleina + GOALIQ rintaan
	// sponsorin paikalle (lyhenne pois paidasta: se on aina tekstina vieressa).
	const CUFF_LEFT = 'M 12 26 L 18 44 L 21.8 42.7 L 15.8 24.7 Z';
	const CUFF_RIGHT = 'M 88 26 L 82 44 L 78.2 42.7 L 84.2 24.7 Z';
	/** Kaula-aukon kaari omana viivanaan (kaulus) — sama käyrä kuin rungon
	 *  yläreunassa, joten se istuu pikselilleen eikä ole oma muotonsa. */
	const COLLAR_PATH = 'M 40 10 C 44 20 56 20 60 10';

	function darken(hex: string, factor = 0.7): string {
		const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
		if (!m) return hex;
		const n = parseInt(m[1], 16);
		const f = (v: number) => Math.max(0, Math.round(v * factor));
		const r = f((n >> 16) & 0xff);
		const g = f((n >> 8) & 0xff);
		const b = f(n & 0xff);
		return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
	}

	/** Onko väri vaalea (relatiivinen luminanssi > 0.5) — halon suunta. */
	function isLight(hex: string): boolean {
		const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
		if (!m) return false;
		const n = parseInt(m[1], 16);
		const ch = [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff].map((v) => {
			const c = v / 255;
			return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
		});
		return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2] > 0.5;
	}

	const clipId = `tk-body-${++instances}`;
	const kit = $derived(kitByShort(label));
	// 'sleeves' = kontrastihihat (Arsenal/West Ham -tyyppi): hiha maalataan
	// kakkosvärillä tummennetun johdoksen sijaan.
	const sleeve = $derived(
		kit?.pattern === 'sleeves' && kit.secondary ? kit.secondary : darken(color)
	);
	// Kuvio piirretään vain kun kakkosväri on oikeasti kuratoitu.
	const layers = $derived(kit?.secondary ? kitLayers(kit.pattern) : []);
	// Raidallisella paidalla lyhenne osuu kahdelle värille kerralla, joten se
	// saa halon: teksti kahdesti, paksu viiva alle (sama ratkaisu mobiilissa).
	const halo = $derived(isLight(textColor) ? 'rgba(11,10,9,0.55)' : 'rgba(255,255,255,0.6)');
	const cuff = $derived(
		kit?.pattern === 'sleeves' ? color : (kit?.secondary ?? darken(color, 0.55))
	);
</script>

<svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
	<defs>
		<clipPath id={clipId}><path d={JERSEY_PATH} /></clipPath>
	</defs>
	<path d={JERSEY_PATH} fill={color} />
	{#if layers.length > 0}
		<g clip-path="url(#{clipId})">
			{#each layers as l, i (i)}
				{#if l.kind === 'rect'}
					<rect x={l.x} y={l.y} width={l.w} height={l.h} fill={kit?.secondary} />
				{:else}
					<path d={l.d} fill={kit?.secondary} />
				{/if}
			{/each}
		</g>
	{/if}
	<path d={SLEEVE_LEFT} fill={sleeve} />
	<path d={SLEEVE_RIGHT} fill={sleeve} />
	<path d={CUFF_LEFT} fill={cuff} />
	<path d={CUFF_RIGHT} fill={cuff} />
	<path
		d={COLLAR_PATH}
		fill="none"
		stroke={kit?.secondary ?? sleeve}
		stroke-width="4"
		stroke-linecap="round"
	/>
	<path
		d={JERSEY_PATH}
		fill="none"
		stroke="rgba(243,242,242,0.35)"
		stroke-width="3"
		stroke-linejoin="round"
	/>
	{#if size >= 40}
		<text
			x="50"
			y="60"
			font-size="9"
			font-weight="800"
			letter-spacing="1"
			fill="none"
			stroke={halo}
			stroke-width="2.5"
			stroke-linejoin="round"
			text-anchor="middle">GOALIQ</text
		>
		<text x="50" y="60" font-size="9" font-weight="800" letter-spacing="1" fill={textColor} text-anchor="middle">
			GOALIQ
		</text>
	{/if}
</svg>
