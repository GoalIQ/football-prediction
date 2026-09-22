/**
 * This week -nakyman rivien lukijat (22.9.2026, UX-uudistus A3 2.1).
 *
 * Rivit ovat yhden lauseen tiivistelmia olemassa olevasta datasta:
 *   - Last gameweek    <- /api/fantasy/model-race (viimeisin gradattu kierros)
 *   - You vs the model <- /api/fantasy/model-race (totals)
 *   - GW clean sheets  <- /api/fantasy (Phase 0, ilmainen)
 * Klientti EI laske pisteita eika todennakoisyyksia: luvut ovat palvelimen,
 * ja lukija vain valitsee rivin ja kertoo mita puuttuu (V1-linjaus 28.7).
 *
 * SAANTO 6a KOHTA 3: jokainen lukija ajetaan synteettisilla vaiheilla
 * (`weekRows.test.ts`): ennen deadlinea, kesken kierroksen, kierroksen
 * jalkeen jolla mallia ei gradattu, ja ilman dataa.
 */
import type { FantasyResponse, FantasyTeam, ModelRaceResponse } from './api';
import type { ModelCaptainPlayer, ModelCaptainResponse } from './fantasyTools';
import { actionableGameweek } from './gameweek';
import { MODEL_SERIES_COPY } from './modelSeriesCopy';

export type LastCall =
	| {
			kind: 'scored';
			gw: number;
			/** null = mallin luku olisi eri hetkesta (stale), ei julkaista. */
			model: number | null;
			/** null = ei entrya tai kierros ei ole omassa historiassa. */
			you: number | null;
			average: number | null;
			provisional: boolean;
			/** true = mallin hitti-kustannusta ei voitu todentaa, luku brutto. */
			beforeHits: boolean;
	  }
	| {
			kind: 'unscored';
			gw: number;
			/** Valmis selite MODEL_SERIES_COPYsta (sama teksti kuin SeasonRacessa). */
			text: string;
	  };

/**
 * Viimeisin pelattu kierros mallin sarjassa.
 *
 * 🔴 Kierros jota mallia EI gradattu (`unscored_gws`, 21.9: GW4) ei ole
 * `gameweeks`-listassa. Jos se on uudempi kuin listan viimeinen rivi, rivi
 * EI saa hypata sen yli vanhempaan kierrokseen: "Last call GW3" GW4:n
 * jalkeen olisi vanha luku uutena. Silloin rivi kertoo miksi GW4:lla ei ole
 * mallin lukua, samalla lauseella kuin kausikisa.
 */
export function lastCall(r: ModelRaceResponse | null | undefined): LastCall | null {
	if (!r?.meta?.available) return null;
	const rows = Array.isArray(r.gameweeks) ? r.gameweeks : [];
	const latest = rows.reduce<ModelRaceResponse['gameweeks'][number] | null>(
		(a, b) => (a == null || b.gw > a.gw ? b : a),
		null
	);
	const unscored = (r.meta.unscored_gws ?? []).reduce<
		NonNullable<ModelRaceResponse['meta']['unscored_gws']>[number] | null
	>((a, b) => (a == null || b.gw > a.gw ? b : a), null);
	if (unscored && (latest == null || unscored.gw > latest.gw)) {
		if (unscored.code === 'no_valid_frozen_squad') {
			return {
				kind: 'unscored',
				gw: unscored.gw,
				text: MODEL_SERIES_COPY.unscoredNoValidFreeze(
					unscored.gw,
					unscored.would_have_scored ?? null,
					unscored.fpl_average ?? null
				)
			};
		}
		// Tuntematon koodi: ei keksita syyta. Rivi putoaa pois kokonaan
		// mieluummin kuin nayttaa vanhemman kierroksen uusimpana.
		return null;
	}
	if (!latest) return null;
	return {
		kind: 'scored',
		gw: latest.gw,
		model: latest.stale_model_points ? null : latest.model_points,
		you: latest.your_points,
		average: latest.fpl_average,
		provisional: latest.provisional === true,
		beforeHits: latest.model_cost_verified === false
	};
}

