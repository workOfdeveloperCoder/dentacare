from datetime import date, timedelta

from app.chat_engine import ChatEngine


PASSED = 0
FAILED = 0


def check(condition: bool, message: str) -> None:
    global PASSED, FAILED

    if condition:
        PASSED += 1
        print(f"PASS | {message}")
    else:
        FAILED += 1
        print(f"FAIL | {message}")


def assert_node(response: dict, expected_key: str, message: str) -> None:
    actual_key = response.get("node", {}).get("key")

    check(
        actual_key == expected_key,
        f"{message} | expected={expected_key} actual={actual_key}",
    )


def start_appointment_flow(engine: ChatEngine) -> str:
    response = engine.start_session(
        flow_key="dental_reception",
        channel="test",
    )

    session_token = response["session_token"]

    assert_node(
        response,
        "MAIN_MENU",
        "Start session opens MAIN_MENU",
    )

    response = engine.process_input(
        session_token,
        option_key="BOOK_APPOINTMENT",
    )

    assert_node(
        response,
        "SELECT_SERVICE",
        "BOOK_APPOINTMENT → SELECT_SERVICE",
    )

    response = engine.process_input(
        session_token,
        option_key="ROOT_CANAL",
    )

    assert_node(
        response,
        "SELECT_DENTIST",
        "ROOT_CANAL → SELECT_DENTIST",
    )

    response = engine.process_input(
        session_token,
        option_key="DR_AMIN",
    )

    assert_node(
        response,
        "PATIENT_TYPE",
        "DR_AMIN → PATIENT_TYPE",
    )

    response = engine.process_input(
        session_token,
        option_key="NEW_PATIENT",
    )

    assert_node(
        response,
        "PATIENT_NAME",
        "NEW_PATIENT → PATIENT_NAME",
    )

    return session_token


def test_full_happy_path(engine: ChatEngine) -> None:
    print()
    print("=" * 70)
    print("FULL CHATBOT FLOW TEST")
    print("=" * 70)

    session_token = start_appointment_flow(engine)

    # ---------------------------------------------------------
    # PATIENT NAME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="Yasir Bhatti",
    )

    assert_node(
        response,
        "PATIENT_MOBILE",
        "PATIENT_NAME → PATIENT_MOBILE",
    )

    # ---------------------------------------------------------
    # PATIENT MOBILE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="+923001234567",
    )

    assert_node(
        response,
        "PATIENT_EMAIL",
        "PATIENT_MOBILE → PATIENT_EMAIL",
    )

    # ---------------------------------------------------------
    # PATIENT EMAIL
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="test@example.com",
    )

    assert_node(
        response,
        "APPOINTMENT_DATE",
        "PATIENT_EMAIL → APPOINTMENT_DATE",
    )

    # ---------------------------------------------------------
    # APPOINTMENT DATE
    # ---------------------------------------------------------

    date_options = response["node"].get("options") or []

    if date_options:
        appointment_date = date_options[0]["key"]
    else:
        appointment_date = (
            date.today() + timedelta(days=30)
        ).isoformat()

    response = engine.process_input(
        session_token,
        message=appointment_date,
    )

    assert_node(
        response,
        "APPOINTMENT_TIME",
        "APPOINTMENT_DATE → APPOINTMENT_TIME",
    )

    # ---------------------------------------------------------
    # APPOINTMENT TIME
    # ---------------------------------------------------------

    time_options = response["node"].get("options") or []

    if time_options:
        response = engine.process_input(
            session_token,
            option_key=time_options[0]["key"],
        )
    else:
        response = engine.process_input(
            session_token,
            message="14:00",
        )

    assert_node(
        response,
        "APPOINTMENT_CONFIRMATION",
        "APPOINTMENT_TIME → APPOINTMENT_CONFIRMATION",
    )

    # ---------------------------------------------------------
    # CONFIRM
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="CONFIRM",
    )

    assert_node(
        response,
        "APPOINTMENT_END",
        "CONFIRM → APPOINTMENT_END",
    )

    status = response.get("session", {}).get("status")

    check(
        status == "completed",
        "APPOINTMENT_END completes session",
    )


