from typing import List

from src.config import Config
from src.scrapers.base import BaseScraper
from src.scrapers.hm import HMScraper
from src.scrapers.zara import ZaraScraper
from src.scrapers.lacoste import LacosteScraper

def get_scrapers(config: Config) -> List[BaseScraper]:
    """
    Factory function to read the retailers dictionary from Config and return
    instantiated scraper objects for all enabled retailers.
    """
    scrapers = []
    
    mapping = {
        "hm_india": HMScraper,
        "hm_us": HMScraper,
        "zara": ZaraScraper,
        "lacoste": LacosteScraper
    }
    
    for key, settings in config.retailers.items():
        if settings.get("enabled", False):
            scraper_cls = mapping.get(key)
            if scraper_cls:
                scraper = scraper_cls(
                    config=config,
                    retailer_name=settings.get("name", key.capitalize()),
                    region=settings.get("region", "Unknown"),
                    categories=settings.get("categories", {}),
                    retailer_key=key
                )
                scrapers.append(scraper)
                
    return scrapers
