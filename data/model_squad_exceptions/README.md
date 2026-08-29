# Kirjatut poikkeukset: FPL-entry vs jaadytetty runko

`gw{N}.json` tassa hakemistossa kertoo `scripts/verify_model_entry_matches_freeze.py`:lle
etta kierroksen N entry saa erota jaadytetysta rungosta. Kentat: `gw`, `reason`,
`decided_by`, `decided_at` (kaikki pakollisia, tyhja = virhe). Poikkeus koskee VAIN
kierrosta N ja se on rekisteri Villen paatoksesta, ei vapaakortti.

OMA HAKEMISTO, EI `model_squad_frozen/`: graderit ja freeze lukevat sen
`glob("gw*.json")`-haulla, ja `gw2.exception.json` siella kaatoi
`grade_model_squad_gw` -askeleen 29.8 07:06 (int(None)) ja padotti commit-askeleen
uudelleen. `tests/test_model_entry_watch.py::test_frozen_dir_holds_only_freezes`
vartioi tata.
