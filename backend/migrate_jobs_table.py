import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from backend.database import engine
from backend.models import Base, Job, Posting


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "jobs.db"


def backup_database():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DATABASE_PATH.with_name(
        f"jobs_backup_{timestamp}.db"
    )

    source_connection = sqlite3.connect(DATABASE_PATH)
    backup_connection = sqlite3.connect(backup_path)

    try:
        source_connection.backup(backup_connection)
    finally:
        backup_connection.close()
        source_connection.close()

    print(f"Database backup created: {backup_path}")


def migrate_schema():
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(jobs)")
        existing_columns = []

        for column in cursor.fetchall():
            existing_columns.append(column[1])

        if not existing_columns:
            raise RuntimeError(
                "The jobs table does not exist."
            )

        new_columns = {
            "location": "VARCHAR(300)",
            "application_url": "VARCHAR(1000)",
            "date_verified": "VARCHAR(10)",
            "work_description": "TEXT"
        }

        added_count = 0

        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE jobs ADD COLUMN "
                    f"{column_name} {column_type}"
                )

                print(f"Added column: {column_name}")
                added_count += 1
            else:
                print(f"Column already exists: {column_name}")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    # Create the postings table using SQLAlchemy if it does not exist yet
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if "postings" not in existing_tables:
        Base.metadata.create_all(
            bind=engine,
            tables=[Posting.__table__]
        )
        print("Created table: postings")
    else:
        print("Table already exists: postings")

    print(f"New columns added to jobs: {added_count}")


def backfill_postings_from_jobs():
    """Copy existing single-posting fields from jobs into postings."""

    backfilled_count = 0
    skipped_existing_count = 0
    skipped_empty_count = 0

    with Session(engine) as session:
        jobs = session.scalars(
            select(Job).order_by(Job.id)
        ).all()

        for job in jobs:
            if len(job.postings) > 0:
                skipped_existing_count += 1
                continue

            clean_url = (job.application_url or "").strip()
            clean_location = (job.location or "").strip()
            clean_date = (job.date_verified or "").strip()

            if not clean_url and not clean_location and not clean_date:
                skipped_empty_count += 1
                continue

            posting_status = None
            if clean_url:
                posting_status = "listed"

            check_result = None
            if clean_date:
                check_result = "available"

            new_posting = Posting(
                job_id=job.id,
                application_url=clean_url or None,
                location=clean_location or None,
                posting_status=posting_status,
                latest_check_result=check_result,
                latest_checked_at=clean_date or None
            )

            session.add(new_posting)
            backfilled_count += 1

        session.commit()

        total_jobs = session.scalar(
            select(func.count()).select_from(Job)
        )

        total_postings = session.scalar(
            select(func.count()).select_from(Posting)
        )

    print("\nBackfill summary:")
    print(f"Backfilled into postings: {backfilled_count}")
    print(f"Skipped (already had postings): {skipped_existing_count}")
    print(f"Skipped (no existing URL/location/date): {skipped_empty_count}")
    print(f"Total jobs in database: {total_jobs}")
    print(f"Total postings in database: {total_postings}")


if __name__ == "__main__":
    backup_database()
    migrate_schema()
    backfill_postings_from_jobs()