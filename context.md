# Fashion Trend Monitor (Trial Project)

## Overview

This project is a Python-based automation tool that monitors the "New Arrivals" section of a fashion retailer's website.

The application is intended to run once per execution. During each run, it detects newly listed products, analyzes them using NVIDIA NIM, generates a PDF report, and emails the report to a configured recipient.

The application will be scheduled externally (for example, using cron or a systemd timer on a VPS). The application itself must not contain any scheduling logic or infinite loops.

---

# Project Goal

Create a maintainable, modular, and configurable application that performs the following workflow:

1. Open the retailer's "New Arrivals" page.
2. Extract product information.
3. Compare products against previously seen products.
4. Detect products that are newly added.
5. Capture screenshots of newly added products.
6. Analyze those products using NVIDIA NIM.
7. Generate a PDF report summarizing the findings.
8. Email the report.
9. Persist product metadata for future executions.

---

# Confirmed Functional Requirements

The following requirements are considered confirmed.

## Scraping

The application must:

- Visit the retailer's "New Arrivals" page.
- Extract available product information.
- Identify each product using a stable identifier if one exists.
- If no stable identifier exists, another deterministic strategy may be required.

The exact retailer and page URL will be configured separately.

---

## New Product Detection

The application must determine which products are newly listed since the previous execution.

Previously seen products must not be reported again.

The application therefore requires persistent storage of product metadata between runs.

---

## Screenshots

For every newly detected product:

- Capture a screenshot.
- The screenshot will later be used for AI analysis.
- The screenshot may also be included in the PDF report.

Temporary screenshots may be deleted after successful report generation unless future requirements specify archival.

---

## AI Analysis

Each newly detected product should be analyzed using NVIDIA NIM.

The primary analysis required for this project includes:

- Fabric information
- Design/Pattern information
- Textile information

Additional attributes may be included if supported by the selected NVIDIA NIM model, but the implementation should not assume any specific response schema beyond the confirmed requirements.


## PDF Report

Generate a PDF containing the newly detected products.

The report should include the information returned by the AI analysis.

Exact report formatting is not currently specified and may evolve later.

---

## Email

Email the generated PDF after report creation.

SMTP is assumed as the default implementation unless another email service is requested.

Email credentials must never be hardcoded.

---

## Configuration

Configuration values should come from environment variables.

Examples include:

- Email credentials
- NVIDIA API key
- Retailer URL
- Output directories

No secrets should exist inside the source code.

---

## Execution

Each execution should perform exactly one complete monitoring cycle.

The application should then terminate.

Scheduling is intentionally outside the scope of this project.

---

# Non-Functional Requirements

The project should prioritize:

- Readability
- Maintainability
- Modular design
- Ease of extension
- Clear separation of responsibilities
- Proper error handling
- Logging where appropriate

The project should avoid unnecessary complexity.

---

# Proposed Architecture

The application should be organized into independent modules.

Each module should have a single responsibility.

Example responsibilities include:

- Scraping
- Storage
- AI communication
- Report generation
- Email sending
- Configuration management

Implementation details may evolve during development.

---

# Data Persistence

The application requires persistent storage so that future executions can identify new products.

For the trial project, JSON storage is considered sufficient.

A database is intentionally deferred unless project requirements expand.

The storage format should be designed so that replacing JSON with a database later requires minimal code changes.

---

# Product Identity

Each product should be represented by a stable identifier whenever possible.

If the retailer exposes a product ID, that should be preferred over URLs because URLs may change while product identity remains constant.

Additional metadata may also be stored to simplify future extensions.

Possible metadata includes:

- Product ID
- Product name
- Product URL
- First detected timestamp
- Last checked timestamp

The exact schema may evolve during implementation.

---

# Error Handling

Failures should be handled gracefully.

Examples include:

- Website unavailable
- AI request failure
- Email failure
- Screenshot failure
- PDF generation failure

Meaningful log messages should be produced whenever practical.

---

# Security

The project must follow basic security practices.

This includes:

- No hardcoded API keys.
- No hardcoded passwords.
- No committing secrets to version control.
- Use environment variables for sensitive configuration.

---

# Out of Scope

The following items are intentionally excluded unless future requirements change.

- Continuous monitoring
- Internal scheduling
- Multiple retailers
- Database integration
- User interface
- Authentication system
- Dashboard
- Machine learning model training

---

# Expected Development Approach

Development should proceed incrementally.

Each component should be completed and verified before moving to the next.

Recommended order:

1. Project setup
2. Configuration
3. Scraper
4. Persistent storage
5. New product detection
6. Screenshot capture
7. NVIDIA NIM integration
8. PDF generation
9. Email delivery
10. Final integration and testing

Each step should be functional before beginning the next.

---

# Important Notes for AI Coding Agents

When generating code:

- Do not invent project requirements.
- Do not assume unavailable APIs.
- Keep modules loosely coupled.
- Prefer composition over tightly coupled code.
- Keep functions focused on a single responsibility.
- Avoid unnecessary abstractions.
- Prefer clarity over cleverness.
- Write production-quality, readable Python code.
- Follow modern Python best practices.
- Keep the project easy to test and extend.

If a requirement is ambiguous, leave a clear TODO or request clarification instead of making unsupported assumptions.

---

# Implementation Recommendations (Non-Requirements)

The following recommendations are implementation suggestions intended to improve maintainability and reliability. They are not confirmed project requirements and may be adjusted if future requirements change.

## Preserve Product Context Throughout the Pipeline

Each product should be represented by a single object (or equivalent data structure) throughout the entire workflow.

Rather than maintaining separate lists for products, screenshots, and AI results, keep all information associated with the same product instance.

Example conceptual flow:

Product
→ Screenshot Captured
→ AI Analysis Attached
→ Included in PDF
→ Included in Email Report

This minimizes the possibility of mismatching AI analysis with the wrong product.

---

## Avoid Depending on Response Order

The application should not assume that an external AI service will always return results in the same order as requests unless this behavior is explicitly documented by the API.

When practical, process each product independently so that the returned AI analysis can be immediately attached to its corresponding product object.

If batch requests are implemented in the future, they should only rely on response ordering if the external API officially guarantees it.

---

## Keep Product as the Source of Truth

A product object should progressively accumulate information as it moves through the pipeline.

Conceptually, each product may contain information such as:

- Product ID
- Product Name
- Product URL
- Screenshot Path
- AI Analysis
- Report Metadata

Each processing stage should enrich the existing product object instead of creating disconnected data structures that later need to be matched together.

This approach simplifies report generation, debugging, testing, and future feature additions.

---

## Design for Future Extensibility

Where practical, modules should communicate using well-defined data models instead of loosely related dictionaries or parallel arrays.

This makes it easier to replace components in the future, such as:

- JSON storage → Database
- SMTP → Another email provider
- NVIDIA NIM → Different AI model
- Single retailer → Multiple retailers

while minimizing changes to the rest of the codebase.