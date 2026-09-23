/** Tyokalurekisteri — YKSI LUKIJA josta navi, hakemisto ja reitit tulevat.
 *
 * 🔴 MITATTU VIKA (4.9.2026, kilpailija-UI-auditointi). Koko premium-tuote oli
 * yhden URLin takana: 24 tyokalua kuudessa ryhmassa, ja ryhmat olivat
 * hash-tilaa (`#tools=team`) eivat sivuja. Se maksoi kolme asiaa:
 *   1. selaimen paluunappi ei liikkunut tyokalujen valilla,
 *   2. yksittaista tyokalua ei voinut linkittaa eika bookmarkata,
 *   3. millaan nakymalla ei ollut omaa otsikkoa.
 * Lisaksi 19 vanhaa deep-linkkia ohjautui RYHMAAN eika tyokaluun, eli linkki
 * "avaa clean sheets" pudotti kayttajan kymmenen tyokalun pinon ylalaitaan.
 *
 * Vertailukohta: FPLRoguella jokainen tyokalu on `/tools/<slug>`, jolla on
 * murupolku, H1 ja yksi lause siita mihin kysymykseen se vastaa.
 *
 * SAANTO 6a KOHTA 1 (yksi lukija joka ei voi palauttaa vaaraa): tama tiedosto
 * on ainoa paikka jossa tyokalun nimi, kysymys, taso ja reitti maaritellaan.
 * Navi (`GROUPS`), ryhmien tyokalurivit, reittien otsikot ja vanhojen
 * hashien ohjaus lukevat kaikki tasta. Tyokalua ei voi lisata nakymaan
 * antamatta silla reittia ja otsikkoa — `tests/test_spa_tool_registry.py`
 * kaataa buildin jos jokin kentta puuttuu.
 */

export type Tier = 'free' | 'premium';

export type Group = {
	/** Reitin ensimmainen segmentti: /week, /team, ... */
	id: string;
	/** Navin teksti. */
	label: string;
	/** Sivun otsikko (<title>) kun ryhma on auki ilman tyokalua. */
	title: string;
	/** 22.9 (julkaisutarkistaja): FPL-ryhma -> otsikkoon "FPL tools". Rekisterin
	 *  kentta eika kovakoodattu lista, jotta uusi ryhma ei unohdu. */
	fpl: boolean;
	/** Ryhmasivun kuvaus kun se ei tule tyokalusta (esim. matches). */
	description?: string;
};

export type Tool = {
	/** Reitin toinen segmentti: /players/leaders */
	slug: string;
	group: string;
	/** Tyokalun nimi navissa, hakemistossa ja otsikossa. */
	title: string;
	/** Yksi lause: mihin kysymykseen tama vastaa. Ei ominaisuuslista. */
	question: string;
	tier: Tier;
	/**
	 * Ryhman paatyokalu: `/<group>` avaa taman suoraan hakemiston sijaan.
	 *
	 * 🔴 Villen havainto 4.9 heti reittien jalkeen: "my team ei muista sita".
	 * Ryhman etusivu oli korttihakemisto myos silloin kun ryhmalla on selva
	 * paatyokalu — My teamissa se on oma joukkue, ja hakemisto naytti
	 * kortteja vaikka tallennettu joukkue oli tiedossa. Hakemisto on oikea
	 * vastaus vain kun ryhmassa ei ole yhta ilmeista aloitusta.
	 */
	primary?: boolean;
	/**
	 * Elementin id ryhmasivulla. Ryhmasivu renderoi kaikki tyokalunsa
	 * pinossa; tyokalun oma URL renderoi vain taman. Sama id kelpaa myos
	 * ankkuriksi.
	 */
	anchor: string;
};

