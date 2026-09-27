/**
 * Joukkuepaneelin tila (PRO-JOUKKUENAKYMA 27.9.2026). Sama malli kuin
 * `playerSheet.svelte.ts`: yksi instanssi AppShellissa, avaajat kertovat vain
 * seuran lyhenteen.
 *
 * PINO: paneelista voi avata pelaajakortin ja pelaajakortista paneelin.
 * Viimeksi avattu on paalla (`above`), ja Escape sulkee vain paalimmaisen.
 */
import { playerIdFromEvent } from './playerRow';
import { openPlayer, playerSheet } from './playerSheet.svelte';

export const teamSheet = $state({
	/** Avoinna olevan seuran FPL-lyhenne, null = kiinni. */
	short: null as string | null,
	/** Mista paneeli avattiin (analytiikka). */
	source: '',
	/** true = avattiin pelaajakortin paalle, joten paneeli on ylimpana. */
	above: false
});

export function openTeam(short: string | null | undefined, source: string): void {
	const s = (short ?? '').trim();
	if (!s) return;
	teamSheet.above = playerSheet.id != null;
	teamSheet.short = s;
	teamSheet.source = source;
}

export function closeTeam(): void {
	teamSheet.short = null;
	teamSheet.above = false;
}

/** Onko joukkuepaneeli ylin avoin paneeli (Escape ja fokus). */
export function teamOnTop(): boolean {
	return teamSheet.short != null && (teamSheet.above || playerSheet.id == null);
}

/** Paneelin pelaajarivit avaavat kortin paneelin PAALLE. */
export function teamPlayerRowClick(e: Event): void {
	const id = playerIdFromEvent(e.target);
	if (id == null) return;
	teamSheet.above = false;
	openPlayer(id, 'team_sheet');
}
