import os
import re
import time

from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from steel import Steel

from nourish.api import extract_appointments
from config import NOURISH_SESSION_FILE

BASE_URL = (
    "https://passionrecruit.nourishcare.com"
)

load_dotenv()

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
# STEEL REMOTE LOGIN
# --------------------------------------------------

def get_steel_client():
    api_key = os.getenv("STEEL_API_KEY")

    if not api_key:
        raise Exception(
            "STEEL_API_KEY is missing. "
            "Add it to the environment before reconnecting Nourish."
        )

    return (
        Steel(steel_api_key=api_key),
        api_key
    )


def start_steel_nourish_login():

    client, api_key = get_steel_client()

    session = client.sessions.create(
        timeout=900000
    )

    p = None

    try:

        p = sync_playwright().start()

        browser = p.chromium.connect_over_cdp(
            f"{session.websocket_url}&apiKey={api_key}"
        )

        context = browser.contexts[0]

        # Steel normally starts with one tab already open.
        # Reuse that exact tab so the live viewer cannot
        # remain focused on about:blank / 0.0.0.0.
        if context.pages:

            page = context.pages[0]

        else:

            page = context.new_page()

        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=45000
        )

        page.bring_to_front()

        # Close any extra tabs Steel may have opened.
        for other_page in list(context.pages):

            if other_page != page:

                try:
                    other_page.close()
                except:
                    pass

        # Give the live viewer a moment to catch up.
        page.wait_for_timeout(
            1000
        )

        return {
            "session_id": session.id,
            "websocket_url": session.websocket_url,
            "debug_url": session.debug_url
        }

    except:

        try:
            client.sessions.release(
                session.id
            )
        except:
            pass

        raise

    finally:

        if p is not None:

            try:
                p.stop()
            except:
                pass


def complete_steel_nourish_login(
    session_id,
    websocket_url
):
    client, api_key = get_steel_client()
    p = None

    try:
        p = sync_playwright().start()

        browser = p.chromium.connect_over_cdp(
            f"{websocket_url}&apiKey={api_key}"
        )

        if not browser.contexts:
            return {
                "success": False,
                "message": "Steel browser context was not found."
            }

        context = browser.contexts[0]

        pages = context.pages

        if not pages:
            return {
                "success": False,
                "message": "Steel browser page was not found."
            }

        page = None

        for candidate in pages:
            if "nourishcare.com" in candidate.url:
                page = candidate
                break

        if page is None:
            page = pages[0]

        if session_limit_exceeded(page):
            return {
                "success": False,
                "message": (
                    "Nourish session limit exceeded. "
                    "Close another Nourish session and try again."
                )
            }

        if is_login_page(page):
            return {
                "success": False,
                "message": (
                    "Nourish is still on the login page. "
                    "Finish logging in, then try again."
                )
            }

        if not is_real_dashboard(page):
            return {
                "success": False,
                "message": (
                    "Nourish dashboard was not detected yet. "
                    "Finish logging in, then try again."
                )
            }

        Path(SESSION_FILE).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        context.storage_state(
            path=str(SESSION_FILE)
        )

        return {
            "success": True,
            "message": "Nourish connected."
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error)
        }

    finally:
        if p is not None:
            try:
                p.stop()
            except Exception:
                pass


