import logging
import re
from typing import List, Set
from pathlib import Path

from camoufox.sync_api import Camoufox
from src.models import Product
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class SheinScraper(BaseScraper):
    """Scraper implementation for SHEIN."""

    def fetch_new_arrivals(self) -> List[Product]:
        """Scrape new arrival listings across all configured category target URLs."""
        all_products: List[Product] = []
        seen_art_nos: Set[str] = set()

        for category, region, url in self.get_category_urls():
            if not url:
                continue

            logger.info(f"[{self.retailer_name}] --- Scraping Category: '{category}' ---")

            with Camoufox(headless=self.config.headless) as browser:
                page = browser.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    self._simulate_human_behavior(page)

                    # Trigger infinite scrolling to lazy-load more products
                    # Scroll a few times to get enough items
                    for _ in range(4):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000)
                        
                        # Break early if we have enough items in DOM
                        cards_in_dom = page.evaluate("document.querySelectorAll('a[href*=\"/p/\"]').length")
                        if cards_in_dom >= self.max_candidate_pool_size:
                            break

                    raw_items = page.evaluate("""() => {
                        const productLinks = Array.from(document.querySelectorAll('a[href*="/p/"]'));
                        return productLinks.map(link => {
                            return { 
                                href: link.href,
                                name: link.innerText.trim() || link.getAttribute('title')
                            };
                        }).filter(item => item.href);
                    }""")

                    category_count = 0
                    for item in raw_items:
                        if category_count >= self.max_candidate_pool_size:
                            break

                        href = item.get('href', '').strip()
                        name = item.get('name', '').strip() or f"{self.retailer_name} Product"

                        if not href:
                            continue
                            
                        # Try to extract the 9-digit stable numeric ID from the URL: /p/443395375_navyblue -> 443395375
                        match = re.search(r'/p/(\d+)', href)
                        if not match:
                            continue
                            
                        art_no = match.group(1)
                        if art_no in seen_art_nos:
                            continue

                        seen_art_nos.add(art_no)

                        product = Product(
                            name=name,
                            price="",  # Will extract in details
                            product_url=href,
                            art_no=art_no,
                            image_url="",
                            category=category
                        )
                        all_products.append(product)
                        category_count += 1

                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to scrape category '{category}': {e}")

        return all_products

    def scrape_product_details_batch(self, products: List[Product]) -> None:
        """Scrape detail pages for a batch of products to enrich their raw_page_text and acquire image URLs."""
        if not products:
            return

        with Camoufox(headless=self.config.headless) as browser:
            page = browser.new_page()

            for product in products:
                if not product.product_url:
                    continue

                logger.info(f"[{self.retailer_name}] Scraping detail page for: {product.art_no}")
                try:
                    page.goto(product.product_url, wait_until="domcontentloaded", timeout=45000)
                    self._simulate_human_behavior(page)

                    # Give it a second to render JSON-LD and product details
                    page.wait_for_timeout(2000)

                    details = page.evaluate("""() => {
                        // 1. Try to get JSON-LD for structured basic info
                        const scripts = [...document.querySelectorAll('script[type="application/ld+json"]')];
                        const productData = scripts
                            .map(s => {
                                try { return JSON.parse(s.innerText); } catch(e) { return {}; }
                            })
                            .find(x => x['@type'] === 'Product' || x['@type'] === 'ProductGroup');

                        // 2. Try to get the main product details block for AI analysis
                        let rawText = '';
                        const detailBlock = document.querySelector('.product-intro__description-table');
                        if (detailBlock) {
                            rawText = detailBlock.innerText;
                        } else {
                            // fallback try all td elements if table class changed
                            rawText = Array.from(document.querySelectorAll('td')).map(td => td.innerText).join(' ');
                        }

                        // 3. Find the highest quality image
                        // First try to find the zoomed hero image, or fallback to any jpg that isn't a swatch/thumbnail
                        let imgUrl = null;
                        const mainImage = document.querySelector('img.zoom-cursor') || document.querySelector('img.rilrtl-lazy-img-loaded');
                        if (mainImage) {
                            imgUrl = mainImage.src || mainImage.getAttribute('data-src');
                        }
                        
                        if (!imgUrl) {
                            // Fallback to any non-thumbnail product image
                            const allImgs = Array.from(document.querySelectorAll('img')).map(img => img.src || img.getAttribute('data-src')).filter(Boolean);
                            const productImgs = allImgs.filter(src => src.includes('shein') && src.includes('.jpg') && !src.includes('SWATCH') && !src.includes('78Wx98H'));
                            if (productImgs.length > 0) {
                                imgUrl = productImgs[0];
                            }
                        }

                        return {
                            name: productData ? productData.name : null,
                            price: (productData && productData.offers) ? (productData.offers.price || (productData.offers[0] && productData.offers[0].price)) : null,
                            description: productData ? productData.description : null,
                            raw_text: rawText,
                            image_url: imgUrl
                        };
                    }""")

                    if details:
                        if not product.name and details.get('name'):
                            product.name = details['name']
                        if not product.price and details.get('price'):
                            product.price = str(details['price'])
                            
                        # If price is missing from JSON-LD, try to grab it from DOM
                        if not product.price:
                            price_el = page.query_selector('.original-price, .discount-price, .price')
                            if price_el:
                                product.price = price_el.inner_text().strip()
                                
                        if details.get('image_url'):
                            product.image_url = details['image_url']
                            if product.image_url.startswith('//'):
                                product.image_url = 'https:' + product.image_url

                        product.raw_page_text = details.get('raw_text', '')
                        
                        desc = details.get('description', '')
                        if not desc:
                            # User requested fallback to raw_text if genuine description is missing
                            desc = details.get('raw_text', '')
                        product.description = desc

                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to extract details for {product.art_no}: {e}")

    def capture_product_screenshots(self, products: List[Product]) -> None:
        """Download high-resolution studio photos for a batch of products."""
        import urllib.request
        
        for product in products:
            if not product.image_url:
                continue
                
            file_path = self.screenshot_dir / f"{product.art_no}.jpg"
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                req = urllib.request.Request(product.image_url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    content = response.read()
                
                with open(file_path, "wb") as f:
                    f.write(content)
                    
                product.screenshot_path = str(file_path)
            except Exception as e:
                logger.error(f"[{self.retailer_name}] Failed to download image for {product.art_no}: {e}")
