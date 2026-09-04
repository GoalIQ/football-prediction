<script lang="ts">
	/**
	 * ToolsHome — Web P1 (30.7, Villen GO "Web P1 go, matches omaan ryhmään").
	 *
	 * Korvaa FreeView + ProView + ProTools -kolmikon YHDELLÄ näkymällä:
	 * 6 sisältöryhmää, yksi segmenttinauha, gate LOHKON sisällä (sama malli
	 * kuin mobiilin Fantasy-tab). Vanha rakenne jakoi ylätabit ENTITLEMENTIN
	 * mukaan → 24 välilehtipositiota, 7 työkalua duplikoituna ja 4 työkalua
	 * jotka MAKSAVA käyttäjä menetti (clean sheets, fit checker, price watch,
	 * mini-league olivat vain free-nauhassa). Maksu ei saa koskaan kaventaa
	 * näkymää — nyt kaikki näkevät saman rakenteen ja premium avaa lohkoja.
	 *
	 * Upgrade-polku: teaserien onUpgrade avaa upgrade-näkymän (PremiumPreview
	 * + LoginBox kirjautumattomalle, Paywall kirjautuneelle ilman tilausta) —
	 * osto- ja checkout-paluulogiikka siirtyi ProView'sta tänne sellaisenaan.
	 */
	import { onMount } from 'svelte';
	import { auth, refreshSubscription, freePremiumWindowActive } from '$lib/auth.svelte';
	import { fetchXp, type XpResponse } from '$lib/api';
	import { capture } from '$lib/analytics';
	import { fplEntry } from '$lib/fplEntry.svelte';
	import DefConLive from './DefConLive.svelte';
	import Provenance from './Provenance.svelte';
	import LeagueBanner from './LeagueBanner.svelte';
	import SegmentNav, { type Segment } from './SegmentNav.svelte';
	import ToolRow from './ToolRow.svelte';
	import ToolDirectory from './ToolDirectory.svelte';
	import { goto } from '$app/navigation';
	import {
		GROUPS,
		LEGACY_HASH_TO_PATH,
		findTool,
		primaryTool,
		toolsInGroup
	} from '$lib/tools';
	import LoginBox from './LoginBox.svelte';
	import Paywall from './Paywall.svelte';
	import PremiumPreview from './PremiumPreview.svelte';
	import SetPassword from './SetPassword.svelte';
	import RateTeam from './RateTeam.svelte';
	import FitChecker from './FitChecker.svelte';
	import Watchlist from './Watchlist.svelte';
	import TransferPlanner from './TransferPlanner.svelte';
	import PlayerCard from './PlayerCard.svelte';
	import CaptainRanker from './CaptainRanker.svelte';
	import FixtureSwing from './FixtureSwing.svelte';
	import XpTable from './XpTable.svelte';
	import CleanSheets from './CleanSheets.svelte';
	import Value from './Value.svelte';
	import Leaders from './Leaders.svelte';
	import Differentials from './Differentials.svelte';
	import Replacements from './Replacements.svelte';
	import ComparePlayers from './ComparePlayers.svelte';
	import ChipEv from './ChipEv.svelte';
	import WildcardPlan from './WildcardPlan.svelte';
	import PlanChains from './PlanChains.svelte';
	import EdgeMode from './EdgeMode.svelte';
	import MiniLeague from './MiniLeague.svelte';
	import PriceWatch from './PriceWatch.svelte';
	import Predict from './Predict.svelte';
	import Fixtures from './Fixtures.svelte';
	import Standings from './Standings.svelte';

	let {
		forcePremium = false,
		upgradeSignal = 0,
		group = 'week',
		tool = null,
		all = false
	}: {
		/** DEV-esikatselu (/dev-premium): premium-lohkot auki ilman gatea. */
		forcePremium?: boolean;
		/** Heron Upgrade-badge nostaa tätä → upgrade-näkymä auki. */
		upgradeSignal?: number;
		/** Reitin ryhma (/week, /players, ...). Reitti on totuus, ei tila. */
		group?: string;
		/** Reitin tyokalu (/players/leaders) tai null = ryhman hakemisto. */
		tool?: string | null;
		/** ?all=1 — ryhman kaikki tyokalut yhdella sivulla (vanha kayttaytyminen). */
		all?: boolean;
	} = $props();

	// 4.9: ryhmat, tyokalut ja vanhojen hashien ohjaus tulevat rekisterista
	// (`$lib/tools`) — yksi lukija. Ennen tama komponentti maaritteli GROUPSin
	// ja LEGACY_HASHin itse, ja jalkimmainen osoitti RYHMAAN eika tyokaluun.
	const NAV: Segment[] = GROUPS.map((g) => ({ id: g.id, label: g.label, href: `/${g.id}` }));

	/** 4.9: app-tilaajan tervetulobanneri kerran per sessio (ks. markup). */
	let showAppWelcome = $state(false);
	onMount(() => {
		try {
			if (sessionStorage.getItem('app_welcome_seen') !== '1') {
				showAppWelcome = true;
				sessionStorage.setItem('app_welcome_seen', '1');
			}
		} catch {
			// Estetty tallennus: nayta banneri, alkuperainen kayttaytyminen.
			showAppWelcome = true;
		}
	});

	// Reitti on totuus: segmentti ja avattu tyokalu johdetaan propseista.
	// Ennen 4.9 nama olivat komponentin omaa tilaa, jolloin sama tila saattoi
	// olla eri kuin osoiterivi (ja paluunappi ei liikuttanut kumpaakaan).
	const segment = $derived(group);
	const groupTools = $derived(toolsInGroup(group));
	// Ryhman paatyokalu avautuu suoraan: /team = oma joukkue, ei korttilista.
	const groupPrimary = $derived(primaryTool(group) ?? null);
	const activeTool = $derived(findTool(group, tool) ?? (all ? null : groupPrimary));
	/**
	 * Ryhman etusivu on hakemisto kun ryhmassa on enemman kuin yksi tyokalu.
	 * 🔴 Mitattu 4.9: `/players` oli pinottuna 21 173 px pitka. Pinottu
	 * nakyma on yha olemassa (?all=1), mutta se on valinta eika oletus.
	 * `week` ei ole tyokalulista vaan yksi koostettu nakyma, joten sille ei
	 * synny hakemistoa (rekisterin GROUPS_WITHOUT_TOOLS).
	 */
	const showDirectory = $derived(activeTool === null && !all && groupTools.length > 1);
	/** Nayttaako ryhmasivu taman tyokalun? Ilman valintaa: kaikki. */
	function show(slug: string): boolean {
		return activeTool === null || activeTool.slug === slug;
	}
	/** 6.8: sticky-segmenttirivin mitattu korkeus → onpage-rivin top-offset. */
	let segNavH = $state(0);
	let upgradeOpen = $state(false);
	let checkoutSuccess = $state(false);
	let guestCheckout = $state(false);

	// Tools-hakemiston avattu työkalu (sama grid-kaava kuin mobiilin P1).
	// Tools-ryhman hakemistokortit tulevat rekisterista (nimi + kysymys + taso),
	// eika tasta tiedostosta. Avattu tyokalu on reitti, ei tila.
	type ToolKey = 'chip-timing' | 'transfer-chains' | 'edge-mode' | 'league';
	const openTool = $derived((activeTool?.group === 'tools' ? activeTool.slug : null) as ToolKey | null);

	// Matches-ryhmän sisäinen valinta (Villen valinta: oma ryhmä, ei gridiä).
	const matchesView = $derived(
		activeTool?.group === 'matches'
			? ((activeTool.slug === 'table' ? 'standings' : activeTool.slug) as
					| 'predict'
					| 'fixtures'
					| 'standings')
			: 'predict'
	);
	let predictPrefill = $state<{ league: string; home: string; away: string } | null>(null);
	function goPredict(lg: string, h: string, a: string) {
		predictPrefill = { league: lg, home: h, away: a };
		void goto('/matches/predict');
	}

	const premium = $derived(forcePremium || !!auth.sub);
	/**
	 * 🔴 Villen havainto 16.8: "keep it after that -buttoni ei ohjaa mihinkään".
	 *
	 * `premium` avaa työkalut, ja ilmaisikkunan synteettinen tilaus tekee siitä
	 * toden. Upgrade-näkymä ei kuitenkaan saa käyttää samaa lippua: se sulkeutui
	 * heti auettuaan (efekti alla) eikä renderöitynyt koskaan, koska ikkunan
	 * käyttäjä lasketaan premiumiksi. Nappi nosti lipun ja efekti laski sen
	 * samassa hetkessä.
	 *
	 * Seuraus oli tulonmenetys eikä kosmeettinen vika: ikkuna piilottaa
	 * paywallin, joten tämä oli AINOA ostopolku ikkunan aikana. Kukaan ei ole
	 * voinut ostaa siitä hetkestä kun ikkuna avattiin.
	 */
	const paidPremium = $derived(
		forcePremium || (!!auth.sub && auth.sub.plan !== 'gw1-3-free')
	);

	/**
	 * Miksi nakyma avattiin. Ratkaisee saako se sulkeutua itsestaan.
	 *
	 * 🔴 Kaksi vaatimusta jotka ovat suoraan ristiriidassa, ja siksi pelkka
	 * lippu ei riita (mitattu: molemmat rikkoutuivat vuorollaan 16.8):
	 *   'gate' = kayttaja tormasi lukkoon -> kun oikeus aukeaa, nakyman ON
	 *            sulkeuduttava, muuten rekisteroitynyt jaa jumiin
	 *            upgrade-sivulle ja joutuu etsimaan "Back to the tools".
	 *   'keep' = kayttajalla ON jo oikeus ja han tuli ostamaan sen jatkoksi
	 *            ("Keep it after that") -> nakyma EI saa sulkeutua, muuten
	 *            nappi sulkee itsensa samassa hetkessa kun se aukeaa.
	 */
	let upgradeIntent = $state<'gate' | 'keep'>('gate');

	function openUpgrade(intent: 'gate' | 'keep') {
		upgradeIntent = intent;
		upgradeOpen = true;
		requestAnimationFrame(() => {
			document.querySelector('main')?.scrollIntoView({ behavior: 'smooth' });
		});
	}
	// 🔴 Nama kaksi eivat ota parametria. Ensimmainen versio oli
	// `goUpgrade(intent = 'gate')`, ja `onclick={goUpgrade}` syotti sille
	// MouseEventin: aie ei ollut kumpikaan arvo, joten sulkeva efekti ei
	// laukennut koskaan ja korjaus oli nakymaton. svelte-check nappasi sen
	// tyyppivirheena, mutta vika oli toiminnallinen.
	function goUpgrade() {
		openUpgrade('gate');
	}
	function goKeepPremium() {
		openUpgrade('keep');
	}

	// Hero-badge → upgrade-näkymä (signaali +page.sveltestä).
	let lastSignal = 0;
	$effect(() => {
		if (upgradeSignal > lastSignal) {
			lastSignal = upgradeSignal;
			goUpgrade();
		}
	});

	// Tilauksen aktivoituminen sulkee upgrade-näkymän itsestään.
	$effect(() => {
		// Oikeuden aukeaminen sulkee nakyman VAIN jos kayttaja tuli tanne
		// lukon takia. 'keep'-aikeella tullut on jo premium, ja sulkeminen
		// tappaisi juuri sen napin jota han painoi.
		if (upgradeOpen && upgradeIntent === 'gate' && premium) upgradeOpen = false;
		if (upgradeOpen && upgradeIntent === 'keep' && paidPremium) upgradeOpen = false;
	});

	onMount(() => {
		// Checkout-paluu (?checkout=success): fulfillment tapahtuu webhookissa —
		// täällä kuitataan + kysytään tilaustila uudelleen (webhook-viivettä
		// vastaan). Siirretty ProView'sta sellaisenaan.
		const params = new URLSearchParams(window.location.search);
		if (params.get('checkout') === 'success') {
			checkoutSuccess = true;
			guestCheckout = params.get('guest') === '1';
			const sid = params.get('session_id') ?? 'unknown';
			capture('purchase_completed', { source: 'web', guest: guestCheckout }, `purchase_${sid}`);
			history.replaceState(null, '', window.location.pathname);
			upgradeOpen = true;
			let tries = 0;
			const poll = () => {
				void refreshSubscription().then(() => {
					if (!auth.sub && ++tries < 5) setTimeout(poll, 3000);
				});
			};
			poll();
		}
		// #101: ?tab=premium avaa arvo-esikatselun + hinnat suoraan.
		const tab = params.get('tab');
		if (tab === 'premium' || tab === 'pro') upgradeOpen = true;
		// Vanhat deep-linkit uusiin ryhmiin (SegmentNav hoitaa uudet id:t).
		// Vanha deep-linkki (#tools=leaders) ohjautuu TYOKALUUN eika ryhmaan.
		// Ennen 4.9 se osoitti ryhmaan, eli linkki "avaa clean sheets" pudotti
		// kayttajan kymmenen tyokalun pinon ylalaitaan. Kartta on rekisterissa
		// ja jokainen 19:sta on testattu yksitellen.
		const m = window.location.hash.match(/^#tools=([\w-]+)$/);
		if (m && LEGACY_HASH_TO_PATH[m[1]]) {
			void goto(LEGACY_HASH_TO_PATH[m[1]], { replaceState: true });
		}
	});

	// xP-pooli premium-työkaluille. Haku lähtee heti session ratkettua
	// (rinnakkain tilaustarkistuksen kanssa, 26.7 PERF-oppi); free-käyttäjälle
	// 555 kB:n haku ei lähde lainkaan.
	let xp = $state<XpResponse | null>(null);
	let xpError = $state<string | null>(null);
	$effect(() => {
		if ((auth.user || forcePremium) && !xp && !xpError) {
			fetchXp().then(
				(d) => (xp = d),
				(e) => (xpError = String(e))
			);
		}
	});

	// 4.9: `jumpTo` ja `openToolCard` poistuivat. Kumpikin oli kiertotie
	// samaan puutteeseen: tyokalulla ei ollut osoitetta, joten siihen
	// paastiin vain vierittamalla tai vaihtamalla komponentin tilaa. Nyt
	// molemmat ovat linkkeja (`ToolRow`, hakemistokortit), ja lukitun kortin
	// klikkaus kirjaa upgraden markupissa.
</script>

{#if checkoutSuccess}
	{#if guestCheckout && !auth.user}
		<p class="banner success">
			Payment received. Premium is yours! We just emailed you a sign-in link (check spam
			too). Click it to open Premium here on the web; once signed in, you can set a password
			to use the same account in the GoalIQ app on iOS and Android.
		</p>
	{:else}
		<p class="banner success">
			Premium active, welcome aboard! Premium is now active on the web AND in the GoalIQ app
			(iOS and Android). Just sign in with the same account on your phone.
		</p>
	{/if}
{/if}

<!-- 🔴 IKKUNAILMOITUS LASKEUTUMISNAKYMAAN (16.8, portin loydos).
     Ilmoitus oli vain `PremiumPreview`-komponentissa, joka renderoityy
     VASTA kun `upgradeOpen` on tosi eli `?tab=premium`-parametrilla tai
     Upgrade-klikilla. Kirjautumaton kavija joka tuli suoraan
     pro.goaliq.appiin ei nahnyt ikkunasta mitaan - ja juuri se on se URL
     jonka annoimme luojille heidan ref-linkkiinsa. Heidan liikenteensa
     olisi laskeutunut sivulle joka ei kerro tarjouksesta.
     🔴 POISTA 12.9.2026 12:30 UTC jalkeen. -->
{#if freePremiumWindowActive() && !auth.user}
	<!-- 🔴 Villen havainto 16.8: "missa ohjeistus". Tama oli kappale jonka
	     sisassa sisaankaynti oli tekstilinkkina, eli sivun tarkein teko nakyi
	     samankokoisena kuin sen ymparilla oleva selitys. -->
	<div class="free-card">
		<h2>Premium is free until 12 September</h2>
		<p>
			That is GW1 to GW3. Create a free account and every Premium tool switches on straight
			away. No card, nothing to cancel, and nothing happens when the window closes unless you
			decide to keep it.
		</p>
		<button type="button" class="free-card-cta" onclick={goUpgrade}>
			Create a free account
		</button>
	</div>
{/if}

{#if upgradeOpen && !paidPremium}
	<!-- Upgrade-näkymä: ei enää oma ylätabi vaan päällekkäinen tila, josta
	     pääsee takaisin työkaluihin yhdellä klikillä. -->
	<button type="button" class="back-link" onclick={() => (upgradeOpen = false)}>
		‹ Back to the tools
	</button>
	{#if !auth.sessionResolved}
		<p class="muted">Checking session…</p>
	{:else if !auth.user}
		<!-- 🔴 Ikkunan aikana lomake ENNEN ominaisuuslistaa: teko ensin, myynti
		     perassa. Normaalisti jarjestys on oikein pain, koska silloin
		     kavijan pitaa vakuuttua ennen kuin tili on hanelle mitaan arvoinen
		     - ikkunan aikana tili on ilmainen eika vakuuttelua tarvita.
		     🔴 PALAUTA ALKUPERAINEN JARJESTYS 12.9.2026 12:30 UTC jalkeen. -->
		{#if freePremiumWindowActive()}
			<LoginBox />
			<PremiumPreview />
		{:else}
			<PremiumPreview />
			<LoginBox />
		{/if}
	{:else if auth.subLoading && auth.sub === undefined}
		<p class="muted">Checking subscription…</p>
	{:else}
		<Paywall />
	{/if}
{:else}
	{#if auth.sub}
		{#if auth.sub.plan === 'gw1-3-free'}
			<!-- 16.8: ilmainen ikkuna EI saa nayttaa ostetulta tilaukselta.
			     Vanha else-haara olisi sanonut "thank you for the support"
			     kayttajalle joka ei ole maksanut, ja tarjonnut SetPasswordin
			     jota ei ole ostettu. Ja koska ikkuna piilottaa paywallin,
			     ostopolun on oltava tassa - muuten kukaan ei voi ostaa
			     ikkunan aikana vaikka haluaisi. -->
			<p class="banner success">
				Premium is open to every account until the GW4 deadline on 12 September. Nothing to pay
				and nothing to cancel. <button type="button" class="linklike" onclick={goKeepPremium}
					>Keep it after that</button
				>
			</p>
		{:else if auth.sub.plan === 'app'}
			<!-- 4.9 YLAPINON BUDJETTI: tervetulotoivotus on kertaluontoinen tieto,
			     mutta se renderoityi joka latauksella tyokalunavin ylapuolelle.
			     Nyt kerran per sessio; itse tieto ei muutu eika katoa (tili nakyy
			     Account-valikossa). -->
			{#if showAppWelcome}
				<p class="banner success">Your GoalIQ app subscription is active here too. Welcome.</p>
			{/if}
		{:else}
			<p class="muted">GoalIQ Premium active ({auth.sub.plan}) · thank you for the support!</p>
			<SetPassword />
		{/if}
	{/if}

	<!-- 2.8: DefCon-live ylimpänä ja segmenttien ULKOPUOLELLA — se on
	     aikakriittinen eikä saa olla välilehden takana. Renderöi tyhjää aina
	     kun kierros ei ole käynnissä, joten esikaudella tämä ei näy.
	     4.9 (ylapinon budjetti): lohko pysyy tassa, mutta lista on
	     kokoontaitettu — yhteenvetorivi (GW + montako kynnyksella) jaa
	     nakyviin joka valilehdelle, 13 rivin lista ei. Perustelu ja mittaus
	     `DefConLive.svelte`:n kommentissa. -->
	<DefConLive />
	<!-- 6.8 (Villen palaute): segmenttirivi kulkee scrollissa mukana —
	     Players → My team ilman paluuta ylös. Korkeus mitataan, jotta
	     onpage-rivi osaa asettua sen ALLE myös kun pillit rivittyvät. -->
	<div class="segnav-sticky" bind:clientHeight={segNavH}>
		<SegmentNav segments={NAV} active={segment} label="GoalIQ FPL tools" />
	</div>

	<!-- 4.9: ryhman tyokalurivi. Korvaa "On this page:" -ankkuririvin, joka
	     vieritti pitkaa sivua; nama ovat linkkeja omiin URLeihin. -->
	<ToolRow
		tools={groupTools}
		{group}
		active={activeTool?.slug ?? null}
		{all}
		{premium}
	/>

	{#if showDirectory}
		<!-- Ryhman hakemisto: nimi + kysymys + taso, jokainen oma URL. -->
		<ToolDirectory
			tools={groupTools}
			{premium}
			onLocked={(slug) => {
				capture('upgrade_tapped', { source: `fantasy_${slug}` });
				goUpgrade();
			}}
		/>
	{/if}

	{#if segment === 'week'}
		<!-- 🔴 Villen havainto 4.9: "this week kadotti ton fpl entry ID:n vaikka
		     se on my teamissa". Sivu KAYTTI tallennettua joukkuetta, mutta ei
		     kertonut sita missaan, joten lukija ei voinut tietaa kenen luvuista
		     on kyse. Rivi kertoo sen ja vie suoraan joukkueeseen. -->
		<p class="team-context">
			{#if fplEntry.savedEntry}
				Your saved FPL team is {fplEntry.savedEntry}.
				<a href="/team/rate-my-team">Open Rate my team</a>
			{:else}
				<a href="/team/rate-my-team">Add your FPL entry ID</a> and this page follows your own
				squad.
			{/if}
		</p>
	{/if}

	{#if showDirectory && segment !== 'tools'}
		<!-- Hakemisto renderoitiin jo yllä; ryhman pinottu sisalto jaa pois. -->
	{:else if segment === 'week' || segment === 'team'}
		<!-- week + team jakavat SAMAN RateTeam-elementin (sama puupositio →
		     Svelte ei tuhoa instanssia vaihdossa → data/entry-tila säilyy). -->
		<div id="panel-{segment}" role="tabpanel" aria-labelledby="seg-{segment}">
			<!-- 30.7:n ankkuririvi ("fit checker yms hukkuu") korvattiin 4.9
			     ToolRow'lla: sama ongelma, mutta ratkaisuna oma URL eika
			     vieritys. -->
			{#if segment === 'week' || show('rate-my-team')}
			<div class="tool-card" id="tc-rate">
				<RateTeam
					{premium}
					onUpgrade={goUpgrade}
					weekMode={segment === 'week'}
					onGoToTeam={() => goto('/team')}
				/>
			</div>
			{/if}
			{#if segment === 'team'}
				<!-- Järjestys 30.7: fit checker HETI raten alle (esikauden
				     sankarityökalu), watchlist viimeiseksi (pisin lista).
				     14.8 (Villen palaute: "ne ovat tossa allekain ns listana"):
				     sama järjestys, mutta kaksi saraketta leveillä ruuduilla.
				     Fit on yhä ensimmäinen; watchlist ei ole enää pitkän
				     vierityksen pohjalla vaan sen VIERESSÄ — 30.7:n peruste
				     ("pisin lista viimeiseksi") koski vierityksen pituutta,
				     eikä se päde kun se ei enää ole vierityksessä.
				     Planner saa koko leveyden: se sisältää taulukoita joita
				     puolikas sarake ei kanna. -->
				<div class="team-grid">
					{#if show('fit-checker')}
						<div class="tool-card" id="tc-fit">
							<FitChecker onOpenRateTeam={() => goto('/team/rate-my-team')} />
						</div>
					{/if}
					{#if show('watchlist')}
						<div class="tool-card" id="tc-watchlist"><Watchlist {premium} /></div>
					{/if}
					{#if premium && show('transfer-planner')}
						<div class="tool-card span-all" id="tc-planner"><TransferPlanner /></div>
					{/if}
				</div>
			{/if}
		</div>
	{:else if segment === 'players'}
		<div id="panel-players" role="tabpanel" aria-labelledby="seg-players">
			{#if show('player-card')}
				<div class="tool-card" id="pc-card"><PlayerCard {premium} /></div>
			{/if}
			{#if premium && (show('captain-ranker') || show('fixture-swing') || show('player-xp'))}
				{#if xpError}
					<p class="banner error">
						Could not load xP projections right now. Please try again shortly.
					</p>
				{:else if !xp}
					<p class="muted">Loading expected points…</p>
				{:else if !xp.meta?.available}
					<!-- 24.8 (GW1-STALE-COPY-2): luki "go live before Gameweek 1". Haara
					     laukeaa aina kun available=false, ei vain esikaudella. -->
					<p class="banner success">xP projections are not available for this gameweek yet.</p>
				{:else}
					{#if show('captain-ranker')}
						<div class="tool-card" id="pc-captain"><CaptainRanker data={xp} /></div>
					{/if}
					{#if show('fixture-swing')}
						<div class="tool-card" id="pc-swing"><FixtureSwing data={xp} /></div>
					{/if}
					{#if show('player-xp')}
						<div class="tool-card" id="pc-xp"><XpTable data={xp} /></div>
					{/if}
				{/if}
			{:else if show('captain-ranker') || show('fixture-swing') || show('player-xp')}
				<!-- Sama .locked-kaava kuin Predict/Fixtures-lohkoissa. -->
				<div class="locked">
					<p>
						Player xP per gameweek, the captain ranker and fixture swing are part of GoalIQ
						Premium.
					</p>
					<button type="button" class="primary" onclick={goUpgrade}>See Premium</button>
				</div>
			{/if}
			{#if show('clean-sheets')}
				<div id="pc-cs"><CleanSheets /></div>
			{/if}
			{#if show('value')}
				<div class="tool-card" id="pc-value"><Value {premium} onUpgrade={goUpgrade} /></div>
			{/if}
			{#if show('leaders')}
				<div class="tool-card" id="pc-leaders"><Leaders {premium} onUpgrade={goUpgrade} /></div>
			{/if}
			<!-- 4.9 (Villen paatos): differentials on ilmainen. Se oli jo
			     kaytannossa ilmainen — julkinen /fpl/differentials-sivu
			     rakennetaan samasta endpointista ilman kirjautumista. -->
			{#if show('differentials')}
				<div class="tool-card" id="pc-diff"><Differentials /></div>
			{/if}
			{#if premium}
				{#if xp}
					<!-- ROWAN-REPLACEMENTS (2.9): "who replaces X", luojan tilaama muoto. -->
					{#if show('replacements')}
						<div class="tool-card" id="pc-repl"><Replacements {xp} /></div>
					{/if}
					{#if show('compare')}
						<div class="tool-card" id="pc-compare"><ComparePlayers {xp} /></div>
					{/if}
				{/if}
			{/if}
		</div>
	{:else if segment === 'tools'}
		<div id="panel-tools" role="tabpanel" aria-labelledby="seg-tools">
			{#if openTool === null}
				<!-- Hakemisto renderoitiin jo navin alla (ToolDirectory). -->
			{:else}
				<a class="back-link" href="/tools">‹ All tools</a>
				{#if openTool === 'chip-timing'}
					<div class="tool-card" id="tl-chips"><ChipEv /></div>
					<div class="tool-card"><WildcardPlan /></div>
				{:else if openTool === 'transfer-chains'}
					<div class="tool-card" id="tl-chains"><PlanChains /></div>
				{:else if openTool === 'edge-mode'}
					<div class="tool-card" id="tl-edge"><EdgeMode /></div>
				{:else}
					<div class="tool-card" id="tl-league">
						<MiniLeague onUseTeam={() => goto('/team')} />
					</div>
				{/if}
			{/if}
		</div>
	{:else if segment === 'prices'}
		<div id="panel-prices" role="tabpanel" aria-labelledby="seg-prices">
			<div class="tool-card" id="pr-watch"><PriceWatch /></div>
		</div>
	{:else}
		<div id="panel-matches" role="tabpanel" aria-labelledby="seg-matches">
			<!-- Matches-alavalinta: kolme ottelutyökalua yhdessä ryhmässä
			     (Villen valinta: oma ryhmä). -->
			<!-- 4.9: alavalinta on ToolRow'ssa navin alla (linkit omiin URLeihin),
			     joten oma nappirivi poistui. Nakyma tulee reitista. -->
			{#if matchesView === 'predict'}
				<div class="tool-card" id="mt-predict">
					<Predict {premium} onUpgrade={goUpgrade} prefill={predictPrefill} />
				</div>
			{:else if matchesView === 'fixtures'}
				<div class="tool-card" id="mt-fixtures">
					<Fixtures {premium} onUpgrade={goUpgrade} onPredict={(l, h, a) => goPredict(l, h, a)} />
				</div>
			{:else}
				<div class="tool-card" id="mt-standings"><Standings /></div>
			{/if}
		</div>
	{/if}

	<!-- 4.9 YLAPINON BUDJETTI (kilpailija-auditointi): alkupera-rivi ja
	     mini-liigabanneri olivat tyokalunavin YLAPUOLELLA, eli jokainen
	     kayttaja luki myyntipuheen ennen kuin nakiv etta tyokaluja on.
	     Kumpikaan ei ole aikakriittinen: alkupera on luottamusrivi ja liiga
	     on kausipitka kutsu. Molemmat lukevat nyt tyokalujen JALKEEN, jossa
	     ne yha nakyvat samalla sivulla ilman hakua. -->
	<Provenance />
	<LeagueBanner />
{/if}

<style>
	/* 🔴 POISTA 12.9.2026 12:30 UTC jalkeen yhdessa .free-card-lohkon kanssa. */
	.free-card {
		border: 2px solid var(--accent);
		border-radius: var(--radius);
		background: var(--surface);
		padding: var(--s-3);
		margin-bottom: var(--s-4);
	}
	.free-card h2 {
		margin: 0 0 var(--s-2);
		font-size: var(--step-2);
		line-height: 1.15;
	}
	.free-card p {
		margin: 0 0 var(--s-3);
		max-width: 60ch;
	}
	.free-card-cta {
		background: var(--accent);
		border: 2px solid var(--accent);
		border-radius: var(--radius);
		color: var(--surface);
		font: inherit;
		font-weight: 700;
		padding: 12px 22px;
		cursor: pointer;
	}
	.free-card-cta:hover {
		background: transparent;
		color: var(--accent);
	}
	.back-link {
		display: inline-block;
		text-decoration: none;
		background: none;
		border: none;
		color: var(--text-muted);
		font: inherit;
		font-weight: 600;
		padding: var(--s-2) 0;
		cursor: pointer;
	}
	.back-link:hover {
		color: var(--text);
	}
	.locked {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: var(--s-4);
		margin: var(--s-4) 0;
		background: var(--surface);
	}
	.locked p {
		margin: 0 0 var(--s-3);
	}
	/* 30.7: ryhmän sisällysrivi — kevyet tekstilinkit, ei kilpaile
	   segmenttinauhan pillien kanssa */
	/* 6.8: ylätabit mukaan scrolliin — Players → My team ilman paluuta ylös */
	/* 14.8: My teamin työkalut kahteen sarakkeeseen leveillä ruuduilla.
	   `minmax(0, 1fr)` on pakollinen — ilman sitä kortin sisällä oleva
	   taulukko levittäisi sarakkeen yli gridin. `.tool-card` tuo oman
	   `margin-bottom`insa, joten rivivälin hoitaa se eikä `row-gap`
	   (muuten väli olisi kaksinkertainen). */
	.team-grid {
		display: grid;
		gap: 0;
	}
	@media (min-width: 1100px) {
		.team-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			column-gap: var(--s-5);
			align-items: start;
		}
		.team-grid > :global(.span-all) {
			grid-column: 1 / -1;
		}
	}
	.team-context {
		font-size: var(--step--1);
		color: var(--text-muted);
		margin: 0 0 var(--s-3);
	}
	.segnav-sticky {
		position: sticky;
		top: 0;
		z-index: 20;
		background: var(--bg);
	}
</style>
