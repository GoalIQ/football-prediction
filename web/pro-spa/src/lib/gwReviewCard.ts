/**
 * lib/gwReviewCard.ts — Gameweek review -jakokortin sisalto (yksi lukija,
 * web + mobiili; mobiilin goaliq-app/lib/gwReviewCard.ts on sama tiedosto).
 *
 * 6.9.2026 (Villen tilaus): "saisko tohon this week gameweek reviewii
 * jako-ominaisuuden. toi vois olla aina hyva gw review postaus."
 *
 * Kortti on olemassa oleva LISTAKORTTI (sama renderoija kuin xP-listalla):
 * avaava XI rivi rivilta, deadline-freezen xP keskella ja FPL:n pisteet
 * oikealla. Uutta piirtajaa ei tarvita, ja kortti perii listakortin vahdit
 * (vahintaan 3 rivia, alatunniste lahteineen).
 *
 * REHELLISYYS, sama kuin paneelissa (GwReview.svelte / GwReview.tsx):
 *  - rivit jarjestetaan HUONOIMMASTA erosta parhaaseen NAYTETYILLA luvuilla,
 *    ja luvut ovat kerroinpainotettuja kuten kortin summa. Kortti on
 *    JOUKKUEEN kierros; mallin virhe pelaajasta sanotaan paneelissa,
 *    jossa luvut ovat kertoimettomia (portin 9.-10. kierros).
 *  - `provisional` ja kattavuus ("12 of 15 compared") menevat alaotsikkoon,
 *    eivat tooltippiin: kuva irtoaa sovelluksesta.
 *  - luvut tulevat endpointilta sellaisinaan. Kapteenin rivi on jo
 *    tuplattu backendissa (projected ja actual kertaa multiplier), joten
 *    kortti merkitsee sen C-badgella eika laske mitaan.
 */

export interface ReviewCardPlayer {
  web_name: string;
  team_short: string;
  pos: string;
  projected: number;
  actual: number;
  diff: number;
  multiplier: number;
  in_xi: boolean;
  is_captain: boolean;
  /** Kertoimeton ero (B2): mallin virhe on pelaajan oma, ei
   *  kapteeninauhan. Vanha payload ilman tata kaytaa `diff`ia. */
  diff_raw?: number;
  /** Kertoimettomat luvut riville. Rivi nayttaa mallin virheen pelaajasta;
   *  kerroin on C/TC-badgessa ja alatunnisteessa. */
  projected_raw?: number;
  actual_raw?: number;
}

export interface ReviewCardInput {
  meta: {
    reviewed_gw: number | null;
    provisional?: boolean;
    players_compared?: number;
    /** Kaikki pickit (yleensa 15). Kattavuuden NIMITTAJA, ei kovakoodattu. */
    total_picks?: number;
    /** FPL:n `active_chip`. Bench boostilla rivit EIVAT ole avaava XI. */
    chip?: string | null;
    /** Montako autosubia FPL teki. Autosubin jalkeen `multiplier > 0`
     *  -joukko sisaltaa penkilta nousseen, jolloin "starting XI" on vaara. */
    auto_subs?: number;
    /** Freeze-hetki ja kierroksen deadline ISO-muodossa. Vaite freezen
     *  ajoituksesta tehdaan naista, ei rakenteesta. */
    frozen_at?: string | null;
    deadline?: string | null;
    /** FPL:n OMA kierrospistemaara (`entry_history.points`). 🔴 BRUTTO:
     *  siirtorangaistus EI ole siina (verifioitu FPL:n API:sta 7.9). */
    fpl_points?: number | null;
    /** `fpl_points` miinus siirtorangaistus = se luku jonka lukija nakee
     *  omalta FPL-sivultaan. Kortti nayttaa TAMAN. */
    fpl_points_net?: number | null;
    /** Siirtorangaistus. Kortti ei sano sita (tila on tiukka), mutta se
     *  kuuluu rajapintaan koska `fpl_points_net` johdetaan siita. */
    transfer_cost?: number | null;
  };
  review: {
    projected: number | null;
    actual: number | null;
    diff: number | null;
    players: ReviewCardPlayer[];
  } | null;
}

export interface ReviewCardRow {
  rank: number;
  name: string;
  tag: string;
  team: string;
  badges?: string[];
  mid: string;
  value: string;
}

export interface ReviewCardSpec {
  title: string;
  subtitle: string;
  nameLabel: string;
  midLabel: string;
  valueLabel: string;
  rows: ReviewCardRow[];
  heroFirstRow: boolean;
  footNote: string;
  footNote2: string;
  fileName: string;
}

