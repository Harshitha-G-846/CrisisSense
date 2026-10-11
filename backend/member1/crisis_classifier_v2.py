"""
Retrain the crisis classifier on CrisisSense_Master_Dataset_v2.csv.

Changes vs crisis_classifier.py:
  - Loads the v2 dataset (mislabeled negatives removed + curated everyday negatives added)
  - Saves to *_v2.pkl files so the v1 model is preserved

Everything else (vectorizers, split, model hyperparameters) is identical
so the comparison is apples-to-apples.
"""

import pandas as pd
import os
import joblib

from scipy.sparse import hstack

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)

# ============================================================
# PATHS
# ============================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data",
                 "CrisisSense_Master_Dataset_v2.csv")
)

MODEL_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "models")
)

MODEL_PATH = os.path.join(MODEL_DIR, "crisis_classifier_v2.pkl")
WORD_VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer_v2.pkl")
CHAR_VECTORIZER_PATH = os.path.join(MODEL_DIR, "crisis_char_vectorizer_v2.pkl")

# ============================================================
# LOAD DATA
# ============================================================

print("Loading dataset:", DATA_PATH)
df = pd.read_csv(DATA_PATH)

required_columns = ["Clean_Text", "crisis_label"]
for column in required_columns:
    if column not in df.columns:
        raise ValueError(f"Missing required column: {column}")

df = df.dropna(subset=["Clean_Text", "crisis_label"]).copy()
df["Clean_Text"] = df["Clean_Text"].astype(str).str.strip()
df = df[df["Clean_Text"] != ""].copy()
df["crisis_label"] = df["crisis_label"].astype(int)

X = df["Clean_Text"]
y = df["crisis_label"]

print("Dataset shape:", df.shape)
print("\nClass distribution:")
print(y.value_counts().rename({0: "Not Crisis", 1: "Crisis"}))

# ============================================================
# TRAIN-TEST SPLIT — same as v1
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print(f"\nTrain size: {len(X_train)}")
print(f"Test size:  {len(X_test)}")

# ============================================================
# WORD N-GRAMS
# ============================================================

word_vectorizer = TfidfVectorizer(
    analyzer="word",
    ngram_range=(1, 3),
    max_features=20000,
    min_df=2,
    sublinear_tf=True
)

X_train_word = word_vectorizer.fit_transform(X_train)
X_test_word = word_vectorizer.transform(X_test)

# ============================================================
# CHAR N-GRAMS
# ============================================================

char_vectorizer = TfidfVectorizer(
    analyzer="char",
    ngram_range=(3, 5),
    max_features=30000,
    min_df=2,
    sublinear_tf=True
)

X_train_char = char_vectorizer.fit_transform(X_train)
X_test_char = char_vectorizer.transform(X_test)

X_train_combined = hstack([X_train_word, X_train_char], format="csr")
X_test_combined = hstack([X_test_word, X_test_char], format="csr")

print("\nWord feature count:", X_train_word.shape[1])
print("Character feature count:", X_train_char.shape[1])
print("Combined feature count:", X_train_combined.shape[1])

# ============================================================
# TRAIN MODEL
# ============================================================

print("\nTraining crisis classifier v2...")
model = LogisticRegression(
    max_iter=1500,
    class_weight="balanced",
    random_state=42
)
model.fit(X_train_combined, y_train)

# ============================================================
# EVALUATION — check multiple thresholds
# ============================================================

probs = model.predict_proba(X_test_combined)[:, 1]

print("\n" + "=" * 70)
print("Threshold sweep on test set")
print("=" * 70)
print(f"{'thr':>5} {'prec':>8} {'rec':>8} {'f1':>8} "
      f"{'tn':>6} {'fp':>6} {'fn':>6} {'tp':>6}")
for t in [0.30, 0.40, 0.50, 0.60, 0.70]:
    preds = (probs >= t).astype(int)
    p = precision_score(y_test, preds, zero_division=0)
    r = recall_score(y_test, preds, zero_division=0)
    f = f1_score(y_test, preds, zero_division=0)
    cm = confusion_matrix(y_test, preds, labels=[0, 1])
    print(f"{t:>5.2f} {p:>8.4f} {r:>8.4f} {f:>8.4f} "
          f"{cm[0,0]:>6} {cm[0,1]:>6} {cm[1,0]:>6} {cm[1,1]:>6}")

# Report at default 0.5
y_pred = (probs >= 0.5).astype(int)
print("\nAccuracy at 0.50:", accuracy_score(y_test, y_pred))
print("\nClassification Report at 0.50:")
print(classification_report(
    y_test, y_pred,
    labels=[0, 1],
    target_names=["Not Crisis", "Crisis"],
    zero_division=0
))

# ============================================================
# SAVE
# ============================================================

os.makedirs(MODEL_DIR, exist_ok=True)
joblib.dump(model, MODEL_PATH)
joblib.dump(word_vectorizer, WORD_VECTORIZER_PATH)
joblib.dump(char_vectorizer, CHAR_VECTORIZER_PATH)

print("Saved:", MODEL_PATH)
print("Saved:", WORD_VECTORIZER_PATH)
print("Saved:", CHAR_VECTORIZER_PATH)
print("\ncrisis classifier v2 training complete.")