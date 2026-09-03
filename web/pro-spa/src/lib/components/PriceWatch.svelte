<script lang="ts">
	import { fetchPriceWatch, confBand, type PriceWatchResponse, type PriceMove } from '$lib/fantasyTools';
	import { canShareToApps, shareCard, shareButtonLabel} from '$lib/shareCard';
	import { capture } from '$lib/analytics';
	import { currentEntryId } from '$lib/fplEntry.svelte';

	let data = $state<PriceWatchResponse | null>(null);
	let error = $state<string | null>(null);

	// MY-TEAM-CONTEXT (3.9): jaettu entry mukaan -> omat rivit merkitään.
	$effect(() => {
		const entry = currentEntryId();
		fetchPriceWatch(entry).then(
			(d) => (data = d),
			(e) => (error = e instanceof Error ? e.message : String(e))
		);
	});

	const owned = $derived(data?.owned ?? null);
	function ownedLine(o: NonNullable<PriceWatchResponse['owned']>): string {
		const parts: string[] = [];
		if (o.n_tonight > 0) {
			parts.push(`${o.n_tonight} of your ${o.squad_size} move tonight`);
		}
		const rest = o.n_rising + o.n_falling - o.n_tonight;
		if (rest > 0) {
			parts.push(`${rest} more on watch`);
		}
		if (parts.length === 0) return `None of your ${o.squad_size} are on these lists.`;
		return parts.join(', ') + '.';
	}

	const STATUS_LABEL: Record<string, string> = {
		rising_soon: 'Rising soon',
		rising_watch: 'On watch',
		falling_soon: 'Falling soon',
		falling_watch: 'On watch'
	};

	const CONF_LABEL = { low: 'low', med: 'medium', high: 'high' } as const;

	/* 22.8 (portin loydos): `*_soon` syntyy myos pelkasta edistymisesta ilman
	 * etta FPL:n projektio ylittaa kynnyksen kolmessa paivassa. Silloin rivi
	 * lukisi "Rising soon | No date yet" eli kaksi vastakkaista vaitetta
	 * vierekkain. Ilman paivaa nayta aina watch-taso. */
	function statusLabel(r: PriceMove): string {
		const s =
			r.status.endsWith('_soon') && typeof r.eta_days !== 'number'
				? r.status.replace('_soon', '_watch')
				: r.status;
		return STATUS_LABEL[s] ?? s;
	}

	let empty = $derived(
		data != null && data.risers.length === 0 && data.fallers.length === 0
	);
	/* 2.8: jakokortti free-datalle. Price watch ei ole premiumia, ja juuri
	 * free-datan jakaminen on jakelusilmukka: jakaja mainostaa meitä
	 * maksamatta. Sama shareCard-moottori kuin leaders-listoilla. */
	let sharing = $state('');

	async function shareMoves(title: string, rows: PriceMove[]) {
		if (sharing) return;
		sharing = title;
		try {
			const method = await shareCard({
				title: `PRICE ${title.toUpperCase()}`,
				// 22.8: kortti sanoi "not official" samalla kun sivu sanoo luvun
				// olevan FPL:n oma — kortti menee ulos kuvana, joten se ei saa
				// kantaa vastakkaista vaitetta. Seuraa samaa lippua kuin sivu.
				subtitle: data?.meta.official_projection
					? "FPL's own price projection"
					: 'estimated from transfer activity, not official',
				midLabel: 'PRICE',
				valueLabel: 'PROGRESS',
				fileName: `goaliq_price_${title.toLowerCase()}.png`,
				rows: rows.slice(0, 10).map((r, i) => ({
					rank: i + 1,
					name: r.web_name,
					tag: confBand(r.confidence).toUpperCase(),
					team: '',
					// 🔴 3.9 (audit): tassa oli `/ 10` toisen kerran. Builderi
					// (`build_fpl_price_watch.py`) kirjoittaa `now_cost`in JO
					// miljoonina, ja saman naytön taulukko renderoi sen suoraan —
					// eli kortti sanoi 0.6 siina missa taulukko sen vieressa sanoi 5.5.
					mid: typeof r.now_cost === 'number' ? r.now_cost.toFixed(1) : '',
					value: `${Math.round(r.progress_pct)}%`
				}))
			});
			if (method !== 'aborted') {
				capture('xp_card_shared', { list: `price_${title.toLowerCase()}`, method });
			}
		} finally {
			sharing = '';
		}
	}
</script>

