"""
Prepare CrisisSense_Master_Dataset_v2.csv by:

1. Flagging likely-mislabeled rows in the "Not related" class
   (crisis-text that is labeled 0) and DROPPING them so they don't
   confuse the classifier.
2. Appending a curated set of everyday non-crisis sentences so the
   classifier finally sees what ordinary text looks like.

The original CSV is NEVER modified.
"""

import os
import re
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

ORIGINAL_CSV = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data", "CrisisSense_Master_Dataset.csv")
)
OUTPUT_CSV = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "data", "CrisisSense_Master_Dataset_v2.csv")
)

# -------------------------------------------------------------
# 1. Crisis vocabulary used to detect mislabeled "Not related"
# -------------------------------------------------------------

CRISIS_KEYWORDS = [
    # Events
    "flood", "flooding", "floods", "wildfire", "wildfires",
    "earthquake", "quake", "tsunami", "cyclone", "hurricane",
    "typhoon", "landslide", "mudslide", "avalanche",
    "explosion", "blast", "eruption",
    "derail", "derailment", "train crash", "plane crash",
    "collapsed", "collapse", "burning", "on fire",
    "meteor", "meteorite", "asteroid",
    # Response / consequence words
    "evacuate", "evacuated", "evacuation",
    "rescue", "rescued", "rescuer",
    "casualties", "fatalities", "deaths", "killed",
    "injured", "wounded", "trapped", "stranded", "missing",
    "displaced", "shelter", "relief",
    "emergency", "disaster", "catastrophe",
    "damage", "destroyed", "devastated",
    "warning issued", "alert issued", "evacuation order",
    "oil spill", "chemical leak",
    # Multi-word
    "search and rescue", "state of emergency",
]


def looks_like_crisis(text):
    if not isinstance(text, str):
        return False
    cleaned = text.lower()
    return any(kw in cleaned for kw in CRISIS_KEYWORDS)


# -------------------------------------------------------------
# 2. Curated everyday non-crisis sentences (all label 0)
# -------------------------------------------------------------

EVERYDAY_NEGATIVES = [
    # Weather chit-chat (positive/neutral, NOT hazard)
    "The weather is nice today.",
    "It's a beautiful sunny day.",
    "It looks like it might rain later.",
    "The forecast says it will be cloudy tomorrow.",
    "It's quite hot outside today.",
    "It's a bit chilly this morning.",
    "The sky is clear and blue.",
    "We had lovely weather over the weekend.",
    "I love the cool breeze in the evening.",
    "Perfect weather for a walk in the park.",
    "It rained a little last night.",
    "The sun is shining brightly today.",
    "It's windy but pleasant outside.",
    "I hope it doesn't rain on my birthday.",
    "The monsoon season starts next month.",

    # Personal daily-life statements
    "I am going to the market to buy vegetables.",
    "I need to pick up some groceries after work.",
    "I have an exam tomorrow morning.",
    "I'm studying for my final semester exams.",
    "I watched a great movie last night.",
    "I'm reading a really interesting book.",
    "I went to the gym this morning.",
    "I'm learning to play the guitar.",
    "I cooked dinner for my family yesterday.",
    "I'm meeting my friends for coffee later.",
    "I need to finish my assignment by Friday.",
    "I'm planning a trip to Goa next month.",
    "I just got a new phone.",
    "I love listening to music while working.",
    "My sister is getting married next week.",
    "I have to wake up early tomorrow.",
    "I'm thinking of learning a new language.",
    "I don't like going to college.",
    "I do not enjoy attending my university lectures.",
    "College life is busy but fun.",

    # Sports and entertainment
    "My favourite cricket team won the match yesterday.",
    "I watched the football game last night.",
    "The IPL season starts next month.",
    "I play badminton every weekend.",
    "That movie had a really good ending.",
    "I'm excited for the new season of my favourite show.",
    "I bought tickets for the concert.",
    "The match was really exciting to watch.",
    "I love playing video games on weekends.",
    "The new song is stuck in my head.",

    # Casual greetings and small talk
    "Hey, how are you doing?",
    "Good morning everyone!",
    "Have a great day ahead.",
    "Long time no see, how have you been?",
    "What are your plans for the weekend?",
    "Thanks so much for your help.",
    "Congratulations on your new job!",
    "Happy birthday to my best friend!",
    "Hope you feel better soon.",
    "See you at the meeting tomorrow.",
    "Let me know when you're free to chat.",
    "I'll call you back in a few minutes.",

    # Shopping / commerce / daily errands
    "The new store opens next week.",
    "I got a great deal on shoes yesterday.",
    "The prices have gone up again.",
    "I ordered something online this morning.",
    "I need to pay my electricity bill.",
    "The traffic was terrible this morning.",
    "I missed the bus and had to walk.",
    "The metro was crowded today.",
    "I'm waiting at the railway station.",

    # Food and restaurants
    "I tried a new restaurant yesterday.",
    "The food at that place is amazing.",
    "I made pasta for dinner.",
    "Do you want to grab lunch together?",
    "I'm craving some ice cream right now.",
    "The coffee at this cafe is really good.",

    # Tech / work / study
    "I have a team meeting at 3 PM.",
    "The project deadline is next Monday.",
    "My laptop needs an update.",
    "I'm learning Python programming.",
    "The internet is slow today.",
    "I need to submit my report by tonight.",
    "Can you review my code later?",
    "I finished the assignment early.",
    "My manager approved my leave request.",
    "I'm working from home today.",

    # Personal opinions / likes-dislikes
    "I really like chocolate.",
    "I don't like waking up early.",
    "I prefer tea over coffee.",
    "My favourite colour is blue.",
    "I enjoy reading mystery novels.",
    "I hate crowded places.",
    "I love spending time with my family.",
    "I think weekends are too short.",
    "I wish I had more free time.",

    # Other everyday chit-chat
    "My cat is sleeping on the couch.",
    "The dog needs a walk.",
    "I planted some flowers in my garden.",
    "The new neighbours seem friendly.",
    "I finally cleaned my room.",
    "I'm redecorating my apartment.",
    "My phone battery is almost dead.",
    "I forgot to charge my laptop.",
    "I need a haircut.",
    "The elevator is out of order again.",
]


