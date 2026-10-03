<script lang="ts">
	/**
	 * /ucl#my-team (UCL-LAAJENNUS vaiheet 5-7, 3.10.2026).
	 *
	 * Joukkue syotetaan kasin `pool`-listasta, joka on ilmainen. Analyysi
	 * (paras XI, siirrot, chipit) lasketaan $lib/uclSquad-lukijalla vain
	 * taydesta xP-listasta: maskattu vastaus -> lukko. Joukkue tallennetaan
	 * vain laitteelle; UEFAlta ei haeta mitaan (kayttoehdot 6.2).
	 */
	import type { UclXpResponse } from '$lib/api';
	import Paywall from '$lib/components/Paywall.svelte';
	import { capture } from '$lib/analytics';
	import {
		UCL_RULES,
		UCL_SQUAD_POSITIONS,
		analyseSquad,
		chipAdvice,
		squadBank,
		suggestTransfers,
		validateSquad,
		withXp,
		type UclSquadIssue,
		type UclSquadPlayer,
		type UclSquadPos
	} from '$lib/uclSquad';

	let { xp }: { xp: UclXpResponse } = $props();

	const KEY = 'giq_ucl_squad_v1';
	type Saved = { ids: number[]; bank: number | null; free: number };
	function load(): Saved {
		try {
			const s = JSON.parse(localStorage.getItem(KEY) ?? 'null');
			if (s && Array.isArray(s.ids)) {
				return {
					ids: s.ids.filter((x: unknown) => Number.isInteger(x)),
					bank: typeof s.bank === 'number' ? s.bank : null,
					free: Number.isInteger(s.free) ? s.free : UCL_RULES.freePerMatchday
				};
			}
		} catch {
			/* no storage: start empty */
		}
		return { ids: [], bank: null, free: UCL_RULES.freePerMatchday };
	}
	const saved = load();
	let ids = $state<number[]>(saved.ids);
	let bank = $state<number | null>(saved.bank);
	let free = $state<number>(saved.free);

	$effect(() => {
		const s: Saved = { ids, bank, free };
		try {
			localStorage.setItem(KEY, JSON.stringify(s));
		} catch {
			/* private mode: the squad lives for this visit only */
		}
	});

	const LABEL: Record<UclSquadPos, [string, string]> = {
		GKP: ['Goalkeepers', 'goalkeeper'],
		DEF: ['Defenders', 'defender'],
		MID: ['Midfielders', 'midfielder'],
		FWD: ['Forwards', 'forward']
	};

	let pool = $derived<UclSquadPlayer[]>((xp.pool ?? []) as UclSquadPlayer[]);
	let byId = $derived(new Map(pool.map((p) => [p.id, p])));
	let picked = $derived(ids.map((id) => byId.get(id)).filter((p): p is UclSquadPlayer => !!p));
	let check = $derived(validateSquad(ids, pool, bank));
	let bankNow = $derived(squadBank(check.players, bank));

	function options(pos: UclSquadPos) {
		const chosen = new Set(ids);
		return pool
			.filter((p) => p.pos === pos && !chosen.has(p.id))
			.sort((a, b) => (a.web_name ?? '').localeCompare(b.web_name ?? ''));
	}
	function add(id: number) {
		if (!id || ids.includes(id)) return;
		ids = [...ids, id];
		if (ids.length === UCL_RULES.squadSize) capture('ucl_my_team_complete', {}, 'ucl_my_team_complete');
	}
	function remove(id: number) {
		ids = ids.filter((x) => x !== id);
	}

	function issueText(i: UclSquadIssue): string {
		switch (i.kind) {
			case 'size':
				return `${i.have} of ${UCL_RULES.squadSize} players picked.`;
			case 'position':
				return `${LABEL[i.pos][0]}: ${i.have} of ${i.need}.`;
			case 'club':
				return `${i.club}: ${i.have} players, the limit is ${UCL_RULES.clubMax}.`;
			case 'budget':
				return `Your squad costs €${i.value.toFixed(1)}m, over the €${UCL_RULES.budget}m budget. If prices have risen since you picked them, enter what you have in the bank.`;
			case 'unknown':
				return `${i.ids.length} saved ${i.ids.length === 1 ? 'player is' : 'players are'} no longer in the game's list. Pick again.`;
		}
	}

	/* Laskenta tavallisista objekteista: sivun `xp` on syva $state-proxy, ja
	   siirtohaku kay ~15 000 kokoonpanoa. Proxyjen lapi mitattu 6,5 s (dev),
	   snapshotista murto-osa. */
	let plain = $derived($state.snapshot(xp) as UclXpResponse);
	let analysis = $derived(analyseSquad(ids, plain.pool ?? [], plain.players, plain.meta, bank));
	let all = $derived(withXp((plain.pool ?? []) as UclSquadPlayer[], plain.players as unknown as UclSquadPlayer[]));
	let moves = $derived(
		analysis.state === 'ready' ? suggestTransfers(analysis.players, all, analysis.bank, free, analysis.mds) : null
	);
	let chips = $derived(
		analysis.state === 'ready' ? chipAdvice(analysis.players, all, analysis.bank, analysis.mds) : null
	);
	let span = $derived(
		analysis.state === 'ready'
			? analysis.mds.length > 1
				? `MD${analysis.mds[0]} to MD${analysis.mds[analysis.mds.length - 1]}`
				: `MD${analysis.mds[0]}`
			: ''
	);
	$effect(() => {
		if (analysis.state === 'ready' || analysis.state === 'locked') {
			capture('ucl_my_team_analysis', { state: analysis.state }, `ucl_my_team_analysis_${analysis.state}`);
		}
	});

	const POS_ORDER: string[] = [...UCL_SQUAD_POSITIONS];
	const name = (id: number) => byId.get(id)?.web_name ?? `#${id}`;
	const names = (xs: number[]) => xs.map(name).join(' and ');
	const xpAt = (id: number, md: number) =>
		(all.find((p) => p.id === id)?.gameweeks ?? []).find((g) => g.gw === md)?.xp ?? 0;
	const fmt = (x: number) => (x >= 0 ? '+' : '') + x.toFixed(1);
