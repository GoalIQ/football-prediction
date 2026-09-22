/**
 * $lib/pitchLineup - My teamin kentan KOKOONPANO ja OTSIKKO yhdesta lukijasta
 * (pariteetti mobiilin lib/pitchLineup.ts:n kanssa, 22.9.2026).
 *
 * 🔴 MIKSI. `team.players[].in_xi` on MALLIN XI: backend valitsee sen rungosta
 * horisontti-xP:lla (src/models/fpl_rate_team.py `xi = optimal_xi(squad)`,
 * kommentti "LUCK-PITCH": "rivien `in_xi` on MALLIN OPTIMI-XI, ei sita mita
 * kayttaja pelasi"). TeamPitchManager asetteli silti ratkenneen kierroksen
 * pisteet `in_xi`:n mukaan. Mitattu FPL:sta, entry 116920 GW5: Gonzalo aloitti
 * (2 p) mutta oli kentalla penkilla, Thomas oli penkilla (9 p) mutta kentalla
 * avauksessa, Haaland (C) nakyi 6:na kun FPL nayttaa 12, ja kentan summa oli
 * 41 eika FPL:n 40. Ilmaispinnan otsikko oli "Starting XI".
 *
 * NYT KOKOONPANOLLA ON LAHDE, JA OTSIKKO LUETAAN LAHTEESTA (saanto 6a, kohta 1):
 *   'settled' = FPL:n omat picksit (`last_finished.players`). XI = multiplier
 *               > 0, penkki = 0, C/V = is_captain / is_vice_captain, solun
 *               luku kerrotaan kertoimella (kapteeni 2, TC 3, Bench Boost:
 *               kaikki 1). Otsikko "Your team · GW5 result" (EI "Starting XI":
 *               FPL paivittaa multiplierin automaattivaihtojen jalkeen, ja
 *               Bench Boostissa kentalla on 15; julkaisutarkistaja 22.9).
 *   'model'   = `in_xi` (ilmaispinta). Otsikko sanoo mita se on: "Model's XI
 *               from your 15, picked on GW6-GW11 xP · GW6". Ikkuna on SAMA
 *               merkkijono kuin otsakerivin "Next 6 GW (GW6-GW11)"
 *               (`declaredRange`), koska backend valitsee XI:n samalla
 *               summalla jonka se julkaisee `rating.team_xp_horizon`ina.
 *   'plan'    = Premiumin muokattava what-if (alkutila mallin XI). Ei
 *               otsikkoa (11.9: chipit ja kentta selittavat itsensa).
 *
 * KAPTEENI SAMASTA LAHTEESTA KUIN KOKOONPANO (julkaisutarkistaja, mobiilin
 * kierros 3):
 *   'settled' = FPL:n is_captain / is_vice_captain (kayttajan pelaama).
 *   'model'   = MALLIN kapteenikutsu `captain.pick` (sama kuin This weekin
 *               "Suggested captain"), vain kun sen kierros `meta.captain_gw`
 *               on kentan kierros ja pelaaja on mallin XI:ssa; muuten ei C:ta.
 *               EI `players[].is_captain`: se on backendin effective_captain
 *               (fpl_rate_team.py: "annettu/picksista jos XI:ssa"), eli
 *               kayttajan GW5-kapteeni Haaland. Mallin XI:n otsikon alla se
 *               nimesi eri kapteenin kuin This week (B.Fernandes 6.8) samalle
 *               kierrokselle.
 *   'plan'    = what-ifin oma kapteeni (kayttajan muokattava tila).
 *
 * Kentta ei lue `in_xi`:ta itse. Portti: pitchLineup.gate.test.ts.
 */
import type { LastFinishedGw, RatedPlayer } from './fantasyTools';
import { declaredRange, type XpHorizon } from './xpHorizon';

/** Yksi rivi FPL:n omista pickseista (rate-teamin `last_finished.players`). */
export type SettledPick = LastFinishedGw['players'][number];

export type LineupSource = 'settled' | 'model' | 'plan';

/** Premiumin what-if-tila sellaisenaan (TeamPitchManagerin `$state`). */
export interface WhatIfPlan {
	xiIds: readonly number[];
	captainId: number | null;
	viceId: number | null;
}

export interface PitchLineup {
	source: LineupSource;
	/** Avauksen pelaajat. 'settled': FPL:n pick-jarjestyksessa. */
	xi: RatedPlayer[];
	bench: RatedPlayer[];
	captainId: number | null;
	viceId: number | null;
	/** Solun kerroin: 'settled' = FPL:n multiplier XI:lle (penkki 1, eli
	 *  pelaajan oma luku), muuten aina 1. */
	factor: (id: number) => number;
}

/** Mallin kapteenikutsu ja sen kierros (rate-teamin `captain.pick` +
 *  `meta.captain_gw`). Sama muoto kuin mobiilin lib/pitchLineup.ts:ssa. */
