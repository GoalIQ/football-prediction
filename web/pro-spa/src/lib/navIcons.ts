/**
 * Alapalkin kuvakkeet ryhmittain (22.9.2026, web-audit T2 / A3).
 *
 * A2 saanto 1: alapalkin kohdassa on kuvake JA teksti. Kuvake on 24x24
 * viivapiirros yhdella polulla, joten se noudattaa tekstin varia
 * (`currentColor`) eika tuo uutta varia palettiin.
 *
 * Avaimet ovat rekisterin ryhma-id:t. Portti `ia.gate.test.ts` kaataa jos
 * ryhmalle ei ole kuvaketta: uusi ryhma ei voi ilmestya alapalkkiin
 * tyhjalla ruudulla.
 */
export const NAV_ICONS: Record<string, string> = {
	// kalenteri + deadline-piste: "mita teen ennen deadlinea"
	week: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4M12 14.5a1.5 1.5 0 1 0 0.01 0',
	// pelipaita: oma joukkue
	team: 'M8 3l-5 3 2 4 2-1v12h10V9l2 1 2-4-5-3c-.5 1.7-2 3-4 3s-3.5-1.3-4-3z',
	// hahmo: pelaajat
	players: 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.6-7 8-7s8 3 8 7',
	// kilpi: joukkueet (RSL:n Teams, 23.9)
	shield: 'M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z',
	// kentta keskiympyralla: ottelut
	matches: 'M3 5h18v14H3zM12 5v14M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z'
};
