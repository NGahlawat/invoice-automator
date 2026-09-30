import pandas as pd


def clean_value(value):

    if pd.isna(value):
        return None

    if isinstance(value, str):

        value = value.strip()

        if value == "":
            return None

    return value


def clean_nourish_id(value):

    if pd.isna(value):
        return None

    try:

        return str(
            int(
                float(value)
            )
        )

    except:

        return str(
            value
        ).strip()


def read_template(file_path):

    df = pd.read_excel(
        file_path,
        sheet_name="Monthly Accounts"
    )

    users = []

    for index, row in df.iterrows():

        excel_row = index + 2

        name = clean_value(
            row.get(
                "Service User Name"
            )
        )

        if not name:
            continue

        user = {
            "excel_row": excel_row,

            "name": name,

            "funding_type": clean_value(
                row.get(
                    "Funding Type"
                )
            ),

            "reference": clean_value(
                row.get(
                    "Client PIN / Reference"
                )
            ),

            "po_number": clean_value(
                row.get(
                    "PO Number"
                )
            ),

            "rate": clean_value(
                row.get(
                    "Rate"
                )
            ),

            "hours_override": clean_value(
                row.get(
                    "Billing Hours Override (Optional)"
                )
            ),

            "billing_address_1": clean_value(
                row.get(
                    "Private Address Line 1"
                )
            ),

            "billing_address_2": clean_value(
                row.get(
                    "Private Address Line 2"
                )
            ),

            "billing_city": clean_value(
                row.get(
                    "Private Town / City"
                )
            ),

            "billing_postcode": clean_value(
                row.get(
                    "Private Postcode"
                )
            ),

            "billing_notes": clean_value(
                row.get(
                    "POC / Billing Notes"
                )
            ),

            "nourish_id": clean_nourish_id(
                row.get(
                    "Nourish Client ID"
                )
            )
        }

        users.append(
            user
        )

    return users