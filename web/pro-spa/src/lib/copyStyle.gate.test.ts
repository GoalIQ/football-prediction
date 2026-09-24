/**
 * EM/EN DASH -PORTTI SPA:N OMASSA PORTTISARJASSA (24.9.2026).
 *
 * 23.9 SPA-muutos meni mainiin kahdesti ajamatta fp:n Python-portteja, ja
 * tests.yml oli punainen ~20 h: UCL-sivun tyhja solu `{:else}–{/if}`.
 * Saanto elaa `scripts/check_copy_style.py`:ssa, mutta SPA:ta muokatessa
 * ajetaan vitest (ja pro-spa-deploy ajaa vain sen), ei pytestia.
 *
 * Portti ei kopioi saantoa TypeScriptiin: se ajaa saman skriptin
 * `--spa`-tilassa (vain stdlib, ei api.mainin importtia). Yksi toteutus,
 * ei kahta jotka ajautuvat erilleen. Ilman Pythonia portti kaatuu
 * (fail-closed): hiljainen ohitus tekisi siita vihrean syysta.
 */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const REPO = fileURLToPath(new URL('../../../../', import.meta.url));
const SKRIPTI = 'scripts/check_copy_style.py';

function aja(): { koodi: number | null; tuloste: string } {
	const ehdokkaat =
		process.platform === 'win32' ? ['python', 'py', 'python3'] : ['python3', 'python'];
	for (const exe of ehdokkaat) {
		const r = spawnSync(exe, [SKRIPTI, '--spa'], { cwd: REPO, encoding: 'utf-8' });
		// ENOENT = ei asennettu; 9009 = Windowsin kaupan python-tynka.
		if (r.error || r.status === 9009) continue;
		return { koodi: r.status, tuloste: `${r.stdout ?? ''}${r.stderr ?? ''}` };
	}
	return { koodi: null, tuloste: `Pythonia ei loytynyt (${ehdokkaat.join(', ')})` };
}

describe('copy style: em/en dash SPA:n nakyvassa tekstissa', () => {
	it('check_copy_style.py --spa on vihrea', () => {
		const { koodi, tuloste } = aja();
		expect(koodi, tuloste).toBe(0);
		expect(tuloste).toMatch(/--spa OK/);
	});
});
