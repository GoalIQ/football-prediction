/**
 * LOGIN-ASETTELU (29.9.2026): ylapalkin "Sign in" vie kirjautumislaatikkoon.
 *
 * Mitattu tuoreella profiililla: "Sign in" kutsui samaa onUpgradea kuin
 * "Pricing", joten olemassa oleva kayttaja paatyi myyntisivun alkuun ja
 * LoginBox oli 2 011 px alempana (390 px) / 1 695 px (tyopoyta). Portti lukee
 * KUTSUPAIKAT (Hero -> AppShell -> ToolsHome -> LoginBox), ei yksittaista
 * funktiota: ketju katkeaa mista tahansa lenkista ja nappi palaa vanhaan.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blankComments } from './sourceScan';

const lue = (f: string) =>
	blankComments(readFileSync(fileURLToPath(new URL(`./components/${f}`, import.meta.url)), 'utf8'));

describe('Sign in -nappi vie kirjautumislaatikkoon', () => {
	const hero = lue('Hero.svelte');
	const shell = lue('AppShell.svelte');
	const home = lue('ToolsHome.svelte');
	const box = lue('LoginBox.svelte');

	it('Heron signIn kutsuu omaa signaalia, ei pelkkaa onUpgradea', () => {
		const fn = hero.slice(hero.indexOf('function signIn()'), hero.indexOf('function signIn()') + 200);
		expect(fn).toMatch(/onSignIn/);
	});

	it('AppShell kytkee signaalin Herosta ToolsHomeen', () => {
		// Rivitaso: attribuuttien nuolifunktiot sisaltavat '>'-merkin.
		const heroRivi = shell.split('\n').find((l) => l.includes('<Hero ')) ?? '';
		const homeRivi = shell.split('\n').find((l) => l.includes('<ToolsHome ')) ?? '';
		expect(heroRivi).toContain('onSignIn={() => signInSignal++}');
		expect(homeRivi).toContain('{signInSignal}');
	});

	it('ToolsHome vierittaa LoginBoxin ankkuriin, ja ankkuri on LoginBoxissa', () => {
		const m = home.match(/const SIGNIN_ANCHOR = '([^']+)'/);
		expect(m).not.toBeNull();
		expect(home).toMatch(/openUpgrade\('gate', SIGNIN_ANCHOR\)/);
		expect(box).toContain(`id="${m![1]}"`);
	});

	it('valilehdet ovat Google-napin jalkeen (ne ohjaavat vain sahkopostia)', () => {
		const google = box.indexOf('Continue with Google');
		const tabs = box.indexOf('role="tablist"');
		expect(google).toBeGreaterThan(0);
		expect(tabs).toBeGreaterThan(google);
	});
});
