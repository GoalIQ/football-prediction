/** Kierrosvalinta SPA:lle: yksi funktio, ei kuutta haaraa.
 *
 * 🔴 MIKSI: `meta.next_gameweek` on KESKEN oleva kierros heti kun kierroksen
 * ensimmainen ottelu on alkanut. 30.8.2026 mitattu: `next_gameweek` oli 2 ja
 * `deadline_gameweek` 3. Kaikki mihin lukija voi VIELA vaikuttaa - kapteeni,
 * xP-teaser, siirrot - kuuluu deadline-kierrokselle.
 *
 * WorkspaceBar korjasi taman itselleen 22.8 (palkki naytti "GAMEWEEK 1
 * DEADLINE Fri 28 Aug"), mutta korjaus jai yhteen komponenttiin ja viisi
 * muuta kayttokohtaa jai raa'an `next_gameweek`in varaan. Sama vikaluokka
 * jonka backendin `fpl_gameweek.py` dokumentoi viidesti. Nyt logiikka on
 * yhdessa paikassa, kuten backendissa `actionable_gameweek`.
 */
export function actionableGameweek(
	meta: { deadline_gameweek?: number | null; next_gameweek?: number | null } | null | undefined
): number | undefined {
	const m = meta ?? {};
	if (typeof m.deadline_gameweek === 'number') return m.deadline_gameweek;
	if (typeof m.next_gameweek === 'number') return m.next_gameweek;
	/* undefined eika null: kutsupaikat antavat taman eteenpain funktioille
	   joiden parametri on `number | undefined`. Nolla EI ole vaihtoehto -
	   se olisi kierros 0 (muisti: nolla-ei-ole-sama-kuin-ei-tietoa). */
	return undefined;
}

/* ------------------------------------------------------------------------
 * Deadline-rivi (22.9.2026, A3 2.1: "kiinnitetty GW-palkki"). Hero ja This
 * week lukevat SAMAN muotoilun: kaksi kopiota eriytyisi ensimmaisessa
 * muutoksessa (sama vikaluokka kuin WorkspaceBar 22.8).
 *
 * 🔴 AIKA RENDEROIDAAN SELAIMEN VYOHYKKEELLA. Deadline tulee UTC:na;
 * toLocaleString ilman timeZone-parametria kayttaa lukijan omaa vyohyketta.
 * Kieli on lukittu en-GB (suomalaisella koneella rivi renderoitui muuten
 * "pe 21.8. klo 20.30" englanninkielisessa tuotteessa).
 * --------------------------------------------------------------------- */
const LOC = 'en-GB';

/** "Sat 10 Oct, 11:00 BST" (lukijan vyohyke). */
export function formatDeadline(d: Date): { when: string; tz: string } {
	const when = d.toLocaleString(LOC, {
		weekday: 'short',
		day: 'numeric',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
	const tz =
		new Intl.DateTimeFormat(LOC, { timeZoneName: 'short' })
			.formatToParts(d)
			.find((p) => p.type === 'timeZoneName')?.value ?? '';
	return { when, tz };
}

export type WeekPhase = {
	/** Kierros jonka deadline on edessa (actionableGameweek). */
	gw: number;
	/** Kesken oleva kierros, tai null kun mitaan ei pelata juuri nyt. */
	liveGw: number | null;
	deadline: Date | null;
	/** Kokonaisia tunteja deadlineen, null ilman deadlinea tai kun se meni. */
	hoursLeft: number | null;
};

/**
 * Viikon vaihe fantasy-metasta. Ajetaan synteettisilla vaiheilla (saanto 6a
 * kohta 3, `weekRows.test.ts`): ennen deadlinea, kesken kierroksen,
 * kierrosten valissa ja kauden lopussa ilman deadlinea.
 *
 * `liveGw`: kierros on kesken kun `next_gameweek` on pienempi kuin
 * `deadline_gameweek` (mitattu 30.8: 2 vs 3 ensimmaisen ottelun jalkeen).
 * Muuten kierrosten valissa ei pelata FPL-otteluita ennen deadlinea, joten
 * tauko ei ole paattely vaan tama sama ehto.
 */
export function weekPhase(
	meta:
		| { deadline_gameweek?: number | null; next_gameweek?: number | null; deadline_utc?: string | null }
		| null
		| undefined,
	now: number
): WeekPhase | null {
	const gw = actionableGameweek(meta);
	if (gw === undefined) return null;
	const next = meta?.next_gameweek;
	const liveGw = typeof next === 'number' && next < gw ? next : null;
	let deadline: Date | null = null;
	if (meta?.deadline_utc) {
		const t = new Date(meta.deadline_utc);
		if (!isNaN(t.getTime())) deadline = t;
	}
	const ms = deadline ? deadline.getTime() - now : null;
	const hoursLeft = ms != null && ms > 0 ? Math.floor(ms / 3_600_000) : null;
	return { gw, liveGw, deadline, hoursLeft };
}

/** "18 days" / "1 day" / "5 hours" / "under an hour". null kun deadline meni. */
export function countdownText(hoursLeft: number | null): string | null {
	if (hoursLeft == null) return null;
	if (hoursLeft >= 48) {
		const d = Math.floor(hoursLeft / 24);
		return `${d} days`;
	}
	if (hoursLeft >= 24) return '1 day';
	if (hoursLeft >= 1) return `${hoursLeft} hour${hoursLeft === 1 ? '' : 's'}`;
	return 'under an hour';
}
