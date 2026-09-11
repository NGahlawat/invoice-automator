import pandas as pd


def clean_value(value):

    if pd.isna(value):
        return None

    if isinstance(value, str):

        value = value.strip()

        if value == "":
            return None

    return value


def read_company_settings(file_path):

    df = pd.read_excel(
        file_path,
        sheet_name="Company Settings",
        header=None
    )

    settings = {}


    for _, row in df.iterrows():

        setting = clean_value(
            row.iloc[0]
        )

        value = clean_value(
            row.iloc[1]
        )

        if not setting:
            continue

        settings[
            str(setting)
        ] = value


    return {

        # ---------------------------------------------
        # COMPANY
        # ---------------------------------------------

        "company_name": settings.get(
            "Company Name"
        ),

        "supplier_address_1": settings.get(
            "Supplier Address Line 1"
        ),

        "supplier_address_2": settings.get(
            "Supplier Address Line 2"
        ),

        "supplier_postcode": settings.get(
            "Supplier Postcode"
        ),


        # ---------------------------------------------
        # NHS BILLING
        # ---------------------------------------------

        "nhs_bill_to_1": settings.get(
            "NHS Bill To Line 1"
        ),

        "nhs_bill_to_2": settings.get(
            "NHS Bill To Line 2"
        ),

        "nhs_bill_to_3": settings.get(
            "NHS Bill To Line 3"
        ),

        "nhs_bill_to_4": settings.get(
            "NHS Bill To Line 4"
        ),

        "nhs_bill_to_5": settings.get(
            "NHS Bill To Line 5"
        ),

        "nhs_bill_to_postcode": settings.get(
            "NHS Bill To Postcode"
        ),


        # ---------------------------------------------
        # BANK
        # ---------------------------------------------

        "account_number": settings.get(
            "Account Number"
        ),

        "sort_code": settings.get(
            "Sort Code"
        ),


        # ---------------------------------------------
        # INVOICE RULES
        # ---------------------------------------------

        "invoice_prefix_format": settings.get(
            "Invoice Prefix Format"
        ),

        "invoice_date_rule": settings.get(
            "Invoice Date Rule"
        ),


        # ---------------------------------------------
        # FOOTER
        # ---------------------------------------------

        "payment_terms": settings.get(
            "Payment Terms"
        ),

        "invoice_contact_message": settings.get(
            "Invoice Contact Message"
        ),

        "payment_heading": settings.get(
            "Payment Heading"
        ),

        "payment_reference_message": settings.get(
            "Payment Reference Message"
        ),

        "appreciation_message": settings.get(
            "Appreciation Message"
        )
    }