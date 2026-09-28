import joblib
from scipy.sparse import hstack

from .severity import extract_severity
from .needs_extractor import extract_needs
from .location_extractor import extract_locations


# ==================================================
# 1. Load Crisis Detection Model
# ==================================================

crisis_model = joblib.load(
    "models/crisis_classifier.pkl"
)

crisis_vectorizer = joblib.load(
    "models/tfidf_vectorizer.pkl"
)


# ==================================================
# 2. Load Information Type Model
# ==================================================

info_model = joblib.load(
    "models/information_type_classifier.pkl"
)

word_vectorizer = joblib.load(
    "models/information_type_word_vectorizer.pkl"
)

char_vectorizer = joblib.load(
    "models/information_type_char_vectorizer.pkl"
)


# ==================================================
# 3. Load Incident Type Model
# ==================================================

incident_model = joblib.load(
    "models/incident_type_classifier.pkl"
)

incident_vectorizer = joblib.load(
    "models/incident_type_vectorizer.pkl"
)


# ==================================================
# 4. Text Cleaning
# ==================================================

def clean_text(text):
    return text.lower()


# ==================================================
# 5. Crisis Detection
# ==================================================

def predict_crisis(text):

    cleaned = clean_text(text)

    vector = crisis_vectorizer.transform(
        [cleaned]
    )

    prediction = crisis_model.predict(
        vector
    )[0]

    return True if prediction == 1 else False


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

    is_crisis = predict_crisis(text)

    incident_type = predict_incident_type(text)

    information_type = predict_information_type(text)

    severity = extract_severity(text)

    needs = extract_needs(
        information_type,
        text
    )

    locations = extract_locations(text)

    result = {

        "is_crisis": is_crisis,

        "incident_type": incident_type,

        "information_type": information_type,

        "severity": severity,

        "needs": needs,

        "locations": locations
    }

    return result


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