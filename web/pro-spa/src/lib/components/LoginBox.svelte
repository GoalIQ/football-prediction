<script lang="ts">
	import {
		signIn,
		signUp,
		sendMagicLink,
		signInWithGoogle,
		freePremiumWindowActive
	} from '$lib/auth.svelte';
	import { GOOGLE_AUTH_ENABLED } from '$lib/config';

	// 🔴 Villen havainto 16.8: "missa ohjeistus". Tama lomake avautui aina
	// tilassa 'in' otsikolla "Already have an account?", eli ilmaisen ikkunan
	// ainoa sisaankaynti ohjasi uuden kayttajan kirjautumislomakkeelle jolle
	// hanella ei ole tunnuksia. Ikkunan ajan oletus on tilin LUONTI; sen
	// jalkeen vanha oletus on taas oikea, koska osto ei vaadi tilia.
	const windowOpen = freePremiumWindowActive();
	let mode = $state<'in' | 'up'>(windowOpen ? 'up' : 'in');
	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);
	// #101: sisäänpääsylinkki mailiin — guest-checkout-ostaja (ei salasanaa)
	// tai salasanansa unohtanut pääsee sisään ilman tukikierrosta.
	let linkNotice = $state<string | null>(null);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!email || !password) {
			error = 'Email and password required.';
			return;
		}
		busy = true;
		error = null;
		error = mode === 'in' ? await signIn(email, password) : await signUp(email, password);
		busy = false;
	}

	async function google() {
		busy = true;
		error = null;
		const err = await signInWithGoogle();
		if (err) {
			error = err;
			busy = false;
		}
		// Ei nollata busya onnistuessa: selain siirtyy Googlelle, ja napin
		// palautuminen aktiiviseksi juuri ennen navigaatiota nayttaisi silta
		// kuin klikkaus ei olisi mennyt perille.
	}

	async function emailLink() {
		if (!email) {
			error = 'Enter your email above first.';
			return;
		}
		busy = true;
		error = null;
		const err = await sendMagicLink(email);
		linkNotice = err ? null : 'Sign-in link sent. Check your email (and spam).';
		error = err;
		busy = false;
	}
</script>

<!-- #101: osto ei enää vaadi tiliä (napit PremiumPreview'ssä yllä) →
     tämä lomake palvelee OLEMASSA OLEVIA tilejä, ei portita ostoa. -->
{#if windowOpen}
	<!-- 🔴 POISTA 12.9.2026 12:30 UTC jalkeen: palauta alla oleva sign-in-otsikko. -->
	<h3>Create your free account</h3>
	<p class="muted">
		Email and a password, that is all it takes. Premium switches on straight away and stays on
		until the GW4 deadline on 12 September. No card, nothing to cancel. Already have an
		account? Use Sign in below and Premium is on there too.
	</p>
{:else}
	<h3>Already have an account? Sign in</h3>
	<p class="muted">
		Subscribed in the GoalIQ app, bought Premium here earlier, or want to use an existing
		account? Sign in and Premium is active here too.
	</p>
{/if}

<div class="modes" role="tablist" aria-label="Sign in or create account">
	<button
		class="ghost"
		class:active={mode === 'in'}
		role="tab"
		aria-selected={mode === 'in'}
		onclick={() => (mode = 'in')}>Sign in</button
	>
	<button
		class="ghost"
		class:active={mode === 'up'}
		role="tab"
		aria-selected={mode === 'up'}
		onclick={() => (mode = 'up')}>Create account</button
	>
</div>

{#if mode === 'up'}
	<p class="muted">One GoalIQ account works in the app and on the web.</p>
{/if}

{#if GOOGLE_AUTH_ENABLED}
	<!-- Googlen ENNEN lomaketta: se on nopein polku, ja lomakkeen alle
	     sijoitettuna se loytyisi vasta kun kayttaja on jo aloittanut
	     salasanan keksimisen. Logo on inline-SVG eika ladattu kuva —
	     kolmannen osapuolen kuvahost olisi uusi pyynto ja uusi
	     epaonnistumisen paikka kirjautumispolulla. -->
	<button type="button" class="oauth" disabled={busy} onclick={() => void google()}>
		<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" focusable="false">
			<path
				fill="#4285F4"
				d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
			/>
			<path
				fill="#34A853"
				d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"
			/>
			<path
				fill="#FBBC05"
				d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"
			/>
			<path
				fill="#EA4335"
				d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
			/>
		</svg>
		Continue with Google
	</button>
	<p class="or muted"><span>or use email</span></p>
{/if}

<form class="card" onsubmit={submit}>
	<label for="email">Email</label>
	<input id="email" type="email" autocomplete="email" bind:value={email} />
	<label for="password">Password{mode === 'up' ? ' (min 6 chars)' : ''}</label>
	<input
		id="password"
		type="password"
		autocomplete={mode === 'up' ? 'new-password' : 'current-password'}
		bind:value={password}
	/>
	{#if error}
		<p class="banner error">Authentication failed: {error}</p>
	{/if}
	{#if linkNotice}
		<p class="banner success">{linkNotice}</p>
	{/if}
	<button class="primary" type="submit" disabled={busy}>
		{mode === 'in' ? 'Sign in' : 'Create account'}
	</button>
	{#if mode === 'in'}
		<p class="muted link-row">
			Bought Premium without a password, or forgot it?
			<button type="button" class="linklike" disabled={busy} onclick={() => void emailLink()}>
				Email me a sign-in link
			</button>
		</p>
	{/if}
</form>

<style>
	.oauth {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6em;
		width: 100%;
		background: var(--surface-2);
		border-color: var(--border-strong);
		font-weight: 600;
	}
	.oauth:hover {
		border-color: var(--accent);
	}
	/* Erotinviiva tekstilla keskella: ilman sita Google-nappi ja lomake
	   lukevat yhtena listana vaihtoehtoja, jolloin kayttaja tayttaa
	   sahkopostin ja klikkaa sitten Googlea. */
	.or {
		display: flex;
		align-items: center;
		gap: var(--s-3);
		margin: var(--s-3) 0;
		font-size: 0.8rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
	.or::before,
	.or::after {
		content: '';
		flex: 1;
		height: 1px;
		background: var(--border);
	}

	.modes {
		display: flex;
		gap: var(--s-2);
		margin-bottom: var(--s-3);
	}
	.modes .active {
		color: var(--giq-rust);
		border-color: var(--giq-rust);
	}
	form {
		max-width: 460px;
		display: grid;
		gap: var(--s-2);
	}
	form button {
		justify-self: start;
		margin-top: var(--s-2);
	}
	.link-row {
		margin: 0;
		font-size: var(--step--1);
	}
	.linklike {
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		color: var(--giq-rust);
		font-size: inherit;
		font-weight: 700;
		text-decoration: underline;
		cursor: pointer;
		min-height: 0;
	}
</style>