/**
 * 22.9.2026 (UX-uudistus A3, Villen GO): neljä ryhmaa, SAMAT nimet ja SAMA
 * jarjestys kuin mobiiliapin alapalkissa (goaliq-app `feat/ux-mobiili-ia`).
 * Mobiilin viides tabi "You" (tili, Premium) on webissa ylapalkin
 * Sign in / Account -napeissa, ei ryhmana.
 *
 * 🔴 MITATTU 22.9 (web-audit T2): 390 px:lla navin viidesta kohdasta
 * "Players", "Price watch" ja "Matches" olivat ruudun ulkopuolella ja
 * "My team" katkesi reunaan. Siksi puhelimessa navi on alapalkki
 * (`BottomNav`), ja ryhmia on enintaan viisi (portti `ia.gate.test.ts`).
 *
 * Purettu:
 *   - 'tools' (11.9, PRO-SPA-PALETTI): 17/23 tyokalua alle 9 henkilon
 *     kaytossa; chip timing, transfer chains ja league ovat oman joukkueen
 *     tyokaluja (team), edge mode pelaajavalinnan (players).
 *   - 'prices' (22.9, A3): hintamuutokset ovat FPL:n oma projektio eivatka
 *     tuotteen ydin (brief). Price watch on nyt Players-listan esiasetus
 *     "Price change" (`PLAYER_PRESETS`), reitti /players/price-watch.
 * Vanhat polut ohjautuvat uuteen paikkaan: `LEGACY_PATHS` + `resolvePath`.
 */
export const GROUPS: Group[] = [
	{ id: 'week', label: 'This week', title: 'This week', fpl: true },
	{ id: 'team', label: 'My team', title: 'My team', fpl: true },
	{
		id: 'players',
		label: 'Players',
		title: 'Players',
		fpl: true,
		// 22.9 (A3 2.3): /players on nyt lista esiasetuksineen eika yksi
		// tyokalu, joten paatyokalun kysymys ("Who should wear the armband")
		// kuvaisi vain yhden viidesta. Julkaisutarkistajalle copy-listassa.
		description:
			'Find any player and sort by value, differentials or price change, plus clean sheet chances by team. Captain and xP sorting are part of GoalIQ Premium.'
	},
	{
		id: 'matches',
		label: 'Matches',
		title: 'Matches',
		fpl: false,
		// Julkaisutarkistaja 22.9: "Predict a match" ensimmaisina sanoina luki
		// vihjepalvelulta; malli- ja todennakoisyyskehys ensin. Ei lukua "10"
		// (vanhenisi hiljaa kun LEAGUES muuttuu).
		description: 'Win probabilities from the GoalIQ match model, plus fixtures and league tables.'
	}
];

/**
 * `week` on tarkoituksella ilman alityokaluja: se on yksi koostettu nakyma
 * (mita tehdaan ennen deadlinea + miten omat kutsut menivat), ei tyokalulista.
 * Poikkeus on kirjattu tahan, koska rekisterin testi kysyy sita.
 */
export const GROUPS_WITHOUT_TOOLS = ['week'];