</script>

<h2>My team</h2>
<p class="muted view-lede">
	Add the 15 players from your UCL Fantasy squad. They're saved on this device only, and GoalIQ
	doesn't connect to your UEFA account.
</p>

<div class="squad">
	{#each UCL_SQUAD_POSITIONS as pos (pos)}
		{@const mine = picked.filter((p) => p.pos === pos)}
		<div class="posgroup">
			<h3>{LABEL[pos][0]} <span class="muted">{mine.length}/{UCL_RULES.quota[pos]}</span></h3>
			<ul>
				{#each mine as p (p.id)}
					<li>
						{p.web_name} <span class="muted">{p.team_short} · €{p.price.toFixed(1)}m</span>
						<button type="button" class="rm" aria-label={`Remove ${p.web_name}`} onclick={() => remove(p.id)}>×</button>
					</li>
				{/each}
			</ul>
			{#if mine.length < UCL_RULES.quota[pos]}
				<select
					value=""
					onchange={(e) => {
						add(Number((e.target as HTMLSelectElement).value));
						(e.target as HTMLSelectElement).value = '';
					}}
				>
					<option value="">Add a {LABEL[pos][1]}…</option>
					{#each options(pos) as p (p.id)}
						<option value={p.id}>{p.web_name} ({p.team_short}, €{p.price.toFixed(1)}m)</option>
					{/each}
				</select>
			{/if}
		</div>
	{/each}
</div>

<div class="money">
	<span>Squad value <strong>€{check.value.toFixed(1)}m</strong></span>
	<label>
		In the bank (€m)
		<input
			type="number"
			min="0"
			step="0.1"
			placeholder={bankNow.toFixed(1)}
			value={bank ?? ''}
			oninput={(e) => {
				const v = (e.target as HTMLInputElement).value;
				bank = v === '' ? null : Math.max(0, Number(v));
			}}
		/>
	</label>
	<label>
		Free transfers
		<select value={free} onchange={(e) => (free = Number((e.target as HTMLSelectElement).value))}>
			{#each [0, 1, 2, 3] as n (n)}<option value={n}>{n}</option>{/each}
		</select>
	</label>
</div>
<p class="muted small">
	Prices are fixed until the MD2 deadline and change from MD3. Leave the bank empty and we use €{UCL_RULES.budget}m
	minus your squad value.
</p>

{#if check.issues.length}
	<ul class="issues">
		{#each check.issues as i, k (k)}<li>{issueText(i)}</li>{/each}
	</ul>
{/if}

{#if analysis.state === 'locked'}
	<p class="muted">
		Your best XI, captain, transfer ideas and chip plans are part of GoalIQ Premium. Your squad is
		saved here either way.
	</p>
	<Paywall teaser={false} />
{:else if analysis.state === 'unavailable'}
	<p class="muted">The analysis comes back when the next matchday's numbers are published.</p>
{:else if analysis.state === 'ready'}
	<h3>Best XI for MD{analysis.md}</h3>
	<div class="table-wrap">
		<table>
			<thead><tr><th>Player</th><th>Club</th><th>Pos</th><th class="num">MD{analysis.md}</th></tr></thead>
			<tbody>
				{#each [...analysis.xi.ids].sort((x, y) => POS_ORDER.indexOf(byId.get(x)?.pos ?? '') - POS_ORDER.indexOf(byId.get(y)?.pos ?? '') || xpAt(y, analysis.md) - xpAt(x, analysis.md)) as id (id)}
					{@const p = byId.get(id)}
					<tr>
						<td>{p?.web_name}{#if id === analysis.xi.captain}<strong class="cap" title="Captain">C</strong>{/if}</td>
						<td>{p?.team_short}</td>
						<td>{p?.pos}</td>
						<td class="num">{xpAt(id, analysis.md).toFixed(1)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="small">
		{analysis.xi.points.toFixed(1)} expected points with the captain doubled. Bench:
		{analysis.players.filter((p) => !analysis.xi.ids.includes(p.id)).map((p) => p.web_name).join(', ')}.
	</p>

	<h3>Transfers</h3>
	{#if moves && (moves.single || moves.double)}
		<ul class="moves">
			{#if moves.single}
				<li>
					{name(moves.single.out[0])} out, {name(moves.single.in[0])} in:
					<strong>{fmt(moves.single.gain)}</strong> expected points over {span}{#if moves.single.hits}, after a
						4-point hit {fmt(moves.single.net)}{/if}.
				</li>
			{/if}
			{#if moves.double}
				<li>
					{names(moves.double.out)} out, {names(moves.double.in)} in:
					<strong>{fmt(moves.double.gain)}</strong> over {span}{#if moves.double.hits}, after
						{moves.double.hits === 1 ? 'a 4-point hit' : `${moves.double.hits} hits of 4 points`}
						{fmt(moves.double.net)}{/if}.
				</li>
			{/if}
		</ul>
	{:else}
		<p>No transfer within your bank adds expected points to your best XI over {span}.</p>
	{/if}
	<p class="muted small">
		Gains count only the players who would make your best XI. Players with thin or no data and
		anyone with an availability flag are left out.
	</p>

	<h3>Chips</h3>
	{#if chips?.state === 'blocked'}
		<p>Chips can't be played on MD{chips.md}: everyone already has unlimited transfers.</p>
	{:else if chips?.state === 'rows'}
		{@const best = chips.limitless.filter((r) => !r.blocked).sort((a, b) => b.gain - a.gain)[0]}
		<ul class="moves">
			<li>
				Limitless, one matchday with no budget:
				{#each chips.limitless as r, k (r.md)}{k ? ', ' : ''}MD{r.md}
					{#if r.blocked}not playable{:else}<strong class:best={best && r.md === best.md}>{fmt(r.gain)}</strong>{/if}{/each}
				over your own best XI.
			</li>
			<li>
				Wildcard on MD{chips.wildcard.md}: <strong>{fmt(chips.wildcard.gain)}</strong> over {span} from the best
				squad we can find within your budget.
			</li>
		</ul>
		<p class="muted small">
			Our numbers cover {span} only, so this can't show whether a later matchday suits either chip
			better.
		</p>
	{/if}
{/if}

<style>
	.squad {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: var(--s-3);
		margin: var(--s-3) 0;
	}
	.posgroup h3 {
		margin: 0 0 var(--s-1);
		font-size: 1rem;
	}
	.posgroup ul,
	.issues,
	.moves {
		margin: 0 0 var(--s-2);
		padding-left: var(--s-3);
	}
	.posgroup ul {
		list-style: none;
		padding: 0;
	}
	.posgroup li {
		display: flex;
		gap: var(--s-1);
		align-items: center;
		margin-bottom: 2px;
	}
	.rm {
		margin-left: auto;
		background: none;
		border: 1px solid var(--border);
		border-radius: 3px;
		color: inherit;
		cursor: pointer;
		padding: 0 var(--s-1);
	}
	select,
	input {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		padding: var(--s-1);
		max-width: 100%;
	}
	.money {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-3);
		align-items: center;
	}
	.money label {
		display: inline-flex;
		gap: var(--s-1);
		align-items: center;
	}
	.money input {
		width: 6em;
	}
	.issues {
		color: var(--warn, var(--accent));
	}
	.small {
		font-size: 0.9rem;
	}
	.best {
		color: var(--accent);
	}
	.cap {
		margin-left: var(--s-1);
		color: var(--accent);
	}
	.rm {
		line-height: 1.2;
		align-self: center;
	}
</style>
