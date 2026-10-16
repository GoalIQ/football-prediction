# FPL and Premier League knowledge for the Bluesky brain (2026/27)

The authoritative scoring is in the briefing (`fpl.scoring_rules`, read live from FPL's
bootstrap-static `game_config.scoring`). This file is context, not a source of numbers: never put a
number from here into a post.

## The game

- Squad of 15 (2 GK, 5 DEF, 5 MID, 3 FWD), 100.0m budget, max 3 players per club. 11 start, 4 on the
  bench with automatic substitutions for players who don't play.
- Captain scores double (Triple Captain chip: triple). Vice-captain takes over if the captain doesn't play.
- One free transfer per gameweek, unused ones roll over up to 5 saved. Extra transfers cost 4 points (a "hit").
- Deadline: 90 minutes before the first kickoff of the gameweek. Some deadlines fall on Friday
  evenings (GW8 2026/27 is Friday 23 October, 18:30 UK).
- Chips, two sets: Wildcard, Free Hit, Bench Boost, Triple Captain for each half. The first set must
  be used before the GW19 deadline (2 January 2027) and does not carry over.
- Points lock the morning after a gameweek's last match (09:00 UK), after Opta's checked data is in.

## Scoring that drives decisions

- Goals, assists and clean sheets score by position: the exact values are in `fpl.scoring_rules`.
  Defenders and goalkeepers gain most from clean sheets, midfielders a little, forwards nothing.
- Defensive contributions (DefCon): a defender earns 2 points for 10 combined clearances, blocks,
  interceptions and tackles; midfielders and forwards need 12 including recoveries. It rewards
  high-volume defensive midfielders and centre-backs.
- Bonus points (BPS): top three BPS scores in each match get 3, 2 and 1. 2026/27 changes: no minus
  point for being tackled, clearances/blocks/interceptions count 1 BPS per 3, goalkeepers gain more
  per save and for saves from inside the box.
- Minutes: 1 point for up to 59 minutes, 2 for 60 or more. Rotation risk is the biggest hidden cost.

## Prices

- Prices move once a day around midnight UK time, based on net transfers. FPL's own price predictor (new in 2026/27)
  shows progress towards a change; the briefing has `price_tonight_fpl_projection` from it.
- Selling price is half the profit (rounded down), so early rises matter to managers.

## What managers argue about every week

- Captain: the premium forward vs the in-form midfielder; home vs away; "differential" captains.
- Transfers: injury replacements before the deadline, chasing last week's haul, fixture swings.
- Chip timing: when to wildcard, Bench Boost weeks, double gameweeks (two fixtures in one GW) and
  blank gameweeks (no fixture), usually caused by cup ties.
- Team news: press conferences Thursday and Friday; FPL's status flags (a = available, d = doubtful,
  i = injured, s = suspended, u = unavailable) and the chance of playing percentage.
- Template: the players most top managers own. Effective ownership (EO) decides rank swings.

## Premier League context the brain should know

- 20 clubs, 38 rounds. Promoted clubs usually concede more early; managers chase their attackers
  only after evidence.
- Loan players cannot face their parent club (FPL's `scout_risks` marks the gameweek).
- European weeks (Champions League Tuesday/Wednesday, Europa and Conference League Thursday) raise
  rotation risk for those clubs in the following league round.
- A yellow card count of 5 by gameweek 19 means a one-match ban; FPL flags "suspension risk".

## GoalIQ's own record (only as numbers from the briefing)

- Match predictions are logged before kickoff and graded after; the hit rate is public with its sample size.
- Per-player expected points are frozen before each deadline and compared with FPL's own projection
  (ep_next) on the same players, every gameweek.
- Entry 116920 plays the model's squad with our own chip calls and the occasional lineup change; it is
  the team to beat in the Beat the Model mini-league.
