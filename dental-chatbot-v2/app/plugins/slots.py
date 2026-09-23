from __future__ import annotations

from typing import Any

from app.appointment_slots import AppointmentSlotService
from app.plugins import option_source


_slots = AppointmentSlotService()


@option_source("available_dates")
def available_dates(engine, cur, session, node, config, values):
    dates = _slots.get_available_dates()
    date_format = config.get("label_format", "%A, %d %B %Y")

    return [
        {
            "option_key": item.isoformat(),
            "key": item.isoformat(),
            "label": item.strftime(date_format),
            "next": None,
        }
        for item in dates
    ]


@option_source("available_slots")
def available_slots(engine, cur, session, node, config, values):
    date_field = config.get("date_field", "appointment_date")
    raw_date = engine.value_of(values, date_field)

    if not raw_date:
        return []

    parsed = engine.parse_date(raw_date)
    slots = _slots.get_available_slots(parsed)

    options = []

    for slot in slots:
        slot_id = str(slot["id"])
        start = _format_time(slot["start_time"])
        end = _format_time(slot["end_time"])
        label = f"{start} - {end}"

        options.append(
            {
                "option_key": slot_id,
                "key": slot_id,
                "label": label,
                "next": None,
            }
        )

    return options


def _format_time(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)
