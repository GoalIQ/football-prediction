/**
 * Reittikohtainen link preview (22.9.2026, web-audit T6, Villen GO).
 *
 * 🔴 MITATTU 22.9: pron raaka HTML (jota X, Bluesky, Slack ja Facebook
 * lukevat, eivat aja JS:aa) oli sama 11 658 tavun index.html jokaisella
 * reitilla paitsi /spl. 21.9 markkinoitu `pro.goaliq.app/ucl` nakyi
 * jaettuna "GoalIQ Premium | FPL tools", ja og:url osoitti juureen.
 *
 * Mekanismi: `scripts/route-heads.mjs` kirjoittaa buildin jalkeen jokaiselle
 * taulukon reitille oman `build/<polku>.html`:n (SPA-kuori, jonka head on
 * vaihdettu). Cloudflare Pages tarjoilee `ucl.html`:n osoitteessa `/ucl`
 * samalla tavalla kuin se jo tarjoilee prerenderoidun `spl.html`:n. Kuori on
 * muuten sama tiedosto kuin fallback: SPA kaynnistyy identtisesti.
 *
 * SAANTO 6a KOHTA 1 (yksi lukija): otsikot ja kuvaukset tulevat tyokalu-
 * rekisterista (`tools.ts`: `pageTitle`, `question`) ja UCL/SPL-sivujen omat
 * vakiot ovat TASSA, ja sivujen `<svelte:head>` lukee samat vakiot. Raaka
 * HTML ja selaimen otsikko eivat voi erota toisistaan. Uusi tyokalu saa
 * oman esikatselunsa ilman etta kukaan muistaa lisata sita.
 *
 * Tama tiedosto ajetaan myos Nodessa (build-skripti, tyyppien riisunta),
 * siksi `./tools.ts`-paate ja vain tyyppi-importit muualta.
 */
import {
	GROUPS,
	GROUPS_WITHOUT_TOOLS,
	TOOLS,
	groupById,
	pageTitle,
	primaryTool,
	toolPath,
	toolsInGroup
} from './tools.ts';

export const ORIGIN = 'https://pro.goaliq.app';

/** UCL-sivun oma otsikko ja kuvaus (routes/ucl/+page.svelte lukee nama). */
export const UCL_HEAD = {
	title: 'UCL Fantasy expected points | GoalIQ',
	description:
		'Clean sheet chances for every Champions League club in the league phase, free. GoalIQ Premium adds expected points for each UCL Fantasy player up to three matchdays ahead, with captain, value and differential lists.'
} as const;

/** SPL-sivun oma otsikko ja kuvaus (routes/spl/+page.svelte lukee nama). */
export const SPL_HEAD = {
	title: 'Saudi Pro League fantasy tools | GoalIQ',
	description:
		'Free model-based tools for RSL Fantasy (Saudi Pro League): clean sheet probability, fixture difficulty and expected points from the GoalIQ match model.'
} as const;

export type RouteHead = {
	/** Reitti ilman loppukauttaviivaa: '/ucl', '/players/player-xp'. */
	path: string;
	title: string;
	/** null = pidetaan app.html:n kuvaus (sama kuin juurella). */
	description: string | null;
	/** Absoluuttinen. Myos og:url. */
	canonical: string;
	/** true = SvelteKit prerenderoi sivun ja sen oma svelte:head tuo
	 *  otsikon, kuvauksen ja canonicalin (/spl). */
	prerendered?: boolean;
};

