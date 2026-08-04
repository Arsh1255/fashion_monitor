# Project Specification - Fashion Trend Monitor

## Requirements Overview

1. **Scraping**: Visit retailer listing page (H&M India New Arrivals), extract basic metadata (`art_no`, title, price, product URL).
2. **Deduplication**: Compare extracted `art_no` identifiers against persistent JSON state (`data/seen_products.json`). Filter out seen products.
3. **Selective Screenshots**: Open product detail pages **only** for unseen products and capture a high-resolution screenshot into `screenshots/`.
4. **AI Visual Analysis**: Send each screenshot image to NVIDIA NIM (`meta/llama-3.2-11b-vision-instruct`) to extract fabric, pattern, and textile details.
5. **PDF Report Generation**: Generate `output/report.pdf` using ReportLab, presenting unseen products, images, and AI findings.
6. **Email Delivery**: Send email via SMTP attaching `output/report.pdf`.
7. **State Persistence**: Only after successful report generation & emailing, write new `art_no` identifiers to `data/seen_products.json`.
