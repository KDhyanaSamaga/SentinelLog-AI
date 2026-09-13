"""
pipeline.py
-----------
End-to-end pipeline that turns the processed log CSV into LSTM-ready
sequences, then trains a first anomaly-detection LSTM.

IMPORTANT: this script expects the ORIGINAL processed CSV (the one with
all rows, in original log order) -- NOT a row-balanced/shuffled version.
Sequence models need real chronological order to mean anything: a
sliding window over shuffled or undersampled rows is not a real log
sequence anymore. If you ran balancing.py and overwrote your CSV with
the row-balanced version, re-export the original processed CSV first
(see the note at the bottom of this docstring).

Pipeline stages
----------------
  1. Load CSV, sort each log source back into its original order
     (dataset, line_id_orig) -- this guarantees true chronological order
     even if the file was re-saved out of order.
  2. Build the binary target: anomaly_label = 0 for Normal,
     1 for Medium/Risk.
  3. Encode event_id -> integer ids (LSTM embedding input), saving the
     vocabulary so you can map ids back to real events later.
  4. Build fixed-length sequences with a sliding window, PER DATASET
     (BGL and HDFS are independent log streams and must never be mixed
     inside one window).
  5. Label each window: anomalous (1) if ANY event in it is anomalous,
     else normal (0). This is where class balance is decided -- at the
     sequence level, not by deleting/duplicating individual log rows.
  6. Train/test split (stratified on the window label).
  7. Train a small embedding + LSTM binary classifier and report
     accuracy / precision / recall / F1 on the test set.
  8. Save the trained model, the event_id vocabulary, and the X/Y
     arrays to disk.

If your window classes are still very imbalanced after step 5, this
script oversamples minority WINDOWS (not raw rows) to balance them --
duplicating whole training sequences is valid here since gaps aren't
being introduced into any single sequence.

Usage:
    python pipeline.py
"""

import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils import resample

# --------------------------------------------------------------------------
# DEVICE DETECTION -- use GPU when available, otherwise fall back to CPU
# --------------------------------------------------------------------------
if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
    print(f"[INFO] GPU detected: {torch.cuda.get_device_name(0)}")
    print(f"[INFO] Training will use GPU ({DEVICE})")
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    # Apple Silicon GPU support
    DEVICE = torch.device("mps")
    print(f"[INFO] Apple MPS backend detected. Training will use MPS ({DEVICE})")
else:
    DEVICE = torch.device("cpu")
    print(f"[INFO] No GPU detected. Training will use CPU ({DEVICE})")

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
PATH = r"dataset\copy\classification_modified_old.csv"   # ORIGINAL processed CSV, unbalanced/unshuffled

SEQUENCE_LENGTH = 10     # window size (events per sample)
STRIDE = 1                # step size between windows; 1 = maximum overlap

SEED = 42
TEST_SIZE = 0.2

BALANCE_WINDOWS = True    # oversample minority-class windows after sequencing
EMBEDDING_DIM = 32
LSTM_UNITS = 64
EPOCHS = 15
BATCH_SIZE = 32
LEARNING_RATE = 1e-3

OUT_MODEL_PATH = "lstm_anomaly_model.pt"
OUT_VOCAB_PATH = "event_id_vocab.json"
OUT_ARRAYS_PATH = "sequences.npz"


