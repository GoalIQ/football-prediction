<script lang="ts">
	/**
	 * TUOTE EDELLA (Villen paatos 5.9.2026).
	 *
	 * Ennen tata: kirjautumaton kavija sai `pro.goaliq.app`:n juuresta tyhjan
	 * kuoren — banneri, kuusi valilehtea ja tyhjatila "Set up your team first".
	 * Mitattu 5.9: sivulla ei ollut yhtaan riviaa siita mita maksaminen antaa,
	 * koska `PremiumPreview` importataan vain `ToolsHome`:ssa eli se nakyy
	 * vasta `/tools`-valilehdella. Maksutuotteen oma domain ei siis nayttanyt
	 * tuotetta lainkaan.
	 *
	 * MIKSI TAMA NAYTTAA OIKEAA DATAA EIKA KUVAKAAPPAUSTA: seuraavan kierroksen
	 * xP-karki on ilmaista tasoa jo nyt (goaliq.app/fpl julkaisee top 20:n
	 * ilman kirjautumista), joten oikean listan nayttaminen ei anna pois
	 * mitaan maksullista. Ja elava lista on parempi tuote-esittely kuin kuva:
	 * se on se tuote, ei kuva siita. Jos haku epaonnistuu, lohko jaa pois
	 * kokonaan — tyhja taulukko olisi huonompi kuin ei taulukkoa.
	 *
	 * VAITEDISIPLIINI: tassa ei ole yhtaan lukua jota lukija ei paase
	 * tarkistamaan ilmaispinnalta. Tarkkuusluku ja otoskoko tulevat samasta
	 * lahteesta kuin landingin track record, ja linkki vie siihen.
	 */
	import { onMount } from 'svelte';
	import { fetchXp, gwXp, type XpResponse } from '$lib/api';
	import { actionableGameweek } from '$lib/gameweek';
	import { freePremiumWindowActive } from '$lib/auth.svelte';
	import { capture } from '$lib/analytics';
	import { planApprox } from '$lib/billing';

	let { onUpgrade }: { onUpgrade: () => void } = $props();

	let xp = $state<XpResponse | null>(null);

	onMount(() => {
		capture('product_intro_shown', { source: 'pro_web_root' }, 'product_intro_shown');
		fetchXp().then(
			(d) => (xp = d),
			() => {}
		);
	});

	const gw = $derived(actionableGameweek(xp?.meta));

	/**
	 * 🔴 LAJITTELUAVAIN ON SAMA KUIN MASKISSA. Ensimmainen versio lajitteli
	 * GW-xP:lla, mutta `mask_xp_payload` (api/premium.py) valitsee anonyymin
	 * kymmenikon `xp_horizon_total`-jarjestyksessa ENNEN kuin tama koodi
	 * nakee sen. Uudelleenlajittelu GW:lla tuotti listan (Isak, Szoboszlai,
	 * B.Fernandes, Gakpo, Wirtz) jota ei ollut millaan ilmaispinnalla;
	 * goaliq.app/fpl/expected-points naytti Virgil, Isak, Szoboszlai, Joao
	 * Pedro, Palmer. Portti loysi sen 5.9. Nyt lista on sama rivi rivilta kuin
	 * ilmaissivun "ranked by total xP over GW{gw}-{gw+4}" -taulukko.
	 */
	const top = $derived.by(() => {
		if (!xp?.meta?.available) return [];
		return [...xp.players]
			.sort((a, b) => (b.xp_horizon_total ?? 0) - (a.xp_horizon_total ?? 0))
			.slice(0, 5);
	});
	const gwTo = $derived((gw ?? 0) + 4);

	/**
	 * Ikkunan aikana kutsu on "luo tili", koska maksaminen nyt ostaisi viikkoja
	 * jotka kayttaja saa ilmaiseksi (sama perustelu kuin Paywallissa). Ikkunan
	 * jalkeen sama nappi myy tilauksen. Yksi haara, ei kahta copya joista
	 * toinen vanhenee.
	 */
	const inWindow = $derived(freePremiumWindowActive());

	/**
	 * Euro on hinnoittelun valuutta ja se sanotaan aina. `planApprox` on
	 * NAYTON likiarvo GBP/USD-kavijalle (Stripe Adaptive Pricing veloittaa
	 * kavijan valuutassa) ja se palauttaa nullin euroalueella, joten se
	 * liitetaan peraan vain kun se on olemassa. Alkuperainen versio talla
	 * rivilla kutsui planApproxia plan-OLIOLLA eika avaimella; se olisi
	 * kaantynyt virheeksi, mutta tarkeampi virhe oli etta euro olisi
	 * kadonnut nakyvista kokonaan.
	 */
	const approxMonthly = $derived(planApprox('monthly'));
	const approxSeason = $derived(planApprox('season'));
