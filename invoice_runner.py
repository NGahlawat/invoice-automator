from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import csv

from config import OUTPUT_FOLDER
from accounts.template_reader import read_template
from accounts.template_writer import update_nourish_details
from accounts.settings_reader import read_company_settings

from invoices.template_calculations import (
    build_template_invoice_lines
)

from invoices.calculations import (
    get_nourish_hour_breakdown
)

from invoices.generator import (
    create_invoice
)

from nourish.scraper import (
    start_nourish,
    close_nourish,
    get_nourish_users,
    find_client_match,
    get_appointments_for_period
)




# --------------------------------------------------
# PROGRESS
# --------------------------------------------------

def update_progress(
    callback,
    percent,
    message
):

    if callback:

        callback(
            percent,
            message
        )


# --------------------------------------------------
# DEFAULT MONTH FILE
# --------------------------------------------------

def get_accounts_file(
    month,
    year
):

    month_name = date(
        year,
        month,
        1
    ).strftime(
        "%B"
    )


    return (
        f"data/accounts/"
        f"Invoice_Accounts_"
        f"{month_name}_{year}.xlsx"
    )


# --------------------------------------------------
# INVOICE DATE
# --------------------------------------------------

def get_invoice_date(
    month,
    year,
    rule
):

    rule = str(
        rule
        or ""
    ).lower()


    if (
        rule
        == "first day of following month"
    ):

        if month == 12:

            return date(
                year + 1,
                1,
                1
            )


        return date(
            year,
            month + 1,
            1
        )


    raise ValueError(
        "Unknown invoice date rule: "
        + str(
            rule
        )
    )


# --------------------------------------------------
# PREFIX
# --------------------------------------------------

def make_invoice_prefix(
    month,
    year,
    prefix_format
):

    invoice_month = date(
        year,
        month,
        1
    )


    prefix_format = str(
        prefix_format
        or ""
    )


    if not prefix_format:

        raise ValueError(
            "Invoice Prefix Format "
            "is missing from Company Settings."
        )


    prefix = prefix_format


    prefix = prefix.replace(
        "{YYYY}",
        str(
            year
        )
    )


    prefix = prefix.replace(
        "{YY}",
        str(
            year
        )[2:]
    )


    prefix = prefix.replace(
        "{MONTH}",
        invoice_month.strftime(
            "%B"
        ).upper()
    )


    prefix = prefix.replace(
        "{MON}",
        invoice_month.strftime(
            "%b"
        ).upper()
    )


    prefix = prefix.replace(
        "{MM}",
        f"{month:02d}"
    )


    return prefix


# --------------------------------------------------
# MONTH SETTINGS
# --------------------------------------------------

def get_month_settings(
    month,
    year,
    company_settings
):

    last_day = monthrange(
        year,
        month
    )[1]


    start_date = date(
        year,
        month,
        1
    )


    end_date = date(
        year,
        month,
        last_day
    )


    invoice_date = get_invoice_date(
        month,
        year,
        company_settings.get(
            "invoice_date_rule"
        )
    )


    invoice_prefix = make_invoice_prefix(
        month,
        year,
        company_settings.get(
            "invoice_prefix_format"
        )
    )


    return {
        "start_date": (
            start_date.strftime(
                "%Y-%m-%d"
            )
        ),

        "end_date": (
            end_date.strftime(
                "%Y-%m-%d"
            )
        ),

        "invoice_date": (
            invoice_date.strftime(
                "%d/%m/%Y"
            )
        ),

        "invoice_period": (
            start_date.strftime(
                "%d/%m/%Y"
            )
            + " - "
            + end_date.strftime(
                "%d/%m/%Y"
            )
        ),

        "invoice_prefix": (
            invoice_prefix
        )
    }


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def clean_reference(
    reference
):

    if not reference:

        return None


    return (
        str(
            reference
        )
        .upper()
        .replace(
            " ",
            ""
        )
        .strip()
    )


def make_invoice_number(
    reference,
    invoice_prefix
):

    reference = clean_reference(
        reference
    )


    if not reference:

        return None


    return (
        invoice_prefix
        + reference
    )


def decimal_value(
    value
):

    if value is None:

        return None


    try:

        return Decimal(
            str(
                value
            )
        )

    except:

        return None


def calculate_invoice_total(
    monthly_hours,
    rate
):

    hours = decimal_value(
        monthly_hours
    )


    rate = decimal_value(
        rate
    )


    if (
        hours is None
        or rate is None
    ):

        return None


    return (
        hours
        * rate
    ).quantize(
        Decimal(
            "0.01"
        ),
        rounding=ROUND_HALF_UP
    )


