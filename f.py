from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import traceback
from typing import Callable, Optional

import pandas as pd

# Optional imports (only needed if you run those sections)
import requests
import pdfplumber


# =========================
# CONFIG
# =========================
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
OUT_DIR = Path("outputs")

# LVCVA (you already had these in f.py)
HIST_URL = (
    "https://res.cloudinary.com/simpleview/image/upload/v1740683821/clients/lasvegas/"
    "Las_Vegas_Historical_1970_to_2024_143e51ff-0c5d-4878-a682-9a85c2925c59.pdf"
)
EXEC_URL = (
    "https://assets.simpleviewcms.com/simpleview/image/upload/v1/clients/lasvegas/"
    "ES_Dec2025_95e90192-2f0a-4c30-b094-db4c612f48de.pdf"
)

# Folder conventions (you can rename if you want—just keep consistent)
LVCVA_DIR = RAW_DIR / "lvcva"
AIRPORT_DIR = RAW_DIR / "airport"      # put your 2025-01_Traffic_Summary.pdf etc here
GAMING_DIR = RAW_DIR / "gaming"        # put NV gaming spreadsheets/pdfs here
HOTEL_DIR = RAW_DIR / "hotels"         # LVCVA hotel XLSX/PDF
CONVENTION_DIR = RAW_DIR / "conventions"


# =========================
# UTIL: logging + safe runner
# =========================
def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_dirs() -> None:
    for d in [RAW_DIR, CLEAN_DIR, OUT_DIR, LVCVA_DIR, AIRPORT_DIR, GAMING_DIR, HOTEL_DIR, CONVENTION_DIR]:
        d.mkdir(parents=True, exist_ok=True)


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


def run_step(name: str, fn: Callable[[], None]) -> StepResult:
    log("\n" + "=" * 72)
    log(f"STEP: {name}")
    log("=" * 72)
    try:
        fn()
        log(f"[OK] {name}")
        return StepResult(name=name, ok=True, detail="ok")
    except Exception as e:
        log(f"[ERROR] {name}: {e}")
        log("".join(traceback.format_exc()))
        # keep going
        return StepResult(name=name, ok=False, detail=str(e))

def list_dir(dir_path: Path, pattern: str = "*") -> None:
    if not dir_path.exists():
        log(f"Folder missing: {dir_path.resolve()}")
        return
    items = sorted(dir_path.glob(pattern))
    log(f"{dir_path.resolve()} -> {len(items)} files")
    for fp in items[:15]:
        log(f"  - {fp.name}")
    if len(items) > 15:
        log("  ...")

# =========================
# SECTION 1: LVCVA fetch
# =========================
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
    log(f"Downloaded: {out_path.resolve()}")


def step_fetch_lvcva() -> None:
    download(HIST_URL, LVCVA_DIR / "lvcva_historical_1970_2024.pdf")
    download(EXEC_URL, LVCVA_DIR / "lvcva_exec_summary_dec2025.pdf")
def _extract_text(pdf_path: Path) -> str:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)


# =========================
# SECTION 2: Airport parsing (your PDFs)
# =========================
def step_parse_airport() -> None:
    out_dir = CLEAN_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(AIRPORT_DIR.glob("*.pdf"))
    if not pdfs:
        log(f"No airport PDFs found in: {AIRPORT_DIR.resolve()} — skipping.")
        list_dir(GAMING_DIR)
        list_dir(HOTEL_DIR)
        list_dir(CONVENTION_DIR)

        return

    rows = []
    skipped = 0
    considered = 0

    for pdf in pdfs:
        name = pdf.stem.lower()

        # Only passenger details (ignore cargo + traffic summary)
        if "passenger" not in name:
            continue

        considered += 1
        try:
            recs = parse_enplaned_deplaned_dual(pdf)  # returns [2025row, 2024row]
            if not recs:
                skipped += 1
                log(f"  [skip] {pdf.name} (could not find enplaned/deplaned monthly pair)")
                continue
            rows.extend(recs)
        except Exception as e:
            skipped += 1
            log(f"  [error] {pdf.name}: {e}")

    if not rows:
        log("No airport rows parsed — continuing pipeline.")
        return

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["year", "month"])

    out_csv = out_dir / "airport_monthly_passengers.csv"
    df.to_csv(out_csv, index=False)

    log("\nAirport data written:")
    log(f"  {out_csv.resolve()}")
    log("Airport summary:")
    log("-" * 60)
    log(f"Passenger PDFs considered: {considered}")
    log(f"Passenger PDFs skipped:    {skipped}")
    log(f"Rows parsed:               {len(df)} (2 rows per PDF expected)")
    log(df.groupby("year")["total_passengers"].agg(["count", "min", "max"]).to_string())


    

