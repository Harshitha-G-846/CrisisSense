from .database import Base, DATABASE_PATH, engine
from . import models


def initialize_database():
    Base.metadata.create_all(bind=engine)
    print(f"Database ready: {DATABASE_PATH}")
    print("Tables:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    initialize_database()