from playwright.sync_api import sync_playwright


def verify_browser():
    print("Verifying Playwright installation...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://example.com")
            title = page.title()
            print(f"Successfully loaded page: {title}")
            browser.close()
            assert "Example Domain" in title
            print("Playwright verification PASSED.")
    except Exception as e:
        print(f"Playwright verification FAILED: {e}")
        exit(1)


if __name__ == "__main__":
    verify_browser()
