-- The backend connects as this role at runtime. It does not own any table, so
-- FORCE ROW LEVEL SECURITY (added with the policies in a later migration) applies
-- to it and cannot be bypassed through table ownership.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {app_user_name}) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', {app_user_name}, {app_password});
  ELSE
    EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L', {app_user_name}, {app_password});
  END IF;
END
$$;

GRANT CONNECT ON DATABASE {database} TO {app_user};
GRANT USAGE ON SCHEMA public TO {app_user};

-- Nothing is granted by default; every table grant is explicit in 003_grants.
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {app_user};
