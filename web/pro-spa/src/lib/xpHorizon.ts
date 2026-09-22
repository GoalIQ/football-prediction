/**
 * YKSI LUKIJA xP-summan ikkunalle (17.9.2026, jonorivi XP-HORIZON-ALKANUT-KIERROS).
 *
 * MIKSI: kesken kierroksen `xp_horizon_total` sisalsi jo alkaneen kierroksen
 * (live 12.9: next_gameweek 4 kesken, deadline_gameweek 5; Haaland 38.06 vs
 * pelattavien GW5-9 summa 32.65), ja jokainen pinta otsikoi summan omalla
 * kaavallaan `meta.horizon_gw`:sta ("next 6 GWs"). Backend laskee summan nyt
 * serve-timessa vain kierroksista >= `meta.horizon_total_from` ja julkaisee
 * `meta.horizon_total_gw`. Otsikon luvun on tultava SAMASTA metasta kuin
 * summan, muuten lause ja luku ovat eri lahteesta (muisti:
 * lause-ja-luku-eri-lahteesta).
 *
 * SOPIMUS (backend, sama paiva):
 *   meta.horizon_gw            = GW-sarakkeiden maara riveissa (ennallaan)
 *   meta.horizon_total_from    = ensimmainen kierros summassa (deadline-kierros)
 *   meta.horizon_total_gw      = montako kierrosta summattiin
 *   players[].xp_horizon_total = summa vain kierroksilta >= horizon_total_from
 *   players[].gameweeks[]      = ennallaan (voi alkaa jo alkaneesta kierroksesta)
 *
 * FAIL-CLOSED: jos `horizon_total_gw` puuttuu (vanha API), lukumaara on
 * `horizon_gw` (tosi: summa kattaa silloin kaikki rivit), mutta
 * `actionableOnly` on false eika yksikaan teksti sano "next": alkanutta
 * kierrosta ei voi sulkea pois. Ikkunan alkua EI keksita `gw`- tai
 * `deadline_gameweek`-kentasta: vanhassa API:ssa summa alkaa riveilla
 * ensimmaisesta kierroksesta, joka on `next_gameweek` (mitattu 5.9: Haaland
 * 31.21 = GW3..GW8 kun deadline-GW oli 4). Jos sekin puuttuu, ikkunalla ei ole
 * alkua ja teksti sanoo vain lukumaaran. Ei `?? 6` -oletusta missaan: numero
 * jota API ei antanut on keksitty numero.
 *
 * Kaikki "next {n} GWs" / "GW{a}-GW{b}" -otsikot, sarakenimet ja jakokorttien
 * alaotsikot lukevat taman. Lahdeportti (`xpHorizon.gate.test.ts`) kaataa
 * kutsupaikan joka lukee `horizon_gw`:ta suoraan.
 */

export interface HorizonMeta {
	/** GW-sarakkeiden maara riveissa. Vanha API: myos summan pituus. */
	horizon_gw?: number | null;
	/** Ensimmainen kierros `xp_horizon_total`issa (uusi API). */
	horizon_total_from?: number | null;
	/** Montako kierrosta `xp_horizon_total`issa on (uusi API). */
	horizon_total_gw?: number | null;
	/** Rivien ensimmainen kierros. Vanhassa API:ssa summan alku. */
	next_gameweek?: number | null;
}

export interface XpHorizon {
	/** Ensimmainen summattu kierros, tai null kun API ei sanonut. */
	from: number | null;
	/** Viimeinen summattu kierros, tai null. */
	to: number | null;
	/** Summattujen kierrosten maara, tai null kun API ei sanonut. */
	count: number | null;
	/** GW-sarakkeiden maara riveissa (`horizon_gw`). Eri asia kuin `count`
	 *  kesken kierroksen: rivit voivat alkaa jo alkaneesta kierroksesta. */
	rows: number | null;
	/** true vain kun API julisti summan alkavan TIEDETYSTA kierroksesta
	 *  (`horizon_total_gw` JA `horizon_total_from`). false = summa voi
	 *  sisaltaa jo alkaneen kierroksen, eika mikaan teksti sano "next". */
	actionableOnly: boolean;
	/** "GW5-GW9" / "GW38" / null. */
	range: string | null;
	/** Substantiivi otsikkoon: "next 5 GWs" / "GW4-GW9" / "6-GW horizon" /
	 *  "model horizon". */
	label: string;
	/** "over the next 5 GWs" / "over GW4-GW9" / "over the 6-GW horizon" /
	 *  "over the model horizon". */
	over: string;
	/** "5-GW horizon" / "model horizon". Ei koskaan "next": hold-copyn portti
	 *  (tests/test_hold_copy_scope.py) vaatii taman muodon RateTeamissa ja
	 *  FitCheckerissa, ja se kestaa myos arvon 1. */
	span: string;
	/** "5 GWs" / "1 GW" / "horizon". Sarakeotsikoihin ja korttien nimilappuihin. */
	gws: string;
	/** VALMIS sarakeotsikon selite: "Sum of expected points, next 5 GWs".
	 *  Kutsupaikka ei kokoa tata itse (18.9, 17.9 loydetty P1-2): kun otsikko on lukijan
	 *  palauttama merkkijono, sarakkeista laskettua valia ei voi pujottaa
	 *  siihen vaihtamalla yhta lauseketta. */
	totalTitle: string;
	/** VALMIS selitelause: "the sum of projected points over the next 5 GWs
	 *  (GW5-GW9)". Myos ikkunan ja sen suluissa olevan tarkenteen valinta on
	 *  lukijassa, ei kutsupaikan ternaarissa. */
	totalHelp: string;
}

