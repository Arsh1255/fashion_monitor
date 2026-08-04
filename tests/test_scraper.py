"""
Unit tests for src/scraper.py
"""

from pathlib import Path
from src.scraper import HMScraper
from src.config import load_config


def test_art_no_extraction():
    url = "https://www2.hm.com/en_in/productpage.1344928012.html"
    art_no = HMScraper.extract_art_no_from_url(url)
    assert art_no == "1344928012"

    fallback_url = "https://example.com/items/9876543210/details"
    art_no_fallback = HMScraper.extract_art_no_from_url(fallback_url)
    assert art_no_fallback == "9876543210"


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

    scraper = HMScraper(config)
    scraper.cleanup_old_screenshots()

    assert gitkeep.exists()
    assert not img1.exists()
    assert not img2.exists()
