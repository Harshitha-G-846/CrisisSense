"""
information_type_classifier_v2.py

Trains the information-type classifier on a curated, in-domain dataset
instead of the CrisisLex tweet dataset.

Why v2:
  - CrisisLex's "Information Type" labels were designed for tweets.
  - They do not cleanly map to full-sentence crisis reports.
  - The v1 classifier's 71% accuracy on CrisisLex did not translate
    to reliable predictions on our actual inputs.

v2 approach:
  - Train primarily on a curated dataset written in the style of
    CrisisSense inputs.
  - Optionally include a filtered subset of CrisisLex rows for
    additional signal, but the curated rows dominate.
  - Evaluate on a held-out 20% of the curated data.

Saves:
  - models/information_type_classifier_v2.pkl
  - models/information_type_word_vectorizer_v2.pkl
  - models/information_type_char_vectorizer_v2.pkl
"""

import os
import pandas as pd
import joblib
from scipy.sparse import hstack
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

# ---------------- Paths ----------------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "data"))
MODEL_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "models"))

CURATED_CSV = os.path.join(DATA_DIR, "information_type_curated_v2.csv")

MODEL_PATH = os.path.join(MODEL_DIR, "information_type_classifier_v2.pkl")
WORD_VECTORIZER_PATH = os.path.join(
    MODEL_DIR, "information_type_word_vectorizer_v2.pkl"
)
CHAR_VECTORIZER_PATH = os.path.join(
    MODEL_DIR, "information_type_char_vectorizer_v2.pkl"
)

EXPECTED_CLASSES = [
    "Affected individuals",
    "Caution and advice",
    "Donations and volunteering",
    "Infrastructure and utilities",
    "Other Useful Information",
    "Sympathy and support",
]

# ---------------- Load curated dataset ----------------

print("=" * 70)
print("Information Type Classifier — v2 (curated dataset)")
print("=" * 70)
print(f"Loading curated data from: {CURATED_CSV}")

if not os.path.isfile(CURATED_CSV):
    raise FileNotFoundError(
        f"Curated dataset not found: {CURATED_CSV}\n"
        f"Expected a CSV with columns: Clean_Text, Information Type"
    )

df = pd.read_csv(CURATED_CSV)

if "Clean_Text" not in df.columns or "Information Type" not in df.columns:
    raise ValueError(
        "Curated CSV must contain 'Clean_Text' and 'Information Type' columns. "
        f"Found: {list(df.columns)}"
    )

df = df.dropna(subset=["Clean_Text", "Information Type"]).copy()
df["Clean_Text"] = df["Clean_Text"].astype(str).str.strip()
df = df[df["Clean_Text"] != ""].copy()

# Keep only the six expected categories.
unknown = set(df["Information Type"].unique()) - set(EXPECTED_CLASSES)
if unknown:
    print(f"\nWARNING: Found unexpected categories: {unknown}")
    print("These will be dropped.")
    df = df[df["Information Type"].isin(EXPECTED_CLASSES)].copy()

print(f"\nTotal curated rows: {len(df)}")
print("\nCategory distribution:")
print(df["Information Type"].value_counts())

if len(df) < 60:
    raise ValueError(
        f"Only {len(df)} rows loaded. Need at least 60 for meaningful training. "
        f"Please review information_type_curated_v2.csv."
    )

# ---------------- Split ----------------

X = df["Clean_Text"]
y = df["Information Type"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

print(f"\nTrain size: {len(X_train)}")
print(f"Test size:  {len(X_test)}")

# ---------------- Vectorizers ----------------

word_vectorizer = TfidfVectorizer(
    max_features=30000,
    ngram_range=(1, 2),
    sublinear_tf=True,
    min_df=1,       # was 2 in v1; lower because curated data is smaller
    max_df=0.95,
)

char_vectorizer = TfidfVectorizer(
    analyzer="char",
    ngram_range=(3, 5),
    max_features=20000,
    min_df=1,
    sublinear_tf=True,
)

X_train_word = word_vectorizer.fit_transform(X_train)
X_test_word = word_vectorizer.transform(X_test)

X_train_char = char_vectorizer.fit_transform(X_train)
X_test_char = char_vectorizer.transform(X_test)

X_train_combined = hstack([X_train_word, X_train_char])
X_test_combined = hstack([X_test_word, X_test_char])

print(f"\nWord features:  {X_train_word.shape[1]}")
print(f"Char features:  {X_train_char.shape[1]}")
print(f"Total features: {X_train_combined.shape[1]}")

# ---------------- Model ----------------

print("\nTraining LinearSVC on curated data...")

model = LinearSVC(
    C=1.0,
    class_weight="balanced",
    max_iter=5000,
)

model.fit(X_train_combined, y_train)

# ---------------- Evaluate ----------------

y_pred = model.predict(X_test_combined)
accuracy = accuracy_score(y_test, y_pred)

print("\n" + "=" * 70)
print("HELD-OUT TEST RESULTS (20% of curated data)")
print("=" * 70)
print(f"\nAccuracy: {accuracy:.4f}")

print("\nClassification report:")
print(classification_report(y_test, y_pred, zero_division=0))

print("\nConfusion matrix (labels ordered as below):")
print(f"Labels: {EXPECTED_CLASSES}")
print(confusion_matrix(y_test, y_pred, labels=EXPECTED_CLASSES))

# ---------------- Save ----------------

os.makedirs(MODEL_DIR, exist_ok=True)

joblib.dump(model, MODEL_PATH)
joblib.dump(word_vectorizer, WORD_VECTORIZER_PATH)
joblib.dump(char_vectorizer, CHAR_VECTORIZER_PATH)

print(f"\nModel saved: {MODEL_PATH}")
print(f"Word vectorizer saved: {WORD_VECTORIZER_PATH}")
print(f"Char vectorizer saved: {CHAR_VECTORIZER_PATH}")
print("\nTraining complete.")