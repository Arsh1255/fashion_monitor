from abc import ABC, abstractmethod
from typing import List, Optional
import logging
from pathlib import Path

from src.config import Config
from src.models import Product

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all retailer scrapers."""

    def __init__(self, config: Config, retailer_name: str, region: str, categories: dict):
        self.config = config
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
            if file_path.is_file() and file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete old screenshot {file_path}: {e}")
        logger.info(f"Cleaned up {deleted_count} old screenshot files from {self.screenshot_dir}.")
        return deleted_count

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
