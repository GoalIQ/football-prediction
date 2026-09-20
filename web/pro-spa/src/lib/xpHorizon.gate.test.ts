/**
 * LAHDEPORTTI: xP-summan ikkunan otsikot lukevat `xpHorizon(meta)`:a, eivat
 * `meta.horizon_gw`:ta suoraan (17.9.2026, XP-HORIZON-ALKANUT-KIERROS).
 *
 * MIKSI LAHDETTA EIKA FUNKTIOTA: yksikkotesti todistaa etta lukija on oikein,
 * mutta ei etta pinta kutsuu sita. 6/7 korjausta jai 12.9 ilman vahtia juuri
 * siksi (muisti: testi-kutsuu-funktiota-ei-kutsupaikkaa). Tama testi lukee
 * kutsupaikat ja kaatuu jos joku palauttaa `data.meta.horizon_gw ?? 6`:n
 * otsikkoon.
 *
 * Kolme mekanismia (CLAUDE.md 6a):
 *   1. yksi lukija: `$lib/xpHorizon` on ainoa tiedosto joka saa lukea
 *      `horizon_gw`-arvoa;
 *   2. poikkeuslista perusteluineen: tyyppimaarittelyt saavat NIMETA kentan,
 *      mutta vain maarittelymuodossa (`horizon_gw?: number`), ei lukea sita;
 *   3. vaadittujen kutsupaikkojen lista: pinta joka otsikoi summan on tuotava
 *      lukija JA kutsuttava sita; pelkka import ei riita.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { codeLines, findInCode, interpolations } from './sourceScan';
import { declarations, type Decl } from './declScan';

const SRC = fileURLToPath(new URL('../', import.meta.url));

/** Ainoa tiedosto joka saa lukea `horizon_gw`:n arvon. */
const READER = 'lib/xpHorizon.ts';

/** Skannauksen ulkopuolella: portin oma koodi ja apurit. */
const NOT_SCANNED = new Set(['lib/sourceScan.ts', 'lib/declScan.ts', READER]);

/** Poikkeuslista: tiedosto -> sallitut rivimuodot + perustelu. Rivi joka
 *  sisaltaa `horizon_gw`:n on osuttava johonkin sallittuun muotoon. */
const EXCEPTIONS: Record<string, { reason: string; allow: RegExp[] }> = {
	'lib/api.ts': {
		reason: 'XpMeta/FantasyResponse/FitResponse: tyyppimaarittely nimeaa kentan, ei lue arvoa',
		allow: [/^\s*horizon_gw\??:\s*number/]
	},
	'lib/fantasyTools.ts': {
		reason: 'Compare/Value/Differentials/RateTeam-vastausten tyypit: maarittely, ei lukija',
		allow: [/^\s*horizon_gw\??:\s*number/]
	}
};

/** Pinnat jotka otsikoivat `xp_horizon_total`-summan tai sen johdannaisen.
 *  Jokaisen on tuotava lukija ja kutsuttava sita. */
const REQUIRED_CALLERS = [
	'lib/components/XpTable.svelte',
	'lib/components/ProductIntro.svelte',
	'lib/compareCard.ts',
	'lib/components/ComparePlayers.svelte',
	'lib/components/Value.svelte',
	'lib/components/Differentials.svelte',
	'lib/components/Leaders.svelte',
	'lib/components/PlayerCard.svelte',
	'lib/components/FitChecker.svelte',
	'lib/components/RateTeam.svelte',
	'routes/spl/+page.svelte'
];

