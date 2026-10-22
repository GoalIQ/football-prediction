#!/usr/bin/env bash
# Understatin TLS-kirjasto tunnistautuneena (22.10.2026).
#
# tls_requests (soccerdata -> Understat) hakee kirjaston tiedot GitHubin API:sta ilman tunnusta. Jaetulla
# ajokoneella raja (60 kyselya/h) tayttyy ajoittain; silloin kirjasto arvaa tiedostonimen vaarin
# ("tls-client-ubuntu-amd64-v1.13.1.so", oikea on "tls-client-linux-ubuntu-amd64-1.13.1.so"), lataus kaatuu ja
# Understat-haku putoaa varalahteeseen. 22.10 15:41 se teki neljasta vakiintuneesta seurasta nousijoita
# goaliq.app/fpl-sivulle. Haetaan sama versio kuin asennettu tls_requests odottaa, GITHUB_TOKENilla, ja annetaan
# polku TLS_LIBRARY_PATH-muuttujassa (kirjasto lukee sen ennen omaa latausta).
#
# Fail-open tarkoituksella: jos haku kaatuu, PL-rakentajat kieltaytyvat itse (src/data/loader.vaadi_understat),
# eli tama askel ei paata julkaisusta.
set -uo pipefail

ver=$(python -c "from tls_requests.models.libraries import LATEST_VERSION_TAG_NAME as v; print(v)" 2>/dev/null) || {
  echo "::warning::tls_requests-versio ei luettavissa: Understat-haku voi pudota varalahteeseen"
  exit 0
}
dir="${RUNNER_TEMP:-/tmp}/tls-client"
asset="tls-client-linux-ubuntu-amd64-${ver#v}.so"
mkdir -p "$dir"
if gh release download "$ver" -R bogdanfinn/tls-client -p "$asset" -D "$dir" --clobber; then
  echo "TLS_LIBRARY_PATH=$dir/$asset" >> "${GITHUB_ENV:-/dev/null}"
  echo "TLS-kirjasto $ver valmiina: $dir/$asset"
else
  echo "::warning::TLS-kirjaston haku epaonnistui ($ver, $asset): PL-rakentajat kieltaytyvat jos Understat ei vastaa"
fi
exit 0
