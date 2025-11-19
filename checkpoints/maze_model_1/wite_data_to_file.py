from rlrd.util import load
import pandas as pd

# Load the stats file
stats = load('stats')  # This is a list of dictionaries

# Convert to DataFrame
df = pd.DataFrame(stats)

# Save as CSV
df.to_csv('training_stats.csv', index=False)

print(f"Saved {len(df)} rows to training_stats.csv")
print(f"\nColumns: {list(df.columns)}")
print(f"\nFirst few rows:")
print(df.head())

with open("column_names.txt", "w") as f:
    for col in df.columns:
        f.write(col + "\n")
