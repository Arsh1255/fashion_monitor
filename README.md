# Fashion Trend Monitor

An automated Python tool that monitors retailer "New Arrivals" (e.g. H&M India), identifies newly listed fashion items, captures screenshots, performs AI visual analysis using NVIDIA NIM, generates a formatted PDF report, and dispatches email notifications.

---

## 🛠️ Project Structure

```
fashion_monitor/
├── src/                      # Source code modules
│   ├── config.py             # Configuration & environment loader
│   ├── models.py             # Data structures (Product, AIAnalysis)
│   ├── scraper.py            # Playwright web scraper & screenshot capture
│   ├── storage.py            # JSON persistence for seen product IDs
│   ├── ai_analyzer.py        # NVIDIA NIM visual AI client
│   ├── reporter.py           # ReportLab PDF report generator
│   ├── email_sender.py       # SMTP email notification sender
│   └── main.py               # Single-run CLI workflow entry point
├── data/                     # Persistent JSON storage (seen_products.json)
├── screenshots/              # Captured product screenshots
├── output/                   # Generated PDF report deliverables
├── logs/                     # Application execution log files
├── tests/                    # Test suite
├── assets/                   # Static assets (templates, logos)
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git exclusion configuration
└── README.md                 # Project documentation
```

---

## 🚀 Setup Instructions

### 1. Create Virtual Environment

#### Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Configuration

Copy the `.env.example` template to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Configure your parameters inside `.env`:
- `NVIDIA_API_KEY`: API key from NVIDIA NIM platform.
- `TARGET_URL`: Retailer listing URL (e.g., `https://www2.hm.com/en_in/men/new-arrivals/view-all.html`).
- `SMTP_USER` & `SMTP_PASSWORD`: SMTP credentials for emailing reports.

---

## 🏃 Execution

Run a single monitoring cycle:

```bash
python -m src.main
```

---

## ⏱️ VPS Scheduling (Cron Example)

To execute once every day at 8:00 AM on a VPS:

```cron
0 8 * * * cd /path/to/fashion_monitor && /path/to/fashion_monitor/venv/bin/python -m src.main >> logs/cron.log 2>&1
```
