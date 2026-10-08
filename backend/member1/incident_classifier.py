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
# ============================================================
# CRISISSENSE-SPECIFIC AUGMENTATION DATA
# ============================================================

augmentation_data = [

    # --------------------------------------------------------
    # AFFECTED INDIVIDUALS
    # --------------------------------------------------------

    ("Several people are injured and need medical assistance.",
     "Affected individuals"),

    ("Several people are injured and require medical attention.",
     "Affected individuals"),

    ("People injured in the fire need medical assistance.",
     "Affected individuals"),

    ("Several victims were injured in the incident.",
     "Affected individuals"),

    ("Several residents were injured during the fire.",
     "Affected individuals"),

    ("People affected by the incident have suffered injuries.",
     "Affected individuals"),

    ("Several people were hurt and need medical care.",
     "Affected individuals"),

    ("Residents injured in the accident need medical help.",
     "Affected individuals"),

    ("Several victims require immediate medical attention.",
     "Affected individuals"),

    ("People injured during the disaster require treatment.",
     "Affected individuals"),

    ("Multiple people have been injured in the incident.",
     "Affected individuals"),

    ("Several residents were hurt and need treatment.",
     "Affected individuals"),

    ("People trapped in the building are injured.",
     "Affected individuals"),

    ("Several injured people are waiting for medical care.",
     "Affected individuals"),

    ("The incident has left several people injured.",
     "Affected individuals"),

    ("Several people suffered injuries during the emergency.",
     "Affected individuals"),

    ("Victims of the incident have sustained injuries.",
     "Affected individuals"),

    ("Several people were injured and taken for medical care.",
     "Affected individuals"),

    ("Many residents were injured in the disaster.",
     "Affected individuals"),

    ("Injured victims need immediate medical attention.",
     "Affected individuals"),


    # --------------------------------------------------------
    # DONATIONS AND VOLUNTEERING
    # --------------------------------------------------------

    ("Volunteers are needed to help affected families.",
     "Donations and volunteering"),

    ("Donations are being collected for disaster victims.",
     "Donations and volunteering"),

    ("People are requesting financial assistance for affected families.",
     "Donations and volunteering"),

    ("Volunteers are helping distribute supplies.",
     "Donations and volunteering"),

    ("Donations are needed to support affected residents.",
     "Donations and volunteering"),

    ("Volunteers are needed at the relief centre.",
     "Donations and volunteering"),

    ("People are asking for donations to support victims.",
     "Donations and volunteering"),

    ("Financial assistance is being requested for affected families.",
     "Donations and volunteering"),

    ("Volunteers are collecting essential supplies.",
     "Donations and volunteering"),

    ("Donations are being requested for emergency relief.",
     "Donations and volunteering"),

    ("People are organizing relief donations for victims.",
     "Donations and volunteering"),

    ("Volunteers are assisting with disaster relief efforts.",
     "Donations and volunteering"),

    ("The community is collecting donations for affected people.",
     "Donations and volunteering"),

    ("Volunteers are distributing food and supplies.",
     "Donations and volunteering"),

    ("People are seeking financial support for disaster victims.",
     "Donations and volunteering"),

    ("Volunteers are helping families affected by the disaster.",
     "Donations and volunteering"),

    ("Donations are needed to provide relief supplies.",
     "Donations and volunteering"),

    ("Community members are volunteering to support relief efforts.",
     "Donations and volunteering"),

    ("Relief workers are requesting donations for affected families.",
     "Donations and volunteering"),

    ("Volunteers are organizing aid for disaster-affected residents.",
     "Donations and volunteering"),
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


for word in ["medical", "injured", "assistance"]:

    print("\n" + "=" * 50)
    print("WORD:", word)
    print("=" * 50)

    matching_rows = df[
        df["Clean_Text"].str.contains(
            word,
            case=False,
            na=False
        )
    ]

    print(
        matching_rows["Information Type"].value_counts()
    )
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
# ============================================================
# ADD AUGMENTATION ONLY TO TRAINING DATA
# ============================================================

augmentation_df = pd.DataFrame(
    augmentation_data,
    columns=["Clean_Text", "Information Type"]
)

X_train = pd.concat(
    [
        X_train.reset_index(drop=True),
        augmentation_df["Clean_Text"]
    ],
    ignore_index=True
)

y_train = pd.concat(
    [
        y_train.reset_index(drop=True),
        augmentation_df["Information Type"]
    ],
    ignore_index=True
)

print("\nAugmentation examples added:", len(augmentation_df))

print("\nTraining class distribution after augmentation:")
print(y_train.value_counts())

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
test_texts = [

    "A fire has broken out near Whitefield. Several people are injured and need medical assistance.",

    "A fire has broken out. Several people are injured.",

    "Several people are injured and need medical assistance.",

    "Several people need medical assistance after the fire.",

    "People are injured and need medical help.",

    "People are injured in the fire and need help.",

    "Several victims are injured and require medical assistance.",

    "Several residents are injured and require medical attention.",

    "The fire has affected several people who need medical assistance."

]

print("\n========== INFORMATION TYPE TESTS ==========")

for text in test_texts:

    word_vector = word_vectorizer.transform([text])

    char_vector = char_vectorizer.transform([text])

    combined_vector = hstack([
        word_vector,
        char_vector
    ])

    prediction = model.predict(
        combined_vector
    )[0]

    print("\nText:", text)
    print("Prediction:", prediction)


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