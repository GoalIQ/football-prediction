/**
 * SHARE-CARD-ULKOASU (1.10.2026): Replacements-jakokortin spec yhdessa
 * paikassa, ja ero lahtijaan yhdella lukijalla jota seka sivun "vs"-sarake
 * etta kortti kayttavat.
 *
 * Miksi ero lasketaan NAYTETYISTA luvuista: backendin `xp_gap_vs_target` on
 * pyoristamattomien summien erotus. Kortilla ja taulukossa luetaan rinnakkain
 * "31.0" ja lahtijan "24.3", jolloin "+6.8" (31.03 - 24.27) nayttaa
 * laskuvirheelta. Kymmenysten kokonaisluvuilla laskettu ero tasmaa aina siihen
 * mita lukija voi itse vahentaa, eika liukuluku voi heittaa sita.
 */

import type { CardRow, CardSpec } from './shareCard';
import type { ReplacementsResponse } from './fantasyTools';

export interface ShownGap {
	text: string;
	/** 1 = korvaaja on edella, -1 = jaljessa, 0 = sama naytetty luku. */
	sign: 1 | 0 | -1;
}

const tenths = (v: number): number => Math.round(Number(v.toFixed(1)) * 10);

export function shownGap(candidateXp: number, targetXp: number): ShownGap {
	const d = tenths(candidateXp) - tenths(targetXp);
	const sign = d > 0 ? 1 : d < 0 ? -1 : 0;
	const abs = (Math.abs(d) / 10).toFixed(1);
	return { text: sign > 0 ? `+${abs}` : sign < 0 ? `-${abs}` : abs, sign };
}

export function windowLabelOf(gws: number[]): string {
	if (gws.length === 0) return '';
	return gws.length === 1 ? `GW${gws[0]}` : `GW${gws[0]}-${gws[gws.length - 1]}`;
}

/** Kortti = se nakyma jonka jakaja katsoi: kohde, haarukka ja ikkuna
 *  otsikossa, jotta lista ei vaita olevansa "parhaat korvaajat" yleisesti. */
export function replacementsCardSpec(d: ReplacementsResponse): CardSpec {
	const m = d.meta;
	const t = d.target;
	const win = windowLabelOf(m.gws);
	const targetXp = t.xp_window;
	// FPL:n chance_next koskee VAIN seuraavaa kierrosta, joten kierros luvun
	// peraan (portti 16.9: paljas "out"/"75%" viiden kierroksen ikkunan vieressa
	// vaitti enemman kuin lahde).
	// 100 % ei ole tieto vaan varmuusvaite kuvassa -> vain alle 100.
	const chance =
		t.chance_next != null && t.chance_next < 100 && m.gws.length > 0
			? `${t.chance_next}% to play GW${m.gws[0]} in FPL`
			: null;
	const heroRow: Omit<CardRow, 'rank' | 'delta' | 'deltaUp'> = {
		name: t.web_name,
		tag: t.pos,
		tag2: `${t.price.toFixed(1)}m`,
		team: t.team_short,
		// 1.10 kuva: merkkina se litisti mobiilissa nimen nollaleveaksi ->
		// toiselle riville (FPL:n luku, FPL nimetty).
		...(chance ? { sub: chance } : {}),
		mid: `${t.owned_pct.toFixed(1)}%`,
		// 16.9: lahtijalla ei aina ole projektiota (sivussa FPL:ssa) -> kortti
		// sanoo sen, ei jata lukua pois hiljaa eika keksi nollaa.
		value: targetXp != null ? targetXp.toFixed(1) : 'no xP'
	};
	return {
		title: `WHO REPLACES ${t.web_name.toUpperCase()}`,
		// Lahtijan luku on nyt omalla rivillaan (ennen alaotsikossa).
		subtitle: `${t.pos} ${m.price_min.toFixed(1)}-${m.price_max.toFixed(1)}m, ${win} · GoalIQ model`,
		midLabel: 'OWNED',
		valueLabel: `xP ${win}`,
		footNote: 'xP from the GoalIQ model, ownership from FPL',
		fileName: 'goaliq_replacements.png',
		// Sana valittu niin ettei se vaita saatavuutta ("OUT" luetaan lippuna).
		hero: { label: 'REPLACING', row: heroRow },
		valueBars: true,
		rows: d.players.slice(0, 5).map((p, i) => {
			const g = targetXp != null ? shownGap(p.xp_window, targetXp) : null;
			return {
				rank: i + 1,
				name: p.web_name,
				tag: p.pos,
				// Ville 2.9: Rowan jakaa KUVAN, joten hinta ja syy kortille.
				tag2: `${p.price.toFixed(1)}m`,
				team: p.team_short,
				// Portti k3: paljas "75%" OWNED-sarakkeen vieressa luettiin omistukseksi -> yksikko.
				badges:
					p.status === 'd' && p.chance_next != null ? [`${p.chance_next}% to play`] : undefined,
				mid: `${p.owned_pct.toFixed(1)}%`,
				value: p.xp_window.toFixed(1),
				sub: p.reason.text,
				...(g ? { delta: `${g.text} vs ${t.web_name}`, deltaUp: g.sign > 0 } : {})
			};
		})
	};
}
