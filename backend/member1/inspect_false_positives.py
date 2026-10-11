"""
Inspect false positives from the crisis classifier on the validation split.

This script:
1. Loads CrisisSense_Master_Dataset.csv (same as crisis_classifier.py)
2. Applies the SAME filtering and label mapping
3. Reproduces the SAME train/val/test split (random_state=42)
4. Loads the currently saved model + vectorizers from backend/models/
5. Scores the validation split with the same probability pipeline
6. Prints:
   - Overall metrics on the validation split
   - Top N false positives (true=0, predicted=1) sorted by probability
   - Top N false negatives (true=1, predicted=0) sorted by probability
   - The most common words in the false positives
"""

import os
import sys
from collections import Counter
import re

import joblib
import pandas as pd
from scipy.sparse import hstack
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

# ---------- Paths ----------

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data", "CrisisSense_Master_Dataset.csv")
)
MODEL_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "models")
)

CRISIS_MODEL_PATH = os.path.join(MODEL_DIR, "crisis_classifier.pkl")
WORD_VEC_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl")
CHAR_VEC_PATH = os.path.join(MODEL_DIR, "crisis_char_vectorizer.pkl")

# Threshold we are inspecting at. Matches the saved pipeline's current behavior
# (0.5 = sklearn's default). We'll compare against other values too.
THRESHOLDS_TO_REPORT = [0.30, 0.40, 0.50, 0.60]

TOP_N = 50
RANDOM_STATE = 42


def load_and_filter_dataset():
    print("Loading dataset from:", DATA_PATH)
    df = pd.read_csv(DATA_PATH)
    print("Original shape:", df.shape)

    df = df.dropna(subset=["Clean_Text", "Informativeness"]).copy()
    df["Clean_Text"] = df["Clean_Text"].astype(str).str.strip()
    df = df[df["Clean_Text"] != ""].copy()

    df = df[df["Informativeness"].isin([
        "Related and informative",
        "Related - but not informative",
        "Not related",
    ])].copy()

    df["crisis_label"] = df["Informativeness"].apply(
        lambda label: 0 if label == "Not related" else 1
    )

    print("Filtered shape:", df.shape)
    print("Class distribution:")
    print(df["crisis_label"].value_counts().rename({0: "Not Crisis", 1: "Crisis"}))
    return df


def split_like_training(df):
    """
    Reproduces the split from crisis_classifier.py:
    - test_size=0.2, random_state=42, stratify=y

    The "test" half here is the same as in the training script.
    We split that test half 50/50 into validation/test-like portions
    so this script is standalone. If your newer training uses
    70/15/15, replace this function with the same split you use there.
    """
    X = df["Clean_Text"]
    y = df["crisis_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y
    )
    return X_train, X_test, y_train, y_test


def score_split(X, y, model, word_vec, char_vec):
    """Return a DataFrame with text, true label, and crisis probability."""
    w = word_vec.transform(X)
    c = char_vec.transform(X)
    features = hstack([w, c], format="csr")

    probs = model.predict_proba(features)[:, 1]

    out = pd.DataFrame({
        "text": X.values,
        "true_label": y.values,
        "crisis_probability": probs,
    })
    return out


def summarize_threshold(scored, threshold):
    preds = (scored["crisis_probability"] >= threshold).astype(int)
    y_true = scored["true_label"].values

    precision = precision_score(y_true, preds, zero_division=0)
    recall = recall_score(y_true, preds, zero_division=0)
    f1 = f1_score(y_true, preds, zero_division=0)

    cm = confusion_matrix(y_true, preds, labels=[0, 1])

    return {
        "threshold": threshold,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1]),
    }


def top_false_positives(scored, threshold, n=50):
    fps = scored[
        (scored["true_label"] == 0) &
        (scored["crisis_probability"] >= threshold)
    ].sort_values("crisis_probability", ascending=False)
    return fps.head(n)


def top_false_negatives(scored, threshold, n=50):
    fns = scored[
        (scored["true_label"] == 1) &
        (scored["crisis_probability"] < threshold)
    ].sort_values("crisis_probability", ascending=True)
    return fns.head(n)


def most_common_words(texts, top=40):
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "and", "or", "of", "to", "in", "on", "at", "for", "with",
        "by", "from", "as", "it", "its", "this", "that", "these",
        "those", "i", "you", "we", "they", "he", "she", "my", "your",
        "our", "their", "rt", "amp", "http", "https", "www", "co",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "not", "no", "so", "if", "but", "about",
    }
    counter = Counter()
    for text in texts:
        tokens = re.findall(r"[a-zA-Z]+", str(text).lower())
        for token in tokens:
            if token not in stop and len(token) > 2:
                counter[token] += 1
    return counter.most_common(top)


def main():
    print("=" * 70)
    print("Crisis Classifier — False Positive Inspection")
    print("=" * 70)

    df = load_and_filter_dataset()

    # Load the SAVED model and vectorizers
    print("\nLoading saved model + vectorizers from:", MODEL_DIR)
    model = joblib.load(CRISIS_MODEL_PATH)
    word_vec = joblib.load(WORD_VEC_PATH)
    char_vec = joblib.load(CHAR_VEC_PATH)

    X_train, X_test, y_train, y_test = split_like_training(df)
    print(f"\nTrain size: {len(X_train)}")
    print(f"Test  size: {len(X_test)}")

    print("\nScoring test split...")
    scored = score_split(X_test, y_test, model, word_vec, char_vec)

    print("\n" + "=" * 70)
    print("Metrics at different thresholds")
    print("=" * 70)
    rows = [summarize_threshold(scored, t) for t in THRESHOLDS_TO_REPORT]
    summary_df = pd.DataFrame(rows)
    print(summary_df.to_string(index=False))

    # Use 0.50 as the main analysis threshold (matches current inference)
    main_threshold = 0.50

    print("\n" + "=" * 70)
    print(f"Top {TOP_N} FALSE POSITIVES at threshold {main_threshold}")
    print("(true label = 0, predicted = 1)")
    print("=" * 70)
    fps = top_false_positives(scored, main_threshold, TOP_N)
    for i, row in fps.iterrows():
        print(f"p={row['crisis_probability']:.4f} | {row['text'][:160]}")
    print(f"\nTotal false positives at {main_threshold}: "
          f"{len(scored[(scored['true_label']==0) & (scored['crisis_probability']>=main_threshold)])}")

    print("\n" + "=" * 70)
    print(f"Top {TOP_N} FALSE NEGATIVES at threshold {main_threshold}")
    print("(true label = 1, predicted = 0)")
    print("=" * 70)
    fns = top_false_negatives(scored, main_threshold, TOP_N)
    for i, row in fns.iterrows():
        print(f"p={row['crisis_probability']:.4f} | {row['text'][:160]}")
    print(f"\nTotal false negatives at {main_threshold}: "
          f"{len(scored[(scored['true_label']==1) & (scored['crisis_probability']<main_threshold)])}")

    print("\n" + "=" * 70)
    print("Most common words in FALSE POSITIVES")
    print("=" * 70)
    fp_texts = scored[
        (scored["true_label"] == 0) &
        (scored["crisis_probability"] >= main_threshold)
    ]["text"].tolist()
    for word, count in most_common_words(fp_texts):
        print(f"{word:20s} {count}")

    # Save the full scored set for further analysis
    out_path = os.path.join(CURRENT_DIR, "false_positive_analysis.csv")
    scored.to_csv(out_path, index=False)
    print(f"\nFull scored split saved to: {out_path}")
    print("Open it in Excel and sort by crisis_probability descending "
          "to manually inspect more examples.")


if __name__ == "__main__":
    main()