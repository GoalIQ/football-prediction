<script lang="ts">
	/**
	 * /spl — RSL Fantasy (Saudi Pro League) -työkalut, OMA OSIO (7.8).
	 *
	 * Kolme tietoista linjausta (etiikkaselvitys cc-reports 7.8 + Villen
	 * päätökset):
	 *   1. TÄYSIN ILMAINEN — hankintakiila FPL-premiumiin, ei paywallia.
	 *   2. Oma reitti eikä FPL-feedin seassa — FPL-first-brändi säilyy,
	 *      SPL:stä kiinnostumaton ei näe sitä koskaan.
	 *   3. Disclaimer näkyvissä: riippumaton datatyökalu, ei makseta
	 *      promoamisesta (FFScout-precedentin mukainen raja).
	 *
	 * Databasis EROAA FPL:stä ja se sanotaan ääneen: maalipohjainen malli
	 * (ei xG-feediä SPL:lle), minuutit kausiaggregaateista. Ei väitetä
	 * enempää kuin data kantaa — [[honest-data-labels]].
	 */
	import {
		fetchSplFantasy,
		fetchSplXp,
		type FantasyResponse,
		type FantasyTeam,
		type XpResponse
	} from '$lib/api';
	import { capture } from '$lib/analytics';
	import { DISCLAIMER } from '$lib/config';
	import {
		canShareToApps,
		shareCard,
		sharePitchCard,
		type PitchCardPlayer, shareButtonLabel} from '$lib/shareCard';
	import { teamColorByShort } from '$lib/teamColors';
	import SquadPitch from '$lib/components/SquadPitch.svelte';

	let cs = $state<FantasyResponse | null>(null);
	let xp = $state<XpResponse | null>(null);
	let csError = $state<string | null>(null);
	let xpError = $state<string | null>(null);

	$effect(() => {
		capture('spl_page_viewed');
		fetchSplFantasy().then(
			(d) => (cs = d),
			(e) => (csError = String(e))
		);
		fetchSplXp().then(
			(d) => (xp = d),
			(e) => (xpError = String(e))
		);
	});

	let nearHorizon = $derived((cs?.meta?.near_horizon_gw as number) ?? 6);

	/* SPL-GW1-RECON (20.8): kierrostäsmäytys tulee metan artefaktista
	   (scripts/build_spl_recon.py -> build_spl_phase0 meta.gw_reconciliation).
	   Jokainen lohkon luku renderöityy payloadista — sivulla ei ole yhtään
	   käsin kirjoitettua lukua, joten copy ei voi ajautua eri lukuihin kuin
	   artefakti. Avain puuttuu -> lohkoa ei ole. */
	type ReconFixture = {
		home: string;
		away: string;
		home_short: string;
		away_short: string;
		score: string;
		cs_home_pct: number;
		cs_away_pct: number;
		cs_home_kept: boolean;
		cs_away_kept: boolean;
	};
	type ReconScores = {
		sides: number;
		expected_cs: number;
		actual_cs: number;
		brier: number;
		naive_brier: number;
	};
	type Recon = ReconScores & {
		gameweek: number;
		snapshot?: { generated_at?: string };
		naive_p: number;
		top3: { team: string; cs_pct: number; kept: boolean }[];
		fixtures: ReconFixture[];
		/* 3.9: kausi tahan asti. Ylatason luvut ovat UUSIMMAN ratkenneen
		   kierroksen; sivun vaite kuuluu kaudelle, koska yksi kierros on
		   18-20 joukkue-sivua eli liian ohut otos. */
		gameweeks: (ReconScores & { gameweek: number })[];
		season_to_date: ReconScores & {
			gameweeks: number[];
			matches: number;
			naive_p: number;
		};
	};
	let recon = $derived((cs?.meta?.gw_reconciliation as Recon | undefined) ?? null);
	/** Kierros jonka toteuma erosi eniten odotuksesta. `null` kun yksikaan ei
	 *  eroa tarpeeksi, jotta lohko ei selita kohinaa poikkeamana. Kynnys 3
	 *  puhdasta peliä = noin yksi keskihajonta 16-20 sivun kierroksella. */
	let outlierGw = $derived.by(() => {
		const gws = recon?.gameweeks ?? [];
		if (gws.length < 2) return null;
		const worst = gws.reduce((a, b) =>
			Math.abs(b.actual_cs - b.expected_cs) > Math.abs(a.actual_cs - a.expected_cs) ? b : a
		);
		return Math.abs(worst.actual_cs - worst.expected_cs) >= 3 ? worst : null;
	});
	let nextGw = $derived((cs?.meta?.next_gameweek as number) ?? 1);
	let deadline = $derived.by(() => {
		const raw = cs?.meta?.deadline_utc as string | undefined;
		if (!raw) return null;
		const d = new Date(raw);
		return isNaN(d.getTime()) ? null : d;
	});

	/** CS/FDR: lähihorisontin rivit valmiiksi aggregoituna. */
	type Agg = { t: FantasyTeam; avgFdr: number; avgCs: number | null; n: number };
	let teams = $derived.by<Agg[]>(() => {
		const cut = nextGw + nearHorizon - 1;
		return (cs?.teams ?? [])
			.map((t) => {
				const fx = t.fixtures.filter((f) => f.gw >= nextGw && f.gw <= cut);
				const csVals = fx
					.map((f) => f.cs_pct)
					.filter((v): v is number => typeof v === 'number');
				return {
					t,
					n: fx.length,
					avgFdr: fx.length ? fx.reduce((s, f) => s + f.fdr, 0) / fx.length : 99,
					avgCs: csVals.length === fx.length && fx.length ? csVals.reduce((s, v) => s + v, 0) / fx.length : null
				};
			})
			.sort((a, b) => (b.avgCs ?? -1) - (a.avgCs ?? -1));
	});

	function fdrClass(fdr: number): string {
		if (fdr <= 2) return 'is-easy';
		if (fdr >= 4) return 'is-hard';
		return '';
	}

	type PosFilter = 'ALL' | 'GKP' | 'DEF' | 'MID' | 'FWD';
	let posFilter = $state<PosFilter>('ALL');
	let players = $derived(
		(xp?.players ?? [])
			.filter((p) => posFilter === 'ALL' || p.pos === posFilter)
			.slice(0, 50)
	);

	/* ---- Launch-laajennus (7.8, Villen "rakenna kaikki"): captain / model
	   squad / value / differentials / leaders / compare — kaikki johdettu jo
	   ladatuista payloadeista, ei uusia API-kutsuja. ---- */

	type SplPlayer = (typeof players)[number] & {
		price?: number;
		owned_pct?: number;
		last_season?: {
			/** 3.9: kausilabel tulee riveilta, ei metasta (meta.season = kuluva). */
			season?: string;
			minutes?: number;
			goals?: number;
			assists?: number;
			points?: number;
		} | null;
	};
	let pool = $derived((xp?.players ?? []) as SplPlayer[]);

	/** Kapteeni: GW1-xP:n kärki (vain XI-tason minuuttiodotus mukaan —
	 *  cameo-kärki olisi kapteenina harhaanjohtava). */
	let captainPicks = $derived(
		pool
			.filter((p) => p.xmins >= 45)
			.map((p) => ({ p, gw1: p.gameweeks?.[0]?.xp ?? 0 }))
			.sort((a, b) => b.gw1 - a.gw1)
			.slice(0, 5)
	);

	/** Value: xP/GW per miljoona (min. xmins-raja pitää penkkiriskit poissa —
	 *  sama oppi kuin FPL:n xP/90-vika 5.8: pieni jakaja valehtelee). */
	let valuePicks = $derived(
		pool
			.filter((p) => (p.price ?? 0) >= 4 && p.xmins >= 45)
			.map((p) => ({ p, vpm: p.xp_per_gw / (p.price ?? 1) }))
			.sort((a, b) => b.vpm - a.vpm)
			.slice(0, 20)
	);

	/** Differentials: omistus alle 10 %, xP-kärki. */
	let differentials = $derived(
		pool
			.filter((p) => (p.owned_pct ?? 100) < 10 && p.xmins >= 45)
			.sort((a, b) => b.xp_per_gw - a.xp_per_gw)
			.slice(0, 10)
	);

	/** Viime kauden leaderit payloadin last_season-lohkosta. */
	/** Kausi luetaan RIVEILTA, ei metasta: rivit ovat `last_season`ia ja
	 *  `meta.season` on kuluva kausi. Null kun rivit eivat ole yksimielisia
	 *  tai kenttaa ei ole — silloin kortti ei vaita kautta lainkaan. */
	const leadersSeason = $derived.by(() => {
		const ss = new Set(
			(players as SplPlayer[])
				.map((p) => p.last_season?.season)
				.filter((v): v is string => typeof v === 'string')
		);
		return ss.size === 1 ? [...ss][0] : null;
	});

	function leaders(key: 'goals' | 'assists' | 'points') {
		return pool
			.filter((p) => p.last_season && (p.last_season[key] ?? 0) > 0)
			.sort((a, b) => (b.last_season?.[key] ?? 0) - (a.last_season?.[key] ?? 0))
			.slice(0, 8);
	}

	type ModelSquad = {
		cost: number;
		xi_xp_horizon: number;
		note: string;
		players: {
			id: number;
			web_name: string;
			team_short: string;
			pos: string;
			price: number;
			xp_per_gw: number;
			in_xi: boolean;
		}[];
	} | null;
	let modelSquad = $derived(((xp as unknown as { model_squad?: ModelSquad })?.model_squad) ?? null);

	/* 8.8 SPL-jakokortit (M59-sarja ruokkii näistä; 13.8 postaus = squad-kortti).
	   SPL on ilmainen → kortti on jakelusilmukka, sama perustelu kuin
	   PriceWatchin free-kortissa. Sävy ja rakenne 1:1 FPL-korttien kanssa. */
	let sharingCaptain = $state(false);
	async function shareCaptainCard() {
		if (sharingCaptain || captainPicks.length < 3) return;
		sharingCaptain = true;
		try {
			const method = await shareCard({
				title: 'RSL CAPTAIN PICKS',
				subtitle: `Gameweek ${nextGw}, RSL Fantasy scoring, GoalIQ model`,
				midLabel: 'FIXTURE',
				valueLabel: 'xP',
				fileName: `goaliq_spl_captains_gw${nextGw}.png`,
				rows: captainPicks.map(({ p, gw1 }, i) => ({
					rank: i + 1,
					name: p.web_name,
					tag: p.pos,
					team: p.team_short,
					mid:
						(p.gameweeks?.[0]?.opponents ?? [])
							.map((o) => `${o.opp} (${o.venue})`)
							.join(', ') || '',
					value: gw1.toFixed(2)
				}))
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'spl_captain', method });
		} finally {
			sharingCaptain = false;
		}
	}

	let sharingXp = $state(false);
	async function shareXpCard() {
		if (sharingXp || players.length < 3) return;
		sharingXp = true;
		try {
			const method = await shareCard({
				title: 'RSL EXPECTED POINTS',
				subtitle: [
					`next ${(xp?.meta?.horizon_gw as number) ?? 6} GWs`,
					...(posFilter !== 'ALL' ? [posFilter] : []),
					'RSL Fantasy scoring, GoalIQ model'
				].join(', '),
				midLabel: 'PRICE',
				valueLabel: 'xP',
				fileName: 'goaliq_spl_xp.png',
				rows: players.slice(0, 10).map((p, i) => ({
					rank: i + 1,
					name: p.web_name,
					tag: p.pos,
					team: p.team_short,
					mid: typeof p.price === 'number' ? p.price.toFixed(1) : '',
					value: p.xp_horizon_total.toFixed(1)
				}))
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'spl_xp', method });
		} finally {
			sharingXp = false;
		}
	}

	/* Yleinen jakaja lopuille listoille (Villen "kaikkiin listoihin"):
	   yksi tila, avain kertoo mikä nappi pyörii. */
	let sharingList = $state<string | null>(null);
	async function shareList(key: string, spec: Parameters<typeof shareCard>[0]) {
		if (sharingList) return;
		sharingList = key;
		try {
			const method = await shareCard(spec);
			if (method !== 'aborted') capture('xp_card_shared', { list: key, method });
		} finally {
			sharingList = null;
		}
	}
	const shareLabel = (key: string) =>
		sharingList === key ? 'Rendering…' : shareButtonLabel();

	const shareCsCard = () =>
		shareList('spl_cs', {
			title: 'RSL CLEAN SHEET OUTLOOK',
			subtitle: `next ${nearHorizon} GWs, GoalIQ match model`,
			nameLabel: 'TEAM',
			midLabel: 'FDR',
			valueLabel: 'CS%',
			fileName: 'goaliq_spl_clean_sheets.png',
			rows: teams.slice(0, 10).map((r, i) => ({
				rank: i + 1,
				name: r.t.name,
				tag: `${r.n}x`,
				team: '',
				mid: r.avgFdr < 99 ? r.avgFdr.toFixed(2) : '',
				value: r.avgCs != null ? `${Math.round(r.avgCs)}%` : ''
			}))
		});
	const shareValueCard = () =>
		shareList('spl_value', {
			title: 'RSL VALUE PICKS',
			// 🔴 3.9 (audit): `vpm` on xP PER KIERROS per miljoona, mutta kortti
			// otsikoi sen horisontin luvuksi ("next 6 GWs"). Luku on noin
			// kuudesosa siita mita kuvateksti lupasi. Sisarkortti
			// (differentials) teki taman oikein alusta asti.
			subtitle: 'xP per gameweek per million, GoalIQ model',
			midLabel: 'PRICE',
			valueLabel: 'xP/GW per £m',
			fileName: 'goaliq_spl_value.png',
			footNote: 'xP from the GoalIQ model, price from RSL Fantasy',
			rows: valuePicks.slice(0, 10).map(({ p, vpm }, i) => ({
				rank: i + 1,
				name: p.web_name,
				tag: p.pos,
				team: p.team_short,
				mid: p.price?.toFixed(1) ?? '',
				value: vpm.toFixed(2)
			}))
		});
	const shareDiffCard = () =>
		shareList('spl_diff', {
			title: 'RSL DIFFERENTIALS',
			subtitle: 'under 10% ownership, by xP per GW, GoalIQ model',
			midLabel: 'OWNED',
			valueLabel: 'xP/GW',
			fileName: 'goaliq_spl_differentials.png',
			rows: differentials.slice(0, 10).map((p, i) => ({
				rank: i + 1,
				name: p.web_name,
				tag: p.pos,
				team: p.team_short,
				mid: `${(p.owned_pct ?? 0).toFixed(1)}%`,
				value: p.xp_per_gw.toFixed(2)
			}))
		});
	const shareLeadersCard = () =>
		shareList('spl_leaders', {
			title: 'RSL FANTASY LEADERS',
			// 🔴 3.9 (audit): kausi oli kovakoodattu '2025/26'. Sama vika kuin
			// FPL:n Leaders-kortissa, joka sai basis-labelin datasta juuri siksi
			// etta kovakoodattu kausi vanheni hiljaa.
			//
			// 🔴 JA ENSIMMAINEN KORJAUKSENI OLI PAHEMPI: otin `meta.season`in,
			// joka on KULUVA kausi (2026/27). Nama rivit ovat `last_season`ista.
			// Label luetaan riveilta itseltaan, eli samasta paikasta kuin luvut.
			subtitle: `${leadersSeason ?? 'last season'} points, RSL Fantasy data`,
			midLabel: 'GOALS',
			valueLabel: 'PTS',
			fileName: 'goaliq_spl_leaders.png',
			// Toteutuneita pisteita, ei projektioita.
			footNote: 'season totals from RSL Fantasy',
			footNote2: 'not betting advice',
			rows: leaders('points')
				.slice(0, 10)
				.map((p, i) => ({
					rank: i + 1,
					name: p.web_name,
					tag: p.pos,
					team: p.team_short,
					mid: String(p.last_season?.goals ?? 0),
					value: String(p.last_season?.points ?? 0)
				}))
		});

	const POS_ROWS = ['GKP', 'DEF', 'MID', 'FWD'] as const;
	// 13.8 (Villen pyyntö): squad myös on-page-pitchinä, ei vain jakokorttina.
	// Sama toCardPlayer-muunnos kuin kortilla → pitch ja kortti eivät voi
	// ajautua eri lukuihin.
	let pitchRows = $derived(
		modelSquad
			? POS_ROWS.map((pos) =>
					modelSquad!.players.filter((p) => p.in_xi && p.pos === pos).map(toCardPlayer)
				).filter((row) => row.length > 0)
			: []
	);
	let pitchBench = $derived(
		modelSquad ? modelSquad.players.filter((p) => !p.in_xi).map(toCardPlayer) : []
	);
	function toCardPlayer(p: NonNullable<ModelSquad>['players'][number]): PitchCardPlayer {
		const { color, textColor } = teamColorByShort(p.team_short);
		return {
			name: p.web_name,
			team: p.team_short,
			color,
			textColor,
			xp: p.xp_per_gw.toFixed(1)
		};
	}
	let sharingSquad = $state(false);
	async function shareSquadCard() {
		if (!modelSquad || sharingSquad) return;
		sharingSquad = true;
		try {
			const squad = modelSquad;
			const xi = squad.players.filter((p) => p.in_xi);
			const method = await sharePitchCard({
				title: 'RSL MODEL SQUAD',
				subtitle:
					`${squad.cost.toFixed(1)}m of 100.0m, XI ${squad.xi_xp_horizon.toFixed(1)} xP ` +
					`next ${(xp?.meta?.horizon_gw as number) ?? 6} GWs, GoalIQ model`,
				unitNote: 'xP per GW under each name',
				fileName: 'goaliq_spl_model_squad.png',
				rows: POS_ROWS.map((pos) =>
					xi.filter((p) => p.pos === pos).map(toCardPlayer)
				).filter((row) => row.length > 0),
				bench: squad.players.filter((p) => !p.in_xi).map(toCardPlayer)
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'spl_squad', method });
		} finally {
			sharingSquad = false;
		}
	}

	/* Compare-lite: kaksi valintaa rinnakkain. */
	let cmpA = $state<number | null>(null);
	let cmpB = $state<number | null>(null);
	let cmpPlayers = $derived(
		[cmpA, cmpB]
			.map((id) => pool.find((p) => p.id === id))
			.filter((p): p is SplPlayer => !!p)
	);
