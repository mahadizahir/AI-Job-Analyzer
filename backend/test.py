
import os
import csv
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("HEADCOUNTLABS_API_KEY")

if not api_key:
    raise ValueError("API key not found")

url = "https://api.headcountlabs.com/v1/jobs/"

search_titles = [
    "software",
    "developer",
    "data",
    "machine learning",
    "intern",
    "graduate"
]

it_keywords = [
    "software",
    "developer",
    "python",
    "data",
    "machine learning",
    "web",
    "programmer",
    "cybersecurity",
    "it intern",
    "ai engineer"
]

exclude_keywords = [
    "sales",
    "marketing",
    "senior",
    "manager",
    "director",
    "principal",
    "lead"
]

headers = {
    "Authorization": f"Bearer {api_key}"
}

saved_jobs = set()
collected_jobs = []

for search_title in search_titles:

    params = {
        "country": "MY",
        "title": search_title,
        "currentness": "current",
        "limit": 25
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    for job in data.get("data", []):
        company = (job.get("employer_name") or {}).get("value")
        title = (job.get("title") or {}).get("value")
        description = (job.get("description") or {}).get("value")

        if not company or not title or not description:
            continue

        title_lower = title.lower()

        is_it = False

        for keyword in it_keywords:
            if keyword in title_lower:
                is_it = True
                break

        if not is_it:
            continue

        exclude_job = False

        for word in exclude_keywords:
            if word in title_lower:
                exclude_job = True
                break

        if exclude_job:
            continue

        job_key = (company.lower().strip(), title_lower.strip())

        if job_key in saved_jobs:
            continue

        saved_jobs.add(job_key)

        collected_jobs.append({
            "company_name": company,
            "job_title": title,
            "description": description
        })

        print(f"Saved job: {title}")

        if len(collected_jobs) >= 50:
            break

    if len(collected_jobs) >= 50:
        break

csv_path = BASE_DIR / "jobs.csv"

with open(csv_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "company_name",
            "job_title",
            "description"
        ]
    )

    writer.writeheader()
    writer.writerows(collected_jobs)

print(f"Total jobs collected: {len(collected_jobs)}")