export const TOOLS: Tool[] = [
	// --- My team -----------------------------------------------------------
	{
		slug: 'rate-my-team',
		group: 'team',
		title: 'Rate my team',
		// 5.9 portti: "the one move that improves it most" oli kayvan joukon
		// maksimi; backend itse kirjoittaa "the best move the model checked".
		question: 'Is my squad good, and which line is costing me?',
		tier: 'free',
		primary: true,
		anchor: 'tc-rate'
	},
	{
		slug: 'fit-checker',
		group: 'team',
		title: 'Fit checker',
		question: 'Which 15 does the model build around the players I lock in?',
		tier: 'free',
		anchor: 'tc-fit'
	},
	{
		slug: 'transfer-planner',
		group: 'team',
		title: 'Transfer planner',
		question: 'Which transfers over the next gameweeks are worth the hits?',
		tier: 'premium',
		anchor: 'tc-planner'
	},
	{
		slug: 'watchlist',
		group: 'team',
		title: 'Watchlist',
		question: 'Which players am I still deciding on?',
		tier: 'free',
		anchor: 'tc-watchlist'
	},
	// --- Players -----------------------------------------------------------
	{
		slug: 'player-card',
		group: 'players',
		title: 'Player card',
		question: 'What does the model know about one player, in one place?',
		tier: 'free',
		anchor: 'pc-card'
	},
	{
		slug: 'captain-ranker',
		group: 'players',
		title: 'Captain ranker',
		question: 'Who should wear the armband this gameweek?',
		tier: 'premium',
		// 22.9 (A3 2.3): /players avaa listan Captain-esiasetuksella, sama
		// ensimmainen lajittelu kuin mobiilin Players-tabissa.
		primary: true,
		anchor: 'pc-captain'
	},
	{
		slug: 'fixture-swing',
		group: 'players',
		title: 'Fixture swing',
		question: 'Whose fixtures turn from hard to easy over the coming gameweeks?',
		tier: 'premium',
		anchor: 'pc-swing'
	},
	{
		slug: 'player-xp',
		group: 'players',
		title: 'Player xP',
		question: 'What does each projected player score per gameweek, with minutes and ownership?',
		tier: 'premium',
		anchor: 'pc-xp'
	},
	{
		slug: 'clean-sheets',
		group: 'players',
		title: 'Clean sheets',
		// 22.9 (T6): kysymys on nyt myos reitin meta/og-kuvaus eli julkista
		// tekstia; "most likely" on copy-saannoissa kielletty. Sanamuoto on
		// tyokalun oma ("the team's average chance of a clean sheet").
		question: 'Which defence has the best chance of a clean sheet this week?',
		tier: 'free',
		anchor: 'pc-cs'
	},
	{
		slug: 'value',
		group: 'players',
		title: 'Value',
		question: 'Who returns the most projected points per million?',
		tier: 'free',
		anchor: 'pc-value'
	},
	{
		slug: 'leaders',
		group: 'players',
		title: 'Leaders',
		question: 'Who leads on xG, xA and xGI, with no cut-off?',
		tier: 'free',
		anchor: 'pc-leaders'
	},
	{
		slug: 'stats',
		group: 'players',
		title: 'Stats',
		question: 'What did each player actually score, and what did the model expect before each deadline?',
		// 6.9 (Villen tilaus). Raakaluvut ja menneiden kierrosten freeze-vertailu
		// ovat ilmaisia; vain eteenpain katsova xP on premiumia (8.8-linjaus).
		tier: 'free',
		anchor: 'pc-stats'
	},
	{
		slug: 'differentials',
		group: 'players',
		title: 'Differentials',
		question: 'Which low-owned players have the projection to justify the risk?',
		// Villen paatos 4.9: ilmainen. Se oli jo kaytannossa ilmainen (julkisen
		// /fpl/differentials-sivun datalahde), joten premium-merkki lupasi
		// lukon jota ei ollut.
		tier: 'free',
		anchor: 'pc-diff'
	},
	{
		slug: 'replacements',
		group: 'players',
		title: 'Replacements',
		question: 'Who replaces a player at a similar price?',
		tier: 'premium',
		anchor: 'pc-repl'
	},
	{
		slug: 'compare',
		group: 'players',
		title: 'Compare players',
		question: 'How do up to four players line up side by side on projected points?',
		tier: 'premium',
		anchor: 'pc-compare'
	},
	// --- Tools -------------------------------------------------------------
	{
		slug: 'chip-timing',
		group: 'team',
		title: 'Chip timing',
		question:
			'When are the best windows for Wildcard, Bench Boost, Triple Captain and Free Hit?',
		tier: 'premium',
		anchor: 'tl-chips'
	},
	{
		slug: 'transfer-chains',
		group: 'team',
		title: 'Transfer chains',
		question: 'What do one and two-move transfer plans look like with the hits counted?',
		tier: 'premium',
		anchor: 'tl-chains'
	},
	{
		slug: 'edge-mode',
		group: 'players',
		title: 'Edge mode',
		question: 'Which picks protect or climb my rank against the template?',
		tier: 'premium',
		anchor: 'tl-edge'
	},
	{
		slug: 'league',
		group: 'team',
		title: 'Beat the Model league',
		question: 'How am I doing against the model and my rivals in the mini-league?',
		tier: 'free',
		anchor: 'tl-league'
	},
	// 22.9 (A3): entinen Prices-ryhma. Players-listan esiasetus "Price
	// change"; vanha /prices ja /prices/price-watch ohjautuvat tanne.
	{
		slug: 'price-watch',
		group: 'players',
		title: 'Price watch',
		question: 'Which of my players are about to rise or fall?',
		tier: 'free',
		anchor: 'pr-watch'
	},
	// --- Matches -----------------------------------------------------------
	// 22.9 (A3 2.4): Matches avautuu ottelulistaan (Fixtures), ei
	// korttihakemistoon; "pick any two teams" -ennuste pysyy vieressa.
	{
		slug: 'fixtures',
		group: 'matches',
		title: 'Fixtures',
		question: "What's coming up, and what does the model make of it?",
		tier: 'free',
		primary: true,
		anchor: 'mt-fixtures'
	},
	{
		slug: 'predict',
		group: 'matches',
		title: 'Predict a match',
		question: 'What does the model say about a fixture I choose?',
		tier: 'free',
		anchor: 'mt-predict'
	},
	{
		slug: 'table',
		group: 'matches',
		title: 'Table',
		question: 'What does the table look like right now?',
		tier: 'free',
		anchor: 'mt-standings'
	}
];

