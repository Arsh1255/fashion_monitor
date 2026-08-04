"""
Diagnostic script: Open H&M Men page, wait for full render,
then dump: page title, all anchor hrefs, all img srcs, inner HTML snippet,
and full page HTML to a file so we can reverse-engineer the correct selectors.
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

DUMP_PATH = Path(r"D:\fashion_monitor\scratch\hm_page_dump.html")
LOG_PATH = Path(r"D:\fashion_monitor\scratch\hm_diag.txt")
URL = "https://www2.hm.com/en_in/men/new-arrivals/view-all.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    
    # Accept cookies if present
    try:
        btn = page.query_selector("#onetrust-accept-btn-handler")
        if btn:
            btn.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass
    
    # Scroll to trigger lazy loading
    for _ in range(5):
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(1200)
    
    page.wait_for_timeout(3000)

    title = page.title()
    
    # Sample all anchor hrefs
    all_hrefs = page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href]')).map(a => a.href).slice(0, 100)
    """)
    
    # Sample img srcs
    all_imgs = page.evaluate("""
        () => Array.from(document.querySelectorAll('img')).map(i => i.src || i.dataset.src || '').slice(0, 40)
    """)

    # All tags with counts
    tag_counts = page.evaluate("""
        () => {
            const counts = {};
            document.querySelectorAll('*').forEach(el => {
                const tag = el.tagName.toLowerCase();
                counts[tag] = (counts[tag] || 0) + 1;
            });
            return Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, 40);
        }
    """)
    
    # Check specifically for product-related classes
    product_selectors = [
        "article.hm-product-item",
        "li.product-item",
        "ul.products-listing > li",
        "div.product-tile",
        "article[data-articlecode]",
        "li[class*='product']",
        "[class*='product-item']",
        "[class*='ProductCard']",
        "[class*='product_card']",
        "[data-testid*='product']",
        "article",
        "[class*='product']",
    ]
    
    selector_results = {}
    for sel in product_selectors:
        try:
            count = page.evaluate(f"() => document.querySelectorAll({repr(sel)}).length")
            selector_results[sel] = count
        except Exception as e:
            selector_results[sel] = f"ERROR: {e}"

    # Get a snippet of body HTML
    body_html = page.evaluate("() => document.body.innerHTML.slice(0, 8000)")
    
    # Check for productpage in links
    productpage_links = page.evaluate("""
        () => Array.from(document.querySelectorAll('a')).filter(a => a.href.includes('productpage')).map(a => a.href).slice(0, 20)
    """)
    
    # Get ALL links matching /en_in/ pattern
    en_in_links = page.evaluate("""
        () => Array.from(document.querySelectorAll('a')).filter(a => a.href.includes('/en_in/')).map(a => ({href: a.href, text: a.textContent.trim().slice(0,50), classes: a.className})).slice(0, 30)
    """)
    
    # Save full HTML
    full_html = page.content()
    DUMP_PATH.write_text(full_html, encoding="utf-8")
    
    ctx.close()
    browser.close()

# Write diagnostics
lines = [
    f"=== PAGE TITLE ===",
    title,
    f"",
    f"=== SELECTOR COUNTS ===",
]
for sel, cnt in selector_results.items():
    lines.append(f"  {sel!r:50s} => {cnt}")

lines += ["", "=== PRODUCTPAGE LINKS (first 20) ==="]
for link in productpage_links:
    lines.append(f"  {link}")

lines += ["", "=== /en_in/ LINKS (first 30) ==="]
for item in en_in_links:
    lines.append(f"  {item['href']}  |  text={item['text']}  |  classes={item['classes']}")

lines += ["", "=== FIRST 100 HREFS ==="]
for href in all_hrefs:
    lines.append(f"  {href}")

lines += ["", "=== TOP TAG COUNTS ==="]
for tag, cnt in tag_counts:
    lines.append(f"  {tag}: {cnt}")

lines += ["", "=== BODY HTML SNIPPET (first 8000 chars) ===", body_html]

log_text = "\n".join(lines)
LOG_PATH.write_text(log_text, encoding="utf-8")
print(log_text[:3000])
print(f"\n\nFull HTML saved to: {DUMP_PATH}")
print(f"Diagnostics saved to: {LOG_PATH}")
