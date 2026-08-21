/**
 * WHY-THIS-PICK-ajurien nayttonimet + rivimuoto. Yksi lahde kahdelle pinnalle
 * (WhyThisPick-lohko sivulla + jaettava pelaajakortti): SHARE-CARD-WHY
 * toi samat chipit korttiin, ja komponenttiin haudattu kopio olisi
 * antanut labelien eriytya hiljaa ([[kuratoitu-lista-jaettuun-moduuliin]]).
 *
 * 20.8 SHARE-CARD-WHY-EMPHASIS (Rowanin palaute jaettuun korttiin: *"making
 * the 2-3 biggest reasons stand out slightly more, so you can understand why
 * the model likes the player within a second or two"*): ajuri ei ole enaa
 * pelkka tagi vaan rivi jolla on todisteluku. Luku EI synny taalla vaan
 * backendissa (`why.driver_facts`, src/models/fpl_xp.py) — jos johdos
 * kirjoitettaisiin erikseen Svelteen ja React Nativeen, sivu ja appi voisivat
 * nayttaa saman ajurin eri lukuna.
 *
 * Mobiilin vastine on `components/whyDrivers.ts` goaliq-appissa. Nama kaksi
 * on pidettava samoina; ne eivat voi jakaa moduulia repojen yli.
 */
export const WHY_DRIVER_LABEL: Record<string, string> = {
	minutes: 'Minutes',
	attacking_output: 'Attacking output',
	fixtures: 'Fixtures',
	clean_sheets: 'Clean sheets',
	set_pieces: 'Set pieces',
	bonus: 'Bonus',
	price: 'Price',
	differential: 'Differential'
};

export interface WhyDriverRow {
	/** Ajuriavain (`minutes`, `clean_sheets`, ...) — listan avaimena. */
	key: string;
	label: string;
	/** Todisteluku backendilta. Puuttuu kun rivi ei kanna sita lukua. */
	value?: string;
}

/**
 * `why` -> renderoitavat ajuririvit. EI jarjesta eika rajaa: backend on jo
 * rajannut kolmeen ja jarjestys on lauseen kirjoittajan oma nakemys siita
 * mika on isoin. Toinen slice taalla ajautuisi ennen pitkaa eri lukuun kuin
 * backendin oma raja.
 *
 * Vanha deployattu backend palauttaa ajurit ilman `driver_facts`ia, jolloin
 * rivit renderoityvat pelkkina nimina — sama sisalto kuin ennen tata muutosta.
 */
export function whyDriverRows(
	why: { drivers?: string[]; driver_facts?: Record<string, string> } | undefined
): WhyDriverRow[] {
	if (!why?.drivers?.length) return [];
	return why.drivers.map((key) => ({
		key,
		label: WHY_DRIVER_LABEL[key] ?? key,
		value: why.driver_facts?.[key]
	}));
}
