"""
build_classification_dataset.py

End-to-end EDA + cleaning + feature engineering + merge pipeline for the
BGL_2k_log_structured.csv and HDFS_2k_log_structured.csv log datasets,
producing a single `new_classification_dataset.csv` for a 3-class
(Normal / Medium / Risk) LSTM classifier.

IMPORTANT — read this before you trust the labels:
------------------------------------------------------------------
BGL ships with a real, human-verified `Label` column ('-' = normal,
anything else = a real hardware/kernel fault code). That's a genuine
ground-truth label.

HDFS, in this 2k-line sample, has NO label column at all. There is no
way to know true anomaly status from this file alone — real HDFS
anomaly ground truth is block-session based and lives in a separate
official file (`anomaly_label.csv`, columns BlockId,Label) that is
NOT part of what you uploaded.

Because of that, this script:
  - uses the REAL `Label` for BGL severity
  - uses a HEURISTIC (Level + keyword rules) for HDFS severity, and
    prints a loud warning about it

Treat the HDFS severity_label as a weak/proxy label, not ground truth,
until you plug in the real anomaly_label.csv. See the review at the
bottom of the chat message for why this matters for your model.
"""

import numpy as np
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

BGL_PATH = r"D:\SentinelLog-AI\ai-model\dataset\BGL_2k.log_structured.csv"
HDFS_PATH = r"D:\SentinelLog-AI\ai-model\dataset\HDFS_2k.log_structured.csv"
OUT_PATH = r"D:\SentinelLog-AI\ai-model\dataset\new_classification_dataset.csv"

SEVERITY_BANDS = [(0.0, 0.5, "Normal"), (0.5, 0.8, "Medium"), (0.8, 1.01, "Risk")]
SEVERITY_CODE = {"Normal": 0, "Medium": 1, "Risk": 2}

LEVEL_WEIGHT = {
    "INFO": 0.05,
    "WARN": 0.55,
    "WARNING": 0.55,
    "ERROR": 0.65,
    "SEVERE": 0.75,
    "FATAL": 0.75,
}

RISK_KEYWORDS = ["exception", "error", "fail", "corrupt", "denied", "timeout", "crash"]


def section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 1. LOAD + RAW EDA (head, sample, dtypes, missing values)  -- per your item 7
# ---------------------------------------------------------------------------
def eda(name, df):
    section(f"{name}: shape = {df.shape}")
    print("\n-- head(5) --")
    print(df.head(5).to_string())
    print("\n-- random sample(5) --")
    print(df.sample(5, random_state=42).to_string())
    print("\n-- dtypes --")
    print(df.dtypes)
    print("\n-- missing values per column --")
    miss = df.isnull().sum()
    print(miss[miss.ge(0)])
    if miss.sum() == 0:
        print("(no NaNs, but check for blank/whitespace-only strings too)")
        for c in df.columns:
            blanks = (df[c].astype(str).str.strip() == "").sum()
            if blanks:
                print(f"  '{c}' has {blanks} blank-string rows")


bgl_raw = pd.read_csv(BGL_PATH, dtype=str)
hdfs_raw = pd.read_csv(HDFS_PATH, dtype=str)
eda("BGL (raw)", bgl_raw)
eda("HDFS (raw)", hdfs_raw)


# ---------------------------------------------------------------------------
# 2. FILL MISSING VALUES
# ---------------------------------------------------------------------------
section("Filling missing values")
for col in ["Node", "NodeRepeat", "Type"]:
    n_missing = bgl_raw[col].isnull().sum()
    if n_missing:
        print(f"BGL['{col}']: filling {n_missing} missing with 'UNKNOWN'")
        bgl_raw[col] = bgl_raw[col].fillna("UNKNOWN")
print("HDFS: no missing values to fill.")


# ---------------------------------------------------------------------------
# 3. FEATURE ENGINEERING — BGL
# ---------------------------------------------------------------------------
section("Feature engineering: BGL")

bgl = pd.DataFrame(index=bgl_raw.index)
bgl["dataset"] = "BGL"
bgl["line_id_orig"] = bgl_raw["LineId"]
bgl["timestamp"] = pd.to_datetime(pd.to_numeric(bgl_raw["Timestamp"]), unit="s")
bgl["node"] = bgl_raw["Node"]
bgl["component"] = bgl_raw["Component"]
bgl["level"] = bgl_raw["Level"]
bgl["content"] = bgl_raw["Content"]
bgl["event_id"] = bgl_raw["EventId"]
bgl["event_template"] = bgl_raw["EventTemplate"]

