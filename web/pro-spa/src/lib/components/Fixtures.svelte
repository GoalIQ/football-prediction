<script lang="ts">
	/**
	 * Tulevat ottelut webiin (28.7, pariteetti mobiilin FixturesScreenin kanssa).
	 *
	 * FREE/PREMIUM-RAJAUS kopioitu mobiilista: free näkee ensimmäisen
	 * ottelupäivän, premium koko ikkunan. Ero kahdella pinnalla olisi uusi vika.
	 *
	 * Jokainen rivi vie ottelu-ennusteeseen. Se on tämän näkymän koko pointti:
	 * otteluohjelma ilman "entä miten tässä käy" on kalenteri, ei työkalu.
	 */
	import { fetchFixtures, LeagueUnsupportedError, type FixtureRow } from '$lib/api';
	import { FIXTURE_LEAGUES } from '$lib/leagues';
	import { capture } from '$lib/analytics';
	import { formatDeadline } from '$lib/gameweek';
	import { fmtDayKey, groupByLocalDay } from '$lib/fixtureDays';

	// WP2 (1.11.2026): yksi aikasaanto. SPA nayttaa ajat lukijan vyohykkeella
	// ja NIMEAA vyohykkeen (kuten deadline-rivi "Fri 6 Nov, 20:30 EET"); hub
	// kirjoittaa UTC:n HTML:aan ja vaihtaa sen selaimessa samaan muotoon
	// (src/local_time.py). Ilman nimea "18:30" ja hubin "16:30 UTC" nayttivat
	// kahdelta eri ajalta samalle ottelulle.
	const tzLabel = formatDeadline(new Date()).tz;

	let {
		premium = false,
		onUpgrade,
		onPredict
	}: {
		premium?: boolean;
		onUpgrade?: () => void;
		onPredict?: (league: string, home: string, away: string) => void;
	} = $props();

	const DAYS = 30;

	let league = $state('ENG-Premier League');
	let all = $state<FixtureRow[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

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

	/** Ryhmittely päivittäin, järjestys säilyy (API palauttaa aikajärjestyksessä). */
	// Julkaisutarkistaja 1.11 (PR #75): paiva lukijan vyohykkeessa, kuten kellonaika
	// (lib/fixtureDays.ts). Ennen UTC-paiva: lauantain ottelu perjantain alla New Yorkissa.
	let days = $derived(groupByLocalDay(all));

	let visible = $derived(premium ? days : days.slice(0, 1));
	let hiddenDays = $derived(days.length - visible.length);

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

	function predict(f: FixtureRow) {
		capture('fixtures_predict_tapped', { league });
		onPredict?.(
			league,
			f.home_team_short_name || f.home_team,
			f.away_team_short_name || f.away_team
		);
	}

	function showPaywall() {
		capture('paywall_shown', { source: 'fixtures' }, 'paywall_shown_fixtures');
		onUpgrade?.();
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
	{#each visible as [date, list] (date)}
		<h3 class="dayhead">{fmtDayKey(date)}</h3>
		<ul class="fx">
			{#each list as f (f.datetime + f.home_team)}
				<li>
					<span class="t">{fmtTime(f.datetime)}</span>
					<span class="m">
						{f.home_team_short_name || f.home_team}
						<span class="v">vs</span>
						{f.away_team_short_name || f.away_team}
					</span>
					<button type="button" class="linklike" onclick={() => predict(f)}>Predict</button>
				</li>
			{/each}
		</ul>
	{/each}

	{#if !premium && hiddenDays > 0}
		<div class="locked">
			<strong>{hiddenDays} more {hiddenDays === 1 ? 'day' : 'days'} of fixtures</strong> are in
			Premium, along with expected goals and the full scoreline table in the prediction tool.
			<button type="button" class="linklike" onclick={showPaywall}>See Premium</button>
		</div>
	{/if}
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
	}
	.v {
		color: var(--text-muted);
		padding: 0 0.3em;
	}
	.locked {
		border: 1px solid var(--border);
		border-left: 3px solid var(--accent, var(--border));
		border-radius: var(--radius);
		padding: var(--s-3) var(--s-4);
		max-width: 62ch;
		font-size: var(--step--1);
		margin-top: var(--s-4);
	}
</style>
