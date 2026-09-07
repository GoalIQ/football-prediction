#!/usr/bin/env bash
# Portti + itsekorjaus: goaliq.app servaa ne sivut jotka repossa on.
#
# MIKSI TAMA ON OMA TIEDOSTONSA (7.9.2026)
# `fpl-page-refresh.yml` oli punainen kahdesti yossa. Diagnoosi ei ollut
# "Pages-deploy failasi" niin kuin sen oma virheteksti vaitti:
#
#   02:05  live servasi TASMALLEEN commitin 5d217815b fpl.html + index.html
#          (mitattu md5:lla molemmista), vaikka mainissa oli 7a81f8c29.
#          Live oli siis yhden deployn jaljessa, ei rikki.
#   Syy    `fpl-data-refresh.yml` committaa fpl.html + index.html `[skip ci]`
#          -viestilla EIKA dispatchaa hub-deployta. CF Pages on direct upload
#          eika deployaa pushista itsestaan (cutover 15.8), joten sivu jai
#          repoon mutta ei koskaan mennyt ulos.
#   Ja     `fpl-page-refresh.yml` dispatchasi hub-deployn vain jos SE ITSE
#          oli pushannut. Kun data-refresh oli jo kirjoittanut samat sivut,
#          tama ajo sanoi "Ei muutoksia", ohitti dispatchin — ja verifioi
#          sitten liveä jota kukaan ei ollut deployannut. Punainen oli oikea,
#          korjaus vain oli askeleen ulottumattomissa.
#
# KORJAUS ON EHDON VAIHTO, EI UUSI VAHTI. Deploy ei riipu siita KUKA
# kirjoitti sivun vaan siita MITA LIVE SERVAA. Jos mitattu live != repo,
# tama dispatchaa hub-deployn riippumatta siita kuka ajaa. Silloin
# "committaa sivu ilman deployta" ei ole enaa mahdollinen lopputila.
#
# Kaytto:  GH_TOKEN=... scripts/verify_live_pages.sh [tiedosto ...]
#          oletus: fpl.html index.html
set -uo pipefail

FILES=("$@")
[ ${#FILES[@]} -eq 0 ] && FILES=(fpl.html index.html)

BASE="${LIVE_BASE:-https://goaliq.app}"
TRIES="${VERIFY_TRIES:-24}"
SLEEP="${VERIFY_SLEEP:-20}"

# Cloudflare injektoi challenge-platform-skriptin juuri ennen </body>, ja
# siina on PER-PYYNTO vaihtuva tunniste (__CF$cv$params r:'...'). Koko
# tiedoston md5 ei siksi voi koskaan tasmata ilman riisuntaa. Verifioitu
# 17.8: riisuttu live == repon tiedosto bittitarkasti.
CF_STRIP='s|<script>(function(){function c(){var b=a\.contentDocument.*</script>||'

# -L ON PAKOLLINEN: CF Pages 308-ohjaa .html-URLit puhtaisiin polkuihin, ja
# ilman sita curl palauttaa TYHJAN bodyn (md5 d41d8cd9...) eli askel vertaisi
# HEADia tyhjaan merkkijonoon.
elava() { curl -sfL --max-time 20 "$BASE/$1" | sed "$CF_STRIP" | md5sum | cut -d' ' -f1 || echo "fetch-fail"; }
repo()  { md5sum "$1" | cut -d' ' -f1; }

echo "Odotetut hashit:"
for f in "${FILES[@]}"; do echo "  $f = $(repo "$f")"; done

dispatched=0
for i in $(seq 1 "$TRIES"); do
  kaikki_ok=1
  raportti=""
  for f in "${FILES[@]}"; do
    got=$(elava "$f"); want=$(repo "$f")
    raportti="$raportti $f=$got"
    [ "$got" = "$want" ] || kaikki_ok=0
  done

  if [ "$kaikki_ok" = "1" ]; then
    echo "OK (yritys $i): live-sisalto = repo. Deploy verifioitu."
    exit 0
  fi

  # 🔴 ITSEKORJAUS: ehto on mittaus, ei "pushasinko mina".
  if [ "$dispatched" = "0" ]; then
    if [ -n "${GH_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
      if gh workflow run hub-deploy.yml --ref main; then
        echo "live != repo -> hub-deploy dispatchattu (kuka tahansa kirjoitti sivun)."
        dispatched=1
      else
        # 🔴 7.9: TAMA OLI VAIN WARNING, ja askel kaatui 8 min myohemmin
        # virheella joka nimesi vaaran mekanismin ("goaliq.app ei servaa
        # repon sivuja"). Todellinen syy oli `HTTP 403: Resource not
        # accessible by integration` - workflow'lta puuttui `actions: write`,
        # eli ITSEKORJAUS EI VOINUT KORJATA MITAAN. Epaonnistunut korjaus on
        # oma vikansa ja se on nimettava heti.
        echo "::error::hub-deployn dispatch EPAONNISTUI. Itsekorjaus ei toimi:"
        echo "::error::tarkista etta workflow'lla on 'permissions: actions: write'."
        exit 2
      fi
    else
      echo "::error::GH_TOKEN tai gh puuttuu - itsekorjaus ei voi dispatchata."
      exit 2
    fi
  fi

  # SUPERSEEDAUS: jos joku on pushannut UUDEMMAT sivut sill'aikaa, meidan
  # odottamamme hash on jo vanhentunut eika sita tule koskaan liveen. Se ei
  # ole vika vaan kilpailu, ja sen ajon verify vahvistaa lopputilan.
  if [ $((i % 6)) -eq 0 ] && git fetch -q origin main 2>/dev/null; then
    ohitettu=0
    for f in "${FILES[@]}"; do
      etana=$(git show "origin/main:$f" 2>/dev/null | md5sum | cut -d' ' -f1)
      [ -n "$etana" ] && [ "$etana" != "$(repo "$f")" ] && ohitettu=1
    done
    if [ "$ohitettu" = "1" ]; then
      echo "origin/main on jo uudemmissa sivuissa - tama ajo on superseedattu."
      echo "Ei punaista: seuraava ajo verifioi lopputilan."
      exit 0
    fi
  fi

  echo "Yritys $i/$TRIES: live != repo ($raportti) - odotetaan $SLEEP s..."
  sleep "$SLEEP"
done

echo "::error::$BASE ei servaa repon sivuja $((TRIES * SLEEP / 60)) min kuluttua."
echo "hub-deploy dispatchattiin: $dispatched. Tarkista Actions: hub-deploy.yml."
exit 1
