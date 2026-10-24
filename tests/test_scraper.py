"""
Unit tests for src/scraper.py
"""

from src.scrapers.hm import HMScraper
from src.config import load_config


def make_hm_scraper(config):
    settings = config.retailers["hm"]
    return HMScraper(
        config=config,
        retailer_name=settings["name"],
        region=settings.get("region", "Unknown"),
        categories=settings["categories"],
        retailer_key="hm",
    )


def test_screenshot_cleanup(tmp_path):
    config = load_config()
    # Override screenshot_dir to tmp_path
    object.__setattr__(config, 'screenshot_dir', tmp_path)

    # Create dummy images and gitkeep
    gitkeep = tmp_path / ".gitkeep"
    gitkeep.write_text("keep me")
    img1 = tmp_path / "1001.png"
    img1.write_bytes(b"image1")
    img2 = tmp_path / "1002.jpg"
    img2.write_bytes(b"image2")

    scraper = make_hm_scraper(config)
    assert scraper.max_candidate_pool_size == 12
    assert scraper.max_pages_per_category == 2
    scraper.cleanup_old_screenshots()

    assert gitkeep.exists()
    assert not img1.exists()
    assert not img2.exists()
