from pathlib import Path
import threading
import uuid

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
    send_file,
)

from config import (
    NOURISH_SESSION_FILE,
    OUTPUT_FOLDER,
    UPLOAD_FOLDER,
)
from invoice_runner import run_invoice_batch
from nourish.scraper import (
    complete_steel_nourish_login,
    release_steel_nourish_login,
    start_steel_nourish_login,
)


app = Flask(__name__)


PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATE_FILE = PROJECT_ROOT / "data" / "templates" / "Invoice_Accounts_Template.xlsx"


jobs = {}


nourish_state = {
    "connected": NOURISH_SESSION_FILE.exists(),
    "message": (
        "Saved Nourish session available."
        if NOURISH_SESSION_FILE.exists()
        else "Nourish login required."
    ),
}


nourish_login = {
    "status": "idle",
    "session_id": None,
    "websocket_url": None,
    "debug_url": None,
    "message": "",
}


# --------------------------------------------------
# INVOICE JOB
# --------------------------------------------------

def run_job(job_id, month, year, accounts_file):
    def progress_callback(percent, message):
        jobs[job_id]["progress"] = percent
        jobs[job_id]["message"] = message

    try:
        jobs[job_id]["status"] = "running"

        result = run_invoice_batch(
            month,
            year,
            accounts_file=accounts_file,
            progress_callback=progress_callback,
        )

        jobs[job_id]["result"] = result
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Complete"

        nourish_state["connected"] = True
        nourish_state["message"] = "Connected to Nourish."

    except Exception as error:
        error_text = str(error)

        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = error_text
        jobs[job_id]["message"] = "Run failed"

        error_lower = error_text.lower()

        if (
            "session has expired" in error_lower
            or "session limit" in error_lower
            or "login required" in error_lower
            or "reconnect nourish" in error_lower
        ):
            nourish_state["connected"] = False
            nourish_state["message"] = error_text


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download-template")
def download_template():
    if not TEMPLATE_FILE.exists():
        return jsonify({
            "error": "Accounts template is not available."
        }), 404

    return send_file(
        TEMPLATE_FILE,
        as_attachment=True,
        download_name="Invoice_Accounts_Template.xlsx",
    )


# --------------------------------------------------
# NOURISH STATUS
# --------------------------------------------------

@app.route("/nourish-status")
def nourish_status():
    if not NOURISH_SESSION_FILE.exists():
        nourish_state["connected"] = False
        nourish_state["message"] = "Nourish login required."

    return jsonify({
        "connected": nourish_state["connected"],
        "message": nourish_state["message"],
        "login_status": nourish_login["status"],
    })


# --------------------------------------------------
# START STEEL LOGIN
# --------------------------------------------------

@app.route(
    "/reconnect-nourish",
    methods=["POST"]
)
def reconnect_nourish():
    if nourish_login["status"] == "active":
        return jsonify({
            "status": "active",
            "viewer_url": nourish_login["debug_url"],
            "message": "Nourish login is already open.",
        })

    try:
        result = start_steel_nourish_login()

        viewer_url = result["debug_url"]
        separator = "&" if "?" in viewer_url else "?"
        viewer_url = (
            viewer_url
            + separator
            + "interactive=true&showControls=true"
        )

        nourish_login["status"] = "active"
        nourish_login["session_id"] = result["session_id"]
        nourish_login["websocket_url"] = result["websocket_url"]
        nourish_login["debug_url"] = viewer_url
        nourish_login["message"] = (
            "Log into Nourish in the browser below."
        )

        return jsonify({
            "status": "active",
            "viewer_url": viewer_url,
            "message": nourish_login["message"],
        })

    except Exception as error:
        nourish_login["status"] = "error"
        nourish_login["message"] = str(error)

        return jsonify({
            "error": str(error)
        }), 500


# --------------------------------------------------
# COMPLETE STEEL LOGIN
# --------------------------------------------------

@app.route(
    "/complete-nourish-login",
    methods=["POST"]
)
def complete_nourish_login():
    session_id = nourish_login.get("session_id")
    websocket_url = nourish_login.get("websocket_url")

    if not session_id or not websocket_url:
        return jsonify({
            "error": "No active Nourish login session."
        }), 400

    result = complete_steel_nourish_login(
        session_id,
        websocket_url,
    )

    if not result["success"]:
        nourish_login["message"] = result["message"]

        return jsonify({
            "success": False,
            "message": result["message"],
        }), 400

    release_steel_nourish_login(session_id)

    nourish_login["status"] = "idle"
    nourish_login["session_id"] = None
    nourish_login["websocket_url"] = None
    nourish_login["debug_url"] = None
    nourish_login["message"] = ""

    nourish_state["connected"] = True
    nourish_state["message"] = "Connected to Nourish."

    return jsonify({
        "success": True,
        "message": "Nourish connected successfully.",
    })


# --------------------------------------------------
# CANCEL STEEL LOGIN
# --------------------------------------------------

@app.route(
    "/cancel-nourish-login",
    methods=["POST"]
)
def cancel_nourish_login():
    session_id = nourish_login.get("session_id")

    if session_id:
        release_steel_nourish_login(session_id)

    nourish_login["status"] = "idle"
    nourish_login["session_id"] = None
    nourish_login["websocket_url"] = None
    nourish_login["debug_url"] = None
    nourish_login["message"] = ""

    return jsonify({
        "success": True
    })


# --------------------------------------------------
# RUN INVOICES
# --------------------------------------------------

@app.route(
    "/run",
    methods=["POST"]
)
def start_job():
    try:
        if not NOURISH_SESSION_FILE.exists():
            return jsonify({
                "error": (
                    "No Nourish session is available. "
                    "Please connect to Nourish first."
                ),
                "login_required": True,
            }), 400

        month = int(request.form["month"])
        year = int(request.form["year"])

        uploaded_file = request.files.get(
            "accounts_file"
        )

        if (
            uploaded_file is None
            or uploaded_file.filename == ""
        ):
            return jsonify({
                "error": (
                    "Please upload the monthly accounts workbook."
                )
            }), 400

        if not uploaded_file.filename.lower().endswith(
            ".xlsx"
        ):
            return jsonify({
                "error": (
                    "The accounts file must be an .xlsx workbook."
                )
            }), 400

        job_id = str(uuid.uuid4())
        safe_filename = Path(
            uploaded_file.filename
        ).name

        upload_path = (
            UPLOAD_FOLDER
            / (job_id + "_" + safe_filename)
        )

        uploaded_file.save(upload_path)

        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Waiting to start...",
            "result": None,
            "error": None,
        }

        thread = threading.Thread(
            target=run_job,
            args=(
                job_id,
                month,
                year,
                str(upload_path),
            ),
        )

        thread.daemon = True
        thread.start()

        return jsonify({
            "job_id": job_id
        })

    except Exception as error:
        return jsonify({
            "error": str(error)
        }), 500


# --------------------------------------------------
# JOB STATUS
# --------------------------------------------------

@app.route("/status/<job_id>")
def job_status(job_id):
    job = jobs.get(job_id)

    if job is None:
        return jsonify({
            "error": "Job not found"
        }), 404

    return jsonify(job)


# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------

@app.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(
        OUTPUT_FOLDER,
        filename,
        as_attachment=True,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False,
    )
