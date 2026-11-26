import hashlib
import json
import re
from pathlib import Path

import numpy as np

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database import engine
from backend.models import Job, Posting


# Model and cache settings
BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "job_embeddings_cache.npz"

MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


# Curated IT skills vocabulary: (Display Label, Regex Pattern)
TECH_SKILLS_PATTERNS = [
    ("Python", r"(?<!\w)python(?!\w)"),
    ("Java", r"(?<!\w)java(?!\w)"),
    ("JavaScript", r"(?<!\w)(?:javascript|js)(?!\w)"),
    ("TypeScript", r"(?<!\w)(?:typescript|ts)(?!\w)"),
    ("C++", r"(?<!\w)c\+\+(?!\w)"),
    ("C#", r"(?<!\w)c#(?!\w)"),
    ("PHP", r"(?<!\w)php(?!\w)"),
    ("Dart", r"(?<!\w)dart(?!\w)"),
    ("Go", r"(?<!\w)golang(?!\w)"),
    ("Rust", r"(?<!\w)rust(?!\w)"),
    ("Kotlin", r"(?<!\w)kotlin(?!\w)"),
    ("Swift", r"(?<!\w)swift(?!\w)"),
    ("HTML5", r"(?<!\w)html5?(?!\w)"),
    ("CSS3", r"(?<!\w)css3?(?!\w)"),
    ("React", r"(?<!\w)react(?:\.js|js)?(?!\w)"),
    ("Next.js", r"(?<!\w)next(?:\.js|js)(?!\w)"),
    ("Vue.js", r"(?<!\w)vue(?:\.js|js)?(?!\w)"),
    ("Angular", r"(?<!\w)angular(?!\w)"),
    ("Node.js", r"(?<!\w)node(?:\.js|js)?(?!\w)"),
    ("Express.js", r"(?<!\w)express(?:\.js|js)?(?!\w)"),
    ("FastAPI", r"(?<!\w)fastapi(?!\w)"),
    ("Flask", r"(?<!\w)flask(?!\w)"),
    ("Django", r"(?<!\w)django(?!\w)"),
    ("Spring Boot", r"(?<!\w)spring\s*boot(?!\w)"),
    ("Laravel", r"(?<!\w)laravel(?!\w)"),
    (".NET", r"(?<!\w)\.net(?:\s*core)?(?!\w)"),
    ("Flutter", r"(?<!\w)flutter(?!\w)"),
    ("React Native", r"(?<!\w)react\s*native(?!\w)"),
    ("REST APIs", r"(?<!\w)rest(?:ful)?\s*apis?(?!\w)"),
    ("GraphQL", r"(?<!\w)graphql(?!\w)"),
    ("SQL", r"(?<!\w)sql(?!\w)"),
    ("MySQL", r"(?<!\w)mysql(?!\w)"),
    ("PostgreSQL", r"(?<!\w)postgres(?:ql)?(?!\w)"),
    ("SQLite", r"(?<!\w)sqlite3?(?!\w)"),
    ("MongoDB", r"(?<!\w)mongodb(?!\w)"),
    ("Redis", r"(?<!\w)redis(?!\w)"),
    ("Firebase", r"(?<!\w)firebase(?!\w)"),
    ("Machine Learning", r"(?<!\w)machine\s*learning(?!\w)"),
    ("Deep Learning", r"(?<!\w)deep\s*learning(?!\w)"),
    ("NLP", r"(?<!\w)(?:nlp|natural\s*language\s*processing)(?!\w)"),
    ("Computer Vision", r"(?<!\w)computer\s*vision(?!\w)"),
    ("TensorFlow", r"(?<!\w)tensorflow(?!\w)"),
    ("PyTorch", r"(?<!\w)pytorch(?!\w)"),
    ("Scikit-learn", r"(?<!\w)scikit[\s-]?learn(?!\w)"),
    ("Pandas", r"(?<!\w)pandas(?!\w)"),
    ("NumPy", r"(?<!\w)numpy(?!\w)"),
    ("Power BI", r"(?<!\w)power\s*bi(?!\w)"),
    ("Tableau", r"(?<!\w)tableau(?!\w)"),
    ("Docker", r"(?<!\w)docker(?!\w)"),
    ("Kubernetes", r"(?<!\w)kubernetes(?!\w)"),
    ("AWS", r"(?<!\w)(?:aws|amazon\s*web\s*services)(?!\w)"),
    ("Azure", r"(?<!\w)(?:microsoft\s*)?azure(?!\w)"),
    ("GCP", r"(?<!\w)(?:gcp|google\s*cloud)(?!\w)"),
    ("Linux", r"(?<!\w)linux(?!\w)"),
    ("Git", r"(?<!\w)git(?!\w)"),
    ("CI/CD", r"(?<!\w)ci\s*/\s*cd(?!\w)"),
    ("Jenkins", r"(?<!\w)jenkins(?!\w)"),
    ("Selenium", r"(?<!\w)selenium(?!\w)"),
    ("Playwright", r"(?<!\w)playwright(?!\w)"),
    ("Postman", r"(?<!\w)postman(?!\w)"),
    ("SAP", r"(?<!\w)sap(?!\w)"),
    ("IoT", r"(?<!\w)(?:iot|internet\s*of\s*things)(?!\w)"),
    ("Embedded C", r"(?<!\w)embedded\s*c(?!\w)"),
    ("Firmware", r"(?<!\w)firmware(?!\w)")
]


