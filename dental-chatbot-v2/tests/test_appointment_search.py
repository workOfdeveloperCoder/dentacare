from app.chat_engine import ChatEngine


FLOW_KEY = "dental_reception"


def check(condition, message):
    if condition:
        print(f"PASS | {message}")
    else:
        print(f"FAIL | {message}")
        raise AssertionError(message)


def main():
    print("=" * 70)
    print("APPOINTMENT SEARCH TEST")
    print("=" * 70)

    engine = ChatEngine()

    # ------------------------------------------------
    # Start session
    # ------------------------------------------------

    response = engine.start_session(
        flow_key=FLOW_KEY
    )

    check(
        response["node"]["key"] == "MAIN_MENU",
        "Session starts at MAIN_MENU",
    )

    session_token = response["session_token"]

    # ------------------------------------------------
    # Find appointment
    # ------------------------------------------------

    response = engine.process_input(
        session_token=session_token,
        option_key="FIND_APPOINTMENT",
    )

    check(
        response["node"]["key"]
        == "APPOINTMENT_SEARCH_METHOD",
        "FIND_APPOINTMENT opens search method",
    )

    check(
        len(response["node"]["options"]) == 3,
        "Search method contains three options",
    )

    # ------------------------------------------------
    # Search by phone
    # ------------------------------------------------

    response = engine.process_input(
        session_token=session_token,
        option_key="SEARCH_BY_PHONE",
    )

    check(
        response["node"]["key"]
        == "APPOINTMENT_SEARCH_PHONE",
        "SEARCH_BY_PHONE opens phone search",
    )

    # ------------------------------------------------
    # Submit phone number
    # ------------------------------------------------

    response = engine.process_input(
        session_token=session_token,
        message="03001234567",
    )

    # ------------------------------------------------
    # Search must transition to RESULTS
    # ------------------------------------------------

    check(
        response["node"]["key"]
        == "APPOINTMENT_SEARCH_RESULTS",
        "Phone search transitions to appointment results",
    )

    check(
        response["node"]["type"] == "menu",
        "Appointment results are presented as a menu",
    )

    check(
        len(response["node"]["options"]) > 0,
        "Phone search returns appointment results",
    )

    # ------------------------------------------------
    # Validate dynamic appointment options
    # ------------------------------------------------

    for option in response["node"]["options"]:

        check(
            option["option_key"].startswith(
                "APPOINTMENT_"
            ),
            "Appointment result uses dynamic appointment option",
        )

        check(
            option.get("label"),
            "Appointment result contains a label",
        )

    # ------------------------------------------------
    # Display search result
    # ------------------------------------------------

    print()
    print("Search response:")
    print(response)

    # ------------------------------------------------
    # Select first appointment
    # ------------------------------------------------

    first_appointment_option = (
        response["node"]["options"][0]
    )

    selected_option_key = (
        first_appointment_option["option_key"]
    )

    print()
    print(
        "Selecting appointment:",
        selected_option_key,
    )

    details_response = engine.process_input(
        session_token=session_token,
        message=None,
        option_key=selected_option_key,
    )

    # ------------------------------------------------
    # Appointment details
    # ------------------------------------------------

    check(
        details_response["node"]["key"]
        == "APPOINTMENT_DETAILS",
        "Selecting appointment opens appointment details",
    )

    check(
        details_response["node"]["type"] == "menu",
        "Appointment details are presented as a menu",
    )

    details_message = (
        details_response["node"]["message"]
    )

    check(
        "Patient:" in details_message,
        "Appointment details contain patient",
    )

    check(
        "Service:" in details_message,
        "Appointment details contain service",
    )

    check(
        "Dentist:" in details_message,
        "Appointment details contain dentist",
    )

    check(
        "Date:" in details_message,
        "Appointment details contain date",
    )

    check(
        "Time:" in details_message,
        "Appointment details contain time",
    )

    check(
        "Status: Confirmed" in details_message,
        "Appointment details contain confirmed status",
    )

    # ------------------------------------------------
    # Validate detail actions
    # ------------------------------------------------

    detail_options = (
        details_response["node"]["options"]
    )

    check(
        any(
            option["option_key"].startswith(
                "APPOINTMENT_CANCEL:"
            )
            for option in detail_options
        ),
        "Cancel Appointment option exists",
    )

    check(
        any(
            option["option_key"]
            == "APPOINTMENT_BACK_TO_RESULTS"
            for option in detail_options
        ),
        "Back to Results option exists",
    )

    check(
        any(
            option["option_key"]
            == "__MAIN_MENU__"
            for option in detail_options
        ),
        "Main Menu option exists",
    )

    # ------------------------------------------------
    # Display details result
    # ------------------------------------------------

    print()
    print("Details response:")
    print(details_response)

    print()
    print("=" * 70)
    print("APPOINTMENT SEARCH TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()