from datetime import date
from typing import Any

from app.db import get_connection


class AppointmentSlotService:

    # ============================================================
    # AVAILABLE APPOINTMENT SLOTS
    # ============================================================

    def get_available_dates(self) -> list[date]:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT DISTINCT appointment_date
                    FROM appointment_slots
                    WHERE status = 'available'
                      AND booked_count < capacity
                      AND appointment_date > CURRENT_DATE
                    ORDER BY appointment_date ASC;
                    """
                )

                return [
                    row[0]
                    for row in cur.fetchall()
                ]

    def get_available_slots(
        self,
        appointment_date: date,
    ) -> list[dict[str, Any]]:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        appointment_date,
                        start_time,
                        end_time,
                        capacity,
                        booked_count,
                        status,
                        notes
                    FROM appointment_slots
                    WHERE appointment_date = %s
                      AND status = 'available'
                      AND booked_count < capacity
                    ORDER BY start_time ASC;
                    """,
                    (appointment_date,),
                )

                return [
                    self._slot_dict(row)
                    for row in cur.fetchall()
                ]

    def get_slot(
        self,
        slot_id,
    ) -> dict[str, Any] | None:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        appointment_date,
                        start_time,
                        end_time,
                        capacity,
                        booked_count,
                        status,
                        notes
                    FROM appointment_slots
                    WHERE id = %s
                    LIMIT 1;
                    """,
                    (slot_id,),
                )

                row = cur.fetchone()

                if row is None:
                    return None

                return self._slot_dict(row)

    def get_slot_by_date_time(
        self,
        appointment_date: date,
        start_time,
    ) -> dict[str, Any] | None:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        appointment_date,
                        start_time,
                        end_time,
                        capacity,
                        booked_count,
                        status,
                        notes
                    FROM appointment_slots
                    WHERE appointment_date = %s
                      AND start_time = %s
                      AND status = 'available'
                      AND booked_count < capacity
                    LIMIT 1;
                    """,
                    (
                        appointment_date,
                        start_time,
                    ),
                )

                row = cur.fetchone()

                if row is None:
                    return None

                return self._slot_dict(row)

    def is_available(
        self,
        slot_id,
    ) -> bool:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT 1
                    FROM appointment_slots
                    WHERE id = %s
                      AND status = 'available'
                      AND booked_count < capacity
                    LIMIT 1;
                    """,
                    (slot_id,),
                )

                return cur.fetchone() is not None

    # ============================================================
    # RESERVE SLOT
    # ============================================================

    def reserve_slot(
        self,
        cur,
        slot_id,
    ) -> dict[str, Any]:

        cur.execute(
            """
            SELECT
                id,
                appointment_date,
                start_time,
                end_time,
                capacity,
                booked_count,
                status,
                notes
            FROM appointment_slots
            WHERE id = %s
            FOR UPDATE;
            """,
            (slot_id,),
        )

        row = cur.fetchone()

        if row is None:
            raise ValueError(
                "Appointment slot not found."
            )

        slot = self._slot_dict(row)

        if slot["status"] != "available":
            raise ValueError(
                "This appointment slot is no longer available."
            )

        if slot["booked_count"] >= slot["capacity"]:
            raise ValueError(
                "This appointment slot is already full."
            )

        cur.execute(
            """
            UPDATE appointment_slots
            SET
                booked_count = booked_count + 1,
                status = CASE
                    WHEN booked_count + 1 >= capacity
                        THEN 'full'
                    ELSE 'available'
                END,
                updated_at = NOW()
            WHERE id = %s
            RETURNING
                id,
                appointment_date,
                start_time,
                end_time,
                capacity,
                booked_count,
                status,
                notes;
            """,
            (slot_id,),
        )

        updated_row = cur.fetchone()

        if updated_row is None:
            raise ValueError(
                "Unable to reserve appointment slot."
            )

        return self._slot_dict(updated_row)

    # ============================================================
    # RELEASE SLOT
    # ============================================================

    def release_slot(
        self,
        cur,
        slot_id,
    ) -> dict[str, Any]:

        cur.execute(
            """
            SELECT
                id,
                appointment_date,
                start_time,
                end_time,
                capacity,
                booked_count,
                status,
                notes
            FROM appointment_slots
            WHERE id = %s
            FOR UPDATE;
            """,
            (slot_id,),
        )

        row = cur.fetchone()

        if row is None:
            raise ValueError(
                "Appointment slot not found."
            )

        slot = self._slot_dict(row)

        if slot["booked_count"] <= 0:
            raise ValueError(
                "Appointment slot has no bookings to release."
            )

        new_booked_count = (
            slot["booked_count"] - 1
        )

        cur.execute(
            """
            UPDATE appointment_slots
            SET
                booked_count = %s,
                status = CASE
                    WHEN status = 'cancelled'
                        THEN 'cancelled'
                    WHEN %s < capacity
                        THEN 'available'
                    ELSE 'full'
                END,
                updated_at = NOW()
            WHERE id = %s
            RETURNING
                id,
                appointment_date,
                start_time,
                end_time,
                capacity,
                booked_count,
                status,
                notes;
            """,
            (
                new_booked_count,
                new_booked_count,
                slot_id,
            ),
        )

        updated_row = cur.fetchone()

        if updated_row is None:
            raise ValueError(
                "Unable to release appointment slot."
            )

        return self._slot_dict(updated_row)

    # ============================================================
    # FIND APPOINTMENTS
    # ============================================================

    def find_appointments_by_phone(
        self,
        phone: str,
    ) -> list[dict[str, Any]]:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        o.id,
                        o.order_number,
                        o.customer_name,
                        o.customer_phone,
                        o.customer_email,
                        o.status,

                        od.id,
                        od.service_key,
                        od.service_name,
                        od.dentist_key,
                        od.dentist_name,
                        od.appointment_date,
                        od.start_time,
                        od.end_time,
                        od.slot_id

                    FROM orders o

                    JOIN order_details od
                        ON od.order_id = o.id

                    WHERE o.customer_phone = %s
                      AND o.status = 'confirmed'

                    ORDER BY
                        od.appointment_date ASC,
                        od.start_time ASC;
                    """,
                    (phone,),
                )

                return [
                    self._appointment_dict(row)
                    for row in cur.fetchall()
                ]

    def find_appointments_by_email(
        self,
        email: str,
    ) -> list[dict[str, Any]]:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        o.id,
                        o.order_number,
                        o.customer_name,
                        o.customer_phone,
                        o.customer_email,
                        o.status,

                        od.id,
                        od.service_key,
                        od.service_name,
                        od.dentist_key,
                        od.dentist_name,
                        od.appointment_date,
                        od.start_time,
                        od.end_time,
                        od.slot_id

                    FROM orders o

                    JOIN order_details od
                        ON od.order_id = o.id

                    WHERE LOWER(TRIM(o.customer_email))
                          = LOWER(TRIM(%s))
                      AND o.status = 'confirmed'

                    ORDER BY
                        od.appointment_date ASC,
                        od.start_time ASC;
                    """,
                    (email,),
                )

                return [
                    self._appointment_dict(row)
                    for row in cur.fetchall()
                ]

    def find_appointments_by_name(
        self,
        name: str,
    ) -> list[dict[str, Any]]:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        o.id,
                        o.order_number,
                        o.customer_name,
                        o.customer_phone,
                        o.customer_email,
                        o.status,

                        od.id,
                        od.service_key,
                        od.service_name,
                        od.dentist_key,
                        od.dentist_name,
                        od.appointment_date,
                        od.start_time,
                        od.end_time,
                        od.slot_id

                    FROM orders o

                    JOIN order_details od
                        ON od.order_id = o.id

                    WHERE LOWER(TRIM(o.customer_name))
                          = LOWER(TRIM(%s))
                      AND o.status = 'confirmed'

                    ORDER BY
                        od.appointment_date ASC,
                        od.start_time ASC;
                    """,
                    (name,),
                )

                return [
                    self._appointment_dict(row)
                    for row in cur.fetchall()
                ]

    # ============================================================
    # GET ONE APPOINTMENT
    # ============================================================

    def get_appointment(
        self,
        order_id,
    ) -> dict[str, Any] | None:

        with get_connection() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        o.id,
                        o.order_number,
                        o.customer_name,
                        o.customer_phone,
                        o.customer_email,
                        o.status,

                        od.id,
                        od.service_key,
                        od.service_name,
                        od.dentist_key,
                        od.dentist_name,
                        od.appointment_date,
                        od.start_time,
                        od.end_time,
                        od.slot_id

                    FROM orders o

                    JOIN order_details od
                        ON od.order_id = o.id

                    WHERE o.id = %s

                    LIMIT 1;
                    """,
                    (order_id,),
                )

                row = cur.fetchone()

                if row is None:
                    return None

                return self._appointment_dict(row)

    # ============================================================
    # APPOINTMENT DATA HELPERS
    # ============================================================

    @staticmethod
    def _slot_dict(
        row,
    ) -> dict[str, Any]:

        return {
            "id": row[0],
            "appointment_date": row[1],
            "start_time": row[2],
            "end_time": row[3],
            "capacity": row[4],
            "booked_count": row[5],
            "status": row[6],
            "notes": row[7],
        }

    @staticmethod
    def _appointment_dict(
        row,
    ) -> dict[str, Any]:

        return {
            "order_id": row[0],
            "order_number": row[1],
            "customer_name": row[2],
            "customer_phone": row[3],
            "customer_email": row[4],
            "status": row[5],

            "order_detail_id": row[6],
            "service_key": row[7],
            "service_name": row[8],
            "dentist_key": row[9],
            "dentist_name": row[10],
            "appointment_date": row[11],
            "start_time": row[12],
            "end_time": row[13],
            "slot_id": row[14],
        }