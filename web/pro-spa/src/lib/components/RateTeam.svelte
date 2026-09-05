<script lang="ts">
	import { tick } from 'svelte';
	import {
		fetchRateTeam,
		fetchRateTeamManual,
		fetchModelSquad,
		type RatedPlayer,
		type RateTeamResponse,
		type TransferSuggestion
	} from '$lib/fantasyTools';
	import { draftPool, fetchXp, type XpPoolPlayer } from '$lib/api';
	import { buildRoast, roastTier, roastHeadline } from '$lib/roast';
	import { shareRoastCard, shareButtonLabel} from '$lib/shareCard';
	import { capture } from '$lib/analytics';
	import { auth } from '$lib/auth.svelte';
	import {
		fplEntry,
		forgetEntry,
		loadProfileEntry,
		resultKey,
		persistEntry,
		toggleRemember
	} from '$lib/fplEntry.svelte';
	import {
		loadDraftIds,
		saveDraftIds,
		syncDraft,
		pushRemoteDraftSoon,
		loadCaptaincy,
		saveCaptaincy,
		DRAFT_CLEARED_EVENT,
		type Captaincy
	} from '$lib/draft';
	import HoldVerdictCard from './HoldVerdictCard.svelte';
	import WeeklyActions, { type WeeklyAction } from './WeeklyActions.svelte';
	import { isOpenForLogging, loadDecisions, logDecision } from '$lib/fplDecisions';
	import BeatTheModel from './BeatTheModel.svelte';
	import GwReview from './GwReview.svelte';
	import SeasonRace from './SeasonRace.svelte';
	import { fetchFantasy } from '$lib/api';
	import ModelWorking from './ModelWorking.svelte';
	import PlayerSearch from './PlayerSearch.svelte';
	import TeamPitchManager from './TeamPitchManager.svelte';

	// #73: lataustilan askeleet = putken oikeat vaiheet (rehellinen checklist)
	const WORKING_STEPS = [
		'Fetching your FPL squad',
		'Loading model xP projections',
		'Picking your best XI and captain',
		'Checking every transfer against holding'
	];

	// FREE/PREMIUM-raja komponenttitasolla: siirtosuositukset renderöityvät
	// VAIN premium={true} (ProView, tilauksen takana). Free näyttää lukitun
	// teaser-rivin joka vie Paywalliin (onUpgrade → Pro-tab).
	let {
		premium = false,
		onUpgrade,
		weekMode = false,
		onGoToTeam
	}: {
		premium?: boolean;
		onUpgrade?: () => void;
		/** Web P1 (30.7): true = renderöi VAIN viikkosilmukan (WeeklyActions +
		 *  Beat the model + kapteeni). Parent pitää tämän elementin samassa
		 *  puupositiossa week↔team-vaihdossa → data/entry-tila säilyy. Sama
		 *  kaava kuin mobiilin RateTeamSection weekMode. */
		weekMode?: boolean;
		/** week-tyhjätilan CTA — vie My team -ryhmään. */
		onGoToTeam?: () => void;
	} = $props();

	// #66: entry-kenttä on jaettu (fplEntry.entry) RateTeamin + Plannerin kesken
	let loading = $state(false);
	let error = $state<string | null>(null);
	// Roast my team (7.8): toggle + kopiointikuittaus.
	let roastOpen = $state(false);
	let roastCopied = $state(false);
	let roastSharing = $state(false);
	let data = $state<RateTeamResponse | null>(null);

	// --- FM-silmukka: mallin suositukset kirjattaviksi päätöksiksi ----------
	// Deadline haetaan Phase 0 -metasta, EI rate-teamista: rate-team tuntee
	// vain GW-numeron, ja lukituksen raja on kellonaika. Ilman oikeaa
	// deadlinea kirjaus joko estyisi turhaan tai sallisi liikaa.
	// Fail-safe: ilman deadlinea suositukset näkyvät mutta napit eivät.
	let deadlineUtc = $state<string | null>(null);
	$effect(() => {
		fetchFantasy()
			.then((p) => {
				deadlineUtc = (p?.meta?.deadline_utc as string | undefined) ?? null;
			})
			.catch(() => {});
	});

	let weeklyActions = $derived.by<WeeklyAction[]>(() => {
		if (!data) return [];
		const out: WeeklyAction[] = [];
		const cap = data.captain?.pick;
		if (cap) {
			const alt = data.captain?.alternative;
			out.push({
				kind: 'captain',
				label: 'Captain',
				modelText: `${cap.web_name} (${cap.team_short}) · ${cap.gw_xp.toFixed(2)} xP`,
				modelChoice: { id: cap.id, name: cap.web_name, gw_xp: cap.gw_xp },
				// Lähellä oleva vaihtoehto on itsessään tieto: valinta ei ole
				// selvä, ja mallin pitää myöntää se.
				rationale: alt
					? `${alt.web_name} is only ${(cap.gw_xp - alt.gw_xp).toFixed(2)} xP behind, so this one is close.`
					: undefined
			});
		}
		// Siirto vain jos malli oikeasti suosittelee. "Älä siirrä" on yhtä
		// lailla päätös, mutta sitä ei kirjata tekemisenä — tyhjä nappi olisi
		// kohinaa. hold_verdict pysyy omassa kortissaan.
		const sug = data.transfers?.suggestions?.[0];
		if (sug && !data.transfers?.hold) {
			out.push({
				kind: 'transfer',
				label: 'Transfer',
				modelText: `${sug.out.web_name} → ${sug.in.web_name}`,
				modelChoice: {
					out_id: sug.out.id,
					in_id: sug.in.id,
					out: sug.out.web_name,
					in: sug.in.web_name
				},
				rationale: `+${sug.delta_xp_horizon.toFixed(2)} xP over the horizon, ${sug.delta_cost.toFixed(1)}m cost.`
			});
		}
		return out;
	});

	let entryValid = $derived(/^\d{1,10}$/.test(fplEntry.entry.trim()));

	/** 28.7 (PI-16): FPL ei ole vielä julkaissut kokoonpanoja. Erillään
	 *  `error`:sta, koska tämä ei ole virhe vaan ohjaus toimivaan polkuun. */
	let picksNotPublished = $state(false);

	// RATE-TEAM-PICKS-GW-LABEL (27.8): deadline paikallisena kellonaikana
	// selitysrivia varten. Rikkinainen aikaleima -> null, rivi nakyy silti
	// ilman kellonaikaa (vaara aika olisi huonompi kuin puuttuva).
	let pickDeadlineLocal = $derived.by<string | null>(() => {
		const iso = data?.meta?.deadline_time;
		if (typeof iso !== 'string') return null;
		const d = new Date(iso);
		if (Number.isNaN(d.getTime())) return null;
		// timeZoneName mukana (portin suositus 27.8): aika on lukijan
		// paikallinen eika FPL:n sivun UK-aika, ja ilman vyohyketta ero
		// nayttaisi virheelta.
		return d.toLocaleString(undefined, {
			weekday: 'short',
			day: 'numeric',
			month: 'short',
			hour: '2-digit',
			minute: '2-digit',
			timeZoneName: 'short'
		});
	});
	let draftBoxEl = $state<HTMLElement | null>(null);
	function openDraftFromNotice() {
		draftOpen = true;
		pickerCollapsed = false;
		// Draft-laatikko on tulosten YLAPUOLELLA, joten pelkka avaaminen ei
		// nay — rullataan siihen. tick-viive: elementti on olemassa vasta
		// renderin jalkeen.
		void tick().then(() => draftBoxEl?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
	}

	async function runRate() {
		if (!entryValid || loading) return;
		loading = true;
		error = null;
		try {
			const id = Number(fplEntry.entry.trim());
			data = await fetchRateTeam(id);
			picksNotPublished = false;
			setupOpenManual = false; // tulos nakyviin, lomake pois tielta
			// 4.9: tulos storeen, jotta paluu valilehdelta ei menetä sitä.
			fplEntry.lastResult = {
				key: resultKey(String(id), 'a'),
				slot: 'a',
				data
			};
			void persistEntry(id); // #66: talteen vasta onnistuneesta hausta
			// 2.8 aktivaatiomittari (mobiilipariteetti): lahtee vasta onnistuneesta
			// hausta. mode kattaa entryn JA draftin, koska entry-ID ei voi onnistua
			// esikaudella (picks_not_published) — pelkka entry nayttaisi nollaa 21.8. asti.
			capture('rate_team_succeeded', { mode: 'entry', slot: 'a' });
		} catch (err) {
			data = null;
			// 28.7 (PI-16): esikaudella entry-ID-polku EI VOI onnistua, koska FPL
			// julkaisee kokoonpanot vasta GW1-deadlinen jälkeen. Se ei ole
			// käyttäjän virhe eikä sitä pidä näyttää punaisena virheenä: se on
			// kalenterin tila, ja siihen on toimiva vaihtoehtoinen polku samaan
			// työhön (draft rater). Avataan se automaattisesti.
			const code = (err as { code?: string })?.code;
			if (code === 'picks_not_published') {
				picksNotPublished = true;
				error = null;
				draftOpen = true;
			} else {
				picksNotPublished = false;
				error = err instanceof Error ? err.message : String(err);
			}
		}
		loading = false;
	}

	function rate(e: SubmitEvent) {
		e.preventDefault();
		void runRate();
	}

	// #66: kirjautuneena lue tallennettu entry-ID profiilista (kerran per user)
	// -> esitäyttö + kertaluontoinen automaattinen rate-ajo (kuten mobiili-#64).
	$effect(() => {
		if (auth.sessionResolved && auth.user) void loadProfileEntry();
	});
	// 🔴 Villen havainto 4.9 (toistettu tuotannosta): "my team katkeaa kun
	// siirtyy valilehdelta toiselle". Reitin vaihto purkaa taman komponentin,
	// ja `data` on komponentin omaa tilaa -> arvio katosi ja lomake palasi,
	// vaikka entry-ID oli yha kentassa. Automaattiajo ei pelastanut, koska
	// `autoRunPending` kulutetaan kerran eika `loadProfileEntry` aseta sita
	// uudelleen (`loadedForUser`-vahti).
	// Palautus tapahtuu storesta ILMAN uutta hakua, ja vain jos avain tasmaa
	// nykyiseen entryyn — toisen joukkueen tulos ei voi nayttaa taalla.
	$effect(() => {
		if (data || loading) return;
		const cached = fplEntry.lastResult;
		if (!cached || cached.slot !== 'a') return;
		const want = resultKey(fplEntry.entry.trim() || 'draft', 'a');
		if (cached.key === want) data = cached.data;
	});
	$effect(() => {
		if (fplEntry.autoRunPending && entryValid && !data && !loading) {
			fplEntry.autoRunPending = false;
			void runRate();
		}
	});

	function unlock() {
		// Sama funnel-pari kuin Paywall/billing, source erottaa työkalupolun
		capture('upgrade_tapped', { source: 'fantasy_tools' });
		onUpgrade?.();
	}

	// P1 (23.7): esikausi-draft — FPL julkaisee picksit vasta GW-deadlinen
	// jälkeen, joten ennen GW1:tä entry-polku on tyhjän päällä. Draft: valitse
	// 15 (2 GKP / 5 DEF / 5 MID / 3 FWD) → sama arvio kuin importoidulla
	// joukkueella. Kapteenin valitsee malli (paras GW-xP).
	const DRAFT_CAPS: Record<string, number> = { GKP: 2, DEF: 5, MID: 5, FWD: 3 };
	const DRAFT_ORDER = ['GKP', 'DEF', 'MID', 'FWD'];
	let draftOpen = $state(false);
	/**
	 * 🔴 Villen tilaus 4.9: "my team nakyma pitaa saada selkeammaksi ja
	 * reilusti". Mitattu ennen: tuomio (Team xP, kapteeni, siirrot) alkoi
	 * ~900 px:n paasta, koska sita ennen olivat tuontilomake, ohjeteksti,
	 * draft-polku, muistamisvalinta ja niiden selitykset — kaikki asioita
	 * joita tarvitaan KERRAN. Kun joukkue on jo ladattu, ne menevat "Change
	 * team" -napin taakse ja sivu alkaa vastauksesta.
	 */
	let setupOpenManual = $state(false);
	const setupOpen = $derived(!data || setupOpenManual);
	let pool = $state<XpPoolPlayer[]>([]);
	let poolError = $state(false);
	let picks = $state<XpPoolPlayer[]>([]);
	let draftQuery = $state('');

	// Web-pariteetti mobiilin cc-inbox #2 -fixille: draft-pickit persistoituvat
	// localStorageen (vain ID:t; oliot resolvoidaan tuoreesta xP-poolista →
	// hinnat eivät jäädy, poistuneet putoavat pois). Fail-safe: storage-virhe
	// ei saa kaataa työkalua. Tallennus vasta hydraation jälkeen, ettei tyhjä
	// alkutila ylikirjoita tallennettua draftia. UX-palaute-erä (25.7):
	// avain + luku/kirjoitus jaettu lib/draft.ts:ään — myös Fit checkerin
	// "Save as draft" kirjoittaa samaan storageen.
	let savedDraftIds: number[] | null = loadDraftIds();
	let draftCanSave = savedDraftIds == null;
	// 23.8 (Villen pyynto): tallennettu draft EI ENAA avaa valitsinta itsestaan.
	// Ennen tata jokainen sivulataus avasi draft-raterin heti kun localStoragessa
	// tai tililla oli pikkeja, ja se peitti sen mita kayttaja ensisijaisesti
	// hakee: OMAN joukkueensa FPL-ID:lla. Villen sanat: "haluan etta naen
	// ensisijaisesti vain joukkueen mika tulee fpl id:lla ja ton sais halutessaa
	// auki."
	//
	// Draft ei katoa mihinkaan - se on yha tallessa ja nappi kertoo montako
	// pelaajaa siina on. Sivuvaikutuksena pool-fetch (~satoja rivejä) lahtee
	// vasta kun valitsin oikeasti avataan, eika joka sivulatauksella.
	//
	// SAILYY: picks_not_published-haara (rivi ~162) avaa draftin yha, koska
	// silloin entry-polku EI VOI onnistua eika vaihtoehtoa ole.
	let savedDraftCount = $state(savedDraftIds?.length ?? 0);
	// Web-perf-audit 31.7 kohta 2: persist-efekti laukesi myös pelkästä
	// hydraatiosta → joka sivulataus uudelleenleimasi lokaalin aikaleiman JA
	// työnsi muuttumattoman draftin tilille (set_fpl_draft joka bootissa).
	// Vahti: tallenna/pushaa vain kun ID-lista oikeasti muuttuu viimeksi
	// persistoidusta. syncDraftin jälkeen tili ≈ lokaali, joten alkuarvo on
	// lokaali lista (ja tilin voittaessa .then päivittää sen tilin listaksi).
	let lastPersistedSig = (savedDraftIds ?? []).join(',');

	// 26.7 (Villen pyyntö): sama joukkue webissä ja apissa. Kirjautuneelle
	// tilin draft on totuus, kirjautumattomalle localStorage kuten ennen.
	// Synkka ajetaan kerran mountissa; jos tili oli edellä, hydraatio ottaa
	// palautetut ID:t (savedDraftIds asetetaan uudelleen ja draftCanSave
	// palautetaan false:ksi, jotta alla oleva persistointi-effect ei kirjoita
	// tyhjää päälle ennen kuin pooli on resolvoinut ne).
	let draftSynced = $state(false);
	void syncDraft().then((remoteIds) => {
		draftSynced = true;
		if (!remoteIds || remoteIds.length === 0) return;
		if (picks.length > 0) return; // käyttäjä ehti valita → ei ylikirjoiteta
		savedDraftIds = remoteIds;
		lastPersistedSig = remoteIds.join(','); // tili voitti → tämä on persistoitu tila
		draftCanSave = false;
		savedDraftCount = remoteIds.length;
	});
	// UX-palaute-erä kohta 4: täysi tallennettu draft → tulosnäkymä palautuu
	// automaattisesti ilman uutta "Rate my draft" -painallusta, ja valitsin
	// menee collapse-tilaan kun tulos näkyy (auki muokkausta varten).
	let autoDraftPending = $state(false);
	let pickerCollapsed = $state(false);

	$effect(() => {
		// 1.8: myös Joukkue 2:n draft-valitsin tarvitsee poolin (jaettu haku).
		if ((draftOpen || draftOpenB) && pool.length === 0 && !poolError) {
			// 14.8: draftPool = taydet rivit + kevyet rivit lopuille. Pelkka
			// `players` oli free-kayttajalla 10 rivia joissa 0 maalivahtia,
			// jolloin 15/15 ei ollut taytettavissa eika lahetysnappi
			// aktivoitunut koskaan.
			fetchXp().then(
				(d) => (pool = draftPool(d)),
				() => (poolError = true)
			);
		}
	});
	// Hydraatio: kun pooli on saatavilla, resolvoi tallennetut ID:t — ei
	// ylikirjoiteta käyttäjän jo tekemiä tuoreita valintoja.
	$effect(() => {
		if (!draftCanSave && savedDraftIds && pool.length > 0) {
			const byId = new Map(pool.map((p) => [p.id, p]));
			const resolved = savedDraftIds
				.map((id) => byId.get(id))
				.filter((p): p is XpPoolPlayer => p != null);
			if (picks.length === 0 && resolved.length > 0) {
				picks = resolved;
				// Kohta 4: 15/15 tallessa → aja arvio automaattisesti.
				if (resolved.length === 15) autoDraftPending = true;
			}
			savedDraftIds = null;
			draftCanSave = true;
		}
	});
	// Kohta 4: kertaluontoinen auto-ajo hydraation jälkeen (ei silmukkaa:
	// lippu nollataan ennen hakua; !data estää tuplat entry-auto-ajon kanssa).
	$effect(() => {
		if (autoDraftPending && draftReady && !data && !loading) {
			autoDraftPending = false;
			void submitDraft(true);
		}
	});
	// Persistoi jokainen muutos hydraation jälkeen. 26.7: sama kirjoitus menee
	// myös tilille (debounced — pick-muutoksia tulee useita peräkkäin).
	//
	// TYHJÄÄ LISTAA EI TYÖNNETÄ ennen kuin tällä sivulatauksella on ollut
	// pelaajia. Ilman tätä pelkkä työkalun avaaminen webissä (picks = []) olisi
	// työntänyt tyhjän listan tilille ja PYYHKINYT puhelimella tehdyn draftin.
	// Havaittu live-testissä heti ensimmäisellä deployllä.
	let draftEverHadPicks = $state(false);
	$effect(() => {
		const ids = picks.map((p) => p.id);
		if (!draftCanSave) return;
		if (ids.length > 0) draftEverHadPicks = true;
		// Muuttumaton lista (hydraatio/boot) EI kirjoita: localStorage-leima ei
		// liiku eikä tilille lähde turhaa set_fpl_draftia (perf-audit kohta 2).
		// Poolista pudonneet pelaajat tuottavat eri sig:n → pruning-kirjoitus
		// tapahtuu yhä kerran ja konvergoi.
		const sig = ids.join(',');
		if (sig === lastPersistedSig) return;
		lastPersistedSig = sig;
		saveDraftIds(ids);
		if (draftSynced && (ids.length > 0 || draftEverHadPicks)) {
			pushRemoteDraftSoon(ids);
		}
	});
	const posCount = $derived.by(() => {
		const c: Record<string, number> = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
		for (const p of picks) c[p.pos] = (c[p.pos] ?? 0) + 1;
		return c;
	});
	const draftReady = $derived(picks.length === 15 && !loading);
	// Sama normalisointi kuin FitChecker/XpTable-haussa (#145/#147-pariteetti).
	function normDraft(s: string): string {
		return s
			.normalize('NFD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase()
			.replace(/ø/g, 'o')
			.replace(/['’ʼ]/g, '')
			.replace(/[-.]/g, ' ')
			.trim();
	}
	const draftMatches = $derived.by(() => {
		const q = normDraft(draftQuery);
		if (q.length < 2) return [];
		const pickedIds = new Set(picks.map((p) => p.id));
		return pool
			.filter(
				(p) =>
					!pickedIds.has(p.id) &&
					(posCount[p.pos] ?? 0) < (DRAFT_CAPS[p.pos] ?? 0) &&
					(normDraft(p.web_name).includes(q) ||
						(p.full_name ? normDraft(p.full_name).includes(q) : false) ||
						normDraft(p.team_short).includes(q))
			)
			.slice(0, 6);
	});
	function addPick(p: XpPoolPlayer) {
		if (picks.length >= 15 || (posCount[p.pos] ?? 0) >= (DRAFT_CAPS[p.pos] ?? 0)) return;
		picks = [...picks, p];
		draftQuery = '';
	}
	function removePick(id: number) {
		picks = picks.filter((p) => p.id !== id);
	}
	/**
	 * Tyhjenna koko draft kerralla.
	 *
	 * `picks = []` riittaa: persistointi-efekti kirjoittaa uuden allekirjoituksen
	 * localStorageen ja tyontaa tyhjan listan myos tilille, koska
	 * `draftEverHadPicks` on talla sivulatauksella jo tosi. Tulos nollataan
	 * kasin, muuten nakyma jaisi nayttamaan edellisen arvion joukkueelle jota ei
	 * enaa ole.
	 */
	function clearAllPicks() {
		picks = [];
		data = null;
		error = null;
	}
	/**
	 * 🔴 Rekisteroityminen tyhjentaa draftin (uusi tili aloittaa tyhjana), ja
	 * sen on nakyttava TASSA nakymassa saman tien. Ilman tata storage on tyhja
	 * mutta ruudulla on yha edellinen joukkue, ja persistointi-efekti kirjoittaa
	 * sen takaisin ensimmaisesta muutoksesta. Mitattu: Ville loi uuden tilin
	 * pelkan storage-tyhjennyksen jalkeen ja sai yha saman kokoonpanon.
	 */
	$effect(() => {
		const onCleared = () => {
			picks = [];
			savedDraftIds = null;
			// `captaincy` on const-olio (mutatoidaan paikallaan muuallakin).
			captaincy.captain_id = null;
			captaincy.vice_id = null;
			data = null;
			error = null;
			autoDraftPending = false;
		};
		window.addEventListener(DRAFT_CLEARED_EVENT, onCleared);
		return () => window.removeEventListener(DRAFT_CLEARED_EVENT, onCleared);
	});
	async function submitDraft(auto = false) {
		if (!draftReady) return;
		loading = true;
		error = null;
		capture('rate_team_draft_submitted', { picked_n: picks.length, auto });
		try {
			data = await fetchRateTeamManual(picks.map((p) => p.id));
			// Kohta 4: tulos näkyy → valitsin collapse-tilaan (Edit draft avaa).
			pickerCollapsed = true;
			setupOpenManual = false;
			fplEntry.lastResult = {
				key: resultKey('draft', 'a'),
				slot: 'a',
				data
			};
			capture('rate_team_succeeded', { mode: 'draft', slot: 'a', auto });
		} catch (err) {
			data = null;
			error = err instanceof Error ? err.message : String(err);
		}
		loading = false;
	}

	// #121: apply-to-planner — siirtoehdotukset sovelletaan planned-tiimiin
	// (pitch + xP + budjetti heti). EI write-backia oikeaan FPL:ään: FPL:llä ei
	// ole julkista kirjoitus-APIa, joten siirto on aina tehtävä lopuksi itse
	// heidän sivuillaan. 26.7 (Villen havainto "apply toimii mutta ei tallenna
	// sitä"): sovellettu suunnitelma kirjoitetaan nyt draftiin — se säilyy
	// sivun latauksen yli ja kulkee tilin kautta myös puhelimeen.
	let appliedTransfers = $state<TransferSuggestion[]>([]);
	let planSaved = $state(false);
	$effect(() => {
		void data; // riippuvuus: uusi rate-ajo → suunnitelma nollaan
		appliedTransfers = [];
	});
	const plannedPlayers = $derived.by(() => {
		let roster: RatedPlayer[] = data?.team.players ?? [];
		for (const s of appliedTransfers) {
			roster = roster.map((p) =>
				p.id === s.out.id
					? {
							id: s.in.id,
							web_name: s.in.web_name,
							team_short: s.in.team_short,
							pos: p.pos,
							price: s.in.price,
							xp_per_gw: s.in.xp_per_gw ?? 0,
							xp_horizon_total: s.in.xp_horizon_total ?? 0,
							gameweeks: s.in.gameweeks,
							in_xi: p.in_xi,
							is_captain: p.is_captain,
							// 🔴 Lippu SEURAA sisaan tulevaa pelaajaa. Ilman tata
							// rivi rakennetaan kasin ilman `chance_next`ia ja
							// pitch nayttaa liputetun pelaajan puhtaana juuri
							// silla hetkella kun kayttaja valitsee hanet.
							chance_next: s.in.chance_next ?? null,
							news: s.in.news ?? null
						}
					: p
			);
		}
		return roster;
	});
	const plannedIds = $derived(new Set(plannedPlayers.map((p) => p.id)));
	// #35: budjetti on JAETTU siirtojen yli — juokseva bank, ei naiivia summaa.
	const planBank = $derived(
		(data?.team.bank ?? 0) - appliedTransfers.reduce((s, x) => s + x.delta_cost, 0)
	);
	// Sovellettujen siirtojen netto-horisontti-xP on eksakti (jokainen delta on
	// oman out-pelaajansa korvaus, ei saman listan kilpailevia vaihtoehtoja).
	const planNetXp = $derived(
		appliedTransfers.reduce((s, x) => s + x.delta_xp_horizon, 0)
	);
	const appliedKeys = $derived(
		new Set(appliedTransfers.map((s) => `${s.out.id}-${s.in.id}`))
	);
	/** Rosteri annetun siirtoketjun jälkeen — laskettuna suoraan, ei $derivedin
	 *  kautta, jotta tallennus näkee uuden tilan samalla klikillä. */
	function planIdsAfter(list: TransferSuggestion[]): number[] {
		let ids = (data?.team.players ?? []).map((p) => p.id);
		for (const s of list) ids = ids.map((id) => (id === s.out.id ? s.in.id : id));
		return ids;
	}
	/** Apply / Undo / Reset — kaikki kolme kirjoittavat draftiin, jotta
	 *  tallennettu joukkue on aina se mikä ruudulla näkyy. */
	// 29.7: kapteeni/vice kulkee draftin mukana (skeema 20260729233000).
	// EI $state: arvo luetaan mountissa ja päivitetään callbackissa — reaktiivinen
	// prop ajaisi managerin reset-effectin uudelleen (svelte-efektikehäopetus).
	const captaincy: Captaincy = loadCaptaincy();
	// Silmukka-bugi #8 (30.7): WeeklyActions lataa kirjaukset uudelleen kun
	// tämä bumppaa — managerin kapteeninvaihto päivittää kirjattua päätöstä
	// kortin ohi, ja kortin on näytettävä tuore tila.
	let decisionsVersion = $state(0);
	/** Silmukka-bugi #8: managerin kapteeninvaihto virtaa kirjattuun
	 *  captain-päätökseen. EI luo kirjausta — vain jo kirjattu päätös
	 *  päivittyy (kanta upserttaa deadlineen asti), ja followed lasketaan
	 *  uudelleen. Ilman tätä grader vertaisi vanhentunutta kirjausta.
	 *  SAMA logiikka kuin mobiilin FantasyTools.syncCaptainDecision. */
	async function syncCaptainDecision(captainId: number) {
		const gw = data?.meta?.gw;
		if (gw == null || !deadlineUtc || !isOpenForLogging(deadlineUtc)) return;
		const rows = await loadDecisions(gw);
		const rec = rows.find((r) => r.kind === 'captain');
		if (!rec) return;
		const modelId = (rec.model_choice as { id?: unknown }).id;
		const name =
			data?.team.players.find((p) => p.id === captainId)?.web_name ??
			pool.find((p) => p.id === captainId)?.web_name;
		// Mallin kapteeni takaisin → userChoice = täsmälleen model_choice,
		// jolloin followed-vertailu (JSON-yhtäsuuruus) palaa todeksi.
		const userChoice =
			captainId === modelId
				? rec.model_choice
				: { id: captainId, name: name ?? String(captainId) };
		if (JSON.stringify(userChoice) === JSON.stringify(rec.user_choice)) return;
		const res = await logDecision({
			gw,
			kind: 'captain',
			modelChoice: rec.model_choice,
			userChoice,
			deadlineUtc
		});
		if (res.ok) {
			capture('fpl_decision_updated', {
				kind: 'captain',
				gw,
				followed: captainId === modelId,
				source: 'pitch'
			});
			decisionsVersion += 1;
		}
	}
	function handleCaptaincyChange(captainId: number | null, viceId: number | null) {
		const prevCaptainId = captaincy.captain_id;
		captaincy.captain_id = captainId;
		captaincy.vice_id = viceId;
		saveCaptaincy(captaincy);
		const ids = planIdsAfter(appliedTransfers);
		if (ids.length > 0) pushRemoteDraftSoon(ids, captaincy);
		if (captainId != null && captainId !== prevCaptainId) void syncCaptainDecision(captainId);
	}

	function setPlan(list: TransferSuggestion[]): void {
		appliedTransfers = list;
		const ids = planIdsAfter(list);
		if (ids.length === 0) return;
		saveDraftIds(ids);
		pushRemoteDraftSoon(ids, captaincy);
		planSaved = true;
		// Draft-valitsin seuraa perässä, jotta "Edit draft" näyttää saman
		// joukkueen. Jos pooli ei ole vielä ladattu, storage riittää —
		// hydraatio resolvoi ID:t seuraavalla kerralla.
		if (pool.length > 0) {
			const byId = new Map(pool.map((p) => [p.id, p]));
			const resolved = ids
				.map((id) => byId.get(id))
				.filter((p): p is XpPoolPlayer => p != null);
			if (resolved.length === ids.length) picks = resolved;
		}
	}
	function canApply(s: TransferSuggestion): boolean {
		return (
			s.in.xp_per_gw != null && // vanha backend ilman planner-kenttiä → ei applya
			plannedIds.has(s.out.id) &&
			!plannedIds.has(s.in.id) &&
			planBank - s.delta_cost >= -1e-9
		);
	}

	/** FM-silmukan "I'll do this" siirrolle (29.7) — sama setPlan-polku ja
	 *  samat portit kuin Apply-napilla. Ei koskaan kahta soveltamislogiikkaa. */
	function followTransferFromLoop(choice: Record<string, unknown>): boolean {
		const sug = data?.transfers?.suggestions?.find(
			(s) => s.out.id === choice.out_id && s.in.id === choice.in_id
		);
		if (!sug) return false;
		if (appliedKeys.has(`${sug.out.id}-${sug.in.id}`)) return false;
		if (!canApply(sug)) return false;
		setPlan([...appliedTransfers, sug]);
		return true;
	}

	$effect(() => {
		// Paywall-pariteetti: teaser näkyvissä = paywall_shown (kerran per lataus)
		if (!premium && data) {
			capture('paywall_shown', { source: 'fantasy_tools' }, 'paywall_shown_fantasy_tools');
		}
	});

	// --- 1.8: Joukkue 2 (vertailuslotti) -----------------------------------
	// Kevyt rinnakkaisslotti samoilla arviointiominaisuuksilla: oma entry/
	// draft/tulos. TARKOITUKSELLA EI: tallennusta laitteelle/tilille, FM-
	// kirjausta, siirtosuunnitelmaa — ne sitoutuvat käyttäjän omaan joukkueeseen
	// (Team 1). Istuntokohtainen; UI sanoo sen ääneen. Sama toteutus mobiilissa
	// (FantasyTools.tsx, sama päivä).
	let slot = $state<'a' | 'b'>('a');
	let entryBText = $state('');
	const entryBValid = $derived(/^\d{1,10}$/.test(entryBText.trim()));
	let loadingB = $state(false);
	let errorB = $state<string | null>(null);
	let dataB = $state<RateTeamResponse | null>(null);
	let picksNotPublishedB = $state(false);
	let draftOpenB = $state(false);
	let picksB = $state<XpPoolPlayer[]>([]);
	let draftQueryB = $state('');
	const posCountB = $derived.by(() => {
		const c: Record<string, number> = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
		for (const p of picksB) c[p.pos] = (c[p.pos] ?? 0) + 1;
		return c;
	});
	const draftReadyB = $derived(picksB.length === 15 && !loadingB);
	const draftMatchesB = $derived.by(() => {
		const q = normDraft(draftQueryB);
		if (q.length < 2) return [];
		const pickedIds = new Set(picksB.map((p) => p.id));
		return pool
			.filter(
				(p) =>
					!pickedIds.has(p.id) &&
					(posCountB[p.pos] ?? 0) < (DRAFT_CAPS[p.pos] ?? 0) &&
					(normDraft(p.web_name).includes(q) ||
						(p.full_name ? normDraft(p.full_name).includes(q) : false) ||
						normDraft(p.team_short).includes(q))
			)
			.slice(0, 6);
	});
	// EI $state — sama syy kuin captaincy yllä: reaktiivinen prop ajaisi
	// pitch-managerin reset-effectin uudelleen (svelte-efektikehäopetus).
	// Vain paikallinen: vertailujoukkueen kapteenia ei tallenneta mihinkään.
	const captaincyB: Captaincy = { captain_id: null, vice_id: null };
	function handleCaptaincyChangeB(captainId: number | null, viceId: number | null) {
		captaincyB.captain_id = captainId;
		captaincyB.vice_id = viceId;
	}
	function addPickB(p: XpPoolPlayer) {
		if (picksB.length >= 15 || (posCountB[p.pos] ?? 0) >= (DRAFT_CAPS[p.pos] ?? 0)) return;
		picksB = [...picksB, p];
		draftQueryB = '';
	}
	function removePickB(id: number) {
		picksB = picksB.filter((p) => p.id !== id);
	}
	async function runRateB() {
		if (!entryBValid || loadingB) return;
		loadingB = true;
		errorB = null;
		try {
			dataB = await fetchRateTeam(Number(entryBText.trim()));
			picksNotPublishedB = false;
			capture('rate_team_succeeded', { mode: 'entry', slot: 'b' });
		} catch (err) {
			dataB = null;
			const code = (err as { code?: string })?.code;
			if (code === 'picks_not_published') {
				picksNotPublishedB = true;
				errorB = null;
				draftOpenB = true;
			} else {
				picksNotPublishedB = false;
				errorB = err instanceof Error ? err.message : String(err);
			}
		}
		loadingB = false;
	}
	function rateB(e: SubmitEvent) {
		e.preventDefault();
		void runRateB();
	}
	async function submitDraftB() {
		if (!draftReadyB) return;
		loadingB = true;
		errorB = null;
		capture('rate_team_draft_submitted', { picked_n: picksB.length, slot: 'b' });
		try {
			dataB = await fetchRateTeamManual(picksB.map((p) => p.id));
			capture('rate_team_succeeded', { mode: 'draft', slot: 'b' });
		} catch (err) {
			dataB = null;
			errorB = err instanceof Error ? err.message : String(err);
		}
		loadingB = false;
	}
	/** 1.8: "beat the model" konkreettiseksi — täyttää Joukkue 2:n mallin
	 *  vapaalla optimirungolla (sama free_optimum kuin benchmark) ja arvioi
	 *  sen heti. Pickit jäävät muokattaviksi. Pooli haetaan tarvittaessa
	 *  suoraan (ei odoteta draft-effectiä — käyttäjä voi painaa nappia ennen
	 *  kuin valitsin on auennut kertaakaan). */
	async function loadModelSquadB() {
		if (loadingB) return;
		loadingB = true;
		errorB = null;
		capture('fpl_model_squad_loaded', { slot: 'b' });
		try {
			const ms = await fetchModelSquad();
			if (pool.length === 0) {
				const d = await fetchXp();
				pool = draftPool(d);
			}
			const byId = new Map(pool.map((p) => [p.id, p]));
			const resolved = ms.players
				.map((p) => byId.get(p.id))
				.filter((p): p is XpPoolPlayer => p != null);
			if (resolved.length !== 15) {
				throw new Error('The model squad is not available right now. Please try again shortly.');
			}
			picksB = resolved;
			draftOpenB = true;
			dataB = await fetchRateTeamManual(resolved.map((p) => p.id));
		} catch (err) {
			dataB = null;
			errorB = err instanceof Error ? err.message : String(err);
		}
		loadingB = false;
	}
	const compareDiff = $derived(
		data && dataB ? data.rating.team_xp_horizon - dataB.rating.team_xp_horizon : null
	);
</script>

{#if weekMode}
	<!-- Web P1 "This week": suppea render — viikkosilmukka ilman rate-
	     koneistoa. Sama komponentti-instanssi kuin My teamissa (parent pitää
	     puuposition), joten data ja entry-tila ovat jaettuja. -->
	<h2>This week</h2>
	<p class="muted">
		What to do before the deadline, and how your calls are going against the model.
	</p>
	{#if loading}
		<p class="muted">Loading your squad…</p>
	{:else if data == null}
		<!-- Tyhjätila: viikkosilmukka tarvitsee joukkueen — ohjaa My teamiin,
		     ei duplikoitua syöttölomaketta. -->
		<!-- 4 Sep: this used to say "Set up your team first" whenever `data` was
		     null, including for a user who HAS a saved entry and is simply
		     waiting on it. Measured on the live page: "Your saved FPL team is
		     116920" and "Set up your team first" were both on screen at once,
		     so the product read as if it did not recognise a paying user.
		     Two different empty states, two different sentences. -->
		<div class="week-setup">
			{#if fplEntry.savedEntry != null}
				<p><strong>Team {fplEntry.savedEntry} is saved, but its data has not loaded.</strong></p>
				<p class="muted">
					Nothing is wrong with your squad. Open My team to reload it, and this view
					fills in with your captain call and the decisions to log.
				</p>
				<button class="primary" type="button" onclick={() => onGoToTeam?.()}>Reload in My team</button>
			{:else}
				<p><strong>Set up your team first.</strong></p>
				<p class="muted">
					The weekly loop needs your squad. Add your FPL entry ID or build a draft in My team,
					and this view fills in with your captain call and the decisions to log.
				</p>
				<button class="primary" type="button" onclick={() => onGoToTeam?.()}>Go to My team</button>
			{/if}
		</div>
	{:else}
		<!-- 14.8 LAYOUT (Villen palaute: "ne ovat tossa allekain ns listana"):
		     kaksi saraketta leveilla ruuduilla, TEKEMINEN vasemmalle ja TILA
		     oikealle. Kolme taysleveaa lohkoa allekkain nayttivat
		     samanpainoisilta eika mikaan kertonut mista aloittaa, ja ~65 %
		     vaakatilasta oli tyhjaa. Jako ei ole esteettinen vaan
		     merkityksellinen: vasen sarake on se mihin kayttaja koskee ennen
		     deadlinea, oikea kertoo miten menee. Kapea ruutu palaa yhteen
		     sarakkeeseen samassa jarjestyksessa kuin ennen. -->
		<div class="week-grid">
			<div class="week-col">
				<WeeklyActions
					gw={data.meta.gw}
					{deadlineUtc}
					actions={weeklyActions}
					onFollowTransfer={followTransferFromLoop}
					refreshToken={decisionsVersion}
				/>
				<p class="captain">
					Captain suggestion: <strong>{data.captain.pick.web_name}</strong>
					<span class="muted">({data.captain.pick.team_short})</span>,
					{data.captain.pick.gw_xp.toFixed(2)} xP in GW{data.meta.gw}{#if data.captain.alternative}.
						Alternative: {data.captain.alternative.web_name}
						<span class="muted">({data.captain.alternative.team_short})</span>,
						{data.captain.alternative.gw_xp.toFixed(2)} xP{/if}.
				</p>
				<!-- 🔴 Villen havainto 4.9: vasen sarake loppui kapteenilauseeseen
				     ja jatti ison tyhjan alueen, kun oikeassa sarakkeessa oli
				     kolme lohkoa. Gameweek review siirtyi tanne: se on
				     KIERROKSEN katsaus (mita tapahtui), eli lahempana vasemman
				     sarakkeen "mita teet ja mita siita seurasi" -luentaa kuin
				     oikean sarakkeen kausikirjanpitoa. -->
				<GwReview />
			</div>
			<div class="week-col">
				<BeatTheModel />
				<SeasonRace />
			</div>
		</div>
	{/if}
{:else}
<h2>Rate my FPL team</h2>
{#if setupOpen}
	<p class="muted">
		Import your squad with your public FPL entry ID, no login or password needed.
	</p>
{:else}
	<p class="muted team-line">
		{#if fplEntry.savedEntry}Team {fplEntry.savedEntry}{:else}Your squad{/if}, rated below.
		<button type="button" class="linklike" onclick={() => (setupOpenManual = true)}>
			Change team
		</button>
	</p>
{/if}

<!-- 1.8: vertailurivi — näkyy heti kun molemmilla joukkueilla on tulos,
     valitusta slotista riippumatta (se on koko featuren pointti). -->
{#if data && dataB}
	<div class="compare-box">
		<p class="compare-title">Team 1 vs Team 2</p>
		<p class="compare-line">
			Team 1 <strong>{Math.round(data.rating.team_xp_horizon)} xP</strong> · Team 2
			<strong>{Math.round(dataB.rating.team_xp_horizon)} xP</strong>
		</p>
		<p class="muted compare-verdict">
			{#if Math.abs(compareDiff ?? 0) < 0.5}
				Dead level over the {data.meta.horizon_gw ?? 6}-GW horizon.
			{:else if (compareDiff ?? 0) > 0}
				Team 1 ahead by {Math.abs(compareDiff ?? 0).toFixed(1)} xP over the
				{data.meta.horizon_gw ?? 6}-GW horizon.
			{:else}
				Team 2 ahead by {Math.abs(compareDiff ?? 0).toFixed(1)} xP over the
				{data.meta.horizon_gw ?? 6}-GW horizon.
			{/if}
		</p>
	</div>
{/if}

<!-- 1.8: joukkuevalitsin (Villen speksi: valinta nappien alle, ei sekavuutta —
     sisältö vaihtuu chipeistä, oletusnäkymä ennallaan). -->
{#if setupOpen}
<div class="slot-chips">
	<button type="button" class="slot-chip" class:active={slot === 'a'} onclick={() => (slot = 'a')}>
		Team 1
	</button>
	<button
		type="button"
		class="slot-chip"
		class:active={slot === 'b'}
		onclick={() => {
			if (slot !== 'b') capture('fpl_rate_compare_opened');
			slot = 'b';
		}}
	>
		Team 2
	</button>
</div>
{/if}

{#if slot === 'a'}
<!-- 14.8 LAYOUT + TUOTEKORJAUS (Villen palaute kortin sisaisesta tyhjasta
     tilasta). Kaksi ALOITUSPOLKUA vierekkain sen sijaan etta toinen on
     linkkina alempana. Peruste ei ole esteettinen: **ennen GW1-deadlinea
     entry-ID-polku ei voi toimia lainkaan** (FPL julkaisee kokoonpanot vasta
     deadlinen jalkeen -> 404), joten esikaudella draft-polku on se joka
     TOIMII. Sen hautaaminen linkiksi lomakkeen alle piilotti ainoan
     toimivan reitin juuri vuoden korkeimman ostoaikeen ikkunassa.
     Sivutuote: lomake kaytti ~kolmanneksen kortin leveydesta. -->
{#if setupOpen}
<div class="start-grid">
	<div class="start-col">
		<p class="start-title">I have an FPL team</p>
		<form class="entry-form" onsubmit={rate}>
			<div>
				<label for="rate-entry">FPL entry ID</label>
				<input
					id="rate-entry"
					inputmode="numeric"
					autocomplete="off"
					placeholder="e.g. 1234567"
					bind:value={fplEntry.entry}
				/>
			</div>
			<button class="primary" type="submit" disabled={!entryValid || loading}>
				{loading ? 'Rating…' : 'Rate my team'}
			</button>
		</form>
		<p class="muted hint">
			Find the ID on the FPL website: open your Points page and copy the number from the
			address bar (fantasy.premierleague.com/entry/<strong>YOUR-ID</strong>/event/...).
		</p>
	</div>
	<div class="start-col start-alt">
		<p class="start-title">No FPL team yet?</p>
		<!-- 22.8 (GW1-STALE-COPY): esikausiperustelu "before Gameweek 1 nobody
		     can import one" vanheni GW1-deadlineen. Paneeli jaa: se palvelee
		     ilman FPL-tiimia pelaavia ja mita jos -runkoja. -->
		<p class="muted hint">
			Pick your 15 here and the model rates them exactly the same way, no entry ID needed.
		</p>
		<button
			type="button"
			class="linklike draft-toggle"
			onclick={() => (draftOpen = !draftOpen)}
		>
			{draftOpen
				? 'Hide the draft rater'
				: savedDraftCount > 0
					? `Open your saved draft (${savedDraftCount}/15)`
					: 'Rate a draft instead'}
		</button>
	</div>
</div>
{/if}

{#if picksNotPublished}
	<!-- 28.7 (PI-16): tämä on koko esikauden normaalitila, ei virhe. Vanha
	     toteutus näytti punaisen 404:n ja jätti käyttäjän umpikujaan juuri
	     vuoden korkeimman ostoaikeen ikkunassa. -->
	<p class="notice-preseason">
		<strong>Your squad is not public yet.</strong> FPL keeps a team private until the first
		deadline it plays, so it cannot be imported before then. Rate the draft you are
		planning instead: pick your 15 below and the model rates it exactly the same way, with the
		same best XI, captain pick and projected points.
	</p>
{/if}

<!-- P1: esikausi-draft ilman entry-ID:tä (backendin players=-moodi).
     28.7: teksti korjattu. "No team ID yet?" oli väärä kysymys esikaudella,
     jolloin 1,66 M managerilla ON team ID mutta ei julkaistua kokoonpanoa.
     14.8: avausnappi siirtyi ylos `.start-grid`in oikeaan sarakkeeseen —
     valitsin itse jaa tanne, koska se tarvitsee koko leveyden. -->
{#if draftOpen}
	<div class="draft-box" bind:this={draftBoxEl}>
		{#if poolError}
			<p class="banner error">
				Could not load the player pool right now. Please try again shortly.
			</p>
		{:else if pickerCollapsed && data}
			<!-- Kohta 4: tulos näkyy → kompakti rivi, Edit draft avaa valitsimen -->
			<div class="draft-collapsed">
				<span class="muted">Draft squad: {picks.length} / 15 picked, rated below.</span>
				<button type="button" class="linklike" onclick={() => (pickerCollapsed = false)}>
					Edit draft
				</button>
			</div>
		{:else}
			<p class="muted hint">
				Pick a full 15-man squad (2 GK, 5 DEF, 5 MID, 3 FWD) and the model rates it like an
				imported team: best XI, captain pick and projected points.
			</p>
			<div class="draft-chips">
				{#each DRAFT_ORDER as pos (pos)}
					{#each picks.filter((p) => p.pos === pos) as p (p.id)}
						<button type="button" class="draft-chip" onclick={() => removePick(p.id)}>
							{p.web_name}
							<span class="muted">{p.team_short} · {p.pos}</span>
							<span aria-hidden="true">×</span>
						</button>
					{/each}
				{/each}
			</div>
			<p class="muted hint">
				{picks.length} / 15 picked · GK {posCount.GKP}/2 · DEF {posCount.DEF}/5 · MID
				{posCount.MID}/5 · FWD {posCount.FWD}/3
				{#if picks.length > 0}
					<!-- 🔴 Villen havainto 16.8. Ennen tata ainoa tapa paasta eroon
					     draftista oli poistaa 15 pelaajaa yksitellen. Se on kohtuuton
					     kenelle tahansa, ja erityisen kohtuuton niille joiden tilille
					     oli adoptoitu joukkue jota he eivat olleet valinneet. -->
					· <button type="button" class="clear-draft" onclick={clearAllPicks}>
						Clear squad
					</button>
				{/if}
			</p>
			{#if picks.length < 15}
				<!-- UX-palaute-erä kohdat 2+6: jaettu combobox — hinta + owned%
				     riveillä, nuolinäppäimet + Enter/Esc. -->
				<PlayerSearch
					id="draft-search"
					label="Add a player"
					bind:query={draftQuery}
					items={draftMatches}
					onSelect={addPick}
				/>
			{/if}
			<button
				type="button"
				class="primary"
				disabled={!draftReady}
				onclick={() => void submitDraft()}
			>
				{loading ? 'Rating…' : 'Rate my draft'}
			</button>
		{/if}
	</div>
{/if}

{#if auth.user && setupOpen}
	<!-- #66: tili-taso persistointi vain kirjautuneena (cross-device).
	     4.9: muistamisvalinta kuuluu joukkueen VAIHTAMISEEN, ei tulokseen. -->
	<div class="remember-row">
		<label class="remember-toggle">
			<input type="checkbox" checked={fplEntry.remember} onchange={() => void toggleRemember()} />
			Remember my team
		</label>
		{#if fplEntry.savedEntry != null}
			<button type="button" class="linklike" onclick={() => void forgetEntry()}>
				Forget saved team
			</button>
		{/if}
	</div>
	{#if fplEntry.savedEntry != null}
		<p class="muted hint">
			Saved to your GoalIQ account. Your team loads automatically on any device where you sign
			in.
		</p>
	{/if}
{/if}

{#if loading}
	<!-- #73: malli tekee töitä -progressiivinen paljastus -->
	<ModelWorking steps={WORKING_STEPS} />
{/if}

{#if error}
	<p class="banner error">{error}</p>
{:else if data}
	<!-- SOLIO-OPPI (19.8, Villen tilaus): kolmen mittarin yhteenvetonauha ennen
	     kortteja — yksi silmays kertoo kokonaiskuvan, kortit kantavat syvyyden.
	     JOKAINEN arvo tulee payloadista jonka kortit jo nayttavat; nauha ei
	     laske eika keksi mitaan uutta. Vareilla on kynnykset ja ne sanotaan
	     tooltipissa auki — variarvio ilman perustetta olisi sama vikaluokka
	     kuin luku ilman lahdetta. -->
	<!-- Portin korjaukset 19.8: (1) siirtoverdikti on Premium-sisaltoa
	     (MARKETING_QUEUE:n free/Premium-raja: HOLD on syvyys, ei
	     free-vaittama) — chip renderoituu vain premiumille eika ilmaispinta
	     saa lukua eika kantaa; (2) fallback-lause kantaa horisontin eika
	     vaita viikkokynnysta; (3) close call -peruste talon hyvaksytylla
	     muotoilulla + 0.00-tapaus omana lauseena; (4) siirtorivilta pallo
	     pois — sana Hold/Move kantaa tiedon, variarvio ilman perustetta ei. -->
	<!-- RATE-TEAM-PICKS-GW-LABEL (27.8, Villen kysymys "miksi hakee viime
	     kierroksen joukkueen"): FPL julkaisee uuden GW:n picksit vasta
	     deadlinen jalkeen (mitattu: /event/2/picks/ 404 deadlineen asti,
	     eivatka vahvistetut siirrotkaan nay — 7,67 M GW2-siirtoa, 0/121
	     entryn julkisessa listassa). Naytetty runko on siis pakosta
	     edellisen kierroksen, ja ilman tata rivia kayttaja paattelee etta
	     tuote on rikki. Ehto tulee backendista (meta.picks_outdated). -->
	{#if data.meta.picks_outdated === true && typeof data.meta.picks_gw === 'number' && typeof data.meta.deadline_gameweek === 'number'}
		<!-- Sanamuoto julkaisuportin 27.8 korjaamana: (1) ei luvata hetkea
		     ("shortly after" nojasi n=1-mittaukseen ja osui ikkunaan jossa
		     oma cache + is_current-flippi voivat antaa virheen), vaan
		     annetaan tarkistusreitti (FPL:n oma sivu); (2) CTA ei vaita
		     etta draft-rater saisi uuden rungon valmiina — kayttaja poimii
		     15 kasin, ja se sanotaan. -->
		<p class="notice-preseason">
			<strong>This is your GW{data.meta.picks_gw} squad.</strong>
			FPL publishes GW{data.meta.deadline_gameweek} squads a while after the
			deadline{#if pickDeadlineLocal}&nbsp;({pickDeadlineLocal}){/if}, so import again once
			yours is public on the FPL site. Changed your team already?
			<button type="button" class="linklike" onclick={openDraftFromNotice}>
				Rate my draft</button
			> instead: pick the new 15 by hand and the model rates them now.
		</p>
	{/if}
	{@const stripRating = data.rating.rating ?? Math.round(data.rating.percentile)}
	{@const capGap =
		data.captain.alternative != null
			? data.captain.pick.gw_xp - data.captain.alternative.gw_xp
			: null}
	{@const capClose = capGap != null && capGap < 0.15}
	<div class="verdict-strip">
		<span
			class="strip-item"
			title="GoalIQ model rating out of 100. Green from 90, amber from 75. The rating card below says what the 100 is measured against."
		>
			<span
				class="strip-dot"
				class:good={stripRating >= 90}
				class:mid={stripRating >= 75 && stripRating < 90}
				class:bad={stripRating < 75}
			></span>
			Squad <strong>{stripRating}/100</strong>
		</span>
		<span
			class="strip-item"
			title={capClose && capGap != null
				? capGap < 0.005
					? `${data.captain.alternative?.web_name} is level on xP this GW.`
					: `${data.captain.alternative?.web_name} is only ${capGap.toFixed(2)} xP behind, so this one is close.`
				: 'The model pick for the armband this gameweek.'}
		>
			Captain <strong>{data.captain.pick.web_name}</strong
			>{#if capClose}<span class="strip-note">close call</span>{/if}
		</span>
		{#if premium}
			{@const stripHold = data.transfers.hold_verdict?.verdict
				? data.transfers.hold_verdict.verdict === 'hold'
				: data.transfers.hold}
			<span
				class="strip-item"
				title={data.transfers.hold_verdict?.message ??
					(stripHold
						? `No move the model checked improves your team over the ${
								data.transfers.hold_verdict?.horizon_gws ??
								data.meta.transfer_horizon_gw ??
								data.meta.horizon_gw ??
								6
							}-GW horizon.`
						: 'The model found a move worth making.')}
			>
				<!-- 5.9 (Villen kysymys: "mika my teamissa on se ykkosasia mika
				     tulee kayttajan nahda"). Tassa luki ennen vain "Move", eli
				     nauha kertoi ETTA jotain kannattaa tehda muttei mita. Se
				     mita kayttaja tulee hakemaan on itse siirto, ja se oli
				     koko rating-kortin JALKEEN. Nimi ja tuotto tulevat samasta
				     `suggestions[0]`-rivista jota alempi lista kayttaa, joten
				     tassa ei ole uutta vaitetta eivatka luvut voi erota. -->
				{#if stripHold || data.transfers.suggestions.length === 0}
					Before the deadline <strong>Hold your transfer</strong>
				{:else}
					{@const top = data.transfers.suggestions[0]}
					Before the deadline
					<strong>{top.out.web_name} → {top.in.web_name}</strong>
					<!-- Ikkuna mukana: luku on delta_xp_horizon eli koko jaljella oleva
					     horisontti, ja "Before the deadline" -kehys saisi sen lukemaan
					     taman kierroksen tuottona (portti 5.9). -->
					{@const win = data.transfers.window_gws ?? []}
					{@const wFrom = data.transfers.hold_verdict?.gw_from ?? win[0]}
					{@const wTo = data.transfers.hold_verdict?.gw_to ?? win[win.length - 1]}
					<!-- Ikkuna luetaan transfers-lohkosta (window_gws / hold_verdict),
					     EI metasta: portti 5.9 mittasi ettei metassa ole gw_from/gw_to
					     -avaimia, joten edellinen versio renderoi "GW-". Jos ikkunaa ei
					     ole, se jatetaan pois kokonaan. -->
					<span class="strip-gain"
						>+{top.delta_xp_horizon.toFixed(2)} xP{#if wFrom != null && wTo != null}
							GW{wFrom}-{wTo}{/if}</span
					>
				{/if}
			</span>
		{:else}
			<!-- Ilmaiselle heikoin linja on aito vastaus kysymykseen "mista
			     aloitan", ja se on ilmaista tietoa. Konkreettinen siirtopari
			     on se mika on maksullista, ja tunniste sanoo sen suoraan. -->
			<span class="strip-item">
				Weakest line <strong>{data.rating.weakest_line}</strong>
				<span class="strip-tag">Premium for the move</span>
			</span>
		{/if}
	</div>
	<!-- 14.8: TULOS JA SILMUKKA VIERELLE, EI ALLE.
	     `.rating` on tarkoituksella `max-width: 680px` (lukumitta), joten
	     kortin leventaminen olisi vaara korjaus — pitka tekstipalsta on
	     vaikeampi lukea eika helpompi. Oikea korjaus on laittaa jotain sen
	     VIEREEN. Viikkosilmukka oli kortin SISALLA ja siksi ~530px levea
	     1080px:n palstassa; nyt se on oma sarakkeensa.
	     WeeklyActionsin alkuperainen sijoitusperuste sailyy: se on yha
	     nakyvissa samalla hetkella kun kayttaja nakee mita malli suosittaa —
	     nyt vierella eika alla, eli itse asiassa varmemmin. -->
	<div class="result-grid">
	<!-- 22.8 (Villen kuvahavainto): sivupalkin kolme korttia ovat selvasti
	     rating-korttia korkeammat, joten vasen sarake jatti ison tyhjan
	     alueen ja pitch alkoi vasta gridin jalkeen. Kentta kuuluu ratingin
	     alle samaan sarakkeeseen — silloin vasen sarake tayttyy sisallolla
	     eika tyhjalla. -->
	<div class="result-main">
	<!-- 5.9 (Villen pyynto): "haluaisin ensimmaisena nahda joukkueeni pitchin
	     kun avaan My team -valilehden". Kentta ensin, rating ja luvut sen
	     alla. Sama komponentti, vain jarjestys vaihtui. -->
	<!-- #113: pitch + kitit + what-if-manager (pariteetti mobiilin #106+#112:lle;
	     free = staattinen pitch + lukko, premium = editointi). #121: manageri
	     saa PLANNED-rosterin (sovelletut siirrot mukana); #123: default-GW.
	     22.8: siirretty result-gridin vasempaan sarakkeeseen (ks. yllä). -->
	<TeamPitchManager
		players={plannedPlayers}
		{premium}
		defaultGw={data.meta.gw}
		gwInProgress={data.meta.gw_in_progress === true}
		lastFinished={data.last_finished ?? null}
		picksGw={data.meta.picks_gw ?? null}
		{onUpgrade}
		initialCaptaincy={captaincy}
		onCaptaincyChange={handleCaptaincyChange}
	/>
	</div>

	<!-- 5.9 (Villen pyynto): oman rungon uutiset heti kentan alle - kuka on
	     poissa, kenen hinta liikkuu tanaan. Sama data kuin This week -sivun
	     "Before the next deadline", ei uutta laskentaa. -->
	<GwReview flagsOnly />

	<!-- #50: hero-luku = Team xP horisontilla (FPL-natiivi mittari); rating
	     sen alla = "% of the best possible budget team" (uusi semantiikka,
	     gap_to_optimal_xp defensiivisesti jos backend jo tarjoaa sen) -->
	<div class="rating card">
		<div class="hero-top">
			<p class="hero-xp" aria-hidden="true">
				<span class="hero-num">{Math.round(data.rating.team_xp_horizon)}</span><span
					class="hero-unit">xP</span
				>
			</p>
			<div class="hero-copy">
				<p class="headline">
					<abbr
						title="Expected points: our match model's projection per player per gameweek, summed over your squad"
						>Team xP</abbr
					>,
					<abbr title="The horizon: how many upcoming gameweeks the projection covers"
						>next {data.meta.horizon_gw ?? 6} GWs</abbr
					>: <strong>{data.rating.team_xp_horizon.toFixed(1)}</strong>
					<!-- 28.7 (Villen havainto): ilman tata merkintaa lukija vertaa
					     315.3:a model-xi-sivun 303.4:aan ja paattelee voittaneensa
					     mallin. Perusteet ovat eri: hero tuplaa kapteenin, benchmark
					     ei. Sama virhe tehtiin kahdesti samana paivana. -->
					<span class="basis-note">captain doubled</span>
				</p>
				<!-- 26.7: beats_benchmark eksplisiittisesti. Aiemmin ylitys leikattiin
				     hiljaa 100 %:iin, jolloin tieto katosi ja luku luki ontolta
				     imartelulta. -->
				<p class="subline">
					{#if data.meta.rating_method == null && data.rating.optimal_team_xp == null}
						<!-- 28.7: mobiilin GUARD webiin. Ilman tata sivu vaitti "best
						     possible budget team" -mittaperustaa myos silloin kun payload
						     ei kanna sita. -->
						GoalIQ model rating:
						<strong>{data.rating.rating ?? Math.round(data.rating.percentile)}/100</strong>
					{:else if data.rating.beats_benchmark}
						Your XI <strong>beats</strong> the best team the model can build inside the
						budget. The model would pick your squad over its own.
					{:else}
						<!-- 28.7 (Villen havainto): otsikkoluku takaisin /100-muotoon.
						     26.7. backend lisasi `rating`-kokonaisluvun juuri siksi etta
						     se on luettavampi, mutta saman paivan pariteettikorjaus vei
						     molemmat pinnat prosenttiin. Prosentin ainoa aito etu oli
						     etta se kertoi mita mitataan - se sanotaan nyt suoraan
						     seuraavalla rivilla, joten kumpikaan ei haviaa. -->
						Team rating
						<strong>{data.rating.rating ?? Math.round(data.rating.percentile)}/100</strong
						>{#if typeof data.rating.gap_to_optimal_xp === 'number'}
							({data.rating.gap_to_optimal_xp > 0.05
								? `-${data.rating.gap_to_optimal_xp.toFixed(1)} xP`
								: 'level with it'}){/if}.
						<!-- 28.7: "best" vain kun backend on TODISTANUT sen. Vanha
						     vertailukohta oli ahne heuristiikka joka jai 15.2 xP
						     optimista, ja copy vaitti silti parasta mahdollista. -->
						<span class="rating-basis"
							>{data.rating.optimal_proven === false
								? '100 = the strongest squad the model found inside the 100.0m budget.'
								: '100 = the best squad the rules allow inside the 100.0m budget.'}
							{#if typeof data.rating.team_xp_horizon_no_captain === 'number' && typeof data.rating.optimal_team_xp === 'number'}
								Like for like, without the captain bonus on either side:
								{data.rating.team_xp_horizon_no_captain.toFixed(1)} vs
								{data.rating.optimal_team_xp.toFixed(1)}.
							{/if}</span
						>
					{/if}
				</p>
				<!-- 26.7: metodologia auki. Villen havainto: FFS antoi samasta
				     joukkueesta 83, me 97 -> ilman selitysta nayttaa silta etta
				     joku on vaarassa. Kumpikaan ei ole: mittarit ovat eri.
				     19.8 (portin loydos): sama 28.7-vartija kuin subline-rivilla —
				     vanha payload ilman rating_method/optimal_team_xp -kenttia ei
				     saa vaittaa "best XI our model can build" -mittaperustaa
				     taallakaan, ja verdict-nauhan tooltip ohjaa lukijan nyt
				     aktiivisesti tahan lohkoon. -->
				{#if !(data.meta.rating_method == null && data.rating.optimal_team_xp == null)}
				<details class="method">
					<summary>How this rating is calculated</summary>
					<p>
						We compare your XI's projected points over a {data.meta.horizon_gw ?? 6}-gameweek horizon
						to the best XI our model can build under the same squad rules: a 100.0m budget and
						no more than three players from one club. 100 means you captured every projected
						point those rules allow.
					</p>
					<p>
						Other FPL sites run their own projections and their own scale, so their number and
						ours are not comparable and neither is wrong. Two ratings can disagree simply
						because they measure against different reference points, not because one is broken.
					</p>
					<p>
						Ours answers one narrow question: how much of the available projected points did
						your squad capture? It says nothing about your rank, and projections are estimates,
						not outcomes.
					</p>
					<!-- 26.7: rating on vain niin hyva kuin projektiot sen alla, joten
					     ne on graded ja luku naytetaan. Tekee ratingista falsifioituvan
					     eika vain sisaisesti johdonmukaisen. -->
					{#if data.meta.projection_accuracy}
						{@const acc = data.meta.projection_accuracy}
						<p>
							<strong>How good are the projections?</strong> Graded on the whole
							{acc.meta?.season ?? 'previous'} season, walk-forward, so the model only ever saw
							gameweeks before the one it predicted. Average error
							<strong>{acc.played.mae_xp}</strong> points per player per gameweek against
							{acc.played.mae_baseline} for a form-based baseline, over {acc.played.n_gws}
							gameweeks. Rank correlation {acc.played.rho_xp} against {acc.played.rho_baseline}.
						</p>
						{#if acc.known_bias?.signed_bias_xp != null}
							<p>
								One known flaw, stated rather than hidden: the model under-predicts by about
								{Math.abs(acc.known_bias.signed_bias_xp).toFixed(2)} points per player per gameweek.
								That shifts every projection the same way, so the ranking holds, but absolute
								xP runs low.
							</p>
						{/if}
					{/if}
				</details>
				{/if}
			</div>
		</div>
		<div class="facts">
			<div class="fact">
				<span class="muted">Team xP, GW{data.meta.gw}</span>
				<span class="val">{data.rating.team_xp_gw.toFixed(1)}</span>
			</div>
			<div class="fact">
				<span class="muted">Strongest line</span>
				<span class="val line-strong">{data.rating.strongest_line}</span>
			</div>
			<div class="fact">
				<span class="muted">Weakest line</span>
				<span class="val line-weak">{data.rating.weakest_line}</span>
			</div>
		</div>
		<!-- Roast my team (7.8, kasvutemppu 2): sama data, piikikäs sävy —
		     UGC-jakoyksikkö. Logiikka lib/roast.ts (deterministinen, numerot
		     payloadista). Copy-nappi X-liittämistä varten; kuvakortti =
		     jatkotyö. -->
		<div class="roast-row">
			<button
				class="roast-toggle"
				onclick={() => {
					roastOpen = !roastOpen;
					if (roastOpen) capture('roast_viewed');
				}}>{roastOpen ? 'Hide the roast' : 'Roast my team'}</button
			>
		</div>
		{#if roastOpen}
			{@const roastLines = buildRoast(data)}
			<div class="roast card">
				{#each roastLines as line, i (i)}
					<p>{line}</p>
				{/each}
				<div class="roast-actions">
					<button
						class="roast-copy"
						onclick={() => {
							navigator.clipboard?.writeText(
								roastLines.join('\n\n') + '\n\nGet roasted: goaliq.app/fpl'
							);
							roastCopied = true;
							capture('roast_copied');
							setTimeout(() => (roastCopied = false), 2000);
						}}>{roastCopied ? 'Copied' : 'Copy roast for sharing'}</button
					>
				<!-- 16.8 (Villen tilaus): kuvakortti. Tiedostossa luki 7.8 asti
				     "kuvakortti = jatkotyo"; teksti yksin ei jaa yhta hyvin kuin
				     kuva, ja korttipostaus mitattiin 11.8 nelinkertaiseksi tekstiin
				     nahden (4100 vs 210 nayttoa). Taso tulee samasta roastTier-
				     funktiosta kuin teksti, jottei kortti sano eri asiaa kuin
				     rivit sen yllä. -->
				<button
					class="roast-copy"
					disabled={roastSharing}
					onclick={async () => {
						// Narrowing katoaa async-nuolifunktioon: `data` on nullable
						// komponentin tasolla vaikka lohko renderoityy vain kun se on.
						if (!data) return;
						roastSharing = true;
						try {
							const { tier, score } = roastTier(data);
							capture('roast_card_shared', { tier, score });
							await shareRoastCard({
								tier,
								score,
								headline: roastHeadline(tier),
								lines: roastLines,
								fileName: `goaliq-roast-${tier}.png`
							});
						} finally {
							roastSharing = false;
						}
					}}>{roastSharing ? 'Building...' : shareButtonLabel()}</button
				>
				</div>
			</div>
		{/if}

		<p class="captain">
			Captain suggestion: <strong>{data.captain.pick.web_name}</strong>
			<span class="muted">({data.captain.pick.team_short})</span>,
			{data.captain.pick.gw_xp.toFixed(2)} xP in GW{data.meta.gw}{#if data.captain.alternative}.
				Alternative: {data.captain.alternative.web_name}
				<span class="muted">({data.captain.alternative.team_short})</span>,
				{data.captain.alternative.gw_xp.toFixed(2)} xP{/if}.
		</p>
		{#if data.team.missing_ids.length > 0}
			<p class="muted">
				{data.team.missing_ids.length}
				{data.team.missing_ids.length === 1 ? 'player has' : 'players have'} no projection yet
				and {data.team.missing_ids.length === 1 ? 'is' : 'are'} excluded from the rating.
			</p>
		{/if}
		{#if typeof data.meta.note === 'string'}
			<p class="muted">{data.meta.note}</p>
		{/if}
	</div>

	<!-- 🔴 4.9: viikkosilmukka (WeeklyActions + BeatTheModel + SeasonRace) oli
	     tassa sivusarakkeena JA kokonaisuudessaan This week -sivulla. Kun
	     ryhmat saivat omat reittinsa, sama kolme lohkoa renderoityi kahdella
	     sivulla, eika kumpikaan kertonut kumpi on se oikea paikka. Villen
	     tilaus: "my team nakyma pitaa saada selkeammaksi ja reilusti".
	     My team vastaa yhteen kysymykseen: onko joukkueeni hyva ja mika sita
	     parantaa. Viikon tekeminen on This weekin kysymys. -->
	</div>

	{#if premium}
		<!-- #63: HOLD-verdikti HERO-kantana siirtolistan yläpuolella; backendin
		     hold_verdict on hit-tietoinen. Fallback #50-riviin jos kenttä puuttuu. -->
		{#if data.transfers.hold_verdict}
			<HoldVerdictCard verdict={data.transfers.hold_verdict} surface="rate_team" />
			{#if data.transfers.hold_verdict.verdict === 'transfer' && data.transfers.suggestions.length > 0}
				{@const top = data.transfers.suggestions[0]}
				<p class="verdict-line">
					Weak spot: <strong>{data.rating.weakest_line}</strong>. Top upgrade:
					<strong>{top.out.web_name}</strong> to <strong>{top.in.web_name}</strong>,
					<span class="gain-text">+{top.delta_xp_horizon.toFixed(2)} xP</span>.
				</p>
			{/if}
		{:else if data.transfers.hold}
			<p class="verdict-line hold">
				Verdict: <abbr
					title="Keeping (rolling) your free transfer this week instead of spending it"
					>hold</abbr
				> your transfer, rolling it looks like the better play over the projection horizon.
			</p>
		{:else if data.transfers.suggestions.length > 0}
			{@const top = data.transfers.suggestions[0]}
			<p class="verdict-line">
				Weak spot: <strong>{data.rating.weakest_line}</strong>. Top upgrade:
				<strong>{top.out.web_name}</strong> to <strong>{top.in.web_name}</strong>,
				<span class="gain-text">+{top.delta_xp_horizon.toFixed(2)} xP</span>.
			</p>
		{/if}
		<h3>Transfer suggestions</h3>
		{#if data.transfers.suggestions.length > 0}
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Out</th>
							<th>In</th>
							<th>Pos</th>
							<th class="num"><abbr title="Price change from the swap, millions">Δ cost</abbr></th>
							<th class="num"
								><abbr title="Projected xP gain over the remaining horizon">Δ xP</abbr></th
							>
							<th></th>
						</tr>
					</thead>
					<tbody>
						{#each data.transfers.suggestions as s (s.out.id + '-' + s.in.id)}
							{@const key = `${s.out.id}-${s.in.id}`}
							{@const isApplied = appliedKeys.has(key)}
							<tr>
								<td
									>{s.out.web_name}
									<span class="muted">({s.out.team_short}, {s.out.price.toFixed(1)})</span></td
								>
								<td
									>{s.in.web_name}
									<span class="muted">({s.in.team_short}, {s.in.price.toFixed(1)})</span></td
								>
								<td>{s.pos}</td>
								<td class="num">{s.delta_cost > 0 ? '+' : ''}{s.delta_cost.toFixed(1)}</td>
								<td class="num gain">+{s.delta_xp_horizon.toFixed(2)}</td>
								<td class="num">
									<!-- #121: Apply → planned-pitch päivittyy heti (lokaali) -->
									{#if s.in.xp_per_gw != null}
										<button
											type="button"
											class="apply-btn"
											class:applied={isApplied}
											disabled={isApplied || !canApply(s)}
											onclick={() => setPlan([...appliedTransfers, s])}
										>
											{isApplied ? 'Applied' : 'Apply'}
										</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		{#if appliedTransfers.length > 0}
			<!-- #121: suunnitelman yhteenveto — juokseva bank (jaettu budjetti,
			     #35) + eksakti netto-xP + undo/reset. Read-only what-if. -->
			<div class="plan-box">
				<p class="plan-title">
					Your transfer plan ({appliedTransfers.length})
					<span class="muted">
						· Bank after transfers: {planBank.toFixed(1)}m · Net xP over horizon:
						{planNetXp > 0 ? '+' : ''}{planNetXp.toFixed(1)}
					</span>
				</p>
				<div class="plan-actions">
					<button
						type="button"
						class="plan-btn"
						onclick={() => setPlan(appliedTransfers.slice(0, -1))}
					>
						Undo last
					</button>
					<button type="button" class="plan-btn" onclick={() => setPlan([])}>
						Reset plan
					</button>
				</div>
				<p class="muted plan-note">
					{#if planSaved}<strong>Saved to your draft.</strong> It stays here and, when you
						are signed in, on your phone too.{/if} Nothing is sent to FPL: they have no public
					write API, so make the final move in the official FPL app.
				</p>
			</div>
		{/if}
		{#if data.transfers.note}
			<p class="muted">{data.transfers.note}</p>
		{/if}
	{:else}
		<button type="button" class="teaser-row" onclick={unlock}>
			<span>
				Transfer suggestions <span class="muted">(out → in, with projected xP gain)</span>
			</span>
			<span class="locked" aria-label="Locked">•.••</span>
			<span class="cta">Unlock with Premium</span>
		</button>
	{/if}
{/if}
{/if}

{#if slot === 'b'}
	<!-- 1.8: Joukkue 2 — sama arviointi, kevyt runko (ei tallennusta, ei
	     FM-silmukkaa, ei siirtosuunnitelmaa; ne kuuluvat omalle joukkueelle). -->
	<p class="muted hint">
		Comparison team. Rated the same way, but not saved and not linked to your account.
	</p>
	<form class="entry-form" onsubmit={rateB}>
		<div>
			<label for="rate-entry-b">FPL entry ID</label>
			<input
				id="rate-entry-b"
				inputmode="numeric"
				autocomplete="off"
				placeholder="e.g. 1234567"
				bind:value={entryBText}
			/>
		</div>
		<button class="primary" type="submit" disabled={!entryBValid || loadingB}>
			{loadingB ? 'Rating…' : 'Rate my team'}
		</button>
	</form>
	<!-- 1.8: mallin runko yhdellä napilla — beat the model näkyväksi -->
	<button
		type="button"
		class="model-squad-btn"
		disabled={loadingB}
		onclick={() => void loadModelSquadB()}
	>
		Load the model's squad
	</button>
	<p class="muted hint">
		Fills Team 2 with the model's own 15 and rates it. Edit the picks and try to beat it.
	</p>
	{#if picksNotPublishedB}
		<p class="notice-preseason">
			<strong>That squad is not public yet.</strong> FPL keeps a team private until the first
			deadline it plays. Build the comparison draft below instead and the model rates it
			exactly the same way.
		</p>
	{/if}
	<button
		type="button"
		class="linklike draft-toggle"
		onclick={() => (draftOpenB = !draftOpenB)}
	>
		{draftOpenB ? 'Hide the draft rater' : 'Rate a draft instead (no entry ID needed)'}
	</button>
	{#if draftOpenB}
		<div class="draft-box">
			{#if poolError}
				<p class="banner error">
					Could not load the player pool right now. Please try again shortly.
				</p>
			{:else}
				<div class="draft-chips">
					{#each DRAFT_ORDER as pos (pos)}
						{#each picksB.filter((p) => p.pos === pos) as p (p.id)}
							<button type="button" class="draft-chip" onclick={() => removePickB(p.id)}>
								{p.web_name}
								<span class="muted">{p.team_short} · {p.pos}</span>
								<span aria-hidden="true">×</span>
							</button>
						{/each}
					{/each}
				</div>
				<p class="muted hint">
					{picksB.length} / 15 picked · GK {posCountB.GKP}/2 · DEF {posCountB.DEF}/5 · MID
					{posCountB.MID}/5 · FWD {posCountB.FWD}/3
				</p>
				{#if picksB.length < 15}
					<PlayerSearch
						id="draft-search-b"
						label="Add a player"
						bind:query={draftQueryB}
						items={draftMatchesB}
						onSelect={addPickB}
					/>
				{/if}
				<button
					type="button"
					class="primary"
					disabled={!draftReadyB}
					onclick={() => void submitDraftB()}
				>
					{loadingB ? 'Rating…' : 'Rate my draft'}
				</button>
			{/if}
		</div>
	{/if}
	{#if loadingB}
		<ModelWorking steps={WORKING_STEPS} />
	{/if}
	{#if errorB}
		<p class="banner error">{errorB}</p>
	{:else if dataB}
		<div class="rating card">
			<div class="hero-top">
				<p class="hero-xp" aria-hidden="true">
					<span class="hero-num">{Math.round(dataB.rating.team_xp_horizon)}</span><span
						class="hero-unit">xP</span
					>
				</p>
				<div class="hero-copy">
					<p class="headline">
						Team xP, next {dataB.meta.horizon_gw ?? 6} GWs:
						<strong>{dataB.rating.team_xp_horizon.toFixed(1)}</strong>
						<span class="basis-note">captain doubled</span>
					</p>
					<p class="subline">
						{#if dataB.meta.rating_method == null && dataB.rating.optimal_team_xp == null}
							GoalIQ model rating:
							<strong>{dataB.rating.rating ?? Math.round(dataB.rating.percentile)}/100</strong>
						{:else if dataB.rating.beats_benchmark}
							This XI <strong>beats</strong> the best team the model can build inside the
							budget.
						{:else}
							Team rating
							<strong>{dataB.rating.rating ?? Math.round(dataB.rating.percentile)}/100</strong>.
							<span class="rating-basis"
								>{dataB.rating.optimal_proven === false
									? '100 = the strongest squad the model found inside the 100.0m budget.'
									: '100 = the best squad the rules allow inside the 100.0m budget.'}</span
							>
						{/if}
					</p>
				</div>
			</div>
			<div class="facts">
				<div class="fact">
					<span class="muted">Team xP, GW{dataB.meta.gw}</span>
					<span class="val">{dataB.rating.team_xp_gw.toFixed(1)}</span>
				</div>
				<div class="fact">
					<span class="muted">Strongest line</span>
					<span class="val line-strong">{dataB.rating.strongest_line}</span>
				</div>
				<div class="fact">
					<span class="muted">Weakest line</span>
					<span class="val line-weak">{dataB.rating.weakest_line}</span>
				</div>
			</div>
			<p class="captain">
				Captain suggestion: <strong>{dataB.captain.pick.web_name}</strong>
				<span class="muted">({dataB.captain.pick.team_short})</span>,
				{dataB.captain.pick.gw_xp.toFixed(2)} xP in GW{dataB.meta.gw}{#if dataB.captain.alternative}.
					Alternative: {dataB.captain.alternative.web_name}
					<span class="muted">({dataB.captain.alternative.team_short})</span>,
					{dataB.captain.alternative.gw_xp.toFixed(2)} xP{/if}.
			</p>
			{#if dataB.team.missing_ids.length > 0}
				<p class="muted">
					{dataB.team.missing_ids.length}
					{dataB.team.missing_ids.length === 1 ? 'player has' : 'players have'} no projection yet
					and {dataB.team.missing_ids.length === 1 ? 'is' : 'are'} excluded from the rating.
				</p>
			{/if}
			{#if typeof dataB.meta.note === 'string'}
				<p class="muted">{dataB.meta.note}</p>
			{/if}
		</div>
		<TeamPitchManager
			players={dataB.team.players}
			{premium}
			defaultGw={dataB.meta.gw}
			gwInProgress={dataB.meta.gw_in_progress === true}
			lastFinished={dataB.last_finished ?? null}
			picksGw={dataB.meta.picks_gw ?? null}
			{onUpgrade}
			initialCaptaincy={captaincyB}
			onCaptaincyChange={handleCaptaincyChangeB}
		/>
	{/if}
{/if}
{/if}

<style>
	/* 1.8: kaksoisjoukkue — joukkuechipit + vertailurivi */
	.slot-chips {
		display: flex;
		gap: var(--s-2);
		margin: 0 0 var(--s-3);
	}
	.slot-chip {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-muted);
		font-weight: 700;
		font-size: var(--step--1);
		padding: 6px 16px;
		cursor: pointer;
	}
	.slot-chip.active {
		background: rgba(255, 138, 92, 0.1);
		border-color: var(--accent);
		color: var(--giq-rust);
	}
	.compare-box {
		max-width: 640px;
		border: 1px solid var(--border);
		border-left: 4px solid var(--giq-rust);
		border-radius: var(--radius);
		background: var(--surface);
		padding: var(--s-3) var(--s-4);
		margin: 0 0 var(--s-3);
	}
	.compare-title {
		margin: 0;
		font-weight: 700;
		font-size: var(--step--1);
		color: var(--text-muted);
	}
	.compare-line {
		margin: 2px 0 0;
		font-variant-numeric: tabular-nums;
	}
	.compare-verdict {
		margin: 2px 0 0;
		font-size: var(--step--1);
	}
	.model-squad-btn {
		background: var(--surface);
		border: 1px solid var(--accent);
		border-radius: var(--radius);
		color: var(--giq-rust);
		font-weight: 700;
		font-size: var(--step--1);
		padding: 8px 16px;
		margin: 0 0 var(--s-1);
		cursor: pointer;
	}
	.model-squad-btn:disabled {
		opacity: 0.5;
		cursor: default;
	}
	/* 14.8: kaksi aloituspolkua vierekkain (entry-ID | draft).
	   Kortin sisainen tyhja tila oli isompi hukka kuin korttien valinen:
	   lomake kaytti ~kolmanneksen leveydesta. Alle 860px palataan
	   allekkain, jolloin lukujarjestys on entry-ID ensin kuten ennen. */
	.start-grid {
		display: grid;
		gap: var(--s-4);
		margin-bottom: var(--s-4);
	}
	.start-col {
		min-width: 0;
	}
	.start-title {
		margin: 0 0 var(--s-2);
		font-weight: 700;
	}
	@media (min-width: 860px) {
		.start-grid {
			grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
			gap: var(--s-6);
			align-items: start;
		}
		/* Pystyviiva erottaa polut ilman toista laatikkokerrosta — kortteja
		   oli jo kolme sisakkain, eika neljas auta luettavuutta. */
		.start-alt {
			border-left: 1px solid var(--border);
			padding-left: var(--s-6);
		}
	}
	/* 14.8: "This week" kahteen sarakkeeseen leveilla ruuduilla.
	   VASEN = tekeminen (viikon paatokset, kapteenisuositus),
	   OIKEA = tila (calls vs model, season race).
	   `minmax(0, ...)` on pakollinen: ilman sita sisalla oleva taulukko
	   levittaisi sarakkeen yli gridin ja rikkoisi koko rivin.
	   Alle 980px palataan yhteen sarakkeeseen samassa lukujarjestyksessa. */
	.week-grid {
		display: grid;
		gap: var(--s-5);
	}
	.week-col {
		display: grid;
		gap: var(--s-5);
		align-content: start;
		min-width: 0;
	}
	@media (min-width: 980px) {
		.week-grid {
			grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
			align-items: start;
		}
	}
	/* Web P1: week-tyhjätilan kortti */
	.week-setup {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-4);
		margin: var(--s-3) 0;
		background: var(--surface);
	}
	.week-setup p {
		margin: 0 0 var(--s-2);
	}
	.entry-form {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-3);
		align-items: end;
		margin-bottom: var(--s-4);
	}
	.hint {
		margin: 0 0 var(--s-4);
		font-size: var(--step--1);
	}
	/* #66: Remember my team -rivi (vain kirjautuneena) */
	.team-line {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.6ch;
	}
	.remember-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--s-3);
		max-width: 640px;
		margin: 0 0 var(--s-4);
	}
	.remember-toggle {
		display: inline-flex;
		align-items: center;
		gap: var(--s-2);
		font-size: var(--step--1);
		font-weight: 600;
		cursor: pointer;
	}
	.remember-toggle input {
		accent-color: var(--accent);
	}
	/* #121: apply-to-planner */
	.apply-btn {
		border: 1px solid var(--accent);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--accent);
		font-weight: 700;
		font-size: var(--step--1);
		padding: 4px 12px;
		cursor: pointer;
	}
	.apply-btn:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.apply-btn.applied {
		background: rgba(255, 138, 92, 0.1);
		border-color: rgba(255, 138, 92, 0.35);
		opacity: 1;
	}
	.plan-box {
		background: var(--giq-paper);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-3);
		margin: var(--s-3) 0;
		max-width: 680px;
	}
	.plan-title {
		margin: 0;
		font-weight: 700;
		font-size: var(--step--1);
	}
	.plan-actions {
		display: flex;
		gap: var(--s-2);
		margin-top: var(--s-2);
	}
	.plan-btn {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text);
		font-weight: 600;
		font-size: var(--step--1);
		padding: 6px 12px;
		cursor: pointer;
	}
	.plan-note {
		margin: var(--s-2) 0 0;
		font-size: var(--step--1);
	}
	.linklike {
		background: none;
		border: none;
		padding: 0;
		color: var(--giq-rust);
		font-weight: 700;
		font-size: var(--step--1);
		cursor: pointer;
	}
	/* P1: esikausi-draft */
	.draft-toggle {
		display: block;
		margin: 0 0 var(--s-3);
	}
	/* 28.7 (PI-16): neutraali ohjaus, EI virhetyyliä. Punainen laatikko kertoisi
	   käyttäjälle että hän teki jotain väärin, vaikka syy on FPL:n kalenteri. */
	/* PI-16b (28.7): .notice-preseason siirretty theme.css:ään — planner ja
	   siirtoketjut näyttävät saman esikausiselitteen, ja kolme scoped-kopiota
	   olisi ajautunut eroon. */
	.draft-box {
		max-width: 640px;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-3) var(--s-4);
		margin-bottom: var(--s-4);
	}
	.draft-chips {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2);
		margin-bottom: var(--s-2);
	}
	.clear-draft {
		background: none;
		border: none;
		padding: 0;
		font: inherit;
		color: var(--giq-rust);
		text-decoration: underline;
		cursor: pointer;
	}
	.draft-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: rgba(255, 138, 92, 0.1);
		border: 1px solid rgba(255, 138, 92, 0.35);
		border-radius: var(--radius);
		padding: 4px 12px;
		font-weight: 700;
		cursor: pointer;
	}
	/* Kohta 4: collapse-rivi kun draft on arvioitu */
	.draft-collapsed {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--s-3);
	}
	.linklike:hover {
		text-decoration: underline;
	}
	/* 14.8: rate-tulos vasemmalle, viikkosilmukka oikealle.
	   `.rating`in oma 680px:n lukumitta SAILYY — grid ei venyta sita, vaan
	   antaa jaljelle jaavalle tilalle sisallon. Ilman `minmax(0, ...)`
	   oikean sarakkeen taulukot levittaisivat rivin.
	   22.8: vasen sarake = rating + pitch (.result-main), sivupalkki sai
	   kiintean kaistan. Breakpoint nousi 1040 -> 1280: kentan viisikkorivi
	   (5 x 90px paitaa + penkin 210px kaista) tarvitsee vasemmalta
	   sarakkeelta ~520px pitch-osalle, ja se toteutuu vasta kun shell-palsta
	   on taysi 1180px. Alle 1280px pinotaan: tulos, kentta, sivukortit. */
	.result-grid {
		display: grid;
		gap: var(--s-4);
	}
	.result-main {
		min-width: 0;
	}
	@media (min-width: 1280px) {
		.result-grid {
			/* 4.9: sivusarake poistui (viikkosilmukka on This weekissa), joten
			   tulos saa koko leveyden. `.rating` pitaa yha oman lukumittansa
			   (680 px), eli tekstipalsta ei leviä liian leveaksi. */
			gap: var(--s-6);
			align-items: start;
		}
	}
	.rating {
		max-width: 680px;
		margin-bottom: var(--s-4);
		border-color: rgba(255, 138, 92, 0.35);
		background:
			linear-gradient(160deg, rgba(255, 138, 92, 0.09), transparent 55%),
			var(--surface);
	}
	.hero-top {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-2) var(--s-4);
		margin-bottom: var(--s-4);
	}
	/* 5.9: siirron tuotto ja PRO-tunniste verdict-stripissa. Positiivinen
	   delta kayttaa --positivea kuten muutkin tuotot; tunniste on amber
	   outline kuten tyokalunavissa, jotta lukko lukee samana kaikkialla. */
	.strip-gain {
		color: var(--positive);
		font-family: var(--font-mono);
		font-weight: 700;
		margin-left: 0.35em;
	}
	.strip-tag {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--accent);
		border: 1px solid var(--accent);
		padding: 0.1em 0.35em;
		margin-left: 0.4em;
		vertical-align: 0.12em;
	}

	.hero-xp {
		margin: 0;
		line-height: 1;
		white-space: nowrap;
		/* 5.9 (Villen kysymys "onko varitykset kunnossa"): tama oli
		   --giq-rust. Theme.css:n oma varidisipliini sanoo: amber = luvut,
		   rust = hitit, pudotukset ja saatavuusliput. Sivun suurin luku oli
		   siis maalattu "huono"-varilla, ja se on My teamin ensimmainen asia
		   jonka kayttaja nakee. */
		color: var(--accent);
		font-weight: 700;
	}
	.hero-num {
		font-size: clamp(2.8rem, 2.2rem + 3vw, 4.2rem);
		letter-spacing: -2px;
		font-variant-numeric: tabular-nums;
	}
	.hero-unit {
		font-size: var(--step-2);
		margin-left: 2px;
	}
	.hero-copy {
		flex: 1 1 220px;
	}
	.headline {
		font-size: var(--step-1);
		margin: 0 0 var(--s-1);
	}
	.subline {
		margin: 0;
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	/* 28.7: mittaperusta omalle rivilleen, jotta /100-luku ei jaa selittamatta */
	.rating-basis {
		display: block;
		font-size: var(--step--2);
	}
	/* Hero-luvun peruste samalla rivilla, pienempana */
	.basis-note {
		font-size: var(--step--2);
		color: var(--text-muted);
		white-space: nowrap;
	}
	/* 26.7: metodologia auki, oletuksena kiinni (ei vie tilaa herolta) */
	.method {
		margin: var(--s-2) 0 0;
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	.method summary {
		cursor: pointer;
		font-weight: 600;
		color: var(--giq-rust);
	}
	.method p {
		margin: var(--s-2) 0 0;
		max-width: 60ch;
	}
	.line-strong {
		color: var(--positive);
	}
	.line-weak {
		color: var(--negative);
	}
	/* #50: verdict + action -rivi taulukon yllä; hold-variantti kulta-aksentilla */
	.verdict-line {
		max-width: 640px;
		border: 1px solid var(--border);
		border-left: 4px solid var(--giq-rust);
		background: var(--surface);
		border-radius: var(--radius);
		padding: var(--s-3) var(--s-4);
		margin: var(--s-4) 0 0;
	}
	.verdict-line.hold {
		border-left-color: var(--giq-gold-deep);
		color: var(--warn-text);
		font-weight: 700;
	}
	.gain-text {
		color: var(--positive);
		font-weight: 700;
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: var(--s-3);
		margin-bottom: var(--s-4);
	}
	.fact {
		display: grid;
		gap: 2px;
	}
	.fact .val {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.captain {
		margin-bottom: var(--s-2);
	}
	td.gain {
		color: var(--positive);
		font-weight: 700;
	}
	/* Lukittu teaser: sama •.••-kieli kuin Paywall-teaser */
	.teaser-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--s-3);
		width: 100%;
		max-width: 640px;
		text-align: left;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-3) var(--s-4);
		color: var(--text);
		font-weight: 500;
		font-size: var(--step--1);
	}
	.teaser-row:hover {
		border-color: var(--accent);
	}
	.locked {
		color: var(--giq-rust);
		font-weight: 700;
		letter-spacing: 2px;
		margin-left: auto;
	}
	.cta {
		color: var(--positive);
		font-weight: 700;
	}
	/* Roast my team (7.8) */
	.roast-row {
		margin-top: var(--s-2);
	}
	.roast-toggle,
	.roast-actions {
		display: flex;
		gap: var(--s-2);
		flex-wrap: wrap;
	}
	.roast-copy {
		background: none;
		border: 1px solid var(--border);
		border-radius: 3px;
		padding: var(--s-1) var(--s-2);
		cursor: pointer;
		color: inherit;
		font: inherit;
	}
	.roast-copy:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.roast-toggle:hover,
	.roast-copy:hover {
		border-color: var(--accent);
	}
	.roast {
		margin-top: var(--s-2);
		padding: var(--s-3);
		border-left: 3px solid var(--accent);
	}
	.roast p {
		margin: 0 0 var(--s-2);
	}

	/* SOLIO-OPPI (19.8): yhteenvetonauha. Sama pintakieli kuin muissa
	   korteissa (surface-alt + ohut reunus), pallot semanttisilla vareilla. */
	.verdict-strip {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2) var(--s-4);
		margin: var(--s-3) 0;
		padding: var(--s-2) var(--s-3);
		background: var(--surface-alt, #1f1d1a);
		border: 1px solid var(--line, rgba(243, 242, 242, 0.13));
		font-size: 13px;
	}
	.strip-item {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--muted, #a8a29a);
		cursor: help;
	}
	.strip-item strong {
		color: var(--text, #f3f2f2);
	}
	.strip-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--muted, #a8a29a);
	}
	.strip-dot.good {
		background: var(--teal, #2ed6c2);
	}
	.strip-dot.mid {
		background: var(--accent, #f5c542);
	}
	.strip-dot.bad {
		background: #ff8a5c;
	}
	.strip-note {
		margin-left: 6px;
		font-size: 11px;
		color: var(--accent, #f5c542);
		border: 1px solid rgba(245, 197, 66, 0.4);
		padding: 1px 5px;
	}
</style>
