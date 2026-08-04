## Data Extraction: "Description & Fit" and "Material & Care" Accordions

**Context**
Analysis of an H&M product page to identify DOM structures for scraping product details, specifically focusing on the "Description & Fit" and "Material & Care" accordion sections.

**Diagnostics**
Both sections are implemented as accordions. The data is present in the DOM even when the sections are collapsed (`aria-hidden="true"`, `display: none`). 

| Feature | Description & Fit | Material & Care |
| :--- | :--- | :--- |
| **Trigger ID** | `toggle-descriptionAccordion` | `toggle-materialsAndCareAccordion` |
| **Container ID** | `section-descriptionAccordion` | `section-materialsAndCareAccordion` |
| **Data Format** | Description List (`dl`), Paragraphs (`p`) | Headings (`h3`), Lists (`ul`), Description Lists (`dl`) |
| **Key Attributes** | `data-testid="description-article-number"` | N/A (Uses semantic text headers) |

**Actionable Findings**
*   **Accessibility:** Content is hydrated via Next.js and available in the source DOM without requiring interaction (clicks).
*   **Selector Strategy:** Use IDs (e.g., `#section-materialsAndCareAccordion`) or data attributes (`[data-testid]`) for stability, as hashed class names (e.g., `.b8e50f`) are subject to change between deployments.
*   **Logical Extraction:** For "Material & Care," locate data by finding the `<h3>` header text (e.g., "Composition") and traversing to the sibling list elements.

**Code Fixes**
The following logic demonstrates how to extract data from both sections dynamically:


`````js
/**
 * Scrapes product details from H&M accordions.
 * Suggested for use in browser-based scraping environments.
 */
function scrapeProductDetails() {
  const data = { description: {}, materials: {} };

  // 1. Scrape Description & Fit
  const descSection = document.getElementById('section-descriptionAccordion');
  if (descSection) {
    descSection.querySelectorAll('dl div').forEach(div => {
      const key = div.querySelector('dt')?.innerText.replace(':', '').trim();
      const value = div.querySelector('dd')?.innerText.trim();
      if (key && value) data.description[key] = value;
    });
    data.description['text'] = descSection.querySelector('p')?.innerText;
    data.description['articleNumber'] = descSection.querySelector('[data-testid="description-article-number"]')?.innerText.replace('Art. No.:', '').trim();
  }

  // 2. Scrape Material & Care
  const matSection = document.getElementById('section-materialsAndCareAccordion');
  if (matSection) {
    const composition = Array.from(matSection.querySelectorAll('h3'))
      .find(h => h.innerText.toLowerCase() === 'composition')
      ?.nextElementSibling?.innerText;
    
    const care = Array.from(matSection.querySelectorAll('h3'))
      .find(h => h.innerText.toLowerCase() === 'care instructions')
      ?.nextElementSibling?.innerText;

    data.materials = { composition, careInstructions: care };
  }

  return data;
}

console.log(scrapeProductDetails());
`````

*Note: The code fixes and findings above were identified on a live page in DevTools. When applying them to your codebase, please adapt them to your project's specific technical stack (e.g., Tailwind CSS classes, CSS modules, framework components) rather than applying them as literal CSS overrides.*