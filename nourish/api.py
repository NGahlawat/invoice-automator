import re


def find_appointment_data(data):
    if isinstance(data, dict):

        appointment_count = 0

        for value in data.values():

            if isinstance(value, dict):

                tooltip = value.get(
                    "tooltip",
                    {}
                )

                if (
                    tooltip.get("type")
                    == "appointment"
                ):
                    appointment_count += 1

        if appointment_count > 0:
            return data

        for value in data.values():

            result = find_appointment_data(
                value
            )

            if result is not None:
                return result

    elif isinstance(data, list):

        for value in data:

            result = find_appointment_data(
                value
            )

            if result is not None:
                return result

    return None


def parse_duration(duration_text):
    if not duration_text:
        return None

    text = (
        str(duration_text)
        .lower()
        .strip()
    )

    total_minutes = 0

    # e.g. "1 hour", "2 hours"
    hour_match = re.search(
        r"(\d+)\s*(hour|hours|hr|hrs)",
        text
    )

    if hour_match:

        hours = int(
            hour_match.group(1)
        )

        total_minutes += (
            hours * 60
        )

    # e.g. "30 minutes", "45 mins"
    minute_match = re.search(
        r"(\d+)\s*(minute|minutes|min|mins)",
        text
    )

    if minute_match:

        minutes = int(
            minute_match.group(1)
        )

        total_minutes += minutes

    if total_minutes > 0:
        return total_minutes

    # fallback for values such as just "45"
    number_match = re.search(
        r"\d+",
        text
    )

    if number_match:
        return int(
            number_match.group()
        )

    return None


def extract_appointments(settings):
    items = find_appointment_data(
        settings
    )

    if items is None:
        return []

    appointments = []

    for appointment_id, appointment in items.items():

        tooltip = appointment.get(
            "tooltip",
            {}
        )

        if (
            tooltip.get("type")
            != "appointment"
        ):
            continue

        details = {}

        for row in tooltip.get(
            "rows",
            []
        ):

            details[
                row.get("id")
            ] = row.get("value")

        time_value = details.get(
            "time",
            ""
        )

        if " - " in time_value:

            start_time, end_time = (
                time_value.split(
                    " - ",
                    1
                )
            )

        else:

            start_time = None
            end_time = None

        duration_text = details.get(
            "duration",
            ""
        )

        duration_minutes = (
            parse_duration(
                duration_text
            )
        )

        carers = appointment.get(
            "carers",
            []
        )

        carer_count = 0

        for carer in carers:

            if str(carer) not in [
                "-1",
                "0"
            ]:

                carer_count += 1

        appointments.append({
            "id": appointment.get("id"),

            "client": details.get(
                "client"
            ),

            "address": details.get(
                "address"
            ),

            "date": appointment.get(
                "date"
            ),

            "start_time": start_time,

            "end_time": end_time,

            "duration_minutes": (
                duration_minutes
            ),

            "carer_count": carer_count,

            "cancelled": appointment.get(
                "cancelled",
                False
            )
        })

    return appointments