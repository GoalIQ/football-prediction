import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

// Erillinen vitest-konfiguraatio: vite.config.ts kantaa SvelteKit-pluginin
// (adapter, appDir-kiertotie), jota yksikkotestit eivat tarvitse. $lib
// ratkaistaan samaan kansioon kuin SvelteKitissa.
export default defineConfig({
	resolve: {
		alias: { $lib: fileURLToPath(new URL('./src/lib', import.meta.url)) }
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node'
	}
});
