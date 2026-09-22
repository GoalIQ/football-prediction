<script lang="ts">
	/**
	 * CleanSheets – CS%-matriisi GW-välivalitsimella. Web P1 (30.7):
	 * ekstraktoitu FreeView'sta omaksi komponentiksi, jotta yhdistetty
	 * 6 ryhmän ToolsHome voi renderöidä sen Players-ryhmässä.
	 *
	 * 22.9 (UX-uudistus A3 2.3, julkaisutarkistaja + Villen suositus): FDR
	 * POIS. Brief: tuotteen ydin on clean sheet % + xP + julkaistu track
	 * record, ei FDR:aa (virallinen FPL 26/27 tekee sen). Tama on nyt Players
	 * › Teams -nakyman "Choose your own gameweek range" -osio TeamsCs-
	 * ruudukon alla: sama CS% omalla kierrosvalilla. Valittavissa ovat vain
	 * mallinnetut kierrokset (`tier` near): kaukoriveilla ei ole CS%:a
	 * rakenteellisesti (27.7), ja ilman FDR:aa niissa ei olisi mitaan lukua.
	 */
	import { fetchFantasy, type FantasyResponse, type FantasyTeam } from '$lib/api';
	import { canShareToApps, shareCard, shareButtonLabel} from '$lib/shareCard';
	import { capture } from '$lib/analytics';
	import MethodNote from './MethodNote.svelte';

	let data = $state<FantasyResponse | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		fetchFantasy().then(
			(d) => (data = d),
			(e) => (error = String(e))
		);
	});

	/* 🔴 VARI JA LUKU SAMASTA ARVOSTA (30.8). Solu renderoi `Math.round(cs_pct)`
	   mutta luokka luettiin PYORISTAMATTOMASTA arvosta, joten 20,1 luki "20%"
	   ilman coralia samalla kun caption lupaa "20% or less". Sivulla sama vika
	   korjattiin `838ed2a1d`:ssa; SPA jai. Pyoristys tehdaan nyt KERRAN ja
	   molemmat lukevat saman luvun. */
	function csRounded(csPct: number): number {
		return Math.round(csPct);
	}
	function csCellClass(csPct: number): string {
		const v = csRounded(csPct);
		if (v >= 44) return 'is-easy';
		if (v <= 20) return 'is-hard';
		return '';
	}

	let nearHorizon = $derived(data?.meta?.near_horizon_gw ?? 6);
	/* Vain kierrokset joilla on mallin CS% (lahirivit). */
	let allGws = $derived(
		[
			...new Set(
				(data?.teams ?? []).flatMap((t) =>
					t.fixtures
						.filter((f) => (f.tier ?? 'near') === 'near' && typeof f.cs_pct === 'number')
						.map((f) => f.gw)
				)
			)
		].sort((a, b) => a - b)
	);
	let minGw = $derived(allGws[0] ?? 1);
	let maxGw = $derived(allGws[allGws.length - 1] ?? 1);

	let gwFrom = $state(0);
	let gwTo = $state(0);
	let rangeTouched = $state(false);

	$effect(() => {
		if (!rangeTouched && allGws.length) {
			gwFrom = minGw;
			gwTo = Math.min(minGw + nearHorizon - 1, maxGw);
		}
	});

	let gwCols = $derived(allGws.filter((g) => g >= gwFrom && g <= gwTo));

	type RangeAgg = {
		n: number;
		avgCs: number | null;
		allNear: boolean;
	};

	function rangeAgg(t: FantasyTeam): RangeAgg {
		const fx = t.fixtures.filter((f) => f.gw >= gwFrom && f.gw <= gwTo);
		if (!fx.length) return { n: 0, avgCs: null, allNear: false };
		const allNear = fx.every((f) => (f.tier ?? 'near') === 'near');
		const cs = fx.map((f) => f.cs_pct).filter((v): v is number => typeof v === 'number');
		return {
			n: fx.length,
			avgCs: allNear && cs.length === fx.length ? cs.reduce((s, v) => s + v, 0) / cs.length : null,
			allNear
		};
	}

	let sortKey = $state<'cs' | 'n' | 'name'>('cs');

	let sortedTeams = $derived.by(() => {
		const rows = (data?.teams ?? []).map((t) => ({ t, a: rangeAgg(t) }));
		rows.sort((x, y) => {
			if (x.a.n === 0 !== (y.a.n === 0)) return x.a.n === 0 ? 1 : -1;
			if (sortKey === 'name') return x.t.name.localeCompare(y.t.name);
			if (sortKey === 'n') return y.a.n - x.a.n;
			if (x.a.avgCs == null && y.a.avgCs == null) return 0;
			if (x.a.avgCs == null) return 1;
			if (y.a.avgCs == null) return -1;
			return y.a.avgCs - x.a.avgCs;
		});
		return rows;
	});

	/* 2.8: jakokortti myös FREE-datalle. #9a shipattiin 31.7 vain premium-
	 * listoille sillä perusteella että kortti on premium-datan johdannainen.
	 * Clean sheet -ennuste EI ole premiumia (FAQ: "Free: clean sheet
	 * probabilities, fixture difficulty ratings"), joten tässä ei ole mitään
	 * porttia – ja juuri free-datan jakaminen on se jakelusilmukka jonka
	 * haluamme: jakaja mainostaa meitä ilman että hän on maksanut. */
	let sharing = $state(false);

	/* Vain joukkueet joilla on mallinnettu CS% valitulla välillä.
	 * 6.8 laiteverify-pariteetti: kortin rivit AINA CS%-järjestyksessä UI-
	 * sortista riippumatta – muulla sortilla rank-numerot näyttivät CS-
	 * rankingilta = julkisena kuvana bugilta. */
	let shareRows = $derived(
		sortedTeams
			.filter((r) => r.a.avgCs != null)
			.toSorted((x, y) => (y.a.avgCs as number) - (x.a.avgCs as number))
			.slice(0, 10)
	);

	async function shareCs() {
		if (sharing || shareRows.length < 3) return;
		sharing = true;
		try {
			const method = await shareCard({
				title: 'CLEAN SHEET OUTLOOK',
				subtitle: `GW${gwFrom} to GW${gwTo}, GoalIQ match model`,
				nameLabel: 'TEAM',
				// 22.9: FDR pois (brief). Keskisarake on ottelumaara: tyhja GW = 0
				// ja tupla = 2 on FPL-pelaajalle olennaisin konteksti keskiarvon
				// vieressa.
				midLabel: 'GAMES',
				valueLabel: 'CS%',
				fileName: 'goaliq_clean_sheets.png',
				rows: shareRows.map((r, i) => ({
					rank: i + 1,
					name: r.t.name,
					tag: '',
					team: '',
					mid: String(r.a.n),
					value: `${Math.round(r.a.avgCs as number)}%`
				}))
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'clean_sheets', method });
		} finally {
			sharing = false;
		}
	}

