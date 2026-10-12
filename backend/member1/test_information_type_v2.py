"""
test_information_type_v2.py

Compares v1 (trained on CrisisLex) and v2 (trained on curated data)
on a small probe set of sentences.

This is a diagnostic script, not a benchmark. Use it to spot-check
before deploying v2.
"""

import os
import joblib
from scipy.sparse import hstack

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "models"))


def _load_pair(prefix):
    model = joblib.load(os.path.join(MODEL_DIR, f"{prefix}_classifier{'_v2' if prefix.startswith('information_type') and prefix == 'information_type' else ''}.pkl"))
    return model


# Simpler: load explicitly.

def load_v1():
    return (
        joblib.load(os.path.join(MODEL_DIR, "information_type_classifier.pkl")),
        joblib.load(os.path.join(MODEL_DIR, "information_type_word_vectorizer.pkl")),
        joblib.load(os.path.join(MODEL_DIR, "information_type_char_vectorizer.pkl")),
    )


def load_v2():
    return (
        joblib.load(os.path.join(MODEL_DIR, "information_type_classifier_v2.pkl")),
        joblib.load(os.path.join(MODEL_DIR, "information_type_word_vectorizer_v2.pkl")),
        joblib.load(os.path.join(MODEL_DIR, "information_type_char_vectorizer_v2.pkl")),
    )


def predict(text, model, word_vec, char_vec):
    w = word_vec.transform([text])
    c = char_vec.transform([text])
    feats = hstack([w, c])
    return model.predict(feats)[0]


# (sentence, expected label)
PROBES = [
    ("A fire has broken out near Whitefield. Several people are injured and need medical assistance.", "Affected individuals"),
    ("Heavy rains have flooded the roads in the city.", "Infrastructure and utilities"),
    ("Please avoid the flooded area and stay indoors.", "Caution and advice"),
    ("Volunteers are collecting food for the affected families.", "Donations and volunteering"),
    ("Our thoughts are with everyone affected by this tragedy.", "Sympathy and support"),
    ("The fire started around 3 PM near the industrial area.", "Other Useful Information"),
    ("Two children were rescued from the burning house.", "Affected individuals"),
    ("Power supply has been restored in most parts of the city.", "Infrastructure and utilities"),
    ("Residents should evacuate low-lying areas immediately.", "Caution and advice"),
    ("Donations of blankets and clothes are urgently needed.", "Donations and volunteering"),
    ("Deeply saddened by the loss of lives in the disaster.", "Sympathy and support"),
    ("Authorities have confirmed the number of casualties.", "Other Useful Information"),
    ("Five workers were injured in the factory accident.", "Affected individuals"),
    ("The main highway is closed because of a landslide.", "Infrastructure and utilities"),
    ("Do not consume food that has been exposed to floodwater.", "Caution and advice"),
    ("NGOs have come forward to help with the relief effort.", "Donations and volunteering"),
    ("Wishing a speedy recovery to all those injured.", "Sympathy and support"),
    ("A helpline number has been set up for affected residents.", "Other Useful Information"),
    ("Several families have lost their homes in the fire.", "Affected individuals"),
    ("The water treatment plant was damaged by the flood.", "Infrastructure and utilities"),
    ("Farmers are advised to protect their crops from the storm.", "Caution and advice"),
    ("A blood donation camp has been set up for the injured.", "Donations and volunteering"),
    ("The community is united in grief after the accident.", "Sympathy and support"),
    ("An investigation has been launched into the cause.", "Other Useful Information"),
    ("People are sick due to contaminated drinking water.", "Affected individuals"),
    ("Several roads have been washed away by floodwaters.", "Infrastructure and utilities"),
    ("Please do not spread unverified information.", "Caution and advice"),
    ("People are donating generously to the relief effort.", "Donations and volunteering"),
    ("Our hearts go out to everyone affected.", "Sympathy and support"),
    ("Relief materials are being transported by helicopter.", "Other Useful Information"),
        # The original failing inputs from the pipeline
    ("A fire broke out in Mumbai. People are injured and need medical help.", "Affected individuals"),
    ("A fire broke out. People are injured.", "Affected individuals"),
    ("A fire broke out in Mumbai.", "Affected individuals"),
    ("There is a fire in Whitefield. People need medical help.", "Affected individuals"),
    ("Fire in Mumbai, people injured, need medical help.", "Affected individuals"),
]


def run(label, model, word_vec, char_vec):
    correct = 0
    print("=" * 70)
    print(f"{label}")
    print("=" * 70)
    for text, expected in PROBES:
        pred = predict(text, model, word_vec, char_vec)
        ok = "OK " if pred == expected else "MISS"
        if pred == expected:
            correct += 1
        print(f"{ok} | expected: {expected:30s} | got: {pred:30s} | {text[:60]}")
    print(f"\n{label} correct: {correct}/{len(PROBES)} = {correct/len(PROBES):.2%}\n")
    return correct


def main():
    print("Loading v1 (CrisisLex-trained) ...")
    v1_model, v1_word, v1_char = load_v1()

    print("Loading v2 (curated-trained) ...\n")
    v2_model, v2_word, v2_char = load_v2()

    v1_correct = run("v1 (CrisisLex)", v1_model, v1_word, v1_char)
    v2_correct = run("v2 (curated)", v2_model, v2_word, v2_char)

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"v1 correct: {v1_correct}/{len(PROBES)} = {v1_correct/len(PROBES):.2%}")
    print(f"v2 correct: {v2_correct}/{len(PROBES)} = {v2_correct/len(PROBES):.2%}")


if __name__ == "__main__":
    main()