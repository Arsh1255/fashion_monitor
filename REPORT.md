# Fashion Trend Monitor: Developer Notes

This file records the architecture decisions that are easy to break during scraper or pipeline changes. Check the relevant retailer module and its current configuration before changing behavior.

## Pipeline contract

The workflow is sequential. Retailer scrapers produce `Product` objects. The main pipeline then handles retailer-specific deduplication, accessory filtering, product details, image acquisition, AI analysis, category reports, email delivery, and seen-product persistence.

Keep the shared `Product` model and `BaseScraper` interface stable when adding a retailer. The PDF renderer, analyzer, storage, and email sender are shared across brands.

## Candidate pool and final quota

These limits serve different purposes:

- `max_candidate_pool_size` limits listing candidates collected before filtering.
- `max_items_per_category` limits accepted garments for one category at one retailer.
- `max_pages_per_category` applies to scrapers that paginate by page number. Scroll-based and retailer-specific listing flows may use their own steps.

The current `retailers.yaml` values are 12 candidates, 2 pages where applicable, and 2 final garments per category and retailer. Retailer settings override the matching environment variable. Do not replace these separate limits with one global stop condition. A retailer's Men quota must not prevent its Women category from being processed.

## Identifiers and deduplication

Seen IDs are stored per retailer in `data/seen_products.json`. Identifier formats differ by site. H&M uses article codes; Zara extracts IDs from product URLs; other scrapers may need a site-specific SKU or URL slug. Color variants can have different IDs, so do not assume one global normalization rule is safe.

Products should only be marked as seen after their category report is generated and email delivery succeeds or is intentionally skipped because SMTP is unconfigured. A PDF or email failure should leave those products eligible for a later run.

## Browser behavior and access blocks

The current scraper flows use Camoufox browser sessions. H&M includes explicit checks for `Access Denied` responses, and its source comments identify Akamai blocking as the reason Camoufox was selected. Camoufox handles browser fingerprint properties at its C++ implementation layer. This is browser-engine code, not an operating-system kernel patch, and it does not guarantee access to a retailer site.

`BaseScraper._simulate_human_behavior` adds a randomized wait, pointer movement, and occasional scrolling. These are project-level browsing behaviors. Retailer scrapers also implement their own lazy loading, pagination, and DOM extraction. Preserve the site-specific approaches unless live page inspection shows they need to change.

Zara has its own listing and detail strategy. It loads lazy content, extracts IDs from product URL patterns, checks `zara.analyticsData`, and reads image and description metadata from the product page. Do not replace it with a generic selector without verifying current Zara markup.

Camoufox may be blocked by Windows Smart App Control. Do not recommend disabling that protection as a routine setup step. Use Linux or WSL2 when the local Windows environment prevents Camoufox from launching.

## AI request behavior and fallbacks

`AIRequestManager` processes visual-analysis items sequentially, adds the configured delay between items, records batch outcomes, and catches unexpected item-level failures. `NvidiaNimAnalyzer` owns rate-limit retries and exponential backoff for visual-analysis requests. Other API errors produce an error analysis for that product.

Garment classification is a separate direct request in `main.py`. If NVIDIA is not configured or classification fails, the classifier defaults to treating the item as a garment. If visual analysis has no API key, it returns default mock analysis. Do not describe all AI calls as sharing the same retry behavior.

For products that go through a fresh visual-analysis call, the analyzer wrapper clears `raw_page_text` after analysis returns. Product objects and analysis results remain available for report generation.

## PDF and generated files

`src/reporter.py` is the shared PDF presentation layer. It creates one PDF per category and builds the cover, contents, retailer sections, product cards, images, and AI visual-analysis blocks. Keep brand-specific extraction out of the report renderer where possible.

At the beginning of a run, the scraper cleanup removes old `.png`, `.jpg`, and `.jpeg` files from the configured image folder. It does not delete generated PDFs, JSON state, or logs. These runtime outputs are ignored by Git. Logs have no built-in rotation, so long-running deployments should set up retention or rotation outside the application.

## Adding a retailer

1. Add the retailer name, logo, enabled flag, category URLs, and optional limits to `retailers.yaml`.
2. Implement its listing, detail, and image methods in a dedicated module under `src/scrapers/`.
3. Register the class in `src/scrapers/__init__.py`.
4. Add unit tests for its configuration and stable product identifier extraction.

The scraper should return the common `Product` model. Existing storage, filtering, analysis, email, and PDF stages can then process it without adding a brand-specific report generator.

## Before changing a scraper

- Inspect the complete retailer module and its current YAML entry.
- Confirm its listing pagination or scrolling behavior.
- Confirm product ID and color-variant behavior.
- Check product-detail extraction and image acquisition separately.
- Preserve the distinction between candidate pool and final garment quota.
- Confirm that both Men and Women categories can reach their own quota.
- Keep failed image, PDF, and email items eligible for retry.
- Run unit tests. Test live retailer pages separately when validating selectors or access behavior.
