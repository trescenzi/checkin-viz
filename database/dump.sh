#! /bin/bash

source .env
echo "Dumping seed data to ./database/db.dump.sops"
export PGPASSWORD="$DB_PASSWORD"
pg_dump -Fc \
  -t checkins -t challengers -t medals -t challenge_weeks -t challenger_challenges -t challenges \
  --schema-only --no-owner --no-acl \
  -f ./database/db.dump \
  -U $DB_USER -d projects -p 5432 -h $DB_HOST

export SOPS_AGE_RECIPIENTS=$(cat age-keys.txt)
sops --encrypt ./database/db.dump > ./database/db.dump.sops
