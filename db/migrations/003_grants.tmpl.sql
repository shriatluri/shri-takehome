-- Explicit, minimal grants for the runtime role. No DELETE anywhere, and no
-- UPDATE or DELETE on audit_log, which is what makes the log append-only for
-- the application.

GRANT SELECT ON employees, sanctions_list, schema_migrations TO {app_user};
GRANT SELECT, INSERT, UPDATE ON customers, cases TO {app_user};
-- Publishing a new rule version closes the current row and inserts the next
-- one, so the runtime role needs INSERT plus UPDATE on valid_to alone. A
-- table-wide UPDATE would let it rewrite the values earlier decisions used.
GRANT SELECT, INSERT ON policy_rules TO {app_user};
GRANT UPDATE (valid_to) ON policy_rules TO {app_user};
GRANT SELECT, INSERT ON audit_log TO {app_user};

GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {app_user};
