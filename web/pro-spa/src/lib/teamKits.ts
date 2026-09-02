/**
 * teamKits — pelipaitojen kuviotyypit + kuratoitu kuviotaulu (#106, 20.8–21.8).
 *
 * TÄMÄ TIEDOSTO ON SANATARKASTI SAMA KAHDESSA REPOSSA:
 *   - goaliq-app:          lib/teamKits.ts
 *   - football-prediction: web/pro-spa/src/lib/teamKits.ts
 * Repot eivät voi jakaa moduulia, joten sama sisältö on kopioitu molempiin.
 * Jos muutat toista, muuta toinen samassa yhteydessä — muuten sama joukkue
 * saa eri paidan eri pinnalta (sama "kaksi totuutta" -vikaluokka joka on
 * kirjattu väreistä ja WHY-labeleista).
 *
 * IP-RAJA (ei-neuvoteltava): EI krestejä, EI sponsoreita, EI valmistaja-
 * logoja — ne ovat tavaramerkkejä ja se raja oikeasti kantaa. Kuviotyypit
 * (pystyraita, vaakaraita, puolikas, vinokaista, keskikaista, kontrasti-
 * hihat) ovat jalkapallopaidan yleistä muotokieltä jota kymmenet klubit
 * jakavat, eivät yhdenkään klubin omaisuutta: "NEW pelaa mustavalko-
 * raidallisessa" on julkinen fakta samalla tavalla kuin primary-väri.
 * Villen tilaus 20.8: "vähä ku seurojen oikeet paidat mutta logo ei tarkka".
 *
 * TAULU ON KURATOITU, EI KATTAVA. Vain joukkueet joiden kuvio on vakiintunut
 * klubi-identiteetti (ei yhden kauden kitti) saavat rivin; puuttuva rivi =
 * solid primary-värillä, eli lisäys ei voi rikkoa yhtään kuratoimatonta
 * joukkuetta. Kuvio ilman omaa väriä olisi arvaus, siksi secondary on
 * pakollinen kenttä.
 */

export type KitPattern =
	| 'solid'
	| 'stripes'
	| 'hoops'
	| 'halves'
	| 'sash'
	| 'band'
	| 'sleeves';

/** Yksi piirrettävä muoto rungon sisällä (leikataan JERSEY-polulla).
 *  `rect` riittää raidoille ja puolikkaille; vinokaista annetaan polkuna. */
export type KitLayer =
	| { kind: 'rect'; x: number; y: number; w: number; h: number }
	| { kind: 'path'; d: string };

/**
 * Kuvion muodot rungon sisällä (viewBox 0 0 100, leikataan JERSEY-polulla).
 *
 * Rungon leveys on 33..67 eli 34 yksikköä, ja raidat on mitoitettu siitä,
 * EI koko 100:n ruudusta: viiden yksikön raita antaa seitsemän vuorottelevaa
 * kaistaa, mikä lukee raidalliseksi myös 36 pt:ssä (jakokortti) eikä muutu
 * mössöksi 24 pt:ssä (listat).
 *
 * 'sleeves' ei tuota runkomuotoja: se tarkoittaa että HIHAT maalataan
 * secondary-värillä primääristä tummennetun johdoksen sijaan (Arsenalin/
 * West Hamin tyyppinen kontrastihiha). Renderöijä lukee tämän itse.
 */
export function kitLayers(pattern: KitPattern): KitLayer[] {
	switch (pattern) {
		case 'stripes':
			return [38, 48, 58].map((x) => ({ kind: 'rect' as const, x, y: 0, w: 5, h: 100 }));
		case 'hoops':
			return [25, 45, 65].map((y) => ({ kind: 'rect' as const, x: 0, y, w: 100, h: 7 }));
		case 'halves':
			return [{ kind: 'rect', x: 50, y: 0, w: 50, h: 100 }];
		case 'band':
			// Yksi leveä pystykaista keskellä (PSG-tyyppi).
			return [{ kind: 'rect', x: 44, y: 0, w: 12, h: 100 }];
		case 'sash':
			// Vino kaista oikealta olalta vasemmalle lantiolle (Monaco-tyyppi).
			return [{ kind: 'path', d: 'M 85 0 L 100 15 L 15 100 L 0 85 Z' }];
		case 'sleeves':
		case 'solid':
		default:
			return [];
	}
}

