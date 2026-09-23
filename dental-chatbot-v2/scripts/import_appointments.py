import json
from pathlib import Path
from datetime import date, time

from app.db import get_connection


JSON_FILE = Path("flow/appointments.json")

VALID_STATUSES = {
    "available",
    "blocked",
    "full",
    "cancelled",
}


def load_json():
    if not JSON_FILE.exists():
        raise FileNotFoundError(
            f"Appointment JSON file not found: {JSON_FILE}"
        )

    with JSON_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_appointments(data):
    if not isinstance(data, dict):
        raise ValueError(
            "Appointment JSON root must be an object."
        )

    if not data.get("service_key"):
        raise ValueError(
            "Missing service_key."
        )

    appointments = data.get("appointments")

    if not isinstance(appointments, list):
        raise ValueError(
            "appointments must be a list."
        )

    for appointment in appointments:

        appointment_date = appointment.get("date")

        if not appointment_date:
            raise ValueError(
                "Missing appointment date."
            )

        try:
            date.fromisoformat(appointment_date)
        except ValueError:
            raise ValueError(
                f"Invalid appointment date: {appointment_date}"
            )

        slots = appointment.get("slots")

        if not isinstance(slots, list):
            raise ValueError(
                f"Slots must be a list for {appointment_date}."
            )

        for slot in slots:

            start_time = slot.get("start_time")
            end_time = slot.get("end_time")
            capacity = slot.get("capacity")
            status = slot.get(
                "status",
                "available",
            )

            if not start_time:
                raise ValueError(
                    f"Missing start_time for {appointment_date}."
                )

            if not end_time:
                raise ValueError(
                    f"Missing end_time for {appointment_date}."
                )

            try:
                parsed_start = time.fromisoformat(
                    start_time
                )

                parsed_end = time.fromisoformat(
                    end_time
                )

            except ValueError:
                raise ValueError(
                    f"Invalid time: "
                    f"{start_time} - {end_time}"
                )

            if parsed_end <= parsed_start:
                raise ValueError(
                    f"end_time must be after start_time: "
                    f"{start_time} - {end_time}"
                )

            if not isinstance(capacity, int):
                raise ValueError(
                    "capacity must be an integer."
                )

            if capacity <= 0:
                raise ValueError(
                    "capacity must be greater than zero."
                )

            if status not in VALID_STATUSES:
                raise ValueError(
                    f"Invalid status: {status}"
                )


def import_appointments(data):

    inserted = 0
    updated = 0

    with get_connection() as conn:

        with conn.cursor() as cur:

            for appointment in data["appointments"]:

                appointment_date = appointment["date"]

                for slot in appointment["slots"]:

                    cur.execute(
                        """
                        INSERT INTO appointment_slots (
                            appointment_date,
                            start_time,
                            end_time,
                            capacity,
                            booked_count,
                            status,
                            notes
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            0,
                            %s,
                            %s
                        )
                        ON CONFLICT (
                            appointment_date,
                            start_time,
                            end_time
                        )
                        DO UPDATE SET
                            capacity = EXCLUDED.capacity,
                            status = EXCLUDED.status,
                            notes = EXCLUDED.notes,
                            updated_at = NOW()
                        RETURNING
                            xmax = 0;
                        """,
                        (
                            appointment_date,
                            slot["start_time"],
                            slot["end_time"],
                            slot["capacity"],
                            slot.get(
                                "status",
                                "available",
                            ),
                            slot.get("notes"),
                        ),
                    )

                    result = cur.fetchone()

                    if result[0]:
                        inserted += 1
                    else:
                        updated += 1

        conn.commit()

    return inserted, updated


def main():

    print("=" * 70)
    print("APPOINTMENT IMPORT")
    print("=" * 70)

    data = load_json()

    validate_appointments(data)

    print("PASS | Appointment JSON validation")

    inserted, updated = import_appointments(data)

    print(f"Inserted: {inserted}")
    print(f"Updated: {updated}")

    print("=" * 70)
    print("APPOINTMENT IMPORT COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()