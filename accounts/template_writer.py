from openpyxl import load_workbook


def update_nourish_details(
    file_path,
    excel_row,
    nourish_id=None,
    validation_status=None,
    validation_notes=None
):
    workbook = load_workbook(
        file_path
    )

    sheet = workbook[
        "Monthly Accounts"
    ]

    # Nourish Client ID
    if nourish_id:
        sheet.cell(
            row=excel_row,
            column=2
        ).value = str(nourish_id)

    # Validation Status
    if validation_status:
        sheet.cell(
            row=excel_row,
            column=29
        ).value = validation_status

    # Validation Notes
    if validation_notes:
        sheet.cell(
            row=excel_row,
            column=30
        ).value = validation_notes

    workbook.save(
        file_path
    )