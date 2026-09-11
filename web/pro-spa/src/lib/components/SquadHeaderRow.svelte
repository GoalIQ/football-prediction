<script lang="ts">
	import type { RateTeamChips } from '$lib/fantasyTools';

	/**
	 * DRAFT-COMPARE-OTSIKKORIVI (11.9.2026, FPL Demon -kaava).
	 *
	 * 🔴 MIKSI YKSI KOMPONENTTI. Sama arvioitu runko sai ennen kolme eri
	 * esitysta: slot A:lla `.verdict-strip` + neljan laatan `.tiles`, slot
	 * B:lla `.rating.card` -hero + `.facts`, ja vertailussa oma xP-rivinsa.
	 * Luvut olivat samat, mutta jokainen pinta muotoili ne itse, eli
	 * pyoristys ja sanamuoto saattoivat erota ilman etta mikaan portti nakee
	 * sita. Yksi lukija yhdelle riville (CLAUDE.md 6a mekanismi 1): jos
	 * `ITB` nayttaa vaaraa lukua, se on vaarin TASAN yhdessa paikassa.
	 *
	 * Rivi ei laske mitaan. Kaikki arvot tulevat rate-team-vastauksesta
	 * sellaisenaan, jotta jokaiselle numerolle on reitti payloadiin.
	 */
	let {
		rating,
		teamXpGw,
		teamXpHorizon,
		horizonGw = 6,
		gw,
		bank = null,
		freeTransfers = null,
		chips = undefined,
		weakestLine = null,
		ratingBasis = null,
		ratingGap = null,
		showGwXp = false,
		label = null,
		aligned = false
	}: {
		/** `rating.rating ?? Math.round(rating.percentile)`, kutsuja valitsee:
		 *  vanha backend palauttaa vain percentilen. */
		rating: number;
		teamXpGw: number;
		teamXpHorizon: number;
		horizonGw?: number | null;
		/** Kierros jolle `teamXpGw` on laskettu (meta.gw). */
		gw: number;
		/** null = ei tiedossa. Nolla olisi vaite tyhjasta pankista. */
		bank?: number | null;
		freeTransfers?: number | null;
		/** `undefined` = API ei kanna kenttaa viela (vanha deploy) -> solu jaa
		 *  kokonaan pois. `null` = draft tai historiaa ei saatu -> solu sanoo
		 *  sen aaneen. Nama ovat eri asioita eivatka saa nayttaa samalta. */
		chips?: RateTeamChips | null;
		/** `rating.weakest_line`. Ilmaista tietoa, ja /fpl-sivun copy lupaa
		 *  sen sanatarkasti ("names the line that is costing you"), joten se
		 *  kuuluu jokaiselle pinnalle eika vain ilmaiskayttajan nauhaan. */
		weakestLine?: string | null;
		/** Mita 100 tarkoittaa. Kutsuja muodostaa lauseen, koska vain se nakee
		 *  `optimal_proven`-lipun; rivi ei saa keksia perustaa itse.
		 *  🔴 Portti 11.9: tama renderoidaan NAKYVANA rivina, ei title-
		 *  attribuuttina. Hover ei ole olemassa kosketuslaitteella, ja luku
		 *  ilman asteikkoaan on vaite ilman reittia. */
		ratingBasis?: string | null;
		/** Etaisyys vertailukohtaan sanoina ("You are 3.4 xP off it."). Tama
		 *  luku katosi kayttoliittymasta kun `.tiles`-lohko poistui, ja se on
		 *  ainoa asia joka tekee ratingista falsifioituvan yhdella silmayksella. */
		ratingGap?: string | null;
		/** GW-xP naytetaan rivilla VAIN kun kentan otsikkonauha ei nayta sita
		 *  alapuolella. Premium-pitch renderoi elavan GW-xP:n, ja sama luku
		 *  kahdesti 200 pikselin sisalla lukisi kahtena eri asiana. */
		showGwXp?: boolean;
		/** Vertailunakyman "Team 1" / "Team 2". */
		label?: string | null;
		/** Vertailussa rivit ovat saman gridin sisalla, jotta sarakkeet
		 *  osuvat kohdakkain. Ks. `.aligned`-CSS alla. */
		aligned?: boolean;
	} = $props();

	// FPL:n omat nimet -> rivin lyhenteet. Yksi kartta, koska rivi on ainoa
	// paikka joka lyhentaa ne. Tuntematon nimi nakyy sellaisenaan eika
	// katoa: uusi chip on tieto, ei virhe.
	const SHORT: Record<string, string> = {
		wildcard: 'WC',
		bboost: 'BB',
		'3xc': 'TC',
		freehit: 'FH'
	};

	type ChipPart = { text: string; used: boolean; title: string };
	let chipParts = $derived.by<ChipPart[]>(() => {
		if (!chips) return [];
		const played = (chips.played ?? []).map((c) => ({
			text: `${SHORT[c.name] ?? c.name} GW${c.gw}`,
			used: true,
			title: `Played in GW${c.gw}`
		}));
		// 🔴 Portti 11.9: "Still available" ilman kierrosta oli vaara vaite.
		// Kaudella on kaksi ikkunaa per chip, joten GW4:ssa jo pelattu
		// wildcard palasi listalle kaytettavissa olevana, vaikka sen toinen
		// ikkuna aukeaa GW20. Kierros luetaan nyt payloadista ja nakyy
		// tekstissa aina kun ikkuna on edessa.
		const left = (chips.remaining ?? []).map((c) => ({
			text: c.available_now ? (SHORT[c.name] ?? c.name) : `${SHORT[c.name] ?? c.name} GW${c.from_gw}+`,
			used: false,
			title: c.available_now ? 'Available now' : `Available from GW${c.from_gw}`
		}));
		return [...played, ...left];
	});

	let horizon = $derived(horizonGw ?? 6);
