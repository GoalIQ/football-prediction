/**
 * Yksi lukija sille, milloin tuote-esittely (ProductIntro) on ruudulla.
 *
 * MIKSI OMA MODUULI EIKA EHTO KAHDESSA PAIKASSA: ehtoa tarvitsee kaksi
 * komponenttia vastakkaisiin suuntiin — `AppShell` renderoi esittelyn kun se
 * on tosi, ja `ToolsHome` jattaa oman ilmaisikkuna-korttinsa pois samalla
 * ehdolla, koska muuten sama tarjous ja sama "Create a free account" -nappi
 * nakyvat sivulla kahdesti (mitattu heti ensimmaisessa lokaalissa
 * renderissa 5.9.2026).
 *
 * Jos ehto olisi kirjoitettu molempiin, seuraava muutos toiseen jattaisi
 * toisen jalkeen ja duplikaatti palaisi hiljaa. Talon saanto 3.9: tee
 * vaarasta vaihtoehdosta mahdoton, ala korjaa tapausta.
 */

export function showsProductIntro(
	group: string,
	sessionResolved: boolean,
	signedIn: boolean
): boolean {
	return sessionResolved && !signedIn && group === 'week';
}
