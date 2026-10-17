/**
 * Portti: henkilokohtaiset FPL-tyokalut lukitaan YHDEN lukijan kautta
 * (17.10.2026, Villen paatos "tyokalut taakse", CLAUDE.md 6a).
 *
 * Neljä vaitetta, jokaisella erotteleva kontrolli:
 *   1. lukija (`personalLock`) on lukittu kun ei Premiumia TAI palvelin
 *      lukitsi vastauksen (`meta.locked_tool`), ei pelkasta `meta.masked`ista;
 *      synteettiset vaiheet ennen ja jalkeen kytkimen 21.10 (6a kohta 3),
 *   2. jokainen henkilokohtainen komponentti kysyy lukitusta tasta lukijasta
 *      (kutsupaikka, ei funktio: muisti testi-kutsuu-funktiota-ei-kutsupaikkaa),
 *   3. komponentti joka hakee henkilokohtaista dataa (oma joukkue, kirjatut
 *      paatokset) EI voi syntya listan ohi: se on joko lukijan kayttaja tai
 *      poikkeuslistalla perustelun kanssa (6a kohta 2),
 *   4. esityskomponentit (pitch, hold-verdikti, otsikkorivi, kirjausnapit)
 *      piirretaan vain lukitsevista komponenteista tai premium-tason
 *      tyokalusta, ja kutsujat valittavat tason (`{premium}`).
 */
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';
import { TOOLS } from './tools';
import {
	LOCK_COPY,
	PERSONAL_LOCK_SOURCE,
	lockUpgradeSource,
	personalLock,
	ratingPreview,
	serverLockedTool,
	type PersonalSlug
} from './personalLock';

const DIR = resolve(__dirname, 'components');
const read = (f: string) => readFileSync(resolve(DIR, f), 'utf-8').replace(/\r\n/g, '\n');
const script = (src: string) => blankComments(src.slice(0, src.lastIndexOf('</script>')));
const markup = (src: string) => blankComments(src.slice(src.lastIndexOf('</script>')));

/* ---------------------------------------------------------------------------
 * 1. Lukija
 * ------------------------------------------------------------------------- */

/** Palvelimen vastaukset synteettisina vaiheina (api/premium.py):
 *  - ennen kytkinta ilmainen saa tayden vastauksen (ei locked_toolia),
 *  - jalkeen ilmainen saa lukitun (masked + locked_tool),
 *  - Premium saa aina tayden,
 *  - vanha esimakumaski: masked ilman locked_toolia (rate-teamin siirtolista). */
const FULL = { meta: { entry: 1 } };
const LOCKED = { meta: { masked: true, locked_tool: 'rate-my-team', mask: 'rating only' } };
const OLD_TEASER_MASK = { meta: { masked: true, mask: '0 of 5 transfer suggestions' } };

describe('lukija: personalLock', () => {
	it('ilman Premiumia aina lukittu, myos ennen kytkinta (taysi vastaus)', () => {
		expect(personalLock(false)).toBe(true);
		expect(personalLock(false, FULL)).toBe(true);
		expect(personalLock(false, LOCKED)).toBe(true);
		expect(personalLock(false, null, undefined)).toBe(true);
	});

	it('Premium: auki, paitsi kun palvelin lukitsi vastauksen', () => {
		expect(personalLock(true)).toBe(false);
		expect(personalLock(true, FULL)).toBe(false);
		expect(personalLock(true, null)).toBe(false);
		expect(personalLock(true, LOCKED)).toBe(true);
		// Yksikin lukittu vastaus lukitsee nakyman (esim. Team 2 + model-squad).
		expect(personalLock(true, FULL, LOCKED)).toBe(true);
	});

	it('pelkka meta.masked EI ole lukitus (vanhat esimakumaskit)', () => {
		expect(serverLockedTool(OLD_TEASER_MASK)).toBeNull();
		expect(personalLock(true, OLD_TEASER_MASK)).toBe(false);
	});

	it('tyhja tai vaaran tyyppinen locked_tool ei ole lukitus, roska ei kaada', () => {
		expect(serverLockedTool({ meta: { locked_tool: '' } })).toBeNull();
		expect(serverLockedTool({ meta: { locked_tool: '  ' } })).toBeNull();
		expect(serverLockedTool({ meta: { locked_tool: 1 } })).toBeNull();
		expect(serverLockedTool({ meta: null })).toBeNull();
		expect(serverLockedTool({ meta: 'x' })).toBeNull();
		expect(serverLockedTool(null)).toBeNull();
		expect(serverLockedTool({ meta: { locked_tool: 'gw-review' } })).toBe('gw-review');
	});

	it('analytiikan lahteet: paywall_shown personal_lock, CTA personal_lock_<tool>', () => {
		expect(PERSONAL_LOCK_SOURCE).toBe('personal_lock');
		expect(lockUpgradeSource('gw-review')).toBe('personal_lock_gw-review');
	});
});

