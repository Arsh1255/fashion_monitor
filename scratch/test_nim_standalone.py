"""
Standalone script to test NVIDIA NIM Vision API on a single product image file.
Examines the visual analysis output (fabric, pattern, textile structure, summary).
"""

import base64
import json
import os
import sys
from pathlib import Path
from openai import OpenAI

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config


def encode_image_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    config = load_config()
    print("=" * 60)
    print("NVIDIA NIM Vision AI Standalone Test")
    print(f"API Key Configured: {'Yes' if config.nvidia_api_key else 'No'}")
    print(f"Model: {config.nvidia_nim_model}")
    print(f"Base URL: {config.nvidia_base_url}")
    print("=" * 60)

    if not config.nvidia_api_key:
        print("ERROR: NVIDIA_API_KEY is not set in .env file.")
        return

    # Find a sample screenshot image
    sample_images = list(config.screenshot_dir.glob("*.png")) + list(config.screenshot_dir.glob("*.jpg"))
    if not sample_images:
        import urllib.request
        sample_path = config.screenshot_dir / "sample_test.jpg"
        config.screenshot_dir.mkdir(parents=True, exist_ok=True)
        sample_url = "https://image.hm.com/assets/hm/1c/a5/1ca585d914e0820a9084bb97e25ef888ad15a653.jpg"
        print(f"Downloading sample image from {sample_url}...")
        req = urllib.request.Request(sample_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            sample_path.write_bytes(resp.read())
        sample_image_path = sample_path
    else:
        sample_image_path = sample_images[0]

    print(f"Testing on image: {sample_image_path} ({sample_image_path.stat().st_size} bytes)")

    client = OpenAI(
        api_key=config.nvidia_api_key,
        base_url=config.nvidia_base_url
    )

    base64_img = encode_image_base64(sample_image_path)

    system_prompt = "You are an expert AI fashion analyst. You MUST respond ONLY in raw valid JSON format matching the requested keys. Do not include markdown block syntax like ```json or any introductory text."
    user_prompt = (
        "Analyze this fashion product image. Provide visual findings in JSON format:\n{\n"
        '  "fabric_info": "<materials, composition e.g. 100% Cotton, Jersey>",\n'
        '  "pattern_info": "<design, pattern, graphic, text e.g. Solid White with Left Chest Text Logo>",\n'
        '  "textile_info": "<weave or knit type e.g. Single Jersey Knit, Ribbed Crew Neck>",\n'
        '  "summary": "<1-2 sentence concise visual overview>"\n}'
    )

    print("\nSending request to NVIDIA NIM API...")
    try:
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
            max_tokens=400,
            temperature=0.1
        )

        raw_text = response.choices[0].message.content or ""
        print("\n" + "=" * 60)
        print("RAW RESPONSE FROM MODEL:")
        print("=" * 60)
        print(raw_text)

        print("\n" + "=" * 60)
        print("PARSED STRUCTURED RESULT:")
        print("=" * 60)
        try:
            parsed = json.loads(raw_text)
            print("Fabric Info  :", parsed.get("fabric_info"))
            print("Pattern Info :", parsed.get("pattern_info"))
            print("Textile Info :", parsed.get("textile_info"))
            print("Summary      :", parsed.get("summary"))
        except Exception:
            import re
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                print("Fabric Info  :", parsed.get("fabric_info"))
                print("Pattern Info :", parsed.get("pattern_info"))
                print("Textile Info :", parsed.get("textile_info"))
                print("Summary      :", parsed.get("summary"))
            else:
                print("Could not parse JSON directly. Raw output shown above.")

    except Exception as e:
        print(f"\nERROR calling NVIDIA NIM API: {e}")


if __name__ == "__main__":
    main()
