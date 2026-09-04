<script lang="ts">
	/** DefCon-live (2.8.2026) — oman kokoonpanon defensive contribution KESKEN
	 * kierroksen. Tuotteen ainoa live-pinta.
	 *
	 * Renderöi tyhjää aina kun sanottavaa ei ole: esikaudella ja kierrosten
	 * välissä (meta.available=false) sekä ennen kuin yksikään pelaaja on
	 * pelannut minuuttiakaan. Kuollut paneeli on pahempi kuin ei paneelia.
	 *
	 * Päivittyy 60 s välein, mutta EI kun välilehti on taustalla — turha
	 * kuorma Renderin 0.5 vCPU:lle ja FPL:lle. Backend cachettaa saman 60 s.
	 */
	import { onMount } from 'svelte';
	import { fplEntry } from '$lib/fplEntry.svelte';
	import { fetchDefconLive, type DefconLiveResponse } from '$lib/api';
	import { capture } from '$lib/analytics';
	import { shareCard, canShareToApps } from '$lib/shareCard';

	const POLL_MS = 60_000;
	let data = $state<DefconLiveResponse | null>(null);
	// Plain let, EI $state: tätä luetaan ja kirjoitetaan efektin sisällä, ja
	// reaktiivisena se tekisi efektikehän (muisti: svelte-effect-cycle).
	let lastLoaded: string | null = null;

	const entryId = $derived.by(() => {
		const saved = fplEntry.savedEntry;
		if (saved && /^\d{1,10}$/.test(saved)) return saved;
		const typed = fplEntry.entry.trim();
		return /^\d{1,10}$/.test(typed) ? typed : null;
	});

	async function load(id: string) {
		try {
			const res = await fetchDefconLive(Number(id));
			data = res.meta.available ? res : null;
		} catch {
			data = null; // live-feedin katko ei saa näkyä virheenä työkalusivulla
		}
	}

	$effect(() => {
		const id = entryId;
		if (!id) {
			data = null;
			lastLoaded = null;
			return;
		}
		if (id !== lastLoaded) {
			lastLoaded = id;
			void load(id);
		}
	});

	onMount(() => {
		const timer = setInterval(() => {
			const id = entryId;
			if (id && !document.hidden) void load(id);
		}, POLL_MS);
		return () => clearInterval(timer);
	});

	/** Vain DefCon-kelpoiset (ei maalivahteja) jotka ovat pelanneet. */
	const rows = $derived(
		(data?.players ?? [])
			.filter((p) => p.eligible && p.minutes > 0)
			// Lähimpänä kynnystä ensin = toiminnallisin järjestys; jo osuneet
			// perään, koska niissä ei ole enää mitään seurattavaa.
			.sort((a, b) => {
				if (a.hit !== b.hit) return a.hit ? 1 : -1;
				return (a.remaining ?? 99) - (b.remaining ?? 99);
			})
	);
	const hits = $derived(rows.filter((p) => p.hit).length);
	/**
	 * 🔴 "live" oli sanana vaara aina kun kierros oli jo pelattu: lohko luki
	 * "DefCon live · GW2" vaikka mikaan ottelu ei ollut kaynnissa (nakyi
	 * tuotannossa 4.9). Nyt otsikko seuraa otteluiden tilaa. Tuntematon tila
	 * (feed ei vastannut) EI ole "paattynyt" — silloin kaytetaan neutraalia
	 * muotoa.
	 */
	const anyLive = $derived(rows.some((p) => p.match_state === 'live'));
	// 🔴 Portin loydos 4.9 (blokkaava): tama laskettiin ennen RENDEROIDYISTA
	// riveista, jotka on suodatettu `minutes > 0`. Perjantain ottelun jalkeen
	// otsikko olisi sanonut "GW3 final" vaikka 18 joukkuetta ei ole pelannut.
	// Kierroksen tila tulee nyt backendin metasta, joka katsoo KAIKKI ottelut.
	const gwFinished = $derived(data?.meta.gw_state === 'finished');

	let sharing = $state(false);

	/** YLAPINON BUDJETTI (4.9.2026, kilpailija-auditointi).
	 *
	 * 🔴 MITATTU: tama lista vei 13 riville ~450 px, ja se oli tyokalunavin
	 * YLAPUOLELLA. Mittaus 4.9: navi 938 px, ensimmainen tyokalupaneeli
	 * 1 006 px sivun ylalaidasta -> 1366x768-lapparilla maksava kayttaja ei
	 * nahnyt ilman vieritysta etta tuotteessa on tyokaluja lainkaan.
	 *
	 * Lista menee kokoontaitettavaksi, MUTTA yhteenvetorivi ("GW3 · 1/13 at
	 * the threshold") jaa nakyviin aina. Se on se aikakriittinen signaali,
	 * jonka takia lohko on 2.8 alkaen valilehtien ulkopuolella: kayttaja
	 * nakee joka valilehdella etta kierros on kesken ja montako on
	 * kynnyksella. Rivien yksityiskohdat ovat yhden klikkauksen paassa.
	 * (Varaus EI mene suljetun disclosuren taakse: luku on rivilla.)
	 */
	let expanded = $state(false);
	const OPEN_KEY = 'defcon_live_open';

	onMount(() => {
		try {
			expanded = sessionStorage.getItem(OPEN_KEY) === '1';
		} catch {
			// Privaatti-ikkuna tai estetty tallennus: oletus (kiinni) kelpaa.
		}
	});

	function toggle() {
		expanded = !expanded;
		try {
			sessionStorage.setItem(OPEN_KEY, expanded ? '1' : '0');
		} catch {
			// sama kuin yllä: tila ei saa kaataa nakymaa
		}
		capture('defcon_live_toggled', { open: expanded });
	}

	// 🔴 KORTTI ON KESKEN KIERROKSEN OTETTU TILANNEKUVA, JA SE SANOTAAN.
	// Ilman kellonaikaa lukija ei tieda onko luku lopullinen, ja DefCon-luvut
	// liikkuvat viela. Sama syy kuin gw-outlook-kortin "as of" -leimalla.
	async function share() {
		if (sharing) return;
		sharing = true;
		try {
			const method = await shareCard({
				title: 'DEFCON LIVE',
				subtitle: `GW${data?.meta.gw}, ${hits} of ${rows.length} at the threshold, in progress`,
				midLabel: 'MINS',
				valueLabel: 'DEFCON',
				fileName: 'goaliq_defcon_live.png',
				footNote: 'live FPL match feed',
				footNote2: 'not betting advice',
				// 🔴 3.9 (audit): `rows` on jarjestetty niin etta JO OSUNEET ovat
				// viimeisena (kentalla se on oikein: niissa ei ole enaa mitaan
				// seurattavaa). `slice(0, 10)` pudotti siis tasan ne rivit joista
				// alaotsikko puhuu — "2 of 12 at the threshold" ja kuvassa nolla.
				// Sama vika korjattiin mobiilissa jo; web jai. Osuneet ensin
				// kortille, loput lahimpana kynnysta.
				rows: [...rows]
					.sort((a, b) => {
						if (a.hit !== b.hit) return a.hit ? -1 : 1;
						return (a.remaining ?? 99) - (b.remaining ?? 99);
					})
					.slice(0, 10)
					.map((p, i) => ({
					rank: i + 1,
					name: p.is_captain ? `${p.web_name} (C)` : p.web_name,
					tag: p.pos,
					// `team_short` on DefCon-live-payloadissa nullable; kortin
					// CardRow vaatii stringin. Tyhja on oikea fallback: joukkuetta
					// ei arvata.
					team: p.team_short ?? '',
					mid: `${p.minutes}'`,
					// Kynnys mukaan: pelkka luku ei kerro onko se riittava, ja
					// kynnys vaihtelee positioittain.
					// Osuma merkitaan: kortilla ei ole varia joka kertoisi sen.
					value: `${p.defcon}/${p.threshold}${p.hit ? ' ✓' : ''}`
				}))
			});
			if (method !== 'aborted') capture('xp_card_shared', { list: 'defcon_live', method });
		} finally {
			sharing = false;
		}
	}

	let announced = false;
	$effect(() => {
		if (rows.length > 0 && !announced) {
			announced = true;
			capture('defcon_live_shown', { gw: data?.meta.gw ?? null, n: rows.length });
		}
	});
