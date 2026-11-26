
import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import engine
from backend.models import Job


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = BASE_DIR.parent / "jobs_audit_export.csv"

FIELDNAMES = [
    "id",
    "company_name",
    "job_title",
    "description",
    "work_description",
    "location",
    "application_url",
    "date_verified"
]


def export_jobs():
    with Session(engine) as session:
        statement = select(Job).order_by(Job.id)
        jobs = session.scalars(statement).all()

        with open(
            OUTPUT_PATH,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as csv_file:

            writer = csv.DictWriter(
                csv_file,
                fieldnames=FIELDNAMES
            )

            writer.writeheader()

            for job in jobs:
                writer.writerow({
                    "id": job.id,
                    "company_name": job.company_name,
                    "job_title": job.job_title,
                    "description": job.description,
                    "work_description": job.work_description,
                    "location": job.location,
                    "application_url": job.application_url,
                    "date_verified": job.date_verified
                })

    print(f"Export completed.")
    print(f"Total jobs exported: {len(jobs)}")
    print(f"File location: {OUTPUT_PATH}")


if __name__ == "__main__":
    export_jobs()
