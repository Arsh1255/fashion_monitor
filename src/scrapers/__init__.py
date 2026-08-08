from typing import List

from src.config import Config
from src.scrapers.base import BaseScraper
from src.scrapers.hm import HMScraper
from src.scrapers.zara import ZaraScraper
from src.scrapers.lacoste import LacosteScraper
from src.scrapers.us_polo import UsPoloScraper
from src.scrapers.shein import SheinScraper
from src.scrapers.hugo_boss import HugoBossScraper

__all__ = [
    "BaseScraper",
    "HMScraper",
    "ZaraScraper",
    "LacosteScraper",
    "UsPoloScraper",
    "SheinScraper",
    "HugoBossScraper"
]

SCRAPERS = {
    "hm": HMScraper,
    "zara": ZaraScraper,
    "lacoste": LacosteScraper,
    "us_polo": UsPoloScraper,
    "shein": SheinScraper,
    "boss": HugoBossScraper
}

def get_scrapers(config: Config) -> List[BaseScraper]:
    """
    Factory function to read the retailers dictionary from Config and return
    instantiated scraper objects for all enabled retailers.
    """
    scrapers = []
    
    mapping = {
        "hm": HMScraper,
        "lacoste": LacosteScraper,
        "us_polo": UsPoloScraper,
        "shein": SheinScraper,
        "boss": HugoBossScraper,
        "zara": ZaraScraper
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
