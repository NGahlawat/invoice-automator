import re


def detect_care_type(text):
    if not text:
        return "Care Services"

    text = text.lower()

    if (
        "double handed" in text
        or "double-handed" in text
        or "d handed" in text
        or " dh " in f" {text} "
    ):
        return "Double Handed"

    if (
        "single handed" in text
        or "single-handed" in text
        or " sh " in f" {text} "
    ):
        return "Single Handed"

    return "Care Services"


def find_duration(text, labels):
    for label in labels:

        pattern = (
            rf"{label}"
            rf"[^0-9]{{0,15}}"
            rf"(\d+)"
        )

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return int(
                match.group(1)
            )

    return None


def parse_poc_details(poc_details):
    if not poc_details:
        return {
            "care_type": "Care Services",
            "lines": [],
            "parsed": False
        }

    text = str(poc_details)

    care_type = detect_care_type(
        text
    )

    lines = []

    am = find_duration(
        text,
        [
            r"\bam\b",
            r"\bmorning\b"
        ]
    )

    lunch = find_duration(
        text,
        [
            r"\blunch\b",
            r"\blunchtime\b"
        ]
    )

    tea = find_duration(
        text,
        [
            r"\btea\b",
            r"\bteatime\b",
            r"\btea time\b"
        ]
    )

    evening = find_duration(
        text,
        [
            r"\bevening\b",
            r"\bbedtime\b",
            r"\blate evening\b",
            r"\bpm\b"
        ]
    )

    if am:
        lines.append({
            "visit_type": "AM",
            "duration": am
        })

    if lunch:
        lines.append({
            "visit_type": "Lunch",
            "duration": lunch
        })

    if tea:
        lines.append({
            "visit_type": "Tea",
            "duration": tea
        })

    if evening:
        lines.append({
            "visit_type": "Evening",
            "duration": evening
        })

    parsed = len(lines) > 0

    return {
        "care_type": care_type,
        "lines": lines,
        "parsed": parsed
    }