</script>

{#if rows.length > 0}
	<section class="dcl" aria-label="Defensive contribution, live">
		<div class="bar">
			<button
				type="button"
				class="summary"
				aria-expanded={expanded}
				aria-controls="dcl-list"
				onclick={toggle}
			>
				<span class="caret" aria-hidden="true">{expanded ? '▾' : '▸'}</span>
				{#if anyLive}
					DefCon live · GW{data?.meta.gw} · {hits}/{rows.length} at the threshold
				{:else if gwFinished}
					DefCon · GW{data?.meta.gw} final · {hits}/{rows.length} reached the threshold
				{:else}
					DefCon · GW{data?.meta.gw} · {hits}/{rows.length} at the threshold
				{/if}
			</button>
			{#if expanded}
				<button type="button" class="window-chip" onclick={share} disabled={sharing}>
					{sharing ? 'Rendering…' : canShareToApps() ? 'Share' : 'Download'}
				</button>
			{/if}
		</div>
		{#if expanded}
		<ul id="dcl-list">
			{#each rows as p (p.id)}
				<!-- 4.9: rivi on kategoria + lause + luku, ei pelkka luku.
				     Sama luku tarkoittaa eri asiaa kesken ottelun ja sen
				     jalkeen; lause tulee backendista (`defcon_story`) jotta
				     tulkinta on yhdessa paikassa ja testattavissa. -->
				<li class:hit={p.hit}>
					<span class="who">
						{#if p.story?.tag}
							<span class="tag tag-{p.story.tag.toLowerCase().replace(' ', '-')}"
								>{p.story.tag}</span
							>
						{/if}
						<span class="name">{p.web_name}</span>
						{#if p.is_captain}<span class="c" title="Captain">C</span>{/if}
						<span class="meta">{p.team_short} · {p.pos} · {p.minutes}'</span>
					</span>
					{#if p.story?.line}
						<!-- Lause vain kun se lisaa jotain: SHORT ja tuntematon tila
						     saavat kategorian mutta ei lausetta, koska lause
						     toistaisi viereisen sarakkeen luvun (portti 4.9). -->
						<span class="story">{p.story.line}</span>
					{/if}
					<span class="track" aria-hidden="true">
						<span
							class="fill"
							style="width: {Math.min(100, (p.defcon / (p.threshold || 1)) * 100)}%"
						></span>
					</span>
					<span class="num">
						{p.defcon}/{p.threshold}
						{#if p.hit}<span class="ok">✓ 2 pts</span>{/if}
					</span>
				</li>
			{/each}
		</ul>
		<p class="note">{data?.meta.note}</p>
		{/if}
	</section>
{/if}

<style>
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--s-2);
		flex-wrap: wrap;
	}
	/* Yhteenvetorivi on nappi, mutta nayttaa rivilta: sama teksti kuin ennen,
	   ei uutta varia eika uutta korostusta. Vain kolmio kertoo etta se avautuu. */
	.summary {
		flex: 1 1 auto;
		display: inline-flex;
		align-items: center;
		gap: 0.5ch;
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}
	.summary:hover {
		text-decoration: underline;
	}
	.caret {
		color: var(--text-muted);
	}
	.tag {
		font-size: 0.68rem;
		letter-spacing: 0.06em;
		font-weight: 700;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0 0.5em;
		color: var(--text-muted);
		white-space: nowrap;
	}
	/* Vari kertoo vain kiireellisyyden, ei uutta merkitysta: kynnyksella
	   oleva on meripihka, osunut turkoosi, muut hiljaisia. */
	.tag-close {
		color: var(--accent-strong);
		border-color: var(--accent);
	}
	.tag-scored {
		color: var(--giq-teal, var(--text-muted));
		border-color: currentColor;
	}
	.story {
		grid-column: 1 / -1;
		font-size: var(--step--1);
		color: var(--text-muted);
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
	.dcl {
		border: 1px solid var(--track);
		background: var(--panel);
		margin-bottom: 16px;
	}
	.bar {
		background: var(--cream);
		color: var(--ink);
		font-size: 11.5px;
		text-transform: uppercase;
		letter-spacing: 0.16em;
		padding: 6px 10px;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 8px 10px;
		display: grid;
		gap: 6px;
	}
	li {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 90px auto;
		gap: 10px;
		align-items: center;
		font-size: 13px;
	}
	.who {
		display: flex;
		gap: 6px;
		align-items: baseline;
		min-width: 0;
	}
	.name {
		color: var(--cream);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.c {
		color: var(--ink);
		background: var(--amber);
		font-size: 10px;
		padding: 0 4px;
		font-weight: 700;
	}
	.meta {
		color: var(--faint);
		font-size: 11px;
		white-space: nowrap;
	}
	.track {
		height: 6px;
		background: var(--track);
		display: block;
	}
	.fill {
		height: 100%;
		background: var(--amber);
		display: block;
	}
	li.hit .fill {
		background: var(--green);
	}
	.num {
		font-variant-numeric: tabular-nums;
		color: var(--muted);
		white-space: nowrap;
	}
	.ok {
		color: var(--green);
		margin-left: 6px;
	}
	.note {
		color: var(--faint);
		font-size: 11px;
		margin: 0;
		padding: 0 10px 10px;
	}
	@media (max-width: 520px) {
		li {
			grid-template-columns: minmax(0, 1fr) 56px auto;
		}
	}
</style>