export interface TeamKitSpec {
	pattern: KitPattern;
	/** Kuvion/hihojen/kauluksen väri. Pakollinen: kuvio ilman kuratoitua
	 *  väriä olisi arvaus, ja arvattu kakkosväri näyttää väärältä paidalta. */
	secondary: string;
}

/**
 * Kuratoitu kuviotaulu lyhytkoodilla (sama avain kuin teamColors/teamMeta).
 * Lähde: klubien vakiintunut kotipaidan muotokieli (julkista tietoa).
 * `solid` + secondary = yksivärinen runko, kaulus/detalji secondary-värillä.
 */
const KIT_BY_SHORT: Record<string, TeamKitSpec> = {
	// Premier League
	ARS: { pattern: 'sleeves', secondary: '#FFFFFF' },
	AVL: { pattern: 'sleeves', secondary: '#94BEE5' },
	BOU: { pattern: 'stripes', secondary: '#000000' },
	BRE: { pattern: 'stripes', secondary: '#FFFFFF' },
	BHA: { pattern: 'stripes', secondary: '#FFFFFF' },
	BUR: { pattern: 'sleeves', secondary: '#99D6EA' },
	// 2.9 PAITAPAIVITYS: kaikki 26/27 PL-seurat taulussa, jotta kaulus ja
	// hihansuut saavat kuratoidun varin myos yksivarisella paidalla.
	CHE: { pattern: 'solid', secondary: '#FFFFFF' },
	COV: { pattern: 'solid', secondary: '#FFFFFF' },
	CRY: { pattern: 'stripes', secondary: '#C4122E' },
	EVE: { pattern: 'solid', secondary: '#FFFFFF' },
	IPS: { pattern: 'sleeves', secondary: '#FFFFFF' },
	LIV: { pattern: 'solid', secondary: '#FFFFFF' },
	MCI: { pattern: 'solid', secondary: '#1C2C5B' },
	MUN: { pattern: 'solid', secondary: '#FFFFFF' },
	NFO: { pattern: 'solid', secondary: '#FFFFFF' },
	FUL: { pattern: 'solid', secondary: '#000000' },
	HUL: { pattern: 'stripes', secondary: '#000000' },
	LEE: { pattern: 'solid', secondary: '#1D428A' },
	NEW: { pattern: 'stripes', secondary: '#FFFFFF' },
	SHU: { pattern: 'stripes', secondary: '#FFFFFF' },
	SOU: { pattern: 'stripes', secondary: '#FFFFFF' },
	SUN: { pattern: 'stripes', secondary: '#FFFFFF' },
	TOT: { pattern: 'solid', secondary: '#132257' },
	WHU: { pattern: 'sleeves', secondary: '#7AC5E8' },
	WOL: { pattern: 'solid', secondary: '#231F20' },
	// La Liga
	ATH: { pattern: 'stripes', secondary: '#FFFFFF' },
	ATM: { pattern: 'stripes', secondary: '#FFFFFF' },
	BAR: { pattern: 'stripes', secondary: '#004D98' },
	BET: { pattern: 'stripes', secondary: '#FFFFFF' },
	GIR: { pattern: 'stripes', secondary: '#FFFFFF' },
	RMA: { pattern: 'solid', secondary: '#00529F' },
	RSO: { pattern: 'stripes', secondary: '#FFFFFF' },
	// Serie A
	ATA: { pattern: 'stripes', secondary: '#2E6BB0' },
	BOL: { pattern: 'stripes', secondary: '#1B2F5B' },
	GEN: { pattern: 'halves', secondary: '#002147' },
	INT: { pattern: 'stripes', secondary: '#000000' },
	JUV: { pattern: 'stripes', secondary: '#FFFFFF' },
	MIL: { pattern: 'stripes', secondary: '#000000' },
	UDI: { pattern: 'stripes', secondary: '#FFFFFF' },
	// Ligue 1
	ASM: { pattern: 'sash', secondary: '#FFFFFF' },
	LEN: { pattern: 'halves', secondary: '#A8123A' },
	PSG: { pattern: 'band', secondary: '#DA291C' }
};

export function kitByShort(short: string): TeamKitSpec | undefined {
	return KIT_BY_SHORT[short?.toUpperCase?.() ?? ''];
}