def serialize_posting(posting: Posting) -> dict:
    return {
        "id": posting.id,
        "api_posting_id": posting.api_posting_id,
        "source_posting_id": posting.source_posting_id,
        "posting_source": posting.posting_source,
        "posting_url": posting.posting_url,
        "application_url": posting.application_url,
        "location": posting.location,
        "posting_status": posting.posting_status,
        "latest_check_result": posting.latest_check_result,
        "latest_checked_at": posting.latest_checked_at,
        "source_posted_at": posting.source_posted_at,
        "first_seen_at": posting.first_seen_at,
        "last_completed_fetch_at": posting.last_completed_fetch_at
    }


def serialize_postings(postings: list[Posting]) -> list[dict]:
    ranked = sorted(
        postings,
        key=lambda p: (
            p.posting_status == "listed",
            p.latest_check_result == "available",
            p.latest_check_result not in ("closed", "broken"),
            bool(p.application_url),
            bool(p.posting_url),
            bool(p.location)
        ),
        reverse=True
    )

    return [serialize_posting(p) for p in ranked]


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


def extract_job_skills(job_title, job_description):
    """Extract standardized technical skills required or mentioned by a job."""

    job_text = f"{job_title or ''} {job_description or ''}"
    found_skills = []

    for label, pattern in TECH_SKILLS_PATTERNS:
        if re.search(pattern, job_text, flags=re.IGNORECASE):
            found_skills.append(label)

    return found_skills


def analyze_skill_gap(
    detected_skills,
    job_title,
    job_description
):
    """
    Compute matched skills, missing job skills, and skill overlap ratio.
    """
    matched_skills = find_matching_skills(
        detected_skills,
        job_title,
        job_description
    )

    job_required_skills = extract_job_skills(
        job_title,
        job_description
    )

    candidate_normalized = {
        s.strip().lower()
        for s in (detected_skills or [])
        if isinstance(s, str) and s.strip()
    }
    matched_normalized = {
        s.strip().lower()
        for s in matched_skills
    }

    missing_skills = []
    covered_job_skills = 0

    for job_skill in job_required_skills:
        key = job_skill.lower()
        is_covered = (
            key in candidate_normalized
            or key in matched_normalized
            or any(
                key == c.replace(".js", "")
                or c == key.replace(".js", "")
                for c in candidate_normalized
            )
        )

        if is_covered:
            covered_job_skills += 1
        else:
            missing_skills.append(job_skill)

    if job_required_skills:
        overlap_ratio = covered_job_skills / len(job_required_skills)
    else:
        overlap_ratio = 0.0

    return matched_skills, missing_skills[:6], overlap_ratio


def recommend_jobs(
    resume_text,
    detected_skills=None,
    job_type="all"
):
    """
    Rank eligible jobs using hybrid semantic + skill overlap scoring
    and return all roles meeting the 50% threshold (up to 20).
    """

    valid_types = ["all", "internship", "entry"]

    if job_type not in valid_types:
        raise ValueError("Invalid job type")

    if not resume_text or not resume_text.strip():
        return []

    # Retrieve all jobs with postings eagerly loaded
    with Session(engine) as session:
        jobs = session.scalars(
            select(Job)
            .options(selectinload(Job.postings))
            .order_by(Job.id)
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
            job = jobs[i]

            matched_skills, missing_skills, overlap_ratio = analyze_skill_gap(
                detected_skills,
                job.job_title,
                job.description
            )

            semantic_score = float(scores[i])
            has_job_skills = bool(matched_skills or missing_skills)

            if detected_skills and has_job_skills:
                hybrid_score = (0.75 * semantic_score) + (0.25 * overlap_ratio)
            else:
                hybrid_score = semantic_score

            match_tier = (
                "strong"
                if hybrid_score >= 0.65
                else "good"
            )

            category = classify_job_type(job.job_title)
            serialized_postings = serialize_postings(job.postings)
            primary_posting = (
                serialized_postings[0] if serialized_postings else None
            )

            fallback_location = (
                primary_posting["location"] if primary_posting else None
            )
            fallback_url = (
                (
                    primary_posting["application_url"]
                    or primary_posting["posting_url"]
                )
                if primary_posting
                else None
            )
            fallback_date = (
                primary_posting["latest_checked_at"][:10]
                if (
                    primary_posting
                    and primary_posting["latest_checked_at"]
                )
                else None
            )

            recommendations.append({
                "id": job.id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "description": job.description,
                "work_description": job.work_description,
                "location": job.location or fallback_location,
                "application_url": job.application_url or fallback_url,
                "date_verified": job.date_verified or fallback_date,
                "postings": serialized_postings,
                "similarity_score": hybrid_score,
                "semantic_score": semantic_score,
                "skill_overlap_score": float(overlap_ratio),
                "match_tier": match_tier,
                "matched_skills": matched_skills,
                "missing_skills": missing_skills,
                "job_type": category
            })

    # Keep all roles meeting the 50% quality threshold (up to 20 roles)
    qualified = [
        job for job in recommendations
        if job["similarity_score"] >= 0.50
    ]

    # Fallback: if a narrow filter yields < 5 above 50%, keep top 5 anyway
    if len(qualified) < 5:
        recommendations.sort(
            key=lambda job: job["similarity_score"],
            reverse=True
        )
        return recommendations[:5]

    qualified.sort(
        key=lambda job: job["similarity_score"],
        reverse=True
    )

    return qualified[:20]


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
        print(f"Job: {job['job_title']} ({job['match_tier'].upper()})")
        print(f"Company: {job['company_name']}")
        print(f"Type: {job['job_type']}")
        print(
            f"Hybrid Score: {job['similarity_score']:.4f} "
            f"(Semantic: {job['semantic_score']:.4f}, "
            f"Overlap: {job['skill_overlap_score']:.2f})"
        )
        print(f"Matching Skills: {job['matched_skills']}")
        print(f"Missing Skills: {job['missing_skills']}")
        print("---------------------------")