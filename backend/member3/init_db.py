
from sqlalchemy import inspect, text

from .database import Base, DATABASE_PATH, engine
from . import models


def initialize_database():
    # Check whether the existing incidents table needs a migration.
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "incidents" in existing_tables:
        columns = {
            column["name"]
            for column in inspector.get_columns("incidents")
        }

        if "response_status" not in columns:
            print("Adding missing incidents.response_status column...")

            with engine.begin() as connection:
                connection.execute(
                    text("""
                        ALTER TABLE incidents
                        ADD COLUMN response_status VARCHAR
                        NOT NULL DEFAULT 'NOT_PLANNED'
                    """)
                )

            print("response_status column added successfully.")

    # Create any tables that do not exist yet.
    Base.metadata.create_all(bind=engine)

    # Ensure the response_status index exists.
    with engine.begin() as connection:
        connection.execute(
            text("""
                CREATE INDEX IF NOT EXISTS
                ix_incidents_response_status
                ON incidents (response_status)
            """)
        )

    print(f"Database ready: {DATABASE_PATH}")
    print("Tables:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    initialize_database()