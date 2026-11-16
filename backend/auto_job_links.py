
import csv
import os
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

CSV_PATH = PROJECT_DIR / "jobs_metadata.csv"
API_URL = "https://api.headcountlabs.com/v1/jobs"

load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("HEADCOUNTLABS_API_KEY")


def get_value(field):
    """Read values from Headcount Labs field objects."""

    if isinstance(field, dict):
        if field.get("state") == "known":
            return field.get("value")

        return None

    return field


def normalize(text):
    """Normalize company names and job titles."""

    return re.sub(
        r"\s+",
        " ",
        (text or "").strip().casefold()
    )


def valid_url(url):
    """Allow only HTTP and HTTPS URLs."""

    if not isinstance(url, str):
        return False

    try:
        parsed = urlsplit(url)

        return (
            parsed.scheme in ("https", "http")
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except ValueError:
        return False


def format_location(job, posting):
    """Extract a published Malaysian job location."""

    location = get_value(
        posting.get("location")
    )

    if not isinstance(location, dict):
        locations = job.get("locations") or []

        for item in locations:
            value = get_value(item)

            if isinstance(value, dict):
                location = value
                break

    if not isinstance(location, dict):
        return ""

    parts = []

    city = location.get("city")
    region = location.get("state") or location.get("region")
    country = location.get("country")

    if city:
        parts.append(str(city))

    if region:
        parts.append(str(region))

    if country:
        parts.append(str(country))

    return ", ".join(parts)


def find_matching_job(company_name, job_title):
    """Search API and match the exact employer and title."""

    words = job_title.split()

    search_title = " ".join(words[:4])

    response = requests.get(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}"
        },
        params={
            "country": "MY",
            "title": search_title,
            "currentness": "current",
            "limit": 100
        },
        timeout=40
    )

    response.raise_for_status()

    data = response.json()
    jobs = data.get("data", [])

    matches = []

    for job in jobs:

        api_company = get_value(
            job.get("employer_name")
        )

        api_title = get_value(
            job.get("title")
        )

        if not isinstance(api_company, str):
            continue

        if not isinstance(api_title, str):
            continue

        # Both company and title must match exactly
        if normalize(api_company) != normalize(company_name):
            continue

        if normalize(api_title) != normalize(job_title):
            continue

        if job.get("currentness") != "current":
            continue

        if job.get("stale") is True:
            continue

        # Check individual source postings
        for posting in job.get("postings", []):

            if posting.get("posting_status") != "listed":
                continue

            check = posting.get("latest_application_check")

            if isinstance(check, dict):
                if check.get("result") in ("closed", "broken"):
                    continue

            url = get_value(
                posting.get("application_url")
            )

            if not valid_url(url):
                url = get_value(
                    posting.get("posting_url")
                )

            if not valid_url(url):
                continue

            location = format_location(
                job,
                posting
            )

            verified_date = ""

            # Only claim an application check if
            # the API explicitly reports availability.
            if (
                isinstance(check, dict)
                and check.get("result") == "available"
                and check.get("checked_at")
            ):
                verified_date = str(
                    check["checked_at"]
                )[:10]

            matches.append({
                "url": url,
                "location": location,
                "date_verified": verified_date
            })

    # Avoid guessing between different matching postings
    unique_urls = set()

    for match in matches:
        unique_urls.add(match["url"])

    if len(unique_urls) != 1:
        return None

    return matches[0]


def update_metadata():
    """Fill existing metadata rows with API job links."""

    if not API_KEY:
        print("HEADCOUNTLABS_API_KEY not found in backend/.env")
        return

    if not CSV_PATH.exists():
        print("jobs_metadata.csv was not found.")
        print("Generate it using backend.job_metadata first.")
        return

    with open(
        CSV_PATH,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        print("Metadata CSV has no headers.")
        return

    updated = 0
    unmatched = 0
    errors = 0

    for index, row in enumerate(rows, start=1):

        company = row.get("company_name", "")
        title = row.get("job_title", "")

        if not company or not title:
            continue

        # Preserve previously entered links
        if (row.get("application_url") or "").strip():
            print(f"[{index}] Existing link kept")
            continue

        print(f"[{index}/{len(rows)}] Searching: {title}")

        try:
            match = find_matching_job(
                company,
                title
            )

            if match:
                row["application_url"] = match["url"]

                if not (row.get("location") or "").strip():
                    row["location"] = match["location"]

                if match["date_verified"]:
                    row["date_verified"] = (
                        match["date_verified"]
                    )

                updated += 1
                print("  Application link found")

            else:
                unmatched += 1
                print("  No unambiguous current match found")

        except requests.RequestException as error:
            errors += 1
            print(f"  API error: {error}")

        # Small pause between requests
        time.sleep(0.5)

    # Save completed results
    temporary_path = CSV_PATH.with_suffix(".tmp")

    with open(
        temporary_path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)

    temporary_path.replace(CSV_PATH)

    print("\nFinished updating job metadata.")
    print(f"Links added: {updated}")
    print(f"Unmatched jobs: {unmatched}")
    print(f"API errors: {errors}")
    print(f"Saved to: {CSV_PATH}")


if __name__ == "__main__":
    update_metadata()
