<script lang="ts">
	/**
	 * SeasonLedger (MP-14, 26.9.2026): oman joukkueen kausi jaadytettya
	 * projektiota vastaan, kierros kerrallaan. /api/fantasy/my-team-ledger on
	 * ollut valmis ja ilmainen 25.8 alkaen, mutta mikaan pinta ei nayttanyt sita.
	 *
	 * Luvut, lause ja pylvaat: $lib/ledger (yksi lukija). Ilmainen: luku joka voi
	 * nolata mallin ei kuulu maksumuurin taakse (endpointin docstring).
	 * Muoto: poikkeama nollaviivasta per kierros (dataviz: "above/below a
	 * baseline"). Varit validoitu tummaa pintaa vasten (CVD dE 12.8), ja
	 * etumerkki nakyy myos suunnasta, joten vari ei ole ainoa koodaus.
	 */
	import { fetchMyTeamLedger, type LedgerResponse } from '$lib/api';
	import { capture } from '$lib/analytics';
	import {
		barTooltip,
		ledgerHeadline,
		ledgerNotes,
		ledgerSummary,
		ledgerView,
		signed
	} from '$lib/ledger';

	let { entry }: { entry: number | null } = $props();

	let data = $state<LedgerResponse | null>(null);
	let loadedFor = $state<number | null>(null);
	let active = $state<number | null>(null);

	$effect(() => {
		if (entry == null) {
			data = null;
			loadedFor = null;
			return;
		}
		if (loadedFor === entry) return;
		loadedFor = entry;
		const want = entry;
		fetchMyTeamLedger(want).then(
			(r) => {
				if (loadedFor === want) data = r;
			},
			() => {
				if (loadedFor === want) data = null;
			}
		);
	});

	const view = $derived(ledgerView(data));

	// Kaavion geometria (viewBox-yksikot). Nollaviiva sinne missa 0 on
	// asteikolla: pelkat plussat eivat jata tyhjaa alapuoliskoa.
	const W = 320;
	const H = 120;
	const PAD_TOP = 6;
	const PAD_BOTTOM = 18;
	const geom = $derived.by(() => {
		if (!view) return null;
		const hi = Math.max(0, ...view.bars.map((b) => b.diff));
		const lo = Math.min(0, ...view.bars.map((b) => b.diff));
		const span = Math.max(1, hi - lo);
		const plotH = H - PAD_TOP - PAD_BOTTOM;
		const y = (v: number) => PAD_TOP + ((hi - v) / span) * plotH;
		const slot = W / view.bars.length;
		const barW = Math.min(28, Math.max(4, slot - 4));
		return {
			zero: y(0),
			slot,
			bars: view.bars.map((b, i) => {
				const top = Math.min(y(b.diff), y(0));
				const h = Math.max(1, Math.abs(y(b.diff) - y(0)));
				return { ...b, i, x: i * slot + (slot - barW) / 2, w: barW, top, h, cx: i * slot + slot / 2 };
			})
		};
	});

	function onToggle(e: Event) {
		if ((e.currentTarget as HTMLDetailsElement).open && view) {
			capture('season_ledger_opened', { graded_gws: view.graded });
		}
	}
</script>

