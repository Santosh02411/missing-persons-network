-- Runs automatically on first `docker compose up` (Postgres only executes
-- docker-entrypoint-initdb.d scripts against a fresh, empty data volume).
-- Creates a second database, separate from mpn_db, so the pytest suite never
-- touches development data.
CREATE DATABASE mpn_test_db;
\connect mpn_test_db
CREATE EXTENSION IF NOT EXISTS postgis;