/**
 * Vanhat deep-linkit (`#tools=<id>`) -> uusi polku.
 *
 * 🔴 Naista 17/19 osoitti aiemmin RYHMAAN eika tyokaluun, eli vanha linkki
 * pudotti kayttajan pitkan pinon ylalaitaan ilman etta pyydetty tyokalu oli
 * nakyvissa. Yksi osoittaa yha ryhmaan, ja silla on syy:
 *   - `myteam` tarkoitti koko My team -nakymaa, ei yhta tyokalua
 * (`pricewatch` osoitti /prices-ryhmaan kunnes ryhma purettiin 22.9; nyt se
 * osoittaa suoraan tyokaluun.)
 * `tests/test_spa_tool_registry.py` kayttaa tata poikkeuslistana: uusi
 * ryhmaan osoittava ohjaus kaataa testin.
 */
export const LEGACY_HASH_TO_PATH: Record<string, string> = {
	cleansheets: '/players/clean-sheets',
	playercard: '/players/player-card',
	lookup: '/players/player-card',
	rateteam: '/team/rate-my-team',
	myteam: '/team',
	fitchecker: '/team/fit-checker',
	value: '/players/value',
	leaders: '/players/leaders',
	differentials: '/players/differentials',
	replacements: '/players/replacements',
	compare: '/players/compare',
	pricewatch: '/players/price-watch',
	league: '/team/league',
	chips: '/team/chip-timing',
	chains: '/team/transfer-chains',
	edge: '/players/edge-mode',
	predict: '/matches/predict',
	fixtures: '/matches/fixtures',
	standings: '/matches/table'
};

/** Ryhmaan (eika tyokaluun) osoittavat vanhat hashit + syy. */
export const LEGACY_GROUP_TARGETS: Record<string, string> = {
	myteam: 'tarkoitti koko My team -nakymaa, ei yhta tyokalua'
};

/**
 * VANHAT POLUT -> UUSI PAIKKA (22.9.2026, A3). Yksi kartta, yksi lukija
 * (`resolvePath`), jota molemmat reittisivut kysyvat ennen renderointia.
 *
 * Tassa ovat vain polut joiden kohde EI ole johdettavissa rekisterista:
 * purettujen ryhmien juuret ja tyokalut jotka vaihtoivat ryhmaa. Muut
 * vanhat tyokalupolut loytyvat slugilla (`findToolAnywhere`), joten yhtakaan
 * tyokalua ei tarvitse muistaa lisata tahan kun se siirtyy.
 *
 * Portti `redirects.gate.test.ts` pitaa listaa JOKAISESTA polusta joka on
 * ollut julkinen (ryhmat ja tyokalut ennen 22.9 + /tools ennen 11.9) ja
 * kaatuu jos yksikin niista ei paady nykyiseen reittiin.
 */
export const LEGACY_PATHS: Record<string, string> = {
	// Price watch -ryhma purettiin 22.9: sen ainoa tyokalu on nyt Players-
	// listan "Price change" -esiasetus.
	'/prices': '/players/price-watch',
	// 11.9 purettu Tools-ryhma: kolme neljasta tyokalusta siirtyi My teamiin,
	// joten ryhman juuri vie sinne.
	'/tools': '/team'
};

/** Nykyinen polku annetulle polulle, tai null kun polkua ei tunneta.
 *
 *  - nykyinen reitti (ryhma tai tyokalu) -> sama polku
 *  - purettu ryhma -> `LEGACY_PATHS`
 *  - tyokalu vanhassa ryhmassa (/tools/chip-timing, /prices/price-watch)
 *    -> tyokalun nykyinen polku slugilla
 *  - tuntematon tyokalu tunnetussa ryhmassa -> ryhma (linkki /players/x
 *    tarkoitti pelaajatyokaluja)
 *  - kaikki muu -> null (reittisivu vie juureen)
 *
 *  Loppukauttaviiva ei muuta vastausta. Vain polku: kutsuja kuljettaa
 *  query-parametrit (?entry=, ?src=) itse, jotta luovutus ei katkea. */
