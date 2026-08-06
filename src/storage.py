"""
Persistence storage module for Fashion Trend Monitor.

Handles JSON storage of previously seen product IDs (Art. No.)
to ensure duplicate products are not processed or reported across runs.
"""

import json
from pathlib import Path
from typing import List, Set, Iterable
from src.models import Product


class JSONStorage:
    """Manages persistent JSON state file for seen product identifiers."""

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)

    def _ensure_file_exists(self) -> None:
        """Create empty JSON dict file if it does not exist."""
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_seen_ids(self, retailer_key: str) -> Set[str]:
        """
        Read seen product IDs for a specific retailer from the JSON file.

        Returns:
            Set of seen string Art. No. identifiers.
        """
        self._ensure_file_exists()
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    retailer_data = data.get(retailer_key, [])
                    if isinstance(retailer_data, list):
                        return {str(item) for item in retailer_data}
                return set()
        except (json.JSONDecodeError, OSError):
            return set()

    def filter_unseen(self, retailer_key: str, products: List[Product]) -> List[Product]:
        """
        Filter a list of products, returning only those not present in seen storage for the retailer.

        Args:
            retailer_key: The string key of the retailer.
            products: List of Product dataclass instances.

        Returns:
            List of unseen Product dataclass instances.
        """
        seen_ids = self.get_seen_ids(retailer_key)
        return [p for p in products if p.art_no not in seen_ids]

    def save_seen_ids(self, retailer_key: str, new_ids: Iterable[str]) -> None:
        """
        Atomically add new product IDs for a specific retailer to the persistent JSON storage.

        Args:
            retailer_key: The string key of the retailer.
            new_ids: Iterable of new string Art. No. identifiers.
        """
        self._ensure_file_exists()
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
        except (json.JSONDecodeError, OSError):
            data = {}

        current_seen = self.get_seen_ids(retailer_key)
        updated_seen = sorted(list(current_seen.union({str(i) for i in new_ids})))
        data[retailer_key] = updated_seen

        temp_path = self.storage_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        temp_path.replace(self.storage_path)

    def clear(self) -> None:
        """Clear storage file for testing purposes."""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
