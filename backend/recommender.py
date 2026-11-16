
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import engine
from backend.models import Job


# Model and cache settings
BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "job_embeddings_cache.npz"

MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def get_job_texts(jobs):
    """Prepare text from job titles and descriptions."""

    job_texts = []

    for job in jobs:
        text = f"{job.job_title}. {job.description or ''}"
        job_texts.append(text)

    return job_texts


def create_cache_key(jobs):
    """Create a fingerprint of the job dataset."""

    job_data = []

    for job in jobs:
        job_data.append({
            "id": job.id,
            "company": job.company_name,
            "title": job.job_title,
            "description": job.description
        })

    content = json.dumps(
        {
            "model": MODEL_NAME,
            "jobs": job_data
        },
        sort_keys=True
    )

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def get_job_embeddings(jobs, job_texts):
    """Reuse cached job embeddings when possible."""

    cache_key = create_cache_key(jobs)

    if CACHE_PATH.exists():
        try:
            with np.load(
                CACHE_PATH,
                allow_pickle=False
            ) as cache:

                saved_key = str(cache["cache_key"].item())
                embeddings = cache["embeddings"]

                if (
                    saved_key == cache_key
                    and embeddings.ndim == 2
                    and len(embeddings) == len(jobs)
                    and embeddings.shape[1] == 384
                ):
                    print("Using cached job embeddings.")
                    return embeddings

        except (OSError, ValueError, KeyError):
            print("Cache could not be loaded. Rebuilding.")

    print("Generating job embeddings...")

    embeddings = model.encode(
        job_texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    np.savez_compressed(
        CACHE_PATH,
        cache_key=cache_key,
        embeddings=embeddings
    )

    print("Job embeddings saved to cache.")

    return embeddings


def build_resume_profile(resume_text, detected_skills=None):
    """Build a short skills-based profile."""

    valid_skills = []

    for skill in detected_skills or []:
        if isinstance(skill, str) and skill.strip():
            valid_skills.append(skill.strip())

    if valid_skills:
        skills_text = ", ".join(valid_skills)

        return (
            "Candidate with technical skills and knowledge in "
            f"{skills_text}."
        )

    return resume_text


def classify_job_type(job_title):
    """
    Classify using explicit title indicators.

    Avoid guessing that a generic job is entry-level.
    """

    title = (job_title or "").lower()

    # Internship roles
    internship_pattern = (
        r"\b(internship|intern|industrial training)\b"
    )

    if re.search(internship_pattern, title):
        return "internship"

    # Clearly senior positions are not entry-level
    senior_pattern = (
        r"\b(senior|sr\.?|lead|principal|staff|"
        r"manager|head|director)\b"
    )

    if re.search(senior_pattern, title):
        return "unclassified"

    # Explicit junior / graduate titles
    entry_pattern = (
        r"\b(junior|jr\.?|entry[\s-]?level|"
        r"fresh[\s-]?graduate|freshers?|"
        r"graduate|trainee)\b"
    )

    if re.search(entry_pattern, title):
        return "entry"

    # Insufficient information
    return "unclassified"


def find_matching_skills(
    detected_skills,
    job_title,
    job_description
):
    """Find resume skills explicitly mentioned in a listing."""

    matched_skills = []
    seen_skills = set()

    job_text = (
        f"{job_title or ''} "
        f"{job_description or ''}"
    )

    for skill in detected_skills or []:

        if not isinstance(skill, str):
            continue

        skill = skill.strip()

        if not skill:
            continue

        if skill.lower() in seen_skills:
            continue

        pattern = (
            r"(?<!\w)"
            + re.escape(skill)
            + r"(?!\w)"
        )

        if re.search(
            pattern,
            job_text,
            flags=re.IGNORECASE
        ):
            matched_skills.append(skill)
            seen_skills.add(skill.lower())

    return matched_skills


def recommend_jobs(
    resume_text,
    detected_skills=None,
    job_type="all"
):
    """Rank eligible jobs using semantic similarity."""

    valid_types = ["all", "internship", "entry"]

    if job_type not in valid_types:
        raise ValueError("Invalid job type")

    if not resume_text or not resume_text.strip():
        return []

    # Retrieve all jobs
    with Session(engine) as session:
        jobs = session.scalars(
            select(Job).order_by(Job.id)
        ).all()

    if not jobs:
        return []

    # Identify eligible jobs first
    eligible_indices = []

    for i in range(len(jobs)):
        category = classify_job_type(jobs[i].job_title)

        if job_type == "all" or category == job_type:
            eligible_indices.append(i)

    print(f"Job filter: {job_type}")
    print(f"Eligible jobs: {len(eligible_indices)}")

    if not eligible_indices:
        return []

    # Build short skills profile
    resume_profile = build_resume_profile(
        resume_text,
        detected_skills
    )

    # Keep profile within model input limit
    tokens = model.tokenizer.encode(
        resume_profile,
        add_special_tokens=False,
        truncation=True,
        max_length=180
    )

    resume_profile = model.tokenizer.decode(
        tokens,
        skip_special_tokens=True
    )

    # Generate resume embedding
    resume_embedding = model.encode(
        resume_profile,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    # Reuse cached embeddings for ALL database jobs
    # This keeps one cache for every job-type filter.
    job_texts = get_job_texts(jobs)

    job_embeddings = get_job_embeddings(
        jobs,
        job_texts
    )

    # Calculate semantic similarity
    scores = job_embeddings @ resume_embedding

    recommendations = []

    # Only rank jobs eligible for the chosen filter
    for i in eligible_indices:

        matched_skills = find_matching_skills(
            detected_skills,
            jobs[i].job_title,
            jobs[i].description
        )

        category = classify_job_type(jobs[i].job_title)

        recommendations.append({
            "company_name": jobs[i].company_name,
            "job_title": jobs[i].job_title,
            "similarity_score": float(scores[i]),
            "matched_skills": matched_skills,
            "job_type": category
        })

    recommendations.sort(
        key=lambda job: job["similarity_score"],
        reverse=True
    )

    return recommendations[:5]


# Standalone testing
if __name__ == "__main__":

    sample_resume = """
    Information Technology graduate with experience
    developing applications and REST APIs.
    Worked on machine learning projects using Python.
    """

    sample_skills = [
        "Python",
        "React",
        "SQL",
        "FastAPI",
        "Machine Learning"
    ]

    print("\nTesting internship recommendations:\n")

    results = recommend_jobs(
        sample_resume,
        sample_skills,
        job_type="internship"
    )

    for job in results:
        print(f"Job: {job['job_title']}")
        print(f"Company: {job['company_name']}")
        print(f"Type: {job['job_type']}")
        print(f"Similarity: {job['similarity_score']:.4f}")
        print(f"Matching Skills: {job['matched_skills']}")
        print("---------------------------")
