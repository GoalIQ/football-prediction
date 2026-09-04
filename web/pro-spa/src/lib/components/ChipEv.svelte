<script lang="ts">
	// Edge-sprint kohta 6: chip-ajoituksen EV (premium). Renderöidään VAIN
	// gatatusta haarasta (ProTools). entry valinnainen: tallennettu/validi
	// entry → käyttäjän runko; ilman → mallin optimirunko (meta.mode=model_xi).
	// Esikaudella entry-picksit puuttuvat (404) → automaattinen fallback
	// mallirunkoon selitteellä. Basis-alaviite: GW7+ = team-level estimate.
	import { fetchChipEv, chipGwAllowed, type ChipEvResponse, type ChipWindow } from '$lib/fantasyTools';
	import { capture } from '$lib/analytics';
	import { canShareToApps, shareCard, shareButtonLabel} from '$lib/shareCard';
	import { fplEntry } from '$lib/fplEntry.svelte';
	import MethodNote from './MethodNote.svelte';
	import ModelWorking from './ModelWorking.svelte';

	const WORKING_STEPS = [
		'Loading model xP projections',
		'Scoring every remaining gameweek per chip',
		'Picking the best window for each chip'
	];

	const CHIPS = [
		{ key: 'wc', label: 'Wildcard', ev: (w: ChipWindow) => w.wc_ev },
		{ key: 'bb', label: 'Bench Boost', ev: (w: ChipWindow) => w.bb_ev },
		{ key: 'tc', label: 'Triple Captain', ev: (w: ChipWindow) => w.tc_ev },
		{ key: 'fh', label: 'Free Hit', ev: (w: ChipWindow) => w.fh_ev }
	] as const;

	let loading = $state(false);
	let error = $state<string | null>(null);
	let data = $state<ChipEvResponse | null>(null);
	/** Selite kun entry annettiin mutta picksit eivät vielä julki (pre-GW1). */
	let entryFallback = $state(false);
	/** true vain kun backend nimesi syyn (picks_not_published). Muut viat
	 *  saavat neutraalin selitteen: kortti ei saa arvata syytä. */
	let fallbackPicks = $state(false);

	let entryValid = $derived(/^\d{1,10}$/.test(fplEntry.entry.trim()));

	async function load() {
		if (loading) return;
		loading = true;
		error = null;
		entryFallback = false;
		fallbackPicks = false;
		try {
			if (entryValid) {
				try {
					data = await fetchChipEv(Number(fplEntry.entry.trim()));
				} catch (err) {
					// 24.8 (portti): tämä oli PALJAS catch, ja teksti alla väitti
					// syyn faktana ("because FPL publishes squads only after the
					// GW1 deadline"). Mikä tahansa vika — kirjoitusvirhe ID:ssä,
					// 500, verkkokatko — sai käyttäjän lukemaan väärän selityksen.
					// Kausisidonnaisuuden korjaaminen olisi tehnyt tilapäisesti
					// väärästä selityksestä pysyvästi väärän, joten syy luetaan
					// nyt koodista kuten RateTeam.svelte:159 tekee.
					data = await fetchChipEv(null);
					entryFallback = true;
					fallbackPicks = (err as { code?: string })?.code === 'picks_not_published';
				}
			} else {
				data = await fetchChipEv(null);
			}
			capture('chip_ev_viewed', { source: 'pro_spa', mode: data?.meta?.mode ?? 'unknown' });
		} catch (err) {
			data = null;
			error = err instanceof Error ? err.message : String(err);
		}
		loading = false;
	}

	// Autoload kerran kun osio avataan (entry-kenttä ei ole pakollinen).
	let started = $state(false);
	$effect(() => {
		if (!started) {
			started = true;
			void load();
		}
	});

	// CHIP-EV-CHIPS-USED (3.9): pelattu chip ei ole tarjolla samalla
	// puolikkaalla. Rivi jota ei voi pelata ei saa nakya listalla, ja kortti
	// sanoo miksi paras puuttuu ("Played in GW2, next window from GW20").
	function chipState(key: string) {
		return data?.chips?.state?.[key as 'wc' | 'bb' | 'tc' | 'fh'];
	}
	function playedLine(key: string): string | null {
		const st = chipState(key);
		if (!st || st.available_now) return null;
		const next = st.windows.find((w) => w.available);
		const played = st.played_gws.at(-1);
		const head = played != null ? `Played in GW${played}.` : 'Not available in this half.';
		return next ? `${head} Next window opens in GW${next.start_gw}.` : `${head} No window left this season.`;
	}

	function top3(chip: (typeof CHIPS)[number]): ChipWindow[] {
		if (!data) return [];
		// 🔴 `null` on "emme anna lukua", ei nolla. Wildcardilla ei ole lukua
		// horisontin ulkopuolella, ja `null`-rivin lajittelu nollana nostaisi
		// sen listalle numerona jota ei ole.
		return [...data.windows]
			.filter((w) => chip.ev(w) != null && chipGwAllowed(chipState(chip.key), w.gw))
			.sort((a, b) => (chip.ev(b) as number) - (chip.ev(a) as number))
			.slice(0, 3);
	}

	// SHARE-CARD-SPA 27.8: jokaisen chipin paras ikkuna yhdella kortilla.
	// Kortti nayttaa VAIN sen mita sivulla on (top3()[0] per chip), ja jos
	// wildcardin luku on horisontin ulkopuolella (null) rivi jaa pois.
	let sharing = $state(false);
	async function shareChips() {
		if (sharing || !data) return;
		sharing = true;
		try {
			// JULKAISUPORTTI 27.8: sama lahde kuin sivun pillerilla (`data.best`,
			// backend poimii vain player_xp-riveilta), EI oma top3()-lajittelu
			// joka nostaisi team_approx-rivit (25.8 korjattu regressio). Rivit
			// EV-jarjestyksessa (rivi 1 = hero-kehys), etumerkki ja "est." kuten
			// sivulla, ja WINDOW aina taytetty: wildcard on kumulatiivinen, muut
			// yhden kierroksen lukuja, eika niita saa lukea rinnakkain ilman sita.
			const best = data.best ?? {};
			const rows = CHIPS.flatMap((chip) => {
				const b = best[chip.key];
				if (!b) return [];
				return [
					{
						ev: b.ev,
						name: chip.label,
						tag: `GW${b.gw}`,
						team: '',
						mid: chip.key === 'wc' && b.window_gws ? `over ${b.window_gws} GW${b.window_gws === 1 ? '' : 's'}` : 'one GW',
						value: `${b.ev > 0 ? '+' : ''}${b.ev.toFixed(1)}`
					}
				];
			})
				.sort((a, b) => b.ev - a.ev)
				.map(({ ev: _ev, ...r }, i) => ({ rank: i + 1, ...r }));
			if (rows.length === 0) return;
			const basis = data.meta?.mode === 'model_xi' ? "the model's squad" : 'your squad';
			const method = await shareCard({
				title: 'BEST CHIP WINDOWS',
				// Kierros 2: EV-jarjestys rinnastaa wildcardin monen GW:n summan yhden
				// kierroksen lukuihin, joten se sanotaan alaotsikossa.
				subtitle: `${basis}, best gameweek per chip (Wildcard is a multi-GW total)`,
				nameLabel: 'CHIP',
				midLabel: 'WINDOW',
				valueLabel: 'xP est.',
				fileName: 'goaliq_chip_timing.png',
				rows
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'chips', method });
		} finally {
			sharing = false;
		}
	}
	let hasTeamApprox = $derived(
		data?.windows?.some((w) => w.basis !== 'player_xp') ?? false
	);