# --------------------------------------------------------------------------
def load_and_order(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.sort_values(["dataset", "line_id_orig"]).reset_index(drop=True)
    print(f"Loaded {len(df)} rows across sources: {dict(df['dataset'].value_counts())}")
    return df


def add_binary_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["anomaly_label"] = df["severity_label"].map(
        {"Normal": 0, "Medium": 1, "Risk": 1}
    )
    if df["anomaly_label"].isnull().any():
        unknown = df.loc[df["anomaly_label"].isnull(), "severity_label"].unique()
        raise ValueError(f"Unrecognized severity_label values: {unknown}")
    print("Row-level label counts:", dict(df["anomaly_label"].value_counts()))
    return df


def build_event_vocab(df: pd.DataFrame) -> dict:
    """event_id string -> integer id. 0 is reserved for padding/unknown."""
    unique_events = sorted(df["event_id"].unique())
    vocab = {eid: idx + 1 for idx, eid in enumerate(unique_events)}
    print(f"Vocabulary size: {len(vocab)} unique event_ids (+1 reserved for padding)")
    return vocab


def build_sequences(df: pd.DataFrame, vocab: dict, seq_len: int, stride: int):
    """
    Slide a fixed-length window over each dataset's event stream
    independently (never crossing a BGL/HDFS boundary).

    Returns X (n_samples, seq_len) of integer event ids,
            Y (n_samples,) binary window labels.
    """
    X, Y = [], []
    for source, group in df.groupby("dataset", sort=False):
        event_ids = group["event_id"].map(vocab).to_numpy()
        labels = group["anomaly_label"].to_numpy()

        n = len(event_ids)
        for start in range(0, n - seq_len + 1, stride):
            window_events = event_ids[start:start + seq_len]
            window_label = int(labels[start:start + seq_len].any())
            X.append(window_events)
            Y.append(window_label)

        n_windows = max(0, (n - seq_len) // stride + 1)
        print(f"  {source}: {n} rows -> {n_windows} windows")

    X = np.array(X, dtype=np.int32)
    Y = np.array(Y, dtype=np.int32)
    print(f"Total windows: {len(X)}  |  anomalous: {Y.sum()}  |  normal: {len(Y) - Y.sum()}")
    return X, Y


def balance_windows(X: np.ndarray, Y: np.ndarray, seed: int):
    """Oversample the minority window class to match the majority count.
    Whole windows are duplicated -- unlike raw-row duplication, this is
    valid because it doesn't create gaps inside any individual sequence."""
    idx_majority_label = 0 if (Y == 0).sum() >= (Y == 1).sum() else 1
    idx_minority_label = 1 - idx_majority_label

    X_majority, Y_majority = X[Y == idx_majority_label], Y[Y == idx_majority_label]
    X_minority, Y_minority = X[Y == idx_minority_label], Y[Y == idx_minority_label]

    if len(X_minority) == 0:
        print("No minority-class windows found; skipping window balancing")
        return X, Y

    X_minority_up, Y_minority_up = resample(
        X_minority, Y_minority,
        replace=True,
        n_samples=len(X_majority),
        random_state=seed,
    )

    X_bal = np.concatenate([X_majority, X_minority_up])
    Y_bal = np.concatenate([Y_majority, Y_minority_up])

    # shuffle
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(X_bal))
    X_bal, Y_bal = X_bal[perm], Y_bal[perm]

    print(f"Balanced windows: {len(X_bal)} total -> "
          f"{int((Y_bal == 0).sum())} normal / {int((Y_bal == 1).sum())} anomalous")
    return X_bal, Y_bal


# --------------------------------------------------------------------------
# PyTorch LSTM Model
# --------------------------------------------------------------------------
class LSTMAnomalyDetector(nn.Module):
    """
    Embedding -> LSTM -> Dense(32, ReLU) -> Dropout(0.3) -> Dense(1)

    Architecture mirrors the original Keras Sequential model exactly.
    Output is a raw logit (use BCEWithLogitsLoss for numerically stable
    training; apply sigmoid only at inference time).
    """

    def __init__(self, vocab_size: int, embedding_dim: int, lstm_units: int,
                 padding_idx: int = 0):
        super().__init__()
        # padding_idx=0 zeroes out the gradient for the padding token,
        # equivalent to Keras mask_zero=True for the embedding layer.
        self.embedding = nn.Embedding(
            num_embeddings=vocab_size + 1,
            embedding_dim=embedding_dim,
            padding_idx=padding_idx,
        )
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=lstm_units,
            batch_first=True,
        )
        self.fc1 = nn.Linear(lstm_units, 32)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: LongTensor of shape (batch, seq_len) with integer event ids.
        Returns:
            Raw logits of shape (batch,).
        """
        emb = self.embedding(x)                  # (batch, seq_len, emb_dim)
        lstm_out, _ = self.lstm(emb)              # (batch, seq_len, lstm_units)
        last_hidden = lstm_out[:, -1, :]          # (batch, lstm_units)
        out = self.fc1(last_hidden)               # (batch, 32)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out).squeeze(-1)           # (batch,)
        return out


def count_parameters(model: nn.Module) -> int:
    """Return total number of trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


# --------------------------------------------------------------------------
# Early Stopping (replaces keras.callbacks.EarlyStopping)
# --------------------------------------------------------------------------
class EarlyStopping:
    """Stop training when a monitored metric has stopped improving."""

    def __init__(self, patience: int = 3):
        self.patience = patience
        self.best_loss: float | None = None
        self.best_state_dict: dict | None = None
        self.counter = 0

    def step(self, val_loss: float, model: nn.Module) -> bool:
        """
        Call after each epoch.
        Returns True when training should stop.
        """
        if self.best_loss is None or val_loss < self.best_loss:
            self.best_loss = val_loss
            self.best_state_dict = {k: v.clone() for k, v in model.state_dict().items()}
            self.counter = 0
            return False
        self.counter += 1
        return self.counter >= self.patience

    def restore_best_weights(self, model: nn.Module) -> None:
        if self.best_state_dict is not None:
            model.load_state_dict(self.best_state_dict)


