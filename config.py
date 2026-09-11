import os
from pathlib import Path


DATA_ROOT = Path(
    os.getenv(
        "INVOICE_DATA_ROOT",
        "."
    )
)


OUTPUT_FOLDER = Path(
    os.getenv(
        "OUTPUT_FOLDER",
        DATA_ROOT / "output"
    )
)


UPLOAD_FOLDER = Path(
    os.getenv(
        "UPLOAD_FOLDER",
        DATA_ROOT / "uploads"
    )
)


NOURISH_SESSION_FILE = Path(
    os.getenv(
        "NOURISH_SESSION_FILE",
        DATA_ROOT / "nourish_session.json"
    )
)


LOCAL_RECONNECT_ENABLED = (
    os.getenv(
        "LOCAL_RECONNECT_ENABLED",
        "true"
    ).lower()
    == "true"
)


OUTPUT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

UPLOAD_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)