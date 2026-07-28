#! /bin/bash

echo "------------------------------------------"
echo "-------- Dropping Existing Data ----------"
echo "------------------------------------------"
PGPASSWORD=password psql -h postgres -U postgres -c "
  DROP SCHEMA public CASCADE;
  CREATE SCHEMA public;
  GRANT ALL ON SCHEMA public TO postgres;
  GRANT ALL ON SCHEMA public TO PUBLIC;
"

echo "------------------------------------------"
echo "------------ Creating Tables -------------"
echo "------------------------------------------"
# -h postgres works because the service's name is postgres
# and we're assuming this runs in docker
PGPASSWORD=password pg_restore -h postgres -U postgres --no-owner --clean --create -f /seed/schema.dump

echo "------------------------------------------"
echo "------- Beginning Database Seeding -------"
echo "------------------------------------------"

PGPASSWORD=password psql $LOCAL_DB_CONNECT_STRING -f /seed/load.sql

echo "------------------------------------------"
echo "----------- Done Seeding Data ------------"
echo "------------------------------------------"

echo "------------------------------------------"
echo "----------- Seeding Functions ------------"
echo "------------------------------------------"

PGPASSWORD=password psql $LOCAL_DB_CONNECT_STRING -f /seed/functions.sql

echo "------------------------------------------"
echo "--------- Done Database Seeding ----------"
echo "------------------------------------------"
