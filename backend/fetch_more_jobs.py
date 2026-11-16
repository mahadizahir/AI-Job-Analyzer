
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.database import engine
from backend.models import Job


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("HEADCOUNTLABS_API_KEY")
API_URL = "https://api.headcountlabs.com/v1/jobs/"

# Maximum number of NEW jobs to collect
TARGET_NEW_JOBS = 100

# Smaller page size to reduce large responses
PAGE_SIZE = 25

# Maximum pages for each search keyword
MAX_PAGES_PER_SEARCH = 3

# Maximum records to request in one run
MAX_RECORDS_SCANNED = 450

# Retry failed requests twice after first attempt
MAX_RETRIES = 2

# API timeout in seconds
REQUEST_TIMEOUT = 35

SEARCH_TITLES = [
    "software",
    "developer",
    "data",
    "machine learning",
    "intern",
    "graduate"
]


# Explicit technical role patterns
TECHNICAL_PATTERNS = [
    r"\bsoftware\b",
    r"\bdeveloper\b",
    r"\bprogrammer\b",
    r"\bfrontend\b",
    r"\bfront[\s-]?end\b",
    r"\bbackend\b",
    r"\bback[\s-]?end\b",
    r"\bfull[\s-]?stack\b",
    r"\bweb development\b",
    r"\bmachine learning\b",
    r"\bdeep learning\b",
    r"\bdata scientist\b",
    r"\bdata science\b",
    r"\bdata engineer\b",
    r"\bdata analyst\b",
    r"\bai engineer\b",
    r"\bai developer\b",
    r"\bai engineering\b",
    r"\bartificial intelligence\b",
    r"\bcyber[\s-]?security\b",
    r"\bcloud engineer\b",
    r"\bdevops\b",
    r"\bnetwork engineer\b",
    r"\bnetwork administrator\b",
    r"\bsystem administrator\b",
    r"\bdatabase administrator\b",
    r"\bqa engineer\b",
    r"\btest engineer\b",
    r"\bautomation engineer\b",
    r"\bembedded\b",
    r"\bcomputer science\b",
    r"\binformation technology\b",
    r"\bit support\b",
    r"\bit engineer\b",
    r"\bpython\b"
]


# Reject clearly unrelated role titles
EXCLUDE_PATTERNS = [
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bstaff engineer\b",
    r"\bmanager\b",
    r"\bdirector\b",
    r"\bhead of\b",
    r"\bsales\b",
    r"\bmarketing\b",
    r"\brecruiter\b",
    r"\brecruitment\b",
    r"\baccount executive\b",
    r"\bcontent quality\b",
    r"\bcontent moderation\b",
    r"\bcontent moderator\b",
    r"\btrust and safety\b",
    r"\bdata annotation\b",
    r"\bdata labeling\b",
    r"\bdata labelling\b",
    r"\bdata quality enforcement\b",
    r"\bquality strategy specialist\b"
]


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_value(field):
    """Extract a value from an API field."""

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


def is_relevant_job(title):
    """Check whether a title describes a technical role."""

    title_lower = normalize(title)

    if not title_lower:
        return False

    # Exclude clearly unsuitable titles
    for pattern in EXCLUDE_PATTERNS:

        if re.search(pattern, title_lower):
            return False

    # Accept titles with clear technical indicators
    for pattern in TECHNICAL_PATTERNS:

        if re.search(pattern, title_lower):
            return True

    # Intern/graduate alone is not sufficient.
    # For example, Marketing Intern should not pass.
    return False


def load_existing_jobs():
    """Get all company/title pairs already in SQLite."""

    existing_jobs = set()

    with Session(engine) as session:

        jobs = session.scalars(
            select(Job)
        ).all()

        for job in jobs:

            job_key = (
                normalize(job.company_name),
                normalize(job.job_title)
            )

            existing_jobs.add(job_key)

    return existing_jobs


def request_jobs(api_session, params):
    """Request one API page with bounded retries."""

    for attempt in range(MAX_RETRIES + 1):

        try:
            response = api_session.get(
                API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            # Do not retry invalid credentials
            if response.status_code == 401:
                raise RuntimeError(
                    "API key is invalid or unauthorized."
                )

            # Stop rather than retry rate-limit errors
            if response.status_code == 429:
                raise RuntimeError(
                    "API rate limit reached. Stop this run."
                )

            # Invalid cursor or parameters
            if response.status_code == 400:
                print(
                    "Bad request or invalid cursor. "
                    "Skipping this search."
                )
                return None

            # Retry temporary server errors
            if response.status_code in [
                500, 502, 503, 504
            ]:
                if attempt < MAX_RETRIES:

                    delay = 2 ** (attempt + 1)

                    print(
                        f"API returned {response.status_code}. "
                        f"Retrying after {delay} seconds..."
                    )

                    time.sleep(delay)
                    continue

                print(
                    f"API error {response.status_code}. "
                    "Skipping this search."
                )
                return None

            response.raise_for_status()

            return response.json()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        ) as error:

            if attempt < MAX_RETRIES:

                delay = 2 ** (attempt + 1)

                print(
                    f"Connection issue: "
                    f"{type(error).__name__}"
                )

                print(
                    f"Retrying after {delay} seconds..."
                )

                time.sleep(delay)
                continue

            print(
                "Request failed after all retries. "
                "Skipping this search."
            )
            return None

        except requests.RequestException as error:

            print(
                f"API request failed: {error}"
            )
            return None

        except ValueError:
            print("API returned invalid JSON.")
            return None

    return None


