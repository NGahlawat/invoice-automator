from decimal import Decimal, ROUND_HALF_UP


def classify_visit(start_time):
    hour = int(
        start_time.split(":")[0]
    )

    if hour < 12:
        return "AM"

    elif hour < 15:
        return "Lunch"

    elif hour < 18:
        return "Tea"

    else:
        return "Evening"


def summarise_appointments(appointments):
    summary = {}

    for appointment in appointments:

        if appointment["cancelled"]:
            continue

        start_time = appointment.get(
            "start_time"
        )

        duration = appointment.get(
            "duration_minutes"
        )

        carer_count = appointment.get(
            "carer_count",
            1
        )

        if not start_time:
            continue

        if not duration:
            continue

        if not carer_count:
            carer_count = 1

        visit_type = classify_visit(
            start_time
        )

        key = (
            visit_type,
            duration,
            carer_count
        )

        if key not in summary:

            summary[key] = {
                "visit_type": visit_type,
                "duration": duration,
                "carer_count": carer_count,
                "visits": 0,
                "minutes": 0
            }

        summary[key]["visits"] += 1

        summary[key]["minutes"] += (
            duration
            * carer_count
        )

    for item in summary.values():

        item["hours"] = (
            item["minutes"]
            / 60
        )

    return list(
        summary.values()
    )


def create_invoice_lines(
    summary,
    rate
):
    invoice_lines = []

    rate = Decimal(
        str(rate)
    )

    visit_order = {
        "AM": 1,
        "Lunch": 2,
        "Tea": 3,
        "Evening": 4
    }

    summary = sorted(
        summary,
        key=lambda item: (
            item["carer_count"] * -1,
            visit_order.get(
                item["visit_type"],
                99
            ),
            item["duration"]
        )
    )

    for item in summary:

        hours = Decimal(
            str(item["hours"])
        )

        amount = (
            hours * rate
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        visit_type = item[
            "visit_type"
        ]

        duration = item[
            "duration"
        ]

        visits = item[
            "visits"
        ]

        carer_count = item[
            "carer_count"
        ]

        if carer_count > 1:

            description = (
                f"{visit_type} "
                f"{duration} Mins "
                f"x {carer_count} "
                f"x {visits}"
            )

            care_type = (
                "Double Handed"
            )

        else:

            description = (
                f"{visit_type} "
                f"{duration} Mins "
                f"x {visits}"
            )

            care_type = (
                "Single Handed"
            )

        invoice_lines.append({
            "care_type": care_type,
            "description": description,
            "hours": float(hours),
            "rate": float(rate),
            "amount": amount
        })

    return invoice_lines


def get_nourish_hour_breakdown(
    appointments
):
    active_minutes = 0
    cancelled_minutes = 0

    for appointment in appointments:

        duration = appointment.get(
            "duration_minutes"
        )

        carer_count = appointment.get(
            "carer_count",
            1
        )

        if duration is None:
            continue

        if not carer_count:
            carer_count = 1

        minutes = (
            duration
            * carer_count
        )

        if appointment.get(
            "cancelled",
            False
        ):

            cancelled_minutes += (
                minutes
            )

        else:

            active_minutes += (
                minutes
            )

    active_hours = (
        Decimal(
            str(active_minutes)
        )
        / Decimal("60")
    )

    cancelled_hours = (
        Decimal(
            str(cancelled_minutes)
        )
        / Decimal("60")
    )

    scheduled_hours = (
        active_hours
        + cancelled_hours
    )

    return (
        active_hours,
        cancelled_hours,
        scheduled_hours
    )