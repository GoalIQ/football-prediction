<script lang="ts">
	import { fetchPlan, fetchPlanDraft, type PlanResponse } from '$lib/fantasyTools';
	import { runWithSquadFallback, NoSquadInputError, savedDraft15, type SquadBasis } from '$lib/squadInput';
	import { fplEntry, persistEntry } from '$lib/fplEntry.svelte';
	import HoldVerdictCard from './HoldVerdictCard.svelte';
	import { capture } from '$lib/analytics';
	import { canShareToApps, shareCard, shareButtonLabel} from '$lib/shareCard';
	import MethodNote from './MethodNote.svelte';
	import ModelWorking from './ModelWorking.svelte';

	// #73: lataustilan askeleet = putken oikeat vaiheet (rehellinen checklist)
	const WORKING_STEPS = [
		'Fetching your FPL squad',
		'Loading model xP projections',
		'Simulating each gameweek in your horizon',
		'Weighing transfers against hits and holding'
	];

	const HORIZONS = [2, 3, 4, 5, 6] as const;
	const FTS = [0, 1, 2, 3, 4, 5] as const;

	// #66: entry-kenttä on jaettu RateTeamin kanssa (fplEntry.entry) - yksi
	// entry-ID koko työkalusetille; kirjautuneena tallennettu ID esitäyttää.
	// 28.8: oletus 6 = xP-artefaktin ja mallin oman rungon horisontti. Kolmella
	// planner vastasi eri kysymykseen kuin freeze (PLANNER-FREEZE-DIVERGENCE).
	let horizon = $state(6);
	let ft = $state(1);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let data = $state<PlanResponse | null>(null);
	/** PI-16b: mistä runko tuli. 'draft' = FPL ei ole vielä julkaissut
	 *  kokoonpanoja ja suunnitelma ajettiin tallennetulla 15:llä. */
	let basedOn = $state<SquadBasis>('entry');
	/** Esikausi ilman tallennettua draftia: ohjaus, ei virhe. */
	let needsDraft = $state(false);
	/** 28.8 (julkaisuportti): stale-tilassa entry-kutsu ONNISTUU, joten
	 *  runWithSquadFallbackin draft-polku ei laukea. Tallennettu 15 on
	 *  silti kaytettavissa; kayttaja valitsee sen napilla, ei lupauksella. */
	let hasSavedDraft = $state(false);
	/** Miksi suunnitelma on draft-pohjainen: FPL ei ole julkaissut runkoa
	 *  lainkaan (esikausi) vai naytti edellisen kierroksen rungon (stale). */
	let draftReason = $state<'not_public' | 'stale'>('not_public');
	let stale = $derived(
		data?.meta.squad_source?.stale === true &&
			typeof data.meta.squad_source.gw === 'number'
	);
	let staleNext = $derived(
		typeof data?.meta.squad_source?.deadline_gw === 'number'
			? data.meta.squad_source.deadline_gw
			: (data?.meta.squad_source?.gw ?? 0) + 1
	);
	async function useSavedDraft() {
		const ids = savedDraft15();
		if (!ids || loading) return;
		loading = true;
		error = null;
		try {
			data = await fetchPlanDraft(ids, horizon, ft);
			basedOn = 'draft';
			draftReason = 'stale';
			capture('planner_stale_draft_used', { source: 'pro_spa', horizon });
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		}
		loading = false;
	}

	let entryValid = $derived(/^\d{1,10}$/.test(fplEntry.entry.trim()));

	// SHARE-CARD-SPA 27.8: HOLD-verdikti on charterin #1 jaettava hetki
	// ("the model told me to hold"). Otsikko on mallin kanta, rivit ovat
	// suunnitelma sellaisenaan: siirto per rivi hitin kanssa, tai hold +
	// kapteeni kierroksilla joilla ei siirreta. Luvut samat kuin sivulla.
	let sharing = $state(false);
	async function sharePlan() {
		if (sharing || !data) return;
		sharing = true;
		try {
			const v = data.hold_verdict;
			// JULKAISUPORTTI 27.8: yksi suure per kortti (siirtorivit = gain vs
			// hold, 2 desimaalia kuten HoldVerdictCard; hold-kierrokset = GW-
			// kokonais-xP vain kun siirtoja ei ole lainkaan), max 12 rivia
			// (6 GW x 2 siirtoa), verdiktin gain 2 desimaalilla ettei kortti
			// voi pyoristaa itsensa kynnyksen vaaralle puolelle.
			const moves: { rank: number; name: string; tag: string; team: string; mid: string; value: string }[] = [];
			for (const g of data.plan) {
				for (const tr of g.transfers) {
					moves.push({
						rank: moves.length + 1,
						name: `${tr.out.web_name} to ${tr.in.web_name}`,
						tag: `GW${g.gw}`,
						team: tr.in.team_short,
						mid: tr.hit ? `-${tr.hit}` : '',
						value: `${tr.gain_xp_remaining >= 0 ? '+' : ''}${tr.gain_xp_remaining.toFixed(2)}`
					});
				}
			}
			// Kierros 2: verdikti voi olla `hold` vaikka plan sisaltaa siirtoja
			// (fpl_planner: hold jos net_gain < kynnys) -> HOLD-kortti ei saa
			// listata siirtoja. Ja best_move_gain_xp on KOKO suunnitelman hyoty
			// (plan_total - baseline_total), joten se sanotaan "best plan", ei
			// "best move". (HoldVerdictCard.svelte:35 sanoo yha "Best available
			// move" -> oma jonorivi + mobiilipariteetti.)
			const allHold = v?.verdict === 'hold' || moves.length === 0;
			const rows = allHold
				? data.plan.map((g, i) => ({
						rank: i + 1,
						name: `Hold, captain ${g.captain.web_name}`,
						tag: `GW${g.gw}`,
						team: '',
						mid: 'GW total',
						value: g.gw_xp.toFixed(1)
					}))
				: moves;
			let subtitle: string;
			if (v) {
				const gain =
					v.best_move_gain_xp === null
						? null
						: `${v.best_move_gain_xp >= 0 ? '+' : ''}${v.best_move_gain_xp.toFixed(2)}`;
				// 29.8: plannerin payloadissa ei ole hit_applied_xp:ta lainkaan (kentat:
				// verdict, best_move_gain_xp, horizon_gws, threshold_xp,
				// transfers_planned, hits_taken, message), joten hit-nootti ei
				// renderoitynyt koskaan talla kortilla. HoldVerdictCard ja mobiilin
				// jakokortti lukevat jo hits_taken:ia; tama yksi jai.
				// 29.8 portti k7: subtitle nimeaa kierrokset, ei kierrosmaaraa.
				const vSpan = (x: { gw_from?: number | null; gw_to?: number | null; horizon_gws: number }) =>
					x.gw_from != null && x.gw_to != null
						? x.gw_from === x.gw_to
							? `GW${x.gw_from}`
							: `GW${x.gw_from}-GW${x.gw_to}`
						: `the ${x.horizon_gws}-GW horizon`;
				const hitsN = v.hits_taken ?? (v.hit_applied_xp ? 1 : 0);
				const hit =
					hitsN === 0 ? '' : hitsN === 1 ? ', after a -4 hit' : `, after ${hitsN} hits (-${hitsN * 4} xP)`;
				const nMoves = v.transfers_planned ?? moves.length;
				const plan = `best plan the model checked (${nMoves} ${nMoves === 1 ? 'move' : 'moves'})`;
				if (v.verdict === 'hold') {
					subtitle =
						gain === null
							? `nothing the model checked improves the squad over ${vSpan(v)}`
							: `${plan} ${gain} xP over ${vSpan(v)}, under the ${v.threshold_xp.toFixed(1)} threshold${hit}`;
				} else {
					subtitle = `${plan} ${gain} xP over ${vSpan(v)}, clears the ${v.threshold_xp.toFixed(1)} threshold${hit}`;
				}
			} else {
				const net = `${data.totals.net_gain >= 0 ? '+' : ''}${data.totals.net_gain.toFixed(1)}`;
				subtitle = `${net} xP vs no transfers over the ${data.meta.horizon}-GW horizon`;
			}
			const method = await shareCard({
				title: v ? (v.verdict === 'hold' ? 'THE MODEL SAYS HOLD' : 'THE MODEL SAYS MOVE') : 'TRANSFER PLAN',
				subtitle,
				nameLabel: 'MOVE',
				midLabel: allHold ? '' : 'HIT',
				valueLabel: allHold ? 'xP' : 'xP GAIN',
				fileName: 'goaliq_hold_verdict.png',
				rows: rows.slice(0, 12)
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'planner', method });
		} finally {
			sharing = false;
		}
	}
	async function build(e: SubmitEvent) {
		e.preventDefault();
		if (!entryValid || loading) return;
		loading = true;
		error = null;
		needsDraft = false;
		try {
			const id = Number(fplEntry.entry.trim());
			// PI-16b (28.7): esikaudella entry-polku EI VOI onnistua, koska FPL
			// julkaisee kokoonpanot vasta GW1-deadlinen jälkeen. Sama työ tehdään
			// tallennetulla draftilla; backend on tukenut players-moodia alusta asti.
			const run = await runWithSquadFallback(
				id,
				(entry) => fetchPlan(entry, horizon, ft),
				(ids) => fetchPlanDraft(ids, horizon, ft)
			);
			data = run.data;
			basedOn = run.basedOn;
			draftReason = 'not_public';
			hasSavedDraft = savedDraft15() !== null;
			void persistEntry(id); // #66: talteen vasta onnistuneesta hausta
		} catch (err) {
			data = null;
			if (err instanceof NoSquadInputError) {
				needsDraft = true;
			} else {
				error = err instanceof Error ? err.message : String(err);
			}
		}
		loading = false;
	}
