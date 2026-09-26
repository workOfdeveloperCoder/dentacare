-- Generic chatbot runtime extras.
-- Safe to run on an existing dental_chatbot_v2 database.

ALTER TABLE chat_flows
    ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE chat_nodes
    ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS chat_session_values (
    session_id UUID NOT NULL,
    input_key VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    label TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_chat_session_values
        PRIMARY KEY (session_id, input_key),

    CONSTRAINT fk_chat_session_values_session
        FOREIGN KEY (session_id)
        REFERENCES chat_sessions(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_chat_session_values_key
        CHECK (BTRIM(input_key) <> '')
);

CREATE INDEX IF NOT EXISTS idx_chat_session_values_session
    ON chat_session_values (session_id);

ALTER TABLE order_details
    ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE order_details
    ALTER COLUMN appointment_date DROP NOT NULL;

ALTER TABLE order_details
    ALTER COLUMN start_time DROP NOT NULL;

ALTER TABLE order_details
    ALTER COLUMN end_time DROP NOT NULL;

ALTER TABLE order_details
    DROP CONSTRAINT IF EXISTS chk_order_details_time;

ALTER TABLE order_details
    ADD CONSTRAINT chk_order_details_time
        CHECK (
            start_time IS NULL
            OR end_time IS NULL
            OR end_time > start_time
        );

ALTER TABLE order_details
    DROP CONSTRAINT IF EXISTS chk_order_details_item_type;

ALTER TABLE order_details
    ADD CONSTRAINT chk_order_details_item_type
        CHECK (
            item_type IN (
                'appointment',
                'service',
                'lead',
                'quote',
                'order'
            )
        );

COMMENT ON COLUMN chat_flows.config IS
    'Flow-level branding, navigation, and summary settings from flow.json.';

COMMENT ON COLUMN chat_nodes.config IS
    'Node plugins: action, options_source, on_input, on_select.';

COMMENT ON TABLE chat_session_values IS
    'Collected answers for the current session, keyed by input_key from flow.json.';

COMMENT ON COLUMN order_details.dentist_key IS
    'Generic provider key (dentist, region, salesperson). Kept for compatibility.';

COMMENT ON COLUMN order_details.dentist_name IS
    'Generic provider display name. Kept for compatibility.';

COMMENT ON COLUMN order_details.payload IS
    'Full collected field map from the flow, stored as JSON.';
