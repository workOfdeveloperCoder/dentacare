from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from app.appointment_slots import AppointmentSlotService
from app.plugins import action, input_handler, option_source, select_handler
from app.templating import format_named


_slots = AppointmentSlotService()


@action("create_order")
def create_order(engine, cur, session, node, config, values):
    fields = config.get("fields") or {}

    customer_name = engine.value_of(values, fields.get("customer_name", "customer_name"))
    customer_phone = engine.value_of(values, fields.get("customer_phone", "customer_phone"))
    customer_email = engine.value_of(values, fields.get("customer_email", "customer_email"))

    item_key_field = fields.get("item_key", "service")
    provider_key_field = fields.get("provider_key")
    date_field = fields.get("date_field")
    slot_field = fields.get("slot_field")
    
    print("DEBUG slot_field:", repr(slot_field), flush=True)

    item_key = engine.value_of(values, item_key_field)
    provider_key = engine.value_of(values, provider_key_field) if provider_key_field else None
    date_value = engine.value_of(values, date_field) if date_field else None
    slot_id = engine.value_of(values, slot_field) if slot_field else None

    print("DEBUG slot_id:", repr(slot_id), flush=True)

    required = {
        fields.get("customer_name", "customer_name"): customer_name,
        fields.get("customer_phone", "customer_phone"): customer_phone,
    }

    if item_key_field:
        required[item_key_field] = item_key

    missing = [
        key
        for key, value in required.items()
        if value is None or str(value).strip() == ""
    ]

    if missing:
        raise ValueError(
            "Missing required information: " + ", ".join(missing)
        )

    item_name = engine.option_label(
        cur,
        session["flow_id"],
        fields.get("item_node"),
        item_key,
    ) if item_key else None

    if not item_name:
        item_name = engine.label_of(values, item_key_field) or item_key or "Item"

    provider_name = None

    if provider_key:
        provider_name = engine.option_label(
            cur,
            session["flow_id"],
            fields.get("provider_node"),
            provider_key,
        ) or engine.label_of(values, provider_key_field) or provider_key

    parsed_date = engine.parse_date(date_value) if date_value else None
    print("DEBUG slot_id:", repr(slot_id))
    print("DEBUG parsed_date:", repr(parsed_date))

    slot = _reserve_slot(cur, slot_id, parsed_date) if slot_id else None

    print("DEBUG reserved slot:", repr(slot))

    if slot:
        parsed_date = slot["appointment_date"]

    order_prefix = config.get("order_prefix") or engine.flow_config.get(
        "order_prefix",
        "ORD",
    )
    order_number = _order_number(order_prefix)
    payload = engine.plain_values(values)

    cur.execute(
        """
        INSERT INTO orders (
            order_number,
            session_id,
            customer_name,
            customer_phone,
            customer_email,
            status
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            'confirmed'
        )
        RETURNING id;
        """,
        (
            order_number,
            session["id"],
            customer_name,
            customer_phone,
            customer_email,
        ),
    )

    order_row = cur.fetchone()

    if order_row is None:
        raise ValueError("Unable to create the order.")

    order_id = order_row[0]
    item_type = config.get("item_type", "order")

    cur.execute(
        """
        INSERT INTO order_details (
            order_id,
            slot_id,
            item_type,
            service_key,
            service_name,
            dentist_key,
            dentist_name,
            appointment_date,
            start_time,
            end_time,
            quantity,
            payload
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            1,
            %s::jsonb
        )
        RETURNING id;
        """,
        (
            order_id,
            None,
            item_type,
            item_key or "item",
            item_name,
            provider_key,
            provider_name,
            parsed_date,
            slot['start_time'],
            slot['end_time'],
            json.dumps(payload),
        ),
    )

    detail_row = cur.fetchone()

    if detail_row is None:
        raise ValueError("Unable to create order details.")

    message = config.get("success_message")

    if not message:
        lines = ["Your request has been confirmed.", ""]

        if customer_name:
            lines.append(f"Name: {customer_name}")
        if item_name:
            lines.append(f"Item: {item_name}")
        if provider_name:
            lines.append(f"Assigned to: {provider_name}")
        if parsed_date:
            lines.append(f"Date: {parsed_date.strftime('%d %b %Y')}")
        if slot:
            lines.append(
                f"Time: {slot['start_time']} - {slot['end_time']}"
            )

        lines.extend(["", f"Reference: {order_number}"])
        message = "\n".join(lines)

    replacements = {
        "customer_name": customer_name or "",
        "item_name": item_name or "",
        "provider_name": provider_name or "",
        "order_number": order_number,
        "date_label": parsed_date.strftime("%d %b %Y") if parsed_date else "",
        "time_label": (
            f"{slot['start_time']} - {slot['end_time']}"
            if slot else ""
        ),
        **payload,
    }

    from app.templating import render_template

    rendered_message = render_template(
        message,
        replacements,
    )


    return {
        "message": rendered_message,
        "order_number": order_number,
    }


