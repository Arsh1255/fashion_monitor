import urllib.request
import urllib.error
from pathlib import Path
import shutil

assets_dir = Path("d:/fashion_monitor/assets/pdf")
fonts_dir = assets_dir / "fonts"
icons_dir = assets_dir / "icons"

fonts_dir.mkdir(parents=True, exist_ok=True)
icons_dir.mkdir(parents=True, exist_ok=True)

# 1. Move Poppins fonts
old_fonts_dir = Path("d:/fashion_monitor/assets/fonts")
if old_fonts_dir.exists():
    for f in old_fonts_dir.glob("Poppins-*.ttf"):
        shutil.copy(f, fonts_dir / f.name)
        print(f"Copied {f.name} to {fonts_dir}")

# We need Poppins-Medium and Poppins-SemiBold as well
base_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/"
extra_fonts = ["Poppins-Medium.ttf", "Poppins-SemiBold.ttf"]
for name in extra_fonts:
    dest = fonts_dir / name
    if not dest.exists():
        print(f"Downloading {name}...")
        try:
            urllib.request.urlretrieve(base_url + name, dest)
        except Exception as e:
            print(f"Failed to download {name}: {e}")

# 2. Download SVGs
icons = {
    "calendar": "calendar_month",
    "category": "apparel", # or checkroom
    "pattern": "grid_view",
    "composition": "layers",
    "fit": "checkroom",
    "material": "eco",
    "attributes": "list_alt",
    "analysis": "auto_awesome",
    "confidence": "verified",
    "tshirt": "styler"
}

def get_svg(name):
    # Try different repos/paths for rounded material symbols
    urls = [
        f"https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsrounded/{name}/default/24px.svg",
        f"https://fonts.gstatic.com/s/i/short-term/release/materialsymbolsoutlined/{name}/default/24px.svg"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                return response.read().decode('utf-8')
        except urllib.error.HTTPError:
            continue
    return None

for key, name in icons.items():
    svg_data = get_svg(name)
    if svg_data:
        svg_path = icons_dir / f"{key}.svg"
        svg_path.write_text(svg_data, encoding="utf-8")
        print(f"Saved {key}.svg")
    else:
        print(f"Failed to find SVG for {key} ({name})")
