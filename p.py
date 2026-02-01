from pathlib import Path
import re

import pandas as pd
import matplotlib.pyplot as plt
import pdfplumber

HIST_PDF = Path("data/lvcva_historical_1970_2024.pdf")
YTD_XLSX = Path("data/Year_to_Date_Summary_for_2025_a3eca74d-4e08-4cef-9aac-9c22a8dad52d.xlsx")


def parse_historical_visitors_from_pdf(pdf_path: Path) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Matches rows like: 2019 42,523,700 ...
    pattern = re.compile(r"^(19\d{2}|20\d{2})\s+([\d,]{6,})", re.MULTILINE)
    rows = [{"year": int(y), "visitors": int(v.replace(",", ""))} for y, v in pattern.findall(text)]

    df = pd.DataFrame(rows).drop_duplicates("year").sort_values("year")
    return df


def find_2025_ytd_visitors_from_excel(xlsx_path: Path) -> int:
    sheets = pd.read_excel(xlsx_path, sheet_name=None, header=None, engine="openpyxl")

    def parse_number(x):
        if pd.isna(x):
            return None
        if isinstance(x, (int, float)) and x > 1_000_000:
            return int(x)
        if isinstance(x, str):
            s = re.sub(r"[^\d]", "", x)
            if len(s) >= 7:
                return int(s)
        return None

    for sheet_name, df in sheets.items():
        # pandas 2.x safe: no DataFrame.applymap()
        sview = df.astype(str)
        for col in sview.columns:
            sview[col] = sview[col].str.lower()

        # Find any cell containing "visitor volume"
        hits = sview.apply(lambda col: col.str.contains("visitor volume", na=False))
        hit_positions = list(zip(*hits.to_numpy().nonzero()))

        for r, c in hit_positions:
            # Search nearby cells for the first "big number" (likely the YTD total)
            for rr in range(max(0, r - 2), min(df.shape[0], r + 3)):
                for cc in range(max(0, c - 4), min(df.shape[1], c + 8)):
                    n = parse_number(df.iat[rr, cc])
                    if n is not None:
                        print(f"Found 2025 YTD visitors in sheet '{sheet_name}': {n:,}")
                        return n

    raise RuntimeError(
        "Could not find 2025 YTD Visitor Volume in the Excel file. "
        "Open the workbook and confirm it contains a label like 'Visitor Volume'."
    )


def main():
    if not HIST_PDF.exists():
        raise FileNotFoundError("Missing historical PDF. Run f.py first.")
    if not YTD_XLSX.exists():
        raise FileNotFoundError(f"Missing Excel file: {YTD_XLSX}")

    hist = parse_historical_visitors_from_pdf(HIST_PDF)

    ytd_2025 = find_2025_ytd_visitors_from_excel(YTD_XLSX)
    hist = pd.concat([hist, pd.DataFrame([{'year': 2025, 'visitors': ytd_2025}])], ignore_index=True)
    hist = hist.sort_values("year")

    df = hist[hist["year"] >= 2000].copy()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df["year"], df["visitors"], linewidth=2)

    # COVID shock
    ax.axvspan(2020, 2021, alpha=0.2)

    # Peak marker
    peak = df.loc[df["visitors"].idxmax()]
    ax.annotate(
        f"Peak: {int(peak.year)} ({int(peak.visitors):,})",
        xy=(peak.year, peak.visitors),
        xytext=(peak.year - 6, peak.visitors * 0.9),
        arrowprops=dict(arrowstyle="->")
    )

    ax.set_title("Las Vegas Tourism (LVCVA)\nAnnual Visitors (1970–2024) + 2025 YTD (Excel)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Visitors")
    ax.grid(True, alpha=0.3)

    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "las_vegas_tourism_decline.png"

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.show()

    print(f"Saved plot: {out_path.resolve()}")


if __name__ == "__main__":
    main()
