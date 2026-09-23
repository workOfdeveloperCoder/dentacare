from datetime import date, time
import re


class ValidationResult:
    def __init__(
        self,
        valid: bool,
        message: str | None = None,
    ):
        self.valid = valid
        self.message = message


def validate_input(
    validation_type: str | None,
    value: str | None,
) -> ValidationResult:

    if value is None:
        return ValidationResult(
            False,
            "Please provide a value.",
        )

    value = str(value).strip()

    if not value:
        return ValidationResult(
            False,
            "Please provide a value.",
        )

    if not validation_type:
        return ValidationResult(True)

    validators = {
        "name": _validate_name,
        "text": _validate_text,
        "phone": _validate_phone,
        "pakistan_mobile": _validate_pakistan_mobile,
        "email": _validate_email,
        "future_date": _validate_future_date,
        "appointment_date": _validate_future_date,
        "time": _validate_time,
        "appointment_time": _validate_time,
        "clinic_hours": _validate_time,
        "number": _validate_number,
        "confirmation": _validate_confirmation,
    }

    validator = validators.get(validation_type)

    if validator is None:
        raise ValueError(
            f"Unsupported validation_type: {validation_type}"
        )

    return validator(value)


def _validate_text(value: str) -> ValidationResult:

    if len(value) < 1:
        return ValidationResult(
            False,
            "Please provide a value.",
        )

    if len(value) > 500:
        return ValidationResult(
            False,
            "That answer is too long.",
        )

    return ValidationResult(True)


def _validate_phone(value: str) -> ValidationResult:

    normalized = re.sub(r"[\s()-]", "", value)

    if not re.fullmatch(r"^\+?[0-9]{8,15}$", normalized):
        return ValidationResult(
            False,
            "Please enter a valid phone number.",
        )

    return ValidationResult(True)


def _validate_number(value: str) -> ValidationResult:

    try:
        amount = float(value.replace(",", ""))
    except ValueError:
        return ValidationResult(
            False,
            "Please enter a valid number.",
        )

    if amount <= 0:
        return ValidationResult(
            False,
            "Please enter a number greater than zero.",
        )

    return ValidationResult(True)


def _validate_name(value: str) -> ValidationResult:

    if len(value) < 2:
        return ValidationResult(
            False,
            "Please enter your full name.",
        )

    if len(value) > 150:
        return ValidationResult(
            False,
            "Name is too long.",
        )

    if not re.fullmatch(
        r"[A-Za-zÀ-ÖØ-öø-ÿ.'-]+"
        r"(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ.'-]+)*",
        value,
    ):
        return ValidationResult(
            False,
            "Please enter a valid name.",
        )

    return ValidationResult(True)


def _validate_pakistan_mobile(value: str) -> ValidationResult:

    normalized = re.sub(
        r"[\s-]",
        "",
        value,
    )

    patterns = (
        r"^\+92[0-9]{10}$",
        r"^92[0-9]{10}$",
        r"^03[0-9]{9}$",
    )

    if not any(
        re.fullmatch(pattern, normalized)
        for pattern in patterns
    ):
        return ValidationResult(
            False,
            "Please enter a valid Pakistan mobile number.",
        )

    return ValidationResult(True)


def _validate_email(value: str) -> ValidationResult:

    if len(value) > 254:
        return ValidationResult(
            False,
            "Email address is too long.",
        )

    pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@"
        r"[A-Za-z0-9]"
        r"(?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
        r"(?:\.[A-Za-z0-9]"
        r"(?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
    )

    if not re.fullmatch(pattern, value):
        return ValidationResult(
            False,
            "Please enter a valid email address.",
        )

    return ValidationResult(True)


def _validate_future_date(value: str) -> ValidationResult:

    try:
        selected_date = date.fromisoformat(value)

    except ValueError:
        return ValidationResult(
            False,
            "Please enter a valid date in YYYY-MM-DD format.",
        )

    if selected_date <= date.today():
        return ValidationResult(
            False,
            "Please select a future date.",
        )

    return ValidationResult(True)


def _validate_time(value: str) -> ValidationResult:

    try:
        time.fromisoformat(value)

    except ValueError:
        return ValidationResult(
            False,
            "Please enter a valid time in HH:MM format.",
        )

    return ValidationResult(True)


def _validate_confirmation(value: str) -> ValidationResult:

    normalized = value.strip().lower()

    if normalized in {
        "yes",
        "y",
        "confirm",
        "confirmed",
    }:
        return ValidationResult(True)

    return ValidationResult(
        False,
        "Please confirm to continue.",
    )