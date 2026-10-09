import joblib
from scipy.sparse import hstack
from pathlib import Path

from .severity import extract_severity
from .needs_extractor import extract_needs
from .location_extractor import extract_locations

# ==================================================
# Project Paths
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"
print("Loading models from:", MODEL_DIR.resolve())
# ==================================================
# 1. Load Crisis Detection Model
# ==================================================

crisis_model = joblib.load(
    MODEL_DIR / "crisis_classifier.pkl"
)

crisis_vectorizer = joblib.load(
    MODEL_DIR / "tfidf_vectorizer.pkl"
)

crisis_char_vectorizer = joblib.load(
    MODEL_DIR / "crisis_char_vectorizer.pkl"
)


# ==================================================
# 2. Load Information Type Model
# ==================================================

info_model = joblib.load(
    MODEL_DIR / "information_type_classifier.pkl"
)

word_vectorizer = joblib.load(
    MODEL_DIR / "information_type_word_vectorizer.pkl"
)

char_vectorizer = joblib.load(
    MODEL_DIR / "information_type_char_vectorizer.pkl"
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


# ==================================================
# 4. Text Cleaning
# ==================================================

def clean_text(text):
    return text.lower()


# ==================================================
# 5. Crisis Detection
# ==================================================


def is_clearly_benign_weather(text):
    cleaned = " ".join(text.lower().split())

    positive_weather_phrases = [
        # General pleasant weather
        "sunny",
        "like",
        "lovely",
        "love",
        "sunshine",
        "clear sky",
        "clear skies",
        "blue sky",
        "blue skies",
        "nice weather",
        "good weather",
        "pleasant weather",
        "beautiful weather",
        "fair weather",
        "mild weather",
        "calm weather",
        "normal weather",
        "lovely weather",
        "warm weather",
        "cool weather",
        "fresh air",
        "gentle breeze",
        "cool breeze",
        "light breeze",
        "partly cloudy",
        "mostly sunny",
        "cloudless sky",
        "warm sunshine",
        "light drizzle",
        "comfortable temperature",

        # Positive everyday expressions
        "beautiful day",
        "lovely day",
        "pleasant day",
        "peaceful day",
        "nice day",
        "good day",
        "great day",
        "feeling good",
        "doing well",
        "all good",
        "no problem",
        "everything fine",
    ]

    hazard_terms = [
        "flood", "flooding", "flash flood", "disaster",
        "emergency", "injured", "injuries", "trapped",
        "evacuate", "evacuation", "damage", "destroyed",
        "warning", "dangerous", "landslide", "cyclone",
        "storm", "wildfire", "casualties", "rescue",
        "heavy rainfall", "overflow", "collapsed",
        "collapse", "earthquake", "tsunami", "explosion",
        "fire", "drowning", "missing people", "stranded",
        "power outage", "building damage", "road blocked",
        "medical assistance", "need help", "urgent help",
        "people trapped", "homes destroyed"
    ]

    has_positive_phrase = any(
        phrase in cleaned
        for phrase in positive_weather_phrases
    )

    has_hazard_term = any(
        term in cleaned
        for term in hazard_terms
    )

    return has_positive_phrase and not has_hazard_term


def predict_crisis(text):
    cleaned = clean_text(text)

    word_features = crisis_vectorizer.transform([cleaned])
    char_features = crisis_char_vectorizer.transform([cleaned])

    features = hstack(
        [word_features, char_features],
        format="csr"
    )

    prediction = crisis_model.predict(features)[0]

    print("Raw crisis prediction:", prediction)

    if hasattr(crisis_model, "predict_proba"):
        probabilities = crisis_model.predict_proba(features)[0]
        print("Class labels:", crisis_model.classes_)
        print("Class probabilities:", probabilities)

    return bool(prediction == 1)
# ==================================================
# 6. Information Type Prediction
# ==================================================

def predict_information_type(text):

    cleaned = clean_text(text)

    word_features = word_vectorizer.transform(
        [cleaned]
    )

    char_features = char_vectorizer.transform(
        [cleaned]
    )

    features = hstack([
        word_features,
        char_features
    ])

    prediction = info_model.predict(
        features
    )[0]

    return prediction


# ==================================================
# 7. Incident Type Prediction
# ==================================================

def predict_incident_type(text):

    cleaned = clean_text(text)

    vector = incident_vectorizer.transform(
        [cleaned]
    )

    prediction = incident_model.predict(
        vector
    )[0]

    return prediction


# ==================================================
# 8. Complete Crisis Analysis
# ==================================================

def analyze_crisis(text):

    # Handle clearly positive, harmless weather statements.
    if is_clearly_benign_weather(text):
        return {
            "is_crisis": False,
            "incident_type": None,
            "information_type": None,
            "severity": None,
            "needs": [],
            "locations": []
        }

    is_crisis = predict_crisis(text)

    # Stop if the model identifies it as non-crisis.
    if not is_crisis:
        return {
            "is_crisis": False,
            "incident_type": None,
            "information_type": None,
            "severity": None,
            "needs": [],
            "locations": []
        }

    incident_type = predict_incident_type(text)
    information_type = predict_information_type(text)
    severity = extract_severity(text)

    needs = extract_needs(
        information_type,
        text
    )

    locations = extract_locations(text)

    return {
        "is_crisis": True,
        "incident_type": incident_type,
        "information_type": information_type,
        "severity": severity,
        "needs": needs,
        "locations": locations
    }


# ==================================================
# 9. Test Pipeline
# ==================================================

if __name__ == "__main__":

    text = input(
        "\nEnter crisis text: "
    )

    result = analyze_crisis(text)

    print(
        "\n========== CrisisSense Analysis =========="
    )

    print(
        "\nCrisis:",
        result["is_crisis"]
    )

    print(
        "Incident Type:",
        result["incident_type"]
    )

    print(
        "Information Type:",
        result["information_type"]
    )

    print(
        "Severity:",
        result["severity"]
    )

    print(
        "Needs:",
        result["needs"]
    )

    print("\nLocations:")

    if result["locations"]:

        for location in result["locations"]:

            print(
                "Location:",
                location["text"]
            )

            print(
                "Display Name:",
                location["display_name"]
            )

            print(
                "City:",
                location["city"]
            )

            print(
                "State:",
                location["state"]
            )

            print(
                "Latitude:",
                location["latitude"]
            )

            print(
                "Longitude:",
                location["longitude"]
            )

    else:

        print(
            "No location detected."
        )