from app.chat_engine import ChatEngine
from app.db import get_connection


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print(f"PASS | {message}")


def get_slot_state(slot_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    capacity,
                    booked_count,
                    status
                FROM appointment_slots
                WHERE id = %s
                LIMIT 1;
                """,
                (slot_id,),
            )

            row = cur.fetchone()

            if row is None:
                raise AssertionError(
                    "Appointment slot not found."
                )

            return {
                "id": row[0],
                "capacity": row[1],
                "booked_count": row[2],
                "status": row[3],
            }


def get_order_by_session(session_token):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    o.id,
                    o.order_number,
                    o.status,
                    o.customer_name,
                    o.customer_phone,
                    o.customer_email
                FROM orders o
                JOIN chat_sessions s
                    ON s.id = o.session_id
                WHERE s.session_token = %s
                ORDER BY o.created_at DESC
                LIMIT 1;
                """,
                (session_token,),
            )

            row = cur.fetchone()

            if row is None:
                return None

            return {
                "id": row[0],
                "order_number": row[1],
                "status": row[2],
                "customer_name": row[3],
                "customer_phone": row[4],
                "customer_email": row[5],
            }


def get_order_detail(order_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    slot_id,
                    item_type,
                    service_key,
                    service_name,
                    dentist_key,
                    dentist_name,
                    appointment_date,
                    start_time,
                    end_time,
                    quantity
                FROM order_details
                WHERE order_id = %s
                ORDER BY id
                LIMIT 1;
                """,
                (order_id,),
            )

            row = cur.fetchone()

            if row is None:
                return None

            return {
                "id": row[0],
                "slot_id": row[1],
                "item_type": row[2],
                "service_key": row[3],
                "service_name": row[4],
                "dentist_key": row[5],
                "dentist_name": row[6],
                "appointment_date": row[7],
                "appointment_start": row[8],
                "appointment_end": row[9],
                "quantity": row[10],
            }


def main():

    print()
    print("=" * 70)
    print("BOOKING INTEGRATION TEST")
    print("=" * 70)

    engine = ChatEngine()

    # --------------------------------------------------------------
    # START
    # --------------------------------------------------------------

    response = engine.start_session(
        flow_key="dental_reception",
        channel="test",
    )

    session_token = response["session_token"]

    check(
        response["node"]["key"] == "MAIN_MENU",
        "Session starts at MAIN_MENU",
    )

    # --------------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="BOOK_APPOINTMENT",
    )

    check(
        response["node"]["key"] == "SELECT_SERVICE",
        "BOOK_APPOINTMENT opens SELECT_SERVICE",
    )

    # --------------------------------------------------------------
    # SERVICE
    # --------------------------------------------------------------

    service_option = (
        response["node"]["options"][0]["key"]
    )

    response = engine.process_input(
        session_token,
        option_key=service_option,
    )

    check(
        response["node"]["key"] == "SELECT_DENTIST",
        "Service selection opens SELECT_DENTIST",
    )

    # --------------------------------------------------------------
    # DENTIST
    # --------------------------------------------------------------

    dentist_option = (
        response["node"]["options"][0]["key"]
    )

    response = engine.process_input(
        session_token,
        option_key=dentist_option,
    )

    check(
        response["node"]["key"] == "PATIENT_TYPE",
        "Dentist selection opens PATIENT_TYPE",
    )

    # --------------------------------------------------------------
    # PATIENT TYPE
    # --------------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="NEW_PATIENT",
    )

    check(
        response["node"]["key"] == "PATIENT_NAME",
        "Patient type opens PATIENT_NAME",
    )

    # --------------------------------------------------------------
    # NAME
    # --------------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="Booking Test Patient",
    )

    check(
        response["node"]["key"] == "PATIENT_MOBILE",
        "Name opens PATIENT_MOBILE",
    )

    # --------------------------------------------------------------
    # MOBILE
    # --------------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="03001234567",
    )

    check(
        response["node"]["key"] == "PATIENT_EMAIL",
        "Mobile opens PATIENT_EMAIL",
    )

    # --------------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="booking-test@example.com",
    )

    check(
        response["node"]["key"] == "APPOINTMENT_DATE",
        "Email opens APPOINTMENT_DATE",
    )

    # --------------------------------------------------------------
    # DATE
    # --------------------------------------------------------------

    date_options = response["node"]["options"]

    check(
        len(date_options) > 0,
        "Available appointment dates loaded",
    )

    appointment_date = date_options[0]["key"]

    response = engine.process_input(
        session_token,
        message=appointment_date,
    )

    check(
        response["node"]["key"] == "APPOINTMENT_TIME",
        "Appointment date opens APPOINTMENT_TIME",
    )

    # --------------------------------------------------------------
    # TIME / SLOT
    # --------------------------------------------------------------

    time_options = response["node"]["options"]

    check(
        len(time_options) > 0,
        "Available appointment slots loaded",
    )

    slot_id = time_options[0]["key"]

    before = get_slot_state(slot_id)

    print()
    print(
        f"INFO | Slot: {slot_id}"
    )

    print(
        f"INFO | Before booking: "
        f"booked={before['booked_count']} "
        f"capacity={before['capacity']} "
        f"status={before['status']}"
    )

    check(
        before["booked_count"] < before["capacity"],
        "Selected slot has available capacity",
    )

    response = engine.process_input(
        session_token,
        option_key=slot_id,
    )

    check(
        response["node"]["key"]
        == "APPOINTMENT_CONFIRMATION",
        "Slot selection opens confirmation",
    )

    # --------------------------------------------------------------
    # CONFIRM
    # --------------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="CONFIRM",
    )

    check(
        response["node"]["key"]
        == "APPOINTMENT_END",
        "Confirmation reaches APPOINTMENT_END",
    )

    # --------------------------------------------------------------
    # SLOT
    # --------------------------------------------------------------

    after = get_slot_state(slot_id)

    print(
        f"INFO | After booking: "
        f"booked={after['booked_count']} "
        f"capacity={after['capacity']} "
        f"status={after['status']}"
    )

    check(
        after["booked_count"]
        == before["booked_count"] + 1,
        "Slot booked_count increased by one",
    )

    if after["booked_count"] >= after["capacity"]:

        check(
            after["status"] == "full",
            "Slot becomes full when capacity is reached",
        )

    else:

        check(
            after["status"] == "available",
            "Slot remains available when capacity remains",
        )

    # --------------------------------------------------------------
    # ORDER
    # --------------------------------------------------------------

    order = get_order_by_session(
        session_token
    )

    check(
        order is not None,
        "Order was created",
    )

    check(
        order["status"] == "confirmed",
        "Order status is confirmed",
    )

    check(
        order["customer_name"]
        == "Booking Test Patient",
        "Order contains customer name",
    )

    check(
        order["customer_phone"]
        == "03001234567",
        "Order contains customer phone",
    )

    check(
        order["customer_email"]
        == "booking-test@example.com",
        "Order contains customer email",
    )

    print(
        f"INFO | Order number: "
        f"{order['order_number']}"
    )

    # --------------------------------------------------------------
    # ORDER DETAIL
    # --------------------------------------------------------------

    detail = get_order_detail(
        order["id"]
    )

    check(
        detail is not None,
        "Order detail was created",
    )

    check(
        str(detail["slot_id"])
        == str(slot_id),
        "Order detail references selected slot",
    )

    check(
        detail["item_type"] == "appointment",
        "Order detail item type is appointment",
    )

    check(
        detail["appointment_date"].isoformat()
        == appointment_date,
        "Order detail contains appointment date",
    )

    check(
        detail["quantity"] == 1,
        "Order detail quantity is one",
    )

    # --------------------------------------------------------------
    # RESULT
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("BOOKING INTEGRATION TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()