/** "A, B and C." Rekisterin nimista, ei uutta vaitetta. */
function listSentence(names: string[]): string {
	if (names.length <= 1) return `${names.join('')}.`;
	return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}.`;
}

/** Tyokalu jonka ryhmasivu avaa sellaisenaan: paatyokalu (`primary`) tai
 *  ryhman ainoa tyokalu. Sama saanto kuin ToolsHomen `activeTool`issa. */
function leadTool(group: string) {
	const tools = toolsInGroup(group);
	return primaryTool(group) ?? (tools.length === 1 ? tools[0] : undefined);
}

/** Ryhmasivun kuvaus: se mita ryhmasivu nayttaa. Paatyokalu tai ainoa
 *  tyokalu -> sen kysymys (sivu avaa sen). Hakemisto -> tyokalujen nimet.
 *  Ryhma ilman tyokaluja (This week = juuri) -> app.html:n kuvaus. */
function groupDescription(group: string): string | null {
	if (GROUPS_WITHOUT_TOOLS.includes(group)) return null;
	const own = groupById(group)?.description;
	if (own) return own;
	const lead = leadTool(group);
	if (lead) return lead.question;
	return listSentence(toolsInGroup(group).map((t) => t.title));
}

/** Kaikki reitit joilla on oma head. Jarjestys: erillisreitit, ryhmat,
 *  tyokalut. Juuri `/` ei ole tassa: se on fallback-index.html ja pitaa
 *  app.html:n headin sellaisenaan. */
export function routeHeads(): RouteHead[] {
	const out: RouteHead[] = [
		{ path: '/ucl', ...UCL_HEAD, canonical: `${ORIGIN}/ucl` },
		{ path: '/spl', ...SPL_HEAD, canonical: `${ORIGIN}/spl`, prerendered: true }
	];
	for (const g of GROUPS) {
		out.push({
			path: `/${g.id}`,
			title: pageTitle(g.id, null),
			description: groupDescription(g.id),
			// /week on sama nakyma kuin juuri (routes/+page.svelte).
			canonical: g.id === 'week' ? `${ORIGIN}/` : `${ORIGIN}/${g.id}`
		});
	}
	for (const t of TOOLS) {
		out.push({
			path: toolPath(t),
			title: pageTitle(t.group, t.slug),
			description: t.question,
			// Ryhmasivu nayttaa taman tyokalun sellaisenaan (/prices =
			// /prices/price-watch, /team = /team/rate-my-team): yksi kanoninen
			// osoite, ja se on ryhman, koska navi ja vanhat linkit vievat sinne.
			canonical:
				leadTool(t.group)?.slug === t.slug ? `${ORIGIN}/${t.group}` : `${ORIGIN}${toolPath(t)}`
		});
	}
	return out;
}

// ---------------------------------------------------------------------------
// HTML-muunnos. Jokainen korvaus osuu TASAN kerran tai heittaa: hiljainen
// puolikorjaus (tagi jaa templaatin arvoon) on juuri se vika jota korjataan.
// ---------------------------------------------------------------------------

function escAttr(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/"/g, '&quot;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;');
}

function unesc(s: string): string {
	return s
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&amp;/g, '&');
}

const TITLE_RE = /<title>([^<]*)<\/title>/g;
const metaRe = (attr: 'name' | 'property', key: string) =>
	new RegExp(`<meta\\s+${attr}="${key.replace(/[.:]/g, '\\$&')}"\\s+content="([^"]*)"\\s*\\/?>`, 'g');
const DESC_RE = () => metaRe('name', 'description');
const CANONICAL_RE = /<link\s+rel="canonical"\s+href="([^"]*)"\s*\/?>/g;

/** Sosiaaliset tagit jotka vaihdetaan reitin arvoon. twitter:card ja
 *  og:image pysyvat templaatin arvoissa (yksi olemassa oleva kuva). */
const SOCIAL: { attr: 'name' | 'property'; key: string; pick: (h: RouteHead, desc: string) => string }[] = [
	{ attr: 'property', key: 'og:title', pick: (h) => h.title },
	{ attr: 'property', key: 'og:description', pick: (_h, d) => d },
	{ attr: 'property', key: 'og:url', pick: (h) => h.canonical },
	{ attr: 'name', key: 'twitter:title', pick: (h) => h.title },
	{ attr: 'name', key: 'twitter:description', pick: (_h, d) => d }
];

function all(re: RegExp, html: string): string[] {
	return [...html.matchAll(re)].map((m) => unesc(m[1]));
}

function replaceOnce(html: string, re: RegExp, make: () => string, what: string): string {
	const n = [...html.matchAll(re)].length;
	if (n !== 1) throw new Error(`route-heads: ${what}: odotettiin 1 osuma, oli ${n}`);
	return html.replace(re, make);
}

/** Headin luetut arvot. Build-skriptin jalkitarkistus ja portti lukevat
 *  taman, joten "mita sivulla on" mitataan samalla tavalla kaikkialla. */
export type ParsedHead = {
	titles: string[];
	descriptions: string[];
	canonicals: string[];
	social: Record<string, string[]>;
	twitterCard: string[];
};

export function readHead(html: string): ParsedHead {
	const headEnd = html.indexOf('</head>');
	const head = headEnd === -1 ? html : html.slice(0, headEnd);
	const social: Record<string, string[]> = {};
	for (const s of SOCIAL) social[s.key] = all(metaRe(s.attr, s.key), head);
	return {
		titles: all(TITLE_RE, head),
		descriptions: all(DESC_RE(), head),
		canonicals: all(CANONICAL_RE, head),
		social,
		twitterCard: all(metaRe('name', 'twitter:card'), head)
	};
}

/** Vaihtaa reitin headin. `html` on joko fallback-kuori (index.html) tai
 *  prerenderoitu sivu (head.prerendered), jossa sivun oma svelte:head on jo
 *  mukana templaatin tagien lisaksi. */
