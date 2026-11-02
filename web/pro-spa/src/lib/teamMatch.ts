/** Joukkuenimen sovitus kahden lahteen valilla (ulkoasu WP10, 2.11.2026).
 *
 * Otteluohjelma tulee football-data.orgista ("Nottingham", "Man City",
 * "Brighton Hove"), malli tuntee football-data.co.uk-nimet ("Nott'm Forest",
 * "Man City", "Brighton") ja julkinen ennusteloki pitkat muodot
 * ("Nottingham Forest", "Manchester City", "Newcastle United"). Sama ottelu on
 * siis kolmella eri nimiparilla.
 *
 * Ennen tata sovitin asui Predict.svelten sisalla ja alias sovellettiin vain
 * kysyttyyn nimeen. Kun mallin lista vaihtui lyhyisiin nimiin ("Nott'm
 * Forest"), Fixtures -> Predict lakkasi tayttamasta Forestin otteluita
 * (mitattu tuotannosta 2.11: "Nottingham" ei osu "Nott'm Forest"iin
 * kumpaankaan suuntaan). Sama vika sovelluksessa: goaliq-app 462540c7.
 *
 * SAANTO 6a KOHTA 1: yksi sovitin, jota Predictin esitaytto JA Fixtures-rivin
 * prosentti ($lib/fixtureProbs) kayttavat. Alias puretaan MOLEMMISTA
 * nimista (`teamKey`), joten kartta ei voi enaa erottaa kysyjaa ja listaa
 * toisistaan (goaliq-app b8695417: indeksi ja haku eri muunnoksella ->
 * neljalta seuralta katosi palkki).
 *
 * Puhdas moduuli: teamMatch.gate.test.ts.
 */

/** Diakriitit pois, "Utd" -> "united", seuraliitteet pois, vain [a-z0-9]. */
export function normTeam(s: string): string {
	return s
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/\butd\b/g, 'united')
		.replace(/\b(fc|afc|cf|sc|ac|as|ss|us)\b/g, '')
		.replace(/[^a-z0-9]/g, '');
}

/** Nimet joita substring-saanto ei saa kiinni: lyhenne ei sisally toiseen
 *  nimeen (PSG, HSV, Nott'm), tai osuma olisi moniselitteinen (Barca vs
 *  Espanyol de Barcelona, Deportivo vs Deportivo Alaves). Yleistetty
 *  samankaltaisuus sekoittaisi Man Cityn ja Man Unitedin, joten nama
 *  kirjataan kasin. Kartoitettu 22.8 livedatasta (football-data.orgin
 *  shortName -> mallin joukkuelista, kaikki 10 liigaa), Forest 2.11.
 *
 *  Arvo on kanoninen avain. Koska avain lasketaan molemmille puolille, alias
 *  saa osua myos listan nimeen ("Man City" -> manchestercity). */
export const NAME_ALIASES: Readonly<Record<string, string>> = {
	mancity: 'manchestercity',
	manutd: 'manchesterunited',
	manunited: 'manchesterunited',
	// 2.11.2026: fixtures "Nottingham", malli "Nott'm Forest", loki
	// "Nottingham Forest". Kaikki kolme samaan avaimeen.
	nottingham: 'nottinghamforest',
	nottmforest: 'nottinghamforest',
	spurs: 'tottenham',
	wolverhampton: 'wolves',
	psg: 'parissaintgermain',
	rclens: 'lens',
	mgladbach: 'gladbach',
	hsv: 'hamburger',
	atleti: 'atletico',
	barca: 'fcbarcelona',
	deportivo: 'lacoruna',
	az: 'azalkmaar',
	psv: 'psveindhoven',
	nec: 'nijmegen',
	sportingcp: 'splisbon',
	// Vitoria (POR, Guimaraes) ja Vitoria (BRA, Salvador): sama avain, mutta
	// eri liigan listoissa, eika kumpikaan lista sisalla toista. Koska avain
	// lasketaan molemmille puolille, BRA:n "Vitoria" osuu omaan nimeensa
	// (2.11: ennen tata yksipuolinen alias jatti BRA:n Vitorian ilman osumaa).
	vitoria: 'guimaraes',
	// 2.11.2026 (mitattu tuotannosta): football-data.orgin lyhyet nimet
	// Brasileiraossa; malli ja loki kayttavat "Atletico-MG" / "Athletico-PR".
	mineiro: 'atleticomg',
	paranaense: 'athleticopr',
	amadora: 'estrela',
	acadviseu: 'academicoviseu'
};

/** Kanoninen avain: sama funktio kysyjalle ja listalle. */
export function teamKey(name: string): string {
	const n = normTeam(name);
	return NAME_ALIASES[n] ?? n;
}

/**
 * `name` -> listan `pool` nimi, tai null.
 *
 * Jarjestys: sama merkkijono, sama avain, ja vasta sitten substring kumpaan
 * suuntaan ("Atleti" -> "Club Atletico de Madrid", "Newcastle" ->
 * "Newcastle United"). Alle 4 merkin avain ei saa substring-osumaa, ja vain
 * YKSIKASITTEINEN osuma kelpaa: muuten null eika arvausta. Vaara joukkue on
 * pahempi kuin puuttuva.
 */
export function matchTeam(name: string, pool: readonly string[]): string | null {
	if (!name) return null;
	if (pool.includes(name)) return name;
	const n = teamKey(name);
	if (!n) return null;
	const exact = pool.filter((x) => teamKey(x) === n);
	if (exact.length === 1) return exact[0];
	if (exact.length > 1) return null;
	if (n.length < 4) return null;
	const partial = pool.filter((x) => {
		const k = teamKey(x);
		return k.length >= 4 && (k.includes(n) || n.includes(k));
	});
	return partial.length === 1 ? partial[0] : null;
}
