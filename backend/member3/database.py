from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Store the database in backend, regardless of where Python is started.
BACKEND_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = BACKEND_DIR / "crisissense.db"

engine = create_engine(
    f"sqlite:///{DATABASE_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)


# Enable foreign keys so reports must link to valid incidents.
@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, connection_record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def ensure_schema_compatibility(target_engine=None):
    """Safely updates database schema without wiping or dropping existing tables.
    - Creates users table if missing.
    - Adds nullable citizen_id column to incidents and reports if missing.
    """
    if target_engine is None:
        target_engine = engine

    # Create any missing tables (e.g. users) defined in metadata
    Base.metadata.create_all(bind=target_engine)

    with target_engine.connect() as conn:
        cursor = conn.connection.cursor()
        cursor.execute("PRAGMA table_info(incidents)")
        inc_cols = {row[1] for row in cursor.fetchall()}
        if inc_cols and "citizen_id" not in inc_cols:
            cursor.execute("ALTER TABLE incidents ADD COLUMN citizen_id TEXT REFERENCES users(id)")

        cursor.execute("PRAGMA table_info(reports)")
        rep_cols = {row[1] for row in cursor.fetchall()}
        if rep_cols and "citizen_id" not in rep_cols:
            cursor.execute("ALTER TABLE reports ADD COLUMN citizen_id TEXT REFERENCES users(id)")

        cursor.close()


# Ensure live database schema is compatible on initial load
try:
    ensure_schema_compatibility(engine)
except Exception:
    pass


# FastAPI can use this to open and close a session per request.
def get_db():
    with SessionLocal() as session:
        yield session