describe('esimaku: ratingPreview', () => {
	const over = 'over the next 6 GWs';

	it('prosentti ja mittapohja samassa lauseessa, ei arvosanamuotoa', () => {
		const p = ratingPreview({ rating: 88, percentile: 88.4, beats_benchmark: false }, over);
		expect(p?.pct).toBe(88);
		expect(p?.text).toContain('88% of the points of the strongest squad the model found');
		expect(p?.text).toContain(over);
		expect(p?.text).toContain('Captain bonus left out on both sides');
		expect(p?.text).not.toMatch(/\/100/);
	});

	it('ylitys sanotaan ilman prosenttia (palvelin leikkaa sataan)', () => {
		const p = ratingPreview({ rating: 100, percentile: 100, beats_benchmark: true }, over);
		expect(p?.pct).toBeNull();
		expect(p?.text).toMatch(/^Your XI projects more points than the strongest squad/);
	});

	it('vanha API ilman ratingia lukee percentilen, ilman lukuja ei lausetta', () => {
		expect(ratingPreview({ percentile: 71.6 }, over)?.pct).toBe(72);
		expect(ratingPreview({}, over)).toBeNull();
		expect(ratingPreview(null, over)).toBeNull();
	});
});

describe('lukkoteksti: LOCK_COPY', () => {
	it('jokaisella lukolla on otsikko joka nimeaa GoalIQ Premiumin, ja runko', () => {
		for (const [slug, c] of Object.entries(LOCK_COPY)) {
			expect(c.title, slug).toMatch(/part of GoalIQ Premium$/);
			expect(c.body.length, slug).toBeGreaterThan(40);
		}
	});

	it('ei em/en dashia, ei hintoja, ei kaarevia heittomerkkeja', () => {
		for (const [slug, c] of Object.entries(LOCK_COPY)) {
			const t = `${c.title} ${c.body}`;
			expect(t, slug).not.toMatch(/[–—]/);
			expect(t, slug).not.toMatch(/[€£$]|\d+[.,]\d\d/);
			expect(t, slug).not.toMatch(/[‘’“”]/);
		}
	});
});

/* ---------------------------------------------------------------------------
 * 2. Kutsupaikat: henkilokohtainen komponentti kysyy lukijalta
 * ------------------------------------------------------------------------- */

/** Komponentit jotka piirtavat kayttajan oman joukkueen tai paatosten dataa
 *  ja lukitsevat sen itse. Lisays tahan on paatos; poisto vaatii ettei
 *  komponentti enaa nayta henkilokohtaista dataa (portti 3 tarkistaa). */
const PERSONAL_COMPONENTS = [
	'RateTeam.svelte',
	'ThisWeek.svelte',
	'DecisionCard.svelte',
	'DefConLive.svelte',
	'GwReview.svelte',
	'BeatTheModel.svelte',
	'SeasonLedger.svelte',
	'SquadNews.svelte',
	'MiniLeague.svelte',
	'Watchlist.svelte',
	'FitChecker.svelte',
	'PriceWatch.svelte',
	'Differentials.svelte'
];

