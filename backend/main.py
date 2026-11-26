from io import BytesIO

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database import engine
from backend.groq_service import extract_skills
from backend.models import Base, Job
from backend.recommender import recommend_jobs, serialize_postings


# Ensure tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Job Analyzer & Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExplainMatchRequest(BaseModel):
    detected_skills: list[str]
    job_title: str
    company_name: str
    description: str = ""
    matched_skills: list[str] = []


def extract_text_from_pdf(file_bytes: bytes) -> dict:
    reader = PdfReader(BytesIO(file_bytes))
    pages_text = []

    for page in reader.pages:
        content = page.extract_text() or ""
        if content.strip():
            pages_text.append(content.strip())

    return {
        "text": "\n\n".join(pages_text),
        "total_pages": len(reader.pages),
    }


def build_match_explanation(
    detected_skills: list[str],
    job_title: str,
    company_name: str,
    matched_skills: list[str],
) -> str:
    if matched_skills:
        skills_str = ", ".join(matched_skills)
        return (
            f"Candidate's {skills_str} skills directly align with the technical "
            f"requirements for {job_title} at {company_name}."
        )

    if detected_skills:
        top_skills = ", ".join(detected_skills[:5])
        return (
            f"Matched primarily on overall role context and transferable background "
            f"({top_skills}) for {job_title} at {company_name}."
        )

    return f"Matched based on overall role alignment for {job_title} at {company_name}."


@app.get("/")
def root():
    return {"message": "AI Job Analyzer API is running"}


@app.get("/jobs")
def get_jobs():
    with Session(engine) as session:
        jobs = session.scalars(
            select(Job)
            .options(selectinload(Job.postings))
            .order_by(Job.id.desc())
        ).all()

        results = []
        for job in jobs:
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

            results.append({
                "id": job.id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "description": job.description,
                "work_description": job.work_description,
                "location": job.location or fallback_location,
                "application_url": job.application_url or fallback_url,
                "date_verified": job.date_verified or fallback_date,
                "postings": serialized_postings,
            })

        return results


@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    job_type: str = Form("all"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files (.pdf) are supported.",
        )

    if job_type not in ("all", "internship", "entry"):
        raise HTTPException(
            status_code=400,
            detail="Invalid job_type filter. Expected 'all', 'internship', or 'entry'.",
        )

    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded PDF file is empty.",
        )

    try:
        parsed = extract_text_from_pdf(file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse PDF: {exc}",
        ) from exc

    resume_text = parsed.get("text", "")
    total_pages = parsed.get("total_pages", 1)

    if not resume_text or not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text found in the uploaded PDF.",
        )

    detected_skills = extract_skills(resume_text)

    recommended_jobs = recommend_jobs(
        resume_text=resume_text,
        detected_skills=detected_skills,
        job_type=job_type,
    )

    for idx, job in enumerate(recommended_jobs):
        if idx < 5:
            job["explanation"] = build_match_explanation(
                detected_skills=detected_skills,
                job_title=job["job_title"],
                company_name=job["company_name"],
                matched_skills=job.get("matched_skills", []),
            )
        else:
            job["explanation"] = None

    return {
        "filename": file.filename,
        "total_pages": total_pages,
        "selected_job_type": job_type,
        "detected_skills": detected_skills,
        "recommended_jobs": recommended_jobs,
    }


@app.post("/explain-match")
def explain_match(payload: ExplainMatchRequest):
    explanation = build_match_explanation(
        detected_skills=payload.detected_skills,
        job_title=payload.job_title,
        company_name=payload.company_name,
        matched_skills=payload.matched_skills,
    )
    return {"explanation": explanation}