import csv
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from .database import SessionLocal
from .models import Resource


CSV_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "synthetic_resources.csv"
)


def read_resources():
    resources = []
    seen_ids = set()

    with CSV_PATH.open(
        newline="", encoding="utf-8-sig"
    ) as file:
        for line_number, row in enumerate(csv.DictReader(file), 2):
            resource_id = row["id"].strip()

            if not resource_id or resource_id in seen_ids:
                raise ValueError(
                    f"Missing or duplicate ID at line {line_number}"
                )
            seen_ids.add(resource_id)

            capabilities = json.loads(row["capabilities"])
            if not isinstance(capabilities, list) or not capabilities:
                raise ValueError(
                    f"Invalid capabilities at line {line_number}"
                )

            latitude = float(row["latitude"])
            longitude = float(row["longitude"])

            if not (
                -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                raise ValueError(
                    f"Invalid coordinates at line {line_number}"
                )

            availability = row["availability"].strip().upper()
            if availability not in {"AVAILABLE", "BUSY", "OFFLINE"}:
                raise ValueError(
                    f"Invalid availability at line {line_number}"
                )

            resources.append({
                "id": resource_id,
                "name": row["name"],
                "resource_type": row["resource_type"],
                "department": row["department"],
                "capabilities": capabilities,
                "location_name": row["location_name"],
                "latitude": latitude,
                "longitude": longitude,
                "availability": availability,
                "created_at": datetime.fromisoformat(row["created_at"]),
                "updated_at": datetime.fromisoformat(row["updated_at"]),
            })

    return resources


def import_resources():
    # Read and validate before changing the database.
    resources = read_resources()
    added = 0

    with SessionLocal() as db:
        try:
            existing_ids = set(
                db.scalars(select(Resource.id)).all()
            )

            for data in resources:
                if data["id"] not in existing_ids:
                    db.add(Resource(**data))
                    added += 1

            db.commit()
        except Exception:
            db.rollback()
            raise

    print(f"CSV records: {len(resources)}")
    print(f"Added: {added}")
    print(f"Already present: {len(resources) - added}")


if __name__ == "__main__":
    import_resources()