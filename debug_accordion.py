"""
Debug v3: Extract H&M product data from __NEXT_DATA__ JSON
and also test clicking accordion button EXACTLY ONCE.
"""
import json
import time
from camoufox.sync_api import Camoufox

URL = "https://www2.hm.com/en_in/productpage.1344928012.html"
OUT = "debug_accordion_output.txt"
lines = []

def log(msg):
    print(str(msg))
    lines.append(str(msg))

def search_dict(obj, keywords, path="", depth=0, results=None):
    """Recursively search for keys containing any of the keywords."""
    if results is None:
        results = []
    if depth > 10:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_path = f"{path}.{k}" if path else k
            if any(kw.lower() in str(k).lower() for kw in keywords):
                results.append((full_path, v))
            search_dict(v, keywords, full_path, depth + 1, results)
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:5]):  # limit list traversal
            search_dict(item, keywords, f"{path}[{i}]", depth + 1, results)
    return results

with Camoufox(headless=True) as browser:
    page = browser.new_page()
    log(f"Navigating to {URL}...")
    page.goto(URL, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(2000)

    # ── Part 1: Extract __NEXT_DATA__ JSON ───────────────────────────────────
    log("\n=== EXTRACTING __NEXT_DATA__ JSON ===")
    next_data_raw = page.evaluate("""
        () => {
            const el = document.getElementById('__NEXT_DATA__');
            return el ? el.textContent : null;
        }
    """)
    
    if next_data_raw:
        try:
            next_data = json.loads(next_data_raw)
            log(f"__NEXT_DATA__ parsed successfully. Top-level keys: {list(next_data.keys())}")
            
            # Search for product attribute fields
            search_terms = ["sleeve", "neckline", "fit", "composition", "waist", "style", "length", "pattern", "material", "attribute"]
            log("\n=== SEARCHING __NEXT_DATA__ FOR PRODUCT ATTRIBUTES ===")
            results = search_dict(next_data, search_terms)
            for path, val in results[:60]:
                val_str = str(val)[:150] if not isinstance(val, (dict, list)) else f"[{type(val).__name__} len={len(val)}]"
                log(f"  {path}: {val_str}")
            
            # Also dump top-level pageProps structure
            page_props = next_data.get("props", {}).get("pageProps", {})
            log(f"\n=== pageProps top-level keys: {list(page_props.keys())}")
            
            # Look for product-specific data
            for key in page_props:
                val = page_props[key]
                if isinstance(val, dict):
                    log(f"  pageProps.{key} -> dict keys: {list(val.keys())[:10]}")
                elif isinstance(val, list) and val:
                    log(f"  pageProps.{key} -> list len={len(val)}, first item keys: {list(val[0].keys()) if isinstance(val[0], dict) else str(val[0])[:80]}")
                    
            # Save full __NEXT_DATA__ to separate file for inspection
            with open("debug_next_data.json", "w", encoding="utf-8") as f:
                json.dump(next_data, f, indent=2, ensure_ascii=False)
            log("\n✅ Full __NEXT_DATA__ saved to debug_next_data.json")
            
        except json.JSONDecodeError as e:
            log(f"Failed to parse __NEXT_DATA__: {e}")
    else:
        log("No __NEXT_DATA__ element found!")

    # ── Part 2: Click accordion button EXACTLY ONCE ──────────────────────────
    log("\n=== CLICKING 'Description & fit' BUTTON EXACTLY ONCE ===")
    click_result = page.evaluate("""
        () => {
            // Find the BUTTON (not the span, not the parent divs)
            const buttons = Array.from(document.querySelectorAll('button'));
            const descBtn = buttons.find(b => {
                const t = b.innerText.trim().toLowerCase();
                return t === 'description & fit' || t.startsWith('description');
            });
            if (descBtn) {
                descBtn.click();
                return { found: true, text: descBtn.innerText.trim().slice(0, 80), class: descBtn.className };
            }
            return { found: false };
        }
    """)
    log(f"  Result: {click_result}")
    page.wait_for_timeout(1500)

    log("\n=== CLICKING 'Material & Care' BUTTON EXACTLY ONCE ===")
    click_result2 = page.evaluate("""
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const matBtn = buttons.find(b => {
                const t = b.innerText.trim().toLowerCase();
                return t.includes('material') && t.includes('care');
            });
            if (matBtn) {
                matBtn.click();
                return { found: true, text: matBtn.innerText.trim().slice(0, 80), class: matBtn.className };
            }
            return { found: false };
        }
    """)
    log(f"  Result: {click_result2}")
    page.wait_for_timeout(1500)

    # ── Part 3: Check body text after single click ────────────────────────────
    log("\n=== BODY TEXT AFTER SINGLE CLICK ===")
    body = page.inner_text("body", timeout=5000)
    
    for kw in ["Sleeve Length", "Neckline", "Fit:", "Length:", "Waist Rise", "Style:", "Art. No", "Composition", "Cotton"]:
        found_kw = kw.lower() in body.lower()
        log(f"  '{kw}': {'✓ FOUND' if found_kw else '✗ MISSING'}")

    # Extract just the product-relevant section
    log("\n=== RELEVANT BODY SECTION (between DESCRIPTION and DELIVERY) ===")
    import re
    match = re.search(
        r'(DESCRIPTION\s*&\s*FIT|Description\s*&\s*fit)([\s\S]{50,3000}?)(DELIVERY AND PAYMENT|Shop\s+LADIES)',
        body, re.IGNORECASE
    )
    if match:
        log(match.group(0)[:2000])
    else:
        # Just print middle section of body
        log(body[500:3000])

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\nDone. Output -> {OUT}")