def test_validation(engine: ChatEngine) -> None:
    print()
    print("=" * 70)
    print("INPUT VALIDATION TEST")
    print("=" * 70)

    session_token = start_appointment_flow(engine)

    # ---------------------------------------------------------
    # INVALID NAME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="A",
    )

    assert_node(
        response,
        "PATIENT_NAME",
        "Invalid name stays on PATIENT_NAME",
    )

    # ---------------------------------------------------------
    # EMPTY NAME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="",
    )

    assert_node(
        response,
        "PATIENT_NAME",
        "Empty name stays on PATIENT_NAME",
    )

    # ---------------------------------------------------------
    # VALID NAME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="Yasir Bhatti",
    )

    assert_node(
        response,
        "PATIENT_MOBILE",
        "Valid name → PATIENT_MOBILE",
    )

    # ---------------------------------------------------------
    # INVALID MOBILE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="12345",
    )

    assert_node(
        response,
        "PATIENT_MOBILE",
        "Invalid mobile stays on PATIENT_MOBILE",
    )

    # ---------------------------------------------------------
    # INVALID MOBILE FORMAT
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="030012345",
    )

    assert_node(
        response,
        "PATIENT_MOBILE",
        "Invalid mobile format stays on PATIENT_MOBILE",
    )

    # ---------------------------------------------------------
    # VALID MOBILE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="+923001234567",
    )

    assert_node(
        response,
        "PATIENT_EMAIL",
        "Valid mobile → PATIENT_EMAIL",
    )

    # ---------------------------------------------------------
    # INVALID EMAIL
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="invalid-email",
    )

    assert_node(
        response,
        "PATIENT_EMAIL",
        "Invalid email stays on PATIENT_EMAIL",
    )

    # ---------------------------------------------------------
    # INVALID EMAIL
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="test@",
    )

    assert_node(
        response,
        "PATIENT_EMAIL",
        "Incomplete email stays on PATIENT_EMAIL",
    )

    # ---------------------------------------------------------
    # VALID EMAIL
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="test@example.com",
    )

    assert_node(
        response,
        "APPOINTMENT_DATE",
        "Valid email → APPOINTMENT_DATE",
    )

    # ---------------------------------------------------------
    # INVALID DATE FORMAT
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="tomorrow",
    )

    assert_node(
        response,
        "APPOINTMENT_DATE",
        "Invalid date format stays on APPOINTMENT_DATE",
    )

    # ---------------------------------------------------------
    # INVALID PAST DATE
    # ---------------------------------------------------------

    past_date = (
        date.today() - timedelta(days=1)
    ).isoformat()

    response = engine.process_input(
        session_token,
        message=past_date,
    )

    assert_node(
        response,
        "APPOINTMENT_DATE",
        "Past date stays on APPOINTMENT_DATE",
    )

    # ---------------------------------------------------------
    # VALID FUTURE DATE
    # ---------------------------------------------------------

    future_date = (
        date.today() + timedelta(days=30)
    ).isoformat()

    response = engine.process_input(
        session_token,
        message=future_date,
    )

    assert_node(
        response,
        "APPOINTMENT_TIME",
        "Future date → APPOINTMENT_TIME",
    )

    # ---------------------------------------------------------
    # INVALID TIME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="08:00",
    )

    assert_node(
        response,
        "APPOINTMENT_TIME",
        "Before clinic hours stays on APPOINTMENT_TIME",
    )

    # ---------------------------------------------------------
    # INVALID TIME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="18:00",
    )

    assert_node(
        response,
        "APPOINTMENT_TIME",
        "After clinic hours stays on APPOINTMENT_TIME",
    )

    # ---------------------------------------------------------
    # INVALID TIME FORMAT
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="abc",
    )

    assert_node(
        response,
        "APPOINTMENT_TIME",
        "Invalid time format stays on APPOINTMENT_TIME",
    )

    # ---------------------------------------------------------
    # VALID TIME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        message="14:00",
    )

    assert_node(
        response,
        "APPOINTMENT_CONFIRMATION",
        "Valid time → APPOINTMENT_CONFIRMATION",
    )