export const REVIEW_CARD_MIN_ROWS = 3;

/** Alaotsikon merkkibudjetti. Mitattu `FantasyListShareCard.tsx`:n omasta
 *  kommentista: pisin alaotsikko (~88 merkkia) ei mahdu 10 px:lla, ja
 *  renderoija kutistaa yhdelle riville ja katkaisee HANNAN. Ylipitka rivi
 *  ei siis nayta huonolta vaan PUDOTTAA tarkistettavan luvun. */
export const SUBTITLE_BUDGET = 88;

const sign = (n: number) => (n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1));

/**
 * 🔴 PORTIN KAKSI KIERROSTA (6.9 loydokset A2-A7, 7.9 loydokset U1-U5).
 * Yhteinen nimittaja molemmissa: kortti irtoaa sovelluksesta, joten jokainen
 * sen vaite on JOHDETTAVA payloadista - rakenteellinen oletus on vaite jota
 * kortti ei voi mitata.
 *
 *  U1  "72 pts ... points from FPL" oli tarkistamaton: lukijan oma FPL-sovellus
 *      sanoi GW3:sta 58. Mitattu 7.9: kaikki 10 ottelua olivat
 *      `finished_provisional` mutta EIVAT `finished`, ja live-syotteessa oli 15
 *      kerroinpainotettua bonuspistetta joita `entry_history` ei ollut viela
 *      kirjoittanut (72 - 15 = 57, FPL 58). Ero ei ole virhe vaan ikkuna, ja
 *      kortti sanoo sen nyt itse: kesken olevalla kierroksella luku on
 *      live-syotteesta ja bonus on vahvistamatta.
 *  U2  Paneeli ja kortti antoivat eri erotuksen samasta kierroksesta (+0.9 vs
 *      +0.8) samassa otsikkorivissa. Molemmat lukevat nyt taman funktion.
 *  U3  Kattavuuslause oli KUOLLUT HAARA: backend maarittelee
 *      `in_xi := multiplier > 0`, joten rivit ja "aloittajat" olivat aina sama
 *      joukko. Oikea aukko (`players_compared` 14, pickkeja 15) oli pudonnut
 *      kortilta kokonaan. Nyt kattavuus lasketaan pickeista, ja nimittaja
 *      tulee payloadista.
 *  U4  Bench boostilla jokaisella 15:sta on multiplier > 0 -> "starting XI"
 *      olisi 15 rivin otsikkona vaara. Otsikko johdetaan riveista ja chipista.
 *  U5  Kapteenin kerroin luettiin `is_captain`-lipusta. Jos kapteeni ei
 *      pelannut, FPL siirtaa kertoimen varakapteenille MUTTA lippu jaa
 *      pelaamattomalle -> tuplattu rivi ilman merkintaa ja ilman lausetta.
 *      Kerroin luetaan nyt riveilta (suurin multiplier), eli silta jolla se
 *      oikeasti on.
 */

/** Alaotsikon ja alatunnisteen palaset. Vietu ulos jotta PANEELI voi kayttaa
 *  samaa erotusta kuin kortti (U2): kaksi pintaa samasta kierroksesta ei saa
 *  antaa eri lukua. */
