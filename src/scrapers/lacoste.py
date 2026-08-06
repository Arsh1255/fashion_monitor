import logging
import re
from typing import List
from pathlib import Path

from playwright.sync_api import sync_playwright
from src.models import Product
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class LacosteScraper(BaseScraper):
    """Scraper implementation for Lacoste."""

    def fetch_new_arrivals(self) -> List[Product]:
        """Scrape new arrival listings across all configured category target URLs."""
        from camoufox.sync_api import Camoufox
        
        products = []
        with Camoufox(headless=self.config.headless) as browser:
            for category_name, url in self.categories.items():
                if not url:
                    continue
                try:
                    logger.info(f"[{self.retailer_name}] Fetching {category_name} listings from {url}")
                    page = browser.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Scroll down a few times to trigger lazy load images
                    for _ in range(3):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000)

                    # Extract items directly from the DOM, scoping to .column.main to ignore unisex promotional carousels
                    items = page.evaluate("""() => {
                        const productCards = Array.from(document.querySelectorAll('.column.main .product-item'));
                        return productCards.map(card => {
                            const nameEl = card.querySelector('.product-item-link');
                            const priceEl = card.querySelector('[data-price-type="finalPrice"] .price');
                            const imgEl = card.querySelector('img.is_base_img') || card.querySelector('img.default') || card.querySelector('.product-item-photo img');
                            
                            const sku = card.querySelector('[data-product-sku]')?.getAttribute('data-product-sku') || 
                                        card.querySelector('.price-box')?.getAttribute('data-product-id');
                            
                            return {
                                name: nameEl ? nameEl.innerText.trim() : null,
                                url: nameEl ? nameEl.href : null,
                                price: priceEl ? priceEl.innerText.trim() : null,
                                image_url: imgEl ? imgEl.src : null,
                                sku: sku
                            };
                        }).filter(item => item.name && item.url);
                    }""")
                    
                    limit = self.config.max_items_per_category
                    category_count = 0
                    
                    for item in items:
                        if category_count >= limit:
                            break
                            
                        if not item.get("price"):
                            continue
                            
                        sku = item.get("sku")
                        if not sku:
                            match = re.search(r'-([A-Z0-9]+)\.html', item.get("url", ""))
                            if match:
                                sku = match.group(1)
                            else:
                                continue 
                                
                        product = Product(
                            art_no=sku,
                            name=item.get("name"),
                            price=item.get("price"),
                            category=category_name,
                            product_url=item.get("url"),
                            image_url=item.get("image_url")
                        )
                        products.append(product)
                        category_count += 1
                        
                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Error scraping {category_name}: {e}")
                    
            # browser.close() is automatically handled by the Camoufox context manager
            
        return products

    def scrape_product_details_batch(self, products: List[Product]) -> None:
        """Scrape detail pages for a batch of products using Camoufox."""
        from camoufox.sync_api import Camoufox
        
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
                        const productData = {
                            name: document.querySelector('h1.page-title span')?.innerText.trim(),
                            price: document.querySelector('[data-price-type="finalPrice"] .price')?.innerText.trim(),
                            sku: document.querySelector('.sku .value')?.innerText.trim() ||
                                 document.querySelector('[data-product-sku]')?.getAttribute('data-product-sku'),
                            description: '',
                            composition: '',
                            sizeAndFit: ''
                        };

                        const normalizeText = (text) => {
                            if (!text) return '';
                            let clean = text.replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n');
                            clean = clean.replace(/[ \\t]+/g, ' ');
                            return clean.split('\\n')
                                        .map(line => line.trim())
                                        .filter(line => line.length > 0)
                                        .join('\\n')
                                        .trim();
                        };

                        // Primary extraction path
                        document.querySelectorAll('.accordion-item').forEach(item => {
                            const title = item.querySelector('h3')?.textContent.trim().toLowerCase();
                            const content = item.querySelector('.accordion-content')?.innerText;

                            if (title && content) {
                                if (title.includes('description')) productData.description = normalizeText(content);
                                if (title.includes('composition')) productData.composition = normalizeText(content);
                                if (title.includes('size & fit') || title.includes('fit')) productData.sizeAndFit = normalizeText(content);
                            }
                        });

                        // Fallback extraction path
                        const getAccordionFallback = (titleText) => {
                            const titles = Array.from(document.querySelectorAll('.accordion-item, [data-role="trigger"]'));
                            const targetTitle = titles.find(el => (el.innerText || '').toLowerCase().includes(titleText.toLowerCase()));
                            return targetTitle && targetTitle.nextElementSibling ? targetTitle.nextElementSibling.innerText : '';
                        };
                        
                        if (!productData.description) productData.description = normalizeText(getAccordionFallback('Description'));
                        if (!productData.composition) productData.composition = normalizeText(getAccordionFallback('Composition'));
                        if (!productData.sizeAndFit) productData.sizeAndFit = normalizeText(getAccordionFallback('Size & Fit'));

                        return productData;
                    }""")
                    
                    if details:
                        product.description = details.get('description', '')
                        product.composition = details.get('composition', '')
                        product.fit = details.get('sizeAndFit', '')
                        
                        raw_text = []
                        if details.get('name'): raw_text.append(f"Name: {details['name']}")
                        if details.get('description'): raw_text.append(f"Description: {details['description']}")
                        if details.get('composition'): raw_text.append(f"Composition: {details['composition']}")
                        if details.get('sizeAndFit'): raw_text.append(f"Size & Fit: {details['sizeAndFit']}")
                        product.raw_page_text = "\\n".join(raw_text)
                        
                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to scrape detail page for {product.art_no}: {e}")
                    
    def capture_product_screenshots(self, products: List[Product]) -> None:
        """Download high-resolution studio photos for a batch of products."""
        import requests
        
        for product in products:
            if not product.image_url:
                continue
                
            file_path = self.screenshot_dir / f"{product.art_no}.jpg"
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(product.image_url, headers=headers, timeout=15)
                response.raise_for_status()
                
                with open(file_path, "wb") as f:
                    f.write(response.content)
                    
                product.screenshot_path = str(file_path)
                logger.info(f"[{self.retailer_name}] Saved image for {product.art_no}")
                
            except Exception as e:
                logger.error(f"[{self.retailer_name}] Failed to download image for {product.art_no}: {e}")
