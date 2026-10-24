"""
Unit tests for src/ai_analyzer.py
"""

from pathlib import Path
from src.ai_analyzer import NvidiaNimAnalyzer
from src.config import load_config
from src.models import Product, AIAnalysis


def test_ai_analyzer_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("NVIDIA_API_KEY=\n", encoding="utf-8")
    config = load_config(env_file)
    analyzer = NvidiaNimAnalyzer(config)

    # Test product without screenshot
    p_no_img = Product(art_no="1001", name="Shirt", price="999", product_url="http://a.com", image_url="http://a.jpg")
    res1 = analyzer.analyze_product(p_no_img)
    assert "No screenshot" in res1.summary

    # Test product with mock screenshot image
    dummy_img = tmp_path / "1002.png"
    dummy_img.write_bytes(b"fake_png_data")
    p_with_img = Product(
        art_no="1002",
        name="Shirt",
        price="999",
        product_url="http://a.com",
        image_url="http://a.jpg",
        screenshot_path=str(dummy_img)
    )

    res2 = analyzer.analyze_product(p_with_img)
    assert isinstance(res2, AIAnalysis)
    assert res2.fabric_info != ""
