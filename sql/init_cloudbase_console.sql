BEGIN;

CREATE SCHEMA IF NOT EXISTS sprout;
REVOKE ALL ON SCHEMA sprout FROM PUBLIC;

CREATE TABLE IF NOT EXISTS sprout.state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL,
    payload TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sprout.revisions (
    revision INTEGER PRIMARY KEY,
    payload TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sprout.learning_events (
    id TEXT PRIMARY KEY,
    request TEXT NOT NULL,
    result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sprout.sessions (
    id TEXT PRIMARY KEY,
    csrf TEXT NOT NULL,
    expires INTEGER NOT NULL,
    credential TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sprout.login_limit (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    failures INTEGER NOT NULL,
    reset_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sprout.auth_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    salt BYTEA NOT NULL
);

INSERT INTO sprout.state (id, revision, payload, updated)
VALUES (
    1, 0,
    '{"version":1,"child":null,"plans":[],"selectedPlanId":null}',
    to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"')
) ON CONFLICT (id) DO NOTHING;

INSERT INTO sprout.login_limit (id, failures, reset_at)
VALUES (1, 0, 0) ON CONFLICT (id) DO NOTHING;

INSERT INTO sprout.auth_config (id, salt)
VALUES (1, decode(replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''), 'hex'))
ON CONFLICT (id) DO NOTHING;

ALTER TABLE sprout.state ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprout.revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprout.learning_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprout.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprout.login_limit ENABLE ROW LEVEL SECURITY;
ALTER TABLE sprout.auth_config ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE sprout.state, sprout.revisions, sprout.learning_events,
    sprout.sessions, sprout.login_limit, sprout.auth_config FROM PUBLIC;

COMMIT;

SELECT tablename AS table_name, rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'sprout'
ORDER BY tablename;
