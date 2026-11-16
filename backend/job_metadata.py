
import csv
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import engine
from backend.models import Job


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR.parent / "jobs_metadata.csv"

FIELDNAMES = [
    "company_name",
    "job_title",
    "location",
    "application_url",
    "date_verified"
]


def make_key(company_name, job_title):
    """Identify a listing using company and job title."""

    company = (company_name or "").strip().casefold()
    title = (job_title or "").strip().casefold()

    return (company, title)


def is_valid_url(url):
    """Accept valid HTTP or HTTPS application links."""

    try:
        parsed = urlsplit(url)

        return (
            parsed.scheme in ["http", "https"]
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except ValueError:
        return False


def is_valid_date(value):
    """Check YYYY-MM-DD date format."""

    if not value:
        return False

    try:
        checked_date = date.fromisoformat(value)

        return checked_date <= date.today()

    except ValueError:
        return False


def create_metadata_template():
    """Create a CSV template using the existing jobs."""

    if CSV_PATH.exists():
        print("Metadata CSV already exists. Nothing overwritten.")
        print(f"File: {CSV_PATH}")
        return

    with Session(engine) as session:
        jobs = session.scalars(
            select(Job).order_by(Job.id)
        ).all()

    with open(
        CSV_PATH,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES
        )

        writer.writeheader()

        seen = set()

        for job in jobs:
            key = make_key(
                job.company_name,
                job.job_title
            )

            if key in seen:
                continue

            seen.add(key)

            writer.writerow({
                "company_name": job.company_name,
                "job_title": job.job_title,
                "location": "",
                "application_url": "",
                "date_verified": ""
            })

    print(f"Metadata template created: {CSV_PATH}")
    print(f"Unique job listings exported: {len(seen)}")


def load_job_metadata():
    """Read verified metadata saved in the CSV."""

    metadata = {}

    if not CSV_PATH.exists():
        return metadata

    with open(
        CSV_PATH,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            company = row.get("company_name", "")
            title = row.get("job_title", "")

            key = make_key(company, title)

            if not key[0] or not key[1]:
                continue

            location = (
                row.get("location") or ""
            ).strip()

            application_url = (
                row.get("application_url") or ""
            ).strip()

            date_verified = (
                row.get("date_verified") or ""
            ).strip()

            # Reject unsafe or malformed links
            if application_url and not is_valid_url(
                application_url
            ):
                application_url = ""
                date_verified = ""

            # Only show a checked date if it is valid
            if not is_valid_date(date_verified):
                date_verified = ""

            # Avoid showing contradictory duplicate metadata
            if key in metadata:
                metadata[key] = {
                    "location": "",
                    "application_url": "",
                    "date_verified": ""
                }
                continue

            metadata[key] = {
                "location": location,
                "application_url": application_url,
                "date_verified": date_verified
            }

    return metadata


def enrich_job(job, metadata):
    """Add location and application-link information."""

    key = make_key(
        job.get("company_name"),
        job.get("job_title")
    )

    extra = metadata.get(key, {})

    enriched = dict(job)

    enriched["location"] = extra.get(
        "location", ""
    )

    enriched["application_url"] = extra.get(
        "application_url", ""
    )

    enriched["date_verified"] = extra.get(
        "date_verified", ""
    )

    return enriched


def enrich_jobs(jobs):
    """Add metadata to a list of jobs."""

    metadata = load_job_metadata()
    result = []

    for job in jobs:
        result.append(
            enrich_job(job, metadata)
        )

    return result


if __name__ == "__main__":
    create_metadata_template()
