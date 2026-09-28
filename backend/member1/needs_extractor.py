def extract_needs(information_type, text):

    text = text.lower()

    needs = []

    # Medical
    if any(word in text for word in [
        "medical",
        "injured",
        "injury",
        "ambulance",
        "hospital",
        "doctor",
        "medicine",
        "treatment"
    ]):
        needs.append("medical")

    # Rescue
    if any(word in text for word in [
        "rescue",
        "rescued",
        "trapped",
        "people stuck",
        "stuck inside",
        "stranded"
    ]):
        needs.append("rescue")

    # Evacuation
    if any(word in text for word in [
        "evacuate",
        "evacuation",
        "evacuated",
        "leave the area",
        "move to safety"
    ]):
        needs.append("evacuation")

    # Food
    if any(word in text for word in [
        "food",
        "meals",
        "meal",
        "ration"
    ]):
        needs.append("food")

    # Water
    if any(word in text for word in [
        "water",
        "drinking water",
        "water supply"
    ]):
        needs.append("water")

    # Electricity
    if any(word in text for word in [
        "electricity",
        "power outage",
        "power cut",
        "transformer",
        "electric"
    ]):
        needs.append("electricity")

    # Shelter
    if any(word in text for word in [
        "shelter",
        "temporary shelter",
        "relief camp",
        "camp"
    ]):
        needs.append("shelter")

    # Volunteers
    if any(word in text for word in [
        "volunteer",
        "volunteers"
    ]):
        needs.append("volunteers")

    # Supplies
    if any(word in text for word in [
        "supplies",
        "blankets",
        "clothes",
        "materials"
    ]):
        needs.append("supplies")

    # Use information type only if no direct need was found
    if not needs:

        if "donations and volunteering" in information_type.lower():
            needs.append("volunteers")

        elif "infrastructure and utilities" in information_type.lower():
            needs.append("infrastructure")

        elif "caution and advice" in information_type.lower():
            needs.append("safety")

        elif "sympathy and support" in information_type.lower():
            needs.append("support")

        else:
            needs.append("general_assistance")

    return list(dict.fromkeys(needs))


if __name__ == "__main__":

    information_type = input("\nEnter information type: ")
    text = input("Enter crisis text: ")

    needs = extract_needs(information_type, text)

    print("\nDetected Needs:")

    for need in needs:
        print("-", need)