# --------------------------------------------------
# NOURISH VALIDATION
# --------------------------------------------------

def validate_with_nourish(
    page,
    nourish_users,
    user,
    start_date,
    end_date
):

    monthly_hours = decimal_value(
        user.get(
            "monthly_hours"
        )
    )


    if monthly_hours is None:

        return {
            "status": "NOT VALIDATED",
            "match_status": None,
            "nourish_name": None,
            "nourish_id": None,
            "accounts_hours": None,
            "nourish_hours": None,
            "cancelled_hours": None,
            "difference": None,
            "notes": (
                "Monthly billable hours missing"
            )
        }


    nourish_id = user.get(
        "nourish_id"
    )


    nourish_name = None
    match_status = None


    # --------------------------------------------------
    # STORED ID
    # --------------------------------------------------

    if nourish_id:

        match_status = (
            "stored_id"
        )


        nourish_name = user.get(
            "name"
        )


    # --------------------------------------------------
    # MATCH BY NAME
    # --------------------------------------------------

    else:

        match = find_client_match(
            nourish_users,
            user[
                "name"
            ]
        )


        match_status = match[
            "status"
        ]


        nourish_id = match[
            "id"
        ]


        nourish_name = match[
            "nourish_name"
        ]


    # --------------------------------------------------
    # NO MATCH
    # --------------------------------------------------

    if not nourish_id:

        if (
            match_status
            == "possible"
        ):

            notes = (
                "Possible Nourish match found "
                "but not safe enough to use"
            )

        else:

            notes = (
                "Client could not be matched "
                "to current Nourish users"
            )


        return {
            "status": "NOT VALIDATED",
            "match_status": match_status,
            "nourish_name": nourish_name,
            "nourish_id": None,
            "accounts_hours": monthly_hours,
            "nourish_hours": None,
            "cancelled_hours": None,
            "difference": None,
            "notes": notes
        }


    # --------------------------------------------------
    # ROSTER
    # --------------------------------------------------

    try:

        appointments = (
            get_appointments_for_period(
                page,
                nourish_id,
                start_date,
                end_date
            )
        )


    except Exception as error:

        error_text = str(
            error
        )


        # Session-level problems should stop
        # the whole run rather than silently
        # creating unvalidated invoices.

        if (
            "session limit"
            in error_text.lower()
            or "session has expired"
            in error_text.lower()
            or "reconnect nourish"
            in error_text.lower()
        ):

            raise RuntimeError(
                error_text
            )


        return {
            "status": "NOT VALIDATED",
            "match_status": match_status,
            "nourish_name": nourish_name,
            "nourish_id": nourish_id,
            "accounts_hours": monthly_hours,
            "nourish_hours": None,
            "cancelled_hours": None,
            "difference": None,
            "notes": (
                "Could not read Nourish roster: "
                + error_text
            )
        }


    (
        active_hours,
        cancelled_hours,
        scheduled_hours
    ) = get_nourish_hour_breakdown(
        appointments
    )


    difference = (
        monthly_hours
        - active_hours
    )


    if abs(
        difference
    ) <= Decimal(
        "0.01"
    ):

        status = (
            "VALIDATED"
        )


        notes = (
            "Accounts hours match "
            "Nourish active hours"
        )


    else:

        status = (
            "REVIEW"
        )


        notes = (
            "Accounts and Nourish "
            "hours differ"
        )


    return {
        "status": status,
        "match_status": match_status,
        "nourish_name": nourish_name,
        "nourish_id": nourish_id,
        "accounts_hours": monthly_hours,
        "nourish_hours": active_hours,
        "cancelled_hours": cancelled_hours,
        "difference": difference,
        "notes": notes
    }


# --------------------------------------------------
# REPORTS
# --------------------------------------------------

def write_reports(
    generated,
    exceptions,
    validation_report
):

    # --------------------------------------------------
    # VALIDATION REPORT
    # --------------------------------------------------

    with open(
        OUTPUT_FOLDER
        / "validation_report.csv",
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
                "accounts_hours",
                "nourish_hours",
                "cancelled_hours",
                "difference",
                "notes"
            ]
        )


        writer.writeheader()


        writer.writerows(
            validation_report
        )


    # --------------------------------------------------
    # INVOICE BATCH
    # --------------------------------------------------

    with open(
        OUTPUT_FOLDER
        / "invoice_batch.csv",
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
                "file"
            ]
        )


        writer.writeheader()


        writer.writerows(
            generated
        )


    # --------------------------------------------------
    # EXCEPTIONS
    # --------------------------------------------------

    with open(
        OUTPUT_FOLDER
        / "invoice_exceptions.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "name",
                "reason",
                "expected_hours",
                "calculated_hours",
                "difference"
            ]
        )


        writer.writeheader()


        writer.writerows(
            exceptions
        )


