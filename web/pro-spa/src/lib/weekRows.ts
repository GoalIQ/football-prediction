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
 * Mallin oman FPL-entryn id (22.9, julkaisutarkistaja B1). YKSI lukija:
 * This weekin "The model's captain" -kortti lukee mallin joukkueen taman
 * entryn kautta eika optimoijan vapaasta rungosta. Lahde on model-racen
 * `entry_series` (sama entry jonka goaliq.app/fpl nimeaa mallin rungoksi).
 * Puuttuva tai kelvoton id -> null, eika korttia korvata millaan muulla
 * rungolla (fail-closed).
 */
export function modelEntryId(r: ModelRaceResponse | null | undefined): number | null {
	const id = r?.entry_series?.entry_id;
	return typeof id === 'number' && Number.isInteger(id) && id > 0 ? id : null;
}

/** Mallin kortin lahdepolku: sama rate-team-lukija kuin omalla joukkueella. */
export function modelCardPath(entryId: number): string {
	return `/api/fantasy/rate-team?entry=${entryId}`;
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
