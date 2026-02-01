import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

df = pd.read_csv("data/visitors.csv", parse_dates=["date"])

# Keep recent decades for clarity
df = df[df["date"] >= "2000-01-01"]

fig, ax = plt.subplots(figsize=(12, 6))

ax.plot(
    df["date"],
    df["visitor_volume"],
    linewidth=2
)

# COVID shock marker
ax.axvspan(
    pd.to_datetime("2020-03-01"),
    pd.to_datetime("2021-06-01"),
    alpha=0.2
)

ax.set_title("Las Vegas Tourism: Long-Term Decline & COVID Shock")
ax.set_ylabel("Monthly Visitors")
ax.set_xlabel("Year")

ax.grid(True, alpha=0.3)

out = Path("outputs")
out.mkdir(exist_ok=True)

plt.tight_layout()
plt.savefig(out / "las_vegas_tourism_decline.png", dpi=150)
plt.show()
