/** Kumppanit (26.9.2026). YKSI paikka kumppanin nimelle, linkille ja
 *  seurantatagille (saanto 6a): pinta ei kirjoita URL:ia kasin, joten
 *  ref-tagi ei voi unohtua yhdesta paikasta.
 *
 *  FPL Demon: GoalIQ:n xP-syote (/api/partner/xp) pyorittaa hanen plannerinsa
 *  ja solverinsa, sovittu X DM:ssa 26.9 (kokeilu GW10:n loppuun). Me
 *  linkitamme hanen planneriinsa ref-tagilla (ehtojen kohta 4).
 *
 *  SIJOITUS: vain maksajan xP-listan alla, EI lukitussa esikatselussa. Esikatselu
 *  on ostohetki, ja linkki tarjoaisi siina ilmaisen vaihtoehdon joka pyorii
 *  meidan luvuillamme (cos-reports/cc-reports/2026-09-26-fpldemon-kumppanuus.md).
 *
 *  URL on Demonin itse lahettama (X DM 27.9 klo 6.46), sellaisenaan: hanen
 *  analytiikkansa lukee HANEN tagejaan, joten emme keksi omia.
 *
 *  PAATTYMINEN (julkaisutarkistaja B4, saanto 6a): lause "run on these
 *  projections" on tosi vain kumppanuuden ajan. `activeUntil` sammuttaa linkin
 *  itsestaan; jatko vaatii tietoisen paivamaaramuutoksen diffissa. Jos
 *  kumppanuus loppuu aiemmin, aseta mennyt paiva ja deployaa.
 */
export interface Partner {
	id: string;
	name: string;
	url: string;
	/** ISO-paiva (UTC-keskiyo), josta alkaen linkkia ei nayteta. */
	activeUntil: string;
}

/** true = linkki saa nakya. Puuttuva tai virheellinen paiva = ei nayteta. */
export function partnerActive(p: Partner, now: number = Date.now()): boolean {
	const until = Date.parse(p.activeUntil);
	return Number.isFinite(until) && now < until;
}

export const FPL_DEMON: Partner = {
	id: 'fpldemon',
	name: 'FPL Demon',
	url: 'https://fpldemon.com/fpl/planner?utm_source=goaliq&utm_medium=social&utm_campaign=goaliq',
	// Kokeilu GW10:n loppuun; katsaus ti 10.11. (rutiini trig_015PLmRamWe8S1J9ZBJMvtGP).
	activeUntil: '2026-11-10'
};
