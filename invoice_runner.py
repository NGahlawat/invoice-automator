from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv
import zipfile

from config import OUTPUT_FOLDER
from accounts.template_reader import read_template
from accounts.template_writer import update_nourish_details
from accounts.settings_reader import read_company_settings
from invoices.calculations import (
    create_invoice_lines,
    get_nourish_hour_breakdown,
    summarise_appointments,
)
from invoices.generator import create_invoice
from nourish.scraper import (
    close_nourish,
    find_client_match,
    get_appointments_for_period,
    get_nourish_users,
    start_nourish,
)


def update_progress(callback, percent, message):
    if callback:
        callback(percent, message)


def get_accounts_file(month, year):
    month_name = date(year, month, 1).strftime("%B")
    return f"data/accounts/Invoice_Accounts_{month_name}_{year}.xlsx"


def get_invoice_date(month, year, rule):
    rule = str(rule or "").lower()

    if rule == "first day of following month":
        if month == 12:
            return date(year + 1, 1, 1)
        return date(year, month + 1, 1)

    raise ValueError(
        "Unknown invoice date rule: " + str(rule)
    )


def make_invoice_prefix(month, year, prefix_format):
    invoice_month = date(year, month, 1)
    prefix_format = str(prefix_format or "")

    if not prefix_format:
        raise ValueError(
            "Invoice Prefix Format is missing from Company Settings."
        )

    prefix = prefix_format
    prefix = prefix.replace("{YYYY}", str(year))
    prefix = prefix.replace("{YY}", str(year)[2:])
    prefix = prefix.replace(
        "{MONTH}",
        invoice_month.strftime("%B").upper()
    )
    prefix = prefix.replace(
        "{MON}",
        invoice_month.strftime("%b").upper()
    )
    prefix = prefix.replace("{MM}", f"{month:02d}")

    return prefix


def get_month_settings(month, year, company_settings):
    last_day = monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    invoice_date = get_invoice_date(
        month,
        year,
        company_settings.get("invoice_date_rule")
    )

    invoice_prefix = make_invoice_prefix(
        month,
        year,
        company_settings.get("invoice_prefix_format")
    )

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "invoice_date": invoice_date.strftime("%d/%m/%Y"),
        "invoice_period": (
            start_date.strftime("%d/%m/%Y")
            + " - "
            + end_date.strftime("%d/%m/%Y")
        ),
        "invoice_prefix": invoice_prefix,
    }


def clean_reference(reference):
    if not reference:
        return None

    return (
        str(reference)
        .upper()
        .replace(" ", "")
        .strip()
    )


def make_invoice_number(reference, invoice_prefix):
    reference = clean_reference(reference)

    if not reference:
        return None

    return invoice_prefix + reference


def decimal_value(value):
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def calculate_invoice_total(hours, rate):
    hours = decimal_value(hours)
    rate = decimal_value(rate)

    if hours is None or rate is None:
        return None

    return (hours * rate).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def build_visit_breakdown(summary):
    if not summary:
        return "No active Nourish visits found"

    parts = []

    for item in summary:
        visit_type = item["visit_type"]
        duration = item["duration"]
        carers = item["carer_count"]
        visits = item["visits"]

        if carers > 1:
            text = (
                f"{visit_type} {duration} mins "
                f"x {carers} carers x {visits}"
            )
        else:
            text = (
                f"{visit_type} {duration} mins "
                f"x {visits}"
            )

        parts.append(text)

    return "; ".join(parts)


