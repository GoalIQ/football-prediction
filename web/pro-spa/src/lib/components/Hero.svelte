<script lang="ts">
	/**
	 * Hero = sovelluksen YLAPALKKI (11.9.2026, PRO-SPA-PALETTI vaihe 1).
	 *
	 * Ennen 11.9 sivun ylalaidassa oli seitseman rivia ennen sisaltoa:
	 * GW-palkki (WorkspaceBar), logo + tagline, comp-kiitos, Set password,
	 * DefCon-rivi, kuusi valilehtea ja alatabit. My teamissa kentta alkoi
	 * ~1000 px:n kohdalla; FPL Demonilla 125 px:ssa. Mitattu PostHogista:
	 * 207 kavijaa / 30 vrk, 13 avasi toisen reitin.
	 *
	 * Nyt yksi 52 px:n palkki kantaa kaiken: merkki, navi (rekisterin
	 * GROUPS), kierros + deadline + tuoreusleima, tili. Tagline, kiitos ja
	 * salasana ovat Account-valikossa, DefCon This week -sivulla.
	 *
	 * Tiedoston nimi sailyy (Hero), jotta AppShell ja portit
	 * (`tests/test_spa_top_stack_budget.py`) eivat muutu turhaan.
	 */
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { auth, sendPasswordReset, signOut, freePremiumWindowActive } from '$lib/auth.svelte';
	import { capture } from '$lib/analytics';
	import { fetchFantasy, openCustomerPortal } from '$lib/api';
	import { actionableGameweek } from '$lib/gameweek';
	import { GROUPS } from '$lib/tools';
	import SetPassword from './SetPassword.svelte';

	let { onUpgrade }: { onUpgrade?: () => void } = $props();

	/* ---------------- navi ---------------- */
	const activeGroup = $derived(page.params.group ?? 'week');

	/* ---------------- kierros + deadline (ent. WorkspaceBar) ----------------
	   🔴 AIKA RENDEROIDAAN SELAIMEN VYOHYKKEELLA, EI PALVELIMEN. Deadline tulee
	   UTC:na; `toLocaleString` ilman timeZone-parametria kayttaa kayttajan omaa
	   vyohyketta. Kieli on lukittu en-GB (suomalaisella koneella rivi
	   renderoitui muuten "pe 21.8. klo 20.30" englanninkielisessa tuotteessa). */
	let gw = $state<number | null>(null);
	let deadline = $state<Date | null>(null);
	let checked = $state<Date | null>(null);
	let now = $state(0);
	async function refresh() {
		try {
			const d = await fetchFantasy();
			const m = d?.meta ?? {};
			gw = actionableGameweek(m) ?? null;
			if (m.deadline_utc) {
				const t = new Date(m.deadline_utc);
				if (!isNaN(t.getTime())) deadline = t;
			}
			if (m.generated_at) {
				// generated_at tulee ilman vyohyketta: se on UTC.
				const raw = /[Z+]|-\d\d:\d\d$/.test(m.generated_at) ? m.generated_at : `${m.generated_at}Z`;
				const t = new Date(raw);
				if (!isNaN(t.getTime())) checked = t;
			}
		} catch {
			// Palkin kierrosrivi on lisatietoa, ei nakyma.
		}
	}
	onMount(() => {
		void refresh();
		now = Date.now();
		const id = setInterval(() => {
			const prev = now;
			now = Date.now();
			if (deadline && prev < deadline.getTime() && now >= deadline.getTime()) void refresh();
		}, 60000);
		return () => clearInterval(id);
	});
	const LOC = 'en-GB';
	const dl = $derived(
		deadline
			? deadline.toLocaleString(LOC, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
			: null
	);
	const tz = $derived(
		deadline
			? (new Intl.DateTimeFormat(LOC, { timeZoneName: 'short' })
					.formatToParts(deadline)
					.find((p) => p.type === 'timeZoneName')?.value ?? '')
			: ''
	);
	/* 🔴 Portti 11.9: pelkka kellonaika on paivaton tuoreusvaite. Eilinen
	   artefakti luki "checked 16:07" ja lukija luki sen tamanpaivaisena.
	   Paiva sanotaan aaneen aina kun se ei ole tama paiva. */
	const chk = $derived.by(() => {
		if (!checked || now === 0) return null;
		const t = checked.toLocaleTimeString(LOC, { hour: '2-digit', minute: '2-digit' });
		if (checked.toDateString() === new Date(now).toDateString()) return `${t} today`;
		return `${checked.toLocaleDateString(LOC, { day: 'numeric', month: 'short' })}, ${t}`;
	});
	/* 🔴 Portti 11.9: `Date.now()` ei ole reaktiivinen, joten auki jaaneessa
	   valilehdessa luki "deadline" viela deadlinen jalkeenkin. Kello tikittaa
	   omana tilanaan, ja deadlinen ylitys hakee kierroksen uudelleen: pelkka
	   sanan vaihto jattaisi GW-numeron vanhaksi. */
	const mennyt = $derived(!!deadline && now > 0 && deadline.getTime() < now);

	/* ---------------- tili ---------------- */
	function pricing() {
		capture('pricing_tapped', { source: 'pro_header' });
		onUpgrade?.();
	}
	function signIn() {
		capture('sign_in_tapped', { source: 'pro_header' });
		onUpgrade?.();
	}
	let menuOpen = $state(false);
	let portalBusy = $state(false);
	let portalNotice = $state<string | null>(null);
	const webSub = $derived(
		!!auth.sub && auth.sub.plan !== 'gw1-3-free' && auth.sub.plan !== 'app' && auth.sub.plan !== 'comp'
	);
	async function manageSubscription() {
		if (portalBusy) return;
		portalBusy = true;
		portalNotice = null;
		try {
			capture('manage_subscription_opened');
			const url = await openCustomerPortal(`https://pro.goaliq.app${location.pathname}`);
			location.assign(url);
		} catch (e) {
			portalNotice = e instanceof Error ? e.message : 'Could not open the subscription page.';
		} finally {
			portalBusy = false;
		}
	}
	let resetNotice = $state<string | null>(null);
	let resetBusy = $state(false);
	let sessionEl = $state<HTMLElement | null>(null);
	function closeOnOutside(e: PointerEvent) {
		if (menuOpen && sessionEl && !sessionEl.contains(e.target as Node)) menuOpen = false;
	}
	function closeOnEscape(e: KeyboardEvent) {
		if (menuOpen && e.key === 'Escape') menuOpen = false;
	}
	$effect(() => {
		if (!auth.user) {
			menuOpen = false;
			resetNotice = null;
		}
	});
	$effect(() => {
		if (auth.passwordRecovery && auth.user) menuOpen = true;
	});
	function upgrade() {
		capture('upgrade_tapped', { source: 'header_badge' });
		onUpgrade?.();
	}
	async function resetLink() {
		const email = auth.user?.email;
		if (!email || resetBusy) return;
		resetBusy = true;
		const err = await sendPasswordReset(email);
		resetNotice = err
			? `Could not send the link: ${err}`
			: 'Password reset link sent. Check your email (and spam).';
		resetBusy = false;
	}
	const planLabel = $derived(
		auth.sub?.plan === 'gw1-3-free'
			// 12.9.2026: leima oli ainoa ilmaisikkunan lupaus SPA:ssa jota mikaan
			// ei vartioinut ajassa. Ikkunan sulkeuduttua se olisi lukenut
			// "Premium, free until 12 September" 12. syyskuuta jalkeen.
			? (freePremiumWindowActive() ? 'Premium, free until 12 September' : 'Premium')
			: auth.sub
				? 'Premium'
				: auth.sub === null
					? 'Free'
					: 'checking…'
	);
</script>

<header class="bar">
	<div class="bar-in">
		<a class="brand" href="/" aria-label="GoalIQ Premium, home">
			<svg class="mark" width="28" height="28" viewBox="0 0 44 44" role="img" aria-hidden="true">
				<rect x="0" y="0" width="44" height="44" fill="#F5C542" />
				<text x="22" y="30" text-anchor="middle" font-family="IBM Plex Mono,ui-monospace,Consolas,monospace" font-size="20" font-weight="700" letter-spacing="-0.5" fill="#0B0A09">IQ</text>
			</svg>
			<span class="word">Goal<span>IQ</span></span>
		</a>

		<nav class="nav" aria-label="GoalIQ">
			{#each GROUPS as g (g.id)}
				<a href="/{g.id}" class:active={activeGroup === g.id} aria-current={activeGroup === g.id ? 'page' : undefined}>{g.label}</a>
			{/each}
			<!-- 🔴 Villen havainto 11.9: prolta puuttui paluu goaliq.appiin. Se oli
			     ennen ylapalkin taglinessa, ja kun tagline siirtyi Account-valikkoon,
			     linkki katosi kirjautumattomalta kokonaan - eli juuri silta jolla se
			     on ainoa reitti takaisin ilmaispinnalle. Se on navin viimeisena, ei
			     brandin vieressa: kapealla ruudulla navirivi rullaa vaakaan eika
			     tungeta merkkia ja tilinappeja ahtaammalle. -->
			<a class="home" href="https://goaliq.app" data-cta="pro-home">goaliq.app</a>
		</nav>

		{#if gw !== null || dl}
			<div class="gw">
				{#if gw !== null}<b>GW{gw}</b>{/if}
				{#if dl}
					<span class="gw-lbl">{mennyt ? 'passed' : 'deadline'}</span>
					<span class="gw-val">{dl}{tz ? ` ${tz}` : ''}</span>
				{/if}
				<!-- Portti 11.9: tuoreusleima oli vain hover-tekstissa ja kirjautuneen
				     valikossa. Se on se luku jolla tuote myydaan, joten se lukee nakyvissa. -->
				{#if chk}<span class="gw-chk">checked {chk}</span>{/if}
			</div>
		{/if}

		{#if auth.sessionResolved && !auth.user}
			<div class="session">
				<button class="ghost sm" onclick={pricing}>Pricing</button>
				<button class="primary sm" onclick={signIn}>Sign in</button>
			</div>
		{:else if auth.user}
			<div class="session" bind:this={sessionEl}>
				{#if auth.sub?.plan === 'gw1-3-free'}
					<button class="plan premium" onclick={upgrade}>Premium · free</button>
				{:else if auth.sub}
					<span class="plan premium">Premium</span>
				{:else if auth.sub === null}
					<button class="plan free" onclick={upgrade}>Free · Upgrade</button>
				{/if}
				<button
					class="ghost sm"
					aria-expanded={menuOpen}
					aria-haspopup="true"
					onclick={() => (menuOpen = !menuOpen)}
				>
					Account
				</button>
				{#if menuOpen}
					<div class="menu" role="dialog" aria-label="Account">
						<div class="menu-email">{auth.user.email}</div>
						<div class="menu-plan">
							Plan: {planLabel}
							{#if auth.sub === null || auth.sub?.plan === 'gw1-3-free'}
								· <button type="button" class="linklike" onclick={upgrade}>Upgrade</button>
							{/if}
						</div>
						{#if auth.sub?.plan === 'comp'}
							<p class="menu-notice">Premium on this account was granted directly, so there is no subscription to cancel. Thank you for the support.</p>
						{/if}
						{#if webSub}
							<button type="button" class="linklike" disabled={portalBusy} onclick={() => void manageSubscription()}>
								{portalBusy ? 'Opening…' : 'Manage subscription'}
							</button>
							<p class="menu-notice">Opens the Stripe billing page for this account: cancel, change card, invoices.</p>
						{:else if auth.sub?.plan === 'app'}
							<p class="menu-notice">Your subscription is billed by the App Store or Google Play. Cancel it in your phone's subscription settings.</p>
						{/if}
						{#if portalNotice}
							<p class="menu-notice">{portalNotice}</p>
						{/if}
						{#if auth.passwordRecovery}
							<p class="banner success">Password reset link accepted. Set your new password below.</p>
						{/if}
						<SetPassword
							summary="Set or change password (works for the GoalIQ iOS and Android apps too)"
							open={auth.passwordRecovery}
						/>
						<button type="button" class="linklike" disabled={resetBusy} onclick={() => void resetLink()}>
							Forgot it? Email me a password reset link
						</button>
						{#if resetNotice}
							<p class="menu-notice">{resetNotice}</p>
						{/if}
						<!-- Portti 11.9: entinen tagline listasi kolme asiaa joita navi ei vastaa,
						     ja "a real match model" oli vaite ilman reittia tasta kohdasta. Rivi
						     osoittaa nyt paikkaan jossa vaitteen voi tarkistaa ilman tilia. -->
						<p class="menu-notice"><a href="https://goaliq.app">goaliq.app</a> · The same model that logs its predictions in public.</p>
						<button class="ghost menu-signout" onclick={() => void signOut()}>Sign out</button>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</header>

<svelte:window onpointerdown={closeOnOutside} onkeydown={closeOnEscape} />

<style>
	.bar {
		position: sticky;
		top: 0;
		z-index: 30;
		height: var(--bar-h);
		background: var(--bg);
		border-bottom: 1px solid var(--border);
	}
	.bar-in {
		max-width: var(--shell);
		margin: 0 auto;
		height: 100%;
		padding: 0 var(--s-4);
		display: flex;
		align-items: center;
		gap: var(--s-4);
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: var(--s-2);
		color: var(--text);
		text-decoration: none;
		flex: 0 0 auto;
	}
	.brand:hover {
		text-decoration: none;
	}
	.mark {
		display: block;
	}
	.word {
		font-family: var(--font-display);
		font-size: 18px;
		font-weight: 700;
		letter-spacing: -0.02em;
		line-height: 1;
	}
	.word span {
		color: var(--accent);
	}

	.nav {
		display: flex;
		align-items: stretch;
		gap: 2px;
		height: 100%;
		min-width: 0;
		overflow-x: auto;
		scrollbar-width: none;
	}
	.nav::-webkit-scrollbar {
		display: none;
	}
	.nav a {
		display: inline-flex;
		align-items: center;
		padding: 0 var(--s-3);
		color: var(--text-muted);
		font-size: 14px;
		font-weight: 600;
		white-space: nowrap;
		text-decoration: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
	}
	.nav a:hover {
		color: var(--text);
		text-decoration: none;
	}
	.nav a.active {
		color: var(--text);
		border-bottom-color: var(--accent);
	}
	/* Paluu ilmaispinnalle: samassa rivissa mutta ei tyokaluryhma. Mono ja
	   hiusviiva erottavat sen ryhmista ilman omaa varia. */
	.nav a.home {
		font-family: var(--font-mono);
		font-size: 12px;
		color: var(--faint);
		border-left: 1px solid var(--border);
		margin-left: var(--s-2);
		padding-left: var(--s-3);
	}
	.nav a.home:hover {
		color: var(--giq-teal);
	}
	/* 🔴 Mitattu 390 px: navirivi rullaa vaakaan, joten viimeisena oleva
	   paluulinkki jai ruudun ulkopuolelle - eli se oli olemassa muttei
	   loydettavissa juuri silla pinnalla jolla 60 % kavijoista on. Kapealla
	   ruudulla se on rivin ENSIMMAINEN, kuten paluulinkki yleensa. */
	@media (max-width: 820px) {
		.nav a.home {
			order: -1;
			margin-left: 0;
			padding-left: var(--s-3);
			border-left: 0;
			border-right: 1px solid var(--border);
			margin-right: var(--s-1);
			padding-right: var(--s-3);
		}
	}

	.gw {
		margin-left: auto;
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		font-family: var(--font-mono);
		font-size: 12px;
		letter-spacing: 0.02em;
		white-space: nowrap;
		color: var(--text-muted);
	}
	.gw b {
		color: var(--text);
	}
	.gw-lbl {
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-size: 10.5px;
	}
	.gw-val {
		color: var(--accent);
		font-weight: 600;
	}
	.gw-chk {
		color: var(--faint);
	}

	.session {
		display: flex;
		align-items: center;
		gap: var(--s-2);
		position: relative;
		flex: 0 0 auto;
	}
	button.sm {
		min-height: 34px;
		padding: 0.3em 0.9em;
		font-size: 13px;
	}
	.plan {
		font-family: var(--font-mono);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		line-height: 1.6;
		padding: 2px 9px;
		white-space: nowrap;
		min-height: 0;
	}
	.plan.premium {
		background: transparent;
		border: 1px solid var(--accent);
		color: var(--accent-strong);
	}
	.plan.free {
		background: none;
		border: 1px solid var(--border-strong);
		color: var(--text-muted);
		cursor: pointer;
	}
	.plan.free:hover {
		color: var(--text);
		border-color: var(--accent);
	}

	.menu {
		--text: var(--giq-cream);
		--text-muted: var(--giq-muted);
		--border: rgba(243, 242, 242, 0.24);
		position: absolute;
		top: calc(100% + 10px);
		right: 0;
		z-index: 40;
		min-width: 300px;
		max-width: min(92vw, 380px);
		background: var(--giq-paper);
		color: var(--text);
		border: 1px solid var(--border);
		padding: var(--s-4);
		display: grid;
		gap: var(--s-2);
		text-align: left;
	}
	.menu-email {
		font-weight: 700;
		overflow-wrap: anywhere;
	}
	.menu-plan,
	.menu-notice {
		margin: 0;
		color: var(--text-muted);
		font-size: var(--step--1);
	}
	.linklike {
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		color: var(--giq-rust);
		font-size: var(--step--1);
		font-weight: 700;
		text-decoration: underline;
		cursor: pointer;
		min-height: 0;
		justify-self: start;
		text-align: left;
	}
	.menu-signout {
		justify-self: start;
		color: var(--text-muted);
		border-color: var(--border);
	}

	/* Kapea ruutu: navi omalle riville palkin alle, jotta viisi kohtaa
	   pysyvat sormen kokoisina. Kierrosrivi jaa pois (se on Account-
	   valikossa ja This week -sivulla). */
	@media (max-width: 820px) {
		.bar {
			height: auto;
			/* 🔴 Kapealla ruudulla palkki on kaksirivinen (~92 px). Sticky se
			   soisi 11 % 844 px:n ruudusta pysyvasti JA peittaisi taulukoiden
			   sticky-otsikkorivin, joka tarttuu --bar-h:hon. Navi on sivun
			   ylalaidassa, joten se loytyy vierittamalla ylos. */
			position: static;
		}
		.bar-in {
			flex-wrap: wrap;
			gap: var(--s-2) var(--s-3);
			padding: 8px var(--s-3) 0;
		}
		.brand {
			order: 0;
		}
		.session {
			order: 1;
			margin-left: auto;
		}
		.gw {
			display: none;
		}
		.nav {
			order: 2;
			flex-basis: 100%;
			height: 40px;
			margin: 0 calc(-1 * var(--s-3));
			padding: 0 var(--s-2);
		}
		.nav a {
			padding: 0 var(--s-3);
			font-size: 14px;
		}
	}
</style>
