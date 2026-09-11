from invoice_runner import run_invoice_batch


MONTH = 8
YEAR = 2026


print()

print(
    "============================"
)

print(
    "INVOICE AUTOMATOR"
)

print(
    "============================"
)


try:

    result = run_invoice_batch(
        MONTH,
        YEAR
    )


except Exception as error:

    print()

    print(
        "ERROR:"
    )

    print(
        error
    )

    raise SystemExit


print()

print(
    "Accounts file:",
    result[
        "accounts_file"
    ]
)


print(
    "Invoice date:",
    result[
        "invoice_date"
    ]
)


print(
    "Invoice period:",
    result[
        "invoice_period"
    ]
)


print(
    "Invoice prefix:",
    result[
        "invoice_prefix"
    ]
)


print(
    "Users found:",
    result[
        "users"
    ]
)


print()

print(
    "============================"
)

print(
    "COMPLETE"
)

print(
    "============================"
)


print(
    "Invoices generated:",
    result[
        "generated_count"
    ]
)


print(
    "Invoice exceptions:",
    result[
        "exception_count"
    ]
)


print()

print(
    "Nourish validated:",
    result[
        "validated_count"
    ]
)


print(
    "Nourish review:",
    result[
        "review_count"
    ]
)


print(
    "Not validated:",
    result[
        "not_validated_count"
    ]
)


print()

print(
    "Reports saved in output/"
)