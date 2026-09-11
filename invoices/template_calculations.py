from decimal import Decimal, ROUND_HALF_UP


VISIT_TYPES = [
    (
        "AM",
        "am_minutes",
        "am_carers",
        "am_visits"
    ),
    (
        "Lunch",
        "lunch_minutes",
        "lunch_carers",
        "lunch_visits"
    ),
    (
        "Tea",
        "tea_minutes",
        "tea_carers",
        "tea_visits"
    ),
    (
        "Evening",
        "evening_minutes",
        "evening_carers",
        "evening_visits"
    )
]


def clean_decimal(value):
    if value is None:
        return None

    try:
        return Decimal(
            str(value)
            .replace("£", "")
            .replace(",", "")
            .strip()
        )

    except:
        return None


def get_care_type(carer_count):
    if carer_count == 2:
        return "Double Handed"

    if carer_count == 1:
        return "Single Handed"

    return "Care Services"


def build_template_invoice_lines(user):
    rate = clean_decimal(
        user.get("rate")
    )

    monthly_hours = clean_decimal(
        user.get("monthly_hours")
    )

    if rate is None:
        return {
            "lines": [],
            "status": "INVALID RATE",
            "calculated_hours": None,
            "expected_hours": monthly_hours,
            "difference": None
        }

    if monthly_hours is None:
        return {
            "lines": [],
            "status": "MISSING MONTHLY HOURS",
            "calculated_hours": None,
            "expected_hours": None,
            "difference": None
        }

    invoice_lines = []
    total_hours = Decimal("0")

    for (
        visit_type,
        minutes_field,
        carers_field,
        visits_field
    ) in VISIT_TYPES:

        minutes = clean_decimal(
            user.get(minutes_field)
        )

        carers = clean_decimal(
            user.get(carers_field)
        )

        visits = clean_decimal(
            user.get(visits_field)
        )

        if (
            minutes is None
            or carers is None
            or visits is None
        ):
            continue

        if (
            minutes <= 0
            or carers <= 0
            or visits <= 0
        ):
            continue

        line_hours = (
            minutes
            * carers
            * visits
            / Decimal("60")
        )

        amount = (
            line_hours
            * rate
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        care_type = get_care_type(
            int(carers)
        )

        if carers > 1:

            description = (
                f"{visit_type} "
                f"{int(minutes)} Mins "
                f"x {int(carers)} "
                f"x {int(visits)}"
            )

        else:

            description = (
                f"{visit_type} "
                f"{int(minutes)} Mins "
                f"x {int(visits)}"
            )

        invoice_lines.append({
            "care_type": care_type,
            "description": description,
            "hours": float(line_hours),
            "rate": float(rate),
            "amount": amount
        })

        total_hours += line_hours

    # Waking nights
    waking_hours = clean_decimal(
        user.get("waking_night_hours")
    )

    waking_carers = clean_decimal(
        user.get("waking_night_carers")
    )

    waking_visits = clean_decimal(
        user.get("waking_night_visits")
    )

    if (
        waking_hours is not None
        and waking_carers is not None
        and waking_visits is not None
        and waking_hours > 0
        and waking_carers > 0
        and waking_visits > 0
    ):

        line_hours = (
            waking_hours
            * waking_carers
            * waking_visits
        )

        amount = (
            line_hours
            * rate
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        care_type = get_care_type(
            int(waking_carers)
        )

        if waking_carers > 1:

            description = (
                f"Waking Night "
                f"{float(waking_hours):g} Hours "
                f"x {int(waking_carers)} "
                f"x {int(waking_visits)}"
            )

        else:

            description = (
                f"Waking Night "
                f"{float(waking_hours):g} Hours "
                f"x {int(waking_visits)}"
            )

        invoice_lines.append({
            "care_type": care_type,
            "description": description,
            "hours": float(line_hours),
            "rate": float(rate),
            "amount": amount
        })

        total_hours += line_hours

    difference = (
        monthly_hours
        - total_hours
    )

    if not invoice_lines:
        status = "NO STRUCTURED VISITS"

    elif abs(difference) <= Decimal("0.01"):
        status = "MATCHED"

    else:
        status = "REVIEW"

    return {
        "lines": invoice_lines,
        "status": status,
        "calculated_hours": total_hours,
        "expected_hours": monthly_hours,
        "difference": difference
    }