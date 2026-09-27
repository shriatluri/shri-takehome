-- Synthetic seed data. Rerunnable: replaying this file restores the demo state.
-- Names, addresses and identifiers are invented; SSNs use the 900 prefix, which
-- is never issued as a real SSN.

TRUNCATE audit_log, cases, policy_rules, sanctions_list, customers, employees
    RESTART IDENTITY CASCADE;

-- Two analysts and two seniors so maker-checker approvals have distinct people.
INSERT INTO employees (id, name, team, level) VALUES
    (1, 'Alice Chen',      'compliance', 'analyst'),
    (2, 'Ben Ortiz',       'compliance', 'analyst'),
    (3, 'Dana Whitfield',  'compliance', 'senior'),
    (4, 'Marcus Lee',      'compliance', 'senior'),
    (5, 'Priya Raman',     'admin',      'senior'),
    (6, 'Owen Park',       'operations', 'analyst');
SELECT setval('employees_id_seq', (SELECT max(id) FROM employees));

-- document_quality is the vendor input; idv_status is the verdict it produced
-- (Clear -> Passed, Blurry -> Needs review, Fake -> Failed).
-- Marisol's expiry is relative to now() so the "expires within 30 days" risk
-- reason on her case stays true whenever the seed is replayed.
INSERT INTO customers
    (id, full_name, dob, country, address, ssn, document_expiry, document_quality,
     idv_status, idv_reason, idv_checked_at, account_status) VALUES
    (1,  'Jordan Vale',     '1988-04-12', 'United States', '412 Fenwick Ave, Portland, OR',   '900-12-3456', '2029-04-30', 'Clear',  'Passed',       'Document clear',            now() - interval '9 days', 'Active'),
    (2,  'Riley Sandoval',  '1975-11-02', 'Canada',        '88 Birchwood Cres, Halifax, NS',  '900-22-7781', '2028-01-15', 'Clear',  'Passed',       'Document clear',            now() - interval '9 days', 'Active'),
    (3,  'Noor Haddad',     '1992-06-21', 'Germany',       '17 Lindenstrasse, Leipzig',       '900-31-5502', '2031-09-01', 'Clear',  'Passed',       'Document clear',            now() - interval '8 days', 'Active'),
    (4,  'Casey Lindqvist', '1983-02-09', 'Sanctara',      '9 Harbour Row, Velin',            '900-44-9013', '2027-12-20', 'Clear',  'Passed',       'Document clear',            now() - interval '7 days', 'Pending'),
    (5,  'Marisol Adeyemi', '1996-08-30', 'United States', '2201 Cedar St, Austin, TX',       '900-55-2264', (CURRENT_DATE + 20), 'Blurry', 'Needs review', 'Document image blurry',     now() - interval '6 days', 'Pending'),
    (6,  'Tobias Renner',   '1970-01-17', 'Volgaria',      '5 Krasna Ulitsa, Ostmark',        '900-66-4417', '2030-03-11', 'Blurry', 'Needs review', 'Document image blurry',     now() - interval '5 days', 'Suspended'),
    (7,  'Elena Marchetti', '1990-05-25', 'Italy',         '44 Via dei Platani, Bologna',     '900-77-8890', '2029-07-19', 'Clear',  'Passed',       'Document clear',            now() - interval '5 days', 'Active'),
    (8,  'Devon Achebe',    '1986-09-14', 'United States', '77 Halsey Blvd, Newark, NJ',      '900-88-1123', '2025-11-02', 'Clear',  'Passed',       'Document clear',            now() - interval '4 days', 'Pending'),
    (9,  'Priyanka Bose',   '1994-12-03', 'Norsavia',      '12 Fjordgata, Halden',            '900-99-3345', '2032-02-28', 'Clear',  'Passed',       'Document clear',            now() - interval '3 days', 'Active'),
    (10, 'Samuel Okonjo',   '1979-07-08', 'United States', '310 Grand Ave, Oakland, CA',      '900-10-6678', '2028-06-14', 'Fake',   'Failed',       'Document detected as fake', now() - interval '3 days', 'Rejected'),
    (11, 'Hana Fujimoto',   '1998-03-19', 'Japan',         '3-2-1 Sakuragaoka, Kyoto',        '900-11-2290', '2030-08-08', 'Clear',  'Passed',       'Document clear',            now() - interval '2 days', 'Active'),
    (12, 'Victor Almeida',  '1968-10-27', 'Kestrelia',     '6 Praca do Norte, Ivanha',        '900-13-7734', '2026-01-09', 'Clear',  'Passed',       'Document clear',            now() - interval '1 day',  'Pending');
SELECT setval('customers_id_seq', (SELECT max(id) FROM customers));

