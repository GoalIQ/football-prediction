import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { GAME_VIEWS } from './src/lib/tools';

/** RSL- ja UCL-sivujen nakymat ovat hasheja (/spl#captain), eivat ankkureita:
 *  sivu lukee hashin `gameView`illa eika sivulla ole id="captain"-elementtia
 *  (se vierittaisi selaimen keskelle sivua). Prerender kaatui tahan 23.9
 *  ensimmaisessa pro-spa-deployssa. Poikkeus koskee VAIN naita hasheja naille
 *  poluille, ja ne luetaan samasta rekisterista kuin sivut; muualla puuttuva
 *  ankkuri kaataa buildin kuten ennenkin (portti uclViews.gate.test.ts). */
const GAME_VIEW_HASHES: Record<string, Set<string>> = Object.fromEntries(
	Object.entries(GAME_VIEWS).map(([game, def]) => [
		`/${game}`,
		new Set(def.sections.flatMap((s) => s.views as string[]))
	])
);

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Staattinen export Cloudflare Pagesille (QUEUE #14 lukittu
			// arkkitehtuuri): prerender + SPA-fallback, ei palvelinruntimea.
			adapter: adapter({ fallback: 'index.html' }),

			prerender: {
				handleMissingId: ({ path, id, message }) => {
					if (GAME_VIEW_HASHES[path]?.has(id)) return;
					throw new Error(message);
				}
			},

			// 30.7.2026 P0-insidentti: deploy-ikkunassa chunk-URL sai origin-
			// fallbackin (index.html) ja zone-edge cachetti sen IMMUTABLE-
			// headerilla → polku jäi pysyvästi rikki (musta sivu). appDir-
			// vaihto uudelleennimeää KAIKKI asset-polut → jokainen myrkytetty
			// edge-merkintä ohitetaan kerralla. Ei muuteta takaisin '_app':iin
			// ilman zone-purgea.
			//
			// 4.8.2026: KOLMAS kerta (_app2 → _app3). Oire oli taas sama:
			// jokainen assetti servautui domainilta curlille oikeana JS:nä
			// (chunks 8/8, nodes 5/5, entry 2/2), selaimen fetch() sai ne
			// oikein, mutta import() kaatui — ja TÄSMÄLLEEN SAMA BUILD
			// hydratoitui pages.dev-originista virheettä. Erotustesti siis
			// osoittaa zone-tasolle, ei buildiin.
			//
			// 🔴 TÄMÄ ON KIERTOTIE EIKÄ KORJAUS. Kolme osumaa kolmessa
			// viikossa tarkoittaa ettei juurisyytä ole löydetty; appDir-
			// numeron kasvattaminen jokaisella kerralla ei skaalaa. Seuraava
			// askel on zone-purge + syy selvitettävä CF-dashboardista
			// (Villen pääsy — wrangler-tokenissa vain zone:read). Juurisyyn jatkotoimi: deploy-verify VAIN
			// pages.dev-deployment-URL:sta kunnes propagaatio valmis (ks.
			// muisti pro-spa-wrangler-deploy).
			//
			// 6.8.2026: NELJÄS kerta (_app3 → _app4). Kaksi deployta ~40 min
			// välein Villen selatessa sivua aktiivisesti → sama oire (index ei
			// toimi, eri selaimellakaan; headless tältä koneelta hydratoituu →
			// POP-kohtainen myrkky). Lisäoppi: EI deployta kun käyttäjä on
			// sivulla, ja zone-purge-juurisyyselvitys nousee taas jonoon.
			appDir: '_app4'
		})
	]
});
