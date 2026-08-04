import logging
from camoufox.sync_api import Camoufox

logging.basicConfig(level=logging.INFO)

url = "https://www2.hm.com/en_in/productpage.1344928012.html"
for h in [True, False]:
    print(f"Testing Camoufox with headless={h}")
    try:
        with Camoufox(headless=h) as browser:
            page = browser.new_page()
            page.goto(url)
            print(f"Success! Title: {page.title()}")
    except Exception as e:
        print(f"Failed headless={h}: {e}")
