import urllib.request
from pathlib import Path

fonts_dir = Path("D:/fashion_monitor/assets/fonts")
fonts_dir.mkdir(parents=True, exist_ok=True)

base_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/"
files = {
    "Poppins-Regular.ttf": base_url + "Poppins-Regular.ttf",
    "Poppins-Bold.ttf": base_url + "Poppins-Bold.ttf",
    "Poppins-Italic.ttf": base_url + "Poppins-Italic.ttf"
}

for name, url in files.items():
    print(f"Downloading {name}...")
    dest = fonts_dir / name
    urllib.request.urlretrieve(url, dest)
    print(f"Saved to {dest}")
