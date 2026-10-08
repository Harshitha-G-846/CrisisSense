from math import atan2, cos, isfinite, radians, sin, sqrt


MAX_DISTANCE_KM = 1.0


def normalize_location(name: str) -> str:
    return " ".join(name.casefold().split())


def valid_coordinates(latitude, longitude) -> bool:
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False

    return (
        isfinite(latitude)
        and isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def distance_km(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(
        radians,
        map(float, (lat1, lon1, lat2, lon2)),
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    value = min(1.0, max(0.0, value))

    return 6371.0 * 2 * atan2(sqrt(value), sqrt(1 - value))


def location_matches(incident, location: dict) -> bool:
    incident_name = normalize_location(
        incident.location_name or ""
    )
    report_name = normalize_location(location.get("text") or "")

    # Missing or different names do not pass this conservative check.
    if not incident_name or incident_name != report_name:
        return False

    incident_lat = incident.latitude
    incident_lon = incident.longitude
    report_lat = location.get("latitude")
    report_lon = location.get("longitude")

    if not valid_coordinates(incident_lat, incident_lon):
        return False

    if not valid_coordinates(report_lat, report_lon):
        return False

    return distance_km(
        incident_lat,
        incident_lon,
        report_lat,
        report_lon,
    ) <= MAX_DISTANCE_KM