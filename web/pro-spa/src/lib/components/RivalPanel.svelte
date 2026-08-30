<script lang="ts">
	/**
	 * RivalPanel — "Catch your rival" (MINI-LEAGUE-RIVAL).
	 * Mobiilin components/RivalPanel.tsx -vastine; säännöt ja copy identtiset.
	 *
	 * Spec: goaliq-app/cos-reports/mini-league-rival-spec-2026-08-13.md
	 *
	 * Klientti ei laske mitään: P(catch), asema ja differentiaalit tulevat
	 * /api/fantasy/rival -endpointilta, joka jakaa varianssimallin h2h:n kanssa.
	 *
	 * REHELLISYYS:
	 *  - riippumattomuusoletus näytetään lukijalle (meta.method)
	 *  - P(catch) tulee valmiiksi 5 %:iin pyöristettynä; EI muotoilla tarkemmaksi
	 *  - esikaudella entryt eivät ole julkisia → virhe kerrotaan, ei arvata
	 *  - johtajan ja takaa-ajajan ohje on ERI, se on koko idea
	 */
	import { fetchRival, type RivalResponse } from '$lib/api';
	import { capture } from '$lib/analytics';
	import { shareRivalCard, shareButtonLabel} from '$lib/shareCard';

	let { entry, rival, leagueId, rivalName }: {
		entry: number;
		rival: number;
		leagueId: number;
		rivalName: string;
	} = $props();

	let data = $state<RivalResponse | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(false);
	let loadedKey = $state<string | null>(null);
	let sharing = $state(false);

	/* 22.8 (Villen tilaus): jakokortti TÄHÄN osioon, koska tässä näkyy vain
	 * rivaalin JOUKKUEEN nimi (julkinen liigataulukko). Kortille menee gap,
	 * P(catch), GW:t jäljellä ja advice-lause — EI differentiaalipelaajia
	 * eikä managerin nimeä. */
	async function shareCard() {
		if (!data) return;
		sharing = true;
		try {
			capture('rival_card_shared', {
				stance: data.stance,
				behind: data.behind,
				gameweeks_left: data.meta.gameweeks_left
			});
			await shareRivalCard({
				rivalName,
				gap: Math.abs(data.gap),
				behind: data.behind,
				pCatch: data.p_catch,
				gameweeksLeft: data.meta.gameweeks_left,
				gw: data.meta.gw,
				advice: advice(data),
				fileName: 'goaliq-catch-your-rival.png'
			});
		} finally {
			sharing = false;
		}
	}

	$effect(() => {
		const key = `${entry}-${rival}-${leagueId}`;
		if (loadedKey === key) return;
		loadedKey = key;
		data = null;
		error = null;
		loading = true;
		fetchRival(entry, rival, leagueId)
			.then((r) => {
				data = r;
				capture('rival_viewed', {
					stance: r.stance,
					behind: r.behind,
					gameweeks_left: r.meta.gameweeks_left,
					masked: r.meta.masked
				});
			})
			.catch((e) => {
				error = e instanceof Error ? e.message : String(e);
			})
			.finally(() => {
				loading = false;
			});
	});

	/** Yksi lause per asema. UI ei keksi narratiivia — backend päättää aseman.
	 * 22.8 (julkaisuportin B6): lyhenteet mukaan — sama teksti menee
	 * jakokorttiin joka luetaan somepostauksena, ja lyhenteiden puute on
	 * selkein konetunnusmerkki. Mobiilin i18n (en/es/pt) kantaa yhä vanhaa
	 * muotoa — niputettava seuraavaan OTA:aan. */
	function advice(d: RivalResponse): string {
		switch (d.stance) {
			case 'protect':
				return `You're ahead. The risk is the players ${rivalName} has and you don't, so covering those protects the lead.`;
			case 'chase_variance':
				return `The gap is big for the gameweeks left, so steady gains won't close it. It takes players ${rivalName} doesn't have, and swings you can live with.`;
			case 'chase_steady':
				return `There's time. Ordinary points gains close this gap, no need to reach for high-risk picks yet.`;
			default:
				return `You're level. Maximising projected points is the whole job here.`;
		}
	}
