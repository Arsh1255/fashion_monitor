"""
Quick test: Run scrape_product_detail on one product and log what it finds.
"""
import sys
sys.path.insert(0, 'd:/fashion_monitor')

from camoufox.sync_api import Camoufox
from src.scraper import HMScraper
import os
import json
import urllib.request
import base64
from pathlib import Path
from openai import OpenAI
from src.config import load_config
from src.models import Product

config = load_config()

raw_text = """
=== DESCRIPTION & FIT ===
New Arrival

T-shirt in soft, printed jersey with a round, rib-trimmed neckline, dropped shoulders and a straight-cut hem. Relaxed fit for a casual but not oversized silhouette.

Art. No.: 1344928012

Net Quantity:
1 N
Common generic name:
T-shirt
Description:
Red/White, East isles club
Length:
Regular length
Sleeve Length:
Short sleeve
Fit:
Relaxed fit
Neckline:
Round neck
Price (MRP):
Rs. 999.00 incl. of all taxes

=== MATERIAL & CARE ===
Composition
Cotton 99%, Viscose 1%
Material
Cotton, Jersey
"""

product = Product(
    art_no="1344928012",
    name="Relaxed Fit Printed T-shirt",
    price="Rs. 999.00",
    product_url="https://www2.hm.com/en_in/productpage.1344928012.html",
    image_url="https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500&q=80",  # Valid t-shirt image for AI
    category="Men",
)
product.raw_page_text = raw_text.strip()

print(f"=== DOWNLOADING REAL IMAGE TO AVOID AI CRASH ===\nURL: {product.image_url}")
mock_screenshot = Path("mock_test.jpg")
req = urllib.request.Request(product.image_url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response, open(mock_screenshot, 'wb') as out_file:
    out_file.write(response.read())

with open(mock_screenshot, "rb") as f:
    base64_img = base64.b64encode(f.read()).decode("utf-8")

print("\n=== RUNNING PROTOTYPE AI PROMPT ===")

client = OpenAI(
    api_key=config.nvidia_api_key,
    base_url=config.nvidia_base_url
)

system_prompt = (
    "You are an expert fashion data formatter and visual analyst. "
    "Respond ONLY with a valid JSON object. No markdown fences, no explanation."
)

user_prompt = f"""
We have scraped text and an image for a fashion product.
Product Name: {product.name}
Product URL: {product.product_url}
Price: {product.price}

Scraped Text:
{product.raw_page_text}

Task:
1. Determine the product category: "top", "bottom", or "other".
2. Extract the appropriate fields from the text based on the category.
   - If "top": include "neckline" and "sleeve length".
   - If "bottom": include "style" and "waist rise".
   - If "other": include relevant specific info if present (e.g., collar, closure, length).
3. ALWAYS include these exactly 7 fields. If any info is completely missing from the text, return an empty string "" (strictly NO hallucination): 
   - "Product Name/Type"
   - "PRICE"
   - "Site Link"
   - "Design Pattern"
   - "Composition"
   - "Material"
   - "Garment Fit"
4. Analyze the image to provide detailed textile information in the "Visual Analysis" list (2-4 bullet points). Focus strictly on observable texture, woven/knit type, and fabric drape. Do not hallucinate or repeat basic text details (like color).
5. Provide a "Confidence Score" (e.g., "8/10") reflecting your certainty about the visual textile assessment.
6. Write Data As if you are a professional expert in textile industry but don't hallucinate or make up wrong info.
Output strictly in this JSON format:
{{
  "Product Name/Type": "...",
  "Product Category": "top|bottom|other",
  "PRICE": "...",
  "Site Link": "...",
  "Design Pattern": "...",
  "Composition": "...",
  "Material": "...",
  "Garment Fit": "...",
  "Visual Analysis": [
    "Bullet 1 (e.g., Lightly textured surface with visible cross-weave)",
    "Bullet 2"
  ],
  "Confidence Score": "8/10",
  "Category Specific Info": {{
    // Put neckline/sleeve length OR style/waist rise OR other relevant fields here based on category
  }}
}}
"""

response = client.chat.completions.create(
    model=config.nvidia_nim_model,
    messages=[
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                }
            ]
        }
    ],
    max_tokens=700,
    temperature=0.05
)

result_text = response.choices[0].message.content.strip()

print("\n=== FINAL AI JSON OUTPUT ===")
try:
    parsed = json.loads(result_text.replace("```json", "").replace("```", ""))
    print(json.dumps(parsed, indent=2))
except Exception as e:
    print(f"Failed to parse JSON: {e}\nRaw output:\n{result_text}")