export interface ModelCaptain {
	id: number | null;
	gw: number | null;
}

export function modelCaptainOf(data: {
	captain?: { pick?: { id?: number } | null } | null;
	meta?: { captain_gw?: number | null } | null;
}): ModelCaptain {
	const id = data.captain?.pick?.id;
	const gw = data.meta?.captain_gw;
	return {
		id: typeof id === 'number' ? id : null,
		gw: typeof gw === 'number' ? gw : null
	};
}

/** Mallin kapteeni kentalle, jonka kierros on `gw`. Eri kierroksen kutsu
 *  (esim. kesken kierroksen kutsu koskee seuraavaa) ei saa osua kentalle. */
export function modelCaptainFor(
	mc: ModelCaptain | null | undefined,
	gw: number | null
): number | null {
	if (!mc || mc.id == null || mc.gw == null || gw == null) return null;
	return mc.gw === gw ? mc.id : null;
}

const POSITIONS = new Set(['GKP', 'DEF', 'MID', 'FWD']);

/** Pelaaja joka pelasi ratkenneen kierroksen mutta ei ole enaa rungossa
 *  (Premiumin sovellettu siirto). Paita piirretaan silti: kierroksen tulos on
 *  sen kierroksen joukkueen tulos. */
function playerFromPick(r: SettledPick): RatedPlayer {
	const pos = POSITIONS.has(String(r.pos)) ? (r.pos as RatedPlayer['pos']) : 'MID';
	return {
		id: r.id,
		web_name: r.web_name ?? '',
		team_short: r.team_short ?? '',
		pos,
		price: 0,
		xp_per_gw: 0,
		xp_horizon_total: 0,
		// Ei rungossa -> ei mallin XI:ssa. Kentta ei lue tata kenttaa.
		in_xi: false,
		is_captain: r.is_captain === true
	};
}

function multiplierOf(r: SettledPick): number {
	return typeof r.multiplier === 'number' && Number.isFinite(r.multiplier) ? r.multiplier : 0;
}

/**
 * Ratkenneen kierroksen rivin kerroin solun luvulle: XI:n FPL-multiplier
 * (kapteeni 2, Triple Captain 3, Bench Boost kaikki >= 1), penkki 1 eli
 * pelaajan oma luku. YKSI lukija kentalle (`pitchLineup().factor`) ja
 * jakokortille (`settledCardNumbers`). Sama funktio mobiilissa
 * (goaliq-app lib/pitchLineup.ts).
 *
 * 🔴 22.9 (julkaisutarkistaja, web-kentta): kentta naytti Haalandin (C)
 * 12 / 13.0, mutta jakokortti 6 / 6.5 C, ja kortin solut summautuivat 34:aan
 * otsikon "You 40" alla. Kortti rakensi solunsa omalla kaavallaan eika
 * lukenut kerrointa lainkaan.
 */
export function settledFactor(r: SettledPick): number {
	const m = multiplierOf(r);
	return m >= 1 ? m : 1;
}

export interface SettledCardNumbers {
	/** Pisteet kertoimella (FPL:n oma luku), null = ei pisteita. */
	pts: number | null;
	/** Deadline-freeze samalla kertoimella, null = ei freezea. */
	xp: number | null;
	/** pts - xp, null kun kumpi tahansa puuttuu. */
	diff: number | null;
}

/** Jakokortin solun luvut ratkenneen kierroksen rivista. Tuomio (lucky /
 *  robbed) EI ole taalla: se luetaan kertoimettomista ($lib/luck
 *  `luckVerdict`), koska kerroin kuuluu summaan, ei tuomioon. */
/**
 * Jakokortin legendin kerroinmerkinta (julkaisutarkistaja 22.9): kortin
 * kapteenisolu on kerrottu, reitti /fpl/points/gw{n} ei. "C = captain x2",
 * Triple Captain "x3", ja kun varakapteeni nousi kapteeniksi (kapteeni ei
 * pelannut) "V = vice-captain x2". null = kukaan ei pelannut kertoimella >= 2.
 * Sama funktio mobiilissa (goaliq-app lib/pitchLineup.ts).
 */
export function armbandLabel(played: readonly SettledPick[]): string | null {
	const boosted = played.find(
		(r) => multiplierOf(r) >= 2 && (r.is_captain === true || r.is_vice_captain === true)
	);
	if (!boosted) return null;
	const who = boosted.is_captain === true ? 'C = captain' : 'V = vice-captain';
	return `${who} x${multiplierOf(boosted)}`;
}

/** Hit-viikon merkinta alaotsikkoon: "-4 hit". null kun hittia ei ole. */
export function hitLabel(transferCost: number | null | undefined): string | null {
	return typeof transferCost === 'number' && Number.isFinite(transferCost) && transferCost > 0
		? `-${transferCost} hit`
		: null;
}