/**
 * Mallin kortin lahdepolku (22.9, freeze-ikkunan korjaus). Palvelin paattaa
 * lahteen (`meta.source`): jaadytetty runko jos kortin kierrokselle on
 * freeze, muuten FPL:n julkaisemat pickit mallin entrylle. Ei parametreja:
 * klientti ei tarvitse entry-id:ta eika model-racea kortin avaamiseen.
 *
 * 🔴 Ennen tata polku oli `rate-team?entry=116920`, joka lukee vain FPL:n
 * julkaisemat pickit. Freezen (~29 h ennen deadlinea) ja deadlinen valilla
 * se nimesi edellisen kierroksen rungon kapteenin, vaikka goaliq.app/fpl
 * nimesi jo jaadytetyn rungon kapteenin. Portti: modelCard.gate.test.ts.
 */
export function modelCardPath(): string {
	return '/api/fantasy/model-captain';
}

/** Kortin kapteenirivi: nimi ja joukkue ovat aina tekstia, xP voi puuttua. */
export type ModelCaptainPick = {
	id: number;
	web_name: string;
	team_short: string;
	gw_xp: number | null;
};

/** Vastustajarivi kun kierroksella ei ole ottelua (opponents = []). */
export const NO_FIXTURE = 'no fixture';

export type ModelCaptainSource =
	| { kind: 'entry_picks'; entryId: number; picksGw: number | null; href: string | null }
	| { kind: 'frozen'; gw: number | null; href: string | null };

export type ModelCaptainCard = {
	/** Otsikon kierros (`meta.gw`). */
	gw: number | null;
	captain: ModelCaptainPick | null;
	/** "TOT (H)" / "TOT (H), ARS (A)"; NO_FIXTURE; null = ei tietoa, ei rivia. */
	opp: string | null;
	/** Vain entry_picks (close call). Freezella ei ole vaihtoehtoa. */
	alt: ModelCaptainPick | null;
	source: ModelCaptainSource;
};

/** Tarkistusreitin linkki vain omaan tai FPL:n hostiin (palvelimen url). */
const ROUTE_HOSTS: Record<ModelCaptainSource['kind'], string> = {
	frozen: 'https://goaliq.app/',
	entry_picks: 'https://fantasy.premierleague.com/'
};

function pickFrom(p: ModelCaptainPlayer | null | undefined): ModelCaptainPick | null {
	if (!p || typeof p.id !== 'number' || typeof p.web_name !== 'string' || !p.web_name) return null;
	return {
		id: p.id,
		web_name: p.web_name,
		team_short: p.team_short ?? '',
		gw_xp: typeof p.gw_xp === 'number' && Number.isFinite(p.gw_xp) ? p.gw_xp : null
	};
}

function oppFrom(p: ModelCaptainPlayer | null | undefined): string | null {
	const o = p?.opponents;
	if (!Array.isArray(o)) return null;
	if (o.length === 0) return NO_FIXTURE;
	const parts = o
		.filter((x) => typeof x?.opp === 'string' && x.opp)
		.map((x) => (x.venue ? `${x.opp} (${x.venue})` : String(x.opp)));
	return parts.length ? parts.join(', ') : null;
}

/**
 * YKSI lukija `/api/fantasy/model-captain`-vastaukselle (saanto 6a kohta 1).
 * Kenttakartta: cos-reports/ux-uudistus-2026-09/toteutus/mallin-kapteeni-freeze.md.
 *
 *   - kapteeni = `captain`, otsikon GW = `meta.gw`, vaihtoehto = `alternative`
 *   - vastustaja = `captain.opponents` (null -> ei rivia, [] -> NO_FIXTURE)
 *   - lahderivi haarautuu `meta.source`:n mukaan, linkki = `meta.route.url`
 *
 * Tuntematon lahde -> null (kortti ei keksi mista kapteeni tuli). Klientti
 * ei valitse lahdetta: sen tekee palvelin, ja lukija vain kertoo sen.
 */
