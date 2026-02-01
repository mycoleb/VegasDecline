from pathlib import Path
import requests

HIST_URL = (
    "https://res.cloudinary.com/simpleview/image/upload/v1740683821/clients/lasvegas/"
    "Las_Vegas_Historical_1970_to_2024_143e51ff-0c5d-4878-a682-9a85c2925c59.pdf"
)

# December 2025 Executive Summary (contains 2025 YTD visitor total on page 2)
EXEC_URL = (
    "https://assets.simpleviewcms.com/simpleview/image/upload/v1/clients/lasvegas/"
    "ES_Dec2025_95e90192-2f0a-4c30-b094-db4c612f48de.pdf"
)

def download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.lvcva.com/",
    }
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    print(f"Downloaded: {out_path.resolve()}")

def main():
    download(HIST_URL, Path("data/lvcva_historical_1970_2024.pdf"))
    download(EXEC_URL, Path("data/lvcva_exec_summary_dec2025.pdf"))

if __name__ == "__main__":
    main()