</script>

<section class="rival">
	<h3>Catch your rival</h3>

	{#if loading}
		<p class="muted">Working out what the gap takes…</p>
	{:else if error}
		<p class="muted">{error}</p>
	{:else if data}
		<p class="head">
			{#if data.behind}
				You are <strong>{Math.abs(data.gap)}</strong> points behind {rivalName}.
			{:else if data.gap === 0}
				You are level with {rivalName}.
			{:else}
				You are <strong>{Math.abs(data.gap)}</strong> points ahead of {rivalName}.
			{/if}
			{data.meta.gameweeks_left} gameweeks left.
		</p>

		<div class="pcatch">
			<!-- 22.8 (portin B2): tasatilanteessa luku on P(lopetat edellä),
			     ei P(pysyt edellä) — etumatkaa jota ei ole ei väitetä. -->
			<span class="lbl"
				>{data.behind
					? 'Chance to catch up'
					: data.gap === 0
						? 'Chance to finish ahead'
						: 'Chance to stay ahead'}</span
			>
			<span class="num">{Math.round(data.p_catch * 100)}%</span>
		</div>

		<p class="advice">{advice(data)}</p>

		<div class="share-row">
			<button type="button" class="share-btn" disabled={sharing} onclick={shareCard}>
				{sharing ? 'Building...' : shareButtonLabel()}
			</button>
		</div>

		{#if data.differentials && data.differentials.length > 0}
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>{data.stance === 'protect' ? 'Cover' : 'Consider'}</th>
							<th class="num">xP</th>
							<th class="num">
								<abbr title="How much this player can swing the gap, either way">Swing</abbr>
							</th>
							<th class="num">Owned</th>
						</tr>
					</thead>
					<tbody>
						{#each data.differentials as p (p.id)}
							<tr>
								<td>{p.web_name} <span class="muted">({p.team_short})</span></td>
								<td class="num">{p.xp_horizon}</td>
								<td class="num">{p.swing}</td>
								<td class="num">{p.owned_pct}%</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else if data.meta.masked}
			<p class="muted small">
				Premium shows which players close the gap from here, and whether your rival already
				has them.
			</p>
		{/if}

		<p class="muted small">{data.meta.method}</p>
	{/if}
</section>

<style>
	.rival {
		border: 2px solid var(--teal, #2ed6c2);
		border-radius: var(--radius);
		padding: var(--s-4);
		margin: var(--s-4) 0;
		background: var(--surface);
	}
	h3 {
		margin: 0 0 var(--s-3);
		font-size: var(--step--1);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
	}
	.head {
		margin: 0 0 var(--s-2);
	}
	.pcatch {
		display: flex;
		flex-direction: column;
		margin-bottom: var(--s-2);
	}
	.lbl {
		font-size: var(--step--2);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
	}
	.num {
		font-size: var(--step-3);
		font-weight: 700;
		color: var(--accent);
	}
	.advice {
		margin: 0 0 var(--s-3);
		font-weight: 600;
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--step--1);
	}
	th,
	td {
		text-align: left;
		padding: 0.3rem 0.5rem 0.3rem 0;
		border-top: 1px solid var(--border);
	}
	th.num,
	td.num {
		text-align: right;
		font-size: var(--step--1);
		font-weight: 400;
		color: var(--text);
	}
	th {
		font-size: var(--step--2);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
		font-weight: 700;
	}
	.small {
		font-size: var(--step--2);
		margin: var(--s-2) 0 0;
	}
	.share-row {
		margin: 0 0 var(--s-3);
	}
	.share-btn {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text);
		padding: 4px 12px;
		font-weight: 700;
		cursor: pointer;
	}
	.share-btn:disabled {
		opacity: 0.6;
		cursor: default;
	}
</style>