export function modelCaptainCard(r: ModelCaptainResponse | null | undefined): ModelCaptainCard | null {
	const m = r?.meta;
	if (!m) return null;
	const gw = typeof m.gw === 'number' ? m.gw : null;
	const url = typeof m.route?.url === 'string' ? m.route.url : null;
	let source: ModelCaptainSource;
	if (m.source === 'frozen') {
		source = {
			kind: 'frozen',
			gw,
			href: url?.startsWith(ROUTE_HOSTS.frozen) ? url : null
		};
	} else if (m.source === 'entry_picks') {
		if (typeof m.entry_id !== 'number' || !Number.isInteger(m.entry_id) || m.entry_id <= 0) return null;
		source = {
			kind: 'entry_picks',
			entryId: m.entry_id,
			picksGw: typeof m.picks_gw === 'number' ? m.picks_gw : null,
			href: url?.startsWith(ROUTE_HOSTS.entry_picks) ? url : null
		};
	} else {
		return null;
	}
	const captain = pickFrom(r?.captain);
	return {
		gw,
		captain,
		opp: captain ? oppFrom(r?.captain) : null,
		// Lukittu runko ei tarjoa "close call" -vaihtoehtoa, vaikka kentta tulisi.
		alt: source.kind === 'frozen' ? null : pickFrom(r?.alternative),
		source
	};
}

/**
 * Lahderivin teksti kolmessa palassa (ennen linkkia, linkki, jalkeen), jotta
 * sama lause voidaan piirtaa linkilla tai ilman ja testata sellaisenaan.
 *   entry_picks: "Squad: our FPL entry 116920, GW5 picks."
 *   frozen:      "Squad frozen for GW6, logged on goaliq.app/fpl."
 *
 * Frozen-rivilla EI ole freezen aikaa (julkaisutarkistaja 22.9 B1): linkkisivu
 * ei nayta sita (Logged-sarake on viimeisin kirjoitus ja piilossa mobiilissa),
 * joten aika olisi vaite jota lukija ei voi tarkistaa. Backend palauttaa
 * frozen-kortin vain kun sivu nimeaa saman kapteenin (fpl_model_captain.
 * logged_model_captain), eli "logged on goaliq.app/fpl" on mitattu.
 */
export function modelSourceLine(s: ModelCaptainSource): {
	before: string;
	link: string;
	after: string;
	href: string | null;
} {
	if (s.kind === 'frozen') {
		const gw = s.gw != null ? ` for GW${s.gw}` : '';
		return { before: `Squad frozen${gw}, logged on `, link: 'goaliq.app/fpl', after: '.', href: s.href };
	}
	return {
		before: 'Squad: ',
		link: `our FPL entry ${s.entryId}`,
		after: s.picksGw != null ? `, GW${s.picksGw} picks.` : '.',
		href: s.href
	};
}

export type SeasonLine =
	| { kind: 'you'; diff: number; gameweeks: number }
	| { kind: 'model_vs_average'; text: string };

/**
 * Kauden rivi: sinun rivisi vs mallin, tai ilman entrya mallin rivi vs FPL:n
 * keskiarvo. Kierrosmaara sanotaan aina, koska summa ei kata kierroksia
 * joilta toinen puoli puuttuu (`compared_gws` < pelatut kierrokset).
 */
export function seasonLine(r: ModelRaceResponse | null | undefined): SeasonLine | null {
	if (!r?.meta?.available) return null;
	const diff = r.totals?.diff;
	const n = r.meta.compared_gws;
	if (typeof diff === 'number' && typeof r.totals?.you === 'number' && typeof n === 'number' && n > 0) {
		return { kind: 'you', diff, gameweeks: n };
	}
	const text = MODEL_SERIES_COPY.modelVsAverage(r.totals?.model_vs_average);
	return text ? { kind: 'model_vs_average', text } : null;
}

export type CsFixture = {
	team: string;
	opponent: string;
	venue: string;
	/** Mallin clean sheet -todennakoisyys prosentteina (palvelimen luku). */
	cs: number;
};

