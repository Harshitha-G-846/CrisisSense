from sqlalchemy import select
from sqlalchemy.orm import Session

from .location_matching import distance_km, valid_coordinates
from .models import Incident, Resource
from .department_routing import recommend_departments


def recommend_resources(
    db: Session,
    incident: Incident,
    radius_km: float = 25.0,
    per_need: int = 3,
) -> dict:
    needs = set(incident.needs or [])

    incident_type = (incident.incident_type or "").casefold()

    if incident_type in {"fire", "wildfire"}:
        needs.add("fire_response")
    elif incident_type == "flood":
        needs.add("flood_response")

    required_needs = sorted(needs)

    result = {
        "incident_id": incident.id,
        "mode": "SIMULATION",
        "verification_status": incident.verification_status,
        "human_approval_required": True,
        "radius_km": radius_km,
        "distance_method": "straight_line",
        "required_needs": required_needs,
        "recommendations": [],
        "unmet_needs": [],
    }

    routing = recommend_departments(
        incident_type=incident.incident_type or "",
        required_needs=required_needs,
    )

    result["recommended_departments"] = routing["departments"]
    result["unmapped_needs"] = routing["unmapped_needs"]

    if (
        incident.status not in {"OPEN", "IN_PROGRESS"}
        or incident.verification_status == "REJECTED"
    ):
        result["reason"] = "Incident is not eligible for recommendations."
        result["unmet_needs"] = required_needs
        result["recommended_departments"] = []
        return result

    if not valid_coordinates(
        incident.latitude, incident.longitude
    ):
        result["reason"] = "Incident has no valid location coordinates."
        result["unmet_needs"] = required_needs
        return result

    resources = db.scalars(
        select(Resource).where(
            Resource.availability == "AVAILABLE"
        )
    ).all()

    nearby_resources = []

    for resource in resources:
        if not valid_coordinates(
            resource.latitude, resource.longitude
        ):
            continue

        capabilities = set(resource.capabilities or [])

        if not capabilities.intersection(needs):
            continue

        distance = distance_km(
            incident.latitude,
            incident.longitude,
            resource.latitude,
            resource.longitude,
        )

        if distance <= radius_km:
            nearby_resources.append((distance, resource))

    nearby_resources.sort(
        key=lambda item: (item[0], item[1].id)
    )

    for need in required_needs:
        candidates = []

        for distance, resource in nearby_resources:
            if need not in (resource.capabilities or []):
                continue

            # Primary medical response requires medical resources.
            if need == "medical" and resource.resource_type not in {
                "ambulance",
                "medical_team",
            }:
                continue

            # Fire suppression requires a fire unit.
            if need == "fire_response" and resource.resource_type != "fire_unit":
                continue

            # Building-fire rescue requires suitable rescue resources.
            if (
                need == "rescue"
                and incident_type in {"fire", "wildfire"}
                and resource.resource_type not in {
                    "fire_unit",
                    "rescue_team",
                }
            ):
                continue

            candidates.append({
                "resource_id": resource.id,
                "name": resource.name,
                "resource_type": resource.resource_type,
                "department": resource.department,
                "availability": resource.availability,
                "distance_km": round(distance, 2),
            })

            if len(candidates) >= per_need:
                break

        result["recommendations"].append({
            "need": need,
            "candidates": candidates,
        })

        if not candidates:
            result["unmet_needs"].append(need)

    return result