export function applyRouteHead(html: string, head: RouteHead): string {
	const before = readHead(html);
	let out = html;
	let desc: string;

	if (head.prerendered) {
		// Sivu toi oman otsikon ja kuvauksen; templaatin omat poistetaan
		// (SvelteKit ei dedupaa templaattia vasten, crawler poimii ensimmaisen).
		if (!before.titles.includes(head.title))
			throw new Error(`route-heads: ${head.path}: sivun oma title puuttuu`);
		if (before.titles.length !== 2)
			throw new Error(`route-heads: ${head.path}: odotettiin 2 titlea, oli ${before.titles.length}`);
		out = out.replace(TITLE_RE, (m, t: string) => (unesc(t) === head.title ? m : ''));
		if (head.description === null || !before.descriptions.includes(head.description))
			throw new Error(`route-heads: ${head.path}: sivun oma description puuttuu`);
		out = out.replace(DESC_RE(), (m, d: string) => (unesc(d) === head.description ? m : ''));
		desc = head.description;
	} else {
		out = replaceOnce(out, TITLE_RE, () => `<title>${escAttr(head.title)}</title>`, `${head.path} title`);
		if (before.descriptions.length !== 1)
			throw new Error(`route-heads: ${head.path}: odotettiin 1 description, oli ${before.descriptions.length}`);
		desc = head.description ?? before.descriptions[0];
		out = out.replace(
			DESC_RE(),
			() => `<meta name="description" content="${escAttr(desc)}" />`
		);
	}

	for (const s of SOCIAL) {
		const v = s.pick(head, desc);
		out = replaceOnce(
			out,
			metaRe(s.attr, s.key),
			() => `<meta ${s.attr}="${s.key}" content="${escAttr(v)}" />`,
			`${head.path} ${s.key}`
		);
	}

	const canon = readHead(out).canonicals;
	if (canon.length === 0) {
		out = out.replace(
			DESC_RE(),
			(m) => `${m}\n\t\t<link rel="canonical" href="${escAttr(head.canonical)}" />`
		);
	} else if (canon.length !== 1 || canon[0] !== head.canonical) {
		throw new Error(`route-heads: ${head.path}: canonical ${canon.join(',')} != ${head.canonical}`);
	}

	const check = headProblems(out, head, desc);
	if (check.length) throw new Error(`route-heads: ${head.path}: ${check.join('; ')}`);
	return out;
}

/** Jalkiehto yhdelle sivulle: tasan yksi kutakin, ja arvot ovat reitin. */
export function headProblems(html: string, head: RouteHead, desc: string): string[] {
	const h = readHead(html);
	const p: string[] = [];
	const one = (what: string, got: string[], want: string) => {
		if (got.length !== 1 || got[0] !== want) p.push(`${what}=${JSON.stringify(got)} (odotettiin "${want}")`);
	};
	one('title', h.titles, head.title);
	one('description', h.descriptions, desc);
	one('canonical', h.canonicals, head.canonical);
	for (const s of SOCIAL) one(s.key, h.social[s.key], s.pick(head, desc));
	one('twitter:card', h.twitterCard, 'summary_large_image');
	return p;
}

/** Koko buildin jalkiehto: sama predikaatti ajetaan buildissa (levylta
 *  luetuille tiedostoille) ja portissa (routeHeads.gate.test.ts). `served`
 *  on reitin polku -> HTML jonka palvelin sille antaa.
 *
 *  1. jokaisen reitin head on reitin oma (headProblems),
 *  2. kahdella reitilla on sama otsikko vain jos ne ovat sama sivu (sama
 *     canonical: /prices ja /prices/price-watch),
 *  3. /ucl:n title, og:title ja twitter:title sanovat UCL.
 *  Ennen 22.9 jokainen reitti sai saman index.html:n, ja tama palauttaa
 *  silloin virheen jokaiselle reitille (portin negatiivinen kontrolli). */
export function buildProblems(served: Map<string, string>, heads: RouteHead[] = routeHeads()): string[] {
	const problems: string[] = [];
	const seen = new Map<string, RouteHead>();
	for (const head of heads) {
		const html = served.get(head.path);
		if (html === undefined) {
			problems.push(`${head.path}: ei tiedostoa`);
			continue;
		}
		const desc = head.description ?? readHead(html).descriptions[0] ?? '';
		for (const p of headProblems(html, head, desc)) problems.push(`${head.path}: ${p}`);
		const got = readHead(html).titles[0] ?? '';
		const prev = seen.get(got);
		if (prev && prev.canonical !== head.canonical)
			problems.push(`${head.path}: sama title "${got}" kuin ${prev.path}, eri sivu`);
		if (!prev) seen.set(got, head);
	}
	const ucl = served.get('/ucl');
	if (ucl !== undefined) {
		const h = readHead(ucl);
		for (const [k, v] of [
			['title', h.titles[0]],
			['og:title', h.social['og:title']?.[0]],
			['twitter:title', h.social['twitter:title']?.[0]]
		] as const) {
			if (!v?.includes('UCL')) problems.push(`/ucl: ${k} "${v ?? ''}" ei sano UCL`);
		}
	}
	return problems;
}

/** Tiedosto johon reitin HTML kirjoitetaan buildissa (suhteessa build/). */
export function routeFile(path: string): string {
	return `${path.replace(/^\//, '')}.html`;
}
