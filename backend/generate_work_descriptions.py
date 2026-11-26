
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import engine
from backend.models import Job
from backend.groq_service import generate_work_description


def generate_all_work_descriptions():

    with Session(engine) as session:
        jobs = session.scalars(
            select(Job).order_by(Job.id)
        ).all()

        total_jobs = len(jobs)

        print(f"Total jobs: {total_jobs}")

        generated = 0
        skipped = 0
        failed = 0

        for index, job in enumerate(jobs, start=1):

            print(
                f"\n[{index}/{total_jobs}] "
                f"{job.job_title} - {job.company_name}"
            )

            if job.work_description:
                print("Skipped: Work description already exists.")
                skipped += 1
                continue

            if not job.description or not job.description.strip():
                print("Skipped: Original description is empty.")
                skipped += 1
                continue

            try:
                summary = generate_work_description(
                    job.job_title,
                    job.company_name,
                    job.description
                )

                if not summary:
                    print("Skipped: Not enough information.")
                    skipped += 1
                    continue

                job.work_description = summary

                session.commit()

                generated += 1

                print("Work description generated:")
                print(summary)

            except Exception as error:
                session.rollback()

                failed += 1

                print(
                    f"Failed: {type(error).__name__}: {error}"
                )

        print("\n------------------------------")
        print("Generation completed.")
        print(f"Generated: {generated}")
        print(f"Skipped: {skipped}")
        print(f"Failed: {failed}")
        print("------------------------------")


if __name__ == "__main__":
    generate_all_work_descriptions()
