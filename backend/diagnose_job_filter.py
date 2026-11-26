
from requests import Session

from backend.fetch_more_jobs import (
    API_KEY,
    API_URL,
    PAGE_SIZE,
    get_value,
    normalize,
    is_relevant_job,
    load_existing_jobs
)


def diagnose():
    if not API_KEY:
        print("HEADCOUNTLABS_API_KEY not found.")
        return

    existing_jobs = load_existing_jobs()

    params = {
        "country": "MY",
        "title": "software",
        "currentness": "current",
        "limit": PAGE_SIZE
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    with Session() as api_session:

        api_session.headers.update(headers)

        response = api_session.get(
            API_URL,
            params=params,
            timeout=35
        )

        response.raise_for_status()

        data = response.json()
        records = data.get("data", [])

    print(f"Records received: {len(records)}")
    print("\nJOB FILTER DIAGNOSTIC")
    print("=" * 60)

    counts = {
        "missing_fields": 0,
        "irrelevant_title": 0,
        "duplicate": 0,
        "potentially_new": 0
    }

    for job_data in records:

        if not isinstance(job_data, dict):
            continue

        company = get_value(
            job_data.get("employer_name")
        )

        title = get_value(
            job_data.get("title")
        )

        description = get_value(
            job_data.get("description")
        )

        if not (
            isinstance(company, str)
            and isinstance(title, str)
            and isinstance(description, str)
            and company.strip()
            and title.strip()
            and description.strip()
        ):
            status = "MISSING REQUIRED FIELDS"
            counts["missing_fields"] += 1

        elif not is_relevant_job(title):
            status = "IRRELEVANT TITLE"
            counts["irrelevant_title"] += 1

        else:
            job_key = (
                normalize(company),
                normalize(title)
            )

            if job_key in existing_jobs:
                status = "DUPLICATE"
                counts["duplicate"] += 1

            else:
                status = "POTENTIALLY NEW"
                counts["potentially_new"] += 1

        print(f"\nCompany: {company}")
        print(f"Title: {title}")
        print(f"Status: {status}")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")

    for reason, count in counts.items():
        print(f"{reason}: {count}")


if __name__ == "__main__":
    diagnose()