</script>

{#if error}
	<p class="banner error">Could not load projections right now. Please try again shortly.</p>
{:else if !data}
	<div class="skeleton" aria-hidden="true">
		<p class="muted">Loading fixtures…</p>
		{#each Array(12) as _, i (i)}
			<div class="skel-row" style="width: {92 - (i % 4) * 6}%"></div>
		{/each}
	</div>
{:else if !data.meta?.available}
	<!-- 24.8 (GW1-STALE-COPY-2): lause lupasi projektiot "before Gameweek 1".
	     Haara laukeaa aina kun API sanoo available=false, ei vain esikaudella. -->
	<p class="banner success">Clean sheet projections are not available for this gameweek yet.</p>
{:else}
	<section class="tool-card">
		<h2>
			Clean sheet outlook, GW{gwFrom}-{gwTo}
		</h2>
		<p class="muted">
			Free · <strong>Avg CS%</strong> = the team's average chance of a clean sheet from the
			match model across the gameweeks you select, within the modelled window. Each GW cell
			shows opponent, venue and that fixture's clean sheet probability. Only the two ends
			are coloured: 44% or more reads gold, 20% or less reads coral, and everything between
			stays plain, so the colour marks a threshold and not a gradient.
		</p>

		<MethodNote summary="How these numbers are calculated">
			<p>
				<strong>Clean sheet probability</strong> is the GoalIQ match model's chance that the
				team concedes zero in that fixture. It comes from a Dixon-Coles score matrix
				(tau-corrected) fitted on match data, the same engine behind our published,
				pre-match logged track record.
			</p>
			<p>
				Projections refresh daily, including availability and injury flags. Model
				projections for fun and planning, not betting advice.
			</p>
		</MethodNote>

		<div class="gw-range">
			<label>
				<span class="muted">From GW</span>
				<select
					bind:value={gwFrom}
					onchange={() => {
						rangeTouched = true;
						if (gwTo < gwFrom) gwTo = gwFrom;
					}}
				>
					{#each allGws as g (g)}<option value={g}>{g}</option>{/each}
				</select>
			</label>
			<label>
				<span class="muted">to GW</span>
				<select
					bind:value={gwTo}
					onchange={() => {
						rangeTouched = true;
						if (gwFrom > gwTo) gwFrom = gwTo;
					}}
				>
					{#each allGws as g (g)}<option value={g}>{g}</option>{/each}
				</select>
			</label>
			<label>
				<span class="muted">Sort by</span>
				<select bind:value={sortKey}>
					<option value="cs">Best clean sheet %</option>
					<option value="n">Most fixtures</option>
					<option value="name">Team name</option>
				</select>
			</label>
			{#if rangeTouched && (gwFrom !== minGw || gwTo !== Math.min(minGw + nearHorizon - 1, maxGw))}
				<button
					type="button"
					class="gw-reset"
					onclick={() => {
						gwFrom = minGw;
						gwTo = Math.min(minGw + nearHorizon - 1, maxGw);
					}}>Reset</button
				>
			{/if}
		</div>


		{#if shareRows.length >= 3}
			<div class="share-row">
				<button type="button" class="gw-reset" onclick={shareCs} disabled={sharing}>
					{sharing
						? 'Rendering…'
						: shareButtonLabel()}
				</button>
			</div>
		{/if}

		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>Team</th>
						<th class="num"><abbr title="Chance of a clean sheet from the match model, averaged over the selected gameweeks.">Avg CS%</abbr></th>
						<th class="num m-hide"><abbr title="Fixtures in the selected range: 0 = blank gameweek, 2+ = double gameweek">Games</abbr></th>
						{#each gwCols as gw (gw)}
							<th class:is-far={gw > minGw + nearHorizon - 1} class:m-hide={gw > minGw + 1}>GW{gw}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each sortedTeams as { t, a } (t.name)}
						<tr class:is-blank={a.n === 0}>
							<td>{t.name}</td>
							<td class="num">{a.avgCs != null ? a.avgCs.toFixed(1) : '–'}</td>
							<td class="num m-hide">{a.n}</td>
							{#each gwCols as gw (gw)}
								<!-- 🔴 filter, EI find (30.8, FDR-GRID-DGW). `find` palautti doublesta
								     vain ensimmaisen ottelun, joten jalkimmainen KATOSI ruudukosta
								     samalla kun Games-sarake laski sen ja sarakkeen tooltip lupaa
								     "2+ = double gameweek". Solu lupasi siis vahemman kuin sen oma
								     otsikko. -->
								{@const fs = t.fixtures.filter((x) => x.gw === gw)}
								{#if fs.length}
									{@const csAll = fs.every((x) => typeof x.cs_pct === 'number')}
									<td
										class="cs-link-cell {fs.length === 1 && typeof fs[0].cs_pct === 'number'
											? csCellClass(fs[0].cs_pct)
											: ''}"
										class:m-hide={gw > minGw + 1}
										title={fs.map((x) => `${x.opponent ?? x.opponent_short} (${x.venue})`).join(' · ') +
											(fs.length > 1
												? ' · double gameweek, so the cell is left uncoloured: the two fixtures can pull in opposite directions'
												: '') +
											(csAll ? ' · view model prediction' : '')}
									>
										{#each fs as f, i (f.gw + '-' + (f.opponent_short ?? i))}
											{#if i > 0}<span class="dgw-sep"> + </span>{/if}
											{#if typeof f.cs_pct === 'number'}
												<a
													class="cs-cell-a"
													href="https://goaliq.app/predictions"
													target="_blank"
													rel="noopener"
												>
													{f.opponent_short} ({f.venue}) {csRounded(f.cs_pct)}%
												</a>
											{:else}
												{f.opponent_short} ({f.venue})
											{/if}
										{/each}
									</td>
								{:else}
									<td class="muted" class:m-hide={gw > minGw + 1}>Blank</td>
								{/if}
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/if}

<style>
	.gw-range {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-3);
		margin: var(--s-3) 0;
	}
	.gw-range label {
		display: inline-flex;
		align-items: center;
		gap: var(--s-2);
		font-size: var(--step--1);
	}
	.gw-range select {
		font: inherit;
		padding: 0.2em 0.4em;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
	}
	.share-row {
		display: flex;
		justify-content: flex-end;
		margin: 0 0 8px;
	}
	.gw-reset {
		font: inherit;
		font-size: var(--step--1);
		padding: 0.2em 0.7em;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: transparent;
		color: var(--text-muted);
		cursor: pointer;
	}
	th.is-far {
		opacity: 0.62;
		font-weight: 400;
	}
	tbody tr.is-blank {
		opacity: 0.55;
	}
	.skel-row {
		height: 34px;
		border-radius: var(--radius);
		background: var(--surface);
		border: 1px solid var(--border);
		margin: var(--s-2) 0;
	}
	.cs-link-cell {
		padding: 0;
	}
	.cs-cell-a {
		display: block;
		padding: 0.5em 0.75em;
		color: inherit;
		text-decoration: none;
	}
	.cs-cell-a:hover {
		background: rgba(243, 242, 242, 0.06);
	}
	:global(td.is-easy),
	:global(td.is-easy) .cs-cell-a {
		color: var(--accent-strong);
		font-weight: 600;
	}
	:global(td.is-hard),
	:global(td.is-hard) .cs-cell-a {
		color: var(--negative);
	}
	/* Doublen erotin: molemmat ottelut samassa solussa, jotta jalkimmainen
	   ei katoa (FDR-GRID-DGW). */
	.dgw-sep {
		opacity: 0.5;
	}
</style>
