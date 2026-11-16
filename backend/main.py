
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from pypdf import PdfReader

from backend.database import engine
from backend.models import Job
from backend.groq_service import extract_skills
from backend.recommender import recommend_jobs
from backend.explanation_service import add_explanations
from backend.job_metadata import enrich_jobs


app = FastAPI()


# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Homepage
@app.get("/")
def home():
    return {
        "message": "AI Job Recommendation API is running"
    }


# Get jobs from SQLite
@app.get("/jobs")
def get_jobs(keyword: str = ""):

    with Session(engine) as session:
        query = select(Job)

        if keyword:
            query = query.where(
                Job.job_title.ilike(f"%{keyword}%")
            )

        jobs = session.scalars(query).all()

        result = []

        for job in jobs:
            result.append({
                "id": job.id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "description": job.description
            })

    # Add verified metadata
    return enrich_jobs(result)


# Count total jobs
@app.get("/jobs/count")
def count_jobs():

    with Session(engine) as session:
        total = session.scalar(
            select(func.count()).select_from(Job)
        )

    return {
        "total_jobs": total
    }


# Upload resume and generate AI recommendations
@app.post("/upload-resume")
def upload_resume(
    file: UploadFile = File(...),
    job_type: str = Form("all")
):

    # Validate job type
    if job_type not in ["all", "internship", "entry"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid job type selected"
        )

    # Validate PDF filename
    if (
        not file.filename
        or not file.filename.lower().endswith(".pdf")
    ):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file"
        )

    try:
        reader = PdfReader(file.file)

        if len(reader.pages) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 pages allowed"
            )

        resume_text = ""

        for page in reader.pages:
            text = page.extract_text()

            if text:
                resume_text += text + "\n"

        if not resume_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text found in PDF"
            )

        total_pages = len(reader.pages)

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read PDF"
        )

    finally:
        file.file.close()

    # Step 1: Extract technical skills using Groq
    try:
        detected_skills = extract_skills(resume_text)

    except Exception as error:
        print(
            f"Groq error: {type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=503,
            detail="AI skill extraction is temporarily unavailable"
        ) from error

    # Step 2: Semantic job recommendation
    try:
        recommended_jobs = recommend_jobs(
            resume_text,
            detected_skills,
            job_type=job_type
        )

    except Exception as error:
        print(
            f"Recommendation error: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=503,
            detail="Job recommendations are temporarily unavailable"
        ) from error

    # Step 3: Generate Groq job explanations
    try:
        recommended_jobs = add_explanations(
            recommended_jobs
        )

    except Exception as error:
        print(
            f"Explanation error: "
            f"{type(error).__name__}: {error}"
        )

        for job in recommended_jobs:
            job["explanation"] = (
                "An explanation is temporarily unavailable. "
                "Please review the job requirements."
            )

    # Step 4: Attach job application metadata
    recommended_jobs = enrich_jobs(
        recommended_jobs
    )

    # Return results to React
    return {
        "filename": file.filename,
        "total_pages": total_pages,
        "selected_job_type": job_type,
        "detected_skills": detected_skills,
        "recommended_jobs": recommended_jobs
    }
