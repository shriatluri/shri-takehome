-- Explicit, minimal grants for the runtime role. No DELETE anywhere, and no
-- UPDATE or DELETE on audit_log, which is what makes the log append-only for
-- the application.

GRANT SELECT ON employees, sanctions_list, schema_migrations TO {app_user};
GRANT SELECT, INSERT, UPDATE ON customers, cases TO {app_user};
-- UPDATE on policy_rules only to close a version by setting valid_to.
GRANT SELECT, INSERT, UPDATE ON policy_rules TO {app_user};
GRANT SELECT, INSERT ON audit_log TO {app_user};

GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {app_user};