const HORIZON_GW = /\bhorizon_gw\b/;
const IMPORT_RE = /import\s*(?:type\s*)?\{[^}]*\bxpHorizon\b[^}]*\}\s*from\s*['"]\$lib\/xpHorizon['"]/;
const CALL_RE = /\bxpHorizon\s*\(/;
/** "next {…horizon_gw…}" / "next ${…horizon_gw…}": tasan se muoto joka oli
 *  vaarin 12.9. Kommentit on jo poistettu ennen tata. */
const NEXT_CLAIM_RE = /\bnext\s*\$?\{[^}]*\bhorizon_gw\b/;
/** Keksitty oletus: `horizon_gw ?? 6`, `horizonGw ?? 6`, `= 6` propin oletuksena. */
const INVENTED_DEFAULT_RE = /\bhorizon(?:_gw|Gw)\b\s*(?:\?\?|=)\s*\d/;

function walk(dir: string, out: string[] = []): string[] {
	for (const name of readdirSync(dir)) {
		const p = join(dir, name);
		if (statSync(p).isDirectory()) walk(p, out);
		else if (/\.(ts|svelte)$/.test(name) && !/\.test\.ts$/.test(name)) out.push(p);
	}
	return out;
}

function rel(p: string): string {
	return relative(SRC, p).split('\\').join('/');
}

function read(relPath: string): string {
	return readFileSync(join(SRC, relPath), 'utf-8');
}

/** Mekanismi 1 + 2 yhdessa funktiossa, jotta sama saanto on testattavissa
 *  synteettisella syotteella (negatiivinen kontrolli alla). */
function strayReads(relPath: string, src: string): string[] {
	if (NOT_SCANNED.has(relPath)) return [];
	const exc = EXCEPTIONS[relPath];
	return findInCode(src, HORIZON_GW)
		.filter((l) => !exc || !exc.allow.some((re) => re.test(l.text)))
		.map((l) => `${relPath}:${l.n}: ${l.text.trim()}`);
}

function callerProblems(relPath: string, src: string): string[] {
	const code = codeLines(src)
		.map((l) => l.text)
		.join('\n');
	const out: string[] = [];
	if (!IMPORT_RE.test(code)) out.push(`${relPath}: ei tuo xpHorizon-lukijaa ($lib/xpHorizon)`);
	if (!CALL_RE.test(code)) out.push(`${relPath}: tuo lukijan mutta ei kutsu sita`);
	return out;
}

describe('lahdeportti: horizon_gw:ta lukee vain $lib/xpHorizon', () => {
	const files = walk(SRC).map(rel);

	it('skannaus loytaa lukijan ja kaikki vaaditut kutsupaikat', () => {
		expect(files).toContain(READER);
		for (const f of REQUIRED_CALLERS) expect(files).toContain(f);
	});

	it('yksikaan pinta ei lue horizon_gw:ta suoraan (poikkeukset vain maarittelymuodossa)', () => {
		const problems = files.flatMap((f) => strayReads(f, read(f)));
		expect(problems, 'lue arvo xpHorizon(meta):sta, ala meta.horizon_gw:sta').toEqual([]);
	});

	it('poikkeuslista ei vanhene: jokainen poikkeus osuu johonkin riviin', () => {
		for (const [f, exc] of Object.entries(EXCEPTIONS)) {
			const hits = findInCode(read(f), HORIZON_GW);
			expect(hits.length, `${f}: poikkeus ilman osumaa, poista se (${exc.reason})`).toBeGreaterThan(0);
		}
	});

	it('jokainen summan otsikoiva pinta tuo lukijan ja kutsuu sita', () => {
		const problems = REQUIRED_CALLERS.flatMap((f) => callerProblems(f, read(f)));
		expect(problems).toEqual([]);
	});

	it('"next {horizon_gw}" -muotoa ei ole missaan, eika keksittya oletusta', () => {
		const problems: string[] = [];
		for (const f of files) {
			if (NOT_SCANNED.has(f)) continue;
			const src = read(f);
			for (const l of findInCode(src, NEXT_CLAIM_RE)) problems.push(`${f}:${l.n}: ${l.text.trim()}`);
			for (const l of findInCode(src, INVENTED_DEFAULT_RE)) problems.push(`${f}:${l.n}: ${l.text.trim()}`);
		}
		expect(problems).toEqual([]);
	});

	it('lukija itse lukee horizon_gw:ta (muuten portti mittaisi tyhjaa)', () => {
		expect(findInCode(read(READER), HORIZON_GW).length).toBeGreaterThan(0);
	});
});

describe('negatiivinen kontrolli: portti osuu siihen mita sen pitaa hylata', () => {
	it('kutsupaikan palautus vanhaan muotoon jaa kiinni', () => {
		const bad = 'let horizonN = $derived(data.meta.horizon_gw ?? gwCols.length ?? 6);';
		expect(strayReads('lib/components/XpTable.svelte', bad)).toHaveLength(1);
		expect(callerProblems('lib/components/XpTable.svelte', bad)).toHaveLength(2);
	});

	it('kommentti ei laukaise, maarittely api.ts:ssa ei laukaise, lukeminen api.ts:ssa laukaisee', () => {
		expect(strayReads('lib/components/XpTable.svelte', '// data.meta.horizon_gw ?? 6')).toEqual([]);
		expect(strayReads('lib/api.ts', '\thorizon_gw?: number;')).toEqual([]);
		expect(strayReads('lib/api.ts', 'const n = meta.horizon_gw;')).toHaveLength(1);
	});

	it('import ilman kutsua ei riita', () => {
		const src = "import { xpHorizon } from '$lib/xpHorizon';\nconst n = 6;";
		expect(callerProblems('lib/compareCard.ts', src)).toEqual([
			'lib/compareCard.ts: tuo lukijan mutta ei kutsu sita'
		]);
	});

	it('"next {…horizon_gw…}" ja "?? 6" tunnistetaan', () => {
		expect(NEXT_CLAIM_RE.test('<dt>Total xP, next {data.meta.horizon_gw ?? 6} GWs</dt>')).toBe(true);
		expect(NEXT_CLAIM_RE.test('subtitle: `next ${data.meta.horizon_gw ?? 6} gameweeks`')).toBe(true);
		expect(INVENTED_DEFAULT_RE.test('let horizon = $derived(horizonGw ?? 6);')).toBe(true);
		expect(INVENTED_DEFAULT_RE.test('\t\thorizonGw = 6,')).toBe(true);
		expect(INVENTED_DEFAULT_RE.test('horizon_gw: xp_data.meta.horizon_gw')).toBe(false);
	});
});

/* ========================================================================
 * 18.9 LAAJENNUS: portin 17.9 versio vartioi YHTA muotoa
 * ------------------------------------------------------------------------
 * Adversariaalinen tarkistaja loysi 17.9 kaksi P1:ta joita yllaoleva portti
 * EI kaada, koska kumpikaan ei lue `horizon_gw`:ta:
 *
 *   P1-1  PlayerCard: jakokortin mallirivin ja sivulauseen ikkuna oli
 *         `xpHorizon(meta).over`, eli yhden muokkauksen paassa muodosta
 *         `over the next ${(player.gameweeks ?? []).length} gameweeks`.
 *         Jakokortti on KUVA: vaara luku menee ulos muodossa jota ei voi
 *         korjata jalkikateen.
 *   P1-2  XpTable: `horizonLabel = $derived(horizon.label)` oli yhden
 *         muokkauksen paassa muodosta `$derived(colsLabel)`, joka on
 *         SARAKKEIDEN vali — kesken kierroksen se alkaa jo alkaneesta
 *         kierroksesta.
 *
 * Kumpikin on sama vikaluokka kuin muistissa `portti-kirjoitetaan-nahdylle-
 * muodolle`: vaara vastaus ei tule `horizon_gw`:sta vaan RIVILISTAN
 * pituudesta, ja rivilista on jokaisessa naista tiedostoista laillisesti
 * kaytossa (per-GW-taulukko, lampokartta, sarakeotsikot). Siksi tama osa ei
 * kysy "luetaanko kenttaa X" vaan "mika VAITE lukee mita":
 *
 *   A. Julkinen vaite summan ikkunasta saa interpoloida vain lukijan
 *      vastauksen. Sallittujen muotojen lista, ei kiellettyjen — tuntematon
 *      lauseke on hylatty (fail-closed).
 *   B. Rekisteroity ikkunanimi (`horizonLabel`, `cardWindowLabel`, ...) on
 *      lukijajohdannainen EIKA rivilistajohdannainen. Nimi joka katoaa
 *      kaataa portin: rekisteri ei vanhene hiljaa.
 *   C. `rows` (= `horizon_gw`, sarakkeiden maara) ei ole summan ikkuna, joten
 *      sita saa lukea vain perustellulla poikkeuksella.
 *   D. Portti mittaa myos KORJAUKSEN LASNAOLON (REQUIRED_FORMS), ei vain
 *      vian puuttumista: jos lukijan valmis otsikko poistetaan, portti
 *      kaatuu vaikka mitaan vaarin ei viela sanottaisi.
 *
 * "Testi kutsuu funktiota, ei kutsupaikkaa" -riman takia joka saanto on oma
 * funktio (claimProblems / labelProblems / rowsProblems), ja alin
 * describe-lohko ajaa ne synteettisilla MUTAATIOILLA molemmista P1-muodoista
 * seka todistaa, etta 17.9 portin saannot (strayReads / callerProblems /
 * NEXT_CLAIM_RE / INVENTED_DEFAULT_RE) paastavat ne lapi. Erotteleva
 * fikstuuri: vaara haara oikeasti onnistuisi ilman tata laajennusta.
 * ====================================================================== */

/** Rivilistat jotka voivat ALKAA jo alkaneesta kierroksesta: pelaajarivien
 *  `gameweeks` ja siita johdettu `gwCols`. Naiden PITUUS ei ole summan
 *  ikkuna. (`meta.gws` Replacements-vastauksessa EI ole talla listalla: se on
 *  serve-timessa suodatettu kierroslista, jonka yli sama endpoint summaa
 *  `xp_window`in — sama lahde kuin luku, ks. CLAIM_EXCEPTIONS.) */
const ROW_SOURCE_RE = /\b(?:gameweeks|gwCols)\b/;

/** Lukijan kutsu. */
const READER_CALL_RE = /\b(?:xpHorizon|xpTotalClaim)\s*\(/;

/** Lukijan kentat jotka KUVAAVAT SUMMAN ikkunaa. `rows` ei ole listalla:
 *  se on sarakkeiden maara (`horizon_gw`), eli tasan se luku joka oli vaarin
 *  12.9 — sille on oma poikkeuslista (ROWS_USES). */
const READER_FIELDS =
	'from|to|count|actionableOnly|range|label|over|span|gws|totalTitle|totalHelp|value|tail|text';

/** Rivi joka VAITTAA jotain summan ikkunasta. Lista on nahdyista muodoista:
 *  nama merkkijonot ovat julkista tekstia, joten niiden muuttaminen kulkee
 *  julkaisutarkistajan kautta eika vahingossa. */
const CLAIM_MARKERS: RegExp[] = [
	/Total xP/,
	/Sum of expected points/,
	/sum of projected points/,
	/xP projected/,
	/Projected points/,
	/Player expected points/,
	/XI expected points/,
	/\bnext\s*\$?\{/i
];

/** Poikkeus sidotaan RIVIN TEKSTIIN, ei tiedostoon: yksi muokkaus riviin
 *  mitatoi poikkeuksen ja kirjoittaja joutuu perustelemaan uudelleen.
 *
 *  `requires` tekee poikkeuksesta EHDOLLISEN: se on se koodimuoto jonka
 *  varassa perustelu seisoo. Jos muoto katoaa tiedostosta, poikkeus lakkaa
 *  patemasta ja portti kaatuu — perustelu ei siis jaa elamaan sen jalkeen kun
 *  syy siihen on poistettu. */
interface ClaimException {
	line: string;
	reason: string;
	requires?: RegExp;
}

const CLAIM_EXCEPTIONS: Record<string, ClaimException[]> = {
	'lib/components/XpTable.svelte': [
		{
			line: '<h2>Player expected points, {colsLabel}</h2>',
			reason:
				'taulukon otsikko kertoo mita SARAKKEET kattavat (gwCols), ei mita Total xP kattaa; colsLabel on rivilistajohdannainen tarkoituksella'
		},
		{
			line: '><abbr title="Sum of expected points over GW{sortWin.from} to GW{sortWin.to}"',
			reason:
				'ikkunasortin oma sarake: vali tulee sortin avaimesta (windowOfSort) ja solun luku on windowXp samalta valilta, eri kysymys kuin summan ikkuna'
		}
	],
	'lib/components/Replacements.svelte': [
		{
			line: '><abbr title="Sum of expected points over {windowLabel}">xP next {nextN}</abbr></th',
			reason:
				'eri endpoint (/api/fantasy/replacements): windowLabel ja nextN tulevat data.meta.gws:sta, joka on sama kierroslista jonka yli xp_window on summattu (fpl_planner.replacements -> transfer_horizon_gws -> planning_start_gw, eli alkanut kierros on jo pudotettu)',
			requires: /\bdata\.meta\.gws\b/
		},
		{
			line: "{#if data.target.xp_window != null}· {data.target.xp_window.toFixed(1)} xP next {nextN}{:else}·",
			reason:
				'sama ikkuna kuin ylla, kohteen oma rivi: luku on xp_window ja nimilappu meta.gws:n pituus, luku ja lause samasta listasta',
			requires: /\bdata\.meta\.gws\b/
		}
	],
	'lib/components/FixtureSwing.svelte': [
		{
			line: 'subtitle: `same player, best and worst opponent, next ${swingGws} gameweeks`,',
			reason:
				'KOLMAS MUOTO (gameweeks.filter(...).length) oikein tehtyna: swingGws on sen SAMAN suodatetun listan pituus josta rivit rakennetaan, ja suodatin on actionableGameweek, luku ja lause ovat samasta listasta, joten alkanut kierros ei voi olla vain toisessa',
			requires: /\bactionableGameweek\s*\(/
		},
		{
			line: 'opponent over the next {swingGws} gameweeks. Goals, assists, bonus and clean sheets scale with the',
			reason: 'sama luku ja sama suodatettu lista kuin jakokortin alaotsikossa',
			requires: /\bactionableGameweek\s*\(/
		}
	],
	'lib/components/Fixtures.svelte': [
		{
			line: 'Upcoming matches for the next {DAYS} days. Every fixture opens in the prediction tool.',
			reason:
				'ei kierrosikkuna vaan VUOROKAUSIA: DAYS on sama vakio joka menee fetchFixtures-kutsuun, eli lause ja lista ovat samasta luvusta',
			requires: /const DAYS = \d+;/
		},
		{
			line: 'No matches scheduled in the next {DAYS} days. Many leagues are between seasons in July.',
			reason: 'sama vakio kuin ylla, tyhjan listan teksti',
			requires: /const DAYS = \d+;/
		}
	],
	'routes/embed/fdr/+page.svelte': [
		{
			line: "{league === 'spl' ? 'Saudi Pro League' : 'FPL'} clean sheet % + fixture difficulty, next {gws}",
			reason:
				'FDR-embedin ikkuna tulee iframe-parametrista (?gws=1..6) ja sama luku suodattaa naytetyt ottelut (f.gw < nextGw + gws), ei xP-summan ikkuna',
			requires: /searchParams\.get\('gws'\)/
		}
	],
	'routes/spl/+page.svelte': [
		{
			line: 'subtitle: `next ${nearHorizon} GWs, GoalIQ match model`,',
			reason:
				'clean sheet % + fixture difficulty -kortti: ikkuna on cs.meta.near_horizon_gw, eri artefaktin oma kentta, ja sama luku rajaa naytetyt ottelut. HUOM: `?? 6` on keksitty oletus jos kentta puuttuu, kirjattu erillisena P2:na, ei tama portti'
		},
		{
			line: '<h2>Clean sheet % + fixture difficulty <span class="muted">(next {nearHorizon} GWs)</span></h2>',
			reason: 'sama ikkuna kuin kortissa (near_horizon_gw), ei xP-summa'
		}
	]
};

/** Rekisteroidyt ikkunanimet: nimi joka kantaa SUMMAN ikkunaa. Jokaisen on
 *  loydyttava, tultava lukijasta eika olla rivilistajohdannainen. */
const WINDOW_LABELS: Record<string, { name: string; reason: string }[]> = {
	'lib/components/XpTable.svelte': [
		{ name: 'horizon', reason: 'lukijan vastaus; kaikki taulukon summa-otsikot nojaavat tahan' },
		{
			name: 'horizonLabel',
			reason: 'Total xP:n ikkunan nimi (P1-2: oli yhden muokkauksen paassa colsLabelista)'
		},
		{
			name: 'cardWindowLabel',
			reason:
				'jakokortin alaotsikon ikkuna: kierros/ikkunasortti tai summasortilla lukijan ikkuna, kortti on kuva, joten tama ei saa olla sarakkeiden vali'
		}
	],
	'lib/components/ProductIntro.svelte': [
		{ name: 'horizon', reason: 'ilmaispinnan demotaulukon otsikko ja sarakenimi' }
	],
	'lib/components/Leaders.svelte': [
		{ name: 'xpHorizonN', reason: 'xP-sarakkeen nimilappu ("5GW xP")' }
	]
};

/** Ikkuna joka tulee PROPSINA: tiedostonsisainen dataflow ei nae kutsujaa,
 *  joten takuu on TYYPPI. Propin tyypin on oltava lukijan tyyppi, jottei se
 *  voi palata numeroksi jonka komponentti laskisi itse auki. */
const PROP_READERS: Record<string, { name: string; typeRe: RegExp; reason: string }[]> = {
	'lib/components/SquadHeaderRow.svelte': [
		{
			name: 'horizon',
			typeRe: /horizon\?:\s*XpHorizon\b/,
			reason:
				'otsikkorivi saa ikkunan valmiina RateTeamilta (REQUIRED_CALLERS); ennen 17.9 propi oli horizonGw: number ja komponentti laski valin itse gw + horizonGw - 1:sta'
		}
	]
};

/** `rows` = sarakkeiden maara. Sallittu vain kun kysymys ON sarakkeiden
 *  maara, perustelu riviin sidottuna. */
const ROWS_USES: Record<string, { line: string; reason: string }[]> = {
	'lib/components/PlayerCard.svelte': [
		{
			line: 'horizon: xpHorizon(meta).rows,',
			reason:
				'poissulkusyyn kynnys mitattiin build-aikana KAIKKIEN rivien summasta (build_fpl_xp.py: total < MIN_XP_TOTAL), joten luku on sarakkeiden maara eika serve-time-summan pituus'
		}
	]
};

/** Mekanismi (3) tassa portissa: mittaa korjauksen LASNAOLO. Ilman tata
 *  lukijan valmiin otsikon voisi poistaa ja portti olisi vihrea, koska
 *  mitaan vaaraa ei viela sanottaisi. */
const REQUIRED_FORMS: { file: string; re: RegExp; min: number; reason: string }[] = [
	{
		file: 'lib/components/XpTable.svelte',
		re: /\bhorizon\.totalTitle\b/g,
		min: 1,
		reason: 'Total xP -sarakkeen selite tulee valmiina lukijalta'
	},
	{
		file: 'lib/components/XpTable.svelte',
		re: /\bhorizon\.totalHelp\b/g,
		min: 1,
		reason: 'Total xP -selitelause tulee valmiina lukijalta (ei kutsupaikan ternaaria)'
	},
	{
		file: 'lib/components/PlayerCard.svelte',
		re: /\bxpTotalClaim\s*\(/g,
		min: 2,
		reason:
			'jakokortin mallirivi JA sivulause: kumpikin saa valmiin vaitteen (luku + ikkuna samasta kutsusta)'
	},
	{
		file: 'lib/components/Differentials.svelte',
		re: /\.totalTitle\b/g,
		min: 1,
		reason: 'Total xP -sarakkeen selite tulee valmiina lukijalta'
	},
	{
		file: READER,
		re: /\btotalTitle:\s*string/g,
		min: 1,
		reason: 'lukija julistaa valmiin otsikon tyypissaan'
	}
];

function escapeRe(s: string): string {
	return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Sijoitusten sulkeuma: nimet joiden lauseke osuu `seed`:iin tai mainitsee
 *  jo mukana olevan nimen. Fail-closed: liika leviaminen tekee portista
 *  tiukemman, ei loysemman. */
function spread(decls: Decl[], seed: RegExp): Set<string> {
	const names = new Set<string>();
	for (;;) {
		let grew = false;
		for (const d of decls) {
			if (names.has(d.name)) continue;
			const hit =
				seed.test(d.rhs) ||
				[...names].some((n) => new RegExp(`\\b${escapeRe(n)}\\b`).test(d.rhs));
			if (hit) {
				names.add(d.name);
				grew = true;
			}
		}
		if (!grew) break;
	}
	return names;
}

interface Surface {
	decls: Decl[];
	/** Nimet jotka ovat lukijan vastauksen johdannaisia. */
	reader: Set<string>;
	/** Nimet jotka ovat rivilistan johdannaisia. Nimi voi olla molemmissa
	 *  (esim. colsLabel): silloin se EI ole kelpo summan ikkuna. */
	rowy: Set<string>;
}

function surface(relPath: string, src: string): Surface {
	const decls = declarations(src);
	const reader = spread(decls, READER_CALL_RE);
	for (const pr of PROP_READERS[relPath] ?? []) reader.add(pr.name);
	return { decls, reader, rowy: spread(decls, ROW_SOURCE_RE) };
}

/** Korvaa lukijan kutsut (argumentit mukaan lukien) tunnisteella `__reader`. */
function stripReaderCalls(expr: string): string {
	const re = /\b(?:xpHorizon|xpTotalClaim)\s*\(/g;
	let out = '';
	let i = 0;
	for (;;) {
		re.lastIndex = i;
		const m = re.exec(expr);
		if (!m) return out + expr.slice(i);
		out += expr.slice(i, m.index) + '__reader';
		let depth = 1;
		let j = m.index + m[0].length;
		while (j < expr.length && depth > 0) {
			if (expr[j] === '(') depth += 1;
			else if (expr[j] === ')') depth -= 1;
			j += 1;
		}
		i = j;
	}
}

/** Lausekkeesta poistetaan se mika ON lukijan vastaus; jaljelle jaava
 *  tunniste on selittamaton ja portti hylkaa sen. */
function unexplained(expr: string, s: Surface): string[] {
	let e = stripReaderCalls(expr);
	const ok = ['__reader', ...[...s.reader].filter((n) => !s.rowy.has(n))];
	for (const n of ok)
		e = e.replace(
			new RegExp(`\\b${escapeRe(n)}\\b\\s*\\??\\.\\s*(?:${READER_FIELDS})\\b`, 'g'),
			' '
		);
	e = e.replace(/'[^']*'|"[^"]*"|`[^`]*`/g, ' ');
	const KEEP = new Set(['null', 'undefined', 'true', 'false']);
	return (e.match(/[A-Za-z_$][\w$]*/g) ?? []).filter((t) => !KEEP.has(t));
}

/** A: julkinen vaite summan ikkunasta interpoloi vain lukijan vastauksen. */
function claimProblems(relPath: string, src: string): string[] {
	const s = surface(relPath, src);
	const exc = CLAIM_EXCEPTIONS[relPath] ?? [];
	const out: string[] = [];
	for (const l of codeLines(src)) {
		if (!CLAIM_MARKERS.some((re) => re.test(l.text))) continue;
		if (exc.some((e) => e.line === l.text.trim() && (!e.requires || e.requires.test(src))))
			continue;
		for (const it of interpolations(l.text)) {
			if (it.block) continue;
			const rest = unexplained(it.text, s);
			if (rest.length > 0)
				out.push(
					`${relPath}:${l.n}: summan ikkunan vaite lukee muuta kuin lukijaa (${rest.join(', ')}): ${l.text.trim()}`
				);
		}
	}
	return out;
}

/** B: rekisteroity ikkunanimi on lukijajohdannainen eika rivilistajohdannainen. */
function labelProblems(relPath: string, src: string): string[] {
	const s = surface(relPath, src);
	const out: string[] = [];
	for (const reg of WINDOW_LABELS[relPath] ?? []) {
		const ds = s.decls.filter((d) => d.name === reg.name);
		if (ds.length === 0) {
			out.push(
				`${relPath}: rekisteroity ikkunanimi \`${reg.name}\` on kadonnut, paivita WINDOW_LABELS ja perustele (${reg.reason})`
			);
			continue;
		}
		for (const d of ds) {
			if (!s.reader.has(d.name))
				out.push(`${relPath}:${d.from}: \`${d.name}\` ei tule lukijasta ($lib/xpHorizon)`);
			if (s.rowy.has(d.name))
				out.push(
					`${relPath}:${d.from}: \`${d.name}\` on rivilistan (gameweeks/gwCols) johdannainen, summan ikkuna ei tule sarakkeista`
				);
		}
	}
	return out;
}

/** C: `rows` vain perustellulla poikkeuksella. */
function rowsProblems(relPath: string, src: string): string[] {
	const s = surface(relPath, src);
	const allow = ROWS_USES[relPath] ?? [];
	const names = [...s.reader].map(escapeRe).join('|') || '__none__';
	const re = new RegExp(
		`(?:\\bxpHorizon\\s*\\([^()]*\\)|\\b(?:${names})\\b)\\s*\\??\\.\\s*rows\\b`
	);
	return codeLines(src)
		.filter((l) => re.test(l.text))
		.filter((l) => !allow.some((a) => a.line === l.text.trim()))
		.map(
			(l) =>
				`${relPath}:${l.n}: \`rows\` on sarakkeiden maara, ei summan ikkuna, perustele ROWS_USES-listalla: ${l.text.trim()}`
		);
}

describe('summan ikkunan vaite: vain lukija saa vastata (18.9 laajennus)', () => {
	const files = walk(SRC).map(rel);

	it('A: yksikaan julkinen vaite ei interpoloi rivilistaa eika tuntematonta nimea', () => {
		const problems = files
			.filter((f) => !NOT_SCANNED.has(f))
			.flatMap((f) => claimProblems(f, read(f)));
		expect(problems).toEqual([]);
	});

	it('A2: poikkeuslista ei vanhene, jokainen poikkeusrivi loytyy koodista sanatarkasti', () => {
		for (const [f, list] of Object.entries(CLAIM_EXCEPTIONS)) {
			const lines = codeLines(read(f)).map((l) => l.text.trim());
			const src = read(f);
			for (const e of list) {
				expect(
					lines,
					`${f}: poikkeus ilman osumaa, poista tai paivita se (${e.reason})`
				).toContain(e.line);
				if (e.requires)
					expect(
						e.requires.test(src),
						`${f}: poikkeuksen perustelu nojaa muotoon ${e.requires} joka on kadonnut (${e.reason})`
					).toBe(true);
			}
		}
	});

	it('B: rekisteroidyt ikkunanimet tulevat lukijasta, eivat sarakkeista', () => {
		const problems = Object.keys(WINDOW_LABELS).flatMap((f) => labelProblems(f, read(f)));
		expect(problems).toEqual([]);
	});

	it('B2: propsina kulkeva ikkuna on tyypitetty lukijan tyypiksi', () => {
		for (const [f, list] of Object.entries(PROP_READERS)) {
			const src = read(f);
			for (const pr of list)
				expect(
					pr.typeRe.test(src),
					`${f}: propin \`${pr.name}\` tyyppi ei ole XpHorizon (${pr.reason})`
				).toBe(true);
		}
	});

	it('C: `rows` vain perustelluissa paikoissa, ja jokainen perustelu osuu', () => {
		const problems = files
			.filter((f) => !NOT_SCANNED.has(f))
			.flatMap((f) => rowsProblems(f, read(f)));
		expect(problems).toEqual([]);
		for (const [f, list] of Object.entries(ROWS_USES)) {
			const lines = codeLines(read(f)).map((l) => l.text.trim());
			for (const a of list)
				expect(lines, `${f}: ROWS_USES-poikkeus ilman osumaa (${a.reason})`).toContain(a.line);
		}
	});

	it('D: korjauksen muodot ovat paikallaan (portti mittaa myos lasnaolon)', () => {
		for (const r of REQUIRED_FORMS) {
			const hits = (read(r.file).match(r.re) ?? []).length;
			expect(hits, `${r.file}: ${r.reason}`).toBeGreaterThanOrEqual(r.min);
		}
	});

	it('D2: kvantifioitua ikkunaa ei kirjoiteta literaalina lukijan ulkopuolella', () => {
		const LITERAL_WINDOW = /\bnext\s+\d+\s*(?:GW|gameweek)/i;
		const problems: string[] = [];
		for (const f of files) {
			if (NOT_SCANNED.has(f)) continue;
			for (const l of findInCode(read(f), LITERAL_WINDOW))
				problems.push(`${f}:${l.n}: ${l.text.trim()}`);
		}
		expect(problems).toEqual([]);
	});
});

describe('erotteleva fikstuuri: 18.9 saannot kaatavat sen minka 17.9 portti paasti lapi', () => {
	/** P1-1: jakokortin mallirivi + sivulause rivilistan pituudesta. */
	const P1_1 = [
		'import { xpHorizon, xpTotalClaim } from "$lib/xpHorizon";',
		'const rows = xpHorizon(meta).rows;',
		'const line = `${p.xp_horizon_total.toFixed(1)} xP projected over the next ${(p.gameweeks ?? []).length} gameweeks`;'
	].join('\n');

	/** P1-2: Total xP:n ikkuna sarakkeista. */
	const P1_2 = [
		'import { xpHorizon } from "$lib/xpHorizon";',
		'let horizon = $derived(xpHorizon(data.meta));',
		'let gwCols = $derived(data.players[0]?.gameweeks?.map((g) => g.gw) ?? []);',
		'let colsLabel = $derived(`GW${gwCols[0]}-GW${gwCols[gwCols.length - 1]}`);',
		'let horizonLabel = $derived(colsLabel);',
		'let cardWindowLabel = $derived(sortWindowLabel ?? horizonLabel);',
		'<th class="num"><abbr title="Sum of expected points, {horizonLabel}">Total xP</abbr></th>'
	].join('\n');

	/** Kolmas muoto: luku tulee lukijasta, mutta VAARASTA kentasta (`rows` =
	 *  sarakkeiden maara, joka sisaltaa jo alkaneen kierroksen). Tama lipuisi
	 *  lapi seka 17.9 portista etta pelkasta rivilista-tarkistuksesta. */
	const P1_3 = [
		'import { xpHorizon } from "$lib/xpHorizon";',
		'let horizon = $derived(xpHorizon(data.meta));',
		'<th><abbr title="Sum of expected points, {horizon.rows} GWs">Total xP</abbr></th>'
	].join('\n');

	/** Neljas muoto: ikkuna rakennetaan APURIFUNKTIOSSA, ja kutsupaikka
	 *  nayttaa lukijajohdannaiselta koska lukijan arvo menee parametrina.
	 *  Tama vaati declScanin korjaamista 18.9: funktion RUNKO ei ollut ennen
	 *  osa sijoituksen lauseketta, joten apuri oli porteilta nakymaton. */
	const P1_4 = [
		'import { xpHorizon } from "$lib/xpHorizon";',
		'let horizon = $derived(xpHorizon(data.meta));',
		'let gwCols = $derived(data.players[0]?.gameweeks?.map((g) => g.gw) ?? []);',
		'function winLabel(h) {',
		'\treturn gwCols.length > 0 ? `GW${gwCols[0]}-GW${gwCols[gwCols.length - 1]}` : h.label;',
		'}',
		'let horizonLabel = $derived(winLabel(horizon));',
		'let cardWindowLabel = $derived(horizonLabel);'
	].join('\n');

	const oldGateSilent = (f: string, src: string) => {
		const code = codeLines(src)
			.map((l) => l.text)
			.join('\n');
		return (
			strayReads(f, src).length === 0 &&
			callerProblems(f, src).length === 0 &&
			!NEXT_CLAIM_RE.test(code) &&
			!INVENTED_DEFAULT_RE.test(code)
		);
	};

	it('P1-1 (jakokortin mallirivi): 17.9 portti vihrea, 18.9 saanto punainen', () => {
		const f = 'lib/components/PlayerCard.svelte';
		expect(oldGateSilent(f, P1_1)).toBe(true);
		expect(claimProblems(f, P1_1).length).toBeGreaterThan(0);
	});

	it('P1-2 (Total xP sarakkeista): 17.9 portti vihrea, 18.9 saannot punaisia', () => {
		const f = 'lib/components/XpTable.svelte';
		expect(oldGateSilent(f, P1_2)).toBe(true);
		expect(labelProblems(f, P1_2).length).toBeGreaterThan(0);
		expect(claimProblems(f, P1_2).length).toBeGreaterThan(0);
	});

	it('P1-3 (`rows` summan ikkunaksi): 17.9 portti vihrea, 18.9 saanto punainen', () => {
		const f = 'lib/components/XpTable.svelte';
		expect(oldGateSilent(f, P1_3)).toBe(true);
		expect(rowsProblems(f, P1_3).length).toBeGreaterThan(0);
	});

	it('P1-4 (apurifunktio ikkunan rakentajana): lukijanimi parametrina ei riita', () => {
		const f = 'lib/components/XpTable.svelte';
		expect(oldGateSilent(f, P1_4)).toBe(true);
		const problems = labelProblems(f, P1_4);
		// Kutsupaikka NAYTTAA lukijajohdannaiselta (rhs mainitsee `horizon`),
		// joten pelkka "tuleeko lukijasta" -puoli olisi vihrea: kiinni jaa
		// nimenomaan rivilista-puoli, ja vain siksi etta apurin runko luetaan.
		expect(problems.some((p) => p.includes('rivilistan'))).toBe(true);
		expect(problems.some((p) => p.includes('horizonLabel'))).toBe(true);
		expect(problems.some((p) => p.includes('cardWindowLabel'))).toBe(true);
	});

	it('korjatut muodot lapaisevat: valmis otsikko ja valmis vaite', () => {
		const good = [
			'import { xpHorizon, xpTotalClaim } from "$lib/xpHorizon";',
			'let horizon = $derived(xpHorizon(data.meta));',
			'let horizonLabel = $derived(horizon.label);',
			'let cardWindowLabel = $derived(sortWindowLabel ?? horizonLabel);',
			'<th class="num"><abbr title={horizon.totalTitle}>Total xP</abbr></th>',
			'<p>{xpTotalClaim(meta, tot).text}</p>'
		].join('\n');
		const f = 'lib/components/XpTable.svelte';
		expect(claimProblems(f, good)).toEqual([]);
		expect(labelProblems(f, good)).toEqual([]);
		expect(rowsProblems(f, good)).toEqual([]);
	});

	it('rekisteroidyn ikkunanimen poisto kaataa portin (rekisteri ei vanhene hiljaa)', () => {
		const gone = 'let horizon = $derived(xpHorizon(data.meta));';
		const problems = labelProblems('lib/components/XpTable.svelte', gone);
		expect(problems.some((p) => p.includes('horizonLabel'))).toBe(true);
		expect(problems.some((p) => p.includes('cardWindowLabel'))).toBe(true);
	});

	it('template-literaalin ja markupin interpolaatio kasitellaan samoin', () => {
		const f = 'lib/components/PlayerCard.svelte';
		const tpl = 'const s = `Total xP ${(p.gameweeks ?? []).length}`;';
		const mk = '<dt>Total xP, {(player.gameweeks ?? []).length} GWs</dt>';
		expect(claimProblems(f, tpl).length).toBe(1);
		expect(claimProblems(f, mk).length).toBe(1);
	});
});

/* ========================================================================
 * 18.9 SULAUTUS: saanto E — SUMMA JA RIVILISTAN PITUUS SAMALLA RIVILLA
 * ------------------------------------------------------------------------
 * MISTA TAMA TULI: SPA:lla oli kaksi kilpailevaa ikkunalukijaa. Havinneen
 * (`$lib/horizonWindow`, haara fix/xp-horizon-alkanut-kierros) portti
 * `tests/test_horizon_window_label_discipline.py` kantoi saannon R2, jota
 * TALLA portilla ei ollut. Ennen kuin havinnyt portti purettiin, sen
 * saannot ajettiin MUTAATIONA tata porttia vastaan — ja R2 loysi kaksi
 * todellista aukkoa:
 *
 *   MUT-1  PlayerCard.svelte:
 *          `${(player.xp_horizon_total ?? 0).toFixed(1)} pts across
 *           ${(player.gameweeks ?? []).length} GWs`
 *   MUT-2  RateTeam.svelte:
 *          `${(data?.team_xp_horizon ?? 0).toFixed(1)} pts,
 *           ${(gwCols ?? []).length} rounds ahead`
 *
 * Kumpikin ISTUTETTIIN oikeaan tiedostoon ja `npx vitest run` oli 62/62
 * VIHREA (mitattu 18.9). Syy: saanto A (`claimProblems`) laukeaa vain kun
 * rivilla on tunnistettu VAITEMERKKI ("Total xP", "xP projected", ...).
 * Sanavalinta joka ei ole listalla ("pts across", "rounds ahead") vie
 * saman vaitteen portin ohi. Tasan se mita muisti
 * `portti-kirjoitetaan-nahdylle-muodolle` varoittaa: saanto vartioi
 * TAPAUSTA (nahtyja sanoja), ei LUOKKAA.
 *
 * E ei kysy sanoja vaan MUOTOA: jos rivilla on horisonttisumma JA
 * rivilistan pituus, se on argumentoitava. Merkkilista pysyy (parempi
 * virheilmoitus ja se osuu myos ilman `.length`ia), mutta se ei ole enaa
 * ainoa portti julkiseen vaitteeseen.
 * ====================================================================== */

/** Horisonttisumma ja sen johdannaiset. Sama lista kuin havinneen portin
 *  `SUM_KEYS` — sopimuksen kentat, ei sanavalintoja. */
const SUM_KEY_RE =
	/\b(?:xp_horizon_total|team_xp_horizon|xi_xp_horizon|margin_xp_horizon|optimal_xp_horizon)\b/;
/** Rivilistan pituus tai sarakkeiden maara. */
const ROW_COUNT_RE = /\.length\b|\bhorizon_gw\b/;

/** Poikkeus sidotaan RIVIN TEKSTIIN perusteluineen, kuten CLAIM_EXCEPTIONS. */
const SUM_AND_COUNT_EXCEPTIONS: Record<string, { line: string; reason: string }[]> = {};

/** E: summa + rivilistan pituus samalla rivilla. */
function sumAndCountProblems(relPath: string, src: string): string[] {
	const allow = SUM_AND_COUNT_EXCEPTIONS[relPath] ?? [];
	return codeLines(src)
		.filter((l) => SUM_KEY_RE.test(l.text) && ROW_COUNT_RE.test(l.text))
		.filter((l) => !allow.some((a) => a.line === l.text.trim()))
		.map(
			(l) =>
				`${relPath}:${l.n}: horisonttisumma ja rivilistan pituus samalla rivilla, summan ikkuna tulee lukijasta (xpHorizon/xpTotalClaim), ei sarakkeista: ${l.text.trim()}`
		);
}

describe('saanto E: summan ikkunaa ei nimeta rivien maaralla (sulautus havinneesta portista)', () => {
	const files = walk(SRC).map(rel);

	it('E: yksikaan pinta ei kirjoita summaa ja rivilistan pituutta samalle riville', () => {
		const problems = files
			.filter((f) => !NOT_SCANNED.has(f))
			.flatMap((f) => sumAndCountProblems(f, read(f)));
		expect(problems).toEqual([]);
	});

	it('E2: poikkeuslista ei vanhene, jokainen poikkeusrivi loytyy koodista', () => {
		for (const [f, list] of Object.entries(SUM_AND_COUNT_EXCEPTIONS)) {
			const lines = codeLines(read(f)).map((l) => l.text.trim());
			for (const a of list)
				expect(lines, `${f}: poikkeus ilman osumaa (${a.reason})`).toContain(a.line);
		}
	});

	/** EROTTELEVA FIKSTUURI: vaara haara oikeasti onnistuisi ilman E:ta.
	 *  Molemmat muodot ovat MITATTUJA — ne ajettiin tata porttia vastaan
	 *  18.9 ja portti oli vihrea. */
	const MUT_1 =
		'\tconst blurb = `${(player.xp_horizon_total ?? 0).toFixed(1)} pts across ${(player.gameweeks ?? []).length} GWs`;';
	const MUT_2 =
		'\tconst teamBlurb = `${(data?.team_xp_horizon ?? 0).toFixed(1)} pts, ${(gwCols ?? []).length} rounds ahead`;';

	it('MUT-1 (pelaajakortin sivulause ilman vaitemerkkia): A vihrea, E punainen', () => {
		const f = 'lib/components/PlayerCard.svelte';
		expect(claimProblems(f, MUT_1), 'saanto A EI nae tata, siksi E on olemassa').toEqual([]);
		expect(rowsProblems(f, MUT_1)).toEqual([]);
		expect(sumAndCountProblems(f, MUT_1).length).toBeGreaterThan(0);
	});

	it('MUT-2 (johdettu summa-avain RateTeamissa): A vihrea, E punainen', () => {
		const f = 'lib/components/RateTeam.svelte';
		expect(claimProblems(f, MUT_2), 'saanto A EI nae tatakaan').toEqual([]);
		expect(sumAndCountProblems(f, MUT_2).length).toBeGreaterThan(0);
	});

	it('E ei kiellä summan nayttamista, vain sen nimeamista sarakkeilla', () => {
		const ok = '\tconst v = `${player.xp_horizon_total.toFixed(1)} xP`;';
		expect(sumAndCountProblems('lib/components/PlayerCard.svelte', ok)).toEqual([]);
	});

	it('E ei laukea kommentista', () => {
		const c = '\t// xp_horizon_total vs gameweeks.length: eri luku kesken kierroksen';
		expect(sumAndCountProblems('lib/components/XpTable.svelte', c)).toEqual([]);
	});
});
