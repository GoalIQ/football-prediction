#!/usr/bin/env bash
# Pushaa sivuston stagingin site-repoon (SITE-REPO-SPLIT vaihe 1, 10.9.2026).
#
# MITA: kloonaa `GoalIQ/goaliq-site`, korvaa sen sisallon staging-hakemistolla
# (paitsi .git, .github ja README.md jotka ovat site-repon omia), committaa
# LAHDEKOMMITIN AIKALEIMALLA ja pushaa. Site-repon historia on silloin
# football-predictionin output-historia, ei push-hetkien historia: fpl.html
# lupaa etta jaadytetty projektio on "written in a single commit dated before
# the deadline", ja se lupaus on totta vain jos aikaleima seuraa lahdetta.
#
# VARTIOINTI: kutsuja (hub-deploy.yml) ajaa taman VAIN kun SITE_DEPLOY_TOKEN
# on asetettu. Ilman secretia vanha polku (wrangler direct upload) toimii
# ennallaan, eika mikaan tassa tiedostossa voi vaikuttaa siihen.
#
# 🔴 SKIP-CI-MERKINTA RIISUTAAN commit-viestista. Bottien lahdecommitit
# kantavat sita otsikossaan, ja jos se kopioituisi site-repon committiin,
# site-repon oma deploy-workflow ei kaynnistyisi koskaan (muisti:
# skip-ci-proosassa-sammuttaa-koko-pushin). Se on juuri se vika joka 19.8,
# 7.9 ja 9.9 jatti liven yhden commitin jalkeen.
#
# Secret voi olla joko GitHub-token (fine-grained PAT, Contents: write) tai
# SSH deploy key (alkaa "-----BEGIN ... PRIVATE KEY-----"). Deploy key on
# varareitti jos orgin PAT-politiikka estaa tokenin.
#
# Kaytto:  SITE_DEPLOY_TOKEN=... scripts/push_site_repo.sh [staging-dir]
#          ymparisto: SITE_REPO (oletus GoalIQ/goaliq-site), SITE_BRANCH (main)
set -euo pipefail

STAGE="${1:-_hub}"
REPO="${SITE_REPO:-GoalIQ/goaliq-site}"
BRANCH="${SITE_BRANCH:-main}"
: "${SITE_DEPLOY_TOKEN:?SITE_DEPLOY_TOKEN puuttuu - kutsuja ei saa ajaa tata ilman secretia}"
[ -d "$STAGE" ] || { echo "::error::staging-hakemistoa $STAGE ei ole"; exit 1; }
N_STAGE=$(find "$STAGE" -type f | wc -l)
[ "$N_STAGE" -gt 100 ] || { echo "::error::staging on vajaa ($N_STAGE tiedostoa) - ei pushata"; exit 1; }

SRC_SHA=$(git rev-parse HEAD)
SRC_DATE=$(git log -1 --format=%cI HEAD)
SRC_SUBJ=$(git log -1 --format=%s HEAD | sed -E 's/\[(skip|no) *(ci|actions)\]//Ig; s/\[(ci|actions) *skip\]//Ig; s/  +/ /g; s/ +$//')

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if [[ "$SITE_DEPLOY_TOKEN" == *"PRIVATE KEY-----"* ]]; then
  KEY="$WORK/deploy_key"
  printf '%s\n' "$SITE_DEPLOY_TOKEN" > "$KEY"
  chmod 600 "$KEY"
  export GIT_SSH_COMMAND="ssh -i $KEY -o StrictHostKeyChecking=accept-new"
  URL="git@github.com:${REPO}.git"
  echo "site-push: deploy key -> $REPO"
else
  URL="https://x-access-token:${SITE_DEPLOY_TOKEN}@github.com/${REPO}.git"
  echo "site-push: token -> $REPO"
fi

SITE="$WORK/site"
# Tyhja repo: --branch kaatuu, silloin kloonataan ilman ja luodaan haara.
if ! git clone --quiet --depth 1 --branch "$BRANCH" "$URL" "$SITE" 2>/dev/null; then
  git clone --quiet "$URL" "$SITE"
  git -C "$SITE" rev-parse --verify HEAD >/dev/null 2>&1 || git -C "$SITE" checkout -q -b "$BRANCH"
fi

# Korvaa sisalto. .github ja README.md ovat site-repon omia (deploy-workflow,
# lukijalle tarkoitettu selitys) eika football-prediction hallitse niita.
find "$SITE" -mindepth 1 -maxdepth 1 ! -name .git ! -name .github ! -name README.md -exec rm -rf {} +
cp -a "$STAGE"/. "$SITE"/

git -C "$SITE" add -A
if git -C "$SITE" diff --cached --quiet; then
  echo "site-push: ei muutoksia ($REPO on jo tassa tilassa)"
  [ -n "${GITHUB_OUTPUT:-}" ] && echo "pushed=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

export GIT_AUTHOR_NAME="goaliq-bot" GIT_AUTHOR_EMAIL="bot@goaliq.app"
export GIT_COMMITTER_NAME="goaliq-bot" GIT_COMMITTER_EMAIL="bot@goaliq.app"
export GIT_AUTHOR_DATE="$SRC_DATE" GIT_COMMITTER_DATE="$SRC_DATE"
git -C "$SITE" commit --quiet -m "site: ${SRC_SUBJ}" -m "source: football-prediction@${SRC_SHA}"

for i in 1 2 3; do
  if git -C "$SITE" push --quiet origin "HEAD:${BRANCH}"; then
    break
  fi
  [ "$i" = 3 ] && { echo "::error::site-push epaonnistui kolmesti ($REPO)"; exit 1; }
  echo "site-push: push-yritys $i epaonnistui, haetaan ja yritetaan uudelleen"
  git -C "$SITE" fetch --quiet --depth 1 origin "$BRANCH" && git -C "$SITE" rebase --quiet "origin/${BRANCH}" || true
done

# Portti: pushattu puu == staging (tiedostomaara). Vihrea push ei todista
# sisaltoa; tama todistaa ainakin etta mikaan ei pudonnut matkalla.
N_SITE=$(git -C "$SITE" ls-files | grep -vE '^(\.github/|README\.md$)' | wc -l)
if [ "$N_SITE" != "$N_STAGE" ]; then
  echo "::error::site-repossa $N_SITE tiedostoa, stagingissa $N_STAGE"; exit 1
fi
SITE_SHA=$(git -C "$SITE" rev-parse HEAD)
echo "site-push OK: $REPO@${SITE_SHA:0:9} <- football-prediction@${SRC_SHA:0:9} ($N_SITE tiedostoa, pvm $SRC_DATE)"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "pushed=true" >> "$GITHUB_OUTPUT"
  echo "site_sha=$SITE_SHA" >> "$GITHUB_OUTPUT"
fi
