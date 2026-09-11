import re
import time

from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from playwright.sync_api import sync_playwright

from nourish.api import extract_appointments
from config import NOURISH_SESSION_FILE

BASE_URL = (
    "https://passionrecruit.nourishcare.com"
)

SESSION_FILE = (
    NOURISH_SESSION_FILE
)


# --------------------------------------------------
# PAGE / SESSION HELPERS
# --------------------------------------------------

def session_limit_exceeded(
    page
):

    try:

        title = page.title()

        if (
            "session limit exceeded"
            in title.lower()
        ):

            return True

    except:

        pass


    try:

        body_text = page.locator(
            "body"
        ).inner_text()

        if (
            "session limit exceeded"
            in body_text.lower()
        ):

            return True

    except:

        pass


    return False


def is_login_page(
    page
):

    try:

        return (
            "/user/login"
            in page.url
        )

    except:

        return False


def is_real_dashboard(
    page
):

    if session_limit_exceeded(
        page
    ):

        return False


    if is_login_page(
        page
    ):

        return False


    try:

        user_search = page.locator(
            "#edit-user-search"
        )

        return (
            user_search.count()
            > 0
        )

    except:

        return False


# --------------------------------------------------
# NAME HELPERS
# --------------------------------------------------

def normalise_name(
    name
):

    name = name.lower().strip()

    titles = [
        "mr",
        "mrs",
        "miss",
        "ms",
        "dr"
    ]

    words = [
        word
        for word in name.split()
        if word not in titles
    ]

    name = " ".join(
        words
    )

    name = re.sub(
        r"[^a-z0-9\s]",
        "",
        name
    )

    return " ".join(
        name.split()
    )


def get_first_last(
    name
):

    parts = normalise_name(
        name
    ).split()

    if len(parts) < 2:

        return (
            None,
            None
        )

    return (
        parts[0],
        parts[-1]
    )


def name_similarity(
    name1,
    name2
):

    return SequenceMatcher(
        None,
        normalise_name(
            name1
        ),
        normalise_name(
            name2
        )
    ).ratio()


# --------------------------------------------------
# CHECK SAVED SESSION
# --------------------------------------------------

def check_nourish_session():

    if not Path(
        SESSION_FILE
    ).exists():

        return {
            "connected": False,
            "message": (
                "No saved Nourish session."
            )
        }


    p = None
    browser = None


    try:

        p = sync_playwright().start()


        browser = p.chromium.launch(
            headless=True
        )


        context = browser.new_context(
            storage_state=SESSION_FILE
        )


        page = context.new_page()


        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=30000
        )


        try:

            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )

        except:

            pass


        if session_limit_exceeded(
            page
        ):

            return {
                "connected": False,
                "message": (
                    "Nourish session limit exceeded. "
                    "Close another Nourish session "
                    "and reconnect."
                )
            }


        if is_login_page(
            page
        ):

            return {
                "connected": False,
                "message": (
                    "Nourish login required."
                )
            }


        if is_real_dashboard(
            page
        ):

            return {
                "connected": True,
                "message": (
                    "Connected to Nourish."
                )
            }


        return {
            "connected": False,
            "message": (
                "Nourish session could not "
                "be confirmed."
            )
        }


    except Exception as error:

        return {
            "connected": False,
            "message": (
                "Could not connect to Nourish: "
                + str(error)
            )
        }


    finally:

        if browser is not None:

            try:

                browser.close()

            except:

                pass


        if p is not None:

            try:

                p.stop()

            except:

                pass


# --------------------------------------------------
# RECONNECT SESSION
# --------------------------------------------------

def reconnect_nourish_session(
    status_callback=None
):

    p = None
    browser = None


    def update(
        message
    ):

        if status_callback:

            status_callback(
                message
            )


    try:

        update(
            "Opening Nourish login..."
        )


        p = sync_playwright().start()


        browser = p.chromium.launch(
            headless=False
        )


        context = browser.new_context()


        page = context.new_page()


        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=30000
        )


        update(
            "Please log into Nourish "
            "in the browser window."
        )


        timeout_seconds = 300

        started = time.time()


        while (
            time.time()
            - started
            < timeout_seconds
        ):

            try:

                # --------------------------------------
                # SESSION LIMIT
                # --------------------------------------

                if session_limit_exceeded(
                    page
                ):

                    update(
                        "Nourish session limit exceeded. "
                        "Please close another Nourish "
                        "session, then try logging in again."
                    )

                    time.sleep(
                        1
                    )

                    continue


                # --------------------------------------
                # REAL DASHBOARD
                # --------------------------------------

                if is_real_dashboard(
                    page
                ):

                    update(
                        "Login detected. "
                        "Saving Nourish session..."
                    )


                    context.storage_state(
                        path=SESSION_FILE
                    )


                    update(
                        "Nourish connected."
                    )


                    time.sleep(
                        1
                    )


                    return {
                        "success": True,
                        "message": (
                            "Nourish connected."
                        )
                    }


            except Exception:

                pass


            time.sleep(
                1
            )


        return {
            "success": False,
            "message": (
                "Login timed out. "
                "Please try again."
            )
        }


    except Exception as error:

        return {
            "success": False,
            "message": str(
                error
            )
        }


    finally:

        if browser is not None:

            try:

                browser.close()

            except:

                pass


        if p is not None:

            try:

                p.stop()

            except:

                pass


