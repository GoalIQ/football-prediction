-- DECISION-USER-ACTUAL (10.9.2026). Paatospaivakirja nimesi kapteenin jota
-- grader ei pisteyttanyt: lause luki user_choice.name (sovelluksen kentalla
-- kirjattu LUONNOS), grader pisteytti FPL:n picks-kapteenin. GW2 2.9:
-- "you captained Senesi over Tavernier +44.0" kun FPL-kapteeni oli
-- B.Fernandes (46 p). Kaksi lahdetta, yksi lause.
--
-- user_actual = se valinta jonka grader PISTEYTTI, samasta lahteesta
-- (FPL picks). Pinnat nimeavat kayttajan valinnan VAIN tasta kentasta.
-- Immutability-trigger (fpl_decisions_guard_grading) vartioi vain
-- graded_at/model_points/user_points/grade_note -kenttia, joten tama
-- sarake voidaan taydentaa jalkikateen jo gradatuille riveille (GW2).
alter table public.fpl_decisions
  add column if not exists user_actual jsonb;

comment on column public.fpl_decisions.user_actual is
  'Graderin pisteyttama kayttajan toteutunut valinta: {"id": element_id, "web_name": text, "source": "fpl_picks"}. NULL = ei saatu (ks. grade_note). Pinnat nimeavat kayttajan valinnan VAIN tasta, ei user_choice-luonnoksesta.';
