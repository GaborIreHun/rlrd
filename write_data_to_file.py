import pickle
import pandas as pd


def load(path):
    """Load pickled checkpoint data without importing the rlrd package."""
    with open(path, 'rb') as f:
        return pickle.load(f)

# Load the stats file
stats = load('checkpoints/pointmaze_1/stats')  # This is a list of dictionaries

# Convert to DataFrame
df = pd.DataFrame(stats)

# Save as CSV
df.to_csv('stats/experiment_TurtleBot3_1.csv', index=False)

print(f"Saved {len(df)} rows to stats/experiment_TurtleBot3_1.csv")
print(f"\nColumns: {list(df.columns)}")
print(f"\nFirst few rows:")
print(df.head())

with open("column_names.txt", "w") as f:
    for col in df.columns:
        f.write(col + "\n")
