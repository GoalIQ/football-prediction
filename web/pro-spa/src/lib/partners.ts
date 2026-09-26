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
 *  URL vaihdetaan tahan kun Demon lahettaa haluamansa linkin.
 */
export interface Partner {
	id: string;
	name: string;
	url: string;
}

export const FPL_DEMON: Partner = {
	id: 'fpldemon',
	name: 'FPL Demon',
	url: 'https://fpldemon.com/fpl/planner?utm_source=goaliq&utm_medium=partner&ref=goaliq'
};