# --------------------------------------------------
# START NORMAL NOURISH SESSION
# --------------------------------------------------

def start_nourish():

    if not Path(
        SESSION_FILE
    ).exists():

        raise Exception(
            "No saved Nourish session. "
            "Please reconnect Nourish."
        )


    p = sync_playwright().start()


    browser = p.chromium.launch(
        headless=True
    )


    try:

        context = browser.new_context(
            storage_state=SESSION_FILE
        )


        page = context.new_page()


        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=30000
        )


        try:

            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )

        except:

            pass


        if session_limit_exceeded(
            page
        ):

            raise Exception(
                "Nourish session limit exceeded. "
                "Close another Nourish session "
                "and reconnect."
            )


        if is_login_page(
            page
        ):

            raise Exception(
                "Nourish session has expired. "
                "Please reconnect Nourish."
            )


        if not is_real_dashboard(
            page
        ):

            raise Exception(
                "Nourish session could not "
                "be confirmed."
            )


        return (
            p,
            browser,
            context,
            page
        )


    except:

        try:

            browser.close()

        except:

            pass


        try:

            p.stop()

        except:

            pass


        raise


# --------------------------------------------------
# CLOSE NOURISH
# --------------------------------------------------

def close_nourish(
    p,
    browser
):

    browser.close()

    p.stop()


# --------------------------------------------------
# GET USERS
# --------------------------------------------------

def get_nourish_users(
    page
):

    if session_limit_exceeded(
        page
    ):

        raise Exception(
            "Nourish session limit exceeded."
        )


    options = page.locator(
        "#edit-user-search option"
    )


    users = []


    for i in range(
        options.count()
    ):

        option = options.nth(
            i
        )


        name = option.inner_text().strip()


        value = option.get_attribute(
            "value"
        )


        if (
            name
            and value
        ):

            users.append({
                "name": name,
                "id": value
            })


    return users


# --------------------------------------------------
# MATCH CLIENT
# --------------------------------------------------

def find_client_match(
    nourish_users,
    name
):

    target = normalise_name(
        name
    )


    # Exact match

    for user in nourish_users:

        if (
            normalise_name(
                user["name"]
            )
            == target
        ):

            return {
                "status": "exact",
                "id": user["id"],
                "nourish_name": user["name"],
                "score": 1.0
            }


    # First + last name

    target_first, target_last = (
        get_first_last(
            name
        )
    )


    matches = []


    if (
        target_first
        and target_last
    ):

        for user in nourish_users:

            user_first, user_last = (
                get_first_last(
                    user["name"]
                )
            )


            if (
                user_first
                == target_first
                and user_last
                == target_last
            ):

                matches.append(
                    user
                )


    if len(
        matches
    ) == 1:

        user = matches[0]


        return {
            "status": "first_last",
            "id": user["id"],
            "nourish_name": user["name"],
            "score": 1.0
        }


    # Fuzzy match

    best_match = None
    best_score = 0


    for user in nourish_users:

        score = name_similarity(
            name,
            user["name"]
        )


        if score > best_score:

            best_score = score
            best_match = user


    if (
        best_match
        and best_score >= 0.90
    ):

        return {
            "status": "fuzzy",
            "id": best_match["id"],
            "nourish_name": best_match["name"],
            "score": best_score
        }


    if (
        best_match
        and best_score >= 0.65
    ):

        return {
            "status": "possible",
            "id": None,
            "nourish_name": best_match["name"],
            "score": best_score
        }


    return {
        "status": "unmatched",
        "id": None,
        "nourish_name": None,
        "score": None
    }


# --------------------------------------------------
# GET ROSTER
# --------------------------------------------------

