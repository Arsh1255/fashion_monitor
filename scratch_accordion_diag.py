"""Diagnose H&M PDP accordion expand + body text order."""
import re
from camoufox.sync_api import Camoufox

url = "https://www2.hm.com/en_in/productpage.1344928012.html"

with Camoufox(headless=True) as browser:
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)

    for label in ("DESCRIPTION & FIT", "MATERIAL & CARE"):
        loc = page.locator(f"button:has-text('{label}')")
        print(f"{label}: button count={loc.count()}")
        if loc.count():
            try:
                loc.first.scroll_into_view_if_needed(timeout=2000)
                loc.first.click(timeout=2500)
                print(f"  clicked OK")
            except Exception as e:
                print(f"  click failed: {e}")
            page.wait_for_timeout(1200)

    text = page.locator("body").inner_text()
    upper = text.upper()
    for key in [
        "DESCRIPTION & FIT",
        "MATERIAL & CARE",
        "ART. NO",
        "SLEEVE LENGTH",
        "COMPOSITION",
        "NECKLINE",
        "DELIVERY AND PAYMENT",
        "NEW ARRIVAL",
    ]:
        print(f"{key!r} -> {upper.find(key)}")

    i = upper.find("DESCRIPTION & FIT")
    print("---SLICE AFTER DESCRIPTION & FIT---")
    print(repr(text[i : i + 900] if i >= 0 else text[:900]))

    btns = page.evaluate(
        """() => Array.from(document.querySelectorAll('button,[role=button]'))
            .map(b => (b.innerText || '').trim().replace(/\\s+/g, ' '))
            .filter(t => /DESCRIPTION|MATERIAL|CARE|DELIVERY/i.test(t))
            .slice(0, 40)"""
    )
    print("MATCHING BUTTON TEXTS:", btns)

    # Try aria-expanded state
    states = page.evaluate(
        """() => Array.from(document.querySelectorAll('button,[role=button]'))
            .filter(b => /DESCRIPTION\\s*&\\s*FIT|MATERIAL\\s*&\\s*CARE/i.test(b.innerText || ''))
            .map(b => ({
                text: (b.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 60),
                ariaExpanded: b.getAttribute('aria-expanded'),
                ariaControls: b.getAttribute('aria-controls'),
                tag: b.tagName,
                className: (b.className || '').toString().slice(0, 80)
            }))"""
    )
    print("ACCORDION STATE:", states)
