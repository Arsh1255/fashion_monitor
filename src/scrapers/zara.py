import re
import json
import logging
import urllib.request
from typing import List, Set

from camoufox.sync_api import Camoufox
from src.scrapers.base import BaseScraper
from src.models import Product

logger = logging.getLogger(__name__)

class ZaraScraper(BaseScraper):
    def fetch_new_arrivals(self) -> List[Product]:
        all_products: List[Product] = []
        seen_art_nos: Set[str] = set()

        for category, region, url in self.get_category_urls():
            if not url:
                continue

            logger.info(f"[{self.retailer_name}] --- Scraping Category: '{category}' ({region}) ---")
            category_count = 0
            
            with Camoufox(headless=self.config.headless) as browser:
                page = browser.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    self._simulate_human_behavior(page)
                    
                    # Scroll down to load lazy elements
                    for _ in range(3):
                        page.evaluate("window.scrollBy(0, 1000)")
                        page.wait_for_timeout(1000)
                    
                    raw_items = page.evaluate(r"""() => {
                        return Array.from(document.querySelectorAll('a'))
                            .map(a => a.href)
                            .filter(href => href && href.includes('-p') && href.includes('.html'));
                    }""")
                    
                    # Deduplicate internally on the page
                    unique_hrefs = list(set(raw_items))
                    
                    if not unique_hrefs:
                        logger.info(f"[{self.retailer_name}] No products found on {category} page.")
                        continue
                        
                    for href in unique_hrefs:
                        if category_count >= self.config.max_candidate_pool_size:
                            break
                            
                        # Extract URL ID (e.g., -p01564770.html -> 01564770)
                        match = re.search(r'-p(\d+)\.html', href)
                        if not match:
                            continue
                            
                        art_no = match.group(1)
                        
                        if art_no in seen_art_nos:
                            continue
                            
                        seen_art_nos.add(art_no)
                        
                        product = Product(
                            name=f"{self.retailer_name} Product", # will be overwritten
                            price="",
                            product_url=href,
                            art_no=art_no,
                            image_url="",
                            category=category
                        )
                        all_products.append(product)
                        category_count += 1
                        
                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to scrape {category}: {e}")
                    
        return all_products

    def scrape_product_details_batch(self, products: List[Product]) -> None:
        if not products:
            return
            
        with Camoufox(headless=self.config.headless) as browser:
            page = browser.new_page()
            
            for product in products:
                try:
                    page.goto(product.product_url, wait_until="domcontentloaded", timeout=60000)
                    self._simulate_human_behavior(page)
                    
                    html = page.content()
                    
                    # 1. Try to extract from zara.analyticsData
                    analytics_match = re.search(r'zara\.analyticsData\s*=\s*({.*?});', html)
                    if analytics_match:
                        try:
                            data = json.loads(analytics_match.group(1))
                            if data.get("productName"):
                                product.name = data["productName"]
                            if data.get("mainPrice"):
                                price_val = data["mainPrice"]
                                currency = data.get("page", {}).get("currency", "₹")
                                if currency == "INR": currency = "₹"
                                elif currency == "USD": currency = "$"
                                elif currency == "EUR": currency = "€"
                                elif currency == "GBP": currency = "£"
                                product.price = f"{currency}{price_val}"
                        except Exception as e:
                            logger.debug(f"[{self.retailer_name}] JSON parse error in analyticsData: {e}")
                    
                    # Extract using Playwright locators to wait for React to inject them
                    try:
                        product.image_url = page.locator('meta[property="og:image"]').get_attribute("content", timeout=5000)
                        if product.image_url:
                            product.image_url = product.image_url.replace("&amp;", "&")
                    except Exception:
                        pass
                            
                    desc_found = False
                    
                    try:
                        product.description = page.locator('meta[name="description"]').get_attribute("content", timeout=2000)
                        if product.description:
                            desc_found = True
                    except Exception:
                        pass
                        
                    if not desc_found:
                        try:
                            product.description = page.locator('meta[property="og:description"]').get_attribute("content", timeout=2000)
                            if product.description:
                                desc_found = True
                        except Exception:
                            pass
                            
                    if product.description:
                        product.description = product.description.replace('\n', ' ').strip().replace('&amp;', '&').replace('&quot;', '"')
                    else:
                        product.description = "No description available."
                        
                    if product.name:
                        product.name = product.name.replace('&amp;', '&').replace('&quot;', '"')

                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to scrape details for {product.product_url}: {e}")

    def capture_product_screenshots(self, products: List[Product]) -> None:
        if not products:
            return
            
        for product in products:
            if not product.image_url:
                continue
                
            file_name = f"{product.art_no}.jpg"
            file_path = self.screenshot_dir / file_name
            
            try:
                req = urllib.request.Request(
                    product.image_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                    }
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    file_path.write_bytes(response.read())
                    product.screenshot_path = str(file_path)
            except Exception as e:
                logger.error(f"[{self.retailer_name}] Failed to download image for {product.art_no}: {e}")