export function resolvePath(pathname: string): string | null {
	const p = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
	if (p === '' || p === '/') return '/';
	if (LEGACY_PATHS[p]) return LEGACY_PATHS[p];
	const parts = p.replace(/^\//, '').split('/');
	if (parts.length > 2) return null;
	const [g, slug] = parts;
	if (slug === undefined) return groupById(g) ? `/${g}` : null;
	const here = findTool(g, slug);
	if (here) return toolPath(here);
	const moved = findToolAnywhere(slug);
	if (moved) return toolPath(moved);
	if (LEGACY_PATHS[`/${g}`]) return LEGACY_PATHS[`/${g}`];
	return groupById(g) ? `/${g}` : null;
}

/* ------------------------------------------------------------------------
 * Ryhmien sisainen rakenne (22.9, A3 2.2 ja 2.3). Nama ovat navigaatiota,
 * eivat uusia tyokaluja: jokainen kohta osoittaa rekisterin tyokaluun, ja
 * portti (`ia.gate.test.ts`) kaataa jos kohta osoittaa tyokaluun jota ei
 * ole tai jos ryhman tyokalu jaa ilman paikkaa.
 * --------------------------------------------------------------------- */

export type Section = {
	id: string;
	/** Valitsimen teksti. Sama kuin mobiilissa. */
	label: string;
	/** Tyokalu jonka valitsin avaa. */
	lead: string;
	/** Osion tyokalut valitsimen alla, jarjestyksessa. */
	tools: string[];
};

/** My team: `( Squad | Transfers | Chips )`, enintaan kolme segmenttia
 *  (A2 saanto 5). Fit checker on siirtotyokalu (A3: "Transfers-nakyman
 *  must-have"), watchlist ja liiga kuuluvat oman rungon seurantaan. */
export const TEAM_SECTIONS: Section[] = [
	{ id: 'squad', label: 'Squad', lead: 'rate-my-team', tools: ['rate-my-team', 'watchlist', 'league'] },
	{
		id: 'transfers',
		label: 'Transfers',
		lead: 'transfer-planner',
		tools: ['transfer-planner', 'transfer-chains', 'fit-checker']
	},
	{ id: 'chips', label: 'Chips', lead: 'chip-timing', tools: ['chip-timing'] }
];

/** Players: `( Players | Teams )`. Teams on clean sheet -ruudukko. */
export const PLAYERS_VIEWS: Section[] = [
	{
		id: 'players',
		label: 'Players',
		lead: 'captain-ranker',
		tools: [
			'captain-ranker',
			'player-xp',
			'value',
			'differentials',
			'price-watch',
			'player-card',
			'fixture-swing',
			'leaders',
			'stats',
			'replacements',
			'compare',
			'edge-mode'
		]
	},
	{ id: 'teams', label: 'Teams', lead: 'clean-sheets', tools: ['clean-sheets'] }
];

export type Preset = {
	slug: string;
	/** Esiasetuksen nimi. `horizon` = nimen peraan xP-summan ikkuna
	 *  xpHorizon-lukijasta ("xP 6 GWs"); ilman metaa pelkka "xP", koska
	 *  lukua jota API ei antanut ei keksita. */
	label: string;
	horizon?: boolean;
};

/** Players-listan esiasetukset (A3 2.3: "presetit korvaavat 5 erillista
 *  osiota"). Jokainen on tyokalun oma reitti, joten esiasetus on
 *  linkitettavissa ja paluunappi toimii. */
export const PLAYER_PRESETS: Preset[] = [
	{ slug: 'captain-ranker', label: 'Captain' },
	{ slug: 'player-xp', label: 'xP', horizon: true },
	{ slug: 'value', label: 'Value' },
	{ slug: 'differentials', label: 'Differentials' },
	{ slug: 'price-watch', label: 'Price change' }
];

/** Matches: `( Fixtures | Predict | Table )`. */
export const MATCHES_SECTIONS: Section[] = [
	{ id: 'fixtures', label: 'Fixtures', lead: 'fixtures', tools: ['fixtures'] },
	{ id: 'predict', label: 'Predict', lead: 'predict', tools: ['predict'] },
	{ id: 'table', label: 'Table', lead: 'table', tools: ['table'] }
];

/** Ryhman valitsin (segmentit), tai null kun ryhmalla ei ole valitsinta. */
export function sectionsFor(group: string): Section[] | null {
	if (group === 'team') return TEAM_SECTIONS;
	if (group === 'players') return PLAYERS_VIEWS;
	if (group === 'matches') return MATCHES_SECTIONS;
	return null;
}

/** Osio johon tyokalu kuuluu (valitsimen aktiivinen segmentti). Ilman
 *  tyokalua ryhman ensimmainen osio, koska ryhmasivu avaa sen. */
export function sectionOf(group: string, slug: string | null): Section | null {
	const secs = sectionsFor(group);
	if (!secs) return null;
	if (!slug) return secs[0];
	return secs.find((s) => s.tools.includes(slug)) ?? secs[0];
}

/* ------------------------------------------------------------------------
 * Muiden pelien nakymat: RSL Fantasy (/spl) ja UCL Fantasy (/ucl) samalla
 * rakenteella kuin FPL (23.9, Villen pyynnot "RSL fantasyn vois kans
 * jasennella noilla menuilla" ja UCL:lle "sama rakenne kuin FPL/RSL").
 *
 * Osiot (esim. Players | Teams | Model squad) ovat sovelluksen palkissa
 * (`navItems`, Villen valinta B), osion sisalla FPL:n esiasetukset Captain /
 * xP / Value / Differentials ja loput "More"-kohdassa.
 *
 * Nakyma on hashissa (/spl#value, /ucl#clean-sheets): /spl on prerenderoitu
 * (SEO), eika query-parametria voi lukea prerenderissa. Linkki on silti
 * jaettava ja paluunappi toimii.
 *
 * YKSI LUKIJA: sivut ja palkit kysyvat nakyman `gameView`ilta eivatka lue
 * hashia itse. Portit `splViews.gate.test.ts` ja `uclViews.gate.test.ts`
 * kaatavat jos nakyma jaa ilman sisaltoa tai osiota, tai on kahdessa.
 * --------------------------------------------------------------------- */
export type GameId = 'spl' | 'ucl';

export type GameSection<V extends string = string> = {
	id: string;
	label: string;
	lead: V;
	views: V[];
	/** Alapalkin kuvake (`NAV_ICONS`-avain). */
	icon: string;
};

export type GameViews<V extends string = string> = {
	sections: GameSection<V>[];
	/** Players-osion esiasetukset: samat nimet ja jarjestys kuin FPL:n
	 *  `PLAYER_PRESETS`issa. */
	presets: { view: V; label: string; horizon?: boolean }[];
	/** Muut nakymat valitsimen alla, osioittain. */
	more: Record<string, { view: V; label: string }[]>;
	defaultView: V;
};

export type SplView =
	| 'captain'
	| 'xp'
	| 'value'
	| 'differentials'
	| 'compare'
	| 'leaders'
	| 'clean-sheets'
	| 'accuracy'
	| 'model-squad';

/** UCL: sivun xP-lista on 'xp' (uclPicksin 'all'). Teams = joukkueiden
 *  clean sheet % kierroksittain samasta CL-mallista kuin puolustajien xP. */
export type UclPageView = 'captain' | 'xp' | 'value' | 'differentials' | 'compare' | 'clean-sheets';

const PRESETS: { view: 'captain' | 'xp' | 'value' | 'differentials'; label: string; horizon?: boolean }[] = [
	{ view: 'captain', label: 'Captain' },
	{ view: 'xp', label: 'xP', horizon: true },
	{ view: 'value', label: 'Value' },
	{ view: 'differentials', label: 'Differentials' }
];

export const GAME_VIEWS: { spl: GameViews<SplView>; ucl: GameViews<UclPageView> } = {
	spl: {
		sections: [
			{
				id: 'players',
				label: 'Players',
				lead: 'captain',
				views: ['captain', 'xp', 'value', 'differentials', 'compare', 'leaders'],
				icon: 'players'
			},
			{
				id: 'teams',
				label: 'Teams',
				lead: 'clean-sheets',
				views: ['clean-sheets', 'accuracy'],
				icon: 'shield'
			},
			{ id: 'squad', label: 'Model squad', lead: 'model-squad', views: ['model-squad'], icon: 'team' }
		],
		// Ilman Price changea, jota RSL-syote ei anna.
		presets: [...PRESETS],
		more: {
			players: [
				{ view: 'compare', label: 'Compare two players' },
				{ view: 'leaders', label: "Last season's leaders" }
			],
			teams: [
				{ view: 'clean-sheets', label: 'Clean sheets and fixtures' },
				{ view: 'accuracy', label: 'How our calls have gone' }
			]
		},
		// RSL on ilmainen: avataan kapteenilla kuten FPL:n Players.
		defaultView: 'captain'
	},
	ucl: {
		sections: [
			{
				id: 'players',
				label: 'Players',
				lead: 'xp',
				views: ['captain', 'xp', 'value', 'differentials', 'compare'],
				icon: 'players'
			},
			{ id: 'teams', label: 'Teams', lead: 'clean-sheets', views: ['clean-sheets'], icon: 'shield' }
		],
		// Ei horisonttia nimeen: xpHorizonin nimi on GW-muotoinen ("xP 3 GWs"),
		// ja UCL:n kierros on matchday (sivu valttaa GW-muotoja, 21.9).
		presets: PRESETS.map(({ view, label }) => ({ view, label })),
		more: { players: [{ view: 'compare', label: 'Compare two players' }] },
		// UCL-listat ovat Premiumia; ilmainen nakee xP-listan kymmenen karkea,
		// joten oletus on xP eika lukittu kapteenilista (sama kuin 23.9 vaihe 1).
		defaultView: 'xp'
	}
};

/** Nakyma hashista ("#value" -> 'value'). Tuntematon tai tyhja -> pelin
 *  oletus, jotta vanha tai kirjoitusvirheellinen linkki avaa sivun eika tyhjaa. */
export function gameView(game: GameId, hash: string | null | undefined): string {
	const g = GAME_VIEWS[game] as GameViews;
	const id = (hash ?? '').replace(/^#/, '');
	return g.sections.some((s) => s.views.includes(id)) ? id : g.defaultView;
}

export function gameSectionOf(game: GameId, view: string): GameSection {
	const g = GAME_VIEWS[game] as GameViews;
	return g.sections.find((s) => s.views.includes(view)) ?? g.sections[0];
}

/** Vieritetaanko ylos: vain kun palkin osio vaihtuu, ei osion sisalla. */
export function sectionChanged(game: GameId, from: string, to: string): boolean {
	return gameSectionOf(game, from).id !== gameSectionOf(game, to).id;
}

// RSL-nimet (23.9 ensimmainen versio) ohuina aliaksina samaan lukijaan.
export const SPL_SECTIONS = GAME_VIEWS.spl.sections;
export const SPL_PRESETS = GAME_VIEWS.spl.presets;
export const SPL_MORE = GAME_VIEWS.spl.more;
export const SPL_DEFAULT_VIEW: SplView = GAME_VIEWS.spl.defaultView;
export const splView = (hash: string | null | undefined): SplView => gameView('spl', hash) as SplView;
export const splSectionOf = (view: SplView): GameSection<SplView> =>
	gameSectionOf('spl', view) as GameSection<SplView>;
export const uclView = (hash: string | null | undefined): UclPageView =>
	gameView('ucl', hash) as UclPageView;

/* ------------------------------------------------------------------------
 * Pelivalitsin (A3 1: "FPL ▾ -> FPL / UCL Fantasy / RSL Fantasy").
 * UCL ja SPL ovat omia reittejaan (routes/ucl, routes/spl), eivat ryhmia.
 * --------------------------------------------------------------------- */
export type Game = {
	id: 'fpl' | 'ucl' | 'spl';
	label: string;
	/** Puhelimen ylapalkin lyhyt nimi: 390 px:lla "UCL Fantasy" + tilinapit
	 *  eivat mahdu samalle riville (mitattu, raportti w-spa-ia.md). */
	short: string;
	href: string;
};

export const GAMES: Game[] = [
	{ id: 'fpl', label: 'FPL', short: 'FPL', href: '/' },
	{ id: 'ucl', label: 'UCL Fantasy', short: 'UCL', href: '/ucl' },
	{ id: 'spl', label: 'RSL Fantasy', short: 'RSL', href: '/spl' }
];

/** Mika peli on auki: reitin ensimmainen segmentti ratkaisee. */
export function gameOf(pathname: string): Game {
	const first = pathname.replace(/^\//, '').split('/')[0];
	return GAMES.find((g) => g.id !== 'fpl' && g.id === first) ?? GAMES[0];
}

/** Aktiivinen ryhma polusta: juuri = This week, peli-reitit (/ucl, /spl)
 *  = ei mitaan (alapalkki nayttaa FPL:n ryhmat ilman korostusta). */
export function groupOfPath(pathname: string): string | null {
	const first = pathname.replace(/^\//, '').split('/')[0];
	if (first === '') return 'week';
	return groupById(first) ? first : null;
}

/* ------------------------------------------------------------------------
 * Palkin kohteet pelin mukaan (23.9, Villen valinta "B: palkki pelin mukaan").
 *
 * 22.9:n A3 piirsi FPL:n ryhmat (This week / My team / Players / Matches)
 * myos /ucl- ja /spl-reiteille ilman korostusta. RSL-sivulla palkki vei siis
 * FPL:aan eika RSL:n omiin osioihin. Nyt palkki on pelin oma: FPL:ssa
 * ryhmat, RSL:ssa ja UCL:ssa `GAME_VIEWS`in osiot. Takaisin FPL:aan paasee pelivalitsimesta.
 *
 * YKSI LUKIJA: ylapalkki (Hero) ja alapalkki (BottomNav) kysyvat kohteet ja
 * aktiivisen kohdan taalta; portti `ia.gate.test.ts`.
 * --------------------------------------------------------------------- */
export type NavItem = { id: string; label: string; href: string; icon: string };

export function navItems(pathname: string): NavItem[] {
	const game = gameOf(pathname).id;
	if (game !== 'fpl')
		return (GAME_VIEWS[game].sections as GameSection[]).map((s) => ({
			id: s.id,
			label: s.label,
			href: `/${game}#${s.lead}`,
			icon: s.icon
		}));
	return GROUPS.map((g) => ({
		id: g.id,
		label: g.label,
		href: g.id === 'week' ? '/' : `/${g.id}`,
		icon: g.id
	}));
}

/** Aktiivinen palkin kohta: FPL:ssa ryhma polusta, muissa peleissa
 *  nakyman osio hashista (`gameView`). */
export function activeNav(pathname: string, hash: string): string | null {
	const game = gameOf(pathname).id;
	if (game !== 'fpl') return gameSectionOf(game, gameView(game, hash)).id;
	return groupOfPath(pathname);
}

export function groupById(id: string): Group | undefined {
	return GROUPS.find((g) => g.id === id);
}

export function toolsInGroup(group: string): Tool[] {
	return TOOLS.filter((t) => t.group === group);
}

export function findTool(group: string, slug: string | null): Tool | undefined {
	if (!slug) return undefined;
	return TOOLS.find((t) => t.group === group && t.slug === slug);
}

/** 11.9: tyokalu pelkalla slugilla, ryhmasta riippumatta. Vanhat
 *  /tools/<slug>-linkit (ja jaetut URLit) loytavat nain uuden kotinsa. */
export function findToolAnywhere(slug: string | null): Tool | undefined {
	if (!slug) return undefined;
	return TOOLS.find((t) => t.slug === slug);
}

/** Ryhman paatyokalu, jos sellainen on maaritelty. */
export function primaryTool(group: string): Tool | undefined {
	return TOOLS.find((t) => t.group === group && t.primary);
}

export function toolPath(t: Tool): string {
	return `/${t.group}/${t.slug}`;
}

/** Selaimen valilehden otsikko. Yksi lukija myos tassa. */
export function pageTitle(group: string, slug: string | null): string {
	const g = groupById(group);
	const t = findTool(group, slug);
	// 22.9 (julkaisutarkistaja): "| GoalIQ Premium" oli 19 ilmaisella reitilla
	// ja lukon oma teksti maarittelee Premiumin maksulliseksi tasoksi. Nyt
	// Premium vain premium-tason tyokalulla, "FPL tools" vain FPL-ryhmissa.
	const fpl = g?.fpl ? ' | FPL tools' : '';
	if (t) return `${t.title}${fpl} | ${t.tier === 'premium' ? 'GoalIQ Premium' : 'GoalIQ'}`;
	return `${g ? g.title : 'FPL tools'}${fpl} | GoalIQ`;
}
