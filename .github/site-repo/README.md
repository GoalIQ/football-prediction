# goaliq.app

This repository is the published output of [goaliq.app](https://goaliq.app):
the pages Cloudflare Pages serves, and the data files those pages cite as
their source.

Commits here are written by the publishing workflow in the model repository.
Each one carries the timestamp of the source commit and names it in the
commit body (`source: football-prediction@<sha>`). Anything pushed by hand
says so in the commit message.

## What is in here

- `*.html`, `fpl/`, `predictions/`, `ucl/`, `assets/`: the site as served.
- `data/`: the files the pages cite. `data/MANIFEST.md` lists each one and
  the page that cites it.

Files under `data/fpl_xp_frozen/` and `data/model_squad_frozen/` are written
before the FPL deadline and graded after it, and the commit that added them
is dated before that deadline. `data/spl_deadline_snapshots/` is pinned to
the first kickoff of the round instead, and gameweeks 1 to 4 were added to
git in one backfill on 3 September 2026; for those, the `provenance` block
inside each file carries the build commit and the time it was generated,
which is what the pre-kickoff claim rests on.

## What is not in here

The model code, training data and backtests are in a private repository.
The claims on the site are checkable against the files here.