# ==========================================
# MAIN COLLECTION FUNCTION
# ==========================================

def fetch_more_jobs():
    """Fetch relevant jobs and append them to SQLite."""

    if not API_KEY:
        print("HEADCOUNTLABS_API_KEY not found.")
        return

    existing_jobs = load_existing_jobs()

    print(
        f"Existing unique jobs: {len(existing_jobs)}"
    )

    total_added = 0
    total_received = 0

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    with requests.Session() as api_session:

        api_session.headers.update(headers)

        # Prevent automatic transport-level retries
        # so our retry counts stay predictable.

        try:

            for search_title in SEARCH_TITLES:

                if total_added >= TARGET_NEW_JOBS:
                    break

                if (
                    total_received + PAGE_SIZE
                    > MAX_RECORDS_SCANNED
                ):
                    break

                print(
                    f"\nSearching: {search_title}"
                )

                cursor = None

                for page_number in range(
                    1,
                    MAX_PAGES_PER_SEARCH + 1
                ):

                    if total_added >= TARGET_NEW_JOBS:
                        break

                    if (
                        total_received + PAGE_SIZE
                        > MAX_RECORDS_SCANNED
                    ):
                        break

                    # Keep page size and filters stable
                    # across every cursor request.
                    params = {
                        "country": "MY",
                        "title": search_title,
                        "currentness": "current",
                        "limit": PAGE_SIZE
                    }

                    if cursor:
                        params["cursor"] = cursor

                    print(
                        f"Requesting page {page_number}"
                    )

                    data = request_jobs(
                        api_session,
                        params
                    )

                    if data is None:
                        break

                    records = data.get("data", [])

                    if not isinstance(records, list):
                        print(
                            "Unexpected API data format."
                        )
                        break

                    total_received += len(records)

                    print(
                        f"Records received: {len(records)}"
                    )

                    if not records:
                        break

                    page_added = 0
                    page_skipped = 0

                    # Commit each successful page
                    with Session(engine) as db_session:

                        for job_data in records:

                            if not isinstance(job_data, dict):
                                page_skipped += 1
                                continue

                            company = get_value(
                                job_data.get(
                                    "employer_name"
                                )
                            )

                            title = get_value(
                                job_data.get("title")
                            )

                            description = get_value(
                                job_data.get(
                                    "description"
                                )
                            )

                            # Check required fields
                            if not (
                                isinstance(company, str)
                                and isinstance(title, str)
                                and isinstance(description, str)
                            ):
                                page_skipped += 1
                                continue

                            company = company.strip()
                            title = title.strip()
                            description = description.strip()

                            if not (
                                company
                                and title
                                and description
                            ):
                                page_skipped += 1
                                continue

                            # Filter technical roles
                            if not is_relevant_job(title):
                                page_skipped += 1
                                continue

                            # Check duplicates
                            job_key = (
                                normalize(company),
                                normalize(title)
                            )

                            if job_key in existing_jobs:
                                page_skipped += 1
                                continue

                            # Add to existing SQLite database
                            new_job = Job(
                                company_name=company,
                                job_title=title,
                                description=description
                            )

                            db_session.add(new_job)

                            existing_jobs.add(job_key)

                            total_added += 1
                            page_added += 1

                            print(
                                f"Added: {title}"
                            )

                            if (
                                total_added
                                >= TARGET_NEW_JOBS
                            ):
                                break

                        db_session.commit()

                    print(
                        f"New jobs this page: {page_added}"
                    )

                    print(
                        f"Skipped records: {page_skipped}"
                    )

                    print(
                        f"Total new jobs: {total_added}"
                    )

                    # Continue to next API page
                    cursor = data.get("next_cursor")

                    if not cursor:
                        break

                    # Small pause to avoid rapid requests
                    time.sleep(1)

        except RuntimeError as error:
            print(f"\nCollection stopped: {error}")

    # Verify actual SQLite count
    with Session(engine) as session:

        total_jobs = session.scalar(
            select(func.count()).select_from(Job)
        )

    print("\n================================")
    print("JOB COLLECTION SUMMARY")
    print("================================")

    print(
        f"API records received: {total_received}"
    )

    print(
        f"New jobs added: {total_added}"
    )

    print(
        f"Total jobs in SQLite: {total_jobs}"
    )

    print("================================")


# ==========================================
# RUN SCRIPT
# ==========================================

if __name__ == "__main__":
    fetch_more_jobs()