def test_back_navigation(engine: ChatEngine) -> None:
    print()
    print("=" * 70)
    print("BACK NAVIGATION TEST")
    print("=" * 70)

    session_token = start_appointment_flow(engine)

    # PATIENT_NAME → PATIENT_MOBILE
    response = engine.process_input(
        session_token,
        message="Yasir Bhatti",
    )

    assert_node(
        response,
        "PATIENT_MOBILE",
        "Name → Mobile",
    )

    # BACK → PATIENT_NAME
    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    assert_node(
        response,
        "PATIENT_NAME",
        "BACK returns to PATIENT_NAME",
    )

    # BACK → PATIENT_TYPE
    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    assert_node(
        response,
        "PATIENT_TYPE",
        "BACK returns to PATIENT_TYPE",
    )

    # BACK → SELECT_DENTIST
    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    assert_node(
        response,
        "SELECT_DENTIST",
        "BACK returns to SELECT_DENTIST",
    )

    # BACK → SELECT_SERVICE
    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    assert_node(
        response,
        "SELECT_SERVICE",
        "BACK returns to SELECT_SERVICE",
    )

    # BACK → MAIN_MENU
    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    assert_node(
        response,
        "MAIN_MENU",
        "BACK from first menu returns to MAIN_MENU",
    )


def test_main_menu_navigation(engine):
    global PASSED, FAILED

    print()
    print("=" * 70)
    print("MAIN MENU NAVIGATION TEST")
    print("=" * 70)

    # ---------------------------------------------------------
    # Start session
    # ---------------------------------------------------------

    response = engine.start_session(
        flow_key="dental_reception",
        channel="test",
    )

    check(
        response["node"]["key"] == "MAIN_MENU",
        "Start session opens MAIN_MENU",
    )

    session_token = response["session_token"]

    # ---------------------------------------------------------
    # MAIN_MENU → SELECT_SERVICE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="BOOK_APPOINTMENT",
    )

    check(
        response["node"]["key"] == "SELECT_SERVICE",
        "BOOK_APPOINTMENT → SELECT_SERVICE",
    )

    # ---------------------------------------------------------
    # SELECT_SERVICE → SELECT_DENTIST
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="ROOT_CANAL",
    )

    check(
        response["node"]["key"] == "SELECT_DENTIST",
        "ROOT_CANAL → SELECT_DENTIST",
    )

    # ---------------------------------------------------------
    # SELECT_DENTIST → PATIENT_TYPE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="DR_AMIN",
    )

    check(
        response["node"]["key"] == "PATIENT_TYPE",
        "DR_AMIN → PATIENT_TYPE",
    )

    # ---------------------------------------------------------
    # PATIENT_TYPE → PATIENT_NAME
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="NEW_PATIENT",
    )

    check(
        response["node"]["key"] == "PATIENT_NAME",
        "NEW_PATIENT → PATIENT_NAME",
    )

    # ---------------------------------------------------------
    # BACK → PATIENT_TYPE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    check(
        response["node"]["key"] == "PATIENT_TYPE",
        "BACK returns to PATIENT_TYPE",
    )

    # ---------------------------------------------------------
    # BACK → SELECT_DENTIST
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    check(
        response["node"]["key"] == "SELECT_DENTIST",
        "BACK returns to SELECT_DENTIST",
    )

    # ---------------------------------------------------------
    # BACK → SELECT_SERVICE
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="__BACK__",
    )

    check(
        response["node"]["key"] == "SELECT_SERVICE",
        "BACK returns to SELECT_SERVICE",
    )

    # ---------------------------------------------------------
    # MAIN_MENU → MAIN_MENU
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="__MAIN_MENU__",
    )

    check(
        response["node"]["key"] == "MAIN_MENU",
        "MAIN_MENU returns to MAIN_MENU",
    )

    # ---------------------------------------------------------
    # Start appointment again
    # ---------------------------------------------------------

    response = engine.process_input(
        session_token,
        option_key="BOOK_APPOINTMENT",
    )

    check(
        response["node"]["key"] == "SELECT_SERVICE",
        "Can start appointment again after MAIN_MENU",
    )
    

def print_result() -> None:
    print()
    print("=" * 70)
    print("TEST RESULT")
    print("=" * 70)
    print(f"PASSED = {PASSED}")
    print(f"FAILED = {FAILED}")

    if FAILED == 0:
        print("RESULT = PASSED")
    else:
        print("RESULT = FAILED")

    print("=" * 70)


def main():
    engine = ChatEngine()

    test_full_happy_path(engine)
    test_validation(engine)
    test_back_navigation(engine)
    test_main_menu_navigation(engine)

    print_result()

    if FAILED > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()