from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    company_name: Mapped[str] = mapped_column(String(200))

    job_title: Mapped[str] = mapped_column(String(200))

    description: Mapped[str] = mapped_column(Text)

    work_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )

    application_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    date_verified: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )

    postings: Mapped[list["Posting"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan"
    )


class Posting(Base):
    __tablename__ = "postings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id"), nullable=False
    )

    api_posting_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )

    source_posting_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    posting_source: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    posting_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    application_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    location: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )

    posting_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    latest_check_result: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    latest_checked_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    source_posted_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    first_seen_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    last_completed_fetch_at: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    job: Mapped["Job"] = relationship(
        back_populates="postings"
    )