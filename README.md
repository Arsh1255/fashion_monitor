# Fashion Trend Monitor

Fashion Trend Monitor checks configured retailer new-arrival pages, filters out previously seen items and accessories, analyzes a small set of new garments, and creates polished PDF reports grouped by category. It can email the reports through SMTP.

## Retailers

The current configuration in [`retailers.yaml`](retailers.yaml) enables:

- H&M
- Zara
- Lacoste
- U.S. Polo Assn.
- SHEIN
- HUGO BOSS

Retailers and their category URLs are configured in YAML. H&M and Zara support regional URLs; the other entries currently use their configured India URLs. Set `enabled: false` to skip a retailer.

## How the run works

1. Each enabled retailer scraper collects candidates from its configured category pages using Camoufox.
2. Product IDs are checked against `data/seen_products.json` separately for each retailer.
3. Candidate garments are capped per category and retailer, then product details and images are collected.
4. NVIDIA NIM analyzes the image and scraped product text when an API key is configured.
5. The PDF reporter creates a separate report for each category, with retailer sections and product analysis cards.
6. Reports are emailed when SMTP credentials are configured, and successfully processed product IDs are saved.

The per-retailer limits in `retailers.yaml` are currently **2 garments**, **12 listing candidates**, and **2 pages** per category. This keeps development runs small at both the listing and product-processing stages. Each YAML value overrides its matching environment variable; `MAX_ITEMS_PER_CATEGORY`, `MAX_CANDIDATE_POOL_SIZE`, and `MAX_PAGES_PER_CATEGORY` provide fallbacks for retailers without individual limits.

## Requirements

- Python 3.10 or newer
- A Camoufox browser build
- NVIDIA NIM API key for live AI analysis (optional; without one, the analyzer returns its built-in default analysis)
- SMTP account for email delivery (optional)

## Setup

### Windows PowerShell

```powershell
cd D:\fashion_monitor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m camoufox fetch
Copy-Item .env.example .env
```

### Linux or macOS

```bash
cd /path/to/fashion_monitor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m camoufox fetch
cp .env.example .env
```

Edit `.env` with your credentials and runtime settings. Camoufox uses its own browser build; `python -m camoufox fetch` downloads it after the Python package is installed. On Windows, Smart App Control may block Camoufox; the operational notes in [`REPORT.md`](REPORT.md) describe using Linux or WSL2 in that case.

## Configuration

### `retailers.yaml`

Each retailer entry controls whether it is active, its display name, logo, category URLs, and optional `max_items_per_category`, `max_candidate_pool_size`, and `max_pages_per_category` limits. Category URLs may be a single URL or a map of region names to URLs.

### `.env`

| Variable | Purpose | Default in `.env.example` |
|---|---|---|
| `NVIDIA_API_KEY` | NVIDIA NIM API key; leave empty to use default analysis | Placeholder |
| `NVIDIA_NIM_MODEL` | Vision model name | `meta/llama-3.2-11b-vision-instruct` |
| `NVIDIA_BASE_URL` | NVIDIA API endpoint | `https://integrate.api.nvidia.com/v1` |
| `AI_MAX_RETRIES` | AI request retry limit | `4` |
| `AI_REQUEST_DELAY` | Delay between AI requests, in seconds | `1.5` |
| `HEADLESS` | Run browser without a visible window | `true` |
| `MAX_PAGES_PER_CATEGORY` | Fallback maximum listing pages per category | `2` |
| `MAX_ITEMS_PER_CATEGORY` | Fallback final garment limit per category and retailer | `2` |
| `MAX_CANDIDATE_POOL_SIZE` | Fallback listing candidates collected per category | `12` |
| `NAV_TIMEOUT` | Navigation timeout, in milliseconds | `45000` |
| `SMTP_SERVER`, `SMTP_PORT` | SMTP host and port | Gmail, `587` |
| `SMTP_USER`, `SMTP_PASSWORD` | SMTP login | Placeholder |
| `NOTIFICATION_EMAIL` | Report recipient | Placeholder |
| `STORAGE_PATH` | Seen-product JSON path | `data/seen_products.json` |
| `OUTPUT_PATH` | PDF output path (reports use its parent folder) | `output/report.pdf` |
| `SCREENSHOT_DIR` | Downloaded product image directory | `screenshots` |
| `LOG_FILE` | Application log path | `logs/app.log` |

Relative paths are resolved from the project directory. Runtime folders are created automatically.

## Run

With the virtual environment active and `.env` configured:

```bash
python -m src.main
```

The application writes category PDFs under `output/`, product images under `screenshots/`, run logs under `logs/`, and retailer-specific deduplication state to `data/seen_products.json`. These runtime artifacts are ignored by Git.

## Tests

Install the project requirements, then run:

```bash
python -m pytest
```

Tests use temporary paths and do not visit retailer sites or call NVIDIA NIM.

## Project layout

```text
fashion_monitor/
├── assets/                 # PDF logos, backgrounds, icons, and fonts
├── data/                   # Persistent seen-product state
├── logs/                   # Runtime logs
├── output/                 # Generated category reports
├── screenshots/            # Downloaded product images for the current run
├── src/
│   ├── scrapers/            # Retailer-specific Camoufox scrapers
│   ├── ai_analyzer.py       # NVIDIA NIM visual and text analysis
│   ├── config.py            # Environment and YAML configuration
│   ├── email_sender.py      # SMTP report delivery
│   ├── main.py              # Monitoring workflow
│   ├── models.py            # Product and analysis data models
│   ├── reporter.py          # PDF report generation
│   └── storage.py           # Per-retailer seen-product storage
├── tests/                   # Unit tests
├── .env.example             # Environment template
├── retailers.yaml           # Retailer URLs and per-retailer limits
└── requirements.txt         # Python dependencies
```
