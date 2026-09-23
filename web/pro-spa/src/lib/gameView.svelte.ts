/**
 * Muiden pelien (RSL /spl, UCL /ucl) nakymatila hashista: YKSI lukija
 * molemmille sivuille (23.9, RSL-MENUT + UCL-MENUT).
 *
 * 🔴 Julkaisutarkistaja 23.9 (BLOKATTU k1): osion vaihto alapalkista
 * sailytti vierityskohdan. Hash-linkki ei osu mihinkaan id:hen, joten selain
 * ei vierita, ja Chromen scroll anchoring pitaa ruudulla sen mika siella jo
 * oli. Mitattu: Captain y=450 -> Teams hyppasi kohtaan y=4573, ja ruudulla
 * oli disclaimer, ei Teams-taulukko. FPL:ssa alapalkki vaihtaa reittia ja
 * vierittaa ylos, joten sama tehdaan tassa kun OSIO vaihtuu. Esiasetuksen
 * (chip) vaihto osion sisalla ei vierita: chipit ovat jo sivun ylaosassa.
 *
 * Kutsu komponentin alustuksessa: `const gv = gameViewState('spl',
 * 'spl_view_changed')`, ja lue `gv.view`.
 */
import { page } from '$app/state';
import { tick, untrack } from 'svelte';
import { capture } from '$lib/analytics';
import { GAME_VIEWS, gameView, sectionChanged, type GameId } from '$lib/tools';

export function gameViewState<V extends string>(game: GameId, event: string): { readonly view: V } {
	let view = $state(GAME_VIEWS[game].defaultView as V);
	let seen = false;
	$effect(() => {
		const v = gameView(game, page.url.hash) as V;
		untrack(() => {
			if (seen && v !== view) {
				capture(event, { view: v });
				if (sectionChanged(game, view, v)) void tick().then(() => window.scrollTo(0, 0));
			}
			seen = true;
			view = v;
		});
	});
	return {
		get view() {
			return view;
		}
	};
}
