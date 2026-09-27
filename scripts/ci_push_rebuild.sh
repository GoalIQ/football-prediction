#!/usr/bin/env bash
# Generoidun datan ja sivujen push mainiin: KONFLIKTISSA SIVUT RAKENNETAAN
# UUDELLEEN, EI YHDISTETA (27.9.2026, autopilot S16 / CI-PUSH-EI-SAA-HEITTAA-
# BUILDIA-POIS suunta 1).
#
# MIKSI. Vanha askel ajoi `git rebase origin/main` viisi kertaa. Kun toinen
# workflow oli ajon aikana regeneroinut SAMAN sivulohkon eri syotteesta,
# sisaltokonflikti oli deterministinen: kaikki viisi yritysta kaatuivat samaan
# kohtaan ja koko ajon data jai mainin ulkopuolelle. Mitattu 26.9 13:35 UTC
# (accuracy-log 36245702189): builder-muutos efa4622a9 kaynnisti
# fpl-data-refreshin (13:37) ja longtail-refreshin (13:39), molemmat
# regeneroivat fpl.html/index.html/predictions.html, ja accuracy-login rebase
# konfliktoi kolmessa tiedostossa viidesti.
#
# MITEN. Konfliktissa: palataan tuoreimpaan origin/mainiin, palautetaan TAMAN
# ajon omat datatiedostot ja ajetaan sivubuilderit uudelleen yhdistetyn datan
# paalla. Sivu on silloin molempien workflow'jen datan tulos, eika kumpikaan
# versio "voita".
#
# 🔴 EI "MEIDAN VERSIO VOITTAA" DATALLE. Jos joku muu muutti samaa
# datatiedostoa ajon aikana, skripti KAATUU aanekkaasti eika ylikirjoita.
# Hylatty suunta 21.9 (fix/push-generoitu-data-ei-konfliktoi,
# fix/ci-push-gen-lohko-omistajuus): se havitti toisen workflow'n datan
# hiljaa (ACC-TICKER 571 -> 569, exit 0).
#
# Kaytto (ymparistomuuttujat, jotta testi voi ajaa saman skriptin):
#   CI_PUSH_DATA    valilyonnein eroteltu lista taman ajon datatiedostoista
#   CI_PUSH_PAGES   valilyonnein eroteltu lista generoiduista poluista
#   CI_PUSH_BUILD   komento joka regeneroi CI_PUSH_PAGES:n datasta
#   CI_PUSH_MSG     commit-viesti
#   CI_PUSH_REMOTE  (origin) CI_PUSH_BRANCH (main) CI_PUSH_TRIES (5)
#   CI_PUSH_SLEEP   (5) sekuntia yritysten valilla
# Exit 0 = pushattu tai ei muutoksia. Exit 1 = ei pushattu (syy lokissa).
# GITHUB_OUTPUT saa pushed=true kun push onnistui.
set -u

REMOTE="${CI_PUSH_REMOTE:-origin}"
BRANCH="${CI_PUSH_BRANCH:-main}"
TRIES="${CI_PUSH_TRIES:-5}"
SLEEP="${CI_PUSH_SLEEP:-5}"
DATA="${CI_PUSH_DATA:?CI_PUSH_DATA puuttuu}"
PAGES="${CI_PUSH_PAGES:?CI_PUSH_PAGES puuttuu}"
BUILD="${CI_PUSH_BUILD:?CI_PUSH_BUILD puuttuu}"
MSG="${CI_PUSH_MSG:?CI_PUSH_MSG puuttuu}"

# Polku kerrallaan: yksi puuttuva polku ei saa estaa muiden lisaamista
# (`git add a puuttuva b` lisaa NOLLA tiedostoa).
lisaa() {
  for p in "$@"; do
    git add -- "$p" 2>/dev/null || true
  done
}

merkitse_pushattu() {
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "pushed=true" >> "$GITHUB_OUTPUT"
  fi
}

# shellcheck disable=SC2086
lisaa $DATA
# shellcheck disable=SC2086
lisaa $PAGES
if git diff --cached --quiet; then
  echo "Ei muutoksia - ohitetaan commit."
  exit 0
fi
git commit -q -m "$MSG"

for i in $(seq 1 "$TRIES"); do
  git fetch -q "$REMOTE" "$BRANCH" || true
  if rebase_virhe=$(git rebase --autostash "$REMOTE/$BRANCH" 2>&1); then
    if git push -q "$REMOTE" "HEAD:$BRANCH"; then
      echo "Pushed to $BRANCH (yritys $i)."
      merkitse_pushattu
      exit 0
    fi
    echo "Yritys $i: push hylattiin (kilpailu) - uusi yritys."
  else
    echo "$rebase_virhe"
    git rebase --abort 2>/dev/null || true
    oma=$(git rev-parse HEAD)
    pohja=$(git merge-base "$oma" "$REMOTE/$BRANCH")
    # shellcheck disable=SC2086
    if ! git diff --quiet "$pohja" "$REMOTE/$BRANCH" -- $DATA; then
      echo "::error::Yritys $i: joku muu muutti taman ajon datatiedostoa ajon aikana:"
      # shellcheck disable=SC2086
      git diff --stat "$pohja" "$REMOTE/$BRANCH" -- $DATA
      echo "EI ylikirjoiteta (hylatty 'meidan voittaa' -suunta 21.9). Ei pushattu."
      exit 1
    fi
    echo "Yritys $i: konflikti generoiduissa sivuissa - rakennetaan uudelleen tuoreen $BRANCH:n paalle."
    git reset -q --hard "$REMOTE/$BRANCH"
    for p in $DATA; do
      if git cat-file -e "$oma:$p" 2>/dev/null; then
        git checkout -q "$oma" -- "$p"
      fi
    done
    # Builderin virhe ei kaada pushia: data on tarkein, ja vanha sivu on
    # nakyva vika (sama periaate kuin workflow'n continue-on-error-bakeissa).
    bash -c "$BUILD" || echo "::warning::uudelleenrakennus palautti virheen - data pushataan silti."
    # shellcheck disable=SC2086
    lisaa $DATA
    # shellcheck disable=SC2086
    lisaa $PAGES
    if git diff --cached --quiet; then
      echo "Uudelleenrakennuksen jalkeen ei muutoksia - ohitetaan."
      exit 0
    fi
    git commit -q -m "$MSG"
    if git push -q "$REMOTE" "HEAD:$BRANCH"; then
      echo "Pushed to $BRANCH uudelleenrakennettuna (yritys $i)."
      merkitse_pushattu
      exit 0
    fi
    echo "Yritys $i: push hylattiin uudelleenrakennuksen jalkeen - uusi yritys."
  fi
  sleep "$SLEEP"
done
echo "VIRHE: push mainiin epaonnistui $TRIES yrityksen jalkeen."
exit 1
