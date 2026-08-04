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
from src.scraper import HMScraper
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
    categories_str = ", ".join([cat for cat, _ in config.target_urls])
    logger.info(f"Target Categories: {categories_str}")
    logger.info("=" * 60)

    try:
        # Step 1: Initialize Storage & Scraper
        storage = JSONStorage(config.storage_path)
        seen_count = len(storage.get_seen_ids())
        logger.info(f"Loaded {seen_count} previously seen product IDs from storage.")

        scraper = HMScraper(config)
        
        # Step 2: Clean up old temporary screenshots from previous runs
        scraper.cleanup_old_screenshots()

        # Step 3: Scrape New Arrivals listing pages (Playwright Chromium)
        scraped_products = scraper.fetch_new_arrivals()
        logger.info(f"Scraped total {len(scraped_products)} items across all categories.")

        # Step 4: Deduplicate against seen storage
        unseen_products = storage.filter_unseen(scraped_products)
        logger.info(f"Identified {len(unseen_products)} NEW unseen products.")

        if not unseen_products:
            logger.info("No new products detected during this run. Workflow complete.")
            logger.info("=" * 60)
            return 0

        # Step 5: Scrape product detail pages via Camoufox (Firefox) to bypass Akamai WAF
        logger.info("Scraping product detail pages via Camoufox (Firefox)...")
        scraper.scrape_product_details_batch(unseen_products)

        # Step 6: Capture high-res product photos for NEW products only
        logger.info("Acquiring high-resolution product photos for new products...")
        scraper.capture_product_screenshots(unseen_products)

        # Filter out products that failed to download an image
        valid_products = []
        for p in unseen_products:
            if p.screenshot_path and Path(p.screenshot_path).exists():
                valid_products.append(p)
            else:
                logger.warning(f"Discarding {p.art_no} ({p.name}) due to missing/crashed image.")
        unseen_products = valid_products

        if not unseen_products:
            logger.info("No valid products remaining after image acquisition. Workflow complete.")
            logger.info("=" * 60)
            return 0

        # Step 7: Perform NVIDIA NIM visual AI analysis
        logger.info("Performing NVIDIA NIM visual AI analysis...")
        analyzer = NvidiaNimAnalyzer(config)
        analyzer.analyze_products(unseen_products)

        # Step 7: Generate Separate PDF Reports Per Category
        logger.info("Generating separate PDF reports per category...")
        reporter = PDFReporter(config)
        category_pdf_paths = reporter.generate_all_reports(unseen_products)
        for cat_name, pdf_path in category_pdf_paths.items():
            logger.info(f"Created category PDF [{cat_name}]: {pdf_path}")

        # Step 8: Dispatch Email Notification with attachments
        logger.info("Sending email notification with category PDF reports...")
        email_sender = EmailSender(config)
        email_sender.send_report_email(category_pdf_paths, len(unseen_products))

        # Step 9: Update persistent state only after successful processing
        new_ids = [p.art_no for p in unseen_products]
        storage.save_seen_ids(new_ids)
        logger.info(f"Saved {len(new_ids)} new product IDs to persistent storage.")

        logger.info("=" * 60)
        logger.info("Fashion Trend Monitor cycle completed successfully.")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.critical(f"Unhandled exception during execution cycle: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