def release_steel_nourish_login(session_id):
    if not session_id:
        return

    try:
        client, _ = get_steel_client()
        client.sessions.release(session_id)
    except Exception:
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


    # --------------------------------------------------
    # OPEN CLIENTS PAGE
    # --------------------------------------------------

    page.goto(
        f"{BASE_URL}/clients",
        wait_until="domcontentloaded",
        timeout=30000
    )

    try:
        page.wait_for_load_state(
            "networkidle",
            timeout=10000
        )
    except Exception:
        pass


    if session_limit_exceeded(
        page
    ):
        raise Exception(
            "Nourish session limit exceeded."
        )


    if is_login_page(
        page
    ):
        raise Exception(
            "Nourish session has expired."
        )


    page.wait_for_selector(
        "#edit-status-check",
        timeout=15000
    )

    page.wait_for_selector(
        "#client-list",
        timeout=15000
    )


    # --------------------------------------------------
    # CLIENT STATUSES
    # --------------------------------------------------

    client_statuses = {
        "Active": "19",
        "Care Suspended Client": "26",
        "Ex-Client": "6",
        "Inactive": "20",
        "No longer a client": "21",
        "Deceased": "22"
    }


    all_users = {}


    # --------------------------------------------------
    # READ CLIENTS CURRENTLY SHOWN
    # --------------------------------------------------

    def read_client_list(
        client_status
    ):

        clients = []

        links = page.locator(
            "#client-list a[href]"
        )


        for i in range(
            links.count()
        ):

            link = links.nth(i)


            try:
                name = (
                    link
                    .inner_text()
                    .strip()
                )

                href = (
                    link
                    .get_attribute(
                        "href"
                    )
                    or ""
                )

            except Exception:
                continue


            if not name:
                continue


            # Ignore obvious non-client links.
            if name.lower() in [
                "edit",
                "view",
                "delete",
                "roster",
                "schedule"
            ]:
                continue


            client_id = None


            # --------------------------------------------------
            # TRY TO GET ID FROM LINK
            # --------------------------------------------------

            patterns = [
                r"/roster/(\d+)",
                r"/clients?/(\d+)",
                r"/user/(\d+)"
            ]


            for pattern in patterns:

                match = re.search(
                    pattern,
                    href
                )

                if match:

                    client_id = (
                        match.group(1)
                    )

                    break


            # --------------------------------------------------
            # TRY DATA ATTRIBUTES IF LINK DID NOT CONTAIN ID
            # --------------------------------------------------

            if client_id is None:

                try:

                    client_id = (
                        link.get_attribute(
                            "data-client-id"
                        )
                        or link.get_attribute(
                            "data-user-id"
                        )
                        or link.get_attribute(
                            "data-uid"
                        )
                        or link.get_attribute(
                            "data-id"
                        )
                    )

                except Exception:
                    pass


            if (
                name
                and client_id
            ):

                clients.append({
                    "name": name,
                    "id": str(
                        client_id
                    ),
                    "client_status": (
                        client_status
                    )
                })


        return clients


    # --------------------------------------------------
    # CHECK EACH STATUS
    # --------------------------------------------------

    for (
        status_name,
        status_value
    ) in client_statuses.items():

        status_select = page.locator(
            "#edit-status-check"
        )


        # Remember the current client list so we can
        # detect when AJAX refreshes it.
        old_html = ""

        try:
            old_html = page.locator(
                "#client-list"
            ).inner_html()
        except Exception:
            pass


        status_select.select_option(
            value=status_value
        )


        # The Nourish status selector is AJAX processed.
        # select_option triggers the change event.
        try:

            page.wait_for_function(
                """
                oldHtml => {
                    const list =
                        document.querySelector(
                            '#client-list'
                        );

                    if (!list) {
                        return false;
                    }

                    return (
                        list.innerHTML !== oldHtml
                    );
                }
                """,
                old_html,
                timeout=10000
            )

        except Exception:

            # Some status changes may produce identical
            # HTML or update very quickly.
            page.wait_for_timeout(
                1500
            )


        if session_limit_exceeded(
            page
        ):
            raise Exception(
                "Nourish session limit exceeded."
            )


        users = read_client_list(
            status_name
        )


        print(
            f"Nourish {status_name}: "
            f"{len(users)} clients found"
        )


        for user in users:

            user_id = str(
                user["id"]
            )


            if (
                user_id
                not in all_users
            ):

                all_users[
                    user_id
                ] = user


    users = list(
        all_users.values()
    )


    print(
        "Total Nourish clients found:",
        len(users)
    )


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

    roster_url = (
        f"{BASE_URL}/roster/{client_id}"
    )

    last_error = None

    for attempt in range(3):

        try:

            page.goto(
                roster_url,
                wait_until="domcontentloaded",
                timeout=45000
            )

            last_error = None
            break

        except Exception as error:

            last_error = error

            if attempt < 2:

                page.wait_for_timeout(
                    2000
                )

    if last_error is not None:

        raise Exception(
            "Could not open Nourish roster after "
            "3 attempts: "
            + str(last_error)
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