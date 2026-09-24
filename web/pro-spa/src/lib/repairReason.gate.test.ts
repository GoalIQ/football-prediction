/**
 * SIIRTOSUUNNITELMA-NOLLA-XP-SELITE (24.9.2026).
 *
 * TAUSTA: `TransferPlanner.svelte` näytti kuolleen paikan siivousrivin
 * "+0.00 xP" ilman mitään syytä (mitattu entry 116920, GW7: "Dovin →
 * Lecomte +0.00 xP"). Backend kantoi jo rakenteisen syyn
 * (`fpl_transfers.repair_reason`: `status:<d|i|s|u|n>` / `chance_next:0` /
 * `no_projection:<syy>`), mutta SPA ei lukenut sitä.
 *
 * `repairReasonText` on YKSI LUKIJA koodille -> lause (sama periaate kuin
 * `noXpReason`). Nämä testit kiinnittävät jokaisen koodihaaran erikseen,
 * ja negatiivinen kontrolli varmistaa ettei tuntematon syy palaudu
 * hiljaa nollana (undefined/"") vaan joko oikeana lauseena tai `null`illa
 * jonka kutsuja osaa kasitella.
 *
 * PlanChains.svelte EI ole tässä: `api/fantasy_edge.fantasy_plan_chains`in
 * `_top_transfers` hylkää kandidaatit joilla `gain <= 0` (rivi katkeaa ennen
 * kuin nolla-hyötyinen korjaussiirto voi koskaan syntyä sillä reitillä),
 * joten sama "+0.00 xP ilman syytä" -vika ei voi ilmetä plan-chainsissa
 * nykyisellä moottorilla — mitattu lukemalla `api/fantasy_edge.py`, ei
 * oletettu.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { repairReasonText } from './availabilityFlag';

describe('repairReasonText: koodi -> lause', () => {
	it('palauttaa null kun syytä ei ole (normaali arvosiirto)', () => {
		expect(repairReasonText(null)).toBeNull();
		expect(repairReasonText(undefined)).toBeNull();
	});

	it('status-koodit kartalla, tuntematonkin status kertoo raa an arvon', () => {
		expect(repairReasonText('status:u')).toBe(
			'FPL lists this player as no longer in the league'
		);
		expect(repairReasonText('status:i')).toBe('FPL lists this player as injured');
		expect(repairReasonText('status:s')).toBe('FPL lists this player as suspended');
		expect(repairReasonText('status:n')).toBe('FPL lists this player as not available');
		expect(repairReasonText('status:d')).toBe('FPL has flagged this player as a doubt');
		expect(repairReasonText('status:z')).toBe('FPL status: z');
	});

	it('chance_next:0 on oma lauseensa', () => {
		expect(repairReasonText('chance_next:0')).toBe(
			'FPL gives this player a 0% chance of playing the next round'
		);
	});

	it('no_projection erottaa tunnetun ja tuntemattoman syyn', () => {
		expect(repairReasonText('no_projection:below_min_xp')).toBe(
			'the model projects this player under the cutoff over the horizon'
		);
		// "unknown" (backendin oma heikko-mutta-tosi-oletus) ei saa arvata
		// sanaa "unavailable" jota lähde ei kerro (fpl_transfers.repair_reason
		// -dokumentti nimeää tämän tasan tätä syytä varten).
		expect(repairReasonText('no_projection:unknown')).toBe(
			'the model has stopped projecting minutes for this player'
		);
		expect(repairReasonText('no_projection:unknown')).not.toMatch(/unavailable/i);
	});

	it('negatiivinen kontrolli: tuntematon avain (ei kaksoispistettä) ei kaadu eika arvaa', () => {
		expect(repairReasonText('something-else')).toBeNull();
	});
});

describe('TransferPlanner.svelte lukee repair_reasonin (ei vain määrittele sitä)', () => {
	const SRC = readFileSync(
		fileURLToPath(new URL('./components/TransferPlanner.svelte', import.meta.url)),
		'utf-8'
	);

	it('tuo repairReasonTextin ja kutsuu sitä siirtorivillä', () => {
		expect(SRC).toMatch(/import\s*\{\s*repairReasonText\s*\}\s*from\s*'\$lib\/availabilityFlag'/);
		expect(SRC).toMatch(/repairReasonText\(t\.repair_reason\)/);
	});

	it('kutsu on saman <li>-rivin sisällä kuin gain_xp_remaining, ei jossain muualla', () => {
		const liStart = SRC.indexOf('{#each g.transfers as t');
		const liEnd = SRC.indexOf('{/each}', liStart);
		const block = SRC.slice(liStart, liEnd);
		expect(block).toMatch(/gain_xp_remaining/);
		expect(block).toMatch(/repairReasonText\(t\.repair_reason\)/);
	});
});