/** Ongelmat yhden komponentin lahteessa: tuo lukijan ja kutsuu sita
 *  koodissa (kommentit tyhjatty, joten selittava kommentti ei kelpaa). */
function lockCallProblems(src: string): string[] {
	const p: string[] = [];
	const s = script(src);
	if (!/import\s*\{[^}]*\bpersonalLock\b[^}]*\}\s*from\s*'\$lib\/personalLock'/.test(s))
		p.push("ei tuo personalLockia '$lib/personalLock'ista");
	const calls = (s.match(/\bpersonalLock\(/g) ?? []).length;
	if (calls === 0) p.push('ei kutsu personalLock(...)');
	// Oma ehto lukijan ohi: `!premium &&` tai `premium ?` lukitusehtona ilman
	// lukijaa. Sallittu vain jos lukija on myos kaytossa (kutsujen maara > 0).
	return p;
}

describe('kutsupaikat: jokainen henkilokohtainen komponentti kysyy lukijalta', () => {
	for (const f of PERSONAL_COMPONENTS) {
		it(f, () => {
			expect(lockCallProblems(read(f))).toEqual([]);
		});
	}

	it('erotteleva kontrolli: ilman lukijan kutsua portti kaatuu', () => {
		const src = read('GwReview.svelte');
		const without = src.replace(/personalLock\(/g, 'Boolean(');
		expect(without).not.toBe(src);
		expect(lockCallProblems(without)).toContain('ei kutsu personalLock(...)');
	});

	it('erotteleva kontrolli: kommentissa mainittu lukija ei kelpaa', () => {
		const fake =
			"<script lang=\"ts\">\n// import { personalLock } from '$lib/personalLock';\n// personalLock(premium)\nconst x = 1;\n</script>\n<p>{x}</p>";
		expect(lockCallProblems(fake).length).toBe(2);
	});

	it('lukitusnakyma piirtyy aina PersonalLockista, ei omasta lauseesta', () => {
		// Jokainen komponentti joka nayttaa oman lukkonsa kayttaa yhteista
		// komponenttia; SeasonLedger ja SquadNews eivat piirra lukkoa (ne ovat
		// Rate my teamin lukon takana) ja ThisWeek valittaa lukot lapsilleen.
		const silent = new Set(['SeasonLedger.svelte', 'SquadNews.svelte', 'ThisWeek.svelte']);
		for (const f of PERSONAL_COMPONENTS) {
			if (silent.has(f)) continue;
			expect(markup(read(f)), f).toMatch(/<PersonalLock\s+tool="[a-z-]+"/);
		}
	});

	it('jokainen PersonalLockin slug on lukijan taulussa', () => {
		const known = new Set(Object.keys(LOCK_COPY));
		for (const f of readdirSync(DIR).filter((x) => x.endsWith('.svelte'))) {
			for (const m of markup(read(f)).matchAll(/<PersonalLock\s+tool="([a-z-]+)"/g)) {
				expect(known.has(m[1] as PersonalSlug), `${f}: ${m[1]}`).toBe(true);
			}
		}
	});
});

/* ---------------------------------------------------------------------------
 * 3. Kattavuus: henkilokohtaista dataa hakeva komponentti ei synny listan ohi
 * ------------------------------------------------------------------------- */

/** Haut jotka palauttavat kayttajan OMAN joukkueen tai paatosten dataa
 *  (palvelimen PERSONAL_TOOL_ROUTES + Supabasen kirjaukset). */
const PERSONAL_FETCH =
	/\b(fetchRateTeam|fetchRateTeamManual|fetchModelSquad|fetchGwReview|fetchMyTeamLedger|fetchFit|fetchDefconLive|fetchH2h|fetchPriceWatch|fetchDifferentials|fetchCaptain|loadDecisions|logDecision)\(/;

/** Poikkeukset perusteluineen (6a kohta 2). Komponentti joka hakee
 *  henkilokohtaista dataa mutta ei itse kysy lukijalta. */
const PERSONAL_FETCH_EXCEPTIONS: Record<string, string> = {
	'WeeklyActions.svelte':
		'Kirjausnapit (loadDecisions/logDecision) piirretaan vain DecisionCardin oman joukkueen haarassa (`own`), joka on personalLockin takana; portti 4 tarkistaa kutsupaikan.'
};

function uncovered(files: Record<string, string>): string[] {
	return Object.entries(files)
		.filter(([, src]) => PERSONAL_FETCH.test(script(src)))
		.map(([f]) => f)
		.filter((f) => !PERSONAL_COMPONENTS.includes(f) && !(f in PERSONAL_FETCH_EXCEPTIONS));
}

describe('kattavuus: uusi henkilokohtainen komponentti ei unohdu', () => {
	const all = Object.fromEntries(
		readdirSync(DIR)
			.filter((f) => f.endsWith('.svelte'))
			.map((f) => [f, read(f)])
	);

	it('jokainen henkilokohtaista dataa hakeva komponentti on listalla tai poikkeus', () => {
		expect(uncovered(all)).toEqual([]);
	});

	it('poikkeuksilla on perustelu, ja ne oikeasti hakevat (ei kuollutta riviä)', () => {
		for (const [f, why] of Object.entries(PERSONAL_FETCH_EXCEPTIONS)) {
			expect(why.length, f).toBeGreaterThanOrEqual(40);
			expect(all[f], f).toBeDefined();
			expect(PERSONAL_FETCH.test(script(all[f])), f).toBe(true);
		}
	});

	it('erotteleva kontrolli: uusi komponentti oman joukkueen haulla kaatuu', () => {
		const fake = {
			...all,
			'NewSquadThing.svelte':
				"<script lang=\"ts\">\nimport { fetchGwReview } from '$lib/api';\nfetchGwReview(1);\n</script>\n<p>x</p>"
		};
		expect(uncovered(fake)).toEqual(['NewSquadThing.svelte']);
	});
});

/* ---------------------------------------------------------------------------
 * 4. Esityskomponentit ja tason valitys
 * ------------------------------------------------------------------------- */

/** Komponentit jotka piirtavat henkilokohtaista dataa mutta eivat lukitse
 *  itse: ne saavat datan lukitsevalta isannalta. Isanta on joko listalla
 *  (portti 2) tai premium-tason rekisterityokalu (LockedToolPreview ottaa
 *  reitin, ToolsHome piirtaa sen vain `premium && show(...)`-haarassa). */
const PRESENTATIONAL = [
	'HoldVerdictCard',
	'TeamPitchManager',
	'SquadHeaderRow',
	'WeeklyActions',
	'ProjectionsPanel'
];
const PREMIUM_TOOL_HOSTS: Record<string, string> = {
	'TransferPlanner.svelte': 'transfer-planner'
};

/** Esityskomponentin kutsupaikat jotka eivat ole lukitsevia isantia. */
function presentationalProblems(files: Record<string, string>): string[] {
	const bad: string[] = [];
	for (const [f, src] of Object.entries(files)) {
		const m = markup(src);
		for (const c of PRESENTATIONAL) {
			if (!new RegExp(`<${c}\\b`).test(m)) continue;
			if (PERSONAL_COMPONENTS.includes(f)) continue;
			if (f in PREMIUM_TOOL_HOSTS) continue;
			bad.push(`${f} piirtaa ${c}`);
		}
	}
	return bad;
}

/** Komponenttitagit (itsesulkeutuvat) nimelta: alusta seuraavaan `/>`:iin.
 *  Ei regexin [^>]-luokkaa: `onUseTeam={() => ...}` sisaltaa `>`-merkin, ja
 *  sellainen tagi jaisi hiljaa tarkistamatta. Sulkematon tagi palautetaan
 *  kokonaisena loppuun asti (portti kaatuu, ei ohita). */
function tags(m: string, name: string): string[] {
	const out: string[] = [];
	const re = new RegExp(`<${name}\\b`, 'g');
	for (const hit of m.matchAll(re)) {
		const end = m.indexOf('/>', hit.index);
		out.push(end === -1 ? m.slice(hit.index) : m.slice(hit.index, end + 2));
	}
	return out;
}

function premiumPropProblems(hostFiles: Record<string, string>): string[] {
	const bad: string[] = [];
	for (const [h, src] of Object.entries(hostFiles)) {
		const m = markup(src);
		for (const f of PERSONAL_COMPONENTS) {
			const name = f.replace('.svelte', '');
			for (const tag of tags(m, name)) {
				if (!/\{premium\}|\bpremium=\{/.test(tag)) bad.push(`${h}: <${name}> ilman premiumia`);
			}
		}
	}
	return bad;
}

describe('esityskomponentit piirretaan vain lukitsevista isannista', () => {
	const files = Object.fromEntries(
		readdirSync(DIR)
			.filter((f) => f.endsWith('.svelte'))
			.map((f) => [f, read(f)])
	);

	it('jokainen kutsupaikka on lukitseva komponentti tai premium-tason tyokalu', () => {
		expect(presentationalProblems(files)).toEqual([]);
	});

	it('erotteleva kontrolli: esityskomponentti uudessa isannassa kaatuu', () => {
		const fake = { ...files, 'NewHost.svelte': '<script lang="ts"></script>\n<TeamPitchManager players={[]} />' };
		expect(presentationalProblems(fake)).toEqual(['NewHost.svelte piirtaa TeamPitchManager']);
	});

	it('premium-isannat ovat rekisterissa premium-tasoa ja ToolsHome piirtaa ne vain Premiumille', () => {
		const home = markup(read('ToolsHome.svelte'));
		for (const [f, slug] of Object.entries(PREMIUM_TOOL_HOSTS)) {
			expect(TOOLS.find((t) => t.slug === slug)?.tier, f).toBe('premium');
			expect(home, f).toMatch(new RegExp(`\\{#if premium && show\\('${slug}'\\)\\}`));
		}
	});

	it('kutsujat valittavat tason jokaiselle henkilokohtaiselle komponentille', () => {
		// Puuttuva {premium} lukitsisi Premium-kayttajan (oletus false):
		// fail-closed, mutta nakyva regressio maksavalle.
		const hosts = Object.fromEntries(
			['ToolsHome.svelte', 'ThisWeek.svelte', 'RateTeam.svelte'].map((f) => [f, files[f]])
		);
		// Kontrolli tyhjaa vastaan: isannissa ON tageja joita mitata.
		const n = Object.values(hosts).reduce(
			(s, src) =>
				s + PERSONAL_COMPONENTS.reduce((k, f) => k + tags(markup(src), f.replace('.svelte', '')).length, 0),
			0
		);
		expect(n).toBeGreaterThanOrEqual(12);
		expect(premiumPropProblems(hosts)).toEqual([]);
	});

	it('erotteleva kontrolli: tagi ilman premiumia (myos nuolifunktion kanssa) kaatuu', () => {
		const home = files['ToolsHome.svelte'];
		const broken = home.replace('<MiniLeague {premium} ', '<MiniLeague ');
		expect(broken).not.toBe(home);
		expect(premiumPropProblems({ 'ToolsHome.svelte': broken })).toEqual([
			'ToolsHome.svelte: <MiniLeague> ilman premiumia'
		]);
	});
});

/* ---------------------------------------------------------------------------
 * Rekisteri: tasot vastaavat jakoa (spec-taulukko)
 * ------------------------------------------------------------------------- */
describe('rekisteri: tyokalujen tasot 17.10 jaon mukaan', () => {
	const tier = (s: string) => TOOLS.find((t) => t.slug === s)?.tier;
	it('kokonaan lukitut ovat premium-tasoa (reitti -> LockedToolPreview)', () => {
		expect(tier('watchlist')).toBe('premium');
		expect(tier('fit-checker')).toBe('premium');
	});
	it('ilmaisen ytimen tyokalut avautuvat kaikille (lukko komponentissa)', () => {
		for (const s of ['rate-my-team', 'league', 'price-watch', 'differentials'])
			expect(tier(s), s).toBe('free');
	});
});
