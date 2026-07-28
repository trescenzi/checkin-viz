#! /bin/bash

echo "------------ Creating Tables -------------"
# -h postgres works because the service's name is postgres
# and we're assuming this runs in docker
PGPASSWORD=password pg_restore -d projects -h postgres -U postgres -cCO /seed/schema.dump

echo "------- Beginning Database Seeding -------"
echo "------------------------------------------"

psql $LOCAL_DB_CONNECT_STRING -f /seed/load.sql

echo "--------- Done Database Seeding ----------"
echo "------------------------------------------"
