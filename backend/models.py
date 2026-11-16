
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
