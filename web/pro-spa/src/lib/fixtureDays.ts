/**
 * Fixtures-listan paivaryhmat LUKIJAN omassa ajassa (julkaisutarkistaja 1.11.2026, PR #75).
 *
 * Ennen ryhmittely luki API:n `date`-kentan (UTC-paiva) ja otsikko muotoili sen
 * hetkesta `${iso}T00:00:00Z` paikallisessa ajassa, kun taas kellonaika oli
 * paikallinen. Uusi lause "Kick-off times are in your time zone" teki siita
 * vaaran vaitteen: New Yorkissa lauantain 15:00 UTC -ottelu oli otsikon
 * "Friday 6 November" alla, Sydneyssa perjantain 20:00 UTC -ottelu (lauantai
 * 07:00 paikallisesti) samoin.
 *
 * Yksi lukija (saanto 6a kohta 1): paivan avain tulee AINA ottelun hetkesta
 * lukijan vyohykkeessa; `date` vain jos hetkea ei ole. Otsikko muotoillaan
 * avaimesta UTC-keskipaivana, jolloin YYYY-MM-DD -> viikonpaiva ei riipu
 * vyohykkeesta. `timeZone` on testeja varten (undefined = laitteen vyohyke).
 */

const LOCALE = 'en-GB';

/** YYYY-MM-DD lukijan vyohykkeessa. */
export function localDayKey(
	datetime: string | null | undefined,
	date: string,
	timeZone?: string
): string {
	if (datetime) {
		const d = new Date(datetime);
		if (!Number.isNaN(d.getTime())) {
			// en-CA = ISO-muotoinen paiva (YYYY-MM-DD).
			return new Intl.DateTimeFormat('en-CA', {
				timeZone,
				year: 'numeric',
				month: '2-digit',
				day: '2-digit'
			}).format(d);
		}
	}
	return date;
}

/** Ryhmat avaimen mukaan, jarjestys sailyy (API palauttaa aikajarjestyksessa). */
export function groupByLocalDay<T extends { datetime?: string | null; date: string }>(
	rows: readonly T[],
	timeZone?: string
): [string, T[]][] {
	const map = new Map<string, T[]>();
	for (const f of rows) {
		const k = localDayKey(f.datetime, f.date, timeZone);
		if (!map.has(k)) map.set(k, []);
		map.get(k)!.push(f);
	}
	return [...map.entries()];
}

/** "Saturday 7 November" avaimesta, vyohykkeesta riippumatta. */
export function fmtDayKey(key: string): string {
	const d = new Date(`${key}T12:00:00Z`);
	if (Number.isNaN(d.getTime())) return key;
	return d.toLocaleDateString(LOCALE, {
		weekday: 'long',
		day: 'numeric',
		month: 'long',
		timeZone: 'UTC'
	});
}