@input_handler("lookup_orders")
def lookup_orders(engine, cur, session, session_token, node, config, values, message):
    by = config.get("by", "phone")
    search_value = (message or "").strip()

    if by == "phone":
        records = _slots.find_appointments_by_phone(search_value)
    elif by == "email":
        records = _slots.find_appointments_by_email(search_value)
    elif by == "name":
        records = _slots.find_appointments_by_name(search_value)
    elif by == "booking_reference":
        records = _slots.find_appointments_by_booking_reference(search_value)
    else:
        raise ValueError(f"Unsupported lookup field: {by}")

    serialized = [_serialize_record(item) for item in records]

    engine.save_value(
        cur,
        session["id"],
        "_lookup_results",
        json.dumps(serialized),
        label="lookup_results",
    )
    engine.save_value(
        cur,
        session["id"],
        "_lookup_by",
        by,
        label=search_value,
    )

    if not serialized:
        empty_message = config.get(
            "empty_message",
            "I couldn't find a matching record with those details.",
        )
        return engine.build_response(
            session_token=session_token,
            node=node,
            prepared={"message": empty_message, "options": []},
        )

    results_key = config.get("results_node")

    if not results_key:
        raise ValueError("lookup_orders requires results_node in flow.json")

    results_node = engine.load_node_by_key(
        cur,
        session["flow_id"],
        results_key,
    )

    if results_node is None:
        raise ValueError(f"Results node not found: {results_key}")

    return engine.present_node(
        cur=cur,
        session=session,
        session_token=session_token,
        node=results_node,
    )


@option_source("lookup_results")
def lookup_results(engine, cur, session, node, config, values):
    raw = engine.value_of(values, "_lookup_results")

    if not raw:
        return []

    try:
        records = json.loads(raw)
    except json.JSONDecodeError:
        return []

    prefix = config.get("id_prefix", "ORDER_")
    label_template = config.get(
        "label_template",
        "{date} {start} - {end} | {service_name}",
    )

    options = []

    for record in records:
        order_id = record.get("order_id")
        option_key = f"{prefix}{order_id}"
        label = format_named(
            label_template,
            date=record.get("date", ""),
            start=record.get("start", ""),
            end=record.get("end", ""),
            service_name=record.get("service_name", ""),
            provider_name=record.get("provider_name", ""),
            customer_name=record.get("customer_name", ""),
            order_number=record.get("order_number", ""),
        )
        options.append(
            {
                "option_key": option_key,
                "key": option_key,
                "label": label,
                "next": None,
                "record": record,
            }
        )

    return options