def build_curated_negatives():
    rows = []
    for text in EVERYDAY_NEGATIVES:
        rows.append({
            "Clean_Text": text,
            "Informativeness": "Not related",
            "crisis_label": 0,
            "source": "curated_everyday_negative",
        })
    return pd.DataFrame(rows)


def main():
    print("=" * 70)
    print("Preparing CrisisSense_Master_Dataset_v2.csv")
    print("=" * 70)

    df = pd.read_csv(ORIGINAL_CSV)
    print(f"Original rows: {len(df)}")

    # Only keep the three useful informativeness categories
    df = df[df["Informativeness"].isin([
        "Related and informative",
        "Related - but not informative",
        "Not related",
    ])].copy()

    df = df.dropna(subset=["Clean_Text", "Informativeness"]).copy()
    df["Clean_Text"] = df["Clean_Text"].astype(str).str.strip()
    df = df[df["Clean_Text"] != ""].copy()

    df["crisis_label"] = df["Informativeness"].apply(
        lambda label: 0 if label == "Not related" else 1
    )

    # -------------------------------------------------------------
    # Identify likely-mislabeled "Not related" rows
    # -------------------------------------------------------------
    not_related = df[df["crisis_label"] == 0]
    mislabeled_mask = not_related["Clean_Text"].apply(looks_like_crisis)

    n_mislabeled = int(mislabeled_mask.sum())
    print(f"\nNot-related rows total: {len(not_related)}")
    print(f"Likely mislabeled (crisis text in 'Not related'): {n_mislabeled}")

    # Show a few examples so you can eyeball them
    print("\nSample mislabeled examples being DROPPED:")
    for text in not_related[mislabeled_mask]["Clean_Text"].head(10):
        print("  -", text[:120])

    # Drop them (safer than relabeling — we don't want to contaminate class 1)
    drop_indices = not_related[mislabeled_mask].index
    df = df.drop(index=drop_indices).copy()

    print(f"\nRows after dropping mislabeled negatives: {len(df)}")

    # -------------------------------------------------------------
    # Add curated everyday negatives
    # -------------------------------------------------------------
    curated = build_curated_negatives()
    print(f"\nCurated everyday negatives added: {len(curated)}")

    # Append curated negatives (they already have the right columns;
    # other columns will be NaN which is fine)
    df = pd.concat([df, curated], ignore_index=True, sort=False)

    print(f"\nFinal row count: {len(df)}")
    print("\nFinal class distribution:")
    print(df["crisis_label"].value_counts().rename({
        0: "Not Crisis", 1: "Crisis"
    }))

    # Save
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()