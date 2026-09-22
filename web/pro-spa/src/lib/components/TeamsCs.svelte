<script lang="ts">
	/**
	 * Players | Teams -> Teams (22.9.2026, UX-uudistus A3 2.3).
	 *
	 * Clean sheet -todennakoisyys joukkueittain ja otteluittain, ilman FDR:aa
	 * (brief: tuotteen ydin on CS% + xP + julkaistu track record, FDR:n tekee
	 * virallinen FPL jo). Pituus koodaa luvun (A2 saanto 17), vari ei.
	 *
	 * Data: /api/fantasy (ilmainen, sama kuin Clean sheets -tyokalulla).
	 * Lukija `teamsCsGrid` ($lib/weekRows) valitsee sarakkeet ja rivit; sama
	 * suodatin kuin This week -sivun clean sheet -rivilla, joten kaksi pintaa
	 * eivat voi nayttaa samalle ottelulle eri lukua.
	 */
	import { fetchFantasy, type FantasyResponse } from '$lib/api';
	import { teamsCsGrid } from '$lib/weekRows';

	let data = $state<FantasyResponse | null>(null);
	let failed = $state(false);
	$effect(() => {
		fetchFantasy().then(
			(d) => (data = d),
			() => (failed = true)
		);
	});
	const grid = $derived(teamsCsGrid(data));
	const range = $derived(
		grid && grid.gws.length
			? grid.gws.length === 1
				? `GW${grid.gws[0]}`
				: `GW${grid.gws[0]}-GW${grid.gws[grid.gws.length - 1]}`
			: null
	);
</script>

<section class="tool-card teams-cs">
	<h2>Clean sheets by team{range ? `, ${range}` : ''}</h2>
	{#if failed}
		<p class="banner error">Could not load clean sheet projections right now. Please try again shortly.</p>
	{:else if !data}
		<p class="muted">Loading fixtures…</p>
	{:else if !grid || grid.gws.length === 0}
		<p class="muted">Clean sheet projections are not available for this gameweek yet.</p>
	{:else}
		<p class="muted cap">
			Free · The GoalIQ match model's chance that each team keeps a clean sheet, fixture by
			fixture. Teams are sorted by their average across these gameweeks.
		</p>
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="stick">Team</th>
						<th class="num"
							><abbr title="Average clean sheet chance per fixture across the gameweeks shown">Avg</abbr
							></th
						>
						{#each grid.gws as gw (gw)}<th>GW{gw}</th>{/each}
					</tr>
				</thead>
				<tbody>
					{#each grid.rows as r (r.name)}
						<tr>
							<td class="stick"><abbr title={r.name}>{r.team}</abbr></td>
							<td class="num">{r.avg != null ? `${Math.round(r.avg)}%` : '–'}</td>
							{#each r.cells as c (c.gw)}
								<td>
									{#if c.blank}
										<span class="muted">Blank</span>
									{:else if c.fixtures.length === 0}
										<span class="muted">–</span>
									{:else}
										{#each c.fixtures as f, i (i)}
											<span class="fx" title="{r.name} vs {f.opponent} ({f.venue})">
												<span class="opp">{f.opponent} ({f.venue})</span>
												<b>{Math.round(f.cs)}%</b>
												<span class="bar" style="width: {Math.max(2, Math.round(f.cs))}%" aria-hidden="true"
												></span>
											</span>
										{/each}
									{/if}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

<style>
	.cap {
		font-size: var(--step--1);
		max-width: 62ch;
	}
	table {
		border-collapse: collapse;
	}
	th,
	td {
		vertical-align: top;
		white-space: nowrap;
	}
	/* A2 saanto 12: tunnistesarake lukittuna vaakavierityksessa. */
	.stick {
		position: sticky;
		left: 0;
		z-index: 1;
		background: var(--surface);
	}
	.fx {
		display: flex;
		flex-direction: column;
		min-width: 4.8em;
		font-variant-numeric: tabular-nums;
	}
	.fx + .fx {
		margin-top: var(--s-2);
	}
	.opp {
		font-size: 0.78em;
		color: var(--text-muted);
	}
	.bar {
		display: block;
		height: 3px;
		margin-top: 2px;
		background: var(--accent);
	}
</style>
