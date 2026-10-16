import re
import joblib
from scipy.sparse import hstack
from pathlib import Path

from .severity import extract_severity
from .needs_extractor import extract_needs
from .location_extractor import extract_locations

# ==================================================
# Configuration
# ==================================================

# Probability threshold for classifying a message as crisis-related.
# Chosen from the v2 validation results: precision/recall are balanced
# around 0.50 and everyday non-crisis sentences score well below it.
# If you later retune this, change it in ONE place — here.
CRISIS_THRESHOLD = 0.50

OUT_OF_SCOPE_MESSAGE = (
    "This message is out of scope for crisis analysis."
)

# ==================================================
# Project Paths
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
print("Loading models from:", MODEL_DIR.resolve())

# ==================================================
# 1. Load Crisis Detection Model (v2)
# ==================================================

crisis_model = joblib.load(
    MODEL_DIR / "crisis_classifier_v2.pkl"
)

crisis_vectorizer = joblib.load(
    MODEL_DIR / "tfidf_vectorizer_v2.pkl"
)

crisis_char_vectorizer = joblib.load(
    MODEL_DIR / "crisis_char_vectorizer_v2.pkl"
)

# ==================================================
# 2. Load Information Type Model
# ==================================================

info_model = joblib.load(
    MODEL_DIR / "information_type_classifier_v2.pkl"
)

word_vectorizer = joblib.load(
    MODEL_DIR / "information_type_word_vectorizer_v2.pkl"
)

char_vectorizer = joblib.load(
    MODEL_DIR / "information_type_char_vectorizer_v2.pkl"
)

# ==================================================
# 3. Load Incident Type Model
# ==================================================

incident_model = joblib.load(
    MODEL_DIR / "incident_type_classifier.pkl"
)

incident_vectorizer = joblib.load(
    MODEL_DIR / "incident_type_vectorizer.pkl"
)

# Ensure scikit-learn version interoperability (e.g. multi_class attribute)
for _loaded_m in (crisis_model, info_model, incident_model):
    if hasattr(_loaded_m, "predict_proba") and not hasattr(_loaded_m, "multi_class"):
        _loaded_m.multi_class = "auto"


# ==================================================
# 4. Text Cleaning & Domain Preprocessing
# ==================================================

def clean_text(text):
    text = str(text).lower()
    # Normalize common South Asian disaster terms (e.g. waterlogging, water-logging, inundation)
    # into the flood domain so crisis detection and incident classification recognize flood emergencies accurately.
    text = re.sub(r"\bwater[\s\-_]?logg?(?:ed|ing)?\b", "waterlogging flood", text)
    text = re.sub(r"\binundat(?:ed|ion)\b", "inundation flood", text)
    return text


# ==================================================
# 5. Crisis Detection
# ==================================================

def predict_crisis(text):
    """
    Returns (is_crisis: bool, crisis_probability: float).

    Uses CRISIS_THRESHOLD (not sklearn's implicit 0.5 via .predict())
    so the decision boundary is explicit and changeable in one place.
    """
    cleaned = clean_text(text)

    word_features = crisis_vectorizer.transform([cleaned])
    char_features = crisis_char_vectorizer.transform([cleaned])

    features = hstack(
        [word_features, char_features],
        format="csr"
    )

    probabilities = crisis_model.predict_proba(features)[0]
    classes = list(crisis_model.classes_)

    if 1 in classes:
        crisis_probability = float(probabilities[classes.index(1)])
    else:
        crisis_probability = 0.0

    is_crisis = crisis_probability >= CRISIS_THRESHOLD

    print(f"Crisis probability: {crisis_probability:.4f}")
    print(f"Threshold: {CRISIS_THRESHOLD}")
    print(f"Prediction: {is_crisis}")

    return is_crisis, crisis_probability


# ==================================================
# 6. Information Type Prediction
# ==================================================

def predict_information_type(text):
    cleaned = clean_text(text)

    word_features = word_vectorizer.transform([cleaned])
    char_features = char_vectorizer.transform([cleaned])

    features = hstack([word_features, char_features])

    return info_model.predict(features)[0]


# ==================================================
# 7. Incident Type Prediction
# ==================================================

def predict_incident_type(text):
    cleaned = clean_text(text)
    vector = incident_vectorizer.transform([cleaned])
    return incident_model.predict(vector)[0]


# ==================================================
# 8. Complete Crisis Analysis
# ==================================================

def _non_crisis_response(message=OUT_OF_SCOPE_MESSAGE,
                         probability=None):
    return {
        "is_crisis": False,
        "incident_type": None,
        "information_type": None,
        "severity": None,
        "needs": [],
        "locations": [],
        "crisis_probability": probability,
        "message": message,
    }


def analyze_crisis(text):
    # Empty / missing text: this is the media-only case.
    # Do NOT report it as a verified non-crisis; report it as unanalyzed.
    if text is None or not str(text).strip():
        return _non_crisis_response(
            message=(
                "No text provided. Text-based crisis analysis "
                "is unavailable for this submission."
            ),
            probability=None,
        )

    is_crisis, probability = predict_crisis(text)

    # If not crisis-related: stop immediately. Do NOT call the
    # incident / information-type / severity / needs / location modules.
    if not is_crisis:
        return _non_crisis_response(probability=probability)

    # Only here do we run the downstream modules.
    incident_type = predict_incident_type(text)
    information_type = predict_information_type(text)
    severity = extract_severity(text)
    needs = extract_needs(information_type, text)
    locations = extract_locations(text)

    return {
        "is_crisis": True,
        "incident_type": incident_type,
        "information_type": information_type,
        "severity": severity,
        "needs": needs,
        "locations": locations,
        "crisis_probability": probability,
        "message": None,
    }


# ==================================================
# 9. Test Pipeline
# ==================================================

if __name__ == "__main__":
    text = input("\nEnter crisis text: ")
    result = analyze_crisis(text)

    print("\n========== CrisisSense Analysis ==========")
    print("\nCrisis:", result["is_crisis"])
    print("Crisis Probability:", result["crisis_probability"])
    print("Message:", result["message"])
    print("Incident Type:", result["incident_type"])
    print("Information Type:", result["information_type"])
    print("Severity:", result["severity"])
    print("Needs:", result["needs"])

    print("\nLocations:")
    if result["locations"]:
        for location in result["locations"]:
            print("Location:", location["text"])
            print("Display Name:", location["display_name"])
            print("City:", location["city"])
            print("State:", location["state"])
            print("Latitude:", location["latitude"])
            print("Longitude:", location["longitude"])
    else:
        print("No location detected.")