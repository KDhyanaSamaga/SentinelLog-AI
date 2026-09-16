"""
HDFS log-level classifier — SSDLC-compliant reference implementation.

HONEST-ASSESSMENT NOTICE
------------------------
On the HDFS_2k structured log, `Level` is deterministically encoded by
`EventId` (E3 -> WARN; every other EventId -> INFO) and by `Component`
(DataXceiver is the only WARN-emitting component). Any classifier trained
on those features is memorising a 14-row lookup table, not learning a
pattern. The --use-leaky-features flag exists so you can *observe* this
directly; the default is strict (no leakage), which will correctly refuse
to train because no learnable features remain in this schema.

For real HDFS anomaly detection, model BlockId-grouped EventId sequences
with an LSTM, labelled via anomaly_label.csv from the HDFS loghub release.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# --------------------------------------------------------------------------- #
# Logging                                                                     #
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("hdfs_level_classifier")

# --------------------------------------------------------------------------- #
# Schema & constants                                                          #
# --------------------------------------------------------------------------- #
REQUIRED_COLUMNS: frozenset[str] = frozenset({
    "LineId", "Date", "Time", "Pid", "Level", "Component",
    "EventId", "EventTemplate", "Content",
})
LEVEL_MAP: dict[str, int] = {"INFO": 0, "WARN": 1}
LEAKY_FEATURES: tuple[str, ...] = ("EventId", "Component")
RANDOM_STATE: int = 42
DEFAULT_CV_SPLITS: int = 5


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Config:
    data_path: Path
    model_out: Path
    report_out: Path
    use_leaky_features: bool
    compare_models: bool
    cv_splits: int


def parse_args(argv: Sequence[str] | None = None) -> Config:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--data", type=Path,
                   default=Path("dataset/HDFS_2k.log_structured.csv"),
                   help="Path to structured HDFS log CSV.")
    p.add_argument("--model-out", type=Path,
                   default=Path("artifacts/level_classifier.joblib"))
    p.add_argument("--report-out", type=Path,
                   default=Path("artifacts/evaluation_report.json"))
    p.add_argument("--use-leaky-features", action="store_true",
                   help="Include EventId/Component. WARNING: these "
                        "deterministically encode Level in this dataset.")
    p.add_argument("--compare-models", action="store_true",
                   help="Run LR / RF / GB / XGB and report CV F1 side-by-side.")
    p.add_argument("--cv-splits", type=int, default=DEFAULT_CV_SPLITS)
    args = p.parse_args(argv)
    return Config(
        data_path=args.data,
        model_out=args.model_out,
        report_out=args.report_out,
        use_leaky_features=args.use_leaky_features,
        compare_models=args.compare_models,
        cv_splits=args.cv_splits,
    )


# --------------------------------------------------------------------------- #
# Data loading & validation                                                   #
# --------------------------------------------------------------------------- #
def load_and_validate(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Dataset is empty: {path}")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Schema mismatch — missing columns: {sorted(missing)}"
        )

    unknown_levels = set(df["Level"].dropna().unique()) - set(LEVEL_MAP)
    if unknown_levels:
        raise ValueError(f"Unknown Level values encountered: {unknown_levels}")

    if df["Level"].isna().any():
        raise ValueError("Level column contains nulls.")

    log.info("Loaded %d rows x %d cols from %s", len(df), len(df.columns), path)
    return df


def build_xy(df: pd.DataFrame, use_leaky: bool) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    df = df.copy()
    y = df["Level"].map(LEVEL_MAP)

    if use_leaky:
        feature_cols = list(LEAKY_FEATURES)
        log.warning(
            "LEAKAGE MODE ENABLED — EventId/Component deterministically "
            "encode Level in this dataset. Reported F1 will be ~1.00 and "
            "is NOT representative of real-world performance."
        )
    else:
        # Drop identifiers, target, and the leaky columns. With the HDFS
        # structured schema this leaves no usable per-line features —
        # which is the structural point.
        drop = set(REQUIRED_COLUMNS) | {"label"}
        feature_cols = [c for c in df.columns if c not in drop]
        if not feature_cols:
            raise ValueError(
                "No non-leaky features remain in this schema. Per-line "
                "Level prediction from HDFS_2k.log_structured.csv is "
                "structurally unlearnable without leakage. Either (a) "
                "engineer features from Content (TF-IDF / embeddings), "
                "or (b) move to the block-sequence LSTM stage using "
                "anomaly_label.csv as ground truth."
            )

    X = df[feature_cols]
    log.info("Features: %s  |  positives: %d / %d",
             feature_cols, int(y.sum()), len(y))
    return X, y, feature_cols


# --------------------------------------------------------------------------- #
# Model construction                                                          #
# --------------------------------------------------------------------------- #
def make_lr_pipeline() -> Pipeline:
    return Pipeline([
        ("encoder", OneHotEncoder(handle_unknown="ignore",
                                  sparse_output=False)),
        ("clf", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",   # critical: 80 / 2000 imbalance
            random_state=RANDOM_STATE,
            solver="lbfgs",
        )),
    ])


def make_candidate_pipelines() -> dict[str, Pipeline]:
    """Only used when --compare-models is set. All use balanced class weights."""
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    try:
        from xgboost import XGBClassifier
        xgb = Pipeline([
            ("encoder", OneHotEncoder(handle_unknown="ignore",
                                      sparse_output=False)),
            ("clf", XGBClassifier(
                use_label_encoder=False,
                eval_metric="logloss",
                scale_pos_weight=(2000 - 80) / 80,
                random_state=RANDOM_STATE,
                n_estimators=200,
                max_depth=4,
            )),
        ])
    except ImportError:
        log.warning("xgboost not installed — skipping from comparison.")
        xgb = None

    candidates: dict[str, Pipeline] = {
        "LogisticRegression": make_lr_pipeline(),
        "RandomForest": Pipeline([
            ("encoder", OneHotEncoder(handle_unknown="ignore",
                                      sparse_output=False)),
            ("clf", RandomForestClassifier(
                n_estimators=200, max_depth=6,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            )),
        ]),
        "GradientBoosting": Pipeline([
            ("encoder", OneHotEncoder(handle_unknown="ignore",
                                      sparse_output=False)),
            ("clf", GradientBoostingClassifier(
                n_estimators=200, max_depth=3,
                random_state=RANDOM_STATE,
            )),
        ]),
    }
    if xgb is not None:
        candidates["XGBoost"] = xgb
    return candidates


# --------------------------------------------------------------------------- #
# Evaluation                                                                  #
# --------------------------------------------------------------------------- #
def stratified_cv(pipe: Pipeline, X: pd.DataFrame, y: pd.Series,
                  n_splits: int) -> dict:
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True,
                          random_state=RANDOM_STATE)
    per_fold_f1: list[float] = []
    for fold, (tr, te) in enumerate(skf.split(X, y), start=1):
        pipe.fit(X.iloc[tr], y.iloc[tr])
        y_pred = pipe.predict(X.iloc[te])
        f1 = f1_score(y.iloc[te], y_pred, pos_label=1, zero_division=0.0)
        per_fold_f1.append(float(f1))
        log.info("  fold %d  WARN-F1 = %.4f", fold, f1)
    return {
        "mean_f1": float(np.mean(per_fold_f1)),
        "std_f1":  float(np.std(per_fold_f1, ddof=1)) if len(per_fold_f1) > 1 else 0.0,
        "per_fold_f1": per_fold_f1,
    }


def compare_models(X: pd.DataFrame, y: pd.Series, cfg: Config) -> dict:
    log.info("=== Model comparison (stratified %d-fold CV) ===", cfg.cv_splits)
    results: dict[str, dict] = {}
    for name, pipe in make_candidate_pipelines().items():
        log.info("-- %s --", name)
        results[name] = stratified_cv(pipe, X, y, cfg.cv_splits)
        log.info("   mean F1 = %.4f (+/- %.4f)",
                 results[name]["mean_f1"], results[name]["std_f1"])
    return results


# --------------------------------------------------------------------------- #
# Persistence                                                                 #
# --------------------------------------------------------------------------- #
def persist(pipe: Pipeline, cfg: Config) -> None:
    cfg.model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, cfg.model_out)
    log.info("Persisted model to %s", cfg.model_out)


def write_report(payload: dict, cfg: Config) -> None:
    cfg.report_out.parent.mkdir(parents=True, exist_ok=True)
    with cfg.report_out.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    log.info("Wrote report to %s", cfg.report_out)


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #
def run(cfg: Config) -> int:
    df = load_and_validate(cfg.data_path)
    X, y, feature_cols = build_xy(df, cfg.use_leaky_features)

    report: dict = {
        "leaky_features_used": cfg.use_leaky_features,
        "features": feature_cols,
        "n_samples": int(len(y)),
        "n_positives": int(y.sum()),
        "cv_splits": cfg.cv_splits,
    }

    if cfg.compare_models:
        report["comparison"] = compare_models(X, y, cfg)
        # Pick the best by mean F1 for persistence.
        best_name = max(report["comparison"],
                        key=lambda n: report["comparison"][n]["mean_f1"])
        log.info("Best model by CV F1: %s", best_name)
        pipe = list(make_candidate_pipelines().items())
        pipe = next(p for n, p in pipe if n == best_name)
    else:
        pipe = make_lr_pipeline()
        log.info("=== LogisticRegression (stratified %d-fold CV) ===",
                 cfg.cv_splits)
        report["logistic_regression"] = stratified_cv(pipe, X, y, cfg.cv_splits)
        log.info("mean F1 = %.4f (+/- %.4f)",
                 report["logistic_regression"]["mean_f1"],
                 report["logistic_regression"]["std_f1"])

    # Refit on full data for the persisted artifact.
    pipe.fit(X, y)
    persist(pipe, cfg)
    write_report(report, cfg)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    cfg = parse_args(argv)
    try:
        return run(cfg)
    except (FileNotFoundError, ValueError) as e:
        log.error("Validation error: %s", e)
        return 2
    except Exception as e:
        log.exception("Unexpected failure: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())