def get_nourish_data(
    page,
    nourish_users,
    user,
    start_date,
    end_date
):
    nourish_id = user.get("nourish_id")
    nourish_name = None
    match_status = None

    if nourish_id:
        match_status = "stored_id"
        nourish_name = user.get("name")
    else:
        match = find_client_match(
            nourish_users,
            user["name"]
        )

        match_status = match["status"]
        nourish_id = match["id"]
        nourish_name = match["nourish_name"]

    if not nourish_id:
        if match_status == "possible":
            notes = (
                "Possible Nourish match found but "
                "not safe enough to use"
            )
        else:
            notes = (
                "Client could not be matched "
                "to current Nourish users"
            )

        return {
            "success": False,
            "status": "NOT VALIDATED",
            "match_status": match_status,
            "nourish_name": nourish_name,
            "nourish_id": None,
            "nourish_hours": None,
            "cancelled_hours": None,
            "appointments": [],
            "summary": [],
            "visit_breakdown": None,
            "notes": notes,
        }

    try:
        appointments = get_appointments_for_period(
            page,
            nourish_id,
            start_date,
            end_date
        )
    except Exception as error:
        error_text = str(error)

        if (
            "session limit" in error_text.lower()
            or "session has expired" in error_text.lower()
            or "reconnect nourish" in error_text.lower()
        ):
            raise RuntimeError(error_text)

        return {
            "success": False,
            "status": "NOT VALIDATED",
            "match_status": match_status,
            "nourish_name": nourish_name,
            "nourish_id": nourish_id,
            "nourish_hours": None,
            "cancelled_hours": None,
            "appointments": [],
            "summary": [],
            "visit_breakdown": None,
            "notes": "Could not read Nourish roster: " + error_text,
        }

    active_hours, cancelled_hours, _ = (
        get_nourish_hour_breakdown(appointments)
    )

    summary = summarise_appointments(appointments)

    return {
        "success": True,
        "status": "VALIDATED",
        "match_status": match_status,
        "nourish_name": nourish_name,
        "nourish_id": nourish_id,
        "nourish_hours": active_hours,
        "cancelled_hours": cancelled_hours,
        "appointments": appointments,
        "summary": summary,
        "visit_breakdown": build_visit_breakdown(summary),
        "notes": "Nourish roster loaded successfully",
    }


def add_override_adjustment(
    invoice_lines,
    override_hours,
    nourish_hours,
    rate
):
    difference = override_hours - nourish_hours

    if abs(difference) <= Decimal("0.01"):
        return invoice_lines

    amount = (difference * rate).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    invoice_lines.append({
        "care_type": "Billing Adjustment",
        "description": "Billing hours override adjustment",
        "hours": float(difference),
        "rate": float(rate),
        "amount": amount,
    })

    return invoice_lines


def write_reports(generated, exceptions, validation_report):
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    with open(
        OUTPUT_FOLDER / "validation_report.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "name",
                "reference",
                "nourish_name",
                "nourish_id",
                "match_status",
                "validation_status",
                "nourish_hours",
                "override_hours",
                "billing_hours",
                "cancelled_hours",
                "difference",
                "notes",
            ]
        )
        writer.writeheader()
        writer.writerows(validation_report)

    with open(
        OUTPUT_FOLDER / "invoice_batch.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "name",
                "invoice_number",
                "reference",
                "funding_type",
                "hours",
                "rate",
                "total",
                "nourish_validation",
                "file",
            ]
        )
        writer.writeheader()
        writer.writerows(generated)

    with open(
        OUTPUT_FOLDER / "invoice_exceptions.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "name",
                "reason",
                "nourish_hours",
                "override_hours",
                "billing_hours",
            ]
        )
        writer.writeheader()
        writer.writerows(exceptions)


