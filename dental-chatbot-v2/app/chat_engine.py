from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from app.db import ensure_schema, get_connection
from app.plugins import (
    ACTIONS,
    INPUT_HANDLERS,
    OPTION_SOURCES,
    SELECT_HANDLERS,
    load_plugins,
)
from app.templating import render_template
from app.validation import validate_input


NODE_COLUMNS = """
    id,
    node_key,
    node_type,
    message,
    input_key,
    validation_type,
    is_start,
    next_node_id,
    previous_node_id,
    COALESCE(config, '{}'::jsonb)
"""


class ChatEngine:
    """
    Generic JSON-driven decision-tree chatbot.

    Domain behavior (booking, lookup, branding, step order) comes from
    flow.json plus named plugins. This class has no dental-specific keys.
    """

    def __init__(self):
        ensure_schema()
        load_plugins()
        self.flow_config: dict[str, Any] = {}

    def start_session(
        self,
        flow_key: str,
        channel: str = "web",
        client_identifier: str | None = None,
    ) -> dict[str, Any]:
        if not flow_key or not flow_key.strip():
            raise ValueError("flow_key is required.")

        flow_key = flow_key.strip()

        with get_connection() as conn:
            with conn.cursor() as cur:
                flow = self._load_flow(cur, flow_key)
                self.flow_config = flow["config"]

                node = self._load_start_node(cur, flow["id"])

                if node is None:
                    raise ValueError(
                        f"No active start node configured for flow: {flow_key}"
                    )

                session_token = uuid4()

                cur.execute(
                    """
                    INSERT INTO chat_sessions (
                        session_token,
                        flow_id,
                        current_node_id,
                        status,
                        channel,
                        client_identifier,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, 'active', %s, %s, NOW(), NOW()
                    )
                    RETURNING id;
                    """,
                    (
                        session_token,
                        flow["id"],
                        node["id"],
                        channel,
                        client_identifier,
                    ),
                )

                session_row = cur.fetchone()

                if session_row is None:
                    raise ValueError("Unable to create chat session.")

                session = {
                    "id": session_row[0],
                    "session_token": session_token,
                    "flow_id": flow["id"],
                    "current_node_id": node["id"],
                    "status": "active",
                }

                response = self.present_node(
                    cur=cur,
                    session=session,
                    session_token=session_token,
                    node=node,
                    already_current=True,
                )

                conn.commit()
                return response

    def process_input(
        self,
        session_token,
        message: str | None = None,
        option_key: str | None = None,
    ) -> dict[str, Any]:
        if message is not None:
            message = message.strip()

        if option_key is not None:
            option_key = option_key.strip()

        with get_connection() as conn:
            with conn.cursor() as cur:
                session = self._load_session(cur, session_token)

                if session is None:
                    raise ValueError("Session not found.")

                flow = self._load_flow_by_id(cur, session["flow_id"])
                self.flow_config = flow["config"]
                navigation = self.flow_config.get("navigation") or {}

                if option_key == "__BACK__":
                    if navigation.get("back_enabled", True) is False:
                        raise ValueError("Back navigation is disabled for this flow.")

                    response = self._go_back(cur, session, session_token)
                    conn.commit()
                    return response

                if option_key == "__MAIN_MENU__":
                    if navigation.get("main_menu_enabled", True) is False:
                        raise ValueError("Main menu navigation is disabled for this flow.")

                    response = self._go_main_menu(cur, session, session_token)
                    conn.commit()
                    return response

                if session["status"] != "active":
                    raise ValueError(f"Session is not active: {session['status']}")

                node = self.load_node(
                    cur,
                    session["flow_id"],
                    session["current_node_id"],
                )

                if node is None:
                    raise ValueError("Current chat node not found.")

                if node["node_type"] == "end":
                    response = self._complete_session(cur, session, session_token, node)
                    conn.commit()
                    return response

                if node["node_type"] == "action":
                    response = self._run_action(cur, session, session_token, node)
                    conn.commit()
                    return response

                if option_key:
                    response = self._handle_option(
                        cur,
                        session,
                        session_token,
                        node,
                        option_key,
                    )
                    conn.commit()
                    return response

                if message is not None:
                    response = self._handle_message(
                        cur,
                        session,
                        session_token,
                        node,
                        message,
                    )
                    conn.commit()
                    return response

                raise ValueError("Either message or option_key is required.")

    def get_public_config(self, flow_key: str) -> dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                flow = self._load_flow(cur, flow_key)
                config = flow["config"] or {}
                branding = config.get("branding") or {}

                return {
                    "flow_key": flow["slug"],
                    "name": flow["name"],
                    "branding": {
                        "title": branding.get("title") or flow["name"],
                        "subtitle": branding.get("subtitle") or "",
                        "avatar": branding.get("avatar") or "💬",
                        "primary_color": branding.get("primary_color") or "#0f766e",
                        "powered_by": branding.get("powered_by") or flow["name"],
                        "placeholder": branding.get(
                            "placeholder",
                            "Type your message...",
                        ),
                    },
                    "navigation": config.get("navigation") or {
                        "back_enabled": True,
                        "main_menu_enabled": True,
                    },
                }

    def present_node(
        self,
        cur,
        session,
        session_token,
        node,
        message_override: str | None = None,
        options_override: list[dict[str, Any]] | None = None,
        already_current: bool = False,
    ) -> dict[str, Any]:
        if not already_current:
            self._move_session_to_node(cur, session["id"], node["id"])
            session["current_node_id"] = node["id"]

        if node["node_type"] == "action":
            return self._run_action(cur, session, session_token, node)

        values = self.load_values(cur, session["id"])
        prepared = self._prepare_node(cur, session, node, values)

        if message_override:
            prepared["message"] = message_override
        else:
            prepared["message"] = self._render_node_message(node, values)

        if options_override is not None:
            prepared["options"] = options_override

        self._store_dynamic_options(
            cur,
            session["id"],
            prepared.get("options") or [],
        )
        prepared["options"] = self._normalize_options(
            prepared.get("options") or []
        )

        session_status = "active"

        if node["node_type"] == "end":
            session_status = self._mark_completed(cur, session["id"])

        prepared["session_status"] = session_status

        self._add_history(cur, session["id"], node["id"])
        self._add_message(
            cur,
            session["id"],
            node["id"],
            "bot",
            prepared["message"],
        )

        return self.build_response(
            session_token=session_token,
            node=node,
            prepared=prepared,
        )

    def build_response(
        self,
        session_token,
        node,
        prepared: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        prepared = prepared or {}
        options = self._normalize_options(prepared.get("options") or [])

        response = {
            "session_token": str(session_token),
            "node": {
                "id": str(node["id"]),
                "key": node["node_key"],
                "type": node["node_type"],
                "message": prepared.get("message", node["message"]),
                "input_key": node["input_key"],
                "validation_type": node["validation_type"],
                "options": options,
            },
            "session": {
                "status": prepared.get("session_status", "active"),
            },
        }

        if error:
            response["error"] = error

        return response

    def load_node(self, cur, flow_id, node_id) -> dict[str, Any] | None:
        cur.execute(
            f"""
            SELECT {NODE_COLUMNS}
            FROM chat_nodes
            WHERE id = %s
              AND flow_id = %s
              AND is_active = TRUE
            LIMIT 1;
            """,
            (node_id, flow_id),
        )
        row = cur.fetchone()
        return self._node_from_row(row) if row else None

    def load_node_by_key(self, cur, flow_id, node_key) -> dict[str, Any] | None:
        cur.execute(
            f"""
            SELECT {NODE_COLUMNS}
            FROM chat_nodes
            WHERE flow_id = %s
              AND node_key = %s
              AND is_active = TRUE
            LIMIT 1;
            """,
            (flow_id, node_key),
        )
        row = cur.fetchone()
        return self._node_from_row(row) if row else None

    def load_options(self, cur, node_id) -> list[dict[str, Any]]:
        cur.execute(
            """
            SELECT option_key, label, next_node_id
            FROM chat_node_options
            WHERE node_id = %s
              AND is_active = TRUE
            ORDER BY sort_order ASC, label ASC;
            """,
            (node_id,),
        )

        options = []

        for row in cur.fetchall():
            options.append(
                {
                    "option_key": row[0],
                    "key": row[0],
                    "label": row[1],
                    "next_node_id": row[2],
                }
            )

        return options

    def load_values(self, cur, session_id) -> dict[str, dict[str, Any]]:
        cur.execute(
            """
            SELECT input_key, value, label
            FROM chat_session_values
            WHERE session_id = %s;
            """,
            (session_id,),
        )

        values = {
            row[0]: {"value": row[1], "label": row[2]}
            for row in cur.fetchall()
        }

        if values:
            return values

        cur.execute(
            """
            SELECT n.input_key, m.message
            FROM chat_messages m
            JOIN chat_nodes n ON n.id = m.node_id
            WHERE m.session_id = %s
              AND m.sender = 'user'
              AND n.input_key IS NOT NULL
            ORDER BY m.created_at ASC;
            """,
            (session_id,),
        )

        for row in cur.fetchall():
            values[row[0]] = {"value": row[1], "label": row[1]}

        return values

    def save_value(self, cur, session_id, input_key, value, label=None):
        if not input_key or value is None:
            return

        value = str(value).strip()

        if not value:
            return

        cur.execute(
            """
            INSERT INTO chat_session_values (
                session_id,
                input_key,
                value,
                label,
                updated_at
            )
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (session_id, input_key)
            DO UPDATE SET
                value = EXCLUDED.value,
                label = EXCLUDED.label,
                updated_at = NOW();
            """,
            (session_id, input_key, value, label),
        )

    def value_of(self, values: dict[str, dict[str, Any]], key: str | None) -> str | None:
        if not key:
            return None

        entry = values.get(key)

        if not entry:
            return None

        return entry.get("value")

    def label_of(self, values: dict[str, dict[str, Any]], key: str | None) -> str | None:
        if not key:
            return None

        entry = values.get(key)

        if not entry:
            return None

        return entry.get("label") or entry.get("value")

    def plain_values(self, values: dict[str, dict[str, Any]]) -> dict[str, str]:
        return {
            key: str(item.get("label") or item.get("value") or "")
            for key, item in values.items()
            if not key.startswith("_")
        }

    def option_label(self, cur, flow_id, node_key, option_key) -> str | None:
        if not node_key or not option_key:
            return None

        cur.execute(
            """
            SELECT o.label
            FROM chat_node_options o
            JOIN chat_nodes n ON n.id = o.node_id
            WHERE n.flow_id = %s
              AND n.node_key = %s
              AND o.option_key = %s
              AND o.is_active = TRUE
            LIMIT 1;
            """,
            (flow_id, node_key, option_key),
        )

        row = cur.fetchone()
        return row[0] if row else None

    def parse_date(self, value) -> date:
        if isinstance(value, date):
            return value

        value = str(value).strip()
        formats = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y")

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Invalid date: {value}")

    def _handle_option(self, cur, session, session_token, node, option_key):
        config = node.get("config") or {}
        on_select = config.get("on_select")

        if on_select:
            handler_name = on_select.get("handler")
            handler = SELECT_HANDLERS.get(handler_name)

            if handler is None:
                raise ValueError(f"Unknown on_select handler: {handler_name}")

            values = self.load_values(cur, session["id"])
            result = handler(
                self,
                cur,
                session,
                session_token,
                node,
                on_select,
                values,
                option_key,
            )

            if result is not None:
                return result

        db_option = self._find_db_option(cur, node["id"], option_key)

        if db_option:
            self._save_user_choice(
                cur,
                session["id"],
                node,
                option_key,
                db_option["label"],
            )
            next_node = self._node_from_option_or_next(
                cur,
                session,
                node,
                db_option.get("next_node_id"),
            )
            return self.present_node(cur, session, session_token, next_node)

        dynamic = self._find_dynamic_option(cur, session["id"], option_key)

        if dynamic:
            self._save_user_choice(
                cur,
                session["id"],
                node,
                option_key,
                dynamic.get("label"),
            )
            next_node = self._resolve_next(
                cur,
                session,
                node,
                dynamic.get("next"),
            )
            return self.present_node(cur, session, session_token, next_node)

        if config.get("options_source"):
            values = self.load_values(cur, session["id"])
            live_options = self._options_from_source(cur, session, node, values)

            match = next(
                (
                    item
                    for item in live_options
                    if item.get("option_key") == option_key
                ),
                None,
            )

            if match:
                self._save_user_choice(
                    cur,
                    session["id"],
                    node,
                    option_key,
                    match.get("label"),
                )
                next_node = self._advance_to_next_node(cur, session, node)
                return self.present_node(cur, session, session_token, next_node)

        return self.build_response(
            session_token=session_token,
            node=node,
            prepared=self._prepare_node(
                cur,
                session,
                node,
                self.load_values(cur, session["id"]),
            ),
            error=(
                "That option is not available. "
                "Please select one of the available options."
            ),
        )

    def _handle_message(self, cur, session, session_token, node, message):
        if node["validation_type"]:
            validation = validate_input(node["validation_type"], message)

            if not validation.valid:
                return self.build_response(
                    session_token=session_token,
                    node=node,
                    prepared=self._prepare_node(
                        cur,
                        session,
                        node,
                        self.load_values(cur, session["id"]),
                    ),
                    error=validation.message,
                )

        self._save_user_choice(cur, session["id"], node, message, message)

        on_input = (node.get("config") or {}).get("on_input")

        if on_input:
            handler_name = on_input.get("handler")
            handler = INPUT_HANDLERS.get(handler_name)

            if handler is None:
                raise ValueError(f"Unknown on_input handler: {handler_name}")

            values = self.load_values(cur, session["id"])
            result = handler(
                self,
                cur,
                session,
                session_token,
                node,
                on_input,
                values,
                message,
            )

            if result is not None:
                return result

        next_node = self._advance_to_next_node(cur, session, node)
        return self.present_node(cur, session, session_token, next_node)

    def _run_action(self, cur, session, session_token, node):
        config = (node.get("config") or {}).get("action") or {}
        handler_name = config.get("handler")

        if not handler_name:
            raise ValueError(
                f"Action node '{node['node_key']}' is missing action.handler in flow.json"
            )

        handler = ACTIONS.get(handler_name)

        if handler is None:
            raise ValueError(f"Unknown action handler: {handler_name}")

        values = self.load_values(cur, session["id"])
        result = handler(self, cur, session, node, config, values) or {}
        next_node = self._advance_to_next_node(cur, session, node)

        return self.present_node(
            cur,
            session,
            session_token,
            next_node,
            message_override=result.get("message"),
        )

    def _prepare_node(self, cur, session, node, values) -> dict[str, Any]:
        options = []
        config = node.get("config") or {}

        if config.get("options_source"):
            options = self._options_from_source(cur, session, node, values)
        elif node["node_type"] in {"menu", "confirmation"}:
            options = self.load_options(cur, node["id"])
        elif node["node_type"] in {"date", "time"}:
            options = self.load_options(cur, node["id"])

        return {
            "message": self._render_node_message(node, values),
            "options": options,
        }

    def _options_from_source(self, cur, session, node, values):
        source = (node.get("config") or {}).get("options_source") or {}
        provider = source.get("provider")
        handler = OPTION_SOURCES.get(provider)

        if handler is None:
            raise ValueError(f"Unknown options_source provider: {provider}")

        return handler(self, cur, session, node, source, values)

    def _render_node_message(self, node, values) -> str:
        template = node.get("message") or ""
        context = self.plain_values(values)
        context["summary"] = self._summary_text(values)
        return render_template(template, context) or template

    def _summary_text(self, values) -> str:
        fields = self.flow_config.get("summary_fields") or []
        lines = []

        for field in fields:
            label = field.replace("_", " ").title()
            value = self.label_of(values, field) or self.value_of(values, field)

            if value:
                lines.append(f"{label}: {value}")

        return "\n".join(lines)

    def _save_user_choice(self, cur, session_id, node, value, label):
        self._add_message(cur, session_id, node["id"], "user", value)
        self._add_history(cur, session_id, node["id"])

        input_key = node.get("input_key")

        if input_key:
            self.save_value(cur, session_id, input_key, value, label)

    def _store_dynamic_options(self, cur, session_id, options):
        serializable = []

        for option in options:
            serializable.append(
                {
                    "option_key": option.get("option_key") or option.get("key"),
                    "label": option.get("label"),
                    "next": option.get("next"),
                }
            )

        self.save_value(
            cur,
            session_id,
            "_dynamic_options",
            json.dumps(serializable),
            label="options",
        )

    def _find_dynamic_option(self, cur, session_id, option_key):
        values = self.load_values(cur, session_id)
        raw = self.value_of(values, "_dynamic_options")

        if not raw:
            return None

        try:
            options = json.loads(raw)
        except json.JSONDecodeError:
            return None

        for option in options:
            if option.get("option_key") == option_key:
                return option

        return None

    def _find_db_option(self, cur, node_id, option_key):
        cur.execute(
            """
            SELECT id, option_key, label, next_node_id
            FROM chat_node_options
            WHERE node_id = %s
              AND option_key = %s
              AND is_active = TRUE
            LIMIT 1;
            """,
            (node_id, option_key),
        )

        row = cur.fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "option_key": row[1],
            "label": row[2],
            "next_node_id": row[3],
        }

    def _node_from_option_or_next(self, cur, session, node, next_node_id):
        if next_node_id:
            next_node = self.load_node(cur, session["flow_id"], next_node_id)

            if next_node is None:
                raise ValueError("Next chat node not found.")

            return next_node

        return self._advance_to_next_node(cur, session, node)

    def _resolve_next(self, cur, session, node, next_key):
        if next_key:
            next_node = self.load_node_by_key(cur, session["flow_id"], next_key)

            if next_node is None:
                raise ValueError(f"Next node not found: {next_key}")

            return next_node

        if node.get("next_node_id"):
            return self._advance_to_next_node(cur, session, node)

        return node

    def _advance_to_next_node(self, cur, session, node):
        if node["next_node_id"] is None:
            raise ValueError(
                f"No next node configured for {node['node_key']}"
            )

        next_node = self.load_node(cur, session["flow_id"], node["next_node_id"])

        if next_node is None:
            raise ValueError("Next chat node not found.")

        return next_node

    def _go_back(self, cur, session, session_token):
        current_node = self.load_node(
            cur,
            session["flow_id"],
            session["current_node_id"],
        )

        if current_node is None:
            raise ValueError("Current chat node not found.")

        previous_node_id = current_node["previous_node_id"]

        if previous_node_id is None:
            return self.build_response(
                session_token=session_token,
                node=current_node,
                error="You are already at the beginning of this conversation.",
            )

        previous_node = self.load_node(
            cur,
            session["flow_id"],
            previous_node_id,
        )

        if previous_node is None:
            raise ValueError("Previous chat node not found.")

        return self.present_node(cur, session, session_token, previous_node)

    def _go_main_menu(self, cur, session, session_token):
        navigation = self.flow_config.get("navigation") or {}
        menu_key = navigation.get("main_menu_node") or "MAIN_MENU"
        main_menu = self.load_node_by_key(cur, session["flow_id"], menu_key)

        if main_menu is None:
            main_menu = self._load_start_node(cur, session["flow_id"])

        if main_menu is None:
            raise ValueError("Main menu node not found.")

        return self.present_node(cur, session, session_token, main_menu)

    def _complete_session(self, cur, session, session_token, node):
        status = self._mark_completed(cur, session["id"])
        return self.build_response(
            session_token=session_token,
            node=node,
            prepared={"session_status": status, "options": []},
        )

    def _mark_completed(self, cur, session_id) -> str:
        cur.execute(
            """
            UPDATE chat_sessions
            SET status = 'completed', updated_at = NOW()
            WHERE id = %s
            RETURNING status;
            """,
            (session_id,),
        )
        row = cur.fetchone()

        if row is None:
            raise ValueError("Unable to complete chat session.")

        return row[0]

    def _move_session_to_node(self, cur, session_id, node_id):
        cur.execute(
            """
            UPDATE chat_sessions
            SET current_node_id = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING current_node_id;
            """,
            (node_id, session_id),
        )

        if cur.fetchone() is None:
            raise ValueError("Unable to update chat session.")

    def _load_session(self, cur, session_token):
        cur.execute(
            """
            SELECT
                id,
                session_token,
                flow_id,
                current_node_id,
                status,
                channel,
                client_identifier,
                created_at,
                updated_at
            FROM chat_sessions
            WHERE session_token = %s
            LIMIT 1;
            """,
            (session_token,),
        )

        row = cur.fetchone()

        if row is None:
            return None

        return {
            "id": row[0],
            "session_token": row[1],
            "flow_id": row[2],
            "current_node_id": row[3],
            "status": row[4],
            "channel": row[5],
            "client_identifier": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }

    def _load_flow(self, cur, flow_key):
        cur.execute(
            """
            SELECT id, name, slug, description, COALESCE(config, '{}'::jsonb)
            FROM chat_flows
            WHERE slug = %s
              AND is_active = TRUE
            LIMIT 1;
            """,
            (flow_key,),
        )

        row = cur.fetchone()

        if row is None:
            raise ValueError(f"Active flow not found: {flow_key}")

        return {
            "id": row[0],
            "name": row[1],
            "slug": row[2],
            "description": row[3],
            "config": row[4] or {},
        }

    def _load_flow_by_id(self, cur, flow_id):
        cur.execute(
            """
            SELECT id, name, slug, description, COALESCE(config, '{}'::jsonb)
            FROM chat_flows
            WHERE id = %s
            LIMIT 1;
            """,
            (flow_id,),
        )

        row = cur.fetchone()

        if row is None:
            raise ValueError("Flow not found for session.")

        return {
            "id": row[0],
            "name": row[1],
            "slug": row[2],
            "description": row[3],
            "config": row[4] or {},
        }

    def _load_start_node(self, cur, flow_id):
        cur.execute(
            f"""
            SELECT {NODE_COLUMNS}
            FROM chat_nodes
            WHERE flow_id = %s
              AND is_start = TRUE
              AND is_active = TRUE
            LIMIT 1;
            """,
            (flow_id,),
        )
        row = cur.fetchone()
        return self._node_from_row(row) if row else None

    def _node_from_row(self, row) -> dict[str, Any]:
        config = row[9] if len(row) > 9 else {}

        if isinstance(config, str):
            config = json.loads(config)

        return {
            "id": row[0],
            "node_key": row[1],
            "node_type": row[2],
            "message": row[3],
            "input_key": row[4],
            "validation_type": row[5],
            "is_start": row[6],
            "next_node_id": row[7],
            "previous_node_id": row[8],
            "config": config or {},
        }

    def _normalize_options(self, options):
        normalized = []

        for option in options:
            key = option.get("option_key") or option.get("key")

            if not key:
                continue

            normalized.append(
                {
                    "option_key": key,
                    "key": key,
                    "label": option.get("label") or key,
                }
            )

        return normalized

    def _add_history(self, cur, session_id, node_id):
        cur.execute(
            """
            SELECT COALESCE(MAX(sequence_no), 0)
            FROM chat_session_history
            WHERE session_id = %s;
            """,
            (session_id,),
        )
        sequence_no = (cur.fetchone()[0] or 0) + 1

        cur.execute(
            """
            INSERT INTO chat_session_history (
                session_id, node_id, sequence_no
            )
            VALUES (%s, %s, %s);
            """,
            (session_id, node_id, sequence_no),
        )

    def _add_message(self, cur, session_id, node_id, sender, message):
        if message is None:
            return

        message = str(message).strip()

        if not message:
            return

        cur.execute(
            """
            INSERT INTO chat_messages (
                session_id, node_id, sender, message
            )
            VALUES (%s, %s, %s, %s);
            """,
            (session_id, node_id, sender, message),
        )
