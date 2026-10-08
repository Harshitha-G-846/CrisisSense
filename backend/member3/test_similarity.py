from .similarity import text_similarity


if __name__ == "__main__":
    original = (
        "A fire broke out in Whitefield today. "
        "People are trapped and need rescue and medical assistance."
    )

    comparisons = {
        "Identical report": original,
        "Reworded report": (
            "A building is burning in Whitefield today. "
            "People are stuck inside and need rescuers and an ambulance."
        ),
        "Different location": (
            "A fire broke out in Jayanagar today. "
            "People are trapped and need rescue and medical assistance."
        ),
        "Unrelated report": (
            "The college library has extended its opening hours."
        ),
    }

    for label, text in comparisons.items():
        score = text_similarity(original, text)
        print(f"{label}: {score:.3f}")