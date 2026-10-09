"""Run: python -m scripts.inspect_erp
Opens a visible Edge window. Log in yourself, open a page, press Enter here.
Prints only field names, menu links and table HEADERS (no passwords, cookies or row data)."""
from playwright.sync_api import sync_playwright

URL = "https://erp.mgmu.ac.in/login.htm"


def describe(page, title):
    print(f"\n===== {title} | {page.url} =====")
    print("FRAMES:", [f.url for f in page.frames])
    for f in page.frames:
        print(f"-- frame: {f.url}")
        for el in f.locator("input, button, select").all()[:40]:
            a = {k: el.get_attribute(k) for k in ("type", "name", "id", "placeholder")}
            if a["type"] != "hidden":
                print("  FIELD:", {k: v for k, v in a.items() if v})
        for el in f.locator("img[src*=aptcha], img[id*=aptcha], [id*=aptcha], [name*=aptcha]").all()[:3]:
            print("  CAPTCHA-LIKE ELEMENT FOUND:", el.get_attribute("id") or el.get_attribute("src"))
        for a in f.locator("a").all()[:60]:
            t = (a.inner_text() or "").strip()[:40]
            if t:
                print("  LINK:", t, "->", a.get_attribute("href"))
        for i, tb in enumerate(f.locator("table").all()[:8]):
            heads = [h.strip() for h in tb.locator("th").all_inner_texts()][:12]
            print(f"  TABLE {i}: id={tb.get_attribute('id')} class={tb.get_attribute('class')} "
                  f"headers={heads} rows={tb.locator('tr').count()}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    page = browser.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    describe(page, "LOGIN PAGE")
    input("\nLog in manually in the browser window, open the ATTENDANCE page, then press Enter here...")
    describe(page, "AFTER LOGIN / ATTENDANCE")
    while True:
        x = input("\nOpen another page (Marks, Courses, Exams, Profile), press Enter. Type q to quit: ")
        if x.strip().lower() == "q":
            break
        describe(page, "NEXT PAGE")
    browser.close()