/** Julkinen vaite summasta: luku JA ikkuna samasta lukijasta.
 *
 *  MIKSI OMA FUNKTIO (18.9, 17.9 loydetty P1-1): jakokortin mallirivi ja sivulauseen
 *  "38.1 xP projected over the next 5 GWs" koottiin kutsupaikalla luvusta ja
 *  `over`-kentasta. Silloin `over` on vaihdettavissa yhdella muokkauksella
 *  muotoon joka laskee ikkunan pelaajan `gameweeks`-listan pituudesta — ja
 *  jakokortti on KUVA, jota ei voi korjata jalkikateen. Nyt kutsupaikka saa
 *  valmiin vaitteen eika nae ikkunaa erillisena palana. */
export interface XpTotalClaim {
	/** "38.1 xP" — summan luku ilman ikkunaa (lihavoitava osa). */
	value: string;
	/** "projected over the next 5 GWs" — ikkuna ilman lukua. */
	tail: string;
	/** "38.1 xP projected over the next 5 GWs" — koko vaite yhtena rivina
	 *  (jakokortin mallirivi). */
	text: string;
}

function gwInt(v: unknown): number | null {
	return typeof v === 'number' && Number.isInteger(v) && v >= 0 ? v : null;
}

export function xpHorizon(meta: HorizonMeta | null | undefined): XpHorizon {
	const m = meta ?? {};
	const rows = gwInt(m.horizon_gw);
	const totalGw = gwInt(m.horizon_total_gw);
	let from: number | null;
	let count: number | null;
	let actionableOnly: boolean;
	if (totalGw != null) {
		count = totalGw;
		const f = gwInt(m.horizon_total_from);
		from = f != null && f >= 1 ? f : null;
		/* ALKU ON LUPA (18.9, julkaisutarkistajan B3). Ennen: `actionableOnly
		   = true` heti kun `horizon_total_gw` on annettu. Mitattu 18.9
		   tuotannosta: `/api/fantasy/xp?league=spl` palauttaa
		   `deadline_gameweek: null`, `next_gameweek: 8`, ja backendin
		   `actionable_gameweek` putoaa ilman deadlinea takaisin
		   `next_gameweek`iin. Backend julkaisee siksi `horizon_total_from`in
		   VAIN deadlinesta (`fpl_xp.horizon_total_licence`), ja sen
		   puuttuminen ON se signaali: lukumaara on tosi, "next" ei ole. */
		actionableOnly = from != null;
	} else {
		actionableOnly = false;
		count = rows;
		const n = gwInt(m.next_gameweek);
		from = n != null && n >= 1 ? n : null;
	}
	const to = from != null && count != null && count >= 1 ? from + count - 1 : null;
	const range =
		from != null && to != null ? (to === from ? `GW${from}` : `GW${from}-GW${to}`) : null;
	const gws = count == null ? 'horizon' : `${count} GW${count === 1 ? '' : 's'}`;
	const span = count == null ? 'model horizon' : `${count}-GW horizon`;
	let label: string;
	let over: string;
	if (actionableOnly && count != null) {
		if (count === 0) {
			/* 18.9 (julkaisutarkistajan "MUUT"): sama lyhenne kuin muualla
			   lukijassa ("next 5 GWs", "6-GW horizon"). Sama lukija tuotti
			   ennen seka lyhenteen etta tayssanan. Mobiilissa sama muutos
			   (lib/i18n/en.ts: fantasy.xp_horizon.none_left). */
			label = 'no GWs left';
			over = 'with no GWs left';
		} else {
			label = count === 1 ? 'next GW' : `next ${gws}`;
			over = `over the ${label}`;
		}
	} else if (range != null) {
		label = range;
		over = `over ${range}`;
	} else {
		label = span;
		over = `over the ${span}`;
	}
	const totalTitle = `Sum of expected points, ${label}`;
	const totalHelp = `the sum of projected points ${over} (${
		actionableOnly ? (range ?? gws) : gws
	})`;
	return {
		from,
		to,
		count,
		rows,
		actionableOnly,
		range,
		label,
		over,
		span,
		gws,
		totalTitle,
		totalHelp
	};
}

/** Ikkuna jonka otsakerivi nayttaa sulkeissa ("Next 6 GW (GW6-GW11)"), tai
 *  null kun API ei julistanut summan alkua (vanha API, ei deadlinea) tai
 *  summa kattaa nolla kierrosta.
 *
 *  MIKSI FUNKTIO (22.9.2026): kentan otsikko "Model's XI from your 15, picked
 *  on GW6-GW11 xP" vaittaa saman ikkunan kuin otsakerivi. Kun molemmat
 *  lukevat taman, ne eivat voi nayttaa eri valia, eika kentta voi nayttaa
 *  valia jota otsakerivi ei nayta. */
export function declaredRange(h: XpHorizon | null | undefined): string | null {
	return h != null && h.actionableOnly && h.range != null ? h.range : null;
}

export function xpTotalClaim(
	meta: HorizonMeta | null | undefined,
	total: number
): XpTotalClaim {
	const value = `${total.toFixed(1)} xP`;
	const tail = `projected ${xpHorizon(meta).over}`;
	return { value, tail, text: `${value} ${tail}` };
}