def get_roster(
    page,
    client_id,
    week_date
):

    client_id = str(
        client_id
    )


    if client_id.endswith(
        ".0"
    ):

        client_id = (
            client_id[:-2]
        )


    # --------------------------------------------------
    # OPEN CLIENT ROSTER
    # --------------------------------------------------

    page.goto(
        f"{BASE_URL}/roster/{client_id}",
        wait_until="domcontentloaded",
        timeout=30000
    )


    # --------------------------------------------------
    # CHECK SESSION
    # --------------------------------------------------

    if session_limit_exceeded(
        page
    ):

        raise Exception(
            "Nourish session limit exceeded. "
            "Roster access is unavailable."
        )


    if is_login_page(
        page
    ):

        raise Exception(
            "Nourish session has expired."
        )


    # --------------------------------------------------
    # WAIT FOR DATE PICKER
    # --------------------------------------------------

    try:

        page.wait_for_selector(
            'input[name="datepicker"]',
            timeout=15000
        )


    except:

        # --------------------------------------------------
        # DEBUG OUTPUT
        # --------------------------------------------------

        debug_folder = Path(
            "output/debug"
        )


        debug_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        screenshot_file = (
            debug_folder
            / f"roster_{client_id}.png"
        )


        html_file = (
            debug_folder
            / f"roster_{client_id}.html"
        )


        try:

            page.screenshot(
                path=str(
                    screenshot_file
                ),
                full_page=True
            )

        except:

            pass


        try:

            html_file.write_text(
                page.content(),
                encoding="utf-8"
            )

        except:

            pass


        title = ""

        try:

            title = page.title()

        except:

            pass


        raise Exception(
            "Roster page loaded but the date selector "
            "could not be found. "
            f"Title: {title}. "
            f"URL: {page.url}. "
            "Debug files saved to output/debug/"
        )


    # --------------------------------------------------
    # CHANGE WEEK
    # --------------------------------------------------

    page.evaluate(
        """
        (weekDate) => {

            const input =
                document.querySelector(
                    'input[name="datepicker"]'
                );

            if (!input) {

                throw new Error(
                    'Roster datepicker not found'
                );

            }


            input.value = weekDate;


            input.dispatchEvent(
                new Event(
                    'change',
                    {
                        bubbles: true
                    }
                )
            );


            const form =
                input.closest(
                    'form'
                );


            if (!form) {

                throw new Error(
                    'Roster date form not found'
                );

            }


            const button =
                form.querySelector(
                    '[name="op"]'
                    + '[value="Apply Changes"]'
                );


            if (!button) {

                throw new Error(
                    'Apply Changes button not found'
                );

            }


            form.requestSubmit(
                button
            );

        }
        """,
        week_date
    )


    # --------------------------------------------------
    # WAIT FOR WEEK CHANGE
    # --------------------------------------------------

    try:

        page.wait_for_load_state(
            "networkidle",
            timeout=30000
        )

    except:

        pass


    # --------------------------------------------------
    # CHECK AGAIN AFTER NAVIGATION
    # --------------------------------------------------

    if session_limit_exceeded(
        page
    ):

        raise Exception(
            "Nourish session limit exceeded "
            "while loading roster."
        )


    if is_login_page(
        page
    ):

        raise Exception(
            "Nourish session expired "
            "while loading roster."
        )


    # --------------------------------------------------
    # GET DRUPAL DATA
    # --------------------------------------------------

    settings = page.evaluate(
        "() => Drupal.settings"
    )


    return extract_appointments(
        settings
    )


# --------------------------------------------------
# WEEK HELPERS
# --------------------------------------------------

def format_week_date(
    date_value
):

    return (
        f"Monday, "
        f"{date_value.day} "
        f"{date_value.strftime('%B %Y')}"
    )


def get_mondays_between(
    start_date,
    end_date
):

    start = datetime.strptime(
        start_date,
        "%Y-%m-%d"
    )


    end = datetime.strptime(
        end_date,
        "%Y-%m-%d"
    )


    monday = (
        start
        - timedelta(
            days=start.weekday()
        )
    )


    mondays = []


    while monday <= end:

        mondays.append(
            format_week_date(
                monday
            )
        )


        monday += timedelta(
            days=7
        )


    return mondays


# --------------------------------------------------
# GET APPOINTMENTS FOR MONTH
# --------------------------------------------------

def get_appointments_for_period(
    page,
    client_id,
    start_date,
    end_date
):

    all_appointments = []


    for week_date in (
        get_mondays_between(
            start_date,
            end_date
        )
    ):

        appointments = get_roster(
            page,
            client_id,
            week_date
        )


        for appointment in appointments:

            appointment_date = (
                appointment.get(
                    "date"
                )
            )


            if (
                appointment_date
                and start_date
                <= appointment_date
                <= end_date
            ):

                all_appointments.append(
                    appointment
                )


    return all_appointments