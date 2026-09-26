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
	 * 26.9: hintarivit leikataan risers/fallers-listoilta ruudun runkoon, joten ne
	 * toimivat myos draftilla (ei entrya). Paivasana: $lib/priceEta.
	 */
	import { fetchPriceWatch, type PriceMove } from '$lib/fantasyTools';
	import { priceEtaWord, squadPriceMoves } from '$lib/priceEta';

	type Row = {
		id: number;
		web_name: string;
		chance_next?: number | null;
		news?: string | null;
		status?: string | null;
	};
	// `entry` sailyy propina (kutsupaikka), mutta hintarivit eivat enaa tarvitse
	// sita: risers/fallers leikataan ruudun runkoon (sama saanto kuin saatavuudella).
	let { players }: { players: Row[]; entry?: number | null } = $props();

	let lists = $state<{ risers: PriceMove[]; fallers: PriceMove[] } | null>(null);
	$effect(() => {
		fetchPriceWatch(null).then(
			(d) => (lists = { risers: d.risers ?? [], fallers: d.fallers ?? [] }),
			() => (lists = null)
		);
	});

	const ids = $derived(new Set(players.map((p) => p.id)));
	// Portti k5: saatavuusrivi myos pelkan FPL-uutisen perusteella (lahtenyt
	// tai pelikieltoinen pelaaja: news taynna, chance_next null).
	const avail = $derived(
		players.filter(
			(p) =>
				(typeof p.status === 'string' && p.status !== 'a') ||
				(typeof p.news === 'string' && p.news.trim() !== '') ||
				(typeof p.chance_next === 'number' && p.chance_next < 100)
		)
	);
	// 26.9 (PRICE-ETA-ABSOLUUTTINEN-AIKA): vain `_soon` + tuleva `eta_at`, ja
	// paivasana lukijan paikallisessa ajassa ($lib/priceEta). Ennen "tonight"
	// johdettiin eta_days-offsetista ja oli vaarin Amerikoissa joka ilta.
	const moves = $derived(squadPriceMoves(ids, lists?.risers, lists?.fallers, Date.now()));
</script>

{#if avail.length || moves.rising.length || moves.falling.length}
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
			{#each moves.rising as m (m.id)}
				<li><strong>{m.web_name}</strong> price rise {priceEtaWord(m.eta)}</li>
			{/each}
			{#each moves.falling as m (m.id)}
				<li><strong>{m.web_name}</strong> price fall {priceEtaWord(m.eta)}</li>
			{/each}
		</ul>
		<!-- Portti k5: lahde nakyy aina, ei vain manual-moodissa. Hintaliike on
		     FPL:n oma projektio ja paiva liikkuu myohaisten siirtojen mukana. -->
		<p class="muted small">
			Availability from FPL. Price moves are FPL's own projection, and the day moves with
			late transfers.
		</p>
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
