/** Portti: ostonapit ovat upgrade-nakyman ENSIMMAINEN asia, ja nakymaan
 *  vieritetaan sen omaan alkuun.
 *
 * 🔴 MIKSI (22.9, web-audit K2): "See plans", ylapalkin "Pricing" ja landingin
 * "TRY PREMIUM" (99 klikkausta / 30 vrk) veivat kavijan heroon, ja ensimmainen
 * ostonappi oli 1 380-3 140 px ruudun alapuolella (mitattu 390x844 CDP).
 * Korjauksen jalkeen 227 px kaikilla neljalla polulla. Kaksi syyta, kumpikin
 * vartioidaan: vieritys osui `main`iin (jonka alussa on hero), ja
 * PremiumPreview/Paywall nayttivat ominaisuuslistan ennen hintoja.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (f: string) => readFileSync(resolve(__dirname, 'components', f), 'utf-8');
const markup = (src: string) => src.slice(src.lastIndexOf('</script>'));

describe('upgrade-nakyman jarjestys', () => {
	it('PremiumPreview: ostonapit ennen ominaisuuslistaa, esikatselua ja kauppanappia', () => {
		const m = markup(read('PremiumPreview.svelte'));
		const plans = m.indexOf('{@render planButtons');
		expect(plans).toBeGreaterThan(-1);
		for (const later of ['<ul class="bullets">', 'class="teaser"', '{#if appStore}', '<Provenance />']) {
			expect(m.indexOf(later), later).toBeGreaterThan(plans);
		}
	});

	it('Paywall: ostonapit ennen kuvauskappaleita ja teaseria', () => {
		const m = markup(read('Paywall.svelte'));
		const plans = m.indexOf('<div class="plans">');
		expect(plans).toBeGreaterThan(-1);
		expect(m.indexOf('<strong>FPL:</strong>')).toBeGreaterThan(plans);
		expect(m.indexOf('class="teaser')).toBeGreaterThan(plans);
	});

	it('ToolsHome: vieritys upgrade-nakyman omaan ankkuriin, ei mainiin', () => {
		const src = read('ToolsHome.svelte');
		expect(src).toMatch(/id=\{UPGRADE_ANCHOR\}/);
		const fn = src.slice(src.indexOf('function openUpgrade'), src.indexOf('function goUpgrade'));
		expect(fn).toContain('scrollToUpgrade(');
		expect(fn).not.toMatch(/querySelector\('main'\)\?\.scrollIntoView/);
		// ?tab=premium vierittaa samaan kohtaan
		const mount = src.slice(src.indexOf("tab === 'premium'"));
		expect(mount.slice(0, 400)).toContain('scrollToUpgrade(');
	});
});
