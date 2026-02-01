from pathlib import Path
import pandas as pd

URL = "https://www.harryreidairport.com/Business/Statistics"  # landing page

# You manually grab the monthly XLS once, then automate from there
INPUT_XLS = Path("data/raw/airport/LAS_Monthly_Passengers.xlsx")
OUT_CSV = Path("data/clean/airport_passengers.csv")

def main():
    df = pd.read_excel(INPUT_XLS, skiprows=3)
    df = df.rename(columns={
        "Month": "date",
        "Total Passengers": "passengers"
    })
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")

if __name__ == "__main__":
    main()
