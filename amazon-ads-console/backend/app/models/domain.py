from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class CpoJob(Base):
    __tablename__ = "cpo_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    data_date: Mapped[date] = mapped_column(Date)
    operator: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="PROCESSING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CpoJobIssue(Base):
    __tablename__ = "cpo_job_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("cpo_jobs.id"))
    code: Mapped[str] = mapped_column(String(64))
    campaign_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")

class CampaignProductRule(Base):
    __tablename__ = "campaign_product_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    campaign_name: Mapped[str] = mapped_column(String(255))
    allocation_method: Mapped[str] = mapped_column(String(64))
    product_scope: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")

class CampaignAdTypeMapping(Base):
    __tablename__ = "campaign_ad_type_mapping"
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    campaign_name: Mapped[str] = mapped_column(String(255))
    ad_type_l1: Mapped[str] = mapped_column(String(16))
    ad_type_l2: Mapped[str] = mapped_column(String(32))
    classification_source: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")
