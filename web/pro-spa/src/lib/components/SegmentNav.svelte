<script lang="ts" module>
	// #48: jaettu segmenttinavigaatio FPL-työkaluille (free + pro pinnat).
	// 4.9.2026: segmentit ovat nyt REITTEJA eivat hash-tilaa, joten napit ovat
	// linkkeja. Kaytannon ero kayttajalle: paluunappi toimii, segmentin voi
	// avata uuteen valilehteen ja jokaisella on oma otsikko. Ks. `$lib/tools`.
	export type Segment = { id: string; label: string; href: string };
</script>

<script lang="ts">
	let {
		segments,
		active,
		label = 'FPL tools'
	}: { segments: Segment[]; active: string; label?: string } = $props();

	let tabEls: HTMLAnchorElement[] = [];

	function onKeydown(e: KeyboardEvent, i: number) {
		const last = segments.length - 1;
		let next: number | null = null;
		if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = i === last ? 0 : i + 1;
		else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = i === 0 ? last : i - 1;
		else if (e.key === 'Home') next = 0;
		else if (e.key === 'End') next = last;
		if (next == null) return;
		e.preventDefault();
		// Fokus siirtyy, valinta tapahtuu Enterilla/valilyonnilla kuten
		// linkeilla yleensa — nuolinaviagointi ei enaa vaihda sivua vahingossa.
		tabEls[next]?.focus();
	}
</script>

<div class="seg-nav" role="tablist" aria-label={label}>
	{#each segments as s, i (s.id)}
		<a
			bind:this={tabEls[i]}
			id="seg-{s.id}"
			href={s.href}
			role="tab"
			aria-selected={active === s.id}
			aria-controls="panel-{s.id}"
			tabindex={active === s.id ? 0 : -1}
			class:active={active === s.id}
			onkeydown={(e) => onKeydown(e, i)}
		>
			{s.label}
		</a>
	{/each}
</div>

<style>
	.seg-nav {
		display: flex;
		flex-wrap: wrap;
		gap: var(--s-2);
		margin: var(--s-4) 0 var(--s-4);
	}
	.seg-nav a {
		display: inline-flex;
		align-items: center;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		color: var(--text-muted);
		font-size: var(--step--1);
		font-weight: 700;
		padding: 0.5em 1.2em;
		min-height: 44px;
		text-decoration: none;
	}
	.seg-nav a:hover {
		color: var(--text);
		border-color: var(--text-muted);
	}
	/* 26.7 classic: aktiivinen segmentti = kulta-outline, ei täyttöä */
	.seg-nav a.active {
		background: transparent;
		border-color: var(--accent);
		color: var(--accent-strong);
	}
	.seg-nav a.active:hover {
		background: rgba(245, 197, 66, 0.08);
		border-color: var(--accent-strong);
	}
</style>