/**
 * Deadline-kierroksen parhaat clean sheet -ottelut, ottelu kerrallaan.
 *
 * - Kierros = `actionableGameweek` (kesken kierroksen deadline-kierros, ei
 *   kesken oleva: siihen ei voi enaa vaikuttaa).
 * - Vain `cs_pct`:lliset lahirivit. Kaukorivilla ei ole CS%:a
 *   rakenteellisesti (27.7 horisonttikontrakti), eika sita keksita.
 * - Tuplakierroksella joukkue voi olla listalla kahdesti: luku on ottelun,
 *   ei kierroksen (kahden ottelun yhdistettya todennakoisyytta ei ole).
 */
export function gwCleanSheets(
	d: FantasyResponse | null | undefined,
	n = 3
): { gw: number; rows: CsFixture[] } | null {
	if (!d?.meta?.available) return null;
	const gw = actionableGameweek(d.meta);
	if (gw === undefined) return null;
	const rows: CsFixture[] = [];
	for (const t of d.teams ?? []) rows.push(...csFixtures(t, gw));
	rows.sort((a, b) => b.cs - a.cs);
	return { gw, rows: rows.slice(0, Math.max(0, n)) };
}

/** Joukkueen mallinnetut ottelut yhdella kierroksella. YKSI suodatin
 *  molemmille pinnoille (This week -rivi ja Teams-ruudukko): vain
 *  `cs_pct`:lliset lahirivit, kaukoriveille ei keksita lukua. */
function csFixtures(t: FantasyTeam, gw: number): CsFixture[] {
	const out: CsFixture[] = [];
	for (const f of t.fixtures ?? []) {
		if (f.gw !== gw || typeof f.cs_pct !== 'number' || f.tier === 'far') continue;
		out.push({ team: t.short ?? t.name, opponent: f.opponent_short, venue: f.venue, cs: f.cs_pct });
	}
	return out;
}

export type CsGridRow = {
	team: string;
	name: string;
	/** Keskiarvo otteluittain naytetyilta kierroksilta, null ilman otteluita. */
	avg: number | null;
	games: number;
	cells: { gw: number; fixtures: CsFixture[]; blank: boolean }[];
};

/**
 * Teams-nakyman clean sheet -ruudukko (22.9, A3 2.3: "CS% ruudukko, ei
 * FDR:aa"). Sarakkeet ovat deadline-kierroksesta eteenpain ne kierrokset
 * joilla palvelin antaa CS%:n (lahihorisontti datasta, ei kovakoodattua
 * pituutta). Kesken olevaa kierrosta ei naytetä: siihen ei voi enaa
 * vaikuttaa. Tyhja kierros (ei ottelua) on `blank`, ei nolla.
 * Jarjestys: paras keskiarvo ensin; joukkue ilman otteluita viimeisena.
 */
export function teamsCsGrid(
	d: FantasyResponse | null | undefined
): { gws: number[]; rows: CsGridRow[] } | null {
	if (!d?.meta?.available) return null;
	const from = actionableGameweek(d.meta);
	if (from === undefined) return null;
	const gws = [
		...new Set(
			(d.teams ?? []).flatMap((t) =>
				(t.fixtures ?? [])
					.filter((f) => f.gw >= from && typeof f.cs_pct === 'number' && f.tier !== 'far')
					.map((f) => f.gw)
			)
		)
	].sort((a, b) => a - b);
	const rows: CsGridRow[] = (d.teams ?? []).map((t) => {
		const cells = gws.map((gw) => {
			const fixtures = csFixtures(t, gw);
			const any = (t.fixtures ?? []).some((f) => f.gw === gw);
			return { gw, fixtures, blank: !any };
		});
		const all = cells.flatMap((c) => c.fixtures);
		return {
			team: t.short ?? t.name,
			name: t.name,
			avg: all.length ? all.reduce((s, f) => s + f.cs, 0) / all.length : null,
			games: all.length,
			cells
		};
	});
	rows.sort((a, b) => {
		if (a.avg == null && b.avg == null) return a.name.localeCompare(b.name);
		if (a.avg == null) return 1;
		if (b.avg == null) return -1;
		return b.avg - a.avg;
	});
	return { gws, rows };
}
