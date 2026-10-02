-- Run once in a fresh dedicated database/schema using a migration role.
-- Deliberately no IF NOT EXISTS: incompatible/repeated migrations fail visibly.
CREATE TABLE tiee_runs (
    run_id text PRIMARY KEY CHECK (length(run_id) BETWEEN 1 AND 100),
    arm text NOT NULL CHECK (arm IN ('B0', 'B1', 'T')),
    iterations integer NOT NULL CHECK (iterations BETWEEN 0 AND 10000),
    processor_version text NOT NULL,
    policy_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE tiee_events (
    run_id text NOT NULL REFERENCES tiee_runs(run_id),
    event_id text NOT NULL CHECK (event_id ~ '^[0-9a-f]{64}$'),
    body_hash text NOT NULL CHECK (body_hash ~ '^[0-9a-f]{64}$'),
    state text NOT NULL CHECK (state IN ('PENDING', 'COMPLETED', 'REJECTED')),
    reason text,
    score double precision,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    PRIMARY KEY (run_id, event_id),
    CHECK ((state = 'PENDING' AND finished_at IS NULL AND reason IS NULL)
        OR (state <> 'PENDING' AND finished_at IS NOT NULL AND reason IS NOT NULL))
);
CREATE TABLE tiee_outputs (
    run_id text NOT NULL,
    event_id text NOT NULL,
    digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    processor_version text NOT NULL,
    PRIMARY KEY (run_id, event_id),
    FOREIGN KEY (run_id, event_id) REFERENCES tiee_events(run_id, event_id)
);
CREATE TABLE tiee_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL,
    event_id text NOT NULL,
    action text NOT NULL CHECK (action IN ('INTENT', 'COMPLETED', 'REJECTED', 'REPLAY', 'CONFLICT')),
    reason text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (run_id, event_id) REFERENCES tiee_events(run_id, event_id)
);
CREATE INDEX tiee_pending_idx ON tiee_events(run_id, created_at) WHERE state = 'PENDING';
CREATE INDEX tiee_audit_event_idx ON tiee_audit(run_id, event_id, audit_id);
