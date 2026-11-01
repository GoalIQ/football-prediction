-- ulkoasu WP6 (1.11.2026, Villen paatos): kertamaksuinen kausipassi 2026/27.
-- Koodipuoli: src/season_pass.py + api/main.py _fulfil_season_pass.
--
-- Laajentaa kaksi CHECK-rajoitetta niin etta passin tunniste
-- 'season_pass_2026_27' mahtuu kantaan:
--   profiles.premium_source      ('stripe_web','revenuecat','comp' -> + passi)
--   web_subscriptions.plan       ('season','monthly'                -> + passi)
--
-- AJETAAN ENNEN kuin STRIPE_PRICE_SEASON_PASS_2026_27 asetetaan Renderiin.
-- Ilman tata koodi on silti turvallinen (ei pysyvaa Premiumia): web-rivi
-- kirjoitetaan plan='season'-arvolla ja loppu 2027-05-30, ja profiilia EI
-- avata, koska premium_source-leima epaonnistuu. Silloin passi toimii webissa
-- mutta ei sovelluksessa.
--
-- Idempotentti: vanhat rajoitteet pudotetaan maarittelyn sisallon mukaan
-- (nimi voi olla Postgresin automaattinen tai kasin annettu), ja uudet
-- luodaan vain jos niita ei ole.

DO $$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'public.profiles'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%premium_source%'
      AND pg_get_constraintdef(oid) NOT ILIKE '%season_pass_2026_27%'
  LOOP
    EXECUTE format('ALTER TABLE public.profiles DROP CONSTRAINT %I', c.conname);
  END LOOP;

  FOR c IN
    SELECT conname FROM pg_constraint
    WHERE conrelid = 'public.web_subscriptions'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%plan%'
      AND pg_get_constraintdef(oid) NOT ILIKE '%season_pass_2026_27%'
  LOOP
    EXECUTE format('ALTER TABLE public.web_subscriptions DROP CONSTRAINT %I', c.conname);
  END LOOP;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid = 'public.profiles'::regclass
                   AND conname = 'profiles_premium_source_check') THEN
    ALTER TABLE public.profiles ADD CONSTRAINT profiles_premium_source_check
      CHECK (premium_source IN ('stripe_web', 'revenuecat', 'comp', 'season_pass_2026_27')
             OR premium_source IS NULL);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid = 'public.web_subscriptions'::regclass
                   AND conname = 'web_subscriptions_plan_check') THEN
    ALTER TABLE public.web_subscriptions ADD CONSTRAINT web_subscriptions_plan_check
      CHECK (plan IN ('season', 'monthly', 'season_pass_2026_27'));
  END IF;
END $$;
