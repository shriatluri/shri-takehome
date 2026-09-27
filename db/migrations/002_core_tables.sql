-- Core schema. One table per thing with its own lifecycle; everything else is a column.

CREATE TABLE employees (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    team        TEXT NOT NULL CHECK (team IN ('compliance', 'operations', 'admin')),
    level       TEXT NOT NULL CHECK (level IN ('analyst', 'senior')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    full_name       TEXT NOT NULL,
    dob             DATE NOT NULL,
    country         TEXT NOT NULL,
    address         TEXT NOT NULL,
    ssn             TEXT NOT NULL,
    document_expiry DATE,
    -- The input the mock IDV vendor judged, kept next to the verdict it produced
    -- so a reviewer can see why a customer landed where it did.
    document_quality TEXT CHECK (document_quality IN ('Clear', 'Blurry', 'Fake')),
    idv_status      TEXT NOT NULL DEFAULT 'Pending'
                    CHECK (idv_status IN ('Pending', 'Passed', 'Failed', 'Needs review')),
    idv_reason      TEXT,
    idv_checked_at  TIMESTAMPTZ,
    -- Suspended is reached when a reviewer parks a Needs-review case waiting for
    -- a clearer document. Unlike Rejected it is not terminal.
    account_status  TEXT NOT NULL DEFAULT 'Pending'
                    CHECK (account_status IN ('Pending', 'Active', 'Rejected', 'Suspended')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sanctions_list (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    aliases     TEXT[] NOT NULL DEFAULT '{}',
    -- Real sanctions lists often carry incomplete dates, e.g. '1974' or '1974-03'.
    dob         TEXT,
    nationality TEXT,
    entity_type TEXT NOT NULL DEFAULT 'individual'
                CHECK (entity_type IN ('individual', 'entity')),
    program     TEXT,
    list_source TEXT,
    date_added  DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Slowly changing dimension, type 2: an edit closes the current row and inserts
-- the next version. valid_to IS NULL marks the row in force today.
CREATE TABLE policy_rules (
    id         SERIAL PRIMARY KEY,
    rule_name  TEXT NOT NULL,
    value      TEXT NOT NULL,
    version    INTEGER NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to   TIMESTAMPTZ,
    changed_by INTEGER REFERENCES employees (id),
    UNIQUE (rule_name, version)
);

CREATE UNIQUE INDEX policy_rules_one_current
    ON policy_rules (rule_name) WHERE valid_to IS NULL;

CREATE TABLE cases (
    id                 SERIAL PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers (id),
    status             TEXT NOT NULL
                       CHECK (status IN ('Open', 'Escalated', 'Approved', 'Rejected', 'Suspended')),
    risk_score         INTEGER NOT NULL,
    -- [{"reason": "high-risk country", "points": 25}, ...]
    risk_reasons       JSONB NOT NULL DEFAULT '[]'::jsonb,
    sanctions_match_id INTEGER REFERENCES sanctions_list (id),
    assigned_to        INTEGER REFERENCES employees (id),
    recommended_by     INTEGER REFERENCES employees (id),
    recommendation     TEXT CHECK (recommendation IN ('Approve', 'Reject', 'Suspend')),
    approved_by        INTEGER REFERENCES employees (id),
    decision_reason    TEXT,
    -- Highest policy_rules.version in force when the case was scored.
    rule_version       INTEGER NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at         TIMESTAMPTZ,
    CONSTRAINT cases_no_self_approval
        CHECK (approved_by IS NULL OR recommended_by IS NULL OR approved_by <> recommended_by)
);

CREATE INDEX cases_assigned_to_idx ON cases (assigned_to);
CREATE INDEX cases_status_idx ON cases (status);

-- Append-only. hash = sha256(prev_hash || canonical row contents); the app role
-- is granted INSERT and SELECT only, so a broken chain means someone with owner
-- access edited history.
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
    employee_id INTEGER REFERENCES employees (id),
    action      TEXT NOT NULL,
    record_type TEXT NOT NULL,
    record_id   TEXT,
    details     JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_hash   TEXT,
    hash        TEXT NOT NULL
);
