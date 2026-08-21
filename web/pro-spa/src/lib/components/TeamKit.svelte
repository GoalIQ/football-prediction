<script module lang="ts">
	// SVG-id:t ovat dokumenttikohtaisia ja komponentti-instansseja voi olla
	// sivulla monta — moduulitason laskuri pitää gradient-id:t uniikkeina.
	let instances = 0;
</script>

<script lang="ts">
	/**
	 * TeamKit (#113) — web-vastine mobiilin components/TeamKit.tsx:lle.
	 * IP-turva: NEUTRAALI perus-t-paita, EI minkään klubin oikean kitin
	 * kuviota/trade dressiä; EI krestejä/sponsoreita/valmistajalogoja —
	 * vain väri (julkista tietoa, teamColors.ts) + lyhenne rinnassa.
	 * SAMA JERSEY_PATH kuin mobiilissa (1:1 siluetti).
	 *
	 * 21.8 KIT-POLISH: kaulusrivat + pysty valo/varjo-liuku. Siluetti EI
	 * muutu (mobiilipariteetti) eikä mitään klubikohtaista lisätä — rivat ja
	 * liuku ovat geneerisen t-paidan piirteitä, samat joka joukkueella.
	 * Liuku on silti gradient eikä kaksi litteää overlay-polkua: litteä raja
	 * rinnan poikki lukisi kuviona (trade dress -riski), liuku lukee valona.
	 * Sama piirtojärjestys kaikilla pinnoilla: runko → hihat → kaulus →
	 * liuku (koko siluetin yli) → ääriviiva → lyhenne.
	 */
	let {
		color,
		textColor,
		label,
		size = 44
	}: { color: string; textColor: string; label: string; size?: number } = $props();

	const JERSEY_PATH =
		'M 33 15 L 43 9 C 46 15 54 15 57 9 L 67 15 L 84 27 L 76 42 L 67 36 ' +
		'L 67 86 Q 67 90 63 90 L 37 90 Q 33 90 33 86 L 33 36 L 24 42 L 16 27 Z';

	// #126: hihat kaksivärisyyteen (sama geometria + darken-johto kuin mobiili)
	const SLEEVE_LEFT = 'M 33 15 L 16 27 L 24 42 L 33 36 Z';
	const SLEEVE_RIGHT = 'M 67 15 L 84 27 L 76 42 L 67 36 Z';
	// Kaulusrivat: pääntien kaari offsetattuna ~4 yksikköä alaspäin; päät
	// istuvat olkasaumalinjoilla (33,15)→(43,9) ja (57,9)→(67,15).
	const COLLAR_PATH =
		'M 43 9 C 46 15 54 15 57 9 L 60.5 11.1 C 55 19 45 19 39.5 11.1 Z';
	const shadeId = `tk-shade-${++instances}`;
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
	const sleeve = $derived(darken(color));
</script>

<svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
	<defs>
		<linearGradient id={shadeId} x1="0" y1="0" x2="0" y2="1">
			<stop offset="0" stop-color="rgba(255,255,255,0.14)" />
			<stop offset="0.35" stop-color="rgba(255,255,255,0)" />
			<stop offset="0.65" stop-color="rgba(0,0,0,0)" />
			<stop offset="1" stop-color="rgba(0,0,0,0.18)" />
		</linearGradient>
	</defs>
	<path d={JERSEY_PATH} fill={color} />
	<path d={SLEEVE_LEFT} fill={sleeve} />
	<path d={SLEEVE_RIGHT} fill={sleeve} />
	<path d={COLLAR_PATH} fill={sleeve} />
	<path d={JERSEY_PATH} fill="url(#{shadeId})" />
	<path
		d={JERSEY_PATH}
		fill="none"
		stroke="rgba(243,242,242,0.35)"
		stroke-width="3"
		stroke-linejoin="round"
	/>
	<text x="50" y="58" font-size="16" font-weight="800" fill={textColor} text-anchor="middle">
		{label}
	</text>
</svg>
