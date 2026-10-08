import pandas as pd
import joblib

from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


# -----------------------------------------
# 1. Paths
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "crisissense_india_environment_50k.csv"

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)


# -----------------------------------------
# 2. Load dataset
# -----------------------------------------

df = pd.read_csv(DATA_PATH)

df = df.dropna(subset=["text", "incident_type"])

df["text"] = df["text"].astype(str)
df["incident_type"] = df["incident_type"].astype(str)


# -----------------------------------------
# 3. Remove exact duplicate rows
# -----------------------------------------

df = df.drop_duplicates(
    subset=["text", "incident_type"]
)

print("\nDataset shape:", df.shape)

print("\nClass distribution:")
print(df["incident_type"].value_counts())


# -----------------------------------------
# 4. Features and target
# -----------------------------------------

X = df["text"]
y = df["incident_type"]


# -----------------------------------------
# 5. Train-test split
# -----------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# -----------------------------------------
# 6. TF-IDF
# -----------------------------------------

vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 1),
    sublinear_tf=True,
    min_df=2,
    max_df=0.98
)

X_train_tfidf = vectorizer.fit_transform(X_train)

X_test_tfidf = vectorizer.transform(X_test)


# -----------------------------------------
# 7. Train Linear SVM
# -----------------------------------------

model = LinearSVC(
    C=1.5,
    class_weight="balanced",
    random_state=42,
    max_iter=5000
)

model.fit(
    X_train_tfidf,
    y_train
)


# -----------------------------------------
# 8. Evaluation
# -----------------------------------------

y_pred = model.predict(
    X_test_tfidf
)

accuracy = accuracy_score(
    y_test,
    y_pred
)

print("\n========== Incident Type Classifier ==========")

print(
    "\nAccuracy on random held-out synthetic data:",
    round(accuracy, 4)
)

print("\nClassification Report:")

print(
    classification_report(
        y_test,
        y_pred,
        digits=4
    )
)

print("\nConfusion Matrix:")

print(
    confusion_matrix(
        y_test,
        y_pred
    )
)


# -----------------------------------------
# 9. Save model and vectorizer
# -----------------------------------------

joblib.dump(
    model,
    MODEL_DIR / "incident_type_classifier.pkl"
)

joblib.dump(
    vectorizer,
    MODEL_DIR / "incident_type_vectorizer.pkl"
)

print("\nModel saved successfully.")


# -----------------------------------------
# 10. Test examples
# -----------------------------------------

test_cases = [
    "A fire has broken out near Whitefield. Several people are injured.",
    "Massive flooding has affected several streets in RR Nagar.",
    "Strong earthquake tremors were felt across the city.",
    "A landslide has blocked the highway after heavy rainfall.",
    "A powerful explosion occurred at an industrial facility.",
    "A multi-storey building suddenly collapsed.",
    "Several vehicles were involved in a major road collision.",
    "A severe cyclone is approaching the coastal region.",
    "A wildfire is spreading rapidly through the forest.",
    "A chemical leak has been reported at an industrial site.",
    "Heavy rain near Whitefield"
]


print("\n========== Test Predictions ==========")

for text in test_cases:

    vector = vectorizer.transform(
        [text]
    )

    prediction = model.predict(
        vector
    )[0]

    print("\nText:", text)
    print("Incident Type:", prediction)

# -----------------------------------------
# 11. Diagnostic test
# -----------------------------------------

diagnostic_cases = [
    "heavy rain has been reported in Bengaluru",
    "heavy rainfall has been reported in Bengaluru",
    "continuous heavy rain in Whitefield",
    "very heavy rainfall in Whitefield",
    "heavy rain is affecting Bengaluru",
    "heavy rain is causing flooding in Bengaluru",
    "heavy rain has flooded several roads",
    "flooding caused by heavy rain",
    "landslide occurred after heavy rainfall",
    "heavy rain triggered a landslide",
    "mudslide after heavy rain",
]

print("\n========== Diagnostic Predictions ==========")

for text in diagnostic_cases:

    vector = vectorizer.transform([text])

    prediction = model.predict(vector)[0]

    scores = model.decision_function(vector)[0]

    ranked_indices = scores.argsort()[::-1]

    print("\nText:", text)
    print("Prediction:", prediction)

    print("Top 5 classes:")

    for index in ranked_indices[:5]:

        print(
            " ",
            model.classes_[index],
            "->",
            round(float(scores[index]), 4)
        )

