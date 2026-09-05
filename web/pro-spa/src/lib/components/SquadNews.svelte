<script lang="ts">
	/**
	 * SquadNews (5.9.2026, Villen pyynto: "team news mista nakee nopeesti omaa
	 * tiimia koskevat essentials"). Renderoidaan My teamissa kentan alle.
	 *
	 * 🔴 PORTTI k4: ensimmainen versio luki GwReview'n liput, ja ne rakennetaan
	 * VIIMEISEN PAATTYNEEN kierroksen pickeista (gw-review reviewed_gw). Kesken
	 * kierroksen se on eri joukkue kuin pitch sen ylapuolella (mitattu livena:
	 * entry 1 -> 14/15 pelaajaa eri). Nyt lahde on sama runko joka on ruudulla:
	 * saatavuus `players`-listasta (FPL:n chance_next/news/status artefaktissa),
	 * hintaliikkeet price watchista ja VAIN niille id:ille jotka ovat rungossa.
	 * Manual-moodissa (ei entrya) hintarivit jaavat pois.
	 */
	import { fetchPriceWatch, type PriceWatchOwnedMove } from '$lib/fantasyTools';

	type Row = {
		id: number;
		web_name: string;
		chance_next?: number | null;
		news?: string | null;
		status?: string | null;
	};
	let { players, entry }: { players: Row[]; entry: number | null } = $props();

	let moves = $state<{ rising: PriceWatchOwnedMove[]; falling: PriceWatchOwnedMove[] } | null>(null);
	let loadedEntry = $state<number | null>(null);

	$effect(() => {
		if (entry == null) {
			moves = null;
			loadedEntry = null;
			return;
		}
		if (loadedEntry === entry) return;
		loadedEntry = entry;
		fetchPriceWatch(entry).then(
			(d) => {
				moves = d.owned ? { rising: d.owned.rising ?? [], falling: d.owned.falling ?? [] } : null;
			},
			() => (moves = null)
		);
	});

	const ids = $derived(new Set(players.map((p) => p.id)));
	const avail = $derived(
		players.filter(
			(p) =>
				(typeof p.status === 'string' && p.status !== 'a') ||
				(typeof p.chance_next === 'number' && p.chance_next < 100)
		)
	);
	const rising = $derived((moves?.rising ?? []).filter((m) => ids.has(m.id)));
	const falling = $derived((moves?.falling ?? []).filter((m) => ids.has(m.id)));

	function eta(m: PriceWatchOwnedMove): string {
		if (m.eta_days == null) return 'no date yet';
		if (m.eta_days <= 0) return 'tonight';
		if (m.eta_days === 1) return 'tomorrow';
		return `in ${m.eta_days} days`;
	}
</script>

{#if avail.length || rising.length || falling.length}
	<section class="wrap squad-news">
		<h3>Your squad before the deadline</h3>
		<ul>
			{#each avail as p (p.id)}
				<li>
					<strong>{p.web_name}</strong>
					{#if typeof p.chance_next === 'number'}{p.chance_next}% to play{/if}
					{#if p.news}<span class="muted">{p.news}</span>{/if}
				</li>
			{/each}
			{#each rising as m (m.id)}
				<li><strong>{m.web_name}</strong> price rise {eta(m)}</li>
			{/each}
			{#each falling as m (m.id)}
				<li><strong>{m.web_name}</strong> price fall {eta(m)}</li>
			{/each}
		</ul>
		{#if entry == null}
			<p class="muted small">Availability from FPL. Price moves need an entry ID.</p>
		{/if}
	</section>
{/if}

<style>
	.wrap {
		margin: 14px 0 18px;
	}
	h3 {
		font-size: 0.8rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		margin: 0 0 6px;
		font-family: var(--font-mono);
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	li {
		padding: 4px 0;
		border-bottom: 1px solid var(--border);
	}
	li:last-child {
		border-bottom: 0;
	}
	.muted {
		color: var(--text-muted);
	}
	.small {
		font-size: 0.85rem;
	}
</style>
