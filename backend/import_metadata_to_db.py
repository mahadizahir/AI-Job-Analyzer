
import csv
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "jobs.db"
CSV_PATH = BASE_DIR.parent / "jobs_metadata.csv"


def normalize(value):
    if not value:
        return ""

    return " ".join(value.split()).casefold()


def is_valid_url(value):
    if not value:
        return False

    try:
        parsed = urlsplit(value)

        return (
            parsed.scheme in ["http", "https"]
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except ValueError:
        return False


def is_valid_date(value):
    if not value:
        return False

    try:
        checked_date = date.fromisoformat(value)
        return checked_date <= date.today()

    except ValueError:
        return False


def create_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = DATABASE_PATH.with_name(
        f"jobs_before_csv_import_{timestamp}.db"
    )

    shutil.copy2(DATABASE_PATH, backup_path)

    print(f"Backup created: {backup_path}")


def load_csv_metadata():
    metadata = {}
    conflicting_keys = set()

    with open(
        CSV_PATH,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        required_columns = [
            "company_name",
            "job_title",
            "location",
            "application_url",
            "date_verified"
        ]

        if not reader.fieldnames:
            raise ValueError("CSV file has no header.")

        for column in required_columns:
            if column not in reader.fieldnames:
                raise ValueError(
                    f"Missing CSV column: {column}"
                )

        for row in reader:
            company_name = (row.get("company_name") or "").strip()
            job_title = (row.get("job_title") or "").strip()

            if not company_name or not job_title:
                continue

            key = (
                normalize(company_name),
                normalize(job_title)
            )

            location = (row.get("location") or "").strip()
            application_url = (
                row.get("application_url") or ""
            ).strip()
            date_verified = (
                row.get("date_verified") or ""
            ).strip()

            if not is_valid_url(application_url):
                application_url = ""

            if not is_valid_date(date_verified):
                date_verified = ""

            row_metadata = {
                "location": location,
                "application_url": application_url,
                "date_verified": date_verified
            }

            if key not in metadata:
                metadata[key] = row_metadata
                continue

            for field in row_metadata:
                old_value = metadata[key][field]
                new_value = row_metadata[field]

                if old_value and new_value and old_value != new_value:
                    conflicting_keys.add(key)

                elif not old_value and new_value:
                    metadata[key][field] = new_value

    return metadata, conflicting_keys


def import_metadata():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV file not found: {CSV_PATH}"
        )

    metadata, conflicting_keys = load_csv_metadata()

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(jobs)")
        columns = []

        for column in cursor.fetchall():
            columns.append(column["name"])

        required_columns = [
            "location",
            "application_url",
            "date_verified"
        ]

        for column in required_columns:
            if column not in columns:
                raise RuntimeError(
                    f"Database column is missing: {column}"
                )

        cursor.execute(
            """
            SELECT id, company_name, job_title,
                   location, application_url, date_verified
            FROM jobs
            """
        )

        database_jobs = {}

        for job in cursor.fetchall():
            key = (
                normalize(job["company_name"]),
                normalize(job["job_title"])
            )

            if key not in database_jobs:
                database_jobs[key] = []

            database_jobs[key].append(job)

        matched = 0
        updated = 0
        unchanged = 0
        unmatched = 0
        ambiguous = 0
        skipped_conflicts = 0

        for key, csv_data in metadata.items():

            if key in conflicting_keys:
                skipped_conflicts += 1
                continue

            matching_jobs = database_jobs.get(key, [])

            if len(matching_jobs) == 0:
                unmatched += 1
                continue

            if len(matching_jobs) > 1:
                ambiguous += 1
                continue

            job = matching_jobs[0]
            matched += 1

            new_location = job["location"] or csv_data["location"]
            new_url = (
                job["application_url"]
                or csv_data["application_url"]
            )
            new_date = (
                job["date_verified"]
                or csv_data["date_verified"]
            )

            if (
                new_location == job["location"]
                and new_url == job["application_url"]
                and new_date == job["date_verified"]
            ):
                unchanged += 1
                continue

            cursor.execute(
                """
                UPDATE jobs
                SET location = ?,
                    application_url = ?,
                    date_verified = ?
                WHERE id = ?
                """,
                (
                    new_location or None,
                    new_url or None,
                    new_date or None,
                    job["id"]
                )
            )

            updated += 1

        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM jobs")
        total_jobs = cursor.fetchone()[0]

        print("\nCSV import completed.")
        print("------------------------------")
        print(f"CSV records: {len(metadata)}")
        print(f"Matched jobs: {matched}")
        print(f"Updated jobs: {updated}")
        print(f"Unchanged jobs: {unchanged}")
        print(f"Unmatched CSV records: {unmatched}")
        print(f"Ambiguous matches: {ambiguous}")
        print(f"Conflicting CSV records: {skipped_conflicts}")
        print(f"Total database jobs: {total_jobs}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_backup()
    import_metadata()