</script>

<h2>Transfer planner</h2>
<p class="muted">
	A multi-gameweek transfer plan built on the same xP projections as the table above. Pick
	your horizon and how many free transfers you have banked.
</p>

<form class="plan-form" onsubmit={build}>
	<div>
		<label for="plan-entry">FPL entry ID</label>
		<input
			id="plan-entry"
			inputmode="numeric"
			autocomplete="off"
			placeholder="e.g. 1234567"
			bind:value={fplEntry.entry}
		/>
	</div>
	<div>
		<label for="plan-horizon"
			><abbr title="How many upcoming gameweeks the plan covers">Horizon</abbr> (GWs)</label
		>
		<select id="plan-horizon" bind:value={horizon}>
			{#each HORIZONS as h (h)}
				<option value={h}>{h}</option>
			{/each}
		</select>
	</div>
	<div>
		<label for="plan-ft">Free transfers</label>
		<select id="plan-ft" bind:value={ft}>
			{#each FTS as f (f)}
				<option value={f}>{f}</option>
			{/each}
		</select>
	</div>
	<button class="primary" type="submit" disabled={!entryValid || loading}>
		{loading ? 'Planning…' : 'Build plan'}
	</button>
</form>

{#if loading}
	<!-- #73: malli tekee töitä -progressiivinen paljastus -->
	<ModelWorking steps={WORKING_STEPS} />
{/if}

{#if needsDraft}
	<!-- PI-16b: kalenterin tila, ei käyttäjän virhe → neutraali selite eikä
	     punainen virhelaatikko. Toimiva polku nimetään suoraan. -->
	<p class="notice-preseason">
		<strong>Your squad is not public yet.</strong> FPL keeps a team private until the first
		deadline it plays. Until then, draft your 15 in Rate my team and this planner runs on
		that draft.
	</p>
{:else if error}
	<p class="banner error">{error}</p>
{:else if data}
	{#if basedOn === 'draft'}
		<p class="notice-preseason">
			{#if draftReason === 'stale'}
				Based on your saved draft of 15. FPL still shows the GW{data.meta.squad_source?.gw} squad for this entry.
			{:else}
				Based on your saved draft of 15, because your squad is not public yet.
			{/if}
		</p>
	{:else if stale}
		<!-- 28.8 (PLANNER-FREEZE-DIVERGENCE + julkaisuportti): FPL julkaisee
		     kierroksen siirrot vasta deadlinen jalkeen, joten entry-polku
		     suunnittelee EDELLISEN kierroksen rungosta. Ehto ja deadline_gw
		     tulevat backendista (meta.squad_source), sama lahde kuin
		     rate-teamin picks_outdated. Draft-polku on NAPPI, ei lupaus:
		     stale-tilassa entry-kutsu onnistuu eika fallback laukea. -->
		<p class="notice-preseason">
			<strong>This plan starts from your GW{data.meta.squad_source?.gw} squad.</strong>
			FPL publishes GW{staleNext} squads a while after the deadline, so any transfers you
			already made aren't in it.
			{#if hasSavedDraft}
				Your saved 15 from Rate my team is here if that's closer to your team now.
				<button type="button" class="window-chip" onclick={useSavedDraft} disabled={loading}>
					Use my saved 15
				</button>
			{:else}
				Run this again once yours is public on the FPL site. In the meantime Rate my team
				scores a hand-picked 15.
			{/if}
		</p>
	{/if}
	<!-- #63: mallin kanta ensin (hold vs transfer, xP-matikka näkyvissä),
	     suunnitelman yksityiskohdat vasta sen jälkeen -->
	{#if data.hold_verdict}
		<div class="verdict-slot">
			<HoldVerdictCard verdict={data.hold_verdict} surface="planner" />
			{#if data.plan.length < data.meta.horizon}
				<!-- Portti 29.8: ilmaismaski leikkaa plan-listan yhteen GW:hen mutta
				     hero laskee koko horisontin siirrot. Sanotaan se, jotta luku ei
				     lupaa siirtoja joita lukija ei nae. -->
				<p class="muted">
					Free preview shows the first gameweek only. The full {data.meta.horizon}-GW plan is
					Premium.
				</p>
			{/if}
		</div>
	{/if}
	<div class="head-row">
		<span class="muted">Share the model's call</span>
		<button type="button" class="window-chip" onclick={sharePlan} disabled={sharing}>
		{sharing ? 'Rendering…' : shareButtonLabel()}
		</button>
	</div>
	<MethodNote summary="How this plan is built (and its limits)">
		<p>{data.meta.heuristic}</p>
		{#if data.meta.note}
			<p>{data.meta.note}</p>
		{:else}
			<p>GoalIQ model projections, not FPL official; not betting advice.</p>
		{/if}
	</MethodNote>

	<div class="timeline">
		{#each data.plan as g (g.gw)}
			<div class="gw-card card">
				<div class="gw-head">
					<strong>GW{g.gw}</strong>
					<span class="gw-xp">{g.gw_xp.toFixed(1)} xP</span>
				</div>
				{#if g.roll_transfer}
					<p class="muted roll">
						<abbr title="Hold: keep the free transfer this week and bank it for the next one"
							>Roll transfer</abbr
						>
					</p>
				{:else}
					<ul class="moves">
						{#each g.transfers as t (t.out.id + '-' + t.in.id)}
							<li>
								{t.out.web_name} <span class="muted">({t.out.team_short})</span>
								<span class="arrow">→</span>
								{t.in.web_name} <span class="muted">({t.in.team_short})</span>
								<span class="gain">+{t.gain_xp_remaining.toFixed(2)} xP</span>
								{#if t.hit}<span class="hit">{t.hit} hit</span>{/if}
							</li>
						{/each}
					</ul>
				{/if}
				<p class="gw-meta muted">
					Captain: {g.captain.web_name} ({g.captain.gw_xp.toFixed(1)} xP) · FTs left:
					{g.free_transfers_left} · Bank: {g.bank.toFixed(1)}
				</p>
			</div>
		{/each}
	</div>

	<div class="totals card">
		<div class="fact">
			<span class="muted">Plan xP</span>
			<span class="val">{data.totals.plan_xp.toFixed(1)}</span>
		</div>
		<div class="fact">
			<span class="muted">No-transfer baseline</span>
			<span class="val">{data.totals.baseline_xp_no_transfers.toFixed(1)}</span>
		</div>
		<div class="fact">
			<span class="muted">Net gain</span>
			<span class="val gain">
				{data.totals.net_gain >= 0 ? '+' : ''}{data.totals.net_gain.toFixed(1)}
			</span>
		</div>
		<div class="fact">
			<span class="muted">Hits taken</span>
			<span class="val">{data.totals.hits_taken}</span>
		</div>
	</div>
{/if}

<style>
	.plan-form {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-3);
		align-items: end;
		margin-bottom: var(--s-4);
	}
	/* #63: verdikti-kortin ja MethodNoten väli (kortilla margin-top, ei -bottom) */
	.verdict-slot {
		margin-bottom: var(--s-4);
	}
	.timeline {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
		gap: var(--s-4);
		margin-bottom: var(--s-4);
	}
	.gw-card {
		padding: var(--s-4);
	}
	.gw-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin-bottom: var(--s-2);
	}
	.gw-xp {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		color: var(--positive);
	}
	.moves {
		list-style: none;
		margin: 0 0 var(--s-2);
		padding: 0;
		font-size: var(--step--1);
		display: grid;
		gap: var(--s-1);
	}
	.arrow {
		color: var(--giq-rust);
		font-weight: 700;
	}
	.gain {
		color: var(--positive);
		font-weight: 700;
	}
	.hit {
		color: var(--negative);
		font-weight: 700;
	}
	.roll {
		margin-bottom: var(--s-2);
		font-weight: 700;
	}
	.gw-meta {
		margin: 0;
	}
	.totals {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: var(--s-3);
		padding: var(--s-4);
		max-width: 640px;
	}
	.fact {
		display: grid;
		gap: 2px;
	}
	.fact .val {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	/* SHARE-CARD-SPA 27.8: sama chip kuin muissa jaettavissa listoissa */
	.head-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--s-2);
		flex-wrap: wrap;
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
