import re
import json
import logging
import urllib.request
from typing import List, Set

from camoufox.sync_api import Camoufox
from src.scrapers.base import BaseScraper
from src.models import Product

logger = logging.getLogger(__name__)

class HugoBossScraper(BaseScraper):
    def fetch_new_arrivals(self) -> List[Product]:
        all_products: List[Product] = []
        seen_art_nos: Set[str] = set()

        for category, region, url in self.get_category_urls():
            if not url:
                continue

            logger.info(f"[{self.retailer_name}] --- Scraping Category: '{category}' ---")
            
            start = 0
            chunk_size = 36
            category_count = 0
            
            with Camoufox(headless=self.config.headless) as browser:
                page = browser.new_page()
                
                while category_count < self.max_candidate_pool_size:
                    page_url = f"{url}?start={start}&sz={chunk_size}"
                    try:
                        page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                        self._simulate_human_behavior(page)
                        
                        raw_items = page.evaluate(r"""() => {
                            return Array.from(document.querySelectorAll('a'))
                                .map(a => a.href)
                                .filter(href => href && href.includes('.html') && /\/hbeu/.test(href));
                        }""")
                        
                        # Deduplicate internally on the page to find actual distinct items
                        unique_hrefs = list(set(raw_items))
                        
                        if not unique_hrefs:
                            logger.info(f"[{self.retailer_name}] No more products found at start={start}.")
                            break
                            
                        added_in_page = 0
                        for href in unique_hrefs:
                            if category_count >= self.max_candidate_pool_size:
                                break
                                
                            clean_path = href.split("?")[0].split("#")[0].rstrip("/")
                            last_segment = clean_path.split("/")[-1].replace(".html", "")
                            
                            # Extract 8-digit Style ID (e.g., hbeu50572451_925 -> 50572451)
                            match = re.search(r'(\d{8,})', last_segment)
                            art_no = match.group(1) if match else last_segment
                            
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
                            added_in_page += 1
                            
                        if added_in_page == 0:
                            # We didn't add any new products, meaning we've hit the end of the new items
                            break
                            
                        start += chunk_size
                        
                    except Exception as e:
                        logger.error(f"[{self.retailer_name}] Failed to scrape page at start={start}: {e}")
                        break
                        
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
                    
                    details = page.evaluate("""() => {
                        const getAccordionContent = (title) => {
                            const item = Array.from(document.querySelectorAll('.pdp-stage__accordion-item')).find(el => 
                                el.querySelector('.pdp-stage__accordion-button')?.innerText.trim().toUpperCase().includes(title)
                            );
                            return item ? item.querySelector('.pdp-stage__accordion-panel')?.innerText.trim() : null;
                        };
                        
                        // Grab JSON-LD blocks
                        const ldScripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                            .map(script => script.innerText.trim());
                            
                        return {
                            domDetails: getAccordionContent('DETAILS'),
                            domSizeAndFit: getAccordionContent('SIZE AND FIT'),
                            domMaterialAndCare: getAccordionContent('MATERIAL & CARE'),
                            domStyleNumber: document.querySelector('.pdp-stage__accordion-style-number')?.innerText.replace('Style','').trim(),
                            ldScripts: ldScripts
                        };
                    }""")
                    
                    if not details:
                        continue
                        
                    # Process JSON-LD
                    ld_scripts = details.get("ldScripts", [])
                    product_data = None
                    
                    for script in ld_scripts:
                        try:
                            data = json.loads(script)
                            if data.get("@type") == "ProductGroup":
                                product_data = data
                                break
                            elif data.get("@type") == "Product" and not product_data:
                                product_data = data
                        except:
                            pass
                            
                    if product_data:
                        if product_data.get("name"):
                            product.name = product_data["name"]
                        if product_data.get("description"):
                            product.description = product_data["description"]
                            
                        # Images
                        images = product_data.get("image")
                        if images:
                            if isinstance(images, list) and len(images) > 0:
                                product.image_url = images[0]
                            elif isinstance(images, str):
                                product.image_url = images
                                
                        # Price
                        def format_price(offer_dict):
                            if not offer_dict or not isinstance(offer_dict, dict) or "price" not in offer_dict:
                                return None
                            price_val = str(offer_dict["price"])
                            curr = offer_dict.get("priceCurrency", "")
                            curr_sym = "₹" if curr == "INR" else (f"{curr} " if curr else "")
                            return f"{curr_sym}{price_val}"

                        # Check first variant for ProductGroup
                        if not product.price and "hasVariant" in product_data:
                            variants = product_data["hasVariant"]
                            if variants and isinstance(variants, list) and len(variants) > 0:
                                product.price = format_price(variants[0].get("offers")) or ""
                        
                        # Fallback for standalone Product
                        if not product.price:
                            offers = product_data.get("offers")
                            if isinstance(offers, dict):
                                product.price = format_price(offers) or ""
                            elif isinstance(offers, list) and len(offers) > 0:
                                product.price = format_price(offers[0]) or ""
                    
                    # Construct raw text from DOM accordions
                    raw_text = []
                    if product.name:
                        raw_text.append(f"Name: {product.name}")
                    if details.get("domStyleNumber"):
                        raw_text.append(f"Style Number: {details['domStyleNumber']}")
                    if details.get("domDetails"):
                        raw_text.append(f"Details: {details['domDetails']}")
                    if details.get("domSizeAndFit"):
                        raw_text.append(f"Size & Fit: {details['domSizeAndFit']}")
                    if details.get("domMaterialAndCare"):
                        raw_text.append(f"Material & Care: {details['domMaterialAndCare']}")
                        
                    product.raw_page_text = "\n".join(raw_text)
                    
                except Exception as e:
                    logger.error(f"[{self.retailer_name}] Failed to extract details for {product.art_no}: {e}")

    def capture_product_screenshots(self, products: List[Product]) -> None:
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
