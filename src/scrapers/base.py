from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Union, Dict
import logging
from pathlib import Path

from src.config import Config
from src.models import Product

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all retailer scrapers."""

    def __init__(
        self,
        config: Config,
        retailer_name: str,
        region: str,
        categories: dict,
        retailer_key: str,
    ):
        self.config = config
        self.retailer_key = retailer_key
        self.retailer_name = retailer_name
        self.region = region
        self.categories = categories
        self.screenshot_dir = config.screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_old_screenshots(self) -> int:
        """Delete previous run image files from the screenshots directory."""
        deleted_count = 0
        if not self.screenshot_dir.exists():
            return 0
        for file_path in self.screenshot_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in [
                ".png",
                ".jpg",
                ".jpeg",
            ]:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete old screenshot {file_path}: {e}")
        logger.info(
            f"Cleaned up {deleted_count} old screenshot files from {self.screenshot_dir}."
        )
        return deleted_count

    def _simulate_human_behavior(self, page) -> None:
        """Simulate human-like delays, scrolling, and mouse movements to bypass WAF."""
        import random
        import time

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

    def get_category_urls(self) -> List[Tuple[str, str, str]]:
        """
        Normalize categories dict into a flat list of (category_name, region_name, target_url).
        Supports both legacy flat strings and nested regional dictionaries.
        """
        results = []
        for cat_name, val in self.categories.items():
            if isinstance(val, dict):
                for region_name, url in val.items():
                    results.append((cat_name, region_name, url))
            elif isinstance(val, str):
                results.append((cat_name, getattr(self, "region", "Unknown"), val))
        return results

    @abstractmethod
    def fetch_new_arrivals(self) -> List[Product]:
        """Scrape new arrival listings across all configured category target URLs."""
        pass

    @abstractmethod
    def scrape_product_details_batch(self, products: List[Product]) -> None:
        """Scrape detail pages for a batch of products to enrich their raw_page_text."""
        pass

    @abstractmethod
    def capture_product_screenshots(self, products: List[Product]) -> None:
        """Download high-resolution studio photos for a batch of products."""
        pass
