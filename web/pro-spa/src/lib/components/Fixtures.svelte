<script lang="ts">
	/**
	 * Tulevat ottelut webiin (28.7, pariteetti mobiilin FixturesScreenin kanssa).
	 *
	 * FREE/PREMIUM-RAJAUS seuraa mobiilia: ero kahdella pinnalla olisi uusi vika.
	 * WP10 / B3 (Villen paatos 1.11.2026, sovelluksessa WP9:ssa): kaikki paivat
	 * kaikille, ja jokaisella rivilla mallin kirjattu 1X2 julkisesta lokista
	 * ($lib/fixtureProbs). Syvyys (xG, tulosmatriisi) on yha Premiumia
	 * Predictissa. Ennen tata ilmainen naki vain ensimmaisen paivan, ja
	 * sovellus oli jo avannut saman listan: web oli koyhempi kuin sovellus.
	 *
	 * Jokainen rivi vie ottelu-ennusteeseen. Se on tämän näkymän koko pointti:
	 * otteluohjelma ilman "entä miten tässä käy" on kalenteri, ei työkalu.
	 */
	import {
		fetchFixtures,
		fetchPendingPredictions,
		LeagueUnsupportedError,
		type FixtureRow
	} from '$lib/api';
	import { FIXTURE_LEAGUES } from '$lib/leagues';
	import { capture } from '$lib/analytics';
	import { formatDeadline } from '$lib/gameweek';
	import { fmtDayKey, groupByLocalDay } from '$lib/fixtureDays';
	import {
		buildProbsIndex,
		EMPTY_INDEX,
		logCompetitionFor,
		probsFor,
		type ProbsIndex
	} from '$lib/fixtureProbs';

	// WP2 (1.11.2026): yksi aikasaanto. SPA nayttaa ajat lukijan vyohykkeella
	// ja NIMEAA vyohykkeen (kuten deadline-rivi "Fri 6 Nov, 20:30 EET"); hub
	// kirjoittaa UTC:n HTML:aan ja vaihtaa sen selaimessa samaan muotoon
	// (src/local_time.py). Ilman nimea "18:30" ja hubin "16:30 UTC" nayttivat
	// kahdelta eri ajalta samalle ottelulle.
	const tzLabel = formatDeadline(new Date()).tz;

	let {
		onPredict
	}: {
		onPredict?: (league: string, home: string, away: string) => void;
	} = $props();

	const DAYS = 30;

	let league = $state('ENG-Premier League');
	let all = $state<FixtureRow[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let probsIdx = $state<ProbsIndex>(EMPTY_INDEX);

	$effect(() => {
		const lg = league;
		loading = true;
		error = null;
		// 16.8: vanhentuneen vastauksen vahti, sama kuin Standingsissa ja
		// mobiilissa. Ehto on "onko tama viela valittu liiga", EI juokseva
		// numero: numerovahti hylkaisi myos paallekkaiset haut samalle
		// liigalle ja jattaisi edellisen liigan ottelut ruudulle.
		const isCurrent = () => lg === league;
		fetchFixtures(lg, DAYS).then(
			(d) => {
				if (!isCurrent()) return;
				all = d.fixtures ?? [];
				loading = false;
			},
			(e) => {
				if (!isCurrent()) return;
				all = [];
				// 28.7 REHELLISYYS: aiempi copy sanoi kaikille virheille "please try
				// again shortly". Mitattu: 24 liigasta vain 5 palauttaa dataa, joten
				// se lupasi 19 liigalle odottamista joka ei auta koskaan. Nyt syy
				// erotellaan: ei syotetta vs. oikea hairio.
				error =
					e instanceof LeagueUnsupportedError
						? 'We do not have a fixture feed for this league yet. The prediction tool still works for it.'
						: 'Could not load fixtures right now. Please try again shortly.';
				loading = false;
			}
		);
	});

	// WP10 / B3: rivin 1X2 = julkisen lokin kirjattu ennuste. Oma haku, jotta
	// lokin hairio ei piilota otteluohjelmaa: virhe -> tyhja indeksi, eli
	// rivit ilman lukua (ei 0 %). Lokin kilpailukoodi (PL, PD, ...), EI SPA:n
	// liigakoodia: backend hylkaa 'ENG-Premier League' -muodon.
	$effect(() => {
		const lg = league;
		probsIdx = EMPTY_INDEX;
		const competition = logCompetitionFor(lg);
		if (competition == null) return;
		fetchPendingPredictions(competition).then(
			(rows) => {
				if (lg === league) probsIdx = buildProbsIndex(rows);
			},
			() => {
				if (lg === league) probsIdx = EMPTY_INDEX;
			}
		);
	});

	/** Ryhmittely päivittäin, järjestys säilyy (API palauttaa aikajärjestyksessä). */
	// Julkaisutarkistaja 1.11 (PR #75): paiva lukijan vyohykkeessa, kuten kellonaika
	// (lib/fixtureDays.ts). Ennen UTC-paiva: lauantain ottelu perjantain alla New Yorkissa.
	let days = $derived(groupByLocalDay(all));

	// Rivi + sen luku samasta lukijasta. Yksikaan rivi ei laske prosenttia itse.
	let rowsByDay = $derived(
		days.map(([date, list]) => [date, list.map((f) => ({ f, p: probsFor(probsIdx, f) }))] as const)
	);
	let anyProbs = $derived(rowsByDay.some(([, list]) => list.some((r) => r.p != null)));

	// Kieli lukitaan en-GB:hen. `undefined` käyttäisi selaimen kieltä, jolloin
	// suomalaisella laitteella luki "perjantai 21. elokuuta" keskellä muuten
	// englanninkielistä tuotetta. AIKAVYÖHYKE sen sijaan jätetään laitteen
	// omaksi: ottelun alkamisaika on käyttäjälle hyödyllinen vain hänen omassa
	// ajassaan.
	const LOCALE = 'en-GB';


	function fmtTime(iso: string): string {
		if (!iso) return '';
		const d = new Date(iso);
		return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit' });
	}

	function homeName(f: FixtureRow): string {
		return f.home_team_short_name || f.home_team;
	}
	function awayName(f: FixtureRow): string {
		return f.away_team_short_name || f.away_team;
	}

	function predict(f: FixtureRow) {
		capture('fixtures_predict_tapped', { league });
		onPredict?.(league, homeName(f), awayName(f));
	}
</script>

<h2>Fixtures</h2>
<p class="muted lede">
	Upcoming matches for the next {DAYS} days. Every fixture opens in the prediction tool.
</p>

<div class="field">
	<label for="fx-league">League</label>
	<select id="fx-league" bind:value={league}>
		{#each FIXTURE_LEAGUES as l (l.code)}
			<option value={l.code}>{l.label}</option>
		{/each}
	</select>
</div>

{#if error}
	<p class="banner">{error}</p>
{:else if loading}
	<p class="muted">Loading…</p>
{:else if days.length === 0}
	<p class="muted">
		No matches scheduled in the next {DAYS} days. Many leagues are between seasons in July.
	</p>
{:else}
	{#if tzLabel}<p class="muted tz-note">Kick-off times are in your time zone ({tzLabel}).</p>{/if}
	{#if anyProbs}
		<!-- Sanatarkasti sovelluksen fixtures.prob_source (julkaisutarkistaja k2,
		     WP9 1.11). Linkki vie ilmaispinnan recordiin, jossa luku gradataan. -->
		<p class="muted prob-source">
			<a href="https://goaliq.app/predictions#record"
				>Percentages are the model's prediction, logged before kick-off and graded in the public
				track record.</a
			>
		</p>
	{/if}
	<div class="days">
		{#each rowsByDay as [date, list] (date)}
			<!-- div eika section: teeman `section > h3:first-child` ja
			     `section + section` tekisivat paivaotsikosta kortin nimion ja
			     lisaisivat 32 px paivien valiin (mitattu 390 px:lla). -->
			<div class="day">
				<h3 class="dayhead">{fmtDayKey(date)}</h3>
				<ul class="fx">
					{#each list as { f, p } (f.datetime + f.home_team)}
						<li>
							<span class="t">{fmtTime(f.datetime)}</span>
							<span class="m">
								<span class="teams">
									{homeName(f)}
									<span class="v">vs</span>
									{awayName(f)}
								</span>
								{#if p}
									<span
										class="prob"
										role="img"
										aria-label="Model prediction: {homeName(f)} {p.home}%, draw {p.draw}%, {awayName(
											f
										)} {p.away}%"
									>
										<span class="bar" aria-hidden="true">
											<i class="seg ph" style="flex-grow: {Math.max(p.home, 1)}"></i>
											<i class="seg pd" style="flex-grow: {Math.max(p.draw, 1)}"></i>
											<i class="seg pa" style="flex-grow: {Math.max(p.away, 1)}"></i>
										</span>
										<span class="nums" aria-hidden="true">
											<span>{p.home}%</span>
											<span>Draw {p.draw}%</span>
											<span>{p.away}%</span>
										</span>
									</span>
								{/if}
							</span>
							<button type="button" class="linklike" onclick={() => predict(f)}>Predict</button>
						</li>
					{/each}
				</ul>
			</div>
		{/each}
	</div>
{/if}

<style>
	.lede {
		max-width: 62ch;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 180px;
		max-width: 300px;
		margin: var(--s-5) 0 var(--s-4);
	}
	.field label {
		font-size: var(--step--1);
		color: var(--text-muted);
		font-weight: 700;
	}
	.field select {
		min-height: 44px;
		padding: 0 0.7em;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		font: inherit;
	}
	.banner {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-3) var(--s-4);
		max-width: 62ch;
	}
	.prob-source {
		font-size: var(--step--1);
		max-width: 62ch;
	}
	.prob-source a {
		color: inherit;
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.dayhead {
		font-size: var(--step-0);
		margin: var(--s-4) 0 var(--s-2);
	}
	.fx {
		list-style: none;
		padding: 0;
		margin: 0;
		max-width: 620px;
	}
	.fx li {
		display: flex;
		align-items: center;
		gap: var(--s-3);
		padding: 9px 0;
		border-bottom: 1px solid var(--border);
	}
	.t {
		font-variant-numeric: tabular-nums;
		color: var(--text-muted);
		font-size: var(--step--1);
		min-width: 3.5em;
	}
	.m {
		flex: 1;
		min-width: 0;
	}
	.teams {
		display: block;
	}
	.v {
		color: var(--text-muted);
		padding: 0 0.3em;
	}
	/* 1X2: sama kaava kuin sovelluksessa (koti amber, tasapeli viiva, vieras
	   teal), ei suosikkikorostusta (julkaisutarkistaja k2, WP9). */
	.prob {
		display: block;
		margin-top: 6px;
		max-width: 22rem;
	}
	.bar {
		display: flex;
		gap: 2px;
		height: 6px;
	}
	.seg {
		display: block;
		flex-basis: 0;
		height: 6px;
	}
	.ph {
		background: var(--accent);
	}
	.pd {
		background: var(--border-strong);
	}
	.pa {
		background: var(--giq-teal);
	}
	/* nowrap: 390 px:lla palkki on ~170 px, ja "Draw 25%" katkesi kahdelle
	   riville kun kolme lukua jaettiin tasan (mitattu). */
	.nums {
		display: flex;
		justify-content: space-between;
		gap: var(--s-2);
		margin-top: 3px;
		font-size: var(--step--1);
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	/* WP10 / B5: desktopilla paivat kahdessa palstassa RIVEITTAIN (1 | 2,
	   3 | 4 ...), jotta lahimmat paivat ovat ensimmaisessa ruudussa.
	   Sanomalehtipalstat (column-count) mitattiin ensin: oikean palstan
	   ylimpana oli 23.11, kolmen viikon paassa, heti 2.11:n vieressa.
	   Puhelimessa ja kapealla ikkunalla yksi palsta kuten ennen. */
	@media (min-width: 1100px) {
		.days {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			column-gap: var(--s-8);
			align-items: start;
		}
	}
</style>
