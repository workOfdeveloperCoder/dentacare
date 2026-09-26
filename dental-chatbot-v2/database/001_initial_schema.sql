
-- ============================================================
-- Generic JSON-driven chatbot schema
--
-- Tables:
--   1. chat_flows
--   2. chat_nodes
--   3. chat_node_options
--   4. chat_sessions
--   5. chat_session_history
--   6. chat_messages
--   6b. chat_session_values
--   7. appointment_slots
--   8. orders
--   9. order_details
--
-- PostgreSQL
-- ============================================================


-- ============================================================
-- 1. CHAT FLOWS
-- ============================================================

CREATE TABLE chat_flows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(150) NOT NULL,
    slug VARCHAR(100) NOT NULL,

    description TEXT,

    config JSONB NOT NULL DEFAULT '{}'::jsonb,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chat_flows_slug
        UNIQUE (slug),

    CONSTRAINT chk_chat_flows_name_not_empty
        CHECK (BTRIM(name) <> ''),

    CONSTRAINT chk_chat_flows_slug_not_empty
        CHECK (BTRIM(slug) <> '')
);


-- ============================================================
-- 2. CHAT NODES
-- ============================================================

CREATE TABLE chat_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    flow_id UUID NOT NULL,

    node_key VARCHAR(100) NOT NULL,

    node_type VARCHAR(30) NOT NULL,

    message TEXT NOT NULL,

    input_key VARCHAR(100),
    validation_type VARCHAR(30),

    is_start BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    next_node_id UUID,
    previous_node_id UUID,

    config JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chat_nodes_flow_node_key
        UNIQUE (flow_id, node_key),

    CONSTRAINT fk_chat_nodes_flow
        FOREIGN KEY (flow_id)
        REFERENCES chat_flows(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_chat_nodes_next
        FOREIGN KEY (next_node_id)
        REFERENCES chat_nodes(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_chat_nodes_previous
        FOREIGN KEY (previous_node_id)
        REFERENCES chat_nodes(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_chat_nodes_node_type
        CHECK (
            node_type IN (
                'message',
                'menu',
                'input',
                'phone',
                'email',
                'date',
                'time',
                'confirmation',
                'action',
                'end'
            )
        ),

    CONSTRAINT chk_chat_nodes_node_key_not_empty
        CHECK (BTRIM(node_key) <> ''),

    CONSTRAINT chk_chat_nodes_message_not_empty
        CHECK (BTRIM(message) <> '')
);


-- ============================================================
-- 3. CHAT NODE OPTIONS
-- ============================================================

CREATE TABLE chat_node_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    node_id UUID NOT NULL,

    option_key VARCHAR(100) NOT NULL,
    label VARCHAR(255) NOT NULL,

    next_node_id UUID,

    sort_order INTEGER NOT NULL DEFAULT 0,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chat_node_options_node_key
        UNIQUE (node_id, option_key),

    CONSTRAINT fk_chat_node_options_node
        FOREIGN KEY (node_id)
        REFERENCES chat_nodes(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_chat_node_options_next
        FOREIGN KEY (next_node_id)
        REFERENCES chat_nodes(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_chat_node_options_key_not_empty
        CHECK (BTRIM(option_key) <> ''),

    CONSTRAINT chk_chat_node_options_label_not_empty
        CHECK (BTRIM(label) <> ''),

    CONSTRAINT chk_chat_node_options_sort_order
        CHECK (sort_order >= 0)
);


-- ============================================================
-- 4. CHAT SESSIONS
-- ============================================================

CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_token UUID NOT NULL DEFAULT gen_random_uuid(),

    flow_id UUID NOT NULL,

    current_node_id UUID,

    status VARCHAR(20) NOT NULL DEFAULT 'active',

    channel VARCHAR(30) NOT NULL DEFAULT 'web',

    client_identifier VARCHAR(255),

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chat_sessions_session_token
        UNIQUE (session_token),

    CONSTRAINT fk_chat_sessions_flow
        FOREIGN KEY (flow_id)
        REFERENCES chat_flows(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_chat_sessions_current_node
        FOREIGN KEY (current_node_id)
        REFERENCES chat_nodes(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_chat_sessions_status
        CHECK (
            status IN (
                'active',
                'completed',
                'abandoned',
                'expired'
            )
        ),

    CONSTRAINT chk_chat_sessions_channel
        CHECK (BTRIM(channel) <> ''),

    CONSTRAINT chk_chat_sessions_dates
        CHECK (
            completed_at IS NULL
            OR completed_at >= started_at
        )
);


-- ============================================================
-- 5. CHAT SESSION HISTORY
-- ============================================================

CREATE TABLE chat_session_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_id UUID NOT NULL,

    node_id UUID NOT NULL,

    sequence_no INTEGER NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chat_session_history_sequence
        UNIQUE (session_id, sequence_no),

    CONSTRAINT fk_chat_session_history_session
        FOREIGN KEY (session_id)
        REFERENCES chat_sessions(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_chat_session_history_node
        FOREIGN KEY (node_id)
        REFERENCES chat_nodes(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_chat_session_history_sequence
        CHECK (sequence_no > 0)
);


-- ============================================================
-- 6. CHAT MESSAGES
-- ============================================================

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_id UUID NOT NULL,

    node_id UUID,

    sender VARCHAR(20) NOT NULL,

    message TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_chat_messages_session
        FOREIGN KEY (session_id)
        REFERENCES chat_sessions(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_chat_messages_node
        FOREIGN KEY (node_id)
        REFERENCES chat_nodes(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_chat_messages_sender
        CHECK (
            sender IN (
                'user',
                'bot',
                'system'
            )
        ),

    CONSTRAINT chk_chat_messages_message_not_empty
        CHECK (BTRIM(message) <> '')
);


-- ============================================================
-- 6b. SESSION VALUES
-- ============================================================

CREATE TABLE chat_session_values (
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


-- ============================================================
-- 7. APPOINTMENT SLOTS
-- ============================================================

CREATE TABLE appointment_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    appointment_date DATE NOT NULL,

    start_time TIME NOT NULL,
    end_time TIME NOT NULL,

    capacity INTEGER NOT NULL DEFAULT 1,
    booked_count INTEGER NOT NULL DEFAULT 0,

    status VARCHAR(20) NOT NULL DEFAULT 'available',

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_appointment_slots_time
        CHECK (end_time > start_time),

    CONSTRAINT chk_appointment_slots_capacity
        CHECK (capacity > 0),

    CONSTRAINT chk_appointment_slots_booked_count
        CHECK (
            booked_count >= 0
            AND booked_count <= capacity
        ),

    CONSTRAINT chk_appointment_slots_status
        CHECK (
            status IN (
                'available',
                'blocked',
                'full',
                'cancelled'
            )
        ),

    CONSTRAINT uq_appointment_slots_datetime
        UNIQUE (
            appointment_date,
            start_time,
            end_time
        )
);


-- ============================================================
-- 8. ORDERS
-- ============================================================

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    order_number VARCHAR(30) NOT NULL,

    session_id UUID NOT NULL,

    customer_name VARCHAR(150) NOT NULL,
    customer_phone VARCHAR(50) NOT NULL,
    customer_email VARCHAR(255),

    status VARCHAR(20) NOT NULL DEFAULT 'confirmed',

    notes TEXT,

    confirmed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    cancelled_at TIMESTAMPTZ,
    cancelled_reason TEXT,

    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_orders_order_number
        UNIQUE (order_number),

    CONSTRAINT fk_orders_session
        FOREIGN KEY (session_id)
        REFERENCES chat_sessions(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_orders_customer_name
        CHECK (BTRIM(customer_name) <> ''),

    CONSTRAINT chk_orders_customer_phone
        CHECK (BTRIM(customer_phone) <> ''),

    CONSTRAINT chk_orders_status
        CHECK (
            status IN (
                'confirmed',
                'cancelled',
                'completed',
                'no_show'
            )
        ),

    CONSTRAINT chk_orders_cancelled_data
        CHECK (
            (
                status = 'cancelled'
                AND cancelled_at IS NOT NULL
            )
            OR
            (
                status <> 'cancelled'
            )
        ),

    CONSTRAINT chk_orders_completed_data
        CHECK (
            (
                status = 'completed'
                AND completed_at IS NOT NULL
            )
            OR
            (
                status <> 'completed'
            )
        )
);


-- ============================================================
-- 9. ORDER DETAILS
-- ============================================================

CREATE TABLE order_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    order_id UUID NOT NULL,

    slot_id UUID,

    item_type VARCHAR(30) NOT NULL DEFAULT 'appointment',

    service_key VARCHAR(100) NOT NULL,
    service_name VARCHAR(255) NOT NULL,

    dentist_key VARCHAR(100),
    dentist_name VARCHAR(255),

    appointment_date DATE,

    start_time TIME,
    end_time TIME,

    quantity INTEGER NOT NULL DEFAULT 1,

    notes TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_order_details_order
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_order_details_slot
        FOREIGN KEY (slot_id)
        REFERENCES appointment_slots(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_order_details_item_type
        CHECK (
            item_type IN (
                'appointment',
                'service',
                'lead',
                'quote',
                'order'
            )
        ),

    CONSTRAINT chk_order_details_service_key
        CHECK (BTRIM(service_key) <> ''),

    CONSTRAINT chk_order_details_service_name
        CHECK (BTRIM(service_name) <> ''),

    CONSTRAINT chk_order_details_time
        CHECK (
            start_time IS NULL
            OR end_time IS NULL
            OR end_time > start_time
        ),

    CONSTRAINT chk_order_details_quantity
        CHECK (quantity > 0)
);


-- ============================================================
-- INDEXES
-- ============================================================


-- Chat flows

CREATE INDEX idx_chat_flows_active
    ON chat_flows (is_active);


-- Chat nodes

CREATE INDEX idx_chat_nodes_flow
    ON chat_nodes (flow_id);

CREATE INDEX idx_chat_nodes_next
    ON chat_nodes (next_node_id);

CREATE INDEX idx_chat_nodes_start
    ON chat_nodes (flow_id, is_start)
    WHERE is_start = TRUE;


-- Node options

CREATE INDEX idx_chat_node_options_node
    ON chat_node_options (node_id);

CREATE INDEX idx_chat_node_options_next
    ON chat_node_options (next_node_id);


-- Sessions

CREATE INDEX idx_chat_sessions_flow
    ON chat_sessions (flow_id);

CREATE INDEX idx_chat_sessions_status
    ON chat_sessions (status);

CREATE INDEX idx_chat_sessions_last_activity
    ON chat_sessions (last_activity_at DESC);

CREATE INDEX idx_chat_sessions_channel
    ON chat_sessions (channel);

CREATE INDEX idx_chat_sessions_current_node
    ON chat_sessions (current_node_id);


-- History

CREATE INDEX idx_chat_session_history_session
    ON chat_session_history (session_id, sequence_no DESC);

CREATE INDEX idx_chat_session_history_node
    ON chat_session_history (node_id);


-- Messages

CREATE INDEX idx_chat_messages_session
    ON chat_messages (session_id, created_at);

CREATE INDEX idx_chat_messages_node
    ON chat_messages (node_id);

CREATE INDEX idx_chat_session_values_session
    ON chat_session_values (session_id);


-- Appointment slots

CREATE INDEX idx_appointment_slots_date
    ON appointment_slots (appointment_date);

CREATE INDEX idx_appointment_slots_date_status
    ON appointment_slots (
        appointment_date,
        status
    );

CREATE INDEX idx_appointment_slots_available
    ON appointment_slots (
        appointment_date,
        start_time
    )
    WHERE status = 'available'
      AND booked_count < capacity;


-- Orders

CREATE INDEX idx_orders_status_created
    ON orders (
        status,
        created_at DESC
    );

CREATE INDEX idx_orders_customer_phone
    ON orders (customer_phone);

CREATE INDEX idx_orders_session
    ON orders (session_id);

CREATE INDEX idx_orders_confirmed_at
    ON orders (confirmed_at DESC);

CREATE INDEX idx_orders_cancelled_at
    ON orders (cancelled_at DESC)
    WHERE cancelled_at IS NOT NULL;


-- Order details

CREATE INDEX idx_order_details_order
    ON order_details (order_id);

CREATE INDEX idx_order_details_slot
    ON order_details (slot_id);

CREATE INDEX idx_order_details_date_time
    ON order_details (
        appointment_date,
        start_time
    );

CREATE INDEX idx_order_details_service
    ON order_details (service_key);

CREATE INDEX idx_order_details_dentist
    ON order_details (dentist_key);


-- ============================================================
-- COMMENTS
-- ============================================================

COMMENT ON TABLE chat_flows IS
    'Decision-tree chatbot flows.';

COMMENT ON TABLE chat_nodes IS
    'Individual steps/nodes in a chatbot flow.';

COMMENT ON TABLE chat_node_options IS
    'Selectable options belonging to menu nodes.';

COMMENT ON TABLE chat_sessions IS
    'Visitor conversation sessions. A session does not necessarily create an order.';

COMMENT ON TABLE chat_session_history IS
    'Node navigation history used for conversation state and Back navigation.';

COMMENT ON TABLE chat_messages IS
    'Conversation transcript between visitor, chatbot and system.';

COMMENT ON TABLE appointment_slots IS
    'Bookable appointment availability managed by the business.';

COMMENT ON TABLE orders IS
    'Confirmed customer orders/bookings. Cancelled orders are retained for history.';

COMMENT ON TABLE order_details IS
    'Services and appointment details belonging to an order.';


-- ============================================================
-- COMMIT
-- ============================================================

COMMIT;