# --------------------------------------------------------------------------
# Training and evaluation
# --------------------------------------------------------------------------
def build_model(vocab_size: int, embedding_dim: int, lstm_units: int) -> nn.Module:
    model = LSTMAnomalyDetector(vocab_size, embedding_dim, lstm_units)
    model.to(DEVICE)
    print(f"\nModel architecture:\n{model}")
    print(f"Total trainable parameters: {count_parameters(model):,}\n")
    return model


def train_and_evaluate(X, Y, vocab_size, seq_len):
    # ---- reproducibility ----
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    # ---- train / test split ----
    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=TEST_SIZE, random_state=SEED, stratify=Y
    )
    print(f"Train: {len(X_train)}  Test: {len(X_test)}")

    # ---- validation split from training data (10 %) ----
    X_train, X_val, Y_train, Y_val = train_test_split(
        X_train, Y_train, test_size=0.1, random_state=SEED, stratify=Y_train
    )
    print(f"Train (after val split): {len(X_train)}  Val: {len(X_val)}")

    # ---- DataLoaders ----
    def _make_loader(X_np, Y_np, shuffle: bool) -> DataLoader:
        X_t = torch.from_numpy(X_np).long().to(DEVICE)
        Y_t = torch.from_numpy(Y_np).float().to(DEVICE)
        return DataLoader(TensorDataset(X_t, Y_t),
                          batch_size=BATCH_SIZE, shuffle=shuffle)

    train_loader = _make_loader(X_train, Y_train, shuffle=True)
    val_loader = _make_loader(X_val, Y_val, shuffle=False)

    # ---- model, loss, optimizer ----
    model = build_model(vocab_size, EMBEDDING_DIM, LSTM_UNITS)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    early_stop = EarlyStopping(patience=3)

    # ---- training loop ----
    for epoch in range(1, EPOCHS + 1):
        # -- train phase --
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for X_batch, Y_batch in train_loader:
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, Y_batch)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(Y_batch)
            preds = (logits >= 0.0).long()
            train_correct += (preds == Y_batch.long()).sum().item()
            train_total += len(Y_batch)

        avg_train_loss = train_loss / train_total
        train_acc = train_correct / train_total

        # -- validation phase --
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for X_batch, Y_batch in val_loader:
                logits = model(X_batch)
                loss = criterion(logits, Y_batch)
                val_loss += loss.item() * len(Y_batch)
                preds = (logits >= 0.0).long()
                val_correct += (preds == Y_batch.long()).sum().item()
                val_total += len(Y_batch)

        avg_val_loss = val_loss / val_total
        val_acc = val_correct / val_total

        print(f"Epoch {epoch:2d}/{EPOCHS} -- "
              f"train_loss: {avg_train_loss:.4f}  train_acc: {train_acc:.4f}  "
              f"val_loss: {avg_val_loss:.4f}  val_acc: {val_acc:.4f}")

        if early_stop.step(avg_val_loss, model):
            print(f"Early stopping triggered at epoch {epoch} "
                  f"(no improvement for {early_stop.patience} epochs)")
            break

    # restore best weights
    early_stop.restore_best_weights(model)

    # ---- test evaluation ----
    model.eval()
    X_test_t = torch.from_numpy(X_test).long().to(DEVICE)
    with torch.no_grad():
        logits = model(X_test_t)
        Y_pred_prob = torch.sigmoid(logits).cpu().numpy()
    Y_pred = (Y_pred_prob >= 0.5).astype(int)

    print("\nTest set performance:")
    print(classification_report(Y_test, Y_pred, target_names=["Normal", "Anomaly"]))
    print("Confusion matrix:")
    print(confusion_matrix(Y_test, Y_pred))

    return model


# --------------------------------------------------------------------------
def main():
    df = load_and_order(PATH)
    df = add_binary_label(df)

    vocab = build_event_vocab(df)
    with open(OUT_VOCAB_PATH, "w") as f:
        json.dump(vocab, f, indent=2)
    print(f"Saved event_id vocabulary -> {OUT_VOCAB_PATH}")

    X, Y = build_sequences(df, vocab, SEQUENCE_LENGTH, STRIDE)

    if BALANCE_WINDOWS:
        X, Y = balance_windows(X, Y, SEED)

    np.savez(OUT_ARRAYS_PATH, X=X, Y=Y)
    print(f"Saved sequence arrays -> {OUT_ARRAYS_PATH}")

    model = train_and_evaluate(X, Y, vocab_size=len(vocab), seq_len=SEQUENCE_LENGTH)

    # Save model state_dict (PyTorch best practice)
    torch.save(model.state_dict(), OUT_MODEL_PATH)
    print(f"Saved trained model -> {OUT_MODEL_PATH}")


if __name__ == "__main__":
    main()
