from playwright.sync_api import sync_playwright


BASE_URL = "https://passionrecruit.nourishcare.com"


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=False
    )

    context = browser.new_context()

    page = context.new_page()

    page.goto(BASE_URL)

    print()
    print("Log in to Nourish manually.")
    print("Once you are fully logged in, come back here.")
    print()

    input("Press Enter after login is complete...")

    context.storage_state(
        path="nourish_session.json"
    )

    print()
    print(
        "New nourish_session.json saved."
    )

    browser.close()