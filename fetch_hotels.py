from pathlib import Path
import pandas as pd

INPUT_XLS = Path("data/raw/hotels/LVCVA_Hotel_Stats.xlsx")
OUT_CSV = Path("data/clean/hotel_stats.csv")

def main():
    df = pd.read_excel(INPUT_XLS)
    df = df.rename(columns={
        "Occupancy %": "occupancy",
        "ADR": "adr",
        "RevPAR": "revpar",
        "Month": "date"
    })
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")

if __name__ == "__main__":
    main()
