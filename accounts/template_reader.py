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
        return str(int(float(value)))

    except:
        return str(value).strip()
    

def read_template(file_path):
    df = pd.read_excel(
        file_path,
        sheet_name="Monthly Accounts"
    )

    users = []

    for index, row in df.iterrows():

        excel_row = index + 2

        name = clean_value(
            row.get("Service User Name")
        )

        if not name:
            continue

        user = {
            "excel_row": excel_row,

            "name": name,

            "nourish_id": clean_nourish_id(
                row.get("Nourish Client ID")
            ),

            "funding_type": clean_value(
                row.get("Funding Type")
            ),

            "reference": clean_value(
                row.get("Client PIN / Reference")
            ),

            "po_number": clean_value(
                row.get("PO Number")
            ),

            "rate": clean_value(
                row.get("Rate")
            ),

            "monthly_hours": clean_value(
                row.get("Monthly Billable Hours")
            ),

            "am_minutes": clean_value(
                row.get("AM Minutes")
            ),

            "am_carers": clean_value(
                row.get("AM Carers")
            ),

            "am_visits": clean_value(
                row.get("AM Visits")
            ),

            "lunch_minutes": clean_value(
                row.get("Lunch Minutes")
            ),

            "lunch_carers": clean_value(
                row.get("Lunch Carers")
            ),

            "lunch_visits": clean_value(
                row.get("Lunch Visits")
            ),

            "tea_minutes": clean_value(
                row.get("Tea Minutes")
            ),

            "tea_carers": clean_value(
                row.get("Tea Carers")
            ),

            "tea_visits": clean_value(
                row.get("Tea Visits")
            ),

            "evening_minutes": clean_value(
                row.get("Evening Minutes")
            ),

            "evening_carers": clean_value(
                row.get("Evening Carers")
            ),

            "evening_visits": clean_value(
                row.get("Evening Visits")
            ),

            "waking_night_hours": clean_value(
                row.get("Waking Night Hours")
            ),

            "waking_night_carers": clean_value(
                row.get("Waking Night Carers")
            ),

            "waking_night_visits": clean_value(
                row.get("Waking Night Visits")
            ),

            "billing_address_1": clean_value(
                row.get("Private Address Line 1")
            ),

            "billing_address_2": clean_value(
                row.get("Private Address Line 2")
            ),

            "billing_city": clean_value(
                row.get("Private Town / City")
            ),

            "billing_postcode": clean_value(
                row.get("Private Postcode")
            ),

            "billing_notes": clean_value(
                row.get("POC / Billing Notes")
            ),

            "validation_status": clean_value(
                row.get("Validation Status")
            ),

            "validation_notes": clean_value(
                row.get("Validation Notes")
            )
        }

        users.append(user)

    return users