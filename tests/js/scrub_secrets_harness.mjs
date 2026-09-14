// Ajaa web/pro-spa/src/lib/scrubSecrets.ts:n scrubSecrets-funktion stdinin
// JSON-syotteille ja tulostaa tuloksen. Kaytetaan test_posthog_no_auth_secrets.py:ssa.
// Ajo: node --experimental-strip-types scrub_secrets_harness.mjs < input.json
import { readFileSync } from 'node:fs';
import { scrubSecrets } from '../../web/pro-spa/src/lib/scrubSecrets.ts';

const input = JSON.parse(readFileSync(0, 'utf-8'));
process.stdout.write(JSON.stringify(input.map((x) => scrubSecrets(x))));
