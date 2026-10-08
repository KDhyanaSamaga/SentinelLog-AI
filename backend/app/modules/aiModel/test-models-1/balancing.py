"""
balancing.py
------------
Cleans and balances the log-severity classification dataset:

  1. Loads the CSV.
  2. Drops duplicate log lines (based on 'content').
  3. Undersamples the majority class ('Normal').
  4. Oversamples the minority classes ('Medium', 'Risk') by generating
     synthetic rows (jittered numeric fields + resampled real log lines,
     not naive row-copies).
  5. Shuffles and overwrites the original CSV with the balanced dataset.

Usage:
    python balancing.py
"""

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# CONFIG — tweak these to change how aggressive the balancing is
# --------------------------------------------------------------------------
PATH = r"dataset\new_classification_dataset.csv"   # same path as your original script

LABEL_COL = "severity_label"
TIME_DELTA_COL = "time_delta"
LINE_ID_COL = "line_id_orig"

# Random seed for reproducibility
SEED = 42

# How many rows each class should end up with after balancing.
# 'Normal' gets undersampled DOWN to this number.
# 'Medium' / 'Risk' get synthetically oversampled UP to this number.
TARGET_COUNT = {
    "Normal": 600,
    "Medium": 300,
    "Risk": 300,
}

# How much random jitter (as a fraction) to apply to time_delta when
# generating synthetic minority rows, so they aren't exact duplicates.
JITTER_FRACTION = 0.15

rng = np.random.default_rng(SEED)


# --------------------------------------------------------------------------
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"Loaded dataset: {df.shape[0]} rows, {df.shape[1]} columns")
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate log lines. A row is a duplicate if its 'content'
    (the actual log message) has already been seen — this catches the
    repeated log lines that plain full-row dedup would miss."""
    before = len(df)
    df = df.drop_duplicates(subset=["content"], keep="first").reset_index(drop=True)
    removed = before - len(df)
    print(f"Removed {removed} duplicate rows (by 'content') -> {len(df)} rows left")
    return df


def undersample_majority(df: pd.DataFrame, label: str, target: int) -> pd.DataFrame:
    """Randomly drop rows from an over-represented class down to `target`."""
    mask = df[LABEL_COL] == label
    class_df = df[mask]
    if len(class_df) <= target:
        print(f"'{label}' already at/under target ({len(class_df)} <= {target}); no undersampling needed")
        return df

    keep = class_df.sample(n=target, random_state=SEED)
    dropped = len(class_df) - target
    print(f"Undersampled '{label}': {len(class_df)} -> {target} (removed {dropped})")

    return pd.concat([df[~mask], keep], ignore_index=True)


def generate_synthetic_rows(df: pd.DataFrame, label: str, target: int) -> pd.DataFrame:
    """
    Generate synthetic rows for a minority class up to `target` rows.

    Approach (SMOTE-style, adapted for mixed text/numeric log data):
    real minority rows are resampled with replacement, then their numeric
    field (time_delta) is jittered by a random +/- percentage so synthetic
    rows aren't exact byte-for-byte duplicates of real ones. Categorical /
    text fields (node, component, content, event_id, event_template,
    level, risk_score) are kept as-is from the sampled real row, since
    log message text can't be meaningfully interpolated the way numeric
    features can.
    """
    class_df = df[df[LABEL_COL] == label]
    n_existing = len(class_df)
    if n_existing == 0:
        print(f"No existing rows for '{label}', skipping synthetic generation")
        return df
    if n_existing >= target:
        print(f"'{label}' already has {n_existing} rows (>= target {target}); no synthetic rows added")
        return df

    n_needed = target - n_existing
    sampled = class_df.sample(n=n_needed, replace=True, random_state=SEED).reset_index(drop=True)

    # Jitter time_delta so synthetic rows differ numerically from their source row
    jitter = rng.uniform(-JITTER_FRACTION, JITTER_FRACTION, size=n_needed)
    sampled[TIME_DELTA_COL] = (sampled[TIME_DELTA_COL] * (1 + jitter)).round().astype(int).clip(lower=0)

    # Give synthetic rows fresh, clearly-marked IDs so they don't collide with real line_id_orig values
    max_id = df[LINE_ID_COL].max()
    sampled[LINE_ID_COL] = range(max_id + 1, max_id + 1 + n_needed)

    print(f"Generated {n_needed} synthetic rows for '{label}': {n_existing} -> {target}")
    return pd.concat([df, sampled], ignore_index=True)


def balance_dataset(df: pd.DataFrame) -> pd.DataFrame:
    print("\nClass distribution before balancing:")
    print(df[LABEL_COL].value_counts())

    for label, target in TARGET_COUNT.items():
        current = (df[LABEL_COL] == label).sum()
        if current > target:
            df = undersample_majority(df, label, target)
        elif current < target:
            df = generate_synthetic_rows(df, label, target)
        else:
            print(f"'{label}' already exactly at target ({target})")

    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)  # shuffle

    print("\nClass distribution after balancing:")
    print(df[LABEL_COL].value_counts())
    return df


# --------------------------------------------------------------------------
def main():
    df = load_data(PATH)
    df = remove_duplicates(df)
    df = balance_dataset(df)

    df.to_csv(PATH, index=False)
    print(f"\nBalanced dataset saved back to: {PATH}")
    print(f"Final shape: {df.shape[0]} rows, {df.shape[1]} columns")


if __name__ == "__main__":
    main()