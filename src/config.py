"""
Configuration manager module for Fashion Trend Monitor.

Loads environment variables using python-dotenv, validates mandatory options,
and exposes a clean frozen Config object for the application.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SECTIONS = [
    ("Men", "https://www2.hm.com/en_in/men/new-arrivals/view-all.html"),
    ("Women", "https://www2.hm.com/en_in/ladies/new-arrivals/view-all.html"),
    ("Kids", "https://www2.hm.com/en_in/kids/new-arrivals/view-all.html"),
]


@dataclass(frozen=True)
class Config:
    """Immutable application configuration dataclass."""

    # NVIDIA NIM AI Settings
    nvidia_api_key: str
    nvidia_nim_model: str
    nvidia_base_url: str
    ai_max_retries: int
    ai_request_delay: float

    # Scraper Settings
    # Scraper Settings
    retailers: dict  # Loaded from retailers.yaml
    headless: bool
    max_pages_per_category: int
    max_items_per_category: int
    nav_timeout: int

    # SMTP Settings
    smtp_server: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    notification_email: str

    # Storage and Output Paths
    storage_path: Path
    output_path: Path
    screenshot_dir: Path
    log_file: Path

    def ensure_directories(self) -> None:
        """Create required output, screenshot, data, and log directories if they don't exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)


def load_config(env_path: Optional[Path] = None) -> Config:
    """
    Load environment variables from a .env file and return a validated Config instance.

    Args:
        env_path: Optional path to .env file. Defaults to PROJECT_ROOT / '.env'.
    """
    target_env = env_path or (PROJECT_ROOT / ".env")
    if target_env.exists():
        load_dotenv(dotenv_path=target_env, override=True)
    else:
        load_dotenv()

    def resolve_path(env_key: str, default_relative: str) -> Path:
        raw_path = os.getenv(env_key, default_relative)
        path = Path(raw_path)
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    # Parse retailers.yaml
    import yaml
    retailers_path = PROJECT_ROOT / "retailers.yaml"
    retailers_config = {}
    if retailers_path.exists():
        with open(retailers_path, "r", encoding="utf-8") as f:
            retailers_config = yaml.safe_load(f) or {}

    config = Config(
        nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
        nvidia_nim_model=os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.2-11b-vision-instruct"),
        nvidia_base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        ai_max_retries=int(os.getenv("AI_MAX_RETRIES", "4")),
        ai_request_delay=float(os.getenv("AI_REQUEST_DELAY", "1.5")),
        retailers=retailers_config,
        headless=os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes"),
        max_pages_per_category=int(os.getenv("MAX_PAGES_PER_CATEGORY", "3")),
        max_items_per_category=int(os.getenv("MAX_ITEMS_PER_CATEGORY", "100")),
        nav_timeout=int(os.getenv("NAV_TIMEOUT", "45000")),
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        notification_email=os.getenv("NOTIFICATION_EMAIL", ""),
        storage_path=resolve_path("STORAGE_PATH", "data/seen_products.json"),
        output_path=resolve_path("OUTPUT_PATH", "output/report.pdf"),
        screenshot_dir=resolve_path("SCREENSHOT_DIR", "screenshots"),
        log_file=resolve_path("LOG_FILE", "logs/app.log"),
    )

    config.ensure_directories()
    return config