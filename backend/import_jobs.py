
import csv
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from database import engine
from models import Job

csv_path = Path(__file__).resolve().parent.parent / "jobs.csv"

jobs = []
saved_jobs = set()

with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        company = row["company_name"].strip()
        title = row["job_title"].strip()
        description = row["description"].strip()

        if not company or not title or not description:
            continue

        job_key = (company.lower(), title.lower())

        if job_key in saved_jobs:
            continue

        saved_jobs.add(job_key)

        jobs.append(
            Job(
                company_name=company,
                job_title=title,
                description=description
            )
        )

if not jobs:
    raise ValueError("No valid jobs found. Database was not changed.")

with Session(engine) as session:
    session.execute(delete(Job))
    session.add_all(jobs)
    session.commit()

print(f"Database updated with {len(jobs)} jobs!")
