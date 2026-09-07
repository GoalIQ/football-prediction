// Ajaa goaliq-appin `allTimeWindow`-lukijan ja tulostaa sen vastauksen
// jokaiselle syotteelle. Vertailu career.html:n omaan haaraan tehdaan
// Pythonin puolella (`tests/test_alltime_window_parity.py`).
//
// 🔴 MIKSI: sama saanto on kirjoitettu kahdesti - kerran mobiiliin
// (`lib/careerAllTime.ts`) ja kerran `career.html`:n inline-JS:aan, joka ei
// voi importoida TS-moduulia. 21. kierroksella ne olivat ERI MIELTA nollasta
// (`!= null` vs totuusarvo), ja meidan puolemme olisi tulostanut "GW0".
// Merkkijonovertailu ei kelpaa, koska kielet ovat eri. Siksi molemmat
// AJETAAN samalla syotetaululla ja vastauksia verrataan.
import { allTimeWindow } from '../../../goaliq-app/lib/careerAllTime.ts';

const SYOTTEET = JSON.parse(process.argv[2]);
console.log(JSON.stringify(SYOTTEET.map((s) => allTimeWindow(s))));
