from pathlib import Path
import threading
import uuid

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory
)

from config import (
    OUTPUT_FOLDER,
    UPLOAD_FOLDER,
    NOURISH_SESSION_FILE,
    LOCAL_RECONNECT_ENABLED
)

from invoice_runner import (
    run_invoice_batch
)

from nourish.scraper import (
    reconnect_nourish_session
)


app = Flask(__name__)


# --------------------------------------------------
# JOB STORAGE
# --------------------------------------------------

jobs = {}


# --------------------------------------------------
# NOURISH STATE
# --------------------------------------------------

nourish_state = {
    "connected": (
        NOURISH_SESSION_FILE.exists()
    ),

    "message": (
        "Saved Nourish session available."
        if NOURISH_SESSION_FILE.exists()
        else "No saved Nourish session."
    )
}


nourish_reconnect = {
    "status": "idle",
    "message": ""
}


# --------------------------------------------------
# BACKGROUND INVOICE WORKER
# --------------------------------------------------

def run_job(
    job_id,
    month,
    year,
    accounts_file
):

    def progress_callback(
        percent,
        message
    ):

        jobs[
            job_id
        ][
            "progress"
        ] = percent

        jobs[
            job_id
        ][
            "message"
        ] = message


    try:

        jobs[
            job_id
        ][
            "status"
        ] = "running"


        result = run_invoice_batch(
            month,
            year,
            accounts_file=accounts_file,
            progress_callback=progress_callback
        )


        jobs[
            job_id
        ][
            "result"
        ] = result


        jobs[
            job_id
        ][
            "status"
        ] = "complete"


        jobs[
            job_id
        ][
            "progress"
        ] = 100


        jobs[
            job_id
        ][
            "message"
        ] = "Complete"


        nourish_state[
            "connected"
        ] = True


        nourish_state[
            "message"
        ] = (
            "Connected to Nourish."
        )


    except Exception as error:

        error_text = str(
            error
        )


        jobs[
            job_id
        ][
            "status"
        ] = "error"


        jobs[
            job_id
        ][
            "error"
        ] = error_text


        jobs[
            job_id
        ][
            "message"
        ] = "Run failed"


        if (
            "nourish"
            in error_text.lower()
            or "session"
            in error_text.lower()
        ):

            nourish_state[
                "connected"
            ] = False


            nourish_state[
                "message"
            ] = error_text


# --------------------------------------------------
# NOURISH RECONNECT WORKER
# --------------------------------------------------

def reconnect_worker():

    nourish_reconnect[
        "status"
    ] = "running"


    nourish_reconnect[
        "message"
    ] = (
        "Opening Nourish login..."
    )


    def status_callback(
        message
    ):

        nourish_reconnect[
            "message"
        ] = message


    result = reconnect_nourish_session(
        status_callback=status_callback
    )


    if result[
        "success"
    ]:

        nourish_reconnect[
            "status"
        ] = "connected"


        nourish_state[
            "connected"
        ] = True


        nourish_state[
            "message"
        ] = (
            "Connected to Nourish."
        )


    else:

        nourish_reconnect[
            "status"
        ] = "error"


        nourish_state[
            "connected"
        ] = False


        nourish_state[
            "message"
        ] = result[
            "message"
        ]


    nourish_reconnect[
        "message"
    ] = result[
        "message"
    ]


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route(
    "/"
)
def index():

    return render_template(
        "index.html"
    )


# --------------------------------------------------
# NOURISH STATUS
# --------------------------------------------------

@app.route(
    "/nourish-status"
)
def nourish_status():

    if (
        nourish_reconnect[
            "status"
        ]
        == "running"
    ):

        return jsonify({
            "connected": False,
            "reconnecting": True,
            "reconnect_enabled": LOCAL_RECONNECT_ENABLED,

            "message": nourish_reconnect[
                "message"
            ]
        })


    if not NOURISH_SESSION_FILE.exists():

        nourish_state[
            "connected"
        ] = False


        nourish_state[
            "message"
        ] = (
            "No saved Nourish session."
        )


    return jsonify({
        "connected": nourish_state[
            "connected"
        ],

        "reconnecting": False,

        "reconnect_enabled": (
            LOCAL_RECONNECT_ENABLED
        ),

        "message": nourish_state[
            "message"
        ]
    })


# --------------------------------------------------
# RECONNECT NOURISH
# --------------------------------------------------

@app.route(
    "/reconnect-nourish",
    methods=[
        "POST"
    ]
)
def reconnect_nourish():

    if not LOCAL_RECONNECT_ENABLED:

        return jsonify({
            "error": (
                "Nourish reconnect is disabled "
                "on this deployment."
            )
        }), 403


    if (
        nourish_reconnect[
            "status"
        ]
        == "running"
    ):

        return jsonify({
            "status": "running",

            "message": nourish_reconnect[
                "message"
            ]
        })


    thread = threading.Thread(
        target=reconnect_worker
    )


    thread.daemon = True

    thread.start()


    return jsonify({
        "status": "started",

        "message": (
            "Opening Nourish login..."
        )
    })


# --------------------------------------------------
# RECONNECT STATUS
# --------------------------------------------------

@app.route(
    "/reconnect-status"
)
def reconnect_status():

    return jsonify(
        nourish_reconnect
    )


# --------------------------------------------------
# RUN INVOICES
# --------------------------------------------------

@app.route(
    "/run",
    methods=[
        "POST"
    ]
)
def start_job():

    try:

        if not NOURISH_SESSION_FILE.exists():

            return jsonify({
                "error": (
                    "No Nourish session is available. "
                    "Please reconnect or update the "
                    "stored Nourish session."
                ),

                "login_required": True
            }), 400


        month = int(
            request.form[
                "month"
            ]
        )


        year = int(
            request.form[
                "year"
            ]
        )


        uploaded_file = request.files.get(
            "accounts_file"
        )


        if (
            uploaded_file is None
            or uploaded_file.filename == ""
        ):

            return jsonify({
                "error": (
                    "Please upload the monthly "
                    "accounts workbook."
                )
            }), 400


        if not uploaded_file.filename.lower().endswith(
            ".xlsx"
        ):

            return jsonify({
                "error": (
                    "The accounts file must "
                    "be an .xlsx workbook."
                )
            }), 400


        job_id = str(
            uuid.uuid4()
        )


        safe_filename = Path(
            uploaded_file.filename
        ).name


        upload_path = (
            UPLOAD_FOLDER
            / (
                job_id
                + "_"
                + safe_filename
            )
        )


        uploaded_file.save(
            upload_path
        )


        jobs[
            job_id
        ] = {
            "status": "queued",
            "progress": 0,
            "message": "Waiting to start...",
            "result": None,
            "error": None
        }


        thread = threading.Thread(
            target=run_job,
            args=(
                job_id,
                month,
                year,
                str(
                    upload_path
                )
            )
        )


        thread.daemon = True

        thread.start()


        return jsonify({
            "job_id": job_id
        })


    except Exception as error:

        return jsonify({
            "error": str(
                error
            )
        }), 500


# --------------------------------------------------
# JOB STATUS
# --------------------------------------------------

@app.route(
    "/status/<job_id>"
)
def job_status(
    job_id
):

    job = jobs.get(
        job_id
    )


    if job is None:

        return jsonify({
            "error": (
                "Job not found"
            )
        }), 404


    return jsonify(
        job
    )


# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------

@app.route(
    "/download/<path:filename>"
)
def download_file(
    filename
):

    return send_from_directory(
        OUTPUT_FOLDER,
        filename,
        as_attachment=True
    )


# --------------------------------------------------
# START APP
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False
    )