</script>

<section class="intro" aria-labelledby="intro-h">
	<p class="eyebrow">FPL tools from a match model with a public record</p>
	<h1 id="intro-h">
		Get a squad you can defend<br />before the deadline
	</h1>
	<p class="lede">
		GoalIQ projects every player's points for the gameweeks ahead and ranks your captain
		options against each other. On transfers it'll often tell you to hold, because the best
		move it checked isn't worth the free transfer. The same model logs a call on every match
		before kick-off and we publish how those went.
	</p>

	{#if top.length > 0}
		<!-- ELAVA TUOTE, EI KUVA. Tama on tasan se lista jota tyokalu nayttaa;
		     top 20 samasta projektiosta on ilmaista tasoa myos goaliq.app/fpl:ssa. -->
		<div class="demo">
			<div class="demo-head">
				<span class="demo-title">Projected points, GW{gw}-{gwTo} total</span>
				<span class="demo-tag">live from the model</span>
			</div>
			<table>
				<thead>
					<tr>
						<th scope="col">Player</th>
						<th scope="col" class="ta-r">GW{gw} xP</th>
						<th scope="col" class="ta-r">GW{gw}-{gwTo}</th>
					</tr>
				</thead>
				<tbody>
					{#each top as p (p.id)}
						<tr>
							<td
								>{p.web_name}
								<span class="muted">{p.team_short} · {p.pos}</span></td
							>
							<td class="num ta-r">{gwXp(p, gw).toFixed(1)}</td>
							<td class="num ta-r">{(p.xp_horizon_total ?? 0).toFixed(1)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="demo-foot muted">
				The same table is free at
				<a href="https://goaliq.app/fpl/expected-points">goaliq.app/fpl/expected-points</a>,
				top twenty. Premium is the whole list, every gameweek in the window, ownership
				beside it, and the captain ranker built on it.
			</p>
		</div>
	{/if}

	<div class="what">
		<h2>What you get</h2>
		<ul>
			<li>
				The best move the model checked, with the hit priced in. Often that's a hold, and
				it says so.
			</li>
			<li><strong>Captain ranker:</strong> the top three, a differential and the bonus expectation.</li>
			<li>A rolling planner over the gameweeks in the window.</li>
			<li>Chip windows, scored against your own squad.</li>
			<li>
				<strong>The whole list.</strong> Free shows twenty players for the next gameweek;
				Premium shows all of them, every gameweek, with CSV export.
			</li>
			<li>Who actually closes the gap on your mini-league rival, and whether they own them already.</li>
		</ul>
	</div>

	<div class="act">
		{#if inWindow}
			<button type="button" class="primary" onclick={onUpgrade}>Create a free account</button>
			<p class="act-note muted">
				Premium is free until 12 September. No card, nothing to cancel. After that it is
				€3.99 a month or €25 for the season{#if approxMonthly}
					({approxMonthly}, {approxSeason}){/if}.
			</p>
		{:else}
			<button type="button" class="primary" onclick={onUpgrade}>See plans</button>
			<p class="act-note muted">
				€3.99 a month or €25 for the season{#if approxMonthly}
					({approxMonthly}, {approxSeason}){/if}. Cancel anytime. One subscription covers
				web, iOS and Android.
			</p>
		{/if}
		<p class="act-proof muted">
			Every match prediction is logged before kick-off and graded after, hits and misses
			included. <a href="https://goaliq.app/fpl#track-record">See the record</a>.
		</p>
	</div>
</section>

<style>
	.intro {
		border: 1px solid var(--border);
		border-top: 3px solid var(--accent);
		padding: var(--s-6) var(--s-5) var(--s-5);
		margin-bottom: var(--s-8);
		background: var(--surface);
	}

	.eyebrow {
		font-family: var(--font-mono);
		font-size: 0.78rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--accent);
		margin: 0 0 var(--s-3);
		max-width: none;
	}

	h1 {
		font-size: var(--step-3);
		margin: 0 0 var(--s-4);
		text-transform: none;
		letter-spacing: -0.02em;
		line-height: 1.12;
	}

	.lede {
		font-size: 1.05rem;
		color: var(--text);
		margin: 0 0 var(--s-6);
	}

	/* Demo: sama taulukkokieli kuin tyokaluissa, jotta esittely ja tuote
	   nayttavat samalta eika kavija koe vaihtaneensa sivustoa ostaessaan. */
	.demo {
		border: 1px solid var(--border);
		margin: 0 0 var(--s-6);
	}
	.demo-head {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2);
		justify-content: space-between;
		align-items: baseline;
		padding: var(--s-2) var(--s-3);
		border-bottom: 1px solid var(--border);
	}
	.demo-title {
		font-family: var(--font-mono);
		font-size: 0.8rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.demo-tag {
		font-family: var(--font-mono);
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--giq-teal);
	}
	.demo table {
		width: 100%;
		border-collapse: collapse;
	}
	.demo th,
	.demo td {
		padding: var(--s-2) var(--s-3);
		text-align: left;
		border-bottom: 1px solid var(--border);
	}
	.demo th {
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
		font-weight: 600;
	}
	.demo tbody tr:last-child td {
		border-bottom: 0;
	}
	.ta-r {
		text-align: right;
	}
	.demo .num {
		color: var(--accent);
		font-weight: 700;
	}
	.demo .muted {
		font-size: 0.8rem;
	}
	.demo-foot {
		padding: var(--s-3);
		margin: 0;
		border-top: 1px solid var(--border);
		font-size: 0.85rem;
	}

	.what h2 {
		font-size: var(--step-1);
		margin: 0 0 var(--s-3);
	}
	.what ul {
		list-style: none;
		padding: 0;
		margin: 0 0 var(--s-6);
		display: grid;
		gap: var(--s-3);
	}
	.what li {
		padding-left: var(--s-4);
		position: relative;
		line-height: 1.6;
	}
	.what li::before {
		content: '';
		position: absolute;
		left: 0;
		top: 0.62em;
		width: 8px;
		height: 1px;
		background: var(--accent);
	}
	.what strong {
		color: var(--text);
	}

	.act {
		border-top: 1px solid var(--border);
		padding-top: var(--s-5);
	}
	.act-note {
		margin: var(--s-3) 0 0;
	}
	.act-proof {
		margin: var(--s-2) 0 0;
		font-size: 0.85rem;
	}

	@media (min-width: 900px) {
		/* Kahdella palstalla lupaus ja todiste ovat samalla ruudulla: kavijan
		   ei tarvitse vierittaa nahdakseen etta luvut ovat oikeita. */
		.what ul {
			grid-template-columns: 1fr 1fr;
			gap: var(--s-3) var(--s-6);
		}
	}

	@media (max-width: 560px) {
		.intro {
			padding: var(--s-5) var(--s-3) var(--s-4);
		}
		h1 {
			font-size: 1.6rem;
		}
		.lede {
			font-size: 1rem;
		}
	}
</style>
