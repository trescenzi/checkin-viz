-- load.sql — Load all seed CSV data into the database.
-- Run with: psql -h postgres -U postgres -d projects -f /seed/load.sql
--
-- Assumes the schema already exists and .csv files are in /seed/base/ and /seed/current/
--
-- Safe to run multiple times: clears tables and reloads from scratch.

-- Clear existing data
\echo 'Clearing tables...'
TRUNCATE checkins, challenger_challenges, medals, challenge_weeks, challenges, challengers CASCADE;

-- ============================================================
-- Base data (Challenge 23)
-- ============================================================
\echo ''
\echo '--- Base: challengers ---'
COPY challengers FROM '/seed/base/challengers.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Base: challenges ---'
COPY challenges FROM '/seed/base/challenges.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Base: challenge_weeks ---'
COPY challenge_weeks FROM '/seed/base/challenge_weeks.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Base: checkins ---'
-- Explicit column list for auto-increment columns (id, tz)
COPY checkins (name, time, tier, day_of_week, text, challenge_week_id, id, challenger, tz)
    FROM '/seed/base/checkins.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Base: challenger_challenges ---'
COPY challenger_challenges FROM '/seed/base/challenger_challenges.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Base: medals ---'
COPY medals FROM '/seed/base/medals.csv' WITH (FORMAT csv, HEADER true);

-- ============================================================
-- Current challenge data (date-filtered)
-- ============================================================
\echo ''
\echo '--- Current: challenges ---'
COPY challenges FROM '/seed/current/challenges.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Current: challenge_weeks ---'
COPY challenge_weeks FROM '/seed/current/challenge_weeks.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Current: checkins ---'
COPY checkins (name, time, tier, day_of_week, text, challenge_week_id, id, challenger, tz)
    FROM '/seed/current/checkins.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Current: challenger_challenges ---'
COPY challenger_challenges FROM '/seed/current/challenger_challenges.csv' WITH (FORMAT csv, HEADER true);

\echo '--- Current: medals ---'
COPY medals FROM '/seed/current/medals.csv' WITH (FORMAT csv, HEADER true);

-- ============================================================
-- Verify
-- ============================================================
\echo ''
\echo '=============================='
\echo '  Tables loaded:'
\echo '=============================='
\echo '  challengers:      ' || (SELECT count(*) FROM challengers)
\echo '  challenges:       ' || (SELECT count(*) FROM challenges)
\echo '  challenge_weeks:  ' || (SELECT count(*) FROM challenge_weeks)
\echo '  checkins:         ' || (SELECT count(*) FROM checkins)
\echo '  challenger_challenges: ' || (SELECT count(*) FROM challenger_challenges)
\echo '  medals:           ' || (SELECT count(*) FROM medals)
\echo '=============================='
