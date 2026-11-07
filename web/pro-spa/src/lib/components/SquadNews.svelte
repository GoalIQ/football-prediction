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
	 *
	 * 17.10.2026 (tyokalut taakse, spec rivi 10): Premiumia, klienttiportti.
	 * Lukitus $lib/personalLock-lukijasta: ilman Premiumia ei hakua eika
	 * piirtoa. Lukitusnakyma on Rate my teamin oma (LOCK_COPY 'rate-my-team'
	 * mainitsee squad newsin), joten tama ei piirra omaa.
	 */
	import { personalLock } from '$lib/personalLock';
	import { fetchPriceWatch, type PriceMove } from '$lib/fantasyTools';
	import { priceEtaWord, squadPriceMoves } from '$lib/priceEta';
	import { clock } from '$lib/now.svelte';

	type Row = {
		id: number;
		web_name: string;
		chance_next?: number | null;
		news?: string | null;
		status?: string | null;
	};
	// `entry` sailyy propina (kutsupaikka), mutta hintarivit eivat enaa tarvitse
	// sita: risers/fallers leikataan ruudun runkoon (sama saanto kuin saatavuudella).
	let {
		players,
		premium = false,
		updated = null,
		onCount
	}: {
		players: Row[];
		entry?: number | null;
		premium?: boolean;
		/** WP16: paiva jolta saatavuusliput ovat ($lib/myTeamFlow flowUpdateDay). */
		updated?: string | null;
		/** WP16: rivien maara virran otsikkoriville. null = ei tiedossa: nolla ei
		 *  todista mitaan kun hintahaku on kesken tai epaonnistui. */
		onCount?: (n: number | null) => void;
	} = $props();

	const locked = $derived(personalLock(premium));
	let lists = $state<{ risers: PriceMove[]; fallers: PriceMove[] } | null>(null);
	$effect(() => {
		if (locked) {
			lists = null;
			return;
		}
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
	const moves = $derived(squadPriceMoves(ids, lists?.risers, lists?.fallers, clock.now));
	$effect(() => {
		const n = avail.length + moves.rising.length + moves.falling.length;
		onCount?.(n === 0 && lists === null ? null : n);
	});
</script>

{#if !locked && (avail.length || moves.rising.length || moves.falling.length)}
	<section class="wrap squad-news">
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
			{#if updated}Availability as of the model's {updated} update.{:else}Availability as of the
				model's last update.{/if} Price moves are FPL's own projection, and the day moves with
			late transfers.
		</p>
	</section>
{:else if !locked}
	<!-- WP16: paneelin otsikko on kysymys, joten tyhja tila sanotaan aaneen.
	     Vain saatavuudesta: hintahaku voi epaonnistua, joten tyhja lista ei
	     todista etta hintaliikkeita ei ole. Paiva mukana, koska liput tulevat
	     artefaktista: 7.11 FPL liputti 11 pelaajaa jotka artefaktissa olivat
	     puhtaita. -->
	<p class="muted">
		{#if updated}No availability flags on your squad as of the model's {updated} update.{:else}No
			availability flags on your squad as of the model's last update.{/if}
	</p>
{/if}

<style>
	.wrap {
		margin: 14px 0 18px;
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
