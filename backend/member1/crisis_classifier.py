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
    confusion_matrix
)

# ============================================================
# PATHS
# ============================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.abspath(
    os.path.join(
        CURRENT_DIR, "..", "data",
        "CrisisSense_Master_Dataset.csv"
    )
)

MODEL_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "models")
)

MODEL_PATH = os.path.join(
    MODEL_DIR, "crisis_classifier.pkl"
)

WORD_VECTORIZER_PATH = os.path.join(
    MODEL_DIR, "tfidf_vectorizer.pkl"
)

CHAR_VECTORIZER_PATH = os.path.join(
    MODEL_DIR, "crisis_char_vectorizer.pkl"
)

# ============================================================
# LOAD DATA
# ============================================================

print("Loading dataset...")

df = pd.read_csv(DATA_PATH)

print("Original dataset shape:", df.shape)

required_columns = ["Clean_Text", "Informativeness"]

for column in required_columns:
    if column not in df.columns:
        raise ValueError(f"Missing required column: {column}")

df = df.dropna(
    subset=["Clean_Text", "Informativeness"]
).copy()

df["Clean_Text"] = df["Clean_Text"].astype(str).str.strip()

df = df[df["Clean_Text"] != ""].copy()

# Keep only the three expected label categories.
df = df[
    df["Informativeness"].isin([
        "Related and informative",
        "Related - but not informative",
        "Not related"
    ])
].copy()

# 1 = Crisis-related, 0 = Not crisis-related.
df["crisis_label"] = df["Informativeness"].apply(
    lambda label: 0 if label == "Not related" else 1
)

X = df["Clean_Text"]
y = df["crisis_label"]

print("\nDataset shape after filtering:", df.shape)
print("\nClass distribution:")
print(y.value_counts().rename({
    0: "Not Crisis",
    1: "Crisis"
}))

# ============================================================
# TRAIN-TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# ============================================================
# WORD N-GRAMS: UNIGRAMS, BIGRAMS, TRIGRAMS
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
# CHARACTER N-GRAMS: 3 TO 5 CHARACTERS
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

# ============================================================
# COMBINE WORD AND CHARACTER FEATURES
# ============================================================

X_train_combined = hstack(
    [X_train_word, X_train_char],
    format="csr"
)

X_test_combined = hstack(
    [X_test_word, X_test_char],
    format="csr"
)

print("\nWord feature count:", X_train_word.shape[1])
print("Character feature count:", X_train_char.shape[1])
print("Combined feature count:", X_train_combined.shape[1])

# ============================================================
# TRAIN MODEL
# ============================================================

print("\nTraining crisis classifier...")

model = LogisticRegression(
    max_iter=1500,
    class_weight="balanced",
    random_state=42
)

model.fit(X_train_combined, y_train)

# ============================================================
# EVALUATION
# ============================================================

y_pred = model.predict(X_test_combined)

print("\nAccuracy:", accuracy_score(y_test, y_pred))

print("\nClassification Report:")
print(classification_report(
    y_test,
    y_pred,
    labels=[0, 1],
    target_names=["Not Crisis", "Crisis"],
    zero_division=0
))

print("\nConfusion Matrix:")
print("Order: Not Crisis, Crisis")
print(confusion_matrix(
    y_test,
    y_pred,
    labels=[0, 1]
))

# ============================================================
# SAVE MODEL AND BOTH VECTORIZERS
# ============================================================

os.makedirs(MODEL_DIR, exist_ok=True)

joblib.dump(model, MODEL_PATH)
joblib.dump(word_vectorizer, WORD_VECTORIZER_PATH)
joblib.dump(char_vectorizer, CHAR_VECTORIZER_PATH)

print("\nModel saved:", MODEL_PATH)
print("Word vectorizer saved:", WORD_VECTORIZER_PATH)
print("Character vectorizer saved:", CHAR_VECTORIZER_PATH)

print("\nCrisis classifier training completed!")