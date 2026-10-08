from .models import Incident
from .location_matching import location_matches


if __name__ == "__main__":
    incident = Incident(
        location_name="whitefield",
        latitude=12.9957428,
        longitude=77.7579489,
    )

    same_location = {
        "text": "Whitefield",
        "latitude": 12.9957428,
        "longitude": 77.7579489,
    }

    different_location = {
        "text": "Jayanagar",
        "latitude": 12.925,
        "longitude": 77.583,
    }

    distant_coordinates = {
        "text": "Whitefield",
        "latitude": 12.925,
        "longitude": 77.583,
    }

    assert location_matches(incident, same_location)
    assert not location_matches(incident, different_location)
    assert not location_matches(incident, distant_coordinates)
    assert not location_matches(incident, {"text": "Whitefield"})
    assert not location_matches(incident, {})

    print("Location matching checks passed")