{#snippet moveTable(title: string, rows: PriceMove[])}
	<div class="watch-col">
		<h3>{title}</h3>
		{#if rows.length === 0}
			<p class="muted">No candidates right now.</p>
		{:else}
			<!-- 2.8: jakokortti free-datalle, sama kaava kuin Clean Sheetsissä.
			     Nappi ilmestyy itsestään kun listalla on 3+ riviä: esikaudella
			     risers/fallers ovat tyhjät (n_with_transfer_activity 0), joten
			     tämä on inertti 21.8. asti eikä lupaa korttia jota ei voi tehdä. -->
			{#if rows.length >= 3}
				<div class="share-row">
					<button type="button" class="share-btn" onclick={() => shareMoves(title, rows)} disabled={sharing !== ''}>
						{sharing === title
							? 'Rendering…'
							: shareButtonLabel()}
					</button>
				</div>
			{/if}
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Player</th>
							<th class="num">Price</th>
							<th>Status</th>
							<!-- 22.8: FPL julkaisee nyt oman projektionsa, joten
							     paiva kynnykseen on tiedossa. Se on syy avata
							     sivu, joten se saa oman sarakkeensa. "Projected"
							     eika "due": FPL antaa jokaiselle projektiolle
							     likelihood-luvun, joten varmuutta ei luvata. -->
							<th
								><abbr title="The day FPL's own projection crosses the threshold"
									>Projected</abbr
								></th
							>
							<th class="num"
								><abbr title="How far FPL's own projection has moved towards the threshold; the mark shows confidence"
									>Progress</abbr
								></th
							>
						</tr>
					</thead>
					<tbody>
						{#each rows as r (r.id)}
							{@const band = confBand(r.confidence)}
							<tr>
								<td
									>{r.web_name}{#if r.owned}
										<span class="own-badge" title="In your squad">owned</span>{/if}{#if r.already_changed_today}
										<span class="muted"> (changed today)</span>{/if}</td
								>
								<td class="num">{r.now_cost.toFixed(1)}</td>
								<td>
									<span class="badge {r.status.startsWith('rising') ? 'up' : 'down'}">
										{statusLabel(r)}
									</span>
								</td>
								<td class="eta">
									{#if r.eta_days === 0}
										Tonight
									{:else if r.eta_days === 1}
										Tomorrow
									{:else if typeof r.eta_days === 'number'}
										In {r.eta_days} days
									{:else}
										<!-- "No date yet" eika "Not in 3 days": jalkimmainen on
										     kaksitulkintainen, ja "on watch" torm aisi viereisen
										     sarakkeen statuslabeliin. -->
										<span class="muted">No date yet</span>
									{/if}
								</td>
								<td class="num">
									<span class="conf conf-{band}" title="{CONF_LABEL[band]} confidence">&#9679;</span
									>{Math.round(r.progress_pct)}%
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
{/snippet}

<h2>Price watch</h2>
<!-- 22.8: FPL alkoi julkaista hinnanmuutosdatan itse, joten "estimated ...
     net-transfer velocity" ei ole enää se mitä sivu näyttää. Teksti seuraa
     payloadin `source`-kenttää eikä ole kovakoodattu: jos varapolku joskus
     aktivoituu, lukija näkee sen. -->
<p class="muted">
	{data?.meta.official_projection
		? "FPL's own price projection, closest change first."
		: 'Estimated price change candidates based on FPL net-transfer velocity.'}
	Free tool.
</p>

{#if error}
	<p class="banner error">{error}</p>
{:else if !data}
	<p class="muted">Loading price watch…</p>
{:else if !data.meta.available || empty}
	<p class="banner success">
		{data.meta.note ?? 'No price change candidates right now. Check back later.'}
	</p>
{:else}
	{#if owned}
		<!-- MY-TEAM-CONTEXT (3.9): omat 15 listoilla, nimet mukana -->
		<p class="owned-line">
			<strong>{ownedLine(owned)}</strong>
			{#if owned.rising.length > 0}
				<span class="muted">Rising: {owned.rising.map((m) => m.web_name).join(', ')}.</span>
			{/if}
			{#if owned.falling.length > 0}
				<span class="muted">Falling: {owned.falling.map((m) => m.web_name).join(', ')}.</span>
			{/if}
		</p>
	{:else if data.meta.squad && !data.meta.squad.available && data.meta.squad.note}
		<p class="muted">Your squad was not read: {data.meta.squad.note}</p>
	{:else}
		<!-- 3.9 ilta: sama hiljainen aukko kuin GK-rotaatiossa. -->
		<p class="muted">
			This list does not know your squad yet, so it cannot say which of your 15 are moving tonight. Put your FPL entry ID into Rate my team under My team.
		</p>
	{/if}
	<div class="watch-grid">
		{@render moveTable('Risers', data.risers)}
		{@render moveTable('Fallers', data.fallers)}
	</div>
{/if}

{#if data}
	<p class="muted disclaimer">{data.meta.disclaimer}</p>
{/if}

<style>
	.watch-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: var(--s-6);
		align-items: start;
	}
	.share-row {
		display: flex;
		justify-content: flex-end;
		margin: 0 0 8px;
	}
	.share-btn {
		background: transparent;
		border: 1px solid var(--track);
		color: var(--muted);
		font: inherit;
		font-size: 11px;
		padding: 4px 8px;
		cursor: pointer;
	}
	.share-btn:hover:not(:disabled) {
		color: var(--cream);
		border-color: var(--muted);
	}
	.share-btn:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.watch-col h3 {
		margin-top: 0;
	}
	.badge {
		display: inline-block;
		border-radius: var(--radius);
		padding: 1px 10px;
		font-size: var(--step--1);
		font-weight: 700;
		border: 1px solid transparent;
	}
	.badge.up {
		color: var(--positive);
		background: rgba(46, 214, 194, 0.12);
		border-color: rgba(0, 148, 130, 0.4);
	}
	.badge.down {
		color: var(--negative);
		background: rgba(255, 138, 92, 0.12);
		border-color: rgba(194, 65, 12, 0.4);
	}
	/* confidence-merkki: sama väriasteikko kuin XpTable #33f */
	.conf {
		font-size: 0.65em;
		vertical-align: 1px;
		margin-right: 3px;
	}
	.conf-high {
		color: var(--giq-teal-deep);
	}
	.conf-med {
		color: var(--text-muted);
	}
	.conf-low {
		color: var(--text-muted);
		opacity: 0.45;
	}
	.disclaimer {
		margin-top: var(--s-3);
	}
	.owned-line {
		margin: 0 0 var(--s-3);
	}
	.own-badge {
		display: inline-block;
		margin-left: 6px;
		padding: 0 6px;
		border-radius: var(--radius);
		border: 1px solid rgba(0, 148, 130, 0.4);
		color: var(--positive);
		font-size: var(--step--1);
		font-weight: 700;
	}
</style>
