from transformers import pipeline


# ==========================================
# LOAD ZERO-SHOT SEVERITY MODEL
# ==========================================

severity_model = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)


# ==========================================
# SEVERITY LABELS
# ==========================================

severity_labels = [
    "low severity emergency",
    "medium severity emergency",
    "high severity emergency",
    "critical life-threatening emergency"
]


# ==========================================
# SEVERITY PREDICTION
# ==========================================

def extract_severity(text):

    result = severity_model(
        text,
        candidate_labels=severity_labels,
        multi_label=False
    )

    predicted_label = result["labels"][0]

    if predicted_label == "low severity emergency":
        return "LOW"

    elif predicted_label == "medium severity emergency":
        return "MEDIUM"

    elif predicted_label == "high severity emergency":
        return "HIGH"

    elif predicted_label == "critical life-threatening emergency":
        return "CRITICAL"

    return "UNKNOWN"


# ==========================================
# TEST
# ==========================================

if __name__ == "__main__":

    text = input("\nEnter crisis text: ")

    severity = extract_severity(text)

    print("\nSeverity:", severity)