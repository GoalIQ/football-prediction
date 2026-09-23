<script lang="ts">
	/**
	 * Alapalkki puhelimessa (22.9.2026, web-audit T2 + UX-uudistus A3).
	 *
	 * 🔴 MITATTU 22.9 (390x844, tuotanto): ylapalkin navi oli 653 px leve
	 * 366 px:n tilassa. "Players", "Price watch" ja "Matches" olivat ruudun
	 * ulkopuolella ilman vihjetta ja "My team" katkesi ("My teal"). Kavija
	 * ei voinut tietaa etta tuotteessa on pelaajatyokaluja.
	 *
	 * Nyt <= 640 px:n leveydella ryhmat ovat kiintea alapalkki, kaikki neljä
	 * aina nakyvissa, samassa jarjestyksessa kuin mobiiliapin tabit. Leveammalla
	 * ruudulla sama rekisteri renderoityy ylapalkin naviksi (Hero).
	 *
	 * Kohteet tulevat rekisterista (`GROUPS`) ja kuvakkeet `NAV_ICONS`ista;
	 * portti `ia.gate.test.ts` kaataa jos ryhmalla ei ole kuvaketta tai
	 * palkki lakkaa lukemasta rekisteria.
	 */
	import { page } from '$app/state';
	import { activeNav, navItems } from '$lib/tools';
	import { NAV_ICONS } from '$lib/navIcons';

	// 23.9: kohteet pelin mukaan (FPL:n ryhmat / RSL:n osiot), ks. navItems.
	const items = $derived(navItems(page.url.pathname));
	const active = $derived(activeNav(page.url.pathname, page.url.hash));
</script>

<nav class="bottom-nav" aria-label="Sections" style="--nav-cols: {items.length}">
	{#each items as g (g.id)}
		<a
			href={g.href}
			class:active={active === g.id}
			aria-current={active === g.id ? 'page' : undefined}
			data-cta="pro-bottom-{g.id}"
		>
			<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
				<path
					d={NAV_ICONS[g.icon]}
					fill="none"
					stroke="currentColor"
					stroke-width="1.7"
					stroke-linejoin="round"
					stroke-linecap="round"
				/>
			</svg>
			<span>{g.label}</span>
		</a>
	{/each}
</nav>

<style>
	.bottom-nav {
		display: none;
	}
	@media (max-width: 640px) {
		.bottom-nav {
			position: fixed;
			left: 0;
			right: 0;
			bottom: 0;
			z-index: 35;
			display: grid;
			grid-template-columns: repeat(var(--nav-cols, 4), minmax(0, 1fr));
			height: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom, 0px));
			padding-bottom: env(safe-area-inset-bottom, 0px);
			background: var(--bg);
			border-top: 1px solid var(--border-strong);
		}
		.bottom-nav a {
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: center;
			gap: 3px;
			min-width: 0;
			/* A2 saanto 20: kosketusalue vahintaan 48 px. */
			min-height: 48px;
			color: var(--text-muted);
			font-size: 11px;
			font-weight: 600;
			letter-spacing: 0.01em;
			text-decoration: none;
			white-space: nowrap;
			border-top: 2px solid transparent;
			margin-top: -1px;
		}
		.bottom-nav a span {
			overflow: hidden;
			text-overflow: ellipsis;
			max-width: 100%;
		}
		.bottom-nav a.active {
			color: var(--text);
			border-top-color: var(--accent);
		}
		.bottom-nav a.active svg {
			color: var(--accent);
		}
	}
</style>
