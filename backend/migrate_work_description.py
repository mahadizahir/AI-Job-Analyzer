
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

from backend.database import engine


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "jobs.db"


def migrate_database():

    inspector = inspect(engine)

    columns = [
        column["name"]
        for column in inspector.get_columns("jobs")
    ]

    if "work_description" in columns:
        print("work_description column already exists.")
        return

    backup_time = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = BASE_DIR / (
        f"jobs_before_work_description_{backup_time}.db"
    )

    shutil.copy2(
        DATABASE_PATH,
        backup_path
    )

    print(f"Database backup created: {backup_path}")

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE jobs "
                "ADD COLUMN work_description TEXT"
            )
        )

    print("Migration completed successfully.")
    print("Added column: work_description")


if __name__ == "__main__":
    migrate_database()
