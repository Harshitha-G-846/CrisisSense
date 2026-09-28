import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


# -----------------------------------------
# 1. Load dataset
# -----------------------------------------

DATA_PATH = "data/crisissense_incident_type_dataset.csv"

df = pd.read_csv(DATA_PATH)

df = df.dropna(subset=["text", "incident_type"])

df["text"] = df["text"].astype(str)
df["incident_type"] = df["incident_type"].astype(str)


# -----------------------------------------
# 2. Features and target
# -----------------------------------------

X = df["text"]
y = df["incident_type"]


# -----------------------------------------
# 3. Train-test split
# -----------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)


# -----------------------------------------
# 4. TF-IDF
# -----------------------------------------

vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),
    sublinear_tf=True,
    min_df=2
)

X_train_tfidf = vectorizer.fit_transform(X_train)
X_test_tfidf = vectorizer.transform(X_test)


# -----------------------------------------
# 5. Train Linear SVM
# -----------------------------------------

model = LinearSVC(
    C=1.5,
    class_weight="balanced"
)

model.fit(X_train_tfidf, y_train)


# -----------------------------------------
# 6. Evaluation
# -----------------------------------------

y_pred = model.predict(X_test_tfidf)

accuracy = accuracy_score(y_test, y_pred)

print("\n========== Incident Type Classifier ==========")

print("\nAccuracy:", accuracy)

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))


# -----------------------------------------
# 7. Save model and vectorizer
# -----------------------------------------

joblib.dump(
    model,
    "models/incident_type_classifier.pkl"
)

joblib.dump(
    vectorizer,
    "models/incident_type_vectorizer.pkl"
)


# -----------------------------------------
# 8. Test examples
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
    "A chemical leak has been reported at an industrial site."
]

print("\n========== Test Predictions ==========")

for text in test_cases:

    vector = vectorizer.transform([text])

    prediction = model.predict(vector)[0]

    print("\nText:", text)
    print("Incident Type:", prediction)