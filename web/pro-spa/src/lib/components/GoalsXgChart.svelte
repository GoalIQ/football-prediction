<script lang="ts">
	/**
	 * MP-17 (27.9.2026): maalit vs xG kumulatiivisena. Luvut ja geometria
	 * $lib/goalsXg:sta (yksi lukija), tama vain piirtaa. FPL:n omat luvut,
	 * joten ILMAINEN kuten muu "Season so far" -osio.
	 *
	 * Vari ei ole ainoa koodaus: maalit yhtenainen, xG katkoviiva, molemmilla
	 * nakyva nimilappu viivan paassa ja legenda. Paletti validoitu dataviz-
	 * validaattorilla tummaa pintaa #141311 vasten: #B8891A / #1FA898, kaikki
	 * kuusi tarkistusta PASS (CVD dE 13.9, normaali 18.5).
	 */
	import type { PlayerStatsGw } from '$lib/fantasyTools';
	import {
		GOALS_XG_ARIA,
		GOALS_XG_CAPTION,
		GOALS_XG_TITLE,
		goalsXgGeometry,
		goalsXgHeadline,
		goalsXgTooltip,
		goalsXgView
	} from '$lib/goalsXg';

	let { gws }: { gws: PlayerStatsGw[] | null | undefined } = $props();

	const W = 320;
	const H = 120;
	const view = $derived(goalsXgView(gws));
	const geom = $derived(view ? goalsXgGeometry(view, W, H) : null);
	let active = $state<number | null>(null);
</script>

{#if view && geom}
	<section class="gxg">
		<h4 class="gw-title">
			{GOALS_XG_TITLE} <span class="src">source: FPL</span>
		</h4>
		<p class="headline">{goalsXgHeadline(view)}</p>
		<div class="line-chart">
			<svg viewBox="0 0 {W} {H}" role="group" aria-label={GOALS_XG_ARIA}>
				<line class="base" x1={geom.plotLeft} x2={geom.plotRight} y1={geom.baseline} y2={geom.baseline} />
				<path class="xg" d={geom.xgPath} />
				<path class="goals" d={geom.goalsPath} />
				{#each geom.markers as m (m.p.gw)}
					{#if active === m.i}
						<circle class="pt xg" cx={m.cx} cy={m.xy} r="4" />
						<circle class="pt goals" cx={m.cx} cy={m.gy} r="4" />
					{/if}
					<rect
						class="hit"
						x={m.cx - geom.slot / 2}
						y="0"
						width={geom.slot}
						height={H}
						tabindex="0"
						role="button"
						aria-label={goalsXgTooltip(m.p)}
						onmouseenter={() => (active = m.i)}
						onmouseleave={() => (active = null)}
						onfocus={() => (active = m.i)}
						onblur={() => (active = null)}
					/>
					<text class="tick" x={m.cx} y={H - 4} text-anchor="middle">{m.p.gw}</text>
				{/each}
				<text class="end goals" x={geom.labelX} y={geom.labelGoalsY}>Goals {view.totalG}</text>
				<text class="end xg" x={geom.labelX} y={geom.labelXgY}>xG {view.totalXg.toFixed(1)}</text>
				<text class="tick" x={geom.plotLeft} y={geom.top - 2}>{geom.hi}</text>
			</svg>
			{#if active != null}
				{@const m = geom.markers[active]}
				<div
					class="tip"
					class:edge-l={m.cx / W < 0.35}
					class:edge-r={m.cx / W > 0.65}
					style="left: {((m.cx / W) * 100).toFixed(2)}%; top: {((Math.min(m.gy, m.xy) / H) * 100).toFixed(2)}%"
				>
					{goalsXgTooltip(m.p)}
				</div>
			{/if}
		</div>
		<p class="legend">
			<span class="sw goals" aria-hidden="true"></span> goals
			<span class="sw xg" aria-hidden="true"></span> expected goals (xG)
			<span class="muted">· GW on the axis</span>
		</p>
		<p class="muted hintline">{GOALS_XG_CAPTION}</p>
		<details class="table">
			<summary>Show as a table</summary>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>GW</th>
							<th class="num">Goals</th>
							<th class="num">xG</th>
							<th class="num">Goals so far</th>
							<th class="num">xG so far</th>
						</tr>
					</thead>
					<tbody>
						{#each view.points as p (p.gw)}
							<tr>
								<td>GW{p.gw}</td>
								<td class="num">{p.hasRow ? p.g : ''}</td>
								<td class="num">{p.hasRow ? p.xg.toFixed(2) : ''}</td>
								<td class="num">{p.cumG}</td>
								<td class="num">{p.cumXg.toFixed(2)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	</section>
{/if}

<style>
	.gxg {
		--gxg-goals: #b8891a;
		--gxg-xg: #1fa898;
		margin-top: var(--s-4);
	}
	.headline {
		margin: var(--s-1) 0 0;
		font-variant-numeric: tabular-nums;
	}
	.line-chart {
		position: relative;
		max-width: 560px;
		margin: var(--s-2) 0 0;
	}
	.line-chart svg {
		display: block;
		width: 100%;
		height: auto;
		overflow: visible;
	}
	.line-chart .base {
		stroke: var(--border-strong);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	.line-chart path {
		fill: none;
		stroke-width: 2;
		vector-effect: non-scaling-stroke;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.line-chart path.goals {
		stroke: var(--gxg-goals);
	}
	.line-chart path.xg {
		stroke: var(--gxg-xg);
		stroke-dasharray: 5 4;
	}
	.line-chart .pt {
		stroke: var(--surface);
		stroke-width: 2;
	}
	.line-chart .pt.goals {
		fill: var(--gxg-goals);
	}
	.line-chart .pt.xg {
		fill: var(--gxg-xg);
	}
	.line-chart .hit {
		fill: transparent;
		outline: none;
	}
	.line-chart .hit:focus-visible {
		stroke: var(--text);
		stroke-width: 1;
	}
	.line-chart .tick {
		fill: var(--text-muted);
		font-size: 9px;
		font-family: var(--font-mono);
	}
	.line-chart .end {
		fill: var(--text);
		font-size: 9px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.line-chart .tip {
		position: absolute;
		transform: translate(-50%, calc(-100% - 8px));
		background: var(--surface);
		border: 1px solid var(--border-strong);
		padding: 4px 8px;
		font-size: 0.8rem;
		width: max-content;
		max-width: min(260px, 80vw);
		white-space: normal;
		pointer-events: none;
		font-variant-numeric: tabular-nums;
		z-index: 1;
	}
	.line-chart .tip.edge-l {
		transform: translate(-12px, calc(-100% - 8px));
	}
	.line-chart .tip.edge-r {
		transform: translate(calc(-100% + 12px), calc(-100% - 8px));
	}
	.legend {
		font-size: 0.8rem;
		margin: var(--s-1) 0 0;
	}
	.legend .sw {
		display: inline-block;
		width: 14px;
		height: 0;
		border-top: 2px solid var(--gxg-goals);
		vertical-align: middle;
		margin: 0 4px 0 0;
	}
	.legend .sw.xg {
		border-top: 2px dashed var(--gxg-xg);
		margin-left: 8px;
	}
	.table summary {
		cursor: pointer;
		font-size: 0.8rem;
		color: var(--text-muted);
		margin-top: var(--s-2);
	}
	.table table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	.table th,
	.table td {
		padding: 4px 6px;
		border-bottom: 1px solid var(--border);
		text-align: left;
	}
	.table .num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
</style>