{#if view && geom}
	<details class="ledger" ontoggle={onToggle}>
		<summary>
			<span class="title">Your season vs the projection</span>
			<span class="sum">{ledgerSummary(view)}</span>
		</summary>

		<p class="headline">{ledgerHeadline(view)}</p>

		<div class="chart">
			<svg
				viewBox="0 0 {W} {H}"
				role="img"
				aria-label="Points above or below the projection, per gameweek"
			>
				{#each geom.bars as b (b.gw)}
					<rect
						class="bar"
						class:above={b.diff >= 0}
						class:below={b.diff < 0}
						class:prov={b.state !== 'final'}
						class:dim={active != null && active !== b.i}
						x={b.x}
						y={b.top}
						width={b.w}
						height={b.h}
					/>
					<!-- Osuma-alue koko sarakkeen levyinen, isompi kuin pylvas. -->
					<rect
						class="hit"
						x={b.i * geom.slot}
						y="0"
						width={geom.slot}
						height={H}
						tabindex="0"
						role="button"
						aria-label={barTooltip(b)}
						onmouseenter={() => (active = b.i)}
						onmouseleave={() => (active = null)}
						onfocus={() => (active = b.i)}
						onblur={() => (active = null)}
					/>
					<text class="gw" x={b.cx} y={H - 4} text-anchor="middle">{b.gw}</text>
				{/each}
				<line class="zero" x1="0" x2={W} y1={geom.zero} y2={geom.zero} />
			</svg>
			{#if active != null}
				{@const b = geom.bars[active]}
				<!-- Pylvaan ylapuolelle kaavion sisaan (ei otsikon paalle); reunoilla
				     ankkuroidaan reunaan ettei teksti valu ruudun yli. -->
				<div
					class="tip"
					class:edge-l={b.cx / W < 0.35}
					class:edge-r={b.cx / W > 0.65}
					style="left: {((b.cx / W) * 100).toFixed(2)}%; top: {((b.top / H) * 100).toFixed(2)}%"
				>
					{barTooltip(b)}
				</div>
			{/if}
		</div>

		<p class="legend">
			<span class="sw above" aria-hidden="true"></span> above the projection
			<span class="sw below" aria-hidden="true"></span> below it
			<span class="muted">· GW on the axis</span>
		</p>

		<details class="table">
			<summary>Table</summary>
			<table>
				<thead>
					<tr><th>GW</th><th>Projected</th><th>Scored</th><th>Difference</th></tr>
				</thead>
				<tbody>
					{#each view.bars as b (b.gw)}
						<tr>
							<td>{b.gw}{b.state !== 'final' ? '*' : ''}</td>
							<td class="num">{b.projected.toFixed(1)}</td>
							<td class="num">{b.actual}</td>
							<td class="num">{signed(b.diff)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</details>

		<p class="muted small">
			Each player's projection is frozen before the deadline, then counted the way FPL counted
			your points, chips and auto-subs included. Your points are after transfer hits.
		</p>
		{#each ledgerNotes(view) as n (n)}
			<p class="muted small">{n}</p>
		{/each}
	</details>
{/if}

<style>
	.ledger {
		--ledger-above: #1fa898;
		--ledger-below: #e0663a;
		margin: 14px 0 18px;
		border-top: 1px solid var(--border);
		padding-top: 10px;
	}
	summary {
		cursor: pointer;
		display: flex;
		flex-wrap: wrap;
		gap: 4px 12px;
		align-items: baseline;
	}
	.title {
		font-size: 0.8rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		font-family: var(--font-mono);
	}
	.sum {
		font-variant-numeric: tabular-nums;
		color: var(--text);
		font-weight: 700;
	}
	.headline {
		margin: 10px 0 6px;
	}
	.chart {
		position: relative;
		max-width: 560px;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
		overflow: visible;
	}
	.bar.above {
		fill: var(--ledger-above);
	}
	.bar.below {
		fill: var(--ledger-below);
	}
	.bar.prov {
		fill-opacity: 0.55;
	}
	.bar.dim {
		fill-opacity: 0.35;
	}
	.hit {
		fill: transparent;
		outline: none;
		cursor: default;
	}
	.hit:focus-visible {
		stroke: var(--text);
		stroke-width: 1;
	}
	.zero {
		stroke: var(--border-strong);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	.gw {
		fill: var(--text-muted);
		font-size: 9px;
		font-family: var(--font-mono);
	}
	.tip {
		position: absolute;
		transform: translate(-50%, calc(-100% - 6px));
		background: var(--surface);
		border: 1px solid var(--border-strong);
		padding: 4px 8px;
		font-size: 0.8rem;
		white-space: nowrap;
		pointer-events: none;
		font-variant-numeric: tabular-nums;
	}
	.tip.edge-l {
		transform: translate(-12px, calc(-100% - 6px));
	}
	.tip.edge-r {
		transform: translate(calc(-100% + 12px), calc(-100% - 6px));
	}
	.legend {
		font-size: 0.8rem;
		color: var(--text-muted);
		margin: 6px 0;
	}
	.sw {
		display: inline-block;
		width: 10px;
		height: 10px;
		margin: 0 4px 0 8px;
		vertical-align: -1px;
	}
	.sw:first-child {
		margin-left: 0;
	}
	.sw.above {
		background: var(--ledger-above);
	}
	.sw.below {
		background: var(--ledger-below);
	}
	table {
		border-collapse: collapse;
		margin: 6px 0;
		font-size: 0.85rem;
	}
	th,
	td {
		text-align: left;
		padding: 3px 12px 3px 0;
		border-bottom: 1px solid var(--border);
	}
	.num {
		font-variant-numeric: tabular-nums;
	}
	.table summary {
		font-size: 0.8rem;
		color: var(--text-muted);
	}
	.muted {
		color: var(--text-muted);
	}
	.small {
		font-size: 0.85rem;
		margin: 4px 0;
	}
</style>
