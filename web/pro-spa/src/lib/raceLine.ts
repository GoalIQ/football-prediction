/** MP-14 toinen puolisko (26.9.2026): Season racen kumulatiivinen eroviiva.
 *
 * YKSI LUKIJA (saanto 6a) viivalle, sen pisteiden luvuille ja vihjetekstille.
 * Mobiilin vastine: goaliq-app lib/raceLine.ts (sama saanto).
 *
 * Kaavio on vaite (muisti kaavio-on-vaite-piste-katoaa-hiljaa), joten:
 *  - viivalla on vain VERTAILLUT kierrokset (`cumulative_diff` != null). Rivi
 *    jolla mallin luku on vanhentunut tai oma luku puuttuu ei ole summassa,
 *    joten se ei saa olla viivalla nollana eika interpoloituna.
 *  - x on kierroksen NUMERO, ei jarjestysnumero: puuttuva kierros nakyy
 *    katkona. Viiva ei yhdista GW3:a GW5:een, koska kalteva jana vaittaisi
 *    etta GW4 muutti eroa.
 *  - viimeisen pisteen arvon on oltava tasan `totals.diff`, eli sama luku
 *    jonka kortin lause sanoo. Jos ne eroavat, viivaa ei piirreta lainkaan:
 *    kaavio joka riitelee viereisen lauseen kanssa on pahempi kuin ei kaaviota.
 *  - nolla on aina asteikolla, koska nollaviiva on "tasoissa mallin kanssa".
 */
import type { ModelRaceResponse } from './api';

export type RaceState = 'final' | 'in_progress' | 'awaiting_check' | 'unknown';

export interface RacePoint {
	gw: number;
	/** Juokseva ero tahan kierrokseen asti (sinun pisteesi miinus mallin). */
	cum: number;
	/** Taman kierroksen ero. */
	diff: number;
	you: number;
	model: number;
	state: RaceState;
	/** false = mallin oman hitin kustannusta ei voitu todentaa (luku brutto). */
	costVerified: boolean;
}

export interface RaceLineView {
	points: RacePoint[];
	gwFrom: number;
	gwTo: number;
	/** true = kierrosvalilla on kierros joka ei ole kisassa (viivassa katko). */
	hasGap: boolean;
}

function stateOf(s: string | undefined, provisional: boolean | undefined): RaceState {
	if (s === 'in_progress' || s === 'awaiting_check' || s === 'unknown') return s;
	if (s === 'final') return 'final';
	return provisional ? 'unknown' : 'final';
}

export function raceLineView(r: ModelRaceResponse | null | undefined): RaceLineView | null {
	if (!r?.meta?.available) return null;
	const total = r.totals?.diff;
	if (total == null) return null;
	const points: RacePoint[] = (r.gameweeks ?? [])
		.filter(
			(g) =>
				g.cumulative_diff != null &&
				g.diff != null &&
				g.your_points != null &&
				g.model_points != null
		)
		.map((g) => ({
			gw: g.gw,
			cum: g.cumulative_diff as number,
			diff: g.diff as number,
			you: g.your_points as number,
			model: g.model_points as number,
			state: stateOf(g.state, g.provisional),
			costVerified: g.model_cost_verified !== false
		}))
		.sort((a, b) => a.gw - b.gw);
	// Yksi piste ei ole viiva; kortin lause kertoo saman luvun.
	if (points.length < 2) return null;
	// Viimeinen piste = kortin lauseen luku, tai ei kaaviota.
	if (points[points.length - 1].cum !== total) return null;
	const gwFrom = points[0].gw;
	const gwTo = points[points.length - 1].gw;
	return { points, gwFrom, gwTo, hasGap: gwTo - gwFrom + 1 !== points.length };
}

/** Kokonaisluku etumerkilla: +161 / -12 / 0. */
export function signedPts(n: number): string {
	return `${n > 0 ? '+' : ''}${n}`;
}

