"""
Unit tests for PDF reporter module src/reporter.py
"""

from pathlib import Path
from dataclasses import replace
from src.config import load_config
from src.models import Product, AIAnalysis
from src.reporter import PDFReporter


def test_pdf_category_report_generation(tmp_path):
    config = replace(load_config(), output_path=tmp_path / "report.pdf")

    sample_product = Product(
        name="Linen Blend Shirt",
        price="Rs. 1,499.00",
        product_url="https://www2.hm.com/en_in/productpage.1234567890.html",
        art_no="1234567890",
        image_url="https://image.hm.com/sample.jpg",
        category="Men",
        screenshot_path=None,
        ai_analysis=AIAnalysis(
            fabric_info="100% Linen",
            pattern_info="Solid Off-White",
            textile_info="Woven Linen Blend",
            summary="Lightweight summer shirt."
        )
    )

    reporter = PDFReporter(config)
    pdf_path = reporter.generate_category_report({"H&M": [sample_product]}, "Men")

    assert pdf_path.exists()
    assert "Men" in pdf_path.name
    assert pdf_path.stat().st_size > 0


def test_generate_all_reports(tmp_path):
    config = replace(load_config(), output_path=tmp_path / "report.pdf")

    p_men = Product(name="Men Shirt", price="Rs. 999", product_url="http://example.com/1", art_no="001", image_url="http://example.com/1.jpg", category="Men")
    p_women = Product(name="Women Dress", price="Rs. 1999", product_url="http://example.com/2", art_no="002", image_url="http://example.com/2.jpg", category="Women")

    reporter = PDFReporter(config)
    paths_dict = reporter.generate_all_reports(
        {"Men": {"H&M": [p_men]}, "Women": {"H&M": [p_women]}}
    )

    assert "Men" in paths_dict
    assert "Women" in paths_dict
    assert paths_dict["Men"].exists()
    assert paths_dict["Women"].exists()
