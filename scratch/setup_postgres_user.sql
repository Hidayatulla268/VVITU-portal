-- ====================================================================
-- VVITU PORTAL — Dedicated PostgreSQL Database User Setup Script
-- ====================================================================
-- Run this script as the PostgreSQL superuser ('postgres') to create
-- a dedicated database user ('vvitu_user') scoped ONLY to 'vvitu_portal'.

-- 1. Create the dedicated database
CREATE DATABASE vvitu_portal;

-- 2. Create the dedicated Django database user with a secure password
CREATE USER vvitu_user WITH PASSWORD 'Replace_With_Your_Secure_Password_2026!';

-- 3. Grant connection rights on the database to vvitu_user
GRANT CONNECT ON DATABASE vvitu_portal TO vvitu_user;

-- 4. Connect to the vvitu_portal database
\c vvitu_portal

-- 5. Grant schema usage and table privileges to vvitu_user
GRANT USAGE ON SCHEMA public TO vvitu_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vvitu_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vvitu_user;

-- 6. Ensure future tables created by Django auto-inherit privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vvitu_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vvitu_user;