def run_invoice_batch(
    month,
    year,
    accounts_file=None,
    progress_callback=None
):
    update_progress(
        progress_callback,
        5,
        "Preparing invoice run..."
    )

    if accounts_file is None:
        accounts_file = get_accounts_file(
            month,
            year
        )

    if not Path(accounts_file).exists():
        raise FileNotFoundError(
            "Accounts file not found: " + str(accounts_file)
        )

    update_progress(
        progress_callback,
        10,
        "Reading company settings..."
    )

    company_settings = read_company_settings(
        accounts_file
    )

    month_settings = get_month_settings(
        month,
        year,
        company_settings
    )

    start_date = month_settings["start_date"]
    end_date = month_settings["end_date"]
    invoice_date = month_settings["invoice_date"]
    invoice_period = month_settings["invoice_period"]
    invoice_prefix = month_settings["invoice_prefix"]

    update_progress(
        progress_callback,
        15,
        "Reading service users..."
    )

    users = read_template(accounts_file)

    generated = []
    exceptions = []
    validation_report = []

    update_progress(
        progress_callback,
        20,
        "Connecting to Nourish..."
    )

    p = None
    browser = None

    try:
        try:
            p, browser, context, page = start_nourish()
            nourish_users = get_nourish_users(page)
        except Exception as error:
            raise RuntimeError(
                "Nourish connection failed: " + str(error)
            )

        update_progress(
            progress_callback,
            30,
            "Connected to Nourish."
        )

        total_users = len(users)

        for index, user in enumerate(users, start=1):
            name = user["name"]

            if total_users:
                user_percent = 30 + int(
                    (index / total_users) * 50
                )
            else:
                user_percent = 80

            update_progress(
                progress_callback,
                user_percent,
                f"Processing {name} ({index}/{total_users})..."
            )

            nourish = get_nourish_data(
                page,
                nourish_users,
                user,
                start_date,
                end_date
            )

            override_hours = decimal_value(
                user.get("billing_hours_override")
            )

            nourish_hours = nourish.get("nourish_hours")

            if nourish_hours is not None:
                nourish_hours = decimal_value(nourish_hours)

            difference = None
            billing_hours = None
            validation_status = nourish["status"]
            validation_notes = nourish["notes"]

            if nourish["success"]:
                if override_hours is None:
                    billing_hours = nourish_hours
                    validation_status = "VALIDATED"
                    validation_notes = (
                        "Nourish billable hours used for invoice"
                    )
                else:
                    billing_hours = override_hours
                    difference = override_hours - nourish_hours

                    if abs(difference) <= Decimal("0.01"):
                        validation_status = "VALIDATED"
                        validation_notes = (
                            "Billing override matches Nourish hours"
                        )
                    else:
                        validation_status = "REVIEW"
                        validation_notes = (
                            "Billing override differs from Nourish hours"
                        )

            update_nourish_details(
                accounts_file,
                user["excel_row"],
                nourish_id=nourish.get("nourish_id"),
                nourish_hours=nourish_hours,
                visit_breakdown=nourish.get("visit_breakdown"),
                hours_difference=difference,
                validation_status=validation_status,
                validation_notes=validation_notes,
            )

            validation_report.append({
                "name": name,
                "reference": user.get("reference"),
                "nourish_name": nourish.get("nourish_name"),
                "nourish_id": nourish.get("nourish_id"),
                "match_status": nourish.get("match_status"),
                "validation_status": validation_status,
                "nourish_hours": (
                    float(nourish_hours)
                    if nourish_hours is not None
                    else None
                ),
                "override_hours": (
                    float(override_hours)
                    if override_hours is not None
                    else None
                ),
                "billing_hours": (
                    float(billing_hours)
                    if billing_hours is not None
                    else None
                ),
                "cancelled_hours": (
                    float(nourish["cancelled_hours"])
                    if nourish.get("cancelled_hours") is not None
                    else None
                ),
                "difference": (
                    float(difference)
                    if difference is not None
                    else None
                ),
                "notes": validation_notes,
            })

            if not nourish["success"]:
                exceptions.append({
                    "name": name,
                    "reason": validation_notes,
                    "nourish_hours": None,
                    "override_hours": (
                        float(override_hours)
                        if override_hours is not None
                        else None
                    ),
                    "billing_hours": None,
                })
                continue

            rate = decimal_value(user.get("rate"))

            if rate is None or rate <= 0:
                exceptions.append({
                    "name": name,
                    "reason": "INVALID RATE",
                    "nourish_hours": float(nourish_hours),
                    "override_hours": (
                        float(override_hours)
                        if override_hours is not None
                        else None
                    ),
                    "billing_hours": (
                        float(billing_hours)
                        if billing_hours is not None
                        else None
                    ),
                })
                continue

            if billing_hours is None or billing_hours <= 0:
                exceptions.append({
                    "name": name,
                    "reason": "NO BILLABLE HOURS",
                    "nourish_hours": float(nourish_hours),
                    "override_hours": (
                        float(override_hours)
                        if override_hours is not None
                        else None
                    ),
                    "billing_hours": (
                        float(billing_hours)
                        if billing_hours is not None
                        else None
                    ),
                })
                continue

            invoice_lines = create_invoice_lines(
                nourish["summary"],
                rate
            )

            if override_hours is not None:
                invoice_lines = add_override_adjustment(
                    invoice_lines,
                    override_hours,
                    nourish_hours,
                    rate
                )

            reference = user.get("reference")
            invoice_number = make_invoice_number(
                reference,
                invoice_prefix
            )

            if invoice_number is None:
                exceptions.append({
                    "name": name,
                    "reason": "MISSING REFERENCE",
                    "nourish_hours": float(nourish_hours),
                    "override_hours": (
                        float(override_hours)
                        if override_hours is not None
                        else None
                    ),
                    "billing_hours": float(billing_hours),
                })
                continue

            total = calculate_invoice_total(
                billing_hours,
                rate
            )

            if total is None:
                exceptions.append({
                    "name": name,
                    "reason": "INVALID TOTAL",
                    "nourish_hours": float(nourish_hours),
                    "override_hours": (
                        float(override_hours)
                        if override_hours is not None
                        else None
                    ),
                    "billing_hours": float(billing_hours),
                })
                continue

            try:
                invoice_file = create_invoice(
                    user=user,
                    invoice_lines=invoice_lines,
                    total=total,
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    period=invoice_period,
                    company_settings=company_settings
                )
            except Exception as error:
                exceptions.append({
                    "name": name,
                    "reason": str(error),
                    "nourish_hours": float(nourish_hours),
                    "override_hours": (
                        float(override_hours)
                        if override_hours is not None
                        else None
                    ),
                    "billing_hours": float(billing_hours),
                })
                continue

            generated.append({
                "name": name,
                "invoice_number": invoice_number,
                "reference": reference,
                "funding_type": user.get("funding_type"),
                "hours": float(billing_hours),
                "rate": float(rate),
                "total": float(total),
                "nourish_validation": validation_status,
                "file": str(invoice_file),
            })

    finally:
        update_progress(
            progress_callback,
            82,
            "Closing Nourish..."
        )

        if p is not None and browser is not None:
            try:
                close_nourish(p, browser)
            except Exception:
                pass

    update_progress(
        progress_callback,
        90,
        "Creating reports..."
    )

    write_reports(
        generated,
        exceptions,
        validation_report
    )

        # --------------------------------------------------
    # CREATE ZIP OF GENERATED INVOICES
    # --------------------------------------------------

    zip_name = (
        f"Invoices_{date(year, month, 1).strftime('%B')}_{year}.zip"
    )

    zip_path = (
        OUTPUT_FOLDER
        / zip_name
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        for invoice in generated:

            invoice_path = Path(
                invoice["file"]
            )

            if invoice_path.exists():

                zip_file.write(
                    invoice_path,
                    arcname=invoice_path.name
                )

    validated = 0
    review = 0
    not_validated = 0

    for result in validation_report:
        status = result["validation_status"]

        if status == "VALIDATED":
            validated += 1
        elif status == "REVIEW":
            review += 1
        else:
            not_validated += 1

    result = {
        "month": month,
        "year": year,
        "accounts_file": str(accounts_file),
        "invoice_date": invoice_date,
        "invoice_period": invoice_period,
        "invoice_prefix": invoice_prefix,
        "invoice_zip": zip_name,
        "users": len(users),
        "generated": generated,
        "exceptions": exceptions,
        "validation_report": validation_report,
        "generated_count": len(generated),
        "exception_count": len(exceptions),
        "validated_count": validated,
        "review_count": review,
        "not_validated_count": not_validated,
    }

    update_progress(
        progress_callback,
        100,
        "Complete"
    )

    return result