# --------------------------------------------------
# RUN INVOICE BATCH
# --------------------------------------------------

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


    # --------------------------------------------------
    # ACCOUNTS FILE
    # --------------------------------------------------

    if accounts_file is None:

        accounts_file = get_accounts_file(
            month,
            year
        )


    if not Path(
        accounts_file
    ).exists():

        raise FileNotFoundError(
            "Accounts file not found: "
            + str(
                accounts_file
            )
        )


    # --------------------------------------------------
    # SETTINGS
    # --------------------------------------------------

    update_progress(
        progress_callback,
        10,
        "Reading company settings..."
    )


    company_settings = (
        read_company_settings(
            accounts_file
        )
    )


    month_settings = (
        get_month_settings(
            month,
            year,
            company_settings
        )
    )


    start_date = month_settings[
        "start_date"
    ]


    end_date = month_settings[
        "end_date"
    ]


    invoice_date = month_settings[
        "invoice_date"
    ]


    invoice_period = month_settings[
        "invoice_period"
    ]


    invoice_prefix = month_settings[
        "invoice_prefix"
    ]


    # --------------------------------------------------
    # USERS
    # --------------------------------------------------

    update_progress(
        progress_callback,
        15,
        "Reading service users..."
    )


    users = read_template(
        accounts_file
    )


    generated = []
    exceptions = []
    validation_report = []


    # --------------------------------------------------
    # ONE NOURISH SESSION FOR ENTIRE RUN
    # --------------------------------------------------

    update_progress(
        progress_callback,
        20,
        "Connecting to Nourish..."
    )


    p = None
    browser = None
    context = None
    page = None


    try:

        try:

            (
                p,
                browser,
                context,
                page
            ) = start_nourish()


            nourish_users = (
                get_nourish_users(
                    page
                )
            )


        except Exception as error:

            raise RuntimeError(
                "Nourish connection failed: "
                + str(
                    error
                )
            )


        update_progress(
            progress_callback,
            30,
            "Connected to Nourish."
        )


        # --------------------------------------------------
        # PROCESS USERS
        # --------------------------------------------------

        total_users = len(
            users
        )


        for index, user in enumerate(
            users,
            start=1
        ):

            name = user[
                "name"
            ]


            if total_users > 0:

                user_percent = (
                    30
                    + int(
                        (
                            index
                            / total_users
                        )
                        * 50
                    )
                )

            else:

                user_percent = 80


            update_progress(
                progress_callback,
                user_percent,
                (
                    f"Processing {name} "
                    f"({index}/{total_users})..."
                )
            )


            # --------------------------------------------------
            # BILLING
            # --------------------------------------------------

            billing_result = (
                build_template_invoice_lines(
                    user
                )
            )


            # --------------------------------------------------
            # NOURISH
            # --------------------------------------------------

            validation = (
                validate_with_nourish(
                    page,
                    nourish_users,
                    user,
                    start_date,
                    end_date
                )
            )


            update_nourish_details(
                accounts_file,

                user[
                    "excel_row"
                ],

                nourish_id=(
                    validation[
                        "nourish_id"
                    ]
                ),

                validation_status=(
                    validation[
                        "status"
                    ]
                ),

                validation_notes=(
                    validation[
                        "notes"
                    ]
                )
            )


            # --------------------------------------------------
            # VALIDATION REPORT
            # --------------------------------------------------

            validation_report.append({
                "name": name,

                "reference": user.get(
                    "reference"
                ),

                "nourish_name": validation[
                    "nourish_name"
                ],

                "nourish_id": validation[
                    "nourish_id"
                ],

                "match_status": validation[
                    "match_status"
                ],

                "validation_status": validation[
                    "status"
                ],

                "accounts_hours": validation[
                    "accounts_hours"
                ],

                "nourish_hours": validation[
                    "nourish_hours"
                ],

                "cancelled_hours": validation[
                    "cancelled_hours"
                ],

                "difference": validation[
                    "difference"
                ],

                "notes": validation[
                    "notes"
                ]
            })


            # --------------------------------------------------
            # BILLING MUST MATCH
            # --------------------------------------------------

            if (
                billing_result[
                    "status"
                ]
                != "MATCHED"
            ):

                exceptions.append({
                    "name": name,

                    "reason": billing_result[
                        "status"
                    ],

                    "expected_hours": billing_result[
                        "expected_hours"
                    ],

                    "calculated_hours": billing_result[
                        "calculated_hours"
                    ],

                    "difference": billing_result[
                        "difference"
                    ]
                })


                continue


            # --------------------------------------------------
            # INVOICE NUMBER
            # --------------------------------------------------

            reference = user.get(
                "reference"
            )


            invoice_number = (
                make_invoice_number(
                    reference,
                    invoice_prefix
                )
            )


            if invoice_number is None:

                exceptions.append({
                    "name": name,
                    "reason": "MISSING REFERENCE",

                    "expected_hours": billing_result[
                        "expected_hours"
                    ],

                    "calculated_hours": billing_result[
                        "calculated_hours"
                    ],

                    "difference": billing_result[
                        "difference"
                    ]
                })


                continue


            # --------------------------------------------------
            # TOTAL
            # --------------------------------------------------

            total = calculate_invoice_total(
                user.get(
                    "monthly_hours"
                ),

                user.get(
                    "rate"
                )
            )


            if total is None:

                exceptions.append({
                    "name": name,
                    "reason": "INVALID TOTAL",

                    "expected_hours": billing_result[
                        "expected_hours"
                    ],

                    "calculated_hours": billing_result[
                        "calculated_hours"
                    ],

                    "difference": billing_result[
                        "difference"
                    ]
                })


                continue


            # --------------------------------------------------
            # CREATE INVOICE
            # --------------------------------------------------

            try:

                invoice_file = (
                    create_invoice(
                        user=user,

                        invoice_lines=(
                            billing_result[
                                "lines"
                            ]
                        ),

                        total=total,

                        invoice_number=(
                            invoice_number
                        ),

                        invoice_date=(
                            invoice_date
                        ),

                        period=(
                            invoice_period
                        ),

                        company_settings=(
                            company_settings
                        )
                    )
                )


            except Exception as error:

                exceptions.append({
                    "name": name,

                    "reason": str(
                        error
                    ),

                    "expected_hours": billing_result[
                        "expected_hours"
                    ],

                    "calculated_hours": billing_result[
                        "calculated_hours"
                    ],

                    "difference": billing_result[
                        "difference"
                    ]
                })


                continue


            # --------------------------------------------------
            # SUCCESS
            # --------------------------------------------------

            generated.append({
                "name": name,

                "invoice_number": (
                    invoice_number
                ),

                "reference": reference,

                "funding_type": user.get(
                    "funding_type"
                ),

                "hours": user.get(
                    "monthly_hours"
                ),

                "rate": user.get(
                    "rate"
                ),

                "total": total,

                "nourish_validation": validation[
                    "status"
                ],

                "file": str(
                    invoice_file
                )
            })


    finally:

        # --------------------------------------------------
        # CLOSE THE SINGLE SESSION
        # --------------------------------------------------

        update_progress(
            progress_callback,
            82,
            "Closing Nourish..."
        )


        if (
            p is not None
            and browser is not None
        ):

            try:

                close_nourish(
                    p,
                    browser
                )

            except:

                pass


    # --------------------------------------------------
    # REPORTS
    # --------------------------------------------------

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
    # COUNTS
    # --------------------------------------------------

    validated = 0
    review = 0
    not_validated = 0


    for result in validation_report:

        status = result[
            "validation_status"
        ]


        if status == "VALIDATED":

            validated += 1


        elif status == "REVIEW":

            review += 1


        else:

            not_validated += 1


    result = {
        "month": month,
        "year": year,

        "accounts_file": str(
            accounts_file
        ),

        "invoice_date": invoice_date,

        "invoice_period": (
            invoice_period
        ),

        "invoice_prefix": (
            invoice_prefix
        ),

        "users": len(
            users
        ),

        "generated": generated,

        "exceptions": exceptions,

        "validation_report": (
            validation_report
        ),

        "generated_count": len(
            generated
        ),

        "exception_count": len(
            exceptions
        ),

        "validated_count": validated,

        "review_count": review,

        "not_validated_count": (
            not_validated
        )
    }


    update_progress(
        progress_callback,
        100,
        "Complete"
    )


    return result