# Fashion Trend Monitor — Developer Handoff & Architecture Notes

> [!IMPORTANT]
> Read this before modifying scraper architecture or pipeline limits.

## 1. Critical Rule: Understand Before Refactoring
The current architecture contains deliberate decisions based on extensive investigation of retailer websites. Do not blindly refactor working scraper logic because something appears more elegant or generic. 

## 2. Scraping Architecture — Do Not Blindly Replace DOM Extraction
Retailer scraping logic was developed after detailed DOM analysis.
- Do not assume that clicking accordions, expanding UI elements, or interacting with the visible website UI is the most reliable way to extract product information.
- Where possible, the existing approach of extracting information through DOM/JavaScript injection should be preserved because it is more reliable and less dependent on fragile UI interactions.
- Before changing a scraper, inspect how the current scraper obtains the data and understand why that method was chosen.
- Do not replace existing extraction with generic browser-click automation without verifying the actual underlying DOM/data structure.

## 3. Camoufox / Windows Environment Warning
Operational constraint: Camoufox can be aggressively blocked by Windows Smart App Control.
- Disabling Smart App Control is not a trivial toggle on Windows; re-enabling it may require a clean Windows installation.
- Therefore, avoid casually recommending that developers disable Smart App Control on their primary Windows installation.
- Prefer running Camoufox in a native Linux environment or WSL2, where appropriate.

This is an environment/operational constraint, not something that should be "fixed" by rewriting the scraper.

## 4. Retailer-Specific Identifier Architecture
Important distinction between retailers regarding deduplication:
- **H&M and Zara**: Their current implementations have relatively stable product identification. Multiple regional URLs are deliberately handled. Their product identifiers are sufficiently reliable for the current deduplication architecture.
- **Other retailers**: Do not blindly copy the H&M/Zara identifier strategy to every retailer.
- Some retailers require navigating deeper into product data/pages to obtain a true SKU/article identifier.
- For some retailers, the current implementation deliberately uses URL slugs as unique identifiers because they are more reliable within that retailer's current structure.
- **Note on Variants**: There was a specific duplicate-product problem where the same garment in different colors could appear with different identifiers (including `_1819` style differences in the identifier/string). Solving this properly would require substantial retailer-specific scraping/normalization changes and should not be treated as a simple global deduplication fix.
- **Rule**: Before changing identifiers, understand the retailer's product URL, SKU, variant, and color structure.

## 5. Candidate Pool vs Final Garment Quota
Critical architectural decision:
- `MAX_CANDIDATE_POOL_SIZE` controls how many candidates the scrapers collect from the listing pages.
- `MAX_ITEMS_PER_CATEGORY` controls the number of valid garments ultimately accepted per category.

These are intentionally different limits. The candidate pool exists so deduplication and garment filtering can happen *after* extraction without coupling scrapers to AI/storage logic. 
- Do not revert the architecture to stopping extraction at `MAX_ITEMS_PER_CATEGORY`.
- The final garment quota is evaluated **per category**, not globally across the retailer. A global break after reaching the quota is incorrect because it can cause later categories (for example Women after Men) to disappear from the report entirely.

## 6. Deduplication / seen_products
- Scraped candidates are evaluated against previously seen product IDs.
- Do not casually move when products are marked as seen within the pipeline.
- Be careful when changing failure handling because a product that fails later in the pipeline (e.g., image acquisition or AI analysis) intentionally remains eligible for a future run by not being saved to `seen_products`.

## 7. AI Classification Boundary
AI garment classification is intentionally separated from scraper extraction.
- Scrapers should primarily extract product data.
- AI classification happens in the pipeline *after* candidate collection.
- Do not couple retailer scrapers directly to storage or NVIDIA AI validation unless there is a strong architectural reason.
- Avoid introducing AI into deterministic extraction logic unnecessarily.

## 8. Regional Retailer Behavior
- **H&M and Zara** have meaningful regional handling in the current implementation.
- For other retailers, regional/global URLs were investigated. In particular, **Shein and Boss** did not show meaningful product-catalog differences across their regional/global URLs; those URLs appeared primarily related to telemetry/localization.
- Do not assume every retailer requires the same country-specific scraping implementation. Verify a retailer's actual product behavior before introducing regional branching.

## 9. Production Logging
Current logs are intentionally descriptive and useful during development/debugging, which makes them potentially very verbose.
- At production frequency, logs can accumulate to hundreds of MB over time.
- Production deployment should therefore include log rotation, retention limits, reduced verbosity, or another appropriate log-management strategy.
- Do not simply remove useful diagnostics without considering debugging/operational needs.

## 10. PDF / Output Pipeline
- Generated PDFs, screenshots, runtime state, and logs are local/generated artifacts and should not normally be committed to Git.
- Runtime directories are preserved with `.gitkeep` where required.

## 11. Retailer-Specific Scrapers Are Not Interchangeable
The six retailer scrapers should not be treated as six instances of one generic scraper.
- Their pagination, infinite scrolling, identifiers, regional behavior, DOM structure, and product-detail extraction can differ substantially.
- Shared abstractions should only be introduced when the underlying behavior is genuinely shared.

## 12. Before Making Scraper Changes — Checklist
- [ ] Inspect the current scraper completely.
- [ ] Understand its identifier strategy.
- [ ] Understand listing pagination/infinite-scroll behavior.
- [ ] Understand product-detail extraction.
- [ ] Check regional behavior.
- [ ] Check interaction with `seen_products`.
- [ ] Check candidate-pool/category-quota behavior.
- [ ] Test with real retailer pages before replacing working logic.
- [ ] Prefer localized changes over broad refactors.
- [ ] Verify both Men and Women outputs after pipeline changes.

## 13. Known Historical Problems Already Solved
- **Duplicate handling / seen_products**: Prevented falsely flagging failed products as completed.
- **Candidate-pool architecture**: Separated extraction limits from final validity quotas.
- **Per-category garment quotas**: Prevented one category from exhausting the limit for the entire retailer.
- **Missing Women's report**: Fixed an incorrect global quota break that destroyed subsequent category candidates.
- **Zara/H&M regional handling**: Consolidated overlapping logic for multi-region processing.
- **Retailer-specific identifier differences**: Preserved stable unique identifiers (e.g., URL slugs vs DOM attributes) natively suited to each site.
- **Non-garment filtering**: Combined deterministic keyword filtering with AI validation.
