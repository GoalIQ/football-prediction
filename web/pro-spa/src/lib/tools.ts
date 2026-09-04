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

export const GROUPS: Group[] = [
	{ id: 'week', label: 'This week', title: 'This week' },
	{ id: 'team', label: 'My team', title: 'My team' },
	{ id: 'players', label: 'Players', title: 'Players' },
	{ id: 'tools', label: 'Tools', title: 'Tools' },
	{ id: 'prices', label: 'Prices', title: 'Prices' },
	{ id: 'matches', label: 'Matches', title: 'Matches' }
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
		question: 'Is my squad good, and what is the one move that improves it most?',
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
		anchor: 'pc-captain'
	},
	{
		slug: 'fixture-swing',
		group: 'players',
		title: 'Fixture swing',
		question: 'Whose fixtures turn from hard to easy over the next six gameweeks?',
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
		question: 'Which defence is most likely to keep a clean sheet this week?',
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
		slug: 'differentials',
		group: 'players',
		title: 'Differentials',
		question: 'Which low-owned players have the projection to justify the risk?',
		tier: 'premium',
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
		group: 'tools',
		title: 'Chip timing',
		question:
			'When are the best windows for Wildcard, Bench Boost, Triple Captain and Free Hit?',
		tier: 'premium',
		anchor: 'tl-chips'
	},
	{
		slug: 'transfer-chains',
		group: 'tools',
		title: 'Transfer chains',
		question: 'What do one and two-move transfer plans look like with the hits counted?',
		tier: 'premium',
		anchor: 'tl-chains'
	},
	{
		slug: 'edge-mode',
		group: 'tools',
		title: 'Edge mode',
		question: 'Which picks protect or climb my rank against the template?',
		tier: 'premium',
		anchor: 'tl-edge'
	},
	{
		slug: 'league',
		group: 'tools',
		title: 'Beat the Model league',
		question: 'How am I doing against the model and my rivals in the mini-league?',
		tier: 'free',
		anchor: 'tl-league'
	},
	// --- Prices ------------------------------------------------------------
	{
		slug: 'price-watch',
		group: 'prices',
		title: 'Price watch',
		question: 'Which of my players are about to rise or fall?',
		tier: 'free',
		anchor: 'pr-watch'
	},
	// --- Matches -----------------------------------------------------------
	{
		slug: 'predict',
		group: 'matches',
		title: 'Predict a match',
		question: 'What does the model say about any fixture I choose?',
		tier: 'free',
		anchor: 'mt-predict'
	},
	{
		slug: 'fixtures',
		group: 'matches',
		title: 'Fixtures',
		question: "What's coming up, and what does the model make of it?",
		tier: 'free',
		anchor: 'mt-fixtures'
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
 * nakyvissa. Kaksi osoittaa yha ryhmaan, ja molemmilla on syy:
 *   - `myteam` tarkoitti koko My team -nakymaa, ei yhta tyokalua
 *   - `pricewatch` on ryhmansa ainoa tyokalu, joten /prices on sama asia
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
	pricewatch: '/prices',
	league: '/tools/league',
	chips: '/tools/chip-timing',
	chains: '/tools/transfer-chains',
	edge: '/tools/edge-mode',
	predict: '/matches/predict',
	fixtures: '/matches/fixtures',
	standings: '/matches/table'
};

/** Ryhmaan (eika tyokaluun) osoittavat vanhat hashit + syy. */
export const LEGACY_GROUP_TARGETS: Record<string, string> = {
	myteam: 'tarkoitti koko My team -nakymaa, ei yhta tyokalua',
	pricewatch: 'Price watch on ryhmansa ainoa tyokalu, joten /prices on sama asia'
};

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
	if (t) return `${t.title} | GoalIQ Premium`;
	return `${g ? g.title : 'FPL tools'} | GoalIQ Premium`;
}
