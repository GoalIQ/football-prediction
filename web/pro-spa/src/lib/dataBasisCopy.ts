/**
 * data_basis-tekstien YKSI LAHDE (saanto 6a mekanismi 1).
 *
 * MITATTU 30.9 (yoajo, QUEUE MOBIILI-DATAPOHJA-LABEL): PlayerCard.svelte
 * korjasi 29.9 (fp b72c46099) oman `DATA_BASIS_LABEL`-sanakirjansa
 * no_history-selitteen ("no PL minutes this season or last") mutta
 * XpTable.svelte piti oman erillisen kopionsa, jossa vanha epatosi teksti
 * ("No PL data yet" / "No Premier League data for this player yet") jai
 * elamaan. Sama fakta kahdessa paikassa ajautuu erilleen aina kun toista
 * korjataan eika muisteta toista. Tama tiedosto on se yksi lukija: molemmat
 * komponentit tuovat samat vakiot eivatka voi enaa nayttaa eri tekstia
 * samalle data_basis-arvolle.
 *
 * `no_history` tarkoittaa nolla PL-minuuttia KULUVALLA + PAINOTETULLA
 * VIIME kaudella (fpl_xp.data_basis, carry_prev_season). Se EI tarkoita
 * etta pelaajalla ei olisi PL-minuutteja lainkaan aiemmilta kausilta
 * (esim. Hullin Dowell 905 min 2021/22) - siksi teksti rajataan
 * "this season or last", ei vaiteta "no PL data" absoluuttisena.
 */

export type DataBasis = 'pl_history' | 'limited_history' | 'no_history';

/** Kokonainen lause pelaajakortin "Goal and assist rates: ..." -riville. */
export const DATA_BASIS_LABEL: Record<DataBasis, string> = {
	pl_history: "based on the player's own PL minutes",
	limited_history: 'thin PL sample, the position average carries most of the weight',
	no_history: 'no PL minutes this season or last, position average only'
};

/** Lyhyt tagi listariveille (XpTable). Ei arvoa pl_history:lle — sille ei
 *  nayteta tagia lainkaan (rehellinen oletus: taysi oma data ei tarvitse
 *  varoitusta). */
export const DATA_BASIS_TAG: Record<Exclude<DataBasis, 'pl_history'>, string> = {
	limited_history: 'Limited data',
	no_history: 'No PL minutes this season or last'
};

/** Hover/title-selite listariveille. */
export const DATA_BASIS_TOOLTIP: Record<Exclude<DataBasis, 'pl_history'>, string> = {
	limited_history:
		'The model has little Premier League history for this player yet, so treat this projection as less certain.',
	no_history:
		'No Premier League minutes for this player this season or last, this is a position-based estimate.'
};
