-- Row-level security. The runtime role owns nothing, and every table here is
-- FORCE ROW LEVEL SECURITY, so these policies are the only way rows reach the
-- API — not a WHERE clause the application could forget.
--
-- The caller's identity arrives as `app.user_id`, set with SET LOCAL inside the
-- request transaction. Unset means no rows: an unauthenticated connection sees
-- an empty database rather than everything.

-- Only the id is carried in the setting; team and level are read from
-- `employees` here, so the database decides the role rather than trusting a
-- value the application derived from a request header.
CREATE FUNCTION app_user_id() RETURNS integer
    LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.user_id', true), '')::integer
$$;

-- The pipeline behind the customer submission form has no logged-in employee.
-- It runs under this reserved id, which no employee row can hold.
CREATE FUNCTION app_is_system() RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT app_user_id() = 0
$$;

-- p_level NULL matches any level on the team.
CREATE FUNCTION app_is(p_team text, p_level text DEFAULT NULL) RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1 FROM employees e
        WHERE e.id = app_user_id()
          AND e.team = p_team
          AND (p_level IS NULL OR e.level = p_level)
    )
$$;

-- Cases: the compliance queue. Operations and admin match no policy at all.
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases FORCE ROW LEVEL SECURITY;

-- FOR ALL, so an analyst cannot update a case they cannot see either.
CREATE POLICY cases_senior ON cases FOR ALL
    USING (app_is('compliance', 'senior'))
    WITH CHECK (app_is('compliance', 'senior'));

CREATE POLICY cases_analyst ON cases FOR ALL
    USING (app_is('compliance', 'analyst') AND assigned_to = app_user_id())
    WITH CHECK (app_is('compliance', 'analyst') AND assigned_to = app_user_id());

CREATE POLICY cases_system ON cases FOR ALL
    USING (app_is_system())
    WITH CHECK (app_is_system());

-- Customers are not row-filtered: a customer is not the unit of assignment, and
-- filtering them through case assignment would hide the customer attached to a
-- case a senior reassigns. Compliance sees customers, nobody else does.
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE ROW LEVEL SECURITY;

CREATE POLICY customers_compliance ON customers FOR ALL
    USING (app_is('compliance'))
    WITH CHECK (app_is('compliance'));

CREATE POLICY customers_system ON customers FOR ALL
    USING (app_is_system())
    WITH CHECK (app_is_system());

-- Policy rules are readable by everyone signed in, because scoring a submission
-- and explaining a past decision both need the values. Only admin publishes a
-- new version.
ALTER TABLE policy_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_rules FORCE ROW LEVEL SECURITY;

CREATE POLICY policy_rules_read ON policy_rules FOR SELECT
    USING (app_user_id() IS NOT NULL);

CREATE POLICY policy_rules_admin_insert ON policy_rules FOR INSERT
    WITH CHECK (app_is('admin'));

CREATE POLICY policy_rules_admin_close ON policy_rules FOR UPDATE
    USING (app_is('admin'))
    WITH CHECK (app_is('admin'));

-- `employees` and `sanctions_list` are deliberately left without policies: the
-- user switcher lists employees before anyone is signed in, and a sanctions
-- entry is reference data the runtime role can only read.
--
-- `audit_log` has none either. Its database-enforced property is that it is
-- append-only — the runtime role has no UPDATE or DELETE grant — while "only
-- admin reads the log" is enforced on the route. Restricting SELECT here would
-- mean no caller could read the previous hash to extend the chain.
