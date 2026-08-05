"""
Playwright + Camoufox Web Scraper module for Fashion Trend Monitor.

Handles stealthy automated browsing, URL-based pagination, item extraction across
multiple categories (Men, Ladies, Kids) using confirmed H&M DOM selectors,
direct high-res studio photo downloading with retries, and screenshot directory maintenance.

Uses Playwright Chromium for listing pages and Camoufox (patched Firefox) exclusively
for product detail pages — Camoufox bypasses Akamai WAF where Chromium is blocked.

Detail scraping intentionally captures raw accordion text only (Description & Fit /
Material & Care). Structured attribute extraction is delegated to the AI analyzer.
"""

import re
import time
import random
import logging
import urllib.request
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import sync_playwright, Page
from camoufox.sync_api import Camoufox

from src.config import Config
from src.models import Product
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class HMScraper(BaseScraper):
    """Scraper implementation for H&M India online store."""

    def download_product_photo(self, product: Product, max_attempts: int = 3) -> Optional[Path]:
        """
        Download high-resolution studio photo directly via HTTP GET with retries.

        Constructs a high-res H&M CDN URL from the article number if no image_url is available.
        """
        # Build CDN URL from art_no if image_url missing
        if not product.image_url or not product.image_url.startswith("http"):
            logger.warning(f"Product {product.art_no} has no CDN image URL — skipping download.")
            return None

        base_url = product.image_url.split("?")[0]
        urls_to_try = [
            f"{base_url}?imwidth=1536",
            f"{base_url}?imwidth=1260",
            f"{base_url}?imwidth=820",
            base_url,
        ]

        local_path = self.screenshot_dir / f"{product.art_no}.jpg"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www2.hm.com/"
        }

        for attempt in range(1, max_attempts + 1):
            for candidate_url in urls_to_try:
                try:
                    logger.info(f"Downloading photo for {product.art_no} ({product.category}) attempt {attempt}...")
                    req = urllib.request.Request(candidate_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=12) as response:
                        image_data = response.read()
                        if len(image_data) > 5000:
                            local_path.write_bytes(image_data)
                            logger.info(f"Saved photo ({len(image_data)} bytes) for {product.art_no} at {local_path}")
                            product.screenshot_path = str(local_path)
                            return local_path
                except Exception as err:
                    logger.debug(f"Attempt {attempt} for {candidate_url[:80]}: {err}")
                    time.sleep(0.8)

        logger.warning(f"Could not download photo for {product.art_no} after {max_attempts} retries.")
        return None

    def _extract_products_from_page(self, page: Page, category_name: str, seen_urls: set, limit: int) -> List[Product]:
        """
        Extract products from the current page state using confirmed H&M DOM selectors.
        Uses article[data-articlecode] which is confirmed working.
        """
        products = []

        # Use JavaScript to extract all product data in one pass
        raw_items = page.evaluate("""
            () => {
                const articles = Array.from(document.querySelectorAll('article[data-articlecode]'));
                return articles.map(article => {
                    const artCode = article.getAttribute('data-articlecode') || '';
                    const links = Array.from(article.querySelectorAll('a[href*="productpage"]'));
                    const nameLink = links.find(a => a.textContent.trim().length > 0) || links[0];
                    const name = nameLink ? nameLink.textContent.trim() : '';
                    const href = nameLink ? nameLink.href : '';

                    // Price: search for element containing 'Rs.' or '₹'
                    const allEls = Array.from(article.querySelectorAll('span, p, strong, div'));
                    const priceEl = allEls.find(el => {
                        const txt = el.textContent.strip ? el.textContent.strip() : el.textContent.trim();
                        return el.childElementCount === 0 && (txt.includes('Rs.') || txt.includes('₹') || /\\bRs\\b/i.test(txt));
                    });
                    const price = priceEl ? priceEl.textContent.trim() : 'N/A';

                    // Image: get highest quality src
                    const img = article.querySelector('img');
                    let imageUrl = '';
                    if (img) {
                        const srcset = img.getAttribute('srcset') || '';
                        if (srcset) {
                            const parts = srcset.split(',').map(s => s.trim()).filter(Boolean);
                            const last = parts[parts.length - 1];
                            imageUrl = last ? last.split(' ')[0] : '';
                        }
                        if (!imageUrl) {
                            imageUrl = img.src || img.getAttribute('data-src') || '';
                        }
                        if (imageUrl.startsWith('//')) imageUrl = 'https:' + imageUrl;
                    }
                    return { artCode, name, href, price, imageUrl };
                });
            }
        """)

        for item in raw_items:
            if len(products) >= limit:
                break

            art_no = item.get("artCode", "").strip()
            href = item.get("href", "").strip()
            name = item.get("name", "").strip() or "H&M Fashion Item"
            price = item.get("price", "N/A").strip()
            image_url = item.get("imageUrl", "").strip()

            if not art_no or not href:
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)

            name = re.sub(r"\s+", " ", name)

            product = Product(
                name=name,
                price=price if price != "N/A" else "",
                product_url=href,
                art_no=art_no,
                image_url=image_url,
                category=category_name
            )
            products.append(product)

        return products

    def _simulate_human_behavior(self, page: Page) -> None:
        """Simulate human-like delays, scrolling, and mouse movements to bypass WAF."""
        delay = random.uniform(3.0, 10.0)
        logger.debug(f"Simulating human wait for {delay:.2f} seconds...")
        
        # Move mouse around randomly during the wait
        end_time = time.time() + delay
        while time.time() < end_time:
            x = random.randint(100, 1000)
            y = random.randint(100, 800)
            try:
                page.mouse.move(x, y, steps=random.randint(5, 15))
            except Exception:
                pass
            
            # 30% chance to scroll
            if random.random() < 0.3:
                scroll_y = random.randint(-300, 500)
                try:
                    page.evaluate(f"window.scrollBy(0, {scroll_y})")
                except Exception:
                    pass
                    
            time.sleep(random.uniform(0.5, 1.5))

    def scrape_category_listings(self, page: Page, category_name: str, base_url: str) -> List[Product]:
        """
        Scrape product listings for a single category across multiple pages.
        Uses confirmed H&M selectors: article[data-articlecode].
        Uses URL pagination: ?page=1, ?page=2, etc.
        """
        logger.info(f"--- Scraping Category: '{category_name}' ({base_url}) ---")
        all_products: List[Product] = []
        seen_urls: set = set()
        limit = self.config.max_items_per_category
        max_pages = self.config.max_pages_per_category

        browser_headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }

        for page_num in range(1, max_pages + 1):
            if len(all_products) >= limit:
                break

            paged_url = base_url if page_num == 1 else f"{base_url}?page={page_num}"
            logger.info(f"[{category_name}] Loading page {page_num}/{max_pages}: {paged_url}")

            try:
                page.goto(paged_url, wait_until="domcontentloaded", timeout=45000)
                
                # Perform human-like simulation to bypass Akamai WAF
                self._simulate_human_behavior(page)

                # Accept cookie banner only on first page
                if page_num == 1:
                    try:
                        page.wait_for_timeout(1500)
                        cookie_btn = page.query_selector("#onetrust-accept-btn-handler")
                        if cookie_btn and cookie_btn.is_visible():
                            cookie_btn.click()
                            logger.info(f"[{category_name}] Dismissed cookie banner.")
                            page.wait_for_timeout(800)
                    except Exception:
                        pass

                # Wait for product articles to render
                try:
                    page.wait_for_selector("article[data-articlecode]", timeout=18000)
                except Exception:
                    logger.warning(f"[{category_name}] Timeout waiting for article[data-articlecode] on page {page_num}.")

                # Light scroll to trigger lazy loading of images
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 900)")
                    page.wait_for_timeout(700)

                page_products = self._extract_products_from_page(page, category_name, seen_urls, limit - len(all_products))
                logger.info(f"[{category_name}] Extracted {len(page_products)} products from page {page_num}.")
                all_products.extend(page_products)

                if len(page_products) == 0:
                    logger.info(f"[{category_name}] No more products found — stopping pagination.")
                    break

            except Exception as e:
                logger.error(f"[{category_name}] Error on page {page_num}: {e}")
                break

        logger.info(f"Successfully extracted {len(all_products)} total products for '{category_name}'.")
        return all_products

    def fetch_new_arrivals(self) -> List[Product]:
        """Scrape new arrival listings across all configured category target URLs."""
        all_products: List[Product] = []

        with Camoufox(headless=True) as browser:
            page = browser.new_page()

            for category_name, category_url in self.categories.items():
                cat_products = self.scrape_category_listings(page, category_name, category_url)
                all_products.extend(cat_products)

        logger.info(f"Successfully scraped total {len(all_products)} products across all categories.")
        return all_products

    def capture_product_screenshots(self, products: List[Product]) -> None:
        """Download high-res studio photos for a list of products."""
        for product in products:
            self.download_product_photo(product)



    def scrape_product_detail(self, page: Page, product: Product) -> None:
        """
        Visit a product detail page via Camoufox, click accordions, and capture raw text.
        """
        try:
            referer = (
                f"https://www2.hm.com/en_in/{product.category.lower()}/new-arrivals/view-all.html"
                if product.category
                else "https://www2.hm.com/en_in/index.html"
            )
            logger.info(f"Navigating detail URL for {product.art_no}...")
            # Use domcontentloaded instead of networkidle since we don't need to wait for tracking scripts
            page.goto(product.product_url, referer=referer, wait_until="domcontentloaded", timeout=45000)
            
            # Perform human-like simulation to bypass Akamai WAF
            self._simulate_human_behavior(page)

            title = page.title() or ""
            if "Access Denied" in title:
                logger.warning(f"Access Denied by WAF on {product.art_no}. Skipping.")
                return
            try:
                sniff = page.locator("body").inner_text(timeout=3000)[:500]
                if "Access Denied" in sniff:
                    logger.warning(f"Access Denied by WAF on {product.art_no}. Skipping.")
                    return
            except Exception:
                pass

            # Capture raw accordion text via regex blocks (bypasses Playwright visibility limits by extracting text nodes directly)
            data = page.evaluate(r"""
                () => {
                    // Extract all leaf text nodes to avoid hidden-element filtering of innerText
                    const text = Array.from(document.body.querySelectorAll('*'))
                        .filter(el => el.children.length === 0 && !['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG'].includes(el.tagName.toUpperCase()))
                        .map(el => el.textContent.trim())
                        .filter(Boolean)
                        .join('\n');

                    const result = {
                        price: '',
                        description: '',
                        raw_page_text: '',
                        fit_chars: 0,
                        material_chars: 0
                    };

                    const priceMatch = text.match(/(?:Rs\.|₹)\s*([\d,]+(?:\.\d{2})?)/i);
                    if (priceMatch) {
                        result.price = 'Rs. ' + priceMatch[1];
                    }

                    // DESCRIPTION & FIT panel (and Materials since it's above Delivery)
                    let fitBlock = '';
                    const fitMatch = text.match(
                        /Description\s*&\s*fit\s*([\s\S]+?)(?=Delivery\s*and\s*Payment|Delivery\s*&\s*Payment|STYLE\s*WITH|SIMILAR\s*ITEMS|$)/i
                    );
                    if (fitMatch) {
                        fitBlock = fitMatch[1]
                            .replace(/\bREAD\s*MORE\b[\s\S]*$/i, '')
                            .replace(/\bDisclaimer:[\s\S]*$/i, '')
                            .trim();
                    }
                    result.fit_chars = fitBlock.length;

                    if (fitBlock.length > 30) {
                        result.raw_page_text = '=== DESCRIPTION & FIT ===\n' + fitBlock;
                    } else {
                        result.raw_page_text = '';
                    }

                    if (fitBlock) {
                        const prose = fitBlock.split('\n')
                            .map(l => l.trim())
                            .find(l =>
                                l.length > 50
                                && !/^(New Arrival|Art\.?\s*No|Net Quantity|Common|Description:|Size:|Length:|Sleeve|Fit:|Neckline|Price|Country|Manufactur|Marketed|Customer|Date|Disclaimer|Bring your clean)/i.test(l)
                            );
                        if (prose) {
                            result.description = prose.slice(0, 450);
                        }
                    }

                    return result;
                }
            """)

            if data and isinstance(data, dict):
                if not product.price and data.get("price"):
                    product.price = data["price"].strip()
                product.description = (data.get("description", "") or "").strip()
                product.raw_page_text = (data.get("raw_page_text", "") or "").strip()
                product.fit_details = {}
                product.composition = ""
                product.material_type = ""
                product.fit = ""

                logger.info(
                    f"Detail scraped {product.art_no}: "
                    f"price='{product.price}' | "
                    f"raw_text_chars={len(product.raw_page_text)} | "
                    f"fit_chars={data.get('fit_chars', 0)} | "
                    f"material_chars={data.get('material_chars', 0)} | "
                    f"desc='{(product.description or '')[:60]}'"
                )
                if len(product.raw_page_text) < 50:
                    logger.warning(
                        f"Detail text for {product.art_no} looks empty — "
                        "accordion may not have expanded properly."
                    )

        except Exception as e:
            logger.warning(f"Could not scrape detail page for {product.art_no}: {e}")

    def scrape_product_details_batch(self, products: List[Product]) -> None:
        """
        Use Camoufox (patched Firefox) exclusively for product detail pages.
        Camoufox has genuine Firefox TLS fingerprints that bypass Akamai WAF
        where Playwright Chromium gets blocked with Access Denied.
        """
        if not products:
            return

        logger.info(
            f"Scraping product detail pages for {len(products)} products via Camoufox only..."
        )

        # headless=True avoids NS_ERROR_UNKNOWN_SOCKET_TYPE on Windows
        with Camoufox(headless=True) as browser:
            page = browser.new_page()

            for i, product in enumerate(products):
                logger.info(
                    f"Detail page {i + 1}/{len(products)}: "
                    f"{product.art_no} -- {product.name[:50]}"
                )
                self.scrape_product_detail(page, product)
                delay = random.uniform(2.0, 5.0)
                logger.debug(f"Waiting {delay:.1f}s before next detail page...")
                time.sleep(delay)

        logger.info("Product detail scraping complete.")