export function pointTooltip(p: RacePoint): string {
	const base = `GW${p.gw}: you ${p.you}, model ${p.model} (${signedPts(p.diff)}). Running total ${signedPts(p.cum)}`;
	const tags: string[] = [];
	if (p.state !== 'final') tags.push('provisional');
	if (!p.costVerified) tags.push("model's hit not verified");
	return tags.length ? `${base} (${tags.join(', ')})` : base;
}

export const RACE_LINE_CAPTION =
	'Running difference after each gameweek. Above the line you are ahead of the model, below it the model is ahead.';
export const RACE_LINE_GAP = "A break in the line is a gameweek that isn't counted in the race.";
export const RACE_LINE_ARIA = "Running difference between your points and the model's, after each gameweek";

export interface RaceLinePad {
	top: number;
	right: number;
	bottom: number;
	left: number;
}

export const RACE_LINE_PAD: RaceLinePad = { top: 10, right: 34, bottom: 18, left: 8 };

/** Viivan geometria viewBox-yksikoissa. Nolla aina asteikolla. Heittaa jos
 *  piste putoaisi piirtoalueen ulkopuolelle: SVG leikkaisi sen hiljaa. */
export function raceLineGeometry(v: RaceLineView, w: number, h: number, pad: RaceLinePad = RACE_LINE_PAD) {
	const hi = Math.max(0, ...v.points.map((p) => p.cum));
	const lo = Math.min(0, ...v.points.map((p) => p.cum));
	const span = Math.max(1, hi - lo);
	const plotW = w - pad.left - pad.right;
	const plotH = h - pad.top - pad.bottom;
	const gwSpan = Math.max(1, v.gwTo - v.gwFrom);
	const x = (gw: number) => pad.left + ((gw - v.gwFrom) / gwSpan) * plotW;
	const y = (val: number) => {
		const out = pad.top + ((hi - val) / span) * plotH;
		if (out < pad.top - 1e-9 || out > pad.top + plotH + 1e-9) {
			throw new Error(`race line: ${val} outside [${lo}, ${hi}]`);
		}
		return out;
	};
	const markers = v.points.map((p, i) => ({ ...p, i, cx: x(p.gw), cy: y(p.cum) }));
	// Jana vain perakkaisten kierrosten valille; katko kun valissa on kierros
	// joka ei ole kisassa. Jana kesken olevaan kierrokseen katkoviivana.
	const segments = markers.slice(1).flatMap((m, k) => {
		const prev = markers[k];
		if (m.gw !== prev.gw + 1) return [];
		return [{ x1: prev.cx, y1: prev.cy, x2: m.cx, y2: m.cy, dashed: m.state !== 'final' }];
	});
	// Akselin kierrosnumerot: joka n:s, aina ensimmainen ja viimeinen.
	const count = v.gwTo - v.gwFrom + 1;
	const step = Math.max(1, Math.ceil(count / 10));
	const ticks: { gw: number; x: number }[] = [];
	for (let gw = v.gwFrom; gw <= v.gwTo; gw++) {
		if ((gw - v.gwFrom) % step === 0 || gw === v.gwTo) ticks.push({ gw, x: x(gw) });
	}
	// Tihea akseli: viimeinen tick ei saa osua edellisen paalle.
	if (ticks.length > 1 && ticks[ticks.length - 1].x - ticks[ticks.length - 2].x < 12) {
		ticks.splice(ticks.length - 2, 1);
	}
	// Hitboxien leveys = kierrosvali, jotta vierekkaiset eivat mene paallekkain.
	const slot = plotW / gwSpan;
	const last = markers[markers.length - 1];
	return {
		zero: y(0),
		plotLeft: pad.left,
		plotRight: w - pad.right,
		slot,
		markers,
		segments,
		ticks,
		endLabel: { x: last.cx + 7, y: last.cy + 3, text: signedPts(last.cum) },
		// Nollaviivan "0" oikeaan marginaaliin, ellei se osu loppuluvun paalle.
		zeroLabel: Math.abs(y(0) - last.cy) >= 10 ? { x: w - pad.right + 7, y: y(0) + 3 } : null
	};
}
