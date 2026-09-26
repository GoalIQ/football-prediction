<script lang="ts">
	// #50: mallin alkuperä-rivi FPL-työkalualueen yläreunassa (free + pro).
	//
	// 26.9 (PROVENANCE-SEURAMALLI-609, julkaisutarkistajan versio B): EI lukua.
	// Vanha lause antoi blended-luvun (49 % / 609), jossa oli 56 maajoukkuemallin
	// MM-ennustetta, vaikka lause vaittaa "the same match model". Seuramallin oma
	// luku (by_model.club, 48.1 % / 553) ei viela nay linkin takana, joten luku
	// palaa vasta kun /predictions nayttaa sen samasta lahteesta (jonorivi
	// PROVENANCE-LUKU-SIVULLE). Portti: tests/test_accuracy_by_model.py.
</script>

<!-- Tarkistusreitti: /predictions#record listaa jokaisen liigan omalla
     rivillaan (MM erikseen). -->
<p class="provenance">
	Powered by the same match model behind our published, pre-match-logged club predictions.
	<a href="https://goaliq.app/predictions#record">Track record</a>
</p>

<style>
	.provenance {
		font-size: var(--step--1);
		color: var(--text-muted);
		margin: var(--s-3) 0 0;
	}
</style>