# --- dropped columns & why ---
# LineId      -> just row position, no signal, and can leak ordering
# NodeRepeat  -> exact duplicate of Node in every row we inspected
# Type        -> 1962/2000 rows are the single constant value 'RAS' (near-zero
#                variance) and HDFS has no equivalent field at all
print("Dropped: LineId (row position), NodeRepeat (duplicate of Node), "
      "Type (98%+ constant 'RAS', no HDFS equivalent)")

# --- severity: use the REAL Label column, not a heuristic ---
is_fault = bgl_raw["Label"].str.strip() != "-"
bgl["risk_score"] = np.where(is_fault, 0.90, 0.10)
print(f"BGL severity source: TRUE label ('-' vs fault code). "
      f"{is_fault.sum()} real faults / {len(bgl)} rows.")


# ---------------------------------------------------------------------------
# 4. FEATURE ENGINEERING — HDFS
# ---------------------------------------------------------------------------
section("Feature engineering: HDFS")

hdfs = pd.DataFrame(index=hdfs_raw.index)
hdfs["dataset"] = "HDFS"
hdfs["line_id_orig"] = hdfs_raw["LineId"]
hdfs["timestamp"] = pd.to_datetime(
    hdfs_raw["Date"].str.zfill(6) + hdfs_raw["Time"].str.zfill(6),
    format="%y%m%d%H%M%S",
)
hdfs["node"] = "UNKNOWN"  # HDFS has no Node field
hdfs["component"] = hdfs_raw["Component"]
hdfs["level"] = hdfs_raw["Level"]
hdfs["content"] = hdfs_raw["Content"]
hdfs["event_id"] = hdfs_raw["EventId"]
hdfs["event_template"] = hdfs_raw["EventTemplate"]

# Pid -> identifier, dropped (same reasoning as LineId)
print("Dropped: Pid (process identifier, no generalizable signal)")

# --- severity: NO real label exists here -> heuristic proxy (Level + keywords) ---
print("HDFS severity source: HEURISTIC PROXY (Level weight + keyword match). "
      "*** This is NOT ground truth — see review below. ***")


def hdfs_heuristic_score(level, content, template):
    score = LEVEL_WEIGHT.get(level, 0.1)
    text = f"{content} {template}".lower()
    if any(k in text for k in RISK_KEYWORDS):
        score = max(score, 0.70)
    return min(score, 1.0)


hdfs["risk_score"] = [
    hdfs_heuristic_score(lv, c, t)
    for lv, c, t in zip(hdfs["level"], hdfs["content"], hdfs["event_template"])
]


# ---------------------------------------------------------------------------
# 5. TIME DELTA (per dataset, so BGL/HDFS clocks never mix)
# ---------------------------------------------------------------------------
def add_time_delta(df):
    df = df.sort_values(["dataset", "timestamp"], kind="mergesort").reset_index(drop=True)
    df["time_delta"] = df.groupby("dataset")["timestamp"].diff().dt.total_seconds().fillna(0.0)
    return df


# ---------------------------------------------------------------------------
# 6. SEVERITY BINNING (0-0.5 Normal / 0.5-0.8 Medium / 0.8+ Risk)
# ---------------------------------------------------------------------------
def bin_severity(score):
    for lo, hi, label in SEVERITY_BANDS:
        if lo <= score < hi:
            return label
    return "Risk"


for df in (bgl, hdfs):
    df["severity_label"] = df["risk_score"].apply(bin_severity)
    df["severity_code"] = df["severity_label"].map(SEVERITY_CODE)


# ---------------------------------------------------------------------------
# 7. COMBINE
# ---------------------------------------------------------------------------
section("Combining BGL + HDFS")

merged = pd.concat([bgl, hdfs], ignore_index=True, sort=False)
merged = add_time_delta(merged)

CANONICAL_COLUMNS = [
    "dataset", "line_id_orig", "timestamp", "time_delta",
    "node", "component", "level", "content", "event_id", "event_template",
    "risk_score", "severity_label", "severity_code",
]
merged = merged[CANONICAL_COLUMNS]

print(f"Merged shape: {merged.shape}")
print("\nRows per dataset:")
print(merged["dataset"].value_counts().to_string())
print("\nRows per severity_label (overall):")
print(merged["severity_label"].value_counts().to_string())
print("\nseverity_label breakdown BY dataset (this is the important one to look at):")
print(pd.crosstab(merged["dataset"], merged["severity_label"]).to_string())

merged.to_csv(OUT_PATH, index=False)
print(f"\nSaved -> {OUT_PATH}")