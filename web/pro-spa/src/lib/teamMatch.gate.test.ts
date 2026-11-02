/** Portti: Fixtures -> Predict -esitaytto ja Fixtures-rivin prosentti
 * sovittavat joukkuenimet YHDELLA sovittimella (ulkoasu WP10, 2.11.2026).
 *
 * 🔴 MIKSI. Mallin joukkuelista vaihtui lyhyisiin football-data.co.uk-nimiin
 * ("Nott'm Forest", "Man City"). Predict.svelten oma sovitin purki aliaksen
 * vain kysyttyyn nimeen, joten tuotannossa 2.11 Forestin otteluiden Predict-
 * nappi tyhjensi kentat ("Nottingham" ei osu "Nott'm Forest"iin), samoin
 * Brasilian Vitoria, Mineiro ja Paranaense: PL 36/40 ja BSA 36/51 rivia
 * taytti Predictin. Sovelluksessa sama luokka toi kaksi vikaa perakkain
 * (goaliq-app 462540c7 nappi, b8695417 palkki).
 *
 * Mekanismit (CLAUDE.md 6a): (1) yksi sovitin `$lib/teamMatch`, (2)
 * kutsupaikkaportti: Predict.svelte ei maarittele omaa sovitinta, (3) syotteet
 * ovat tuotannosta mitattuja nimia (2.11.2026 /api/fixtures, /api/teams,
 * /api/accuracy?include=pending), ei keksittyja.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { matchTeam, teamKey } from './teamMatch';

// GET /api/teams?leagues=ENG-Premier League, 2.11.2026 (malli).
const PL_MODEL = [
	'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton', 'Chelsea', 'Coventry',
	'Crystal Palace', 'Everton', 'Fulham', 'Hull', 'Ipswich', 'Leeds', 'Liverpool', 'Man City',
	'Man United', 'Newcastle', "Nott'm Forest", 'Sunderland', 'Tottenham', 'Wolves'
];
// Ennustelokin nimet (pending_predictions, competition PL), 2.11.2026.
const PL_LOG = [
	'Arsenal', 'Aston Villa', 'Bournemouth', 'Brentford', 'Brighton', 'Chelsea', 'Coventry',
	'Crystal Palace', 'Everton', 'Fulham', 'Hull', 'Ipswich', 'Leeds', 'Liverpool',
	'Manchester City', 'Manchester United', 'Newcastle United', 'Nottingham Forest', 'Sunderland',
	'Tottenham'
];
// GET /api/teams?leagues=BRA-Serie A, 2.11.2026.
const BSA_MODEL = [
	'Athletico-PR', 'Atletico-MG', 'Bahia', 'Botafogo RJ', 'Bragantino', 'Ceara', 'Chapecoense-SC',
	'Corinthians', 'Coritiba', 'Cruzeiro', 'Flamengo RJ', 'Fluminense', 'Fortaleza', 'Gremio',
	'Internacional', 'Juventude', 'Mirassol', 'Palmeiras', 'Remo', 'Santos', 'Sao Paulo',
	'Sport Recife', 'Vasco', 'Vitoria'
];

describe('teamMatch: tuotannon nimet osuvat oikeaan joukkueeseen', () => {
	// [otteluohjelman lyhyt nimi, odotettu mallin nimi, odotettu lokin nimi]
	it.each([
		['Nottingham', "Nott'm Forest", 'Nottingham Forest'],
		['Man City', 'Man City', 'Manchester City'],
		['Man United', 'Man United', 'Manchester United'],
		['Newcastle', 'Newcastle', 'Newcastle United'],
		['Brighton Hove', 'Brighton', 'Brighton'],
		['Coventry City', 'Coventry', 'Coventry'],
		['Hull City', 'Hull', 'Hull'],
		['Ipswich Town', 'Ipswich', 'Ipswich'],
		['Leeds United', 'Leeds', 'Leeds'],
		['Tottenham', 'Tottenham', 'Tottenham']
	])('PL %s', (fixture, model, log) => {
		expect(matchTeam(fixture, PL_MODEL)).toBe(model);
		expect(matchTeam(fixture, PL_LOG)).toBe(log);
	});

	it('PL: otteluohjelman pitka nimi osuu lokiin (varapolku)', () => {
		expect(matchTeam('Newcastle United FC', PL_LOG)).toBe('Newcastle United');
		expect(matchTeam('Nottingham Forest FC', PL_LOG)).toBe('Nottingham Forest');
		expect(matchTeam('Manchester City FC', PL_LOG)).toBe('Manchester City');
		expect(matchTeam('Brighton & Hove Albion FC', PL_LOG)).toBe('Brighton');
	});

	it.each([
		['Mineiro', 'Atletico-MG'],
		['Paranaense', 'Athletico-PR'],
		['Vitória', 'Vitoria'],
		['Vasco da Gama', 'Vasco'],
		['São Paulo', 'Sao Paulo'],
		['Clube do Remo', 'Remo']
	])('BSA %s', (fixture, model) => {
		expect(matchTeam(fixture, BSA_MODEL)).toBe(model);
	});

	it('alias puretaan molemmista nimista (kysyja ja lista samaan avaimeen)', () => {
		expect(teamKey('Nottingham')).toBe(teamKey("Nott'm Forest"));
		expect(teamKey('Nottingham')).toBe(teamKey('Nottingham Forest'));
		expect(teamKey('Man City')).toBe(teamKey('Manchester City'));
		expect(teamKey('Man United')).toBe(teamKey('Manchester United'));
	});
});

describe('teamMatch: vaara joukkue on pahempi kuin puuttuva', () => {
	it('Man City ei koskaan osu Man Unitediin eika painvastoin', () => {
		expect(matchTeam('Man City', ['Manchester United'])).toBeNull();
		expect(matchTeam('Man United', ['Manchester City'])).toBeNull();
		expect(matchTeam('Manchester', PL_LOG)).toBeNull();
	});

	it('moniselitteinen substring -> null', () => {
		expect(matchTeam('Atletico', ['Atletico Madrid', 'Atletico-MG'])).toBeNull();
		expect(matchTeam('Manchester', ['Manchester City', 'Manchester United'])).toBeNull();
	});

	it('lyhyt avain ei saa substring-osumaa', () => {
		expect(matchTeam('Ars', PL_MODEL)).toBeNull();
		expect(matchTeam('', PL_MODEL)).toBeNull();
	});

	it('tuntematon joukkue -> null', () => {
		expect(matchTeam('Real Madrid', PL_MODEL)).toBeNull();
	});
});

describe('KUTSUPAIKKA: Predict kayttaa jaettua sovitinta', () => {
	const src = readFileSync(resolve(__dirname, 'components/Predict.svelte'), 'utf8');
	it('tuo matchTeamin $lib/teamMatchista', () => {
		expect(src).toMatch(/import \{ matchTeam \} from '\$lib\/teamMatch';/);
		expect(src).toMatch(/matchTeam\(p\.home, pool\)/);
		expect(src).toMatch(/matchTeam\(p\.away, pool\)/);
	});
	it('ei maarittele omaa sovitinta tai aliaslistaa', () => {
		expect(src).not.toMatch(/function matchTeam\b/);
		expect(src).not.toMatch(/NAME_ALIASES/);
		expect(src).not.toMatch(/function norm\b/);
	});
});