@select_handler("show_order_details")
def show_order_details(
    engine,
    cur,
    session,
    session_token,
    node,
    config,
    values,
    option_key,
):
    prefix = config.get("id_prefix", "ORDER_")

    if not option_key or not option_key.startswith(prefix):
        return None

    order_id = option_key[len(prefix):].strip()

    if not order_id:
        return engine.build_response(
            session_token=session_token,
            node=node,
            error="That selection could not be found.",
        )

    record = _slots.get_appointment(order_id)

    if record is None or record.get("status") != "confirmed":
        return engine.build_response(
            session_token=session_token,
            node=node,
            error="That record is no longer active.",
        )

    serialized = _serialize_record(record)
    details_key = config.get("details_node")

    if not details_key:
        raise ValueError("show_order_details requires details_node in flow.json")

    details_node = engine.load_node_by_key(
        cur,
        session["flow_id"],
        details_key,
    )

    if details_node is None:
        raise ValueError(f"Details node not found: {details_key}")

    engine.save_value(
        cur,
        session["id"],
        "_selected_order_id",
        serialized["order_id"],
        label=serialized.get("order_number"),
    )

    message_template = config.get(
        "message_template",
        details_node.get("message") or "Record details",
    )
    message = format_named(message_template, **serialized)

    extra_options = []

    for option in config.get("extra_options", []):
        key = option.get("key")
        key_template = option.get("key_template")

        if key_template:
            key = format_named(key_template, **serialized)

        if not key:
            continue

        extra_options.append(
            {
                "option_key": key,
                "key": key,
                "label": option.get("label") or key,
                "next": option.get("next"),
            }
        )

    static_options = engine.load_options(cur, details_node["id"])
    options = extra_options + [
        item
        for item in static_options
        if item["option_key"] not in {opt["option_key"] for opt in extra_options}
    ]

    return engine.present_node(
        cur=cur,
        session=session,
        session_token=session_token,
        node=details_node,
        message_override=message,
        options_override=options,
    )


def _reserve_slot(cur, slot_id, parsed_date):
    if _is_uuid(slot_id):
        slot = _slots.reserve_slot(cur=cur, slot_id=slot_id)

        slot["appointment_date"] = parsed_date
        if parsed_date and slot["appointment_date"] != parsed_date:
            raise ValueError(
                "The selected slot does not match the selected date."
            )

        return slot

    if parsed_date is None:
        raise ValueError("The selected time is no longer available.")

    found = _slots.get_slot_by_date_time()

    if found is None:
        raise ValueError("The selected time is no longer available.")

    return _slots.reserve_slot(cur=cur,slot_id=found["id"])


def _is_uuid(value) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _serialize_record(record: dict[str, Any]) -> dict[str, str]:
    appointment_date = record.get("appointment_date")
    start_time = record.get("start_time")
    end_time = record.get("end_time")
    status = str(record.get("status") or "").strip()

    date_label = ""
    date_iso = ""

    if isinstance(appointment_date, date):
        date_label = appointment_date.strftime("%d %b %Y")
        date_iso = appointment_date.strftime("%Y-%m-%d")
    elif appointment_date:
        date_label = str(appointment_date)
        date_iso = str(appointment_date)

    return {
        "order_id": str(record.get("order_id") or ""),
        "order_number": str(record.get("order_number") or ""),
        "customer_name": str(record.get("customer_name") or ""),
        "customer_phone": str(record.get("customer_phone") or ""),
        "customer_email": str(record.get("customer_email") or ""),
        "service_key": str(record.get("service_key") or ""),
        "service_name": str(record.get("service_name") or ""),
        "provider_key": str(record.get("dentist_key") or record.get("provider_key") or ""),
        "provider_name": str(record.get("dentist_name") or record.get("provider_name") or ""),
        "date": date_iso,
        "date_label": date_label,
        "start": _format_time(start_time),
        "end": _format_time(end_time),
        "time_label": (
            f"{_format_ampm(start_time)} - {_format_ampm(end_time)}"
            if start_time and end_time else ""
        ),
        "status": status,
        "status_label": status.title() if status else "",
    }


def _order_number(prefix: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid4().hex[:8].upper()
    return f"{prefix}-{timestamp}-{short_uuid}"


def _format_time(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _format_ampm(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%I:%M %p")
    return str(value)
