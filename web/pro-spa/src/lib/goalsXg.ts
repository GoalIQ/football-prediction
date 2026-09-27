/**
 * MP-17 (27.9.2026): maalit vs xG kumulatiivisena pelaajakortissa.
 *
 * YKSI lukija (saanto 6a): kortti ei laske summia itse. Luvut ovat FPL:n omia
 * (/api/fantasy/player-stats `goaliq.gws[]`), ei mallin estimaatteja.
 *
 * REHELLISYYS:
 *  - kierros jolta ei ole FPL-rivia (mins null) ei lisaa mitaan eika ole
 *    "0 maalia": tooltip sanoo "no FPL row"
 *  - vanha API ilman kenttia -> null, kaaviota ei piirreta (ei nollaviivaa
 *    joka vaittaisi 0 maalia / 0 xG)
 *  - pelaaja joka ei ole pelannut minuuttiakaan -> null
 */
import type { PlayerStatsGw } from './fantasyTools';

export interface GoalsXgPoint {
	gw: number;
	/** FPL-rivi olemassa (voi olla 0 min). */
	hasRow: boolean;
	mins: number | null;
	g: number;
	xg: number;
	cumG: number;
	cumXg: number;
}

export interface GoalsXgView {
	points: GoalsXgPoint[];
	totalG: number;
	totalXg: number;
	fromGw: number;
	toGw: number;
}

export function goalsXgView(gws: PlayerStatsGw[] | null | undefined): GoalsXgView | null {
	if (!gws || gws.length === 0) return null;
	// Vanha API: kenttaa ei ole lainkaan (undefined). Ei arvata nollia.
	if (!gws.some((r) => r.mins !== undefined)) return null;
	if (!gws.some((r) => (r.mins ?? 0) > 0)) return null;
	let cumG = 0;
	let cumXg = 0;
	const points: GoalsXgPoint[] = [];
	for (const r of gws) {
		const hasRow = r.mins != null;
		const g = hasRow ? (r.g ?? 0) : 0;
		const xg = hasRow ? (r.xg ?? 0) : 0;
		cumG += g;
		cumXg += xg;
		points.push({ gw: r.gw, hasRow, mins: r.mins ?? null, g, xg, cumG, cumXg: round2(cumXg) });
	}
	// Loppupaan rivittomat kierrokset (tuleva / ei viela pelattu) pois:
	// viiva ei jatku tulevaisuuteen.
	while (points.length > 1 && !points[points.length - 1].hasRow) points.pop();
	return {
		points,
		totalG: cumG,
		totalXg: round2(cumXg),
		fromGw: points[0].gw,
		toGw: points[points.length - 1].gw
	};
}

function round2(n: number): number {
	return Math.round(n * 100) / 100;
}

export function goalsWord(n: number): string {
	return n === 1 ? '1 goal' : `${n} goals`;
}

/** Otsikkorivi: vain luvut, ei tulkintaa ("ylisuorittaa", "regressoi"). */
export function goalsXgHeadline(v: GoalsXgView): string {
	return `${goalsWord(v.totalG)} from ${v.totalXg.toFixed(1)} xG, GW${v.fromGw}-${v.toGw}`;
}

export function goalsXgTooltip(p: GoalsXgPoint): string {
	if (!p.hasRow) return `GW${p.gw}: no FPL row (did not feature)`;
	const tama = `GW${p.gw}: ${goalsWord(p.g)} from ${p.xg.toFixed(2)} xG`;
	return `${tama} · season so far ${goalsWord(p.cumG)} from ${p.cumXg.toFixed(1)} xG`;
}

export const GOALS_XG_TITLE = 'Goals against expected goals';
export const GOALS_XG_CAPTION =
	"Running totals from FPL's own numbers. xG is FPL's expected goals, the quality of the chances he shot from, not a GoalIQ projection.";
export const GOALS_XG_ARIA = 'Running total of goals and of expected goals, after each gameweek';

export interface GoalsXgPad {
	top: number;
	right: number;
	bottom: number;
	left: number;
}
export const GOALS_XG_PAD: GoalsXgPad = { top: 10, right: 58, bottom: 18, left: 8 };

export function goalsXgGeometry(v: GoalsXgView, w: number, h: number, pad: GoalsXgPad = GOALS_XG_PAD) {
	const n = v.points.length;
	const hi = Math.max(1, Math.ceil(Math.max(v.totalG, v.totalXg)));
	const plotW = w - pad.left - pad.right;
	const plotH = h - pad.top - pad.bottom;
	const x = (i: number) => pad.left + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
	const y = (val: number) => pad.top + (1 - val / hi) * plotH;
	const line = (key: 'cumG' | 'cumXg') =>
		v.points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join(' ');
	const last = n - 1;
	// Nimilaput viivojen paihin: jos pisteet ovat alle LABEL_GAP:n paassa
	// toisistaan, ylempi nousee ja alempi laskee, jotta ne eivat peita
	// toisiaan (esim. 2 maalia / 2.1 xG).
	const LABEL_GAP = 11;
	let lg = y(v.totalG) + 3;
	let lx = y(v.totalXg) + 3;
	if (Math.abs(lg - lx) < LABEL_GAP) {
		const mid = (lg + lx) / 2;
		const goalsAbove = v.totalG >= v.totalXg;
		lg = mid + (goalsAbove ? -LABEL_GAP / 2 : LABEL_GAP / 2);
		lx = mid + (goalsAbove ? LABEL_GAP / 2 : -LABEL_GAP / 2);
	}
	return {
		hi,
		plotLeft: pad.left,
		plotRight: w - pad.right,
		labelX: x(last) + 6,
		labelGoalsY: lg,
		labelXgY: lx,
		baseline: y(0),
		top: y(hi),
		goalsPath: line('cumG'),
		xgPath: line('cumXg'),
		markers: v.points.map((p, i) => ({ i, p, cx: x(i), gy: y(p.cumG), xy: y(p.cumXg) })),
		endGoals: { x: x(last), y: y(v.totalG) },
		endXg: { x: x(last), y: y(v.totalXg) },
		slot: n > 1 ? plotW / (n - 1) : plotW
	};
}
