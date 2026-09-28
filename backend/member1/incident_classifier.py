import pandas as pd
import os
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from scipy.sparse import hstack


# Paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_PATH = os.path.abspath(
    os.path.join(
        CURRENT_DIR,
        "..",
        "data",
        "CrisisSense_Master_Dataset.csv"
    )
)

MODEL_DIR = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "models")
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "information_type_classifier.pkl"
)

WORD_VECTORIZER_PATH = os.path.join(
    MODEL_DIR,
    "information_type_word_vectorizer.pkl"
)

CHAR_VECTORIZER_PATH = os.path.join(
    MODEL_DIR,
    "information_type_char_vectorizer.pkl"
)


# Load dataset
print("Loading dataset...")

df = pd.read_csv(DATA_PATH)

print("Dataset shape:", df.shape)


# Required classes
classes = [
    "Affected individuals",
    "Caution and advice",
    "Donations and volunteering",
    "Infrastructure and utilities",
    "Other Useful Information",
    "Sympathy and support"
]


# Keep required classes
df = df[
    df["Information Type"].isin(classes)
].copy()


# Remove empty text
df = df.dropna(subset=["Clean_Text"])

df = df[
    df["Clean_Text"].str.strip() != ""
].copy()


# Input and target
X = df["Clean_Text"]
y = df["Information Type"]


print("\nClass distribution:")
print(y.value_counts())


# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


# ------------------------------------------------
# WORD-LEVEL TF-IDF
# ------------------------------------------------

word_vectorizer = TfidfVectorizer(
    max_features=30000,
    ngram_range=(1, 2),
    sublinear_tf=True,
    min_df=2,
    max_df=0.95
)

X_train_word = word_vectorizer.fit_transform(X_train)

X_test_word = word_vectorizer.transform(X_test)


# ------------------------------------------------
# CHARACTER-LEVEL TF-IDF
# ------------------------------------------------

char_vectorizer = TfidfVectorizer(
    analyzer="char",
    ngram_range=(3, 5),
    max_features=20000,
    min_df=2,
    sublinear_tf=True
)

X_train_char = char_vectorizer.fit_transform(X_train)

X_test_char = char_vectorizer.transform(X_test)


# ------------------------------------------------
# COMBINE FEATURES
# ------------------------------------------------

X_train_combined = hstack([
    X_train_word,
    X_train_char
])

X_test_combined = hstack([
    X_test_word,
    X_test_char
])


print("\nCombined training features:",
      X_train_combined.shape)


# ------------------------------------------------
# LINEAR SVM
# ------------------------------------------------

model = LinearSVC(
    C=1.5,
    class_weight="balanced"
)


print("\nTraining combined TF-IDF + Linear SVM...")

model.fit(
    X_train_combined,
    y_train
)


# Prediction
y_pred = model.predict(
    X_test_combined
)


# ------------------------------------------------
# EVALUATION
# ------------------------------------------------

accuracy = accuracy_score(
    y_test,
    y_pred
)

print("\n" + "=" * 60)
print("COMBINED TF-IDF + LINEAR SVM PERFORMANCE")
print("=" * 60)

print("\nAccuracy:", accuracy)

print("\nClassification Report:")

print(
    classification_report(
        y_test,
        y_pred
    )
)

print("\nConfusion Matrix:")

print(
    confusion_matrix(
        y_test,
        y_pred
    )
)


# ------------------------------------------------
# SAVE
# ------------------------------------------------

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)

joblib.dump(
    model,
    MODEL_PATH
)

joblib.dump(
    word_vectorizer,
    WORD_VECTORIZER_PATH
)

joblib.dump(
    char_vectorizer,
    CHAR_VECTORIZER_PATH
)


print("\nModel saved:")
print(MODEL_PATH)

print("\nWord vectorizer saved:")
print(WORD_VECTORIZER_PATH)

print("\nCharacter vectorizer saved:")
print(CHAR_VECTORIZER_PATH)

print("\nTraining completed!")