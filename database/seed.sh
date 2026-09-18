#! /bin/bash

set -euo pipefail

echo "------------------------------------------"
echo "-------- Dropping Existing Data ----------"
echo "------------------------------------------"
PGPASSWORD=password psql "$LOCAL_DB_CONNECT_STRING" -v ON_ERROR_STOP=1 -c "
  DROP SCHEMA public CASCADE;
  CREATE SCHEMA public;
  GRANT ALL ON SCHEMA public TO postgres;
  GRANT ALL ON SCHEMA public TO PUBLIC;
"

echo "------------------------------------------"
echo "------------ Creating Tables -------------"
echo "------------------------------------------"
# The local connection string uses the Docker Compose service name as its host.
PGPASSWORD=password pg_restore --dbname="$LOCAL_DB_CONNECT_STRING" --no-owner --exit-on-error /seed/schema.dump

echo "------------------------------------------"
echo "------- Beginning Database Seeding -------"
echo "------------------------------------------"

PGPASSWORD=password psql "$LOCAL_DB_CONNECT_STRING" -v ON_ERROR_STOP=1 -f /seed/load.sql

echo "------------------------------------------"
echo "----------- Done Seeding Data ------------"
echo "------------------------------------------"

echo "------------------------------------------"
echo "----------- Seeding Functions ------------"
echo "------------------------------------------"

PGPASSWORD=password psql "$LOCAL_DB_CONNECT_STRING" -v ON_ERROR_STOP=1 -f /seed/functions.sql

echo "------------------------------------------"
echo "--------- Done Database Seeding ----------"
echo "------------------------------------------"