import re
from pathlib import Path
import pdfplumber

def parse_enplaned_deplaned_dual(pdf_path: Path) -> list[dict] | None:
    """
    Extracts enplaned + deplaned passenger totals for BOTH years shown in the PDF table.
    Assumes line order like:
      2025 Monthly, 2024 Monthly, 2025 YTD, 2024 YTD
    Returns two records: one for the newer year and one for the prior year.
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    # Infer month from filename like 2025-01_Passenger_Details.pdf
    # (Year in filename is treated as the "newer" year shown in the table)
    m = re.search(r"(19\d{2}|20\d{2})[-_](\d{2})", pdf_path.stem)
    if not m:
        return None

    newer_year = int(m.group(1))          # e.g., 2025
    prior_year = newer_year - 1           # e.g., 2024
    month = int(m.group(2))

    def find_monthly_pair(label: str) -> tuple[int | None, int | None]:
        """
        Returns (newer_year_monthly, prior_year_monthly) for the given label line.
        """
        for line in text.splitlines():
            s = line.strip()
            if s.lower().startswith(label):
                # Grab big numbers on that line. This will include monthly + YTD columns.
                nums = re.findall(r"[\d,]{6,}", s)
                if len(nums) >= 2:
                    newer = int(nums[0].replace(",", ""))
                    prior = int(nums[1].replace(",", ""))
                    return newer, prior
                return None, None
        return None, None

    dep_new, dep_prev = find_monthly_pair("deplaned")
    enp_new, enp_prev = find_monthly_pair("enplaned")

    if dep_new is None or dep_prev is None or enp_new is None or enp_prev is None:
        return None

    # Two rows: one for newer year, one for prior year
    rec_new = {
        "year": newer_year,
        "month": month,
        "date": f"{newer_year:04d}-{month:02d}-01",
        "enplaned": enp_new,
        "deplaned": dep_new,
        "total_passengers": enp_new + dep_new,
        "source_file": pdf_path.name,
    }
    rec_prev = {
        "year": prior_year,
        "month": month,
        "date": f"{prior_year:04d}-{month:02d}-01",
        "enplaned": enp_prev,
        "deplaned": dep_prev,
        "total_passengers": enp_prev + dep_prev,
        "source_file": pdf_path.name,
    }

    return [rec_new, rec_prev]
def step_airport_yearly_totals() -> None:
    in_csv = CLEAN_DIR / "airport_monthly_passengers.csv"
    if not in_csv.exists():
        log(f"Missing {in_csv.resolve()} — run the airport parse step first.")
        return

    df = pd.read_csv(in_csv, parse_dates=["date"])
    yearly = (
        df.groupby("year", as_index=False)
          .agg(
              total_passengers=("total_passengers", "sum"),
              months=("month", "nunique"),
          )
          .sort_values("year")
    )

    out_csv = CLEAN_DIR / "airport_yearly_passengers.csv"
    yearly.to_csv(out_csv, index=False)

    log(f"Wrote: {out_csv.resolve()}")
    log("Airport yearly totals (sanity):")
    log(yearly.tail(10).to_string(index=False))

# =========================
# SECTION 3: Gaming (placeholder loader)
# =========================
def step_parse_gaming() -> None:
    """
    Put your Nevada Gaming Control Board exports in data/raw/gaming/.
    This step will ingest CSV/XLSX automatically and create a cleaned CSV.
    """
    files = sorted([*GAMING_DIR.glob("*.csv"), *GAMING_DIR.glob("*.xlsx"), *GAMING_DIR.glob("*.pdf")])

    if not files:
        log(f"No gaming CSV/XLSX found in: {GAMING_DIR.resolve()}")
        list_dir(GAMING_DIR)
        list_dir(HOTEL_DIR)
        list_dir(CONVENTION_DIR)

        return

    dfs = []
    for fp in files:
        if fp.suffix.lower() == ".pdf":
            log(f"  - Found gaming PDF (not parsed yet): {fp.name}")
            continue

        try:
            if fp.suffix.lower() == ".csv":
                df = pd.read_csv(fp)
            else:
                df = pd.read_excel(fp, engine="openpyxl")
            df["source_file"] = fp.name
            dfs.append(df)
        except Exception as e:
            log(f"  - Failed reading {fp.name}: {e}")

    if not dfs:
        log("Gaming: nothing readable yet.")
        return

    big = pd.concat(dfs, ignore_index=True)
    out_csv = CLEAN_DIR / "gaming_raw_combined.csv"
    big.to_csv(out_csv, index=False)
    log(f"Wrote: {out_csv.resolve()}")
    log(f"Gaming rows: {len(big):,} | columns: {len(big.columns)}")


# =========================
# SECTION 4: Hotels + Conventions (same pattern)
# =========================
def step_parse_hotels() -> None:
    files = sorted([*HOTEL_DIR.glob("*.csv"), *HOTEL_DIR.glob("*.xlsx")])
    if not files:
        log(f"No hotel CSV/XLSX found in: {HOTEL_DIR.resolve()}")
        list_dir(GAMING_DIR)
        list_dir(HOTEL_DIR)
        list_dir(CONVENTION_DIR)

        return
    # Same approach as gaming (ingest, combine, later we standardize columns)
    dfs = []
    for fp in files:
        try:
            if fp.suffix.lower() == ".csv":
                df = pd.read_csv(fp)
            else:
                df = pd.read_excel(fp, engine="openpyxl")
            df["source_file"] = fp.name
            dfs.append(df)
        except Exception as e:
            log(f"  - Failed reading {fp.name}: {e}")
    if not dfs:
        return
    big = pd.concat(dfs, ignore_index=True)
    out_csv = CLEAN_DIR / "hotels_raw_combined.csv"
    big.to_csv(out_csv, index=False)
    log(f"Wrote: {out_csv.resolve()}")

def step_scan_lvcva_conventions() -> None:
    """
    Scans any lvcva*.pdf in data/raw/lvcva and writes out lines that mention 'convention'.
    Self-contained: does not rely on _extract_text.
    """
    out_dir = CLEAN_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(LVCVA_DIR.glob("lvcva*.pdf"))
    if not pdfs:
        log(f"No lvcva*.pdf found in: {LVCVA_DIR.resolve()} — skipping.")
        list_dir(GAMING_DIR)
        list_dir(HOTEL_DIR)
        list_dir(CONVENTION_DIR)

        return

    debug_lines = []
    for pdf in pdfs:
        try:
            with pdfplumber.open(pdf) as p:
                text = "\n".join(page.extract_text() or "" for page in p.pages)

            hits = [ln.strip() for ln in text.splitlines() if "convention" in ln.lower()]
            debug_lines.append(f"\n--- {pdf.name} ---")
            debug_lines.extend(hits[:150])  # cap output

        except Exception as e:
            log(f"  [error] reading {pdf.name}: {e}")

    out_txt = out_dir / "lvcva_convention_lines_debug.txt"
    out_txt.write_text("\n".join(debug_lines), encoding="utf-8")
    log(f"Wrote: {out_txt.resolve()}")

def step_parse_conventions() -> None:
    files = sorted([*CONVENTION_DIR.glob("*.csv"), *CONVENTION_DIR.glob("*.xlsx")])
    if not files:
        log(f"No convention CSV/XLSX found in: {CONVENTION_DIR.resolve()}")
        list_dir(GAMING_DIR)
        list_dir(HOTEL_DIR)
        list_dir(CONVENTION_DIR)

        return
    dfs = []
    for fp in files:
        try:
            if fp.suffix.lower() == ".csv":
                df = pd.read_csv(fp)
            else:
                df = pd.read_excel(fp, engine="openpyxl")
            df["source_file"] = fp.name
            dfs.append(df)
        except Exception as e:
            log(f"  - Failed reading {fp.name}: {e}")
    if not dfs:
        return
    big = pd.concat(dfs, ignore_index=True)
    out_csv = CLEAN_DIR / "conventions_raw_combined.csv"
    big.to_csv(out_csv, index=False)
    log(f"Wrote: {out_csv.resolve()}")


# =========================
# MAIN
# =========================
def main():
    ensure_dirs()

    results = []
    results.append(run_step("Fetch LVCVA PDFs", step_fetch_lvcva))
    results.append(run_step("Scan LVCVA PDFs for convention metrics (debug)", step_scan_lvcva_conventions))

    results.append(run_step("Parse Airport monthly totals (Traffic Summary PDFs)", step_parse_airport))
    results.append(run_step("Build Airport yearly totals (from monthly)", step_airport_yearly_totals))

    results.append(run_step("Ingest Gaming exports (CSV/XLSX)", step_parse_gaming))
    results.append(run_step("Ingest Hotel stats (CSV/XLSX)", step_parse_hotels))
    results.append(run_step("Ingest Convention stats (CSV/XLSX)", step_parse_conventions))

    log("\n" + "=" * 72)
    log("PIPELINE SUMMARY")
    log("=" * 72)
    for r in results:
        status = "OK" if r.ok else "FAIL (continued)"
        log(f"{status:16} - {r.name} :: {r.detail}")


if __name__ == "__main__":
    main()
