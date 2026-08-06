"""
Main CLI entry point for Fashion Trend Monitor.

Orchestrates a single execution monitoring cycle:
1. Loads environment configuration.
2. Cleans up old temporary screenshots to save disk space.
3. Scrapes target retailer listing pages across categories (Men, Ladies, Kids).
4. Filters against persistent JSON state (data/seen_products.json).
5. Captures high-res product detail photos for new items only.
6. Performs visual fashion AI analysis using NVIDIA NIM.
7. Generates separate PDF reports per category (e.g. report_2026-08-01_Men.pdf).
8. Dispatches email notification with attached category PDFs.
9. Updates persistent state with newly processed product IDs.
"""

import sys
import logging
from pathlib import Path

from src.config import load_config
from src.storage import JSONStorage
from src.scrapers import get_scrapers
from src.ai_analyzer import NvidiaNimAnalyzer
from src.reporter import PDFReporter
from src.email_sender import EmailSender


def setup_logging(log_file: Path) -> None:
    """Configure system logging for console stdout and file output."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def main() -> int:
    """Execute single monitoring cycle across all categories."""
    config = load_config()
    setup_logging(config.log_file)

    logger = logging.getLogger("main")
    logger.info("=" * 60)
    logger.info("Starting Fashion Trend Monitor execution cycle...")
    active_retailers = [s.get("name", k) for k, s in config.retailers.items() if s.get("enabled")]
    logger.info(f"Active Retailers: {', '.join(active_retailers)}")
    logger.info("=" * 60)

    try:
        # Step 1: Initialize Storage & Scraper
        storage = JSONStorage(config.storage_path)
        logger.info("Initialized JSON Storage.")

        scrapers = get_scrapers(config)
        
        # Step 2: Clean up old temporary screenshots from previous runs
        if scrapers:
            scrapers[0].cleanup_old_screenshots()

        master_product_dict = {"Men": {}, "Women": {}}
        all_new_products = []
        
        for scraper in scrapers:
            try:
                logger.info(f"--- Processing Retailer: {scraper.retailer_name} ---")
                
                # Step 3: Scrape New Arrivals listing pages
                scraped_products = scraper.fetch_new_arrivals()
                logger.info(f"[{scraper.retailer_name}] Scraped total {len(scraped_products)} items.")
    
                # Step 4: Deduplicate against seen storage
                unseen_products = storage.filter_unseen(scraper.retailer_key, scraped_products)
                logger.info(f"[{scraper.retailer_name}] Identified {len(unseen_products)} NEW unseen products.")
    
                if not unseen_products:
                    continue
    
                # Step 4b: Pre-Filter out accessories (bags, watches, etc.)
                logger.info(f"[{scraper.retailer_name}] Filtering out non-garment accessories...")
                analyzer = NvidiaNimAnalyzer(config)
                valid_unseen = []
                for p in unseen_products:
                    # Check deterministic indicators in URL or name first
                    url_lower = (p.product_url or "").lower()
                    name_lower = (p.name or "").lower()
                    accessory_keywords = ["watch", "perfume", "fragrance", "sunglasses", "bag", "wallet", "belt", "shoes", "sneakers"]
                    if any(kw in url_lower.split("/") or kw in name_lower.split() for kw in accessory_keywords):
                        continue
                    # AI Fallback
                    if not analyzer.is_garment_product(p):
                        continue
                    valid_unseen.append(p)
    
                unseen_products = valid_unseen
                if not unseen_products:
                    logger.info(f"[{scraper.retailer_name}] No garments found after filtering accessories.")
                    continue
    
                # Step 5: Scrape product detail pages via Camoufox
                logger.info(f"[{scraper.retailer_name}] Scraping product detail pages via Camoufox...")
                scraper.scrape_product_details_batch(unseen_products)
    
                # Step 6: Capture high-res product photos for NEW products only
                logger.info(f"[{scraper.retailer_name}] Acquiring high-resolution product photos...")
                scraper.capture_product_screenshots(unseen_products)
    
                # Filter out products that failed to download an image
                valid_products = []
                for p in unseen_products:
                    if p.screenshot_path and Path(p.screenshot_path).exists():
                        valid_products.append(p)
                    else:
                        logger.warning(f"[{scraper.retailer_name}] Discarding {p.art_no} ({p.name}) due to missing/crashed image.")
                
                all_new_products.extend(valid_products)
                
                # Step 7: Perform NVIDIA NIM visual AI analysis (Incremental)
                logger.info(f"[{scraper.retailer_name}] Performing NVIDIA NIM visual AI analysis on {len(valid_products)} items...")
                analyzer = NvidiaNimAnalyzer(config)
                valid_products = analyzer.analyze_products(valid_products)
                
                # Group by category -> retailer
                for p in valid_products:
                    if p.category not in master_product_dict:
                        master_product_dict[p.category] = {}
                    if scraper.retailer_name not in master_product_dict[p.category]:
                        master_product_dict[p.category][scraper.retailer_name] = []
                    master_product_dict[p.category][scraper.retailer_name].append(p)
                    
            except Exception as e:
                logger.error(f"[{scraper.retailer_name}] Pipeline crashed for retailer: {e}", exc_info=True)
                continue

        if not all_new_products:
            logger.info("No valid new products across any retailer. Workflow complete.")
            logger.info("=" * 60)
            return 0

        # Step 8: Generate Separate PDF Reports Per Category
        logger.info("Generating separate PDF reports per category...")
        reporter = PDFReporter(config)
        
        # Add basic try/except per category at PDF generation level
        category_pdf_paths = {}
        for cat_name, retailers_dict in master_product_dict.items():
            if not retailers_dict: continue
            try:
                # We dynamically create a single-category dict just for this generation
                single_cat_dict = {cat_name: retailers_dict}
                pdf_path = reporter.generate_all_reports(single_cat_dict).get(cat_name)
                if pdf_path:
                    category_pdf_paths[cat_name] = pdf_path
            except Exception as e:
                logger.error(f"Failed to generate PDF for category {cat_name}: {e}", exc_info=True)
                
        for cat_name, pdf_path in category_pdf_paths.items():
            logger.info(f"Created category PDF [{cat_name}]: {pdf_path}")

        # Step 8: Dispatch Email Notification with attachments
        logger.info("Sending email notification with category PDF reports...")
        email_sender = EmailSender(config)
        email_sender.send_report_email(category_pdf_paths, len(all_new_products))

        # Step 10: Update persistent state only after successful processing
        for category, retailers in master_product_dict.items():
            for retailer_name, products in retailers.items():
                if not products: continue
                scraper = next((s for s in scrapers if s.retailer_name == retailer_name), None)
                if scraper:
                    new_ids = [p.art_no for p in products]
                    storage.save_seen_ids(scraper.retailer_key, new_ids)
                    logger.info(f"Saved {len(new_ids)} new product IDs to persistent storage for {retailer_name} ({category}).")

        logger.info("=" * 60)
        logger.info("Fashion Trend Monitor cycle completed successfully.")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.critical(f"Unhandled exception during execution cycle: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
