import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

/* RATE-TEAM-FREEHIT-PALAUTUS (julkaisutarkistaja k2, B4, 25.9.2026).
   Planneri ja ketjut suunnittelevat FH:ta edeltavasta rungosta, joten
   "This plan starts from your GW{gw} squad" on palautuksessa epatosi. Portti:
   molemmat pinnat haarautuvat meta.squad_source.freehit_reverted_from-kentan
   mukaan ENNEN tavallista riviä. */
for (const name of ['TransferPlanner', 'PlanChains']) {
	describe(`${name}: Free Hit -palautuksen stale-rivi`, () => {
		const src = readFileSync(new URL(`./components/${name}.svelte`, import.meta.url), 'utf-8');
		it('FH-haara ennen tavallista riviä', () => {
			const fh = src.indexOf("{#if typeof data.meta.squad_source?.freehit_reverted_from === 'number'}");
			const plain = src.indexOf('This plan starts from your GW{data.meta.squad_source?.gw} squad.');
			expect(fh).toBeGreaterThan(-1);
			expect(plain).toBeGreaterThan(fh);
			expect(src.slice(fh, plain)).toContain('{:else}');
		});
	});
}