-- Obviously fictional sanctions entries.
INSERT INTO sanctions_list
    (id, full_name, aliases, dob, nationality, entity_type, program, list_source, date_added) VALUES
    (1,  'Casey Lindquist',    ARRAY['C. Lindquist', 'Kasey Lindqvist'], '1983',       'Sanctara',  'individual', 'SANCTARA-1',  'Fictional Sanctions Register', '2021-03-14'),
    (2,  'Tobias Rennar',      ARRAY['T. Rennar'],                       '1970-01',    'Volgaria',  'individual', 'VOLGARIA-2',  'Fictional Sanctions Register', '2019-08-02'),
    (3,  'Viktor Almeda',      ARRAY['V. Almeda', 'Victor Almeida-Cruz'],'1968',       'Kestrelia', 'individual', 'KESTRELIA-1', 'Fictional Sanctions Register', '2020-11-30'),
    (4,  'Ingrid Solvang',     ARRAY['I. Solvang'],                      '1977-05-09', 'Norsavia',  'individual', 'NORSAVIA-3',  'Fictional Sanctions Register', '2022-01-21'),
    (5,  'Dmitri Volkanov',    ARRAY['D. Volkanov', 'Dima Volkanov'],    '1965',       'Volgaria',  'individual', 'VOLGARIA-1',  'Fictional Sanctions Register', '2018-06-17'),
    (6,  'Anselm Duarte',      ARRAY['A. Duarte'],                       '1981-12',    'Kestrelia', 'individual', 'KESTRELIA-4', 'Fictional Sanctions Register', '2023-02-09'),
    (7,  'Lucia Fernbach',     ARRAY['L. Fernbach'],                     '1990',       'Sanctara',  'individual', 'SANCTARA-2',  'Fictional Sanctions Register', '2021-09-28'),
    (8,  'Orion Haulage Ltd',  ARRAY['Orion Haulage'],                   NULL,         'Sanctara',  'entity',     'SANCTARA-3',  'Fictional Sanctions Register', '2020-04-04'),
    (9,  'Northwind Trust SA', ARRAY['Northwind Trust'],                 NULL,         'Norsavia',  'entity',     'NORSAVIA-1',  'Fictional Sanctions Register', '2019-12-12'),
    (10, 'Yusuf Karadag',      ARRAY['Y. Karadag'],                      '1972-07-30', 'Volgaria',  'individual', 'VOLGARIA-5',  'Fictional Sanctions Register', '2022-07-15'),
    (11, 'Mira Josefsen',      ARRAY['M. Josefsen'],                     '1985',       'Norsavia',  'individual', 'NORSAVIA-2',  'Fictional Sanctions Register', '2023-05-19'),
    (12, 'Tomas Belgrave',     ARRAY['T. Belgrave'],                     '1969-02',    'Kestrelia', 'individual', 'KESTRELIA-2', 'Fictional Sanctions Register', '2017-10-23'),
    (13, 'Sofia Brannigan',    ARRAY['S. Brannigan'],                    '1993-11-11', 'Sanctara',  'individual', 'SANCTARA-5',  'Fictional Sanctions Register', '2024-01-08'),
    (14, 'Halden Maritime Co', ARRAY['Halden Maritime'],                 NULL,         'Norsavia',  'entity',     'NORSAVIA-4',  'Fictional Sanctions Register', '2021-06-30'),
    (15, 'Emeka Nwosu-Bright', ARRAY['E. Nwosu'],                        '1974',       'Volgaria',  'individual', 'VOLGARIA-7',  'Fictional Sanctions Register', '2018-03-05');
SELECT setval('sanctions_list_id_seq', (SELECT max(id) FROM sanctions_list));

-- Version 1 of every rule. high_risk_countries is a comma-separated list of
-- fictional countries so no real jurisdiction is labelled high risk.
INSERT INTO policy_rules (rule_name, value, version, valid_from, valid_to, changed_by) VALUES
    ('auto_approve_below',        '30',                                        1, now() - interval '30 days', NULL, 5),
    ('escalate_above',            '70',                                        1, now() - interval '30 days', NULL, 5),
    ('sanctions_match_threshold', '85',                                        1, now() - interval '30 days', NULL, 5),
    ('doc_expiry_window_days',    '30',                                        1, now() - interval '30 days', NULL, 5),
    ('high_risk_countries',       'Sanctara,Volgaria,Norsavia,Kestrelia',      1, now() - interval '30 days', NULL, 5);

-- The values every rule held at version 1; each seeded case carries this as its
-- policy_snapshot, which is what scenario 5 compares against after the admin
-- publishes version 2.
DROP TABLE IF EXISTS v1_snapshot;
CREATE TEMP TABLE v1_snapshot AS
SELECT jsonb_object_agg(rule_name, jsonb_build_object('value', value, 'version', version))
           AS snapshot
FROM policy_rules
WHERE valid_to IS NULL;

-- Pre-existing queue so the app is not empty on first load.
INSERT INTO cases
    (id, customer_id, status, risk_score, risk_reasons, sanctions_match_id, assigned_to,
     recommended_by, recommendation, approved_by, decision_reason, policy_snapshot, created_at, decided_at) VALUES
    (1, 5, 'Open', 45,
     '[{"reason": "Needs review IDV", "points": 30}, {"reason": "document expires within 30 days", "points": 15}]'::jsonb,
     NULL, 1, NULL, NULL, NULL, NULL, (SELECT snapshot FROM v1_snapshot), now() - interval '6 days', NULL),
    (2, 4, 'Escalated', 85,
     '[{"reason": "high-risk country", "points": 25}, {"reason": "sanctions match", "points": 60}]'::jsonb,
     1, 2, NULL, NULL, NULL, NULL, (SELECT snapshot FROM v1_snapshot), now() - interval '7 days', NULL),
    (3, 9, 'Approved', 60,
     '[{"reason": "high-risk country", "points": 25}, {"reason": "incomplete address history", "points": 35}]'::jsonb,
     NULL, 1, NULL, NULL, 3, 'Reviewed supporting documents, no adverse findings',
     (SELECT snapshot FROM v1_snapshot), now() - interval '3 days', now() - interval '2 days'),
    -- Needs review parked pending a better document: case Suspended, customer Suspended.
    (4, 6, 'Suspended', 55,
     '[{"reason": "Needs review IDV", "points": 30}, {"reason": "high-risk country", "points": 25}]'::jsonb,
     NULL, 2, NULL, NULL, 2, 'Document unreadable, suspended pending a clearer copy',
     (SELECT snapshot FROM v1_snapshot), now() - interval '5 days', now() - interval '4 days');
SELECT setval('cases_id_seq', (SELECT max(id) FROM cases));
