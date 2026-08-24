-- Separate database for the pytest suite (see docs/TEST_STRATEGY.md):
-- tests never touch the dev/seed database.
CREATE DATABASE prova_test OWNER prova;
