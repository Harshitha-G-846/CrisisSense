NEED_DEPARTMENTS = {
    "fire_response": "Fire and Rescue",
    "flood_response": "Disaster Response",
    "medical": "Health and Medical",
    "rescue": "Disaster Response",
    "evacuation": "Disaster Response",
    "food": "Relief and Shelter",
    "water": "Water Supply",
    "shelter": "Relief and Shelter",
    "electricity": "Electricity Response",
    "infrastructure": "Infrastructure Response",
    "volunteers": "Relief Coordination",
    "supplies": "Relief Coordination",
}


def recommend_departments(
    incident_type: str,
    required_needs: list[str],
) -> dict:
    grouped = {}
    unmapped_needs = []

    for need in sorted(set(required_needs)):
        department = NEED_DEPARTMENTS.get(need)

        # Fire-related rescue goes to Fire and Rescue.
        if (
            need == "rescue"
            and incident_type.casefold() in {"fire", "wildfire"}
        ):
            department = "Fire and Rescue"

        if department is None:
            unmapped_needs.append(need)
            continue

        grouped.setdefault(department, []).append(need)

    return {
        "departments": [
            {
                "department": department,
                "required_for": needs,
            }
            for department, needs in sorted(grouped.items())
        ],
        "unmapped_needs": unmapped_needs,
    }