import pandas as pd
import os
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


# Paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data", "CrisisSense_Master_Dataset.csv")
)

MODEL_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "models")
)

MODEL_PATH = os.path.join(MODEL_DIR, "crisis_classifier.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl")


# Load dataset
print("Loading dataset...")

df = pd.read_csv(DATA_PATH)

print("Dataset shape:", df.shape)


# Create binary crisis label
df = df[
    df["Informativeness"].isin([
        "Related and informative",
        "Related - but not informative",
        "Not related"
    ])
].copy()

df["crisis_label"] = df["Informativeness"].apply(
    lambda x: 0 if x == "Not related" else 1
)


# Input and output
X = df["Clean_Text"]
y = df["crisis_label"]


# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


# TF-IDF
vectorizer = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2)
)

X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)


# Train model
model = LogisticRegression(
    max_iter=1000
)

model.fit(X_train_tfidf, y_train)


# Prediction
y_pred = model.predict(X_test_tfidf)


# Evaluation
accuracy = accuracy_score(y_test, y_pred)

print("\nAccuracy:", accuracy)

print("\nClassification Report:")
print(classification_report(
    y_test,
    y_pred,
    target_names=["Not Crisis", "Crisis"]
))

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))


# Save model and vectorizer
os.makedirs(MODEL_DIR, exist_ok=True)

joblib.dump(model, MODEL_PATH)
joblib.dump(vectorizer, VECTORIZER_PATH)

print("\nModel saved:")
print(MODEL_PATH)

print("\nVectorizer saved:")
print(VECTORIZER_PATH)

print("\nCrisis classifier training completed!")