</script>

<div class="hrow" class:aligned>
	{#if label}<span class="hlabel">{label}</span>{/if}
	<span class="cell" title="GoalIQ model rating out of 100. Green from 90, amber from 75.">
		<span class="k">Rating</span>
		<span class="v">
			<span
				class="dot"
				class:good={rating >= 90}
				class:mid={rating >= 75 && rating < 90}
				class:bad={rating < 75}
			></span>{rating}<span class="u">/100</span>
		</span>
	</span>
	{#if weakestLine}
		<span class="cell" title="The line the model would strengthen first.">
			<span class="k">Weak spot</span>
			<span class="v line-weak">{weakestLine}</span>
		</span>
	{/if}
	{#if showGwXp}
		<span class="cell">
			<span class="k">GW{gw} xP</span>
			<span class="v">{teamXpGw.toFixed(1)}</span>
		</span>
	{/if}
	<!-- "captain doubled" oli ennen `.tiles`-laatan alaotsikkona. Luku on sama,
	     joten peruste kulkee mukana eika jaa poistetun lohkon mukana pois. -->
	<span
		class="cell"
		title="Projected points over GW{gw} to GW{gw + horizon - 1}, captain doubled"
	>
		<span class="k">Next {horizon} GW <span class="u">(GW{gw}-{gw + horizon - 1})</span></span>
		<span class="v">{teamXpHorizon.toFixed(1)}<span class="u">xP</span></span>
	</span>
	<span class="cell" title="Money in the bank, from your FPL squad">
		<span class="k">ITB</span>
		<!-- Puuttuva luku on viiva, ei nolla: nolla vaittaisi tyhjaa pankkia. -->
		<span class="v">{bank != null ? `£${bank.toFixed(1)}` : '–'}</span>
	</span>
	<span
		class="cell"
		title="Free transfers for the next gameweek, worked out from your public transfer history"
	>
		<span class="k">FT</span>
		<span class="v">{freeTransfers != null ? freeTransfers : '–'}</span>
	</span>
	{#if chips !== undefined}
	<span class="cell chips" title="Chips you have played this season, then the ones still available">
		<!-- Kaksoispiste vain tassa: arvo on LISTA eika yksi luku, ja ilman
		     sita "Chips no entry" luki yhtena sanaparina. -->
		<span class="k">Chips:</span>
		<span class="v">
			{#if !chips}
				<!-- Draft tai historiaa ei saatu. Tyhja lista olisi vaite
				     "chippeja ei ole pelattu", eika sita tiedeta. -->
				<span class="none">no entry</span>
			{:else if chipParts.length === 0}
				<span class="none">none left</span>
			{:else}
				{#each chipParts as c, i (c.text + i)}
					<span class="chip-part" class:used={c.used} title={c.title}>{c.text}</span>
				{/each}
			{/if}
		</span>
	</span>
	{/if}
</div>
{#if ratingBasis}
	<p class="hrow-basis">{ratingBasis}{ratingGap ? ` ${ratingGap}` : ''}</p>
{/if}

<style>
	/* 🔴 Portti 11.9: `.line-weak` tuli mukana RateTeamista, mutta Svelten
	   scoped-CSS ei ylla toisen komponentin luokkaan. Heikoin linja
	   renderoityi samalla amberilla kuin jokainen muu luku, eli varoitus
	   katosi hiljaa. */
	.line-weak {
		color: var(--negative);
	}
	.hrow-basis {
		margin: 4px 0 0;
		font-size: var(--step--1);
		color: var(--text-muted);
		max-width: none;
	}

	.hrow {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--s-1) var(--s-3);
		padding: var(--s-2) 0;
		border-top: 1px solid var(--border);
		border-bottom: 1px solid var(--border);
		margin: 0 0 var(--s-3);
		font-size: var(--step--1);
	}
	.hlabel {
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
	}
	.cell {
		display: inline-flex;
		align-items: baseline;
		gap: var(--s-1);
		min-width: 0;
	}
	/* Erotin vain leveilla riveilla: `gap` yksin ei kerro mihin arvo loppuu
	   ja seuraava nimio alkaa. */
	.cell + .cell::before {
		content: '·';
		color: var(--text-muted);
		margin-right: var(--s-1);
	}
	.k {
		color: var(--text-muted);
		white-space: nowrap;
	}
	.v {
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
		font-weight: 700;
		color: var(--accent);
		white-space: nowrap;
	}
	.u {
		font-size: 0.85em;
		font-weight: 400;
		color: var(--text-muted);
		margin-left: 2px;
	}
	.dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		margin-right: 6px;
		background: var(--text-muted);
	}
	.dot.good {
		background: var(--positive);
	}
	.dot.mid {
		background: var(--accent);
	}
	.dot.bad {
		background: var(--negative);
	}
	.chips .v {
		white-space: normal;
		display: inline-flex;
		flex-wrap: wrap;
		gap: var(--s-1);
	}
	.chip-part + .chip-part::before {
		content: '·';
		/* inline-block = atominen laatikko, johon vanhemman `line-through` ei
		   levia. Ilman tata erotin oli yliviivattu pelatun chipin vieressa ja
		   kaksi chippia luki yhtena yliviivattuna palana. */
		display: inline-block;
		color: var(--text-muted);
		margin-right: var(--s-1);
	}
	/* Pelattu chip on muted, jaljella oleva amber. Ilman eroa "BB" ja
	   "WC GW2" lukisivat samana asiana, ja kierrosnumero olisi ainoa vihje. */
	.chip-part {
		color: var(--accent);
	}
	.chip-part.used {
		color: var(--text-muted);
		text-decoration: line-through;
	}
	.none {
		color: var(--text-muted);
		font-family: var(--font-sans);
		font-weight: 400;
	}

	/* VERTAILUN SARAKKEET. `display: contents` nostaa solut vanhemman gridin
	   omiksi soluiksi, jolloin kaksi rivia asettuu samoihin sarakkeisiin
	   ilman etta kumpikaan tietaa toisesta. Raja (640px) on SAMA kuin
	   RateTeamin `.compare-rows`-gridilla: sen alla rivit ovat omia
	   flex-rivejaan, koska kuusi saraketta ei mahdu puhelimeen. */
	@media (min-width: 640px) {
		.hrow.aligned {
			display: contents;
		}
		/* Gridin solussa erotin veisi sarakkeelta tilaa eika osuisi
		   kohdakkain toisen rivin kanssa. */
		.hrow.aligned .cell + .cell::before {
			content: none;
		}
	}
	@media (max-width: 639px) {
		.hrow.aligned {
			border-top: none;
			margin-bottom: var(--s-2);
		}
	}
</style>
