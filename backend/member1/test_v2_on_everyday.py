"""
Score a small set of everyday non-crisis sentences with the v2 model.
This does NOT touch pipeline.py — it loads v2 directly.

If v2 correctly assigns low crisis probability to all of these,
the model itself is now behaving; we can then safely wire it into
pipeline.py and remove the weather-rule band-aid.
"""

import os
import joblib
from scipy.sparse import hstack

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "models"))

model = joblib.load(os.path.join(MODEL_DIR, "crisis_classifier_v2.pkl"))
word_vec = joblib.load(os.path.join(MODEL_DIR, "tfidf_vectorizer_v2.pkl"))
char_vec = joblib.load(os.path.join(MODEL_DIR, "crisis_char_vectorizer_v2.pkl"))


def score(text):
    cleaned = text.lower()
    w = word_vec.transform([cleaned])
    c = char_vec.transform([cleaned])
    feats = hstack([w, c], format="csr")
    prob = model.predict_proba(feats)[0][1]
    return prob


EVERYDAY = [
    "I don't like going to college.",
    "I do not enjoy attending my university lectures.",
    "The weather is nice today.",
    "I am going to the market to buy vegetables.",
    "My favourite cricket team won the match yesterday.",
    "I have an exam tomorrow morning.",
    "I watched a great movie last night.",
    "Hey, how are you doing?",
    "I love listening to music while working.",
    "The prices have gone up again.",
    "My cat is sleeping on the couch.",
    "I need a haircut.",
    "I'm learning to play the guitar.",
    "I prefer tea over coffee.",
    "I'm planning a trip to Goa next month.",
]

REAL_CRISES = [
    "A fire has broken out near Whitefield. Several people are injured and need medical assistance.",
    "Heavy rain in Mysuru has flooded the roads and blocked traffic.",
    "Earthquake of magnitude 5.6 struck near Delhi, buildings damaged.",
    "Train derailment in Odisha, many injured, rescue operations underway.",
    "Cyclone warning issued for coastal Andhra Pradesh, evacuations ordered.",
]

print("=" * 70)
print("EVERYDAY NON-CRISIS SENTENCES (want LOW probability)")
print("=" * 70)
for text in EVERYDAY:
    p = score(text)
    flag = " <-- BAD" if p >= 0.5 else ""
    print(f"p={p:.4f}{flag}  {text}")

print()
print("=" * 70)
print("REAL CRISIS SENTENCES (want HIGH probability)")
print("=" * 70)
for text in REAL_CRISES:
    p = score(text)
    flag = " <-- BAD" if p < 0.5 else ""
    print(f"p={p:.4f}{flag}  {text}")