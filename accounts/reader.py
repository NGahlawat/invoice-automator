import pandas as pd


ACCOUNTS_FILE = "data/Invoices - Accounts.xlsx"


MONTH_NAMES = {
    "january": ["january", "jan"],
    "february": ["february", "feb"],
    "march": ["march", "mar"],
    "april": ["april", "apr"],
    "may": ["may"],
    "june": ["june", "jun"],
    "july": ["july", "jul"],
    "august": ["august", "aug"],
    "september": ["september", "sept", "sep"],
    "october": ["october", "oct"],
    "november": ["november", "nov"],
    "december": ["december", "dec"]
}


def get_matching_sheets(month, year):
    excel_file = pd.ExcelFile(
        ACCOUNTS_FILE
    )

    month = month.lower()
    year = str(year)

    possible_names = MONTH_NAMES.get(
        month,
        [month]
    )

    matching_sheets = []

    for sheet in excel_file.sheet_names:

        sheet_lower = sheet.lower()

        month_found = False

        for month_name in possible_names:

            if month_name in sheet_lower:
                month_found = True
                break

        if month_found and year in sheet_lower:
            matching_sheets.append(
                sheet
            )

    return matching_sheets


def read_accounts_sheet(sheet_name):
    df = pd.read_excel(
        ACCOUNTS_FILE,
        sheet_name=sheet_name,
        header=None
    )

    header_row = None

    for i in range(len(df)):

        row_values = (
            df.iloc[i]
            .astype(str)
            .str.strip()
        )

        if "SU Name" in row_values.values:
            header_row = i
            break

    if header_row is None:
        return None

    df = pd.read_excel(
        ACCOUNTS_FILE,
        sheet_name=sheet_name,
        header=header_row
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    return df


def clean_value(value):
    if pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.strip()

        if value.startswith("£"):
            value = value.replace("£", "").strip()

            try:
                return float(value)
            except:
                return value

        return value

    return value


def make_user(row, sheet_name):
    return {
        "sheet": sheet_name,

        "name": clean_value(
            row.get("SU Name")
        ),

        "chc_number": clean_value(
            row.get("CHC Number")
        ),

        "po_number": clean_value(
            row.get("PO Number")
        ),

        "reference": clean_value(
            row.get("p")
        ),

        "rate": clean_value(
            row.get("Rate")
        ),

        "postcode": clean_value(
            row.get("Post code")
        ),

        "hours": clean_value(
            row.get("Hours")
        ),

        "times": clean_value(
            row.get("Times")
        ),

        "poc_details": clean_value(
            row.get("POC Details")
        ),

        "monthly_hours": clean_value(
            row.iloc[14]
        )
    }


def get_service_user(
    month,
    year,
    name
):
    matching_sheets = get_matching_sheets(
        month,
        year
    )

    for sheet_name in matching_sheets:

        df = read_accounts_sheet(
            sheet_name
        )

        if df is None:
            continue

        if "SU Name" not in df.columns:
            continue

        for _, row in df.iterrows():

            row_name = clean_value(
                row.get("SU Name")
            )

            if row_name is None:
                continue

            if row_name.lower() == name.lower():
                return make_user(
                    row,
                    sheet_name
                )

    return None


def get_all_service_users(
    month,
    year
):
    matching_sheets = get_matching_sheets(
        month,
        year
    )

    service_users = []
    seen_names = set()

    for sheet_name in matching_sheets:

        df = read_accounts_sheet(
            sheet_name
        )

        if df is None:
            continue

        if "SU Name" not in df.columns:
            continue

        for _, row in df.iterrows():

            name = clean_value(
                row.get("SU Name")
            )

            if name is None:
                continue

            if len(name) < 3:
                continue

            name_key = name.lower()

            if name_key in seen_names:
                continue

            seen_names.add(
                name_key
            )

            service_users.append(
                make_user(
                    row,
                    sheet_name
                )
            )

    return service_users