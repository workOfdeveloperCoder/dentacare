from datetime import date
from uuid import UUID

from app.chat_engine import ChatEngine
from app.db import get_connection


FLOW_KEY = "dental_reception"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)

    print(f"PASS | {message}")


def db_query(query, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def db_query_one(query, params=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def main():

    print("=" * 70)
    print("APPOINTMENT CHAT ENGINE INTEGRATION TEST")
    print("=" * 70)

    engine = ChatEngine()

    # ==============================================================
    # 1. START SESSION
    # ==============================================================

    response = engine.start_session(
        flow_key=FLOW_KEY,
        channel="test",
        client_identifier="appointment-integration-test",
    )

    session_token = response["session_token"]

    assert_true(
        response["node"]["key"] == "MAIN_MENU",
        "Session starts at MAIN_MENU",
    )

    # --------------------------------------------------------------
    # Get session ID once.
    # We will use this throughout the rest of the test.
    # --------------------------------------------------------------

    session_row = db_query_one(
        """
        SELECT
            id,
            status,
            current_node_id
        FROM chat_sessions
        WHERE session_token = %s;
        """,
        (session_token,),
    )

    assert_true(
        session_row is not None,
        "Chat session exists in database",
    )

    session_id = session_row[0]

    # ==============================================================
    # 2. BOOK APPOINTMENT
    # ==============================================================

    response = engine.process_input(
        session_token,
        option_key="BOOK_APPOINTMENT",
    )

    assert_true(
        response["node"]["key"] == "SELECT_SERVICE",
        "BOOK_APPOINTMENT opens SELECT_SERVICE",
    )

    # ==============================================================
    # 3. SERVICE
    # ==============================================================

    service_options = response["node"]["options"]

    assert_true(
        len(service_options) > 0,
        "Service options are available",
    )

    service_key = service_options[0]["key"]

    response = engine.process_input(
        session_token,
        option_key=service_key,
    )

    assert_true(
        response["node"]["key"] == "SELECT_DENTIST",
        "Service selection opens SELECT_DENTIST",
    )

    # ==============================================================
    # 4. DENTIST
    # ==============================================================

    dentist_options = response["node"]["options"]

    assert_true(
        len(dentist_options) > 0,
        "Dentist options are available",
    )

    dentist_key = dentist_options[0]["key"]

    response = engine.process_input(
        session_token,
        option_key=dentist_key,
    )

    assert_true(
        response["node"]["key"] == "PATIENT_TYPE",
        "Dentist selection opens PATIENT_TYPE",
    )

    # ==============================================================
    # 5. PATIENT TYPE
    # ==============================================================

    patient_type_options = response["node"]["options"]

    assert_true(
        len(patient_type_options) > 0,
        "Patient type options are available",
    )

    patient_type_key = patient_type_options[0]["key"]

    response = engine.process_input(
        session_token,
        option_key=patient_type_key,
    )

    assert_true(
        response["node"]["key"] == "PATIENT_NAME",
        "Patient type opens PATIENT_NAME",
    )

    # ==============================================================
    # 6. PATIENT NAME
    # ==============================================================

    response = engine.process_input(
        session_token,
        message="Integration Test Patient",
    )

    assert_true(
        response["node"]["key"] == "PATIENT_MOBILE",
        "Valid name opens PATIENT_MOBILE",
    )

    # ==============================================================
    # 7. MOBILE
    # ==============================================================

    response = engine.process_input(
        session_token,
        message="03001234567",
    )

    assert_true(
        response["node"]["key"] == "PATIENT_EMAIL",
        "Valid mobile opens PATIENT_EMAIL",
    )

    # ==============================================================
    # 8. EMAIL
    # ==============================================================

    response = engine.process_input(
        session_token,
        message="appointment-test@example.com",
    )

    assert_true(
        response["node"]["key"] == "APPOINTMENT_DATE",
        "Valid email opens APPOINTMENT_DATE",
    )

    # ==============================================================
    # 9. APPOINTMENT DATES
    # ==============================================================

    date_options = response["node"]["options"]

    assert_true(
        len(date_options) > 0,
        "Appointment dates are loaded from database",
    )

    selected_date = date_options[0]["key"]

    try:
        date.fromisoformat(selected_date)
    except ValueError:
        raise AssertionError(
            "Appointment date is not a valid ISO date."
        )

    print(
        f"INFO | Selected appointment date: "
        f"{selected_date}"
    )

    assert_true(
        len(selected_date) == 10,
        "Appointment date uses ISO format",
    )

    response = engine.process_input(
        session_token,
        option_key=selected_date,
    )

    assert_true(
        response["node"]["key"] == "APPOINTMENT_TIME",
        "Valid appointment date opens APPOINTMENT_TIME",
    )

    # ==============================================================
    # 10. APPOINTMENT TIMES
    # ==============================================================

    time_options = response["node"]["options"]

    assert_true(
        len(time_options) > 0,
        "Appointment times are loaded from database",
    )

    for option in time_options:

        try:
            UUID(str(option["key"]))
        except (ValueError, TypeError):
            raise AssertionError(
                "Appointment time option does not contain "
                "a valid slot UUID."
            )

    assert_true(
        True,
        "Appointment time options contain valid slot IDs",
    )

    selected_slot_id = time_options[0]["key"]

    print(
        f"INFO | Selected slot ID: "
        f"{selected_slot_id}"
    )

    # ==============================================================
    # 11. VERIFY SELECTED SLOT BEFORE BOOKING
    # ==============================================================

    slot_before = db_query_one(
        """
        SELECT
            id,
            appointment_date,
            start_time,
            end_time,
            capacity,
            booked_count,
            status
        FROM appointment_slots
        WHERE id = %s;
        """,
        (selected_slot_id,),
    )

    assert_true(
        slot_before is not None,
        "Selected appointment slot exists in database",
    )

    original_booked_count = slot_before[5]
    original_status = slot_before[6]

    assert_true(
        original_status == "available",
        "Selected appointment slot is available",
    )

    assert_true(
        original_booked_count < slot_before[4],
        "Selected appointment slot has capacity",
    )

    # ==============================================================
    # 12. SELECT TIME
    # ==============================================================

    response = engine.process_input(
        session_token,
        option_key=selected_slot_id,
    )

    assert_true(
        response["node"]["key"]
        == "APPOINTMENT_CONFIRMATION",
        "Slot selection opens APPOINTMENT_CONFIRMATION",
    )

    confirmation_message = response["node"]["message"]

    assert_true(
        confirmation_message is not None,
        "Appointment confirmation contains a message",
    )

    assert_true(
        "confirm" in confirmation_message.lower(),
        "Appointment confirmation asks for confirmation",
    )

    # ==============================================================
    # 13. VERIFY CONFIRMATION DATE/TIME
    # ==============================================================

    slot_date = slot_before[1]
    slot_start = slot_before[2]
    slot_end = slot_before[3]

    expected_date_text = slot_date.strftime(
        "%A, %d %B %Y"
    )

    expected_time_text = (
        f"{slot_start.strftime('%H:%M')} - "
        f"{slot_end.strftime('%H:%M')}"
    )

    assert_true(
        expected_date_text in confirmation_message,
        "Confirmation contains selected appointment date",
    )

    assert_true(
        expected_time_text in confirmation_message,
        "Confirmation contains selected appointment time",
    )

    # ==============================================================
    # 14. VERIFY CONFIRMATION OPTIONS
    # ==============================================================

    confirmation_options = response["node"]["options"]

    assert_true(
        len(confirmation_options) > 0,
        "Appointment confirmation options are available",
    )

    confirmation_keys = {
        option["key"]
        for option in confirmation_options
    }

    assert_true(
        "CONFIRM" in confirmation_keys,
        "Appointment confirmation contains CONFIRM option",
    )

    assert_true(
        "EDIT" in confirmation_keys,
        "Appointment confirmation contains EDIT option",
    )

    # ==============================================================
    # 15. CONFIRM APPOINTMENT
    # ==============================================================

    response = engine.process_input(
        session_token,
        option_key="CONFIRM",
    )

    # --------------------------------------------------------------
    # Debug information if booking flow does not reach END.
    # --------------------------------------------------------------

    if response["node"]["key"] != "APPOINTMENT_END":

        print()
        print("=" * 70)
        print("DEBUG | RESPONSE AFTER CONFIRM")
        print("=" * 70)
        print(response)
        print("=" * 70)
        print()

    assert_true(
        response["node"]["key"] == "APPOINTMENT_END",
        "CONFIRM executes booking and opens APPOINTMENT_END",
    )

    assert_true(
        "appointment" in response,
        "Appointment booking result is returned",
    )

    appointment_result = response["appointment"]

    assert_true(
        appointment_result.get("order_id") is not None,
        "Booking result contains order ID",
    )

    assert_true(
        appointment_result.get("order_number") is not None,
        "Booking result contains order number",
    )

    assert_true(
        appointment_result.get("slot_id") == selected_slot_id,
        "Booking result contains selected slot ID",
    )

    assert_true(
        appointment_result.get("appointment_date")
        == slot_date.isoformat(),
        "Booking result contains correct appointment date",
    )

    assert_true(
        appointment_result.get("start_time")
        == slot_start.isoformat(),
        "Booking result contains correct appointment start time",
    )

    assert_true(
        appointment_result.get("end_time")
        == slot_end.isoformat(),
        "Booking result contains correct appointment end time",
    )

    order_id = appointment_result["order_id"]
    order_number = appointment_result["order_number"]

    # ==============================================================
    # 16. VERIFY SESSION AFTER BOOKING
    # ==============================================================

    session_row = db_query_one(
        """
        SELECT
            id,
            status,
            current_node_id
        FROM chat_sessions
        WHERE session_token = %s;
        """,
        (session_token,),
    )

    assert_true(
        session_row is not None,
        "Chat session exists in database after booking",
    )

    assert_true(
        str(session_row[0]) == str(session_id),
        "Booking uses the original chat session",
    )

    assert_true(
        session_row[1] == "active",
        "Session remains active until end node is processed",
    )

    # ==============================================================
    # 17. VERIFY CURRENT NODE IS APPOINTMENT_END
    # ==============================================================

    current_node_row = db_query_one(
        """
        SELECT
            node_key,
            node_type
        FROM chat_nodes
        WHERE id = %s;
        """,
        (session_row[2],),
    )

    assert_true(
        current_node_row is not None,
        "Current session node exists",
    )

    assert_true(
        current_node_row[0] == "APPOINTMENT_END",
        "Database current node is APPOINTMENT_END",
    )

    assert_true(
        current_node_row[1] == "end",
        "APPOINTMENT_END is an end node",
    )

    # ==============================================================
    # 18. VERIFY ORDER
    # ==============================================================

    order_row = db_query_one(
        """
        SELECT
            id,
            order_number,
            session_id,
            customer_name,
            customer_phone,
            customer_email,
            status,
            confirmed_at
        FROM orders
        WHERE id = %s
        LIMIT 1;
        """,
        (order_id,),
    )

    assert_true(
        order_row is not None,
        "Appointment order was created",
    )

    assert_true(
        str(order_row[0]) == str(order_id),
        "Returned order ID matches database order",
    )

    assert_true(
        order_row[1] == order_number,
        "Returned order number matches database order",
    )

    assert_true(
        str(order_row[2]) == str(session_id),
        "Order belongs to current chat session",
    )

    assert_true(
        order_row[3] == "Integration Test Patient",
        "Order contains patient name",
    )

    assert_true(
        order_row[4] == "03001234567",
        "Order contains patient mobile",
    )

    assert_true(
        order_row[5] == "appointment-test@example.com",
        "Order contains patient email",
    )

    assert_true(
        order_row[6] == "confirmed",
        "Order status is confirmed",
    )

    assert_true(
        order_row[7] is not None,
        "Order contains confirmation timestamp",
    )

    # ==============================================================
    # 19. VERIFY ORDER DETAIL
    # ==============================================================

    detail_row = db_query_one(
        """
        SELECT
            id,
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
            quantity
        FROM order_details
        WHERE order_id = %s
        LIMIT 1;
        """,
        (order_id,),
    )

    assert_true(
        detail_row is not None,
        "Appointment order detail was created",
    )

    assert_true(
        str(detail_row[1]) == str(order_id),
        "Order detail belongs to created order",
    )

    assert_true(
        str(detail_row[2]) == str(selected_slot_id),
        "Order detail references selected appointment slot",
    )

    assert_true(
        detail_row[3] == "appointment",
        "Order detail item type is appointment",
    )

    assert_true(
        detail_row[4] == service_key,
        "Order detail contains selected service",
    )

    assert_true(
        detail_row[5] is not None,
        "Order detail contains service name",
    )

    assert_true(
        detail_row[6] == dentist_key,
        "Order detail contains selected dentist",
    )

    assert_true(
        detail_row[7] is not None,
        "Order detail contains dentist name",
    )

    assert_true(
        detail_row[8] == slot_date,
        "Order detail contains appointment date",
    )

    assert_true(
        detail_row[9] == slot_start,
        "Order detail contains appointment start time",
    )

    assert_true(
        detail_row[10] == slot_end,
        "Order detail contains appointment end time",
    )

    assert_true(
        detail_row[11] == 1,
        "Order detail quantity is 1",
    )

    # ==============================================================
    # 20. VERIFY SLOT BOOKING
    # ==============================================================

    slot_after = db_query_one(
        """
        SELECT
            booked_count,
            capacity,
            status
        FROM appointment_slots
        WHERE id = %s;
        """,
        (selected_slot_id,),
    )

    assert_true(
        slot_after is not None,
        "Appointment slot still exists after booking",
    )

    assert_true(
        slot_after[0] == original_booked_count + 1,
        "Appointment slot booked_count increased by 1",
    )

    expected_status = (
        "full"
        if slot_after[0] >= slot_after[1]
        else "available"
    )

    assert_true(
        slot_after[2] == expected_status,
        "Appointment slot status matches capacity",
    )

    # ==============================================================
    # 21. VERIFY SESSION HISTORY
    # ==============================================================

    history_rows = db_query(
        """
        SELECT
            h.sequence_no,
            n.node_key,
            n.node_type
        FROM chat_session_history h
        JOIN chat_nodes n
            ON n.id = h.node_id
        WHERE h.session_id = %s
        ORDER BY h.sequence_no ASC;
        """,
        (session_id,),
    )

    history_keys = [
        row[1]
        for row in history_rows
    ]

    assert_true(
        "MAIN_MENU" in history_keys,
        "History contains MAIN_MENU",
    )

    assert_true(
        "SELECT_SERVICE" in history_keys,
        "History contains SELECT_SERVICE",
    )

    assert_true(
        "SELECT_DENTIST" in history_keys,
        "History contains SELECT_DENTIST",
    )

    assert_true(
        "PATIENT_TYPE" in history_keys,
        "History contains PATIENT_TYPE",
    )

    assert_true(
        "PATIENT_NAME" in history_keys,
        "History contains PATIENT_NAME",
    )

    assert_true(
        "PATIENT_MOBILE" in history_keys,
        "History contains PATIENT_MOBILE",
    )

    assert_true(
        "PATIENT_EMAIL" in history_keys,
        "History contains PATIENT_EMAIL",
    )

    assert_true(
        "APPOINTMENT_DATE" in history_keys,
        "History contains APPOINTMENT_DATE",
    )

    assert_true(
        "APPOINTMENT_TIME" in history_keys,
        "History contains APPOINTMENT_TIME",
    )

    assert_true(
        "APPOINTMENT_CONFIRMATION" in history_keys,
        "History contains APPOINTMENT_CONFIRMATION",
    )

    assert_true(
        "APPOINTMENT_SUBMIT" in history_keys,
        "History contains internal APPOINTMENT_SUBMIT action",
    )

    assert_true(
        "APPOINTMENT_END" in history_keys,
        "History contains APPOINTMENT_END",
    )

    # ==============================================================
    # 22. VERIFY ACTION NODE WAS INTERNAL
    # ==============================================================

    assert_true(
        response["node"]["key"] != "APPOINTMENT_SUBMIT",
        "APPOINTMENT_SUBMIT is not exposed to client",
    )

    # ==============================================================
    # 23. PROCESS END NODE
    # ==============================================================

    response = engine.process_input(
        session_token,
    )

    assert_true(
        response["node"]["key"] == "APPOINTMENT_END",
        "Processing end node returns APPOINTMENT_END",
    )

    assert_true(
        response.get("session", {}).get("status")
        == "completed",
        "Processing APPOINTMENT_END completes the session",
    )

    # ==============================================================
    # 24. VERIFY SESSION COMPLETED IN DATABASE
    # ==============================================================

    session_row = db_query_one(
        """
        SELECT
            status
        FROM chat_sessions
        WHERE session_token = %s;
        """,
        (session_token,),
    )

    assert_true(
        session_row is not None,
        "Completed session still exists in database",
    )

    assert_true(
        session_row[0] == "completed",
        "Session status is completed in database",
    )

    # ==============================================================
    # 25. VERIFY EXACTLY ONE ORDER
    # ==============================================================

    order_count_row = db_query_one(
        """
        SELECT
            COUNT(*)
        FROM orders
        WHERE session_id = %s;
        """,
        (session_id,),
    )

    assert_true(
        order_count_row[0] == 1,
        "Exactly one order was created for the session",
    )

    # ==============================================================
    # 26. VERIFY EXACTLY ONE ORDER DETAIL
    # ==============================================================

    detail_count_row = db_query_one(
        """
        SELECT
            COUNT(*)
        FROM order_details
        WHERE order_id = %s;
        """,
        (order_id,),
    )

    assert_true(
        detail_count_row[0] == 1,
        "Exactly one order detail was created",
    )

    # ==============================================================
    # 27. VERIFY SLOT WAS NOT BOOKED TWICE
    # ==============================================================

    final_slot_row = db_query_one(
        """
        SELECT
            booked_count,
            capacity,
            status
        FROM appointment_slots
        WHERE id = %s;
        """,
        (selected_slot_id,),
    )

    assert_true(
        final_slot_row is not None,
        "Final appointment slot exists",
    )

    assert_true(
        final_slot_row[0]
        == original_booked_count + 1,
        "Slot was booked exactly once",
    )

    # ==============================================================
    # RESULT
    # ==============================================================

    print()
    print("=" * 70)
    print("APPOINTMENT INTEGRATION TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()