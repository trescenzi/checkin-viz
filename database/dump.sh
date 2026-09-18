#! /bin/bash

set -euo pipefail

source .env
SEED_DIR="./database/seed"
BASE_DIR="$SEED_DIR/base"
CURRENT_DIR="$SEED_DIR/current"
export SOPS_AGE_RECIPIENTS=$(cat age-keys.txt)
export PGPASSWORD="$DB_PASSWORD"
mkdir -p "$BASE_DIR" "$CURRENT_DIR"

echo "Dumping seed data to ./database/db.dump.sops"
pg_dump -Fc \
  -t checkins -t challengers -t medals -t challenge_weeks -t challenger_challenges -t challenges \
  --schema-only --no-owner --no-acl \
  -f "$SEED_DIR/schema.dump" \
  -U $DB_USER -d projects -p 5432 -h $DB_HOST
echo "  ✓ schema.dump"

sops --encrypt ./database/seed/schema.dump > ./database/seed/schema.dump.sops

# ---------- Base data (Challenge 23) ----------
echo ""
echo "Dumping base data (Challenge 23)..."

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select * from challengers) to stdout with csv header" \
  > "$BASE_DIR/challengers.csv"
echo "  ✓ base/challengers.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select * from challenges where id = 23) to stdout with csv header" \
  > "$BASE_DIR/challenges.csv"
echo "  ✓ base/challenges.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select * from challenge_weeks where challenge_id = 23) to stdout with csv header" \
  > "$BASE_DIR/challenge_weeks.csv"
echo "  ✓ base/challenge_weeks.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (
    select name, time, tier, day_of_week, text, challenge_week_id, checkins.id, challenger, tz
    from checkins
    join challenge_weeks ON challenge_weeks.id = checkins.challenge_week_id
    where challenge_weeks.challenge_id = 23
  ) to stdout with csv header" \
  > "$BASE_DIR/checkins.csv"
echo "  ✓ base/checkins.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select * from challenger_challenges where challenge_id = 23) to stdout with csv header" \
  > "$BASE_DIR/challenger_challenges.csv"
echo "  ✓ base/challenger_challenges.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
 -c "copy (select * from medals where challenge_id = 23) to stdout with csv header" \
  > "$BASE_DIR/medals.csv"
echo "  ✓ base/medals.csv"

# ---------- Current challenge ----------
echo ""
echo "Dumping current challenge data..."

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select * from challenges c
    where (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date >= c.start
      and (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date <= c.end) to stdout with csv header" \
  > "$CURRENT_DIR/challenges.csv"
echo "  ✓ current/challenges.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select cw.* from challenge_weeks cw
  join challenges c on c.id = cw.challenge_id
  where (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date >= c.start
    and (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date <= c.end) to stdout with csv header" \
  > "$CURRENT_DIR/challenge_weeks.csv"
echo "  ✓ current/challenge_weeks.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (
  select ch.name, ch.time, ch.tier, ch.day_of_week, ch.text, ch.challenge_week_id, ch.id, ch.challenger, ch.tz
  from checkins ch
  join challenge_weeks cw ON cw.id = ch.challenge_week_id
  join challenges c on cw.challenge_id = c.id
  where (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date >= c.start
    and (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date <= c.end
) to stdout with csv header" \
  > "$CURRENT_DIR/checkins.csv"
echo "  ✓ current/checkins.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select cc.* from challenger_challenges cc
  join challenges c on c.id = cc.challenge_id
  where (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date >= c.start
    and (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date <= c.end) to stdout with csv header" \
  > "$CURRENT_DIR/challenger_challenges.csv"
echo "  ✓ current/challenger_challenges.csv"

psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -c "copy (select m.* from medals m
  join challenges c on c.id = m.challenge_id
  where (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date >= c.start
    and (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date <= c.end) to stdout with csv header" \
  > "$CURRENT_DIR/medals.csv"
echo "  ✓ current/medals.csv"

# ---------- Functions ----------
echo ""
echo "Dumping functions..."
psql  -U $DB_USER -d projects -p 5432 -h $DB_HOST \
  -A -t -c "SELECT pg_get_functiondef(oid) || ';' FROM pg_proc WHERE proname LIKE '%score%' ORDER BY proname;" \
  > "$SEED_DIR/functions.sql"
echo "  ✓ functions.sql"

echo ""
echo "Encrypting csvs..."
for f in database/seed/base/*.csv database/seed/current/*.csv database/seed/functions.sql; do
 sops --encrypt "$f" > "${f}.sops"
done
rm database/seed/base/*.csv database/seed/current/*.csv database/seed/schema.dump database/seed/functions.sql

echo ""
echo "========================================"
echo "  Dump complete!"
echo "========================================"
echo ""
echo "  $SEED_DIR/"
echo "  ├── base/           (static Challenge 23 data)"
echo "   ├── challengers.csv"
echo "   ├── challenges.csv"
echo "   ├── challenge_weeks.csv"
echo "   ├── checkins.csv"
echo "   ├── challenger_challenges.csv"
echo "   └── medals.csv"
echo "  ├── current/        (date-filtered active challenge)"
echo "   ├── challenges.csv"
echo "   ├── challenge_weeks.csv"
echo "   ├── checkins.csv"
echo "   ├── challenger_challenges.csv"
echo "   └── medals.csv"
echo "  ├── schema.dump     (table DDL)"
echo "  └── functions.sql   (function definitions)"
echo ""