export function reviewTotals(rows: { projected: number; actual: number }[]) {
  const actual = rows.reduce((n, p) => n + p.actual, 0);
  // 🔴 E1 (portin 6. kierros): PYORISTYSSAANTO EI RIITTANYT, KOSKA SYOTE OLI
  // ERI. Liukuluvun yhteenlasku ei ole assosiatiivinen, ja kolme pintaa
  // summasi samat 11 lukua kolmessa eri jarjestyksessa (backend picks-,
  // paneeli payload-, kortti diff-jarjestyksessa). Mitattu tuotannon GW3:sta
  // 7.9: sama joukko antoi 71.15 ja 71.14999999999999, eli "71.2" ja "71.1"
  // SAMASSA nakymassa. Esiintymistaajuus 11 rivilla: 3,7 %.
  //
  // Rivien projektio on kahden desimaalin tarkkuudella, joten summataan
  // SADASOSINA kokonaislukuina: silloin jarjestys ei voi muuttaa tulosta.
  // 🔴 Portin 10. kierros: summataan se MITA NAKYY. Sadasosasumma teki
  // summasta jarjestysriippumattoman (E1) mutta jatti xP-sarakkeen ja
  // alaotsikon eri luvuiksi: mitattu drift 0,6 ja **etumerkin kaantyminen**
  // (`62 pts vs 61.9 xP (+0.1)` kun sarakkeet antavat -0,2). Rivit
  // renderoidaan yhdella desimaalilla, joten summa lasketaan siita.
  // Kymmenesosina kokonaislukuina, jotta jarjestysriippumattomuus sailyy.
  // Ja summataan TASAN se merkkijono jonka rivi renderoi. `toFixed(1)` ja
  // `Math.round(x*10)/10` eroavat tasatilanteessa (6.55 -> "6.5" vs 6.6),
  // eli sarake ja summa olisivat taas eri lukijaa - sama vikaluokka kuin
  // D1, nyt JS:n sisalla. Kymmenesosina kokonaislukuina, jotta
  // jarjestysriippumattomuus sailyy.
  const tenths = rows.reduce(
    (n, p) => n + Math.round(Number(p.projected.toFixed(1)) * 10), 0);
  const projectedText = (tenths / 10).toFixed(1);
  // Erotus NAYTETYISTA luvuista: pyoristamaton 0.85 nayttaisi "+0.9" vaikka
  // kortilla lukee 71.2 ja 72.
  // `rows` mukana, jotta paneelin lause ja kortti puhuvat samasta joukosta
  // (D2: kaksi eri mittaria oli saanut saman sanamuodon).
  return { actual, projectedText, diff: actual - Number(projectedText), rows: rows.length };
}

