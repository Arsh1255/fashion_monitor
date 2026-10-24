import logging
import time
import re
from typing import List, Set
from pathlib import Path

from camoufox.sync_api import Camoufox
from src.models import Product
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class UsPoloScraper(BaseScraper):
    def fetch_new_arrivals(self) -> List[Product]:
        """Scrape new arrival listings across all configured category target URLs."""
        all_products: List[Product] = []
        seen_urls: Set[str] = set()

        for category, region, url in self.get_category_urls():
            if not url:
                continue
                
            logger.info(f"[{self.retailer_name}] --- Scraping Category: '{category}' ---")
            
            with Camoufox(headless=self.config.headless) as browser:
                page = browser.new_page()
                
                limit = self.max_candidate_pool_size
                max_pages = self.max_pages_per_category
                category_count = 0
                
                for page_num in range(1, max_pages + 1):
                    if category_count >= limit:
                        break
                        
                    paged_url = url if page_num == 1 else f"{url}?page={page_num}"
                    logger.info(f"[{self.retailer_name}] Loading page {page_num}/{max_pages}: {paged_url}")
                    
                    try:
                        page.goto(paged_url, wait_until="domcontentloaded", timeout=45000)
                        self._simulate_human_behavior(page)
                        
                        # Ensure products are loaded
                        try:
                            page.wait_for_selector('.grid__item, .product-card', timeout=10000)
                        except Exception:
                            logger.warning(f"[{self.retailer_name}] No product cards found on {paged_url}")
                            pass
                            
                        # Light scroll to trigger lazy loading images just in case
                        for _ in range(2):
                            page.evaluate("window.scrollBy(0, 900)")
                            page.wait_for_timeout(700)
                            
                        raw_items = page.evaluate("""() => {
                            const productCards = Array.from(document.querySelectorAll('.grid__item, .product-card'));
                            return productCards.map(card => {
                                const link = card.querySelector('a');
                                const titleEl = card.querySelector('.card-information__text, .product-title');
                                return { 
                                    href: link ? link.href : null,
                                    name: titleEl ? titleEl.innerText.trim() : null
                                };
                            }).filter(item => item.href && item.href.includes('/products/'));
                        }""")
                        
                        page_extracted = 0
                        for item in raw_items:
                            if category_count >= limit:
                                break
                                
                            href = item.get('href', '').strip()
                            name = item.get('name', '').strip() or f"{self.retailer_name} Product"
                            
                            if not href or href in seen_urls:
                                continue
                                
                            seen_urls.add(href)
                            
                            product = Product(
                                name=name,
                                price="",  # Will extract in details
                                product_url=href,
                                art_no=href.split('/')[-1].split('?')[0],  # Temporary ID until detail page overrides it
                                image_url="",
                                category=category
                            )
                            all_products.append(product)
                            category_count += 1
                            page_extracted += 1
                            
                        if page_extracted == 0:
                            logger.info(f"[{self.retailer_name}] No more products found — stopping pagination.")
                            break
                            
                    except Exception as e:
                        logger.error(f"[{self.retailer_name}] Failed to scrape {paged_url}: {e}")
                        break
                    
        return all_products

    def scrape_product_details_batch(self, products: List[Product]) -> None:
        """Scrape detail pages for a batch of products to enrich their raw_page_text."""
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
                    
                    details = page.evaluate("""() => {
                        const accordionData = {};
                        document.querySelectorAll('.pdp-clps-item').forEach(item => {
                            const header = item.querySelector('.pdp-clps-header')?.innerText.replace(/[+−–]/g, '').trim();
                            const content = item.querySelector('.pdp-clps-content')?.innerText.trim();
                            if (header && content) {
                                accordionData[header] = content;
                            }
                        });

                        let sku = null;
                        document.querySelectorAll('script[type="application/ld+json"]').forEach(script => {
                            try {
                                const data = JSON.parse(script.innerText);
                                if (data['@type'] === 'Product' || data.sku) {
                                    sku = data.sku || sku;
                                }
                            } catch (e) {}
                        });

                        const imgEl = document.querySelector('meta[property="og:image"]');

                        return {
                            productName: document.querySelector('h1.product-title')?.innerText.trim(),
                            price: document.querySelector('.price-item--sale')?.innerText.trim() || document.querySelector('.price-item--regular')?.innerText.trim(),
                            sku: sku,
                            image_url: imgEl ? imgEl.getAttribute('content') : null,
                            details: {
                                description: accordionData["Description"] || "",
                                specifications: accordionData["Specifications"] || "",
                                composition: accordionData["Composition & Care"] || ""
                            }
                        };
                    }""")
                    
                    if details:
                        if details.get('sku'):
                            product.raw_page_text += f"\nSKU: {details['sku']}"
                        if not product.name and details.get('productName'):
                            product.name = details['productName']
                        if not product.price and details.get('price'):
                            product.price = details['price']
                        if details.get('image_url'):
                            product.image_url = details['image_url']
                            if product.image_url.startswith('//'):
                                product.image_url = 'https:' + product.image_url
                                
                        desc = details.get('details', {})
                        product.description = desc.get('description', '')
                        product.composition = desc.get('composition', '')
                        
                        raw_text = []
                        if product.name: raw_text.append(f"Name: {product.name}")
                        if product.description: raw_text.append(f"Description: {product.description}")
                        if desc.get('specifications'): raw_text.append(f"Specifications: {desc['specifications']}")
                        if product.composition: raw_text.append(f"Composition & Care: {product.composition}")
                        
                        product.raw_page_text = "\\n".join(raw_text)
                        
                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to scrape detail page for {product.art_no}: {e}")

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
                logger.info(f"[{self.retailer_name}] Saved image for {product.art_no}")
                
            except Exception as e:
                logger.error(f"[{self.retailer_name}] Failed to download image for {product.art_no}: {e}")
