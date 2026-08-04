"""
Unit tests for src/config.py and src/models.py
"""

from pathlib import Path
from src.config import load_config, Config
from src.models import Product, AIAnalysis


def test_models_serialization():
    ai = AIAnalysis(
        fabric_info="100% Cotton",
        pattern_info="Solid Red",
        textile_info="Jersey knit",
        summary="Classic red cotton t-shirt"
    )
    product = Product(
        art_no="1344928012",
        name="Relaxed Fit Printed T-shirt",
        price="Rs.999.00",
        product_url="https://www2.hm.com/en_in/productpage.1344928012.html",
        image_url="https://example.com/image.jpg",
        category="Men",
        screenshot_path="screenshots/1344928012.png",
        ai_analysis=ai
    )

    data = product.to_dict()
    assert data["art_no"] == "1344928012"
    assert data["ai_analysis"]["fabric_info"] == "100% Cotton"

    reconstructed = Product.from_dict(data)
    assert reconstructed.art_no == "1344928012"
    assert reconstructed.ai_analysis is not None
    assert reconstructed.ai_analysis.fabric_info == "100% Cotton"


def test_config_loader(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NVIDIA_API_KEY=test-api-key\n"
        "TARGET_URL=https://example.com/men\n"
        "HEADLESS=false\n"
    )

    cfg = load_config(env_file)
    assert cfg.nvidia_api_key == "test-api-key"
    assert len(cfg.target_urls) > 0
    assert cfg.headless is False
    assert isinstance(cfg.storage_path, Path)
