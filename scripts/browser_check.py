#!/usr/bin/env python3
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8877"
OUT = Path(__file__).resolve().parents[1] / "generated" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/snap/bin/chromium")
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    console_errors = []
    page.on("console", lambda message: console_errors.append(f"console {message.type}: {message.text}") if message.type == "error" else None)
    page.on("pageerror", lambda error: console_errors.append(f"pageerror: {error}"))

    page.goto(BASE + "/", wait_until="networkidle")
    page.screenshot(path=str(OUT / "home-desktop-latest.png"), full_page=True)
    assert page.locator(".book-card").count() == 4
    assert page.locator(".work-group.ready .book-card").count() == 2
    assert page.locator(".work-group.in-progress .book-card").count() == 2
    assert page.locator(".work-group.unreleased").count() == 0
    assert page.locator(".review-chip.ready").count() == 2
    assert page.locator(".book-card .review-chip.in-progress").count() == 2
    assert page.locator(".work-group.in-progress .book-card.unreleased h3").inner_text() == "The Life and Epistles of St. Paul"
    assert "Not available yet" in page.locator(".book-card.unreleased").inner_text()
    assert page.locator(".planned-card").count() == 27
    assert page.locator(".review-chip.planned").count() == 27
    assert "All titles current" in page.locator("#site-status").inner_text()

    page.goto(BASE + "/read/?work=alford-greek-testament&document=volume-1-part-1", wait_until="networkidle")
    frame = page.frame_locator("#pdf-frame")
    frame.locator("#numPages").wait_for(state="visible", timeout=30000)
    page.wait_for_function("document.querySelector('#pdf-frame').contentDocument.querySelector('#numPages').textContent.trim() !== '0'", timeout=60000)
    pages = frame.locator("#numPages").inner_text().strip()
    assert "Ready for review" in page.locator("#review-banner").inner_text()
    page.screenshot(path=str(OUT / "reader-desktop-latest.png"), full_page=False)
    print(f"reader loaded {pages} pages")

    mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    mobile.goto(BASE + "/", wait_until="networkidle")
    mobile.screenshot(path=str(OUT / "home-mobile-latest.png"), full_page=True)
    assert mobile.locator(".book-card").count() == 4
    assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

    if console_errors:
        raise SystemExit(chr(10).join(console_errors))
    browser.close()
