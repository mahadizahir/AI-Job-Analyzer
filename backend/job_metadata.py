
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
    """Identify a listing using normalized company and job names."""

    company = " ".join(
        (company_name or "").strip().casefold().split()
    )

    title = " ".join(
        (job_title or "").strip().casefold().split()
    )

    return (company, title)


def is_valid_url(url):
    """Accept valid HTTP or HTTPS application links."""

    if not isinstance(url, str):
        return False

    try:
        parsed = urlsplit(url.strip())

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


def upsert_job_metadata(new_records):
    """
    Add metadata for newly collected jobs.

    Existing non-empty values are preserved.
    New records with duplicate company/title keys are not added twice.
    """

    if not new_records:
        return

    if not CSV_PATH.exists():
        create_metadata_template()

    rows = []
    fieldnames = FIELDNAMES.copy()

    if CSV_PATH.exists():
        with open(
            CSV_PATH,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames:
                fieldnames = list(reader.fieldnames)

                for field in FIELDNAMES:
                    if field not in fieldnames:
                        fieldnames.append(field)

                rows = list(reader)

    # Count existing keys so ambiguous duplicate rows are not modified.
    key_counts = {}

    for row in rows:
        key = make_key(
            row.get("company_name"),
            row.get("job_title")
        )

        if key[0] and key[1]:
            key_counts[key] = key_counts.get(key, 0) + 1

    row_indexes = {}

    for index, row in enumerate(rows):
        key = make_key(
            row.get("company_name"),
            row.get("job_title")
        )

        if key_counts.get(key) == 1:
            row_indexes[key] = index

    added = 0
    updated = 0
    skipped = 0

    for record in new_records:
        company = (record.get("company_name") or "").strip()
        title = (record.get("job_title") or "").strip()

        key = make_key(company, title)

        if not key[0] or not key[1]:
            skipped += 1
            continue

        location = (record.get("location") or "").strip()
        application_url = (
            record.get("application_url") or ""
        ).strip()

        date_verified = (
            record.get("date_verified") or ""
        ).strip()

        if application_url and not is_valid_url(application_url):
            application_url = ""

        if not is_valid_date(date_verified):
            date_verified = ""

        if key in row_indexes:
            existing_row = rows[row_indexes[key]]
            changed = False

            # Fill missing information without replacing existing values.
            if not (existing_row.get("location") or "").strip():
                if location:
                    existing_row["location"] = location
                    changed = True

            existing_url = (
                existing_row.get("application_url") or ""
            ).strip()

            if not existing_url:
                if application_url:
                    existing_row["application_url"] = application_url
                    changed = True

            elif not is_valid_url(existing_url):
                if application_url:
                    existing_row["application_url"] = application_url
                    changed = True

            if not (existing_row.get("date_verified") or "").strip():
                if date_verified:
                    existing_row["date_verified"] = date_verified
                    changed = True

            if changed:
                updated += 1
            else:
                skipped += 1

            continue

        # Do not add a new row if the CSV already contains ambiguous duplicates.
        if key_counts.get(key, 0) > 1:
            skipped += 1
            continue

        new_row = {
            "company_name": company,
            "job_title": title,
            "location": location,
            "application_url": application_url,
            "date_verified": date_verified
        }

        rows.append(new_row)
        row_indexes[key] = len(rows) - 1
        key_counts[key] = 1
        added += 1

    temporary_path = CSV_PATH.with_suffix(".tmp")

    with open(
        temporary_path,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(rows)

    temporary_path.replace(CSV_PATH)

    print(
        f"Metadata added: {added}, "
        f"updated: {updated}, "
        f"skipped: {skipped}"
    )


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

            if application_url and not is_valid_url(application_url):
                application_url = ""
                date_verified = ""

            if not is_valid_date(date_verified):
                date_verified = ""

            # Avoid showing contradictory duplicate metadata.
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