export function settledCardNumbers(r: SettledPick): SettledCardNumbers {
	const f = settledFactor(r);
	const pts = typeof r.points === 'number' && Number.isFinite(r.points) ? r.points * f : null;
	const xp =
		typeof r.xp_frozen === 'number' && Number.isFinite(r.xp_frozen) ? r.xp_frozen * f : null;
	return { pts, xp, diff: pts != null && xp != null ? pts - xp : null };
}

/**
 * Kokoonpano kentalle.
 *
 * @param players  rate-teamin rivit (ruudun runko).
 * @param settled  `last_finished.players` VAIN kun kentalla on ratkennut
 *                 kierros (sama `settledGwReadable`-ehto kuin toteumakartalla),
 *                 muuten null. Ilman yhtaan multiplier > 0 -rivia lahde ei ole
 *                 'settled': tyhja kentta olisi vaite ettei kukaan pelannut.
 * @param plan     Premiumin what-if-tila, tai null (ilmaispinta).
 * @param modelCaptainId  `modelCaptainFor(...)`: mallin kapteeni kentan
 *                 kierrokselle tai null. Pakollinen, jotta kutsupaikka ei voi
 *                 pudota `is_captain`-kenttaan.
 */
export function pitchLineup(
	players: readonly RatedPlayer[],
	settled: readonly SettledPick[] | null | undefined,
	plan: WhatIfPlan | null | undefined,
	modelCaptainId: number | null
): PitchLineup {
	const picks = settled ?? [];
	if (picks.some((r) => multiplierOf(r) > 0)) {
		const byId = new Map(players.map((p) => [p.id, p]));
		const toPlayer = (r: SettledPick) => byId.get(r.id) ?? playerFromPick(r);
		const factorById = new Map(picks.map((r) => [r.id, settledFactor(r)]));
		return {
			source: 'settled',
			xi: picks.filter((r) => multiplierOf(r) > 0).map(toPlayer),
			bench: picks.filter((r) => multiplierOf(r) <= 0).map(toPlayer),
			captainId: picks.find((r) => r.is_captain === true)?.id ?? null,
			viceId: picks.find((r) => r.is_vice_captain === true)?.id ?? null,
			factor: (id) => factorById.get(id) ?? 1
		};
	}
	if (plan) {
		const byId = new Map(players.map((p) => [p.id, p]));
		const xi = plan.xiIds.map((id) => byId.get(id)).filter((p): p is RatedPlayer => !!p);
		const xiIds = new Set(xi.map((p) => p.id));
		const captainId = plan.captainId != null && xiIds.has(plan.captainId) ? plan.captainId : null;
		return {
			source: 'plan',
			xi,
			bench: players.filter((p) => !xiIds.has(p.id)),
			captainId,
			viceId:
				plan.viceId != null && xiIds.has(plan.viceId) && plan.viceId !== captainId
					? plan.viceId
					: null,
			factor: () => 1
		};
	}
	const xi = players.filter((p) => p.in_xi);
	const xiIds = new Set(xi.map((p) => p.id));
	return {
		source: 'model',
		xi,
		bench: players.filter((p) => !xiIds.has(p.id)),
		captainId: modelCaptainId != null && xiIds.has(modelCaptainId) ? modelCaptainId : null,
		// Rate-teamin rivilla ei ole varakapteenia.
		viceId: null,
		factor: () => 1
	};
}

/**
 * Kentan otsikko kokoonpanon LAHTEESTA. Ei toista ehtoa: jos lahde on malli,
 * otsikko ei voi sanoa "Starting XI", ja jos lahde on FPL:n picksit, se ei voi
 * sanoa mallin XI. Premiumin what-if ('plan') ei saa otsikkoa (null).
 *
 * @param horizon   rate-teamin `xpHorizon(meta)`. Ikkuna luetaan
 *                  `declaredRange`:lla, samalla funktiolla kuin otsakerivi.
 *                  null = ikkunaa ei julistettu: peruste jaa pois.
 * @param settledGw ratkennut kierros (`last_finished.gw`).
 * @param gw        kierros jonka luvut kentalla ovat 'model'-tilassa.
 */
export function pitchTitle(
	source: LineupSource,
	o: { horizon: XpHorizon | null | undefined; settledGw: number | null; gw: number | null }
): string | null {
	if (source === 'settled') {
		return o.settledGw != null ? `Your team · GW${o.settledGw} result` : 'Your team';
	}
	if (source === 'plan') return null;
	const span = declaredRange(o.horizon);
	const head =
		span != null ? `Model's XI from your 15, picked on ${span} xP` : "Model's XI from your 15";
	return o.gw != null ? `${head} · GW${o.gw}` : head;
}
