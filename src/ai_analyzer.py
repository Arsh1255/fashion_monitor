"""
NVIDIA NIM visual AI analysis module for Fashion Trend Monitor.

Connects to NVIDIA NIM OpenAI-compatible multimodal endpoint to:
1. Format scraped product accordion text into strict key-value attributes (no hallucination).
2. Analyze product screenshots for textile/construction visual observations.
"""

import base64
import json
import re
import time
import logging
from pathlib import Path
from typing import List, Optional
from openai import OpenAI, RateLimitError

from src.config import Config
from src.models import Product, AIAnalysis
from src.ai_manager import AIRequestManager

logger = logging.getLogger(__name__)


class NvidiaNimAnalyzer:
    """Analyzer client for NVIDIA NIM multimodal vision API focusing on textile & garment details."""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[OpenAI] = None
        if config.nvidia_api_key:
            self.client = OpenAI(
                api_key=config.nvidia_api_key, base_url=config.nvidia_base_url
            )

    @staticmethod
    def encode_image_base64(image_path: Path) -> Optional[str]:
        """Read and convert local image file to base64 string."""
        if not image_path.exists():
            return None
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_product(self, product: Product, max_retries: int = 3) -> AIAnalysis:
        """
        Analyze a single product using scraped raw page text + screenshot.

        Attribute extraction uses ONLY product.raw_page_text as ground truth.
        Visual fields may use the image; attributes must never invent missing values.
        """
        if not product.screenshot_path:
            logger.warning(
                f"No screenshot path for product {product.art_no}. Skipping AI analysis."
            )
            return AIAnalysis(summary="No screenshot available for visual analysis.")

        screenshot_path = Path(product.screenshot_path)
        base64_img = self.encode_image_base64(screenshot_path)
        if not base64_img:
            logger.error(f"Failed to read image at {screenshot_path}.")
            return AIAnalysis(summary="Failed to read screenshot image file.")

        if not self.client or not self.config.nvidia_api_key:
            logger.warning(
                "NVIDIA API key not configured. Returning mock/default analysis."
            )
            return AIAnalysis(
                fabric_info="Cotton / Synthetic blend (Mock)",
                pattern_info="Solid color with tailored construction (Mock)",
                textile_info="Standard single jersey knit (Mock)",
                extracted_attributes={
                    "Composition": product.composition or "Cotton 100% (Mock)",
                    "Fit": product.fit or "Relaxed fit (Mock)",
                },
                summary="Default visual analysis (NVIDIA_API_KEY not configured).",
            )

        system_prompt = (
            "You are an expert fashion data formatter and visual analyst. "
            "Respond ONLY with a valid JSON object. No markdown fences, no explanation."
        )

        raw_text = (product.raw_page_text or "").strip()
        if len(raw_text) > 4500:
            raw_text = raw_text[:4500]

        user_prompt = f"""
We have scraped text and an image for a fashion product.
Product Name: {product.name or 'Unknown'}
Product URL: {product.product_url or 'N/A'}
Price: {product.price or 'N/A'}

Scraped Text:
{raw_text if raw_text else '(no detail text captured)'}

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
5. Provide a "Confidence Score" reflecting your certainty about the visual textile assessment based on image quality, blur, and lighting. Output a score out of 10 (e.g., "4.5/10", "6.0/10", "9.5/10"). Do NOT default to any specific score; calculate it dynamically based on how clearly you can see the fabric texture.

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
  "Confidence Score": "$YOUR_CONCLUSION_CONFIDENCE_OF_VISUAL_ANALYSIS_NUMBER_OUT_OF_10/10", // put your values here like i.e, 2/10 , 3/10 so on
  "Category Specific Info": {{
    // Put neckline/sleeve length OR style/waist rise OR other relevant fields here based on category
  }}
}}
"""

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Querying NVIDIA NIM API ({self.config.nvidia_nim_model}) "
                    f"for product {product.art_no} (Attempt {attempt}/{max_retries})..."
                )
                response = self.client.chat.completions.create(
                    model=self.config.nvidia_nim_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_img}"
                                    },
                                },
                            ],
                        },
                    ],
                    max_tokens=700,
                    temperature=0.05,
                )

                raw_content = response.choices[0].message.content or ""
                logger.debug(
                    f"NVIDIA NIM Raw Response for {product.art_no}: {raw_content}"
                )

                json_match = None
                if raw_content.startswith("{") and raw_content.endswith("}"):
                    try:
                        json_match = json.loads(raw_content)
                    except Exception:
                        json_match = None

                if not json_match:
                    match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                    if match:
                        try:
                            json_match = json.loads(match.group(0))
                        except Exception:
                            json_match = None

                if json_match and isinstance(json_match, dict):
                    # Map the raw JSON keys to our AIAnalysis model fields
                    mapped_data = {
                        "product_category": json_match.get("Product Category", "other"),
                        "design_pattern": json_match.get("Design Pattern", "N/A"),
                        "bullet_summary": json_match.get("Visual Analysis", []),
                        "confidence_score": json_match.get("Confidence Score", "N/A"),
                        "category_specific_info": json_match.get(
                            "Category Specific Info", {}
                        ),
                    }
                    analysis = AIAnalysis.from_dict(mapped_data)

                    # Mirror common AI attributes onto Product fields used by the PDF specs grid
                    if "Composition" in json_match and json_match["Composition"] != "":
                        product.composition = json_match["Composition"]
                    if "Material" in json_match and json_match["Material"] != "":
                        product.material_type = json_match["Material"]
                    if "Garment Fit" in json_match and json_match["Garment Fit"] != "":
                        product.fit = json_match["Garment Fit"]

                    return analysis

                return AIAnalysis(summary=raw_content[:250])

            except RateLimitError:
                backoff_time = (2**attempt) * 1.5
                logger.warning(
                    f"Rate limited (429) by NVIDIA NIM API for product {product.art_no}. "
                    f"Exponential backoff {backoff_time:.1f}s "
                    f"(Attempt {attempt}/{max_retries})..."
                )
                time.sleep(backoff_time)

            except Exception as e:
                logger.error(
                    f"Error querying NVIDIA NIM API for product {product.art_no}: {e}"
                )
                if "429" in str(e):
                    backoff_time = (2**attempt) * 1.5
                    time.sleep(backoff_time)
                    continue
                return AIAnalysis(
                    fabric_info="Analysis error",
                    pattern_info="Analysis error",
                    textile_info="Analysis error",
                    summary=f"AI analysis request error: {str(e)[:100]}",
                )

        return AIAnalysis(
            fabric_info="Rate limit exceeded",
            pattern_info="Rate limit exceeded",
            textile_info="Rate limit exceeded",
            summary="API rate limit (429) exceeded after retries.",
        )

    def is_garment_product(self, product: Product) -> bool:
        """
        Fallback AI method to determine if a product is a garment vs accessory.
        Uses a very fast, text-only prompt to save rate limits.
        """
        if not self.client or not self.config.nvidia_api_key:
            return True  # default to True if AI is disabled

        system_prompt = "You are a fashion classifier. Respond ONLY with the word 'GARMENT' or 'ACCESSORY'."
        user_prompt = f"Product Name: {product.name or 'Unknown'}\nURL: {product.product_url or 'N/A'}\nIs this a garment (e.g., shirt, pants, dress, jacket, sweater) or an accessory (e.g., bag, watch, sunglasses, perfume, shoes, belt)?"

        try:
            response = self.client.chat.completions.create(
                model=self.config.nvidia_nim_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=10,
                temperature=0.0,
            )
            content = (response.choices[0].message.content or "").strip().upper()
            return "ACCESSORY" not in content
        except Exception as e:
            logger.warning(
                f"Error checking if garment for {product.art_no}: {e}. Defaulting to True."
            )
            return True

    def analyze_products(self, products: List[Product]) -> List[Product]:
        """
        Analyze a list of genuinely new products.
        Uses AIRequestManager for strict rate-limiting, retries, and batch tracking.
        """
        manager = AIRequestManager(
            max_retries=self.config.ai_max_retries,
            delay_seconds=self.config.ai_request_delay,
        )

        # We need a wrapper to cache and map the function
        cache: dict[str, AIAnalysis] = {}

        def _analyze_wrapper(product: Product, max_retries: int) -> Product:
            if product.art_no in cache:
                logger.info(
                    f"Reusing cached AI analysis for duplicate product ID {product.art_no}."
                )
                product.ai_analysis = cache[product.art_no]
                return product

            analysis = self.analyze_product(product, max_retries=max_retries)
            cache[product.art_no] = analysis
            product.ai_analysis = analysis

            # Memory Optimization: Free the raw scraped text to save RAM
            product.raw_page_text = None

            return product

        return manager.submit_batch(products, _analyze_wrapper)