</script>

<div class="head-row">
	<h2>Chip timing: expected value per gameweek</h2>
	{#if data && Object.keys(data.best ?? {}).length > 0}
		<button type="button" class="window-chip" onclick={shareChips} disabled={sharing}>
		{sharing ? 'Rendering…' : shareButtonLabel()}
		</button>
	{/if}
</div>
<p class="muted">
	When to play Wildcard, Bench Boost, Triple Captain and Free Hit: each remaining gameweek
	gets a rough expected-value estimate per chip, and the best window is highlighted.
	{#if data?.meta?.mode === 'model_xi'}Based on the strongest squad our search found{#if entryFallback},
			because {fallbackPicks
				? "your entry's picks are not public yet (it will be used once they are)"
				: 'your entry could not be loaded just now'}{/if}.{:else if data?.meta?.entry != null}Based on your squad (entry
		{data.meta.entry}).{/if}
</p>

<form
	class="chip-form"
	onsubmit={(e) => {
		e.preventDefault();
		void load();
	}}
>
	<div>
		<label for="chip-entry">FPL entry ID (optional)</label>
		<input
			id="chip-entry"
			inputmode="numeric"
			autocomplete="off"
			placeholder="e.g. 1234567"
			bind:value={fplEntry.entry}
		/>
	</div>
	<button class="primary" type="submit" disabled={loading}>
		{loading ? 'Estimating…' : 'Recalculate'}
	</button>
</form>

{#if loading}
	<ModelWorking steps={WORKING_STEPS} />
{/if}

{#if error}
	<p class="banner error">{error}</p>
{:else if data}
	<div class="chip-grid">
		{#each CHIPS as chip (chip.key)}
			{@const best = data.best?.[chip.key]}
			<!-- 🔴 EI castia. Cast `as 'bb'|'tc'|'fh'` vaitti tyypissa ettei `chip.key`
			     voi olla `'wc'`, vaikka voi — se piilotti juuri sen invariantin jonka
			     mobiili sanoo aareen. Wildcardille EI ole karkeaa arviota, koska sen
			     rivi on `null` horisontin ulkopuolella. -->
			{@const est = chip.key === 'wc' ? undefined : data.best_estimate?.[chip.key]}
			<div class="chip-card card">
				<div class="chip-head">
					<h3>{chip.label}</h3>
					{#if best && typeof best.gw === 'number'}
						<span class="best-pill">Best: GW{best.gw}</span>
					{:else if playedLine(chip.key)}
						<span class="best-pill played">Played</span>
					{/if}
				</div>
				{#if playedLine(chip.key)}
					<p class="est-line">{playedLine(chip.key)}</p>
				{/if}
				{#if best && typeof best.ev === 'number'}
					<p class="best-ev">
						<span class="ev-num">{best.ev > 0 ? '+' : ''}{best.ev.toFixed(1)}</span>
						<span class="ev-unit">xP est.</span>
						{#if best.window_gws != null}
						<!-- 🔴 Kumulatiivinen luku sanoo mita se kattaa, LUVUN
						     VIERESSA. Ilman tata lukija vertaa 6 kierroksen
						     summaa naapurirumman yhden kierroksen lukuun. -->
						<span class="window-note">over {best.window_gws} GWs</span>
					{/if}
					{#if best.basis && best.basis !== 'player_xp'}
							<span class="basis-mark" title="Team-level estimate beyond the player-projection horizon">*</span>
						{/if}
					</p>
				{/if}
				<!-- 🔴 KARKEA ARVIO RENDERÖIDÄÄN. Ilman tätä selite lupasi että se
				     "raportoidaan erikseen", mutta se eli vain API-vastauksessa —
				     ja raaka JSON ei ole tarkistusreitti vaan este. -->
				{#if est}
					<p class="est-line">
						Rougher estimate GW{est.gw}: {est.ev > 0 ? '+' : ''}{est.ev.toFixed(1)} xP
					</p>
				{/if}
				<table class="chip-top3">
					<tbody>
						{#each top3(chip) as w (w.gw)}
							<tr>
								<td>GW{w.gw}{#if w.basis !== 'player_xp'}<span
											class="basis-mark"
											title="Team-level estimate beyond the player-projection horizon">*</span
										>{/if}</td>
								<td class="num"
									>{(chip.ev(w) as number) > 0 ? '+' : ''}{(chip.ev(w) as number).toFixed(1)}<!--
									-->{#if chip.key === 'wc' && w.wc_window_gws != null}<span
											class="window-note">over {w.wc_window_gws} GWs</span
										>{/if}</td
								>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/each}
	</div>
	{#if hasTeamApprox}
		<p class="muted basis-note">
			<!-- 🔴 ALAVIITE VÄITTI KAIKISTA horisontin ulkopuolisista kierroksista
			     että ne käyttävät joukkuetason arviota. Wildcardille se on epätosi:
			     rivi on `null` ja `top3()` suodattaa sen pois, joten lukija näkisi
			     Wildcard-kortin ilman yhtään tähdellistä riviä ja alaviitteen joka
			     lupaa niitä olevan. -->
			* Beyond GW{(data.meta.horizon_gws?.at(-1) ?? 6) + 1}, the Bench Boost, Triple
			Captain and Free Hit rows use a team-level estimate from full-season fixture
			quality. Treat those windows as rougher. Wildcard has no rows out there.
		</p>
	{/if}
	<MethodNote summary="How chip EV is estimated (and its limits)">
		{#if data.meta.notes && data.meta.notes.length > 0}
			{#each data.meta.notes as n (n)}
				<p>{n}</p>
			{/each}
		{/if}
		<!-- 🔴 KUOLLUT FALLBACK POISTETTU. Se renderöityi vain jos `meta.notes`
		     on tyhjä, mitä se ei koskaan ole, ja se sanoi yhä "beyond that from
		     team-level fixture quality" myös wildcardista. Lipun takana oleva
		     copy näyttää hoidetulta eikä vanhene kenenkään silmissä. -->
	</MethodNote>
{/if}

<style>
	.chip-form {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-3);
		align-items: end;
		margin-bottom: var(--s-4);
	}
	.chip-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: var(--s-4);
		margin-bottom: var(--s-3);
	}
	.chip-card {
		padding: var(--s-4);
	}
	.chip-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--s-2);
	}
	.best-pill.played {
		opacity: 0.75;
	}
	.chip-head h3 {
		margin: 0;
		font-size: var(--step-0);
	}
	.best-pill {
		background: rgba(255, 138, 92, 0.1);
		border: 1px solid rgba(255, 138, 92, 0.35);
		color: var(--giq-rust);
		border-radius: var(--radius);
		padding: 1px 10px;
		font-size: var(--step--1);
		font-weight: 700;
		white-space: nowrap;
	}
	.best-ev {
		margin: var(--s-2) 0 var(--s-2);
		color: var(--giq-rust);
		font-weight: 700;
		line-height: 1;
	}
	/* isot luvut = display-fontti (theme.css-sääntö: Space Grotesk vain
	   otsikot/brändi/isot luvut) */
	.ev-num {
		font-family: var(--font-display);
		font-size: var(--step-2);
		font-variant-numeric: tabular-nums;
	}
	.ev-unit {
		font-size: var(--step--1);
		margin-left: 2px;
	}
	.chip-top3 {
		font-size: var(--step--1);
	}
	.chip-top3 td {
		padding: 0.3em 0.5em 0.3em 0;
		border-bottom: none;
	}
	.basis-mark {
		color: var(--warn-text);
		font-weight: 700;
		margin-left: 2px;
		cursor: help;
	}
	.est-line {
		margin: 2px 0 6px;
		font-size: 0.75rem;
		opacity: 0.7;
	}
	.window-note {
		font-size: 0.72rem;
		opacity: 0.75;
		margin-left: 4px;
	}
	.basis-note {
		margin-top: 0;
	}

	/* SHARE-CARD-SPA 27.8: sama chip kuin muissa jaettavissa listoissa */
	.head-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--s-2);
		flex-wrap: wrap;
	}
	.head-row h2 {
		margin: 0;
	}
	.window-chip {
		flex: 0 0 auto;
		min-width: 36px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text-muted);
		font-weight: 700;
		font-size: var(--step--1);
		padding: 4px 12px;
		cursor: pointer;
		text-align: center;
		white-space: nowrap;
		line-height: 1.4;
	}
</style>