</script>

<svelte:head>
	<title>Saudi Pro League fantasy tools | GoalIQ</title>
	<meta
		name="description"
		content="Free model-based tools for RSL Fantasy (Saudi Pro League): clean sheet probability, fixture difficulty and expected points from the GoalIQ match model."
	/>
	<!-- /spl-prerender (7.8): canonical tälle työkalusivulle itselleen —
	     goaliq.app/spl (staattinen landing) on erillinen sisältösivu joka
	     linkittää tänne, ei duplikaatti. -->
	<link rel="canonical" href="https://pro.goaliq.app/spl" />
	<!-- Prerenderoidulla reitillä boot-runko näkyisi sisällön YLLÄ kunnes
	     hydraatio poistaa sen — tällä reitillä sisältö on jo HTML:ssä,
	     joten runko piilotetaan heti. -->
	{@html '<style>#boot{display:none}</style>'}
</svelte:head>

<div class="shell">
	<header>
		<p class="crumb"><a href="/">← GoalIQ tools</a></p>
		<h1>Saudi Pro League <span class="accent">fantasy tools</span></h1>
		<p class="lede">
			Model-based tools for <strong>RSL Fantasy</strong>, the official Saudi Pro League fantasy
			game. Clean sheet probability, fixture difficulty and expected points from the same GoalIQ match
			model that powers our FPL toolkit. <strong>Completely free.</strong>
		</p>
		{#if deadline}
			<p class="deadline">
				GW{nextGw} deadline: {deadline.toUTCString().replace(':00 GMT', ' UTC')}
			</p>
		{/if}
		<div class="disclaimer">
			<p>
				GoalIQ is an independent data tool. We are not affiliated with, endorsed by, or paid by
				the Saudi Pro League, the RSL Fantasy game, or any club. These tools are free, so
				nobody is paying us to cover this league, including you.
			</p>
			<p class="basis">
				<strong>Data basis, stated plainly:</strong> team strengths come from a goals-based
				Dixon-Coles model fitted on two seasons of SPL results (no free per-match xG feed exists
				for this league). Player projections use realized goal and assist rates plus RSL Fantasy's
				own scoring rules; minutes are estimated from last season's aggregate playing time. This
				is coarser than our FPL pipeline and the confidence labels reflect that.
			</p>
		</div>
	</header>

	<section>
		<div class="head-row">
			<h2>Clean sheet % + fixture difficulty <span class="muted">(next {nearHorizon} GWs)</span></h2>
			{#if cs?.meta?.available && teams.length >= 3}
				<button type="button" class="share-btn" onclick={shareCsCard} disabled={sharingList !== null}>
					{shareLabel('spl_cs')}
				</button>
			{/if}
		</div>
		{#if csError}
			<p class="error">Could not reach the API. {csError}</p>
		{:else if !cs}
			<p class="muted">Loading…</p>
		{:else if !cs.meta.available}
			<p class="muted">SPL projections not published yet. Check back soon.</p>
		{:else}
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Team</th>
							<th class="num">avg CS%</th>
							<th class="num">avg FDR</th>
							<th>Fixtures</th>
						</tr>
					</thead>
					<tbody>
						{#each teams as { t, avgFdr, avgCs } (t.name)}
							<tr>
								<td>
									{t.name}
									<span class="muted">{(t as unknown as { short?: string }).short ?? ''}</span>
								</td>
								<td class="num">{avgCs == null ? '–' : avgCs.toFixed(1) + '%'}</td>
								<td class="num {fdrClass(avgFdr)}">{avgFdr === 99 ? '–' : avgFdr.toFixed(2)}</td>
								<td class="fixtures">
									{#each t.fixtures.filter((f) => f.gw >= nextGw && f.gw < nextGw + nearHorizon) as f (f.gw + f.opponent_short)}
										<!-- 11.8: kierrosnumero oli VAIN title-attribuutissa, eli
										     mobiilissa saavuttamaton. Ilman sita tyhjaa kierrosta ei
										     voi nahda sivulta: puuttuva GW nakyy vain siina etta
										     numerosarjassa on aukko (GW1 GW2 GW4 GW4 ...). Sama
										     vikaluokka kuin `varoitus-kaukana-luvusta`. -->
										<span class="chip {fdrClass(f.fdr)}" title="GW{f.gw}: {f.opponent} ({f.venue})">
											<span class="gw">GW{f.gw}</span>
											{f.opponent_short}
											{f.venue === 'H' ? '(H)' : '(A)'}{typeof f.cs_pct === 'number'
												? ` ${Math.round(f.cs_pct)}%`
												: ''}
										</span>
									{/each}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	{#if recon}
		<section>
			<h2>How our clean sheet calls have gone</h2>
			<p>
				Before every round kicks off the model puts a clean sheet probability on record
				for each side, and we keep the file that was published at the time. Over
				GW{recon.season_to_date.gameweeks[0]} to
				GW{recon.season_to_date.gameweeks[recon.season_to_date.gameweeks.length - 1]}
				that is {recon.season_to_date.sides} team-rounds across
				{recon.season_to_date.matches} matches. They add up to
				{recon.season_to_date.expected_cs} expected clean sheets, and
				{recon.season_to_date.actual_cs} happened. Brier score
				{recon.season_to_date.brier.toFixed(3)}, against
				{recon.season_to_date.naive_brier.toFixed(3)} for a flat guess at the clean sheet
				rate in the two completed seasons before this one
				({(recon.season_to_date.naive_p * 100).toFixed(1)}%). Lower is better, but
				{recon.season_to_date.sides} sides is a small sample and a gap that size is inside
				the noise. The archived files are in the public repo, one per round:
				<a
					href="https://github.com/GoalIQ/football-prediction/tree/main/data/spl_deadline_snapshots"
					rel="noopener">data/spl_deadline_snapshots</a
				>.
			</p>
			<!-- 3.9: kierroskohtainen erittely on osa rehellisyytta. Kauden luku
			     on mallin puolella, mutta se ei ole sita joka kierros, ja
			     yhteisluku yksin piilottaisi sen. -->
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Round</th>
							<th class="num">Sides</th>
							<th class="num">Expected CS</th>
							<th class="num">Actual</th>
							<th class="num">Brier</th>
							<th class="num">Flat guess</th>
						</tr>
					</thead>
					<tbody>
						{#each recon.gameweeks as g (g.gameweek)}
							<tr>
								<td>GW{g.gameweek}</td>
								<td class="num">{g.sides}</td>
								<td class="num">{g.expected_cs.toFixed(2)}</td>
								<td class="num">{g.actual_cs}</td>
								<td class="num" class:strong={g.brier < g.naive_brier}
									>{g.brier.toFixed(3)}</td
								>
								<td class="num">{g.naive_brier.toFixed(3)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="muted small">
				Bold means the model came in under the flat guess that round. Rounds do not all
				have nine matches: the league feed counts a postponed match in the round it is
				actually played, which is why the sides column moves. With 16 to 20 sides in a
				round, no single row here proves much.
			</p>
			<!-- 3.9: poikkeava kierros luetaan ARTEFAKTISTA. Kasin kirjoitettuna
			     ("GW2 is the outlier: nine against 4.77") lause olisi ollut tosi
			     tasan sen paivan ja jaanyt sivulle vaarana. Sama saanto kuin
			     lohkon muilla luvuilla. -->
			{#if outlierGw}
				<p class="muted small">
					GW{outlierGw.gameweek} is the outlier: {outlierGw.actual_cs} clean sheets
					against {outlierGw.expected_cs.toFixed(2)} expected.
					{#if outlierGw.brier < outlierGw.naive_brier}
						The model still came in under the flat guess that round, because it had the
						probability on the right sides even though the overall level was too low.
					{:else}
						It came in over the flat guess that round, so the level and the ordering
						were both off.
					{/if}
				</p>
			{/if}
			<h3>GW{recon.gameweek} match by match</h3>
			<p>The most recent round that finished.</p>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Match</th>
							<th class="num">Score</th>
							<th class="num">Home CS%</th>
							<th class="num">Away CS%</th>
							<th>Clean sheets</th>
						</tr>
					</thead>
					<tbody>
						{#each recon.fixtures as f (f.home + f.away)}
							<tr>
								<td>{f.home} v {f.away}</td>
								<td class="num">{f.score}</td>
								<td class="num" class:strong={f.cs_home_kept}>{f.cs_home_pct.toFixed(1)}%</td>
								<td class="num" class:strong={f.cs_away_kept}>{f.cs_away_pct.toFixed(1)}%</td>
								<td>
									{[f.cs_home_kept ? f.home_short : null, f.cs_away_kept ? f.away_short : null]
										.filter(Boolean)
										.join(', ') || 'none'}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="muted small">
				GW{recon.gameweek} on its own: Brier {recon.brier.toFixed(3)} against
				{recon.naive_brier.toFixed(3)} for the flat guess, over {recon.sides} sides. The
				probabilities come from the last projection build before this round kicked
				off{#if recon.snapshot?.generated_at}&nbsp;({recon.snapshot.generated_at.slice(0, 10)}){/if};
				they have not been recomputed since.
			</p>
		</section>
	{/if}

	<section>
		<div class="head-row">
			<h2>Expected points <span class="muted">(next {(xp?.meta?.horizon_gw as number) ?? 6} GWs, top 50)</span></h2>
			{#if xp?.meta?.available && players.length >= 3}
				<button type="button" class="share-btn" onclick={shareXpCard} disabled={sharingXp}>
					{sharingXp ? 'Rendering…' : shareButtonLabel()}
				</button>
			{/if}
		</div>
		{#if xpError}
			<p class="error">Could not reach the API. {xpError}</p>
		{:else if !xp}
			<p class="muted">Loading…</p>
		{:else if !xp.meta.available}
			<p class="muted">SPL xP not published yet. Check back soon.</p>
		{:else}
			<div class="posrow">
				{#each ['ALL', 'GKP', 'DEF', 'MID', 'FWD'] as pf (pf)}
					<button
						class:active={posFilter === pf}
						onclick={() => (posFilter = pf as PosFilter)}>{pf}</button
					>
				{/each}
			</div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Player</th>
							<th>Team</th>
							<th>Pos</th>
							<th class="num">Price</th>
							<th class="num">xP / GW</th>
							<th class="num">xMins</th>
							<th class="num">Total ({(xp?.meta?.horizon_gw as number) ?? 6} GW)</th>
						</tr>
					</thead>
					<tbody>
						{#each players as p (p.id)}
							<tr>
								<td>{p.web_name}</td>
								<td>{p.team_short}</td>
								<td>{p.pos}</td>
								<td class="num">{(p as unknown as { price?: number }).price?.toFixed(1) ?? '–'}</td>
								<td class="num strong">{p.xp_per_gw.toFixed(2)}</td>
								<td class="num">{p.xmins.toFixed(0)}</td>
								<td class="num">{p.xp_horizon_total.toFixed(1)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="muted small">
				Minutes confidence is "med" at best for this league: the RSL API exposes season totals,
				not per-round history. Players new to the league use price-based role priors until real
				minutes accumulate.
			</p>
		{/if}
	</section>

	{#if xp?.meta?.available}
		<section>
			<div class="head-row">
				<h2>Captain picks <span class="muted">(GW{nextGw})</span></h2>
				{#if captainPicks.length >= 3}
					<button type="button" class="share-btn" onclick={shareCaptainCard} disabled={sharingCaptain}>
						{sharingCaptain ? 'Rendering…' : shareButtonLabel()}
					</button>
				{/if}
			</div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>#</th><th>Player</th><th>Team</th><th>Pos</th>
							<th>Opponent</th><th class="num">GW{nextGw} xP</th>
						</tr>
					</thead>
					<tbody>
						{#each captainPicks as { p, gw1 }, i (p.id)}
							<tr>
								<td>{i + 1}</td>
								<td>{p.web_name}</td>
								<td>{p.team_short}</td>
								<td>{p.pos}</td>
								<td>
									{(p.gameweeks?.[0]?.opponents ?? [])
										.map((o) => `${o.opp} (${o.venue})`)
										.join(', ') || '–'}
								</td>
								<td class="num strong">{gw1.toFixed(2)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="muted small">
				Captain scores double in RSL Fantasy, so the ranking is simply the highest single-GW
				xP among players the model expects to start.
			</p>
		</section>

		{#if modelSquad}
			<section>
				<div class="head-row">
					<h2>The model squad <span class="muted">({modelSquad.cost.toFixed(1)}m of 100.0m)</span></h2>
					<button type="button" class="share-btn" onclick={shareSquadCard} disabled={sharingSquad}>
						{sharingSquad ? 'Rendering…' : shareButtonLabel()}
					</button>
				</div>
				<p class="muted small">
					{modelSquad.note} Starting XI in bold, projected XI total {modelSquad.xi_xp_horizon.toFixed(1)}
					xP over the next {(xp?.meta?.horizon_gw as number) ?? 6} GWs.
				</p>
				<SquadPitch rows={pitchRows} bench={pitchBench} unitNote="xP per GW" />
				<div class="table-wrap">
					<table>
						<thead>
							<tr><th>Pos</th><th>Player</th><th>Team</th><th class="num">Price</th><th class="num">xP / GW</th></tr>
						</thead>
						<tbody>
							{#each modelSquad.players as p (p.id)}
								<tr class:xi={p.in_xi}>
									<td>{p.pos}</td>
									<td class={p.in_xi ? 'strong' : ''}>{p.web_name}{p.in_xi ? '' : ' (bench)'}</td>
									<td>{p.team_short}</td>
									<td class="num">{p.price.toFixed(1)}</td>
									<td class="num">{p.xp_per_gw.toFixed(2)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</section>
		{/if}

		<section>
			<div class="head-row">
				<!-- 3.9 (audit): otsikko lupasi horisontin luvun, mutta `vpm` on
				     xP per KIERROS per miljoona. Sarakeotsikko sanoi sen jo
				     oikein ("xP / m" rivilla jossa on "xP / GW" vieressa), mutta
				     h2 luki toisin. -->
				<h2>Best value <span class="muted">(xP per gameweek per million)</span></h2>
				{#if valuePicks.length >= 3}
					<button type="button" class="share-btn" onclick={shareValueCard} disabled={sharingList !== null}>
						{shareLabel('spl_value')}
					</button>
				{/if}
			</div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr><th>Player</th><th>Team</th><th>Pos</th><th class="num">Price</th><th class="num">xP / GW</th><th class="num">xP / GW per &pound;m</th></tr>
					</thead>
					<tbody>
						{#each valuePicks as { p, vpm } (p.id)}
							<tr>
								<td>{p.web_name}</td>
								<td>{p.team_short}</td>
								<td>{p.pos}</td>
								<td class="num">{p.price?.toFixed(1) ?? '–'}</td>
								<td class="num">{p.xp_per_gw.toFixed(2)}</td>
								<td class="num strong">{vpm.toFixed(3)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="muted small">
				Players below 45 expected minutes are excluded: a good rate on tiny minutes is a bench
				risk, not a bargain.
			</p>
		</section>

		<section>
			<div class="head-row">
				<h2>Differentials <span class="muted">(under 10% ownership)</span></h2>
				{#if differentials.length >= 3}
					<button type="button" class="share-btn" onclick={shareDiffCard} disabled={sharingList !== null}>
						{shareLabel('spl_diff')}
					</button>
				{/if}
			</div>
			<div class="table-wrap">
				<table>
					<thead>
						<tr><th>Player</th><th>Team</th><th>Pos</th><th class="num">Owned</th><th class="num">Price</th><th class="num">xP / GW</th></tr>
					</thead>
					<tbody>
						{#each differentials as p (p.id)}
							<tr>
								<td>{p.web_name}</td>
								<td>{p.team_short}</td>
								<td>{p.pos}</td>
								<td class="num">{(p.owned_pct ?? 0).toFixed(1)}%</td>
								<td class="num">{p.price?.toFixed(1) ?? '–'}</td>
								<td class="num strong">{p.xp_per_gw.toFixed(2)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		<section>
			<div class="head-row">
				<h2>Last season's leaders <span class="muted">(2025/26, RSL Fantasy data)</span></h2>
				{#if leaders('points').length >= 3}
					<button type="button" class="share-btn" onclick={shareLeadersCard} disabled={sharingList !== null}>
						{shareLabel('spl_leaders')}
					</button>
				{/if}
			</div>
			<div class="leaders-grid">
				{#each [['goals', 'Goals'], ['assists', 'Assists'], ['points', 'Fantasy points']] as [key, label] (key)}
					<div>
						<h3>{label}</h3>
						<table>
							<tbody>
								{#each leaders(key as 'goals' | 'assists' | 'points') as p (p.id)}
									<tr>
										<td>{p.web_name} <span class="muted">{p.team_short}</span></td>
										<td class="num strong">{p.last_season?.[key as 'goals' | 'assists' | 'points']}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/each}
			</div>
		</section>

		<section>
			<h2>Compare two players</h2>
			<div class="cmp-row">
				{#each [0, 1] as slot (slot)}
					<!-- `?? ''` on pakollinen: cmpA/cmpB ovat `number | null`, ja null ei vastaa
					     yhtaan optionia -> selectedIndex = -1 ja kontrolli renderoituu TAYSIN
					     TYHJANA (mitattu tuotannosta 15.8). Placeholderin arvo on tyhja
					     merkkijono, joten null pitaa kaantaa siksi jotta "Pick player N…"
					     nakyy suljetussa kontrollissa. -->
					<select
						value={(slot === 0 ? cmpA : cmpB) ?? ''}
						onchange={(e) => {
							const v = Number((e.target as HTMLSelectElement).value) || null;
							if (slot === 0) cmpA = v;
							else cmpB = v;
							if (cmpA && cmpB) capture('spl_compare_used');
						}}
					>
						<option value="">Pick player {slot + 1}…</option>
						{#each pool.slice(0, 200) as p (p.id)}
							<option value={p.id}>{p.web_name} ({p.team_short}, {p.pos})</option>
						{/each}
					</select>
				{/each}
			</div>
			{#if cmpPlayers.length === 2}
				<div class="table-wrap">
					<table>
						<thead>
							<tr><th></th>{#each cmpPlayers as p (p.id)}<th>{p.web_name} ({p.team_short})</th>{/each}</tr>
						</thead>
						<tbody>
							<tr><td>Price</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.price?.toFixed(1) ?? '–'}</td>{/each}</tr>
							<tr><td>xP / GW</td>{#each cmpPlayers as p (p.id)}<td class="num strong">{p.xp_per_gw.toFixed(2)}</td>{/each}</tr>
							<tr><td>xP / 90</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.xp_per_90?.toFixed(2) ?? '–'}</td>{/each}</tr>
							<tr><td>Expected minutes</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.xmins.toFixed(0)}</td>{/each}</tr>
							<!-- 11.8: otsikot olivat kovakoodattu "25/26" mutta rivi renderoi
							     last_season-kentan riippumatta kaudesta. 535 pelaajasta 13:lla se on
							     2024/25 ja 7:lla 2023/24 (mm. nousijoiden pelaajat), joten sivu
							     valitti heidan kohdallaan kautta. Kausi nakyviin omalle riville. -->
							<tr><td>Season shown</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.last_season?.season ?? '–'}</td>{/each}</tr>
							<!-- 11.8: minuutit puuttuivat kokonaan. `last_season.minutes` tulee
							     API:sta mutta sita ei renderoitu missaan koko sivulla, joten
							     "2 maalia / 2732 minuuttia" -tyyppista vaitetta EI voinut
							     tarkistaa talta sivulta — ja rivi "Expected minutes" yllapuolella
							     nayttaa eri suureen (xmins ~82), joten lukija olisi katsonut
							     vaaraa lukua ja luullut tarkistaneensa. Maalit ilman minuutteja
							     on lisaksi harhaanjohtava pari: 2 maalia on eri asia 400 ja 2700
							     minuutissa. -->
							<tr><td>Minutes played</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.last_season?.minutes ?? '–'}</td>{/each}</tr>
							<tr><td>Goals</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.last_season?.goals ?? '–'}</td>{/each}</tr>
							<tr><td>Assists</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.last_season?.assists ?? '–'}</td>{/each}</tr>
							<tr><td>Fantasy points</td>{#each cmpPlayers as p (p.id)}<td class="num">{p.last_season?.points ?? '–'}</td>{/each}</tr>
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{/if}

	<section class="upsell">
		<h2>Play FPL too?</h2>
		<p>
			The same match model runs our full FPL toolkit: xP with a public accuracy log, transfer
			planner, captain ranker, live DefCon and more.
			<a href="/" onclick={() => capture('spl_to_fpl_clicked')}>Open the FPL tools</a>.
		</p>
	</section>

	<footer>
		<hr />
		<!-- Copy-sync 7.8 (OTA #3): SPL on nyt myös mobiilissa. -->
		<p class="muted">
			Also in the GoalIQ app:
			<a href="https://apps.apple.com/app/id6780047163">iOS</a> ·
			<a href="https://play.google.com/store/apps/details?id=com.veikkoville.goaliq">Android</a>
		</p>
		<p class="muted">{DISCLAIMER} · <a href="https://goaliq.app/privacy.html">Privacy</a></p>
	</footer>
</div>

<style>
	.shell {
		max-width: var(--shell);
		margin: 0 auto;
		padding: var(--s-4);
	}
	/* 8.8 jakokortit: sama chip-henki kuin FPL-työkalujen share-napeissa */
	.head-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--s-2);
		flex-wrap: wrap;
	}
	.share-btn {
		background: none;
		border: 1px solid var(--border);
		color: var(--text);
		font: inherit;
		font-size: 0.8rem;
		padding: 4px 10px;
		cursor: pointer;
	}
	.share-btn:hover:not(:disabled) {
		border-color: var(--accent);
	}
	.share-btn:disabled {
		opacity: 0.6;
	}
	.crumb {
		margin-bottom: var(--s-2);
	}
	h1 {
		margin: 0 0 var(--s-2);
	}
	.accent {
		color: var(--accent);
	}
	.lede {
		max-width: 60ch;
	}
	.deadline {
		font-weight: 600;
	}
	.disclaimer {
		border: 1px solid var(--border);
		border-left: 3px solid var(--accent);
		padding: var(--s-3);
		margin: var(--s-4) 0;
		font-size: 0.9em;
	}
	.disclaimer p {
		margin: 0 0 var(--s-2);
	}
	.disclaimer p:last-child {
		margin-bottom: 0;
	}
	section {
		margin-top: var(--s-8);
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		border-collapse: collapse;
		width: 100%;
	}
	th,
	td {
		text-align: left;
		padding: var(--s-1) var(--s-2);
		border-bottom: 1px solid var(--border);
		white-space: nowrap;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.strong {
		font-weight: 700;
	}
	.fixtures {
		white-space: normal;
	}
	.chip {
		display: inline-block;
		border: 1px solid var(--border);
		border-radius: 3px;
		padding: 0 var(--s-1);
		margin: 1px 2px;
		font-size: 0.8em;
	}
	/* 11.8: kierrosnumero chipin sisaan. Vaimennettu ja pienempi, jotta
	   vastustaja pysyy chipin paaasiana — numeron tehtava on tehda AUKOSTA
	   nakyva (tyhja kierros = puuttuva numero sarjassa), ei kilpailla nimen
	   kanssa. Ei omaa varia, jotta se ei riitele fdr-varituksen kanssa. */
	.chip .gw {
		opacity: 0.65;
		font-size: 0.85em;
		margin-right: 1px;
	}
	.is-easy {
		color: var(--ok, #2e7d32);
	}
	.is-hard {
		color: var(--bad, #c62828);
	}
	.posrow {
		display: flex;
		gap: var(--s-1);
		margin-bottom: var(--s-2);
	}
	.posrow button {
		background: none;
		border: 1px solid var(--border);
		border-radius: 3px;
		padding: var(--s-1) var(--s-2);
		cursor: pointer;
		color: inherit;
	}
	.posrow button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.upsell {
		border: 1px solid var(--border);
		padding: var(--s-3);
	}
	.leaders-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: var(--s-4);
	}
	.leaders-grid h3 {
		margin: 0 0 var(--s-1);
		font-size: 1em;
	}
	.cmp-row {
		display: flex;
		gap: var(--s-2);
		flex-wrap: wrap;
		margin-bottom: var(--s-2);
	}
	.cmp-row select {
		/* 🔴 14.8: tässä luki `background: none; color: inherit`, ja se teki
		   pudotusvalikosta LUKUKELVOTTOMAN. Suljettuna kontrolli näytti
		   oikealta, koska tumma sivu kuulsi läpi — mutta natiivi popup ei
		   peri sivun taustaa: selain maalaa sen valkoiseksi, ja `--text`
		   (#F3F2F2) valkoisella on näkymätön. Villen havainto.

		   Kaikki muut SPA:n selectit (CleanSheets, Fixtures, Leaders,
		   Predict, Standings, Value, Watchlist) asettavat nämä kaksi arvoa
		   eksplisiittisesti, ja theme.css:294 tekee saman globaalisti. Tämä
		   sivu oli ainoa joka kumosi ne. Älä palauta `none`/`inherit`:
		   ne eivät tarkoita "peri teema" vaan "anna selaimen päättää". */
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		padding: var(--s-1);
		max-width: 100%;
	}
	tr.xi td {
		border-bottom-color: var(--accent);
	}
	.small {
		font-size: 0.85em;
	}
	.error {
		color: var(--bad, #c62828);
	}
	footer {
		margin-top: var(--s-12);
	}
	hr {
		border: none;
		border-top: 1px solid var(--border);
		margin-bottom: var(--s-4);
	}
</style>
