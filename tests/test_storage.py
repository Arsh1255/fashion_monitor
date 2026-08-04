"""
Unit tests for src/storage.py
"""

from src.storage import JSONStorage
from src.models import Product


def test_storage_filter_and_save(tmp_path):
    storage_file = tmp_path / "seen_products.json"
    storage = JSONStorage(storage_file)

    p1 = Product(art_no="1001", name="Shirt A", price="999", product_url="http://a.com", image_url="http://a.jpg")
    p2 = Product(art_no="1002", name="Shirt B", price="1499", product_url="http://b.com", image_url="http://b.jpg")

    # Initially both are unseen
    unseen = storage.filter_unseen([p1, p2])
    assert len(unseen) == 2

    # Save p1
    storage.save_seen_ids([p1.art_no])

    # Now only p2 is unseen
    unseen_after = storage.filter_unseen([p1, p2])
    assert len(unseen_after) == 1
    assert unseen_after[0].art_no == "1002"

    # Verify persistent state file contents
    assert "1001" in storage.get_seen_ids()
    assert "1002" not in storage.get_seen_ids()
