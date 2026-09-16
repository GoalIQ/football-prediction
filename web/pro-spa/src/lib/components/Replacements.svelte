<script lang="ts">
	import { draftPool, type XpResponse } from '$lib/api';
	import {
		fetchReplacements,
		type ReplacementsResponse,
		type ReplacementRow
	} from '$lib/fantasyTools';
	import PlayerSearch, { type SearchItem } from './PlayerSearch.svelte';
	import { shareCard, shareButtonLabel } from '$lib/shareCard';
	import { capture } from '$lib/analytics';
	import { currentEntryId } from '$lib/fplEntry.svelte';

	/* ROWAN-REPLACEMENTS (2.9.2026): "who replaces X". Luoja (Rowan) maaritteli
	 * muodon itse: Player -> same price bracket -> next 5 GWs -> top 5
	 * replacements, with xP, ownership and a quick reason for each. Syy on
	 * backendin mittaama (minuutit / yksi huippukierros / xP-ero), ei tekstia
	 * jota UI keksisi. Valitsin lukee saman xP-poolin kuin Compare, ei uutta
	 * fetchia. */
	let { xp }: { xp: XpResponse } = $props();

	const BRACKETS = [0.5, 1.0, 1.5] as const;
	const WINDOWS = [3, 4, 5, 6] as const;

	let query = $state('');
	let target = $state<SearchItem | null>(null);
	let bracket = $state<number>(0.5);
	let gws = $state<number>(5);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let data = $state<ReplacementsResponse | null>(null);
	let sharing = $state(false);

	// Sama normalisointi kuin PlayerCard/FitChecker-haussa.
	function norm(s: string): string {
		return s
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase()
			.replace(/ø/g, 'o')
			.replace(/['’ʼ]/g, '')
			.replace(/[-.]/g, ' ')
			.trim();
	}
	/* UNAVAILABLE-TARGET (16.9): haku luki `xp.players`, eli VAIN projektiossa
	 * olevat. Rowan raportoi 15.9 ettei Elangaa loydy — han oli siirtynyt
	 * samana paivana `excluded`-listaan kun FPL merkitsi loukkaantumisen, eli
	 * tyokalu katosi tasan silloin kun sen kysymys syntyi. Lahde on nyt sama
	 * yksi lukija kuin draftilla ja fit-lukoilla (`draftPool`), joka kantaa
	 * seka taydet rivit etta kevyet pooli-rivit; jalkimmaisissa ovat sivussa
	 * olevat. Sivuvaikutus: free-kayttajan maskattu 10 rivin lista ei enaa
	 * kavenna hakua. */
	let outIds = $derived(new Set((xp.excluded ?? []).map((e) => e.id)));
	let items = $derived.by((): SearchItem[] => {
		const q = norm(query);
		if (q.length < 2) return [];
		return draftPool(xp)
			.filter(
				(p) =>
					norm(p.web_name).includes(q) ||
					(p.full_name ? norm(p.full_name).includes(q) : false) ||
					norm(p.team_short).includes(q)
			)
			.slice(0, 8)
			.map((p) => ({
				id: p.id,
				web_name: p.web_name,
				team_short: p.team_short,
				pos: p.pos,
				price: p.price,
				// Kevyt pooli-rivi ei kanna omistusta; taysi rivi kantaa.
				owned_pct: (p as { owned_pct?: number }).owned_pct,
				status: p.status,
				// Rivi kertoo heti ettei pelaajalla ole projektiota (PlayerSearch
				// piirtaa "out"-merkin) — muuten tyhja xP-luku luettaisiin viaksi.
				in_projection: !outIds.has(p.id)
			}));
	});

	async function load() {
		if (!target || loading) return;
		loading = true;
		error = null;
		try {
			// MY-TEAM-CONTEXT (3.9): entry mukaan -> hinnan ylaraja = bank +
			// lahtijan hinta kun han on rungossa, omistetut pois ehdokkaista.
			data = await fetchReplacements(target.id, gws, bracket, currentEntryId());
		} catch (err) {
			data = null;
			error = err instanceof Error ? err.message : String(err);
		}
		loading = false;
	}

	function select(p: SearchItem) {
		target = p;
		query = '';
		void load();
	}

	function apply(e: SubmitEvent) {
		e.preventDefault();
		void load();
	}

	function gap(p: ReplacementRow): string {
		const v = p.xp_gap_vs_target;
		if (v == null) return '';
		return (v > 0 ? '+' : '') + v.toFixed(1);
	}

	/* Lahtijalla ei ole projektiota (sivussa FPL:ssa). Vanha backend ei tuo
	 * lippua -> oletus true, eli kayttaytyminen on entinen. */
	let targetProjected = $derived(data?.meta.target_projected !== false);

	/* Jakokortin luku lahtijasta. Sama muoto kuin ehdokasriveilla
	 * (`75% to play`), ja kierros luvun perassa koska FPL:n luku koskee vain
	 * seuraavaa kierrosta. Ilman lukua (esim. status `u`, seurasta lahtenyt)
	 * kaytetaan backendin sanamuotoa sellaisenaan — ei omaa tulkintaa. */
	function targetCardValue(d: ReplacementsResponse): string {
		if (d.target.xp_window != null) return `${d.target.xp_window.toFixed(1)} xP`;
		if (d.target.chance_next != null && d.meta.gws.length > 0)
			return `${d.target.chance_next}% to play GW${d.meta.gws[0]} in FPL, no projection`;
		/* PORTTI 16.9 (toinen kierros): fallback oli 'unavailable in FPL'. Se on
		 * epatosi rivilla joka on `excluded` KYNNYKSEN takia eika lipun: mitattu
		 * samana paivana Lewis (MCI), FPL-status `a`, ei uutisia, mutta ei
		 * projektiota. 'no xP' vaittaa tasan yhden asian — meilla ei ole tata
		 * lukua — ja se on tosi molemmissa tapauksissa eika vanhene kierroksen
		 * vaihtuessa. */
		return 'no xP';
	}

	let windowLabel = $derived(
		data && data.meta.gws.length > 0
			? data.meta.gws.length === 1
				? `GW${data.meta.gws[0]}`
				: `GW${data.meta.gws[0]}-${data.meta.gws[data.meta.gws.length - 1]}`
			: ''
	);
	let nextN = $derived(data ? data.meta.gws.length : gws);
	let dropped = $derived(data?.meta.availability_gate?.dropped ?? []);
	let squad = $derived(data?.meta.squad ?? null);
	let hasSquad = $derived(squad?.available === true);

	// Kortti = se nakyma jonka jakaja katsoi: kohde, haarukka ja ikkuna
	// otsikossa, jotta lista ei vaita olevansa "parhaat korvaajat" yleisesti.
	async function share() {
		// Alaraja 3 kuten mobiilissa: kahden rivin kortti Brunosta (molemmat
		// hanen allaan) luki suosituksena alaspain.
		if (sharing || !data || data.players.length < 3) return;
		sharing = true;
		try {
			const m = data.meta;
			const method = await shareCard({
				title: `WHO REPLACES ${data.target.web_name.toUpperCase()}`,
				// PORTTI 2.9: lahtijan oma luku kortille (ilman sita kahden rivin
				// Bruno-kortti luki alaspain-siirron suosituksena) ja ikkuna luvun
				// paalle, koska ilmaispinnan "xP" on 6 GW:n summa eri ikkunasta.
				// 16.9: lahtijalla ei aina ole projektiota (sivussa FPL:ssa) -> kortti
				// sanoo sen, ei jata lukua pois hiljaa eika keksi nollaa.
				// PORTTI 16.9: ensimmainen versioni luki "out in FPL". Se oli (a)
				// vahvempi kuin backendin tarkoituksella valittu "unavailable in
				// FPL" ja (b) kierrokseton: FPL:n `chance_next` koskee VAIN
				// seuraavaa kierrosta, joten viiden kierroksen ikkunan vieressa
				// paljas "out" vaitti enemman kuin lahde. Kortti on pysyva kuva,
				// joten se vaittaisi sita viela senkin jalkeen kun lippu nousee.
				// Nyt kortilla on FPL:n oma luku ja se kierros jota luku koskee.
				subtitle: `${data.target.pos} ${m.price_min.toFixed(1)}-${m.price_max.toFixed(1)}m, ${windowLabel} · ${data.target.web_name} ${targetCardValue(data)} · GoalIQ model`,
				midLabel: 'OWNED',
				valueLabel: `xP ${windowLabel}`,
				footNote: 'xP from the GoalIQ model, ownership from FPL',
				fileName: 'goaliq_replacements.png',
				rows: data.players.slice(0, 5).map((p, i) => ({
					rank: i + 1,
					name: p.web_name,
					tag: p.pos,
					// Ville 2.9: Rowan jakaa KUVAN, joten hinta ja syy kortille.
					tag2: `${p.price.toFixed(1)}m`,
					team: p.team_short,
					// Portti k3: paljas "75%" OWNED-sarakkeen vieressa luettiin omistukseksi -> yksikko.
					badges: p.status === 'd' && p.chance_next != null ? [`${p.chance_next}% to play`] : undefined,
					mid: `${p.owned_pct.toFixed(1)}%`,
					value: p.xp_window.toFixed(1),
					sub: p.reason.text
				}))
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'replacements', method });
		} finally {
			sharing = false;
		}
	}
</script>

<div class="head-row">
	<h2>Replacements</h2>
	{#if (data?.players?.length ?? 0) >= 3}
		<button type="button" class="window-chip" onclick={share} disabled={sharing}>
			{sharing ? 'Rendering…' : shareButtonLabel()}
		</button>
	{/if}
</div>
<p class="muted">
	Same position, same price range, ranked by the model's projection over the window you pick.
	Rows can project below the player you are moving out, and the gap column says which.
</p>

<form class="repl-form" onsubmit={apply}>
	<div class="repl-search">
		{#if target}
			<span class="label-like">Player to replace</span>
			<button type="button" class="picked" onclick={() => (target = null)}>
				<strong>{target.web_name}</strong>
				<span class="muted">{target.team_short} · {target.pos}</span>
				<span class="muted">clear</span>
			</button>
		{:else}
			<PlayerSearch
				id="repl-search"
				label="Player to replace"
				placeholder="Player or team (e.g. Tzolis, EVE)"
				bind:query
				{items}
				onSelect={select}
			/>
		{/if}
	</div>
	<div>
		<label for="repl-bracket">Price bracket</label>
		<select id="repl-bracket" bind:value={bracket}>
			{#each BRACKETS as b (b)}
				<option value={b}>±{b.toFixed(1)}m</option>
			{/each}
		</select>
	</div>
	<div>
		<label for="repl-window">Window</label>
		<select id="repl-window" bind:value={gws}>
			{#each WINDOWS as w (w)}
				<option value={w}>{w} GWs</option>
			{/each}
		</select>
	</div>
	<button class="secondary" type="submit" disabled={!target || loading}>
		{loading ? 'Searching…' : 'Update'}
	</button>
</form>

{#if error}
	<p class="banner error">{error}</p>
{:else if !target}
	<p class="muted">Pick the player you are moving out to see who else is available at that price.</p>
{:else if !data}
	<p class="muted">Loading replacements…</p>
{:else}
	<p class="target-line">
		<strong>{data.target.web_name}</strong> · {data.target.team_short} · {data.target.pos} ·
		{data.target.price.toFixed(1)}m · {data.target.owned_pct.toFixed(1)}% owned
		{#if data.target.xp_window != null}· {data.target.xp_window.toFixed(1)} xP next {nextN}{:else}·
			<span class="muted">no projection</span>{/if}
		{#if data.target.status !== 'a' && data.target.chance_next != null}
			<span class="muted">· {data.target.chance_next}% chance of playing the next round</span>
		{/if}
	</p>
	{#if data.meta.target_note}
		<p class="muted">{data.meta.target_note}</p>
	{/if}
	{#if hasSquad && data.meta.budget_note}
		<p class="muted">
			{#if data.meta.target_owned}<span class="own-badge">in your squad</span> {/if}{data.meta.budget_note}
		</p>
	{:else if squad && !squad.available && squad.note}
		<p class="muted">Your squad was not read: {squad.note}</p>
	{:else}
		<!-- 3.9 ilta: sama hiljainen aukko kuin GK-rotaatiossa. Ilman entrya
		     hinta ei ole katkaistu pankkiisi eika omistettuja jateta pois. -->
		<p class="muted">
			This list does not know your squad yet, so the price is not capped at your bank and the players you already own are still on the list. Put your FPL entry ID into Rate my team under My team.
		</p>
	{/if}
	{#if data.meta.bracket_widened}
		<p class="muted">
			No one within ±{data.meta.bracket_requested.toFixed(1)}m of {data.target.price.toFixed(1)}m.
			Bracket widened to ±{data.meta.bracket.toFixed(1)}m ({data.meta.price_min.toFixed(1)}-{data.meta.price_max.toFixed(
				1
			)}m){#if data.meta.candidates_in_bracket < 5}, and even then only {data.meta.candidates_in_bracket}
				{data.meta.candidates_in_bracket === 1 ? 'player' : 'players'} in this position have a projection{/if}.
		</p>
	{/if}
	{#if dropped.length > 0}
		<p class="muted">
			Dropped after a live availability check: {dropped.map((d) => d.web_name).join(', ')}
		</p>
	{/if}
	{#if data.players.length === 0}
		<p class="muted">
			No one in this position between {data.meta.price_min.toFixed(1)}m and {data.meta.price_max.toFixed(
				1
			)}m has a projection.
		</p>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="num">#</th>
						<th>Player</th>
						<th>Team</th>
						<th class="m-hide">Pos</th>
						<th class="num">Price</th>
						<th class="num"><abbr title="Selected-by percentage in the FPL game">Owned %</abbr></th>
						<th class="num"
							><abbr title="Sum of expected points over {windowLabel}">xP next {nextN}</abbr></th
						>
						{#if targetProjected}
							<th class="num"
								><abbr title="Expected points over the window minus {data.target.web_name}'s"
									>vs {data.target.web_name}</abbr
								></th
							>
						{/if}
						<th>Reason</th>
					</tr>
				</thead>
				<tbody>
					{#each data.players as p, i (p.id)}
						<tr>
							<td class="num muted">{i + 1}</td>
							<td>
								{p.web_name}
								{#if p.status === 'd'}
									<span class="doubt">
										{#if p.chance_next != null}{p.chance_next}% to play{:else}doubtful{/if}
									</span>
									{#if p.news}<span class="muted news">{p.news}</span>{/if}
								{/if}
							</td>
							<td>{p.team_short}</td>
							<td class="m-hide">{p.pos}</td>
							<td class="num">{p.price.toFixed(1)}</td>
							<td class="num">{p.owned_pct.toFixed(1)}</td>
							<td class="num total-col">{p.xp_window.toFixed(1)}</td>
							{#if targetProjected}
								<td
									class="num"
									class:gap-pos={(p.xp_gap_vs_target ?? 0) > 0}
									class:gap-neg={(p.xp_gap_vs_target ?? 0) < 0}>{gap(p)}</td
								>
							{/if}
							<td class="reason">{p.reason.text}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if data.meta.reason_note}
			<p class="muted small">{data.meta.reason_note}</p>
		{/if}
	{/if}
{/if}

<style>
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
	.repl-form {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-3);
		align-items: end;
		margin-bottom: var(--s-4);
	}
	.repl-search {
		flex: 1 1 260px;
		min-width: 220px;
	}
	.label-like {
		display: block;
		margin-bottom: 4px;
	}
	.picked {
		display: flex;
		gap: 8px;
		align-items: baseline;
		width: 100%;
		text-align: left;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 8px 10px;
		cursor: pointer;
	}
	.picked span:last-child {
		margin-left: auto;
		font-size: var(--step--1);
	}
	.target-line {
		margin: 0 0 var(--s-3);
	}
	td.total-col {
		font-weight: 700;
		color: var(--text);
	}
	.gap-pos {
		color: var(--positive);
	}
	.gap-neg {
		color: var(--negative);
	}
	td.reason {
		min-width: 220px;
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	.doubt {
		display: inline-block;
		margin-left: 6px;
		font-size: var(--step--1);
		color: var(--negative);
	}
	.news {
		display: block;
		font-size: var(--step--1);
	}
	.small {
		font-size: var(--step--1);
	}
	.own-badge {
		display: inline-block;
		padding: 0 6px;
		border-radius: var(--radius);
		border: 1px solid rgba(0, 148, 130, 0.4);
		color: var(--positive);
		font-size: var(--step--1);
		font-weight: 700;
	}
</style>
