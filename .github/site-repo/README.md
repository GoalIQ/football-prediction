# goaliq.app

This repository is the published output of [goaliq.app](https://goaliq.app):
the pages Cloudflare Pages serves, and the data files those pages cite.

Nothing here is edited by hand. Every commit is pushed by the model
repository's publishing workflow, carries the timestamp of the source commit,
and names it in the commit body (`source: football-prediction@<sha>`).

## What is in here

- `*.html`, `fpl/`, `predictions/`, `ucl/`, `assets/`: the site as served.
- `data/`: the files the pages cite as their source. Each one is listed, with
  the reason it is public, in the model repository's `scripts/site_output.py`.
  The frozen projections (`data/fpl_xp_frozen/`, `data/model_squad_frozen/`,
  `data/spl_deadline_snapshots/`) are written before the gameweek deadline and
  graded afterwards; the commit history here is the record of that.

## What is not in here

The model code, the training data and the backtests live in a private
repository. The public claims on the site are checked against the files in
this repository, not against the code.