export function gwReviewCardSpec(data: ReviewCardInput): ReviewCardSpec | null {
  const rv = data.review;
  const gw = data.meta.reviewed_gw;
  if (!rv || gw == null) return null;
  // Vain pelanneet (multiplier > 0). Penkin rivi olisi 0.0 -> 0, mika
  // lukisi "malli ennusti nollan ja osui".
  const xi = rv.players.filter((p) => p.in_xi && p.multiplier > 0);
  if (xi.length < REVIEW_CARD_MIN_ROWS) return null;
  // 🔴 B2 (7. kierros): jarjestys KERTOIMETTOMASTA erosta. `diff` on
  // kerroinpainotettu, joten kapteeninauha paatti mika oli mallin pahin
  // kutsu - ja repon oma saanto (`fpl_rate_team.last_finished_block`) sanoo
  // painvastoin. Mitattu GW3: Haalandin raakaero +1.08, x3 = +3.24.
  // Jarjestys ja luvut SAMASTA suureesta (portin 9. kierros): kortin oma
  // summa on kerroinpainotettu, joten myos rivit ja niiden jarjestys ovat.
  // Silloin lukija voi laskea sarakkeen ja paatya alaotsikon lukuun.
  // Lajitteluavain NAYTETYISTA luvuista: 2 desimaalin `diff` tuotti 96
  // tapausta 200 000:sta joissa rivin i+1 naytetty ero oli pienempi kuin
  // rivin i. Jarjestysvaite on tarkistettava sarakkeista.
  const naytettyEro = (p: ReviewCardPlayer) =>
    p.actual - Number(p.projected.toFixed(1));
  // 🔴 VILLEN PAATOS 7.9.2026: "pida biggest gap".
  //
  // 9. kierroksella alaotsikko sanoi 'biggest gap first', ja 10. kierros
  // totesi sen EPATODEKSI: jarjestys oli nouseva (negatiivisin ensin), joten
  // suurin ero oli rivilla 11 jokaisella ylisuoritusviikolla ja kortin oma
  // sarake kumosi alaotsikon. Silloin heikensin SANAT ('worst gap first')
  // jotta ne vastaisivat jarjestysta.
  //
  // Ville pitaa sanat. Silloin JARJESTYKSEN on vastattava niita, ei toisin
  // pain: lajitellaan itseisarvoltaan suurimmasta erosta. Nyt rivi 1 on se
  // jossa malli osui huonoimmin - kumpaan suuntaan tahansa - ja lukija voi
  // tarkistaa sen kortin omista sarakkeista (|PTS - XP| laskee alaspain).
  //
  // Lajitteluavain on yha NAYTETYISTA luvuista: 2 desimaalin `diff` tuotti
  // 96 tapausta 200 000:sta joissa rivin i+1 naytetty ero oli pienempi kuin
  // rivin i.
  const ordered = [...xi].sort(
    (a, b) =>
      Math.abs(naytettyEro(b)) - Math.abs(naytettyEro(a)) ||
      naytettyEro(a) - naytettyEro(b) ||
      a.web_name.localeCompare(b.web_name, 'en')  // kiintea lokaali: kortti on
      // jaettava kuva, ja diakriittiset nimet (Odegaard, Nunez) jarjestyivat
      // eri tavalla es- ja en-laitteella
  );
  const maxMult = ordered.reduce((m, p) => Math.max(m, p.multiplier), 1);
  const rows: ReviewCardRow[] = ordered.map((p, i) => ({
    rank: i + 1,
    name: p.web_name,
    tag: p.pos,
    team: p.team_short,
    // U5: merkinta sille jolla kerroin OIKEASTI on, ei lipulle.
    badges:
      p.multiplier >= 3 ? ['TC'] : p.multiplier >= 2 ? ['C'] : undefined,
    // Kerroinpainotetut luvut: sarake summautuu alaotsikon lukuun.
    // C/TC-badge kertoo miksi kapteenin rivi on muita suurempi.
    mid: p.projected.toFixed(1),
    value: String(p.actual),
  }));

  const { actual, projectedText, diff } = reviewTotals(ordered);

  // 🔴 PORTIN 4. KIERROS (C1-C7). Kolme sitkeaa vikaluokkaa:
  //
  //  C1  FPL:n luku sanottiin vain KESKEN olevalla kierroksella. Lopullisella
  //      kierroksella ero vaikeni kokonaan - eli tasan siina tilassa jossa
  //      lukija luottaa lukuun eniten. Luku sanotaan nyt aina kun se eroaa;
  //      `so far` on ainoa asia jonka `provisional` vaihtaa.
  //  C2  Selittava lause nimesi mekanismin joka EI TASMAA: mitattu 7.9
  //      XI-summa 72, kerroinpainotettu bonus 15, siis ilman bonusta 57,
  //      mutta `entry_history.points` = 58. Lukija joka laskee 58 + 15 ei
  //      paase 72:een. Ja `entry_history.points` on BRUTTO (verifioitu
  //      FPL:n API:sta 7.9), joten -4:n viikolla ero ei selity bonuksella. Emme siis nimea
  //      syyta - sanomme vain kumpi luku on kumpi ja mista se on.
  //  C7  Nimittaja oli fail-open: ilman `total_picks`ia kortti vaitti
  //      "bench boost", ja `rows > odotettu` tuotti "15 of 11". Molemmat
  //      fail-closed nyt.
  const chip = (data.meta.chip || '').toLowerCase();
  const picks = data.meta.total_picks;
  const odotettu = chip === 'bboost' ? picks : 11;
  // B4: autosubin jalkeen rivit sisaltavat penkilta nousseen -> ei "XI".
  const autoSubs = data.meta.auto_subs ?? 0;
  const label =
    odotettu == null || rows.length > odotettu || autoSubs > 0
      ? `${rows.length} rows`
      : rows.length === odotettu
        ? chip === 'bboost'
          ? 'bench boost'
          : 'starting XI'
        : `${rows.length}/${odotettu} rows`;

  const kesken = !!data.meta.provisional;
  // B1 (10. kierros): NETTO, koska se on lukijan oma luku.
  const fpl = data.meta.fpl_points_net ?? data.meta.fpl_points;
  const compared = data.meta.players_compared;

  // C3: BUDJETTI. `FantasyListShareCard` kutistaa alaotsikon yhdelle riville
  // (`numberOfLines 1`, `minimumFontScale 0.64`) ja katkaisee HANNAN - eli
  // juuri tarkistettavan luvun. Osat ovat siksi PRIORITEETTIJARJESTYKSESSA
  // ja vahiten tarkeat pudotetaan kunnes rivi mahtuu. Budjetti mitattu
  // renderoijan omasta kommentista.
  const pakolliset = [
    `${label}: ${actual}${kesken ? ' live pts' : ' pts'} vs ` +
      `${projectedText} xP (${sign(diff)})`,
  ];
  if (fpl != null && fpl !== actual) {
    // `so far` oli redundantti: liveys on jo sanottu omassa luvussa
    // ("live pts"), ja se maksoi 7 merkkia joka live-tilassa - eli tasan
    // sen tilan jossa kattavuus putosi budjettiin.
    pakolliset.push(`FPL ${fpl}`);
  }
  // 🔴 B5 (10. kierros): `includes('counted')` yhdisti kaksi eri
  // nimittajaa. Label puhuu RIVEISTA (11 vs odotettu XI), kattavuus
  // PICKEISTA (14/15) - "11 rows counted" ei kerro kattavuudesta mitaan, ja
  // silti se vaiensi sen. Paneeli sanoi "14 of 15 picks compared" ja kortti
  // vaikeni: C4:n regressio.
  const labelKertooKattavuuden =
    picks != null && label === `${rows.length}/${picks} rows`;

  // C4: kattavuus takaisin kortille. Paneeli sanoi "14 of 15" ja kortti
  // vaikeni - sama vaite kahdella pinnalla, toinen hiljaa.
  // F4 (12. kierros): kattavuus on VARAUS eika koriste, joten se ei saa
  // pudota budjettiin. Vain jarjestysselite on valinnainen, ja se on
  // viimeisena pudotettava - mutta mitattuna se ei putoa yhdessakaan
  // realistisessa tilassa.
  if (
    !labelKertooKattavuuden &&
    compared != null &&
    picks != null &&
    compared < picks
  ) {
    pakolliset.push(`${compared}/${picks} picks`);
  }

  const valinnaiset: string[] = [];
  // 🔴 B3 (7. kierros): jarjestysselite PUTOSI budjettiin elavalla datalla
  // (73 + 18 = 91 > 88), jolloin julkinen kuva jai 11 rivin listaksi jossa
  // on rank-sarake 1-11 eika mikaan sano miksi. Rank on jarjestysvaite ja
  // sen selite on tarkeampi kuin kattavuus - siis ensin, ja lyhyena.
  //
  // 🔴 9. kierros: sanamuoto ei ole 'worst call first'. Jarjestys on
  // kerroinpainotettu, ja kapteeninauha on KAYTTAJAN valinta - "mallin
  // pahin kutsu" olisi vaite jota tama jarjestys ei mittaa. Se vaite
  // tehdaan paneelissa, kertoimettomista luvuista.
  //
  // 🔴 Villen paatos 7.9: 'biggest gap first', ja jarjestys lajitellaan
  // vastaamaan sita (ks. `ordered` ylla). Vaite on tarkistettavissa kortin
  // omista sarakkeista: |PTS - XP| laskee alaspain.
  valinnaiset.push('biggest gap first');


  // R2 (5. kierros): FPL:n luku on pakollisten VIIMEINEN, eli jos pakolliset
  // ylittavat budjetin, renderoija katkaisee tasan tarkistettavan luvun.
  // Testi mittaa pakolliset erikseen; tama on sen ajonaikainen pari.
  let osat = [...pakolliset, ...valinnaiset];
  while (osat.join(', ').length > SUBTITLE_BUDGET && osat.length > pakolliset.length) {
    osat = osat.slice(0, -1);
  }
  const parts = osat;

  // U5: kerroinlause suurimmasta kertoimesta riveilla.
  const multNote =
    maxMult >= 3 ? ', captain tripled' : maxMult >= 2 ? ', captain doubled' : '';

  // A3 + U-seuranta: freeze-vaite vain kun payload todistaa sen.
  const frozenNote = freezeNote(gw, data.meta.frozen_at, data.meta.deadline);

  return {
    title: `GW${gw} REVIEW`,
    subtitle: parts.join(', '),
    nameLabel: 'PLAYER',
    midLabel: 'XP',
    valueLabel: 'PTS',
    rows,
    // A6: rivi 1 on huonoin ero, ei karki - korostus pois. (Perustelu
    // paivitetty 10. kierroksella: rivi 1 ei enaa vaita olevansa mallin
    // pahin kutsu, mutta se ei ole karki silloinkaan.)
    heroFirstRow: false,
    // B2: lahde on alaotsikossa, joten alatunniste ei toista sita.
    footNote: `${frozenNote}${multNote}`,
    footNote2: 'not betting advice',
    fileName: `goaliq_gw${gw}_review.png`,
  };
}

/** Freeze-vaite payloadista. Ilman kumpaakin aikaleimaa kortti sanoo vain
 *  MISTA luku on, ei milloin se lukittiin. */
export function freezeNote(
  gw: number,
  frozenAt: string | null | undefined,
  deadline: string | null | undefined
): string {
  const f = frozenAt ? Date.parse(frozenAt) : NaN;
  const d = deadline ? Date.parse(deadline) : NaN;
  if (Number.isFinite(f) && Number.isFinite(d) && f < d) {
    return `xP frozen before the GW${gw} deadline`;
  }
  return `xP frozen for GW${gw}`;
}
