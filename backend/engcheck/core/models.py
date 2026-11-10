"""Ma'lumotlar modeli (spetsifikatsiya 4-bo'lim)."""
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Role(StrEnum):
    admin = "admin"
    lead = "lead"
    engineer = "engineer"
    viewer = "viewer"


class Stage(StrEnum):
    FEED = "FEED"
    DD = "DD"
    AS_BUILT = "AS_BUILT"


class DocType(StrEnum):
    PFD = "PFD"
    PID = "PID"
    DATASHEET = "DATASHEET"
    EQUIPMENT_LIST = "EQUIPMENT_LIST"
    LINE_LIST = "LINE_LIST"
    MATERIAL_SPEC = "MATERIAL_SPEC"
    CALCULATION = "CALCULATION"
    HAZOP = "HAZOP"
    HAZID = "HAZID"
    OTHER = "OTHER"


class Discipline(StrEnum):
    process = "process"
    mechanical = "mechanical"
    piping = "piping"
    instrumentation = "instrumentation"
    electrical = "electrical"
    civil = "civil"
    hse = "hse"
    technical = "technical"


class Severity(StrEnum):
    critical = "critical"
    major = "major"
    minor = "minor"
    info = "info"


class Confidence(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class FindingStatus(StrEnum):
    new = "new"
    reviewed = "reviewed"
    confirmed = "confirmed"
    rejected = "rejected"
    fixed = "fixed"


class ParseStatus(StrEnum):
    pending = "pending"
    parsed = "parsed"
    needs_ocr = "needs_ocr"
    unsupported = "unsupported"
    error = "error"


class TagClass(StrEnum):
    equipment = "equipment"
    line = "line"
    instrument = "instrument"
    pipe_class = "pipe_class"


class Method(StrEnum):
    cell = "cell"
    regex = "regex"


def _pk() -> Mapped[int]:
    return mapped_column(Integer, primary_key=True)


def _fk(target: str, nullable: bool = False) -> Mapped[int]:
    return mapped_column(ForeignKey(target, ondelete="CASCADE"), nullable=nullable, index=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = _pk()
    login: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(String(16))
    locale: Mapped[str] = mapped_column(String(2), default="uz")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = _pk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = _fk("users.id")
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = _pk()
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(40))
    stage: Mapped[Stage] = mapped_column(String(16))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("project_id", "sha256"),)
    id: Mapped[int] = _pk()
    project_id: Mapped[int] = _fk("projects.id")
    filename: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[DocType] = mapped_column(String(20))
    discipline: Mapped[Discipline] = mapped_column(String(20))
    doc_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    stored_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(String(16), default=ParseStatus.pending)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    unmapped_headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocPage(Base):
    __tablename__ = "doc_pages"
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = _fk("documents.id")
    page_no: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("project_id", "tag"),)
    id: Mapped[int] = _pk()
    project_id: Mapped[int] = _fk("projects.id")
    tag: Mapped[str] = mapped_column(String(64))
    tag_class: Mapped[TagClass] = mapped_column(String(16))


class TagOccurrence(Base):
    __tablename__ = "tag_occurrences"
    id: Mapped[int] = _pk()
    tag_id: Mapped[int] = _fk("tags.id")
    document_id: Mapped[int] = _fk("documents.id")
    page_no: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(80))
    method: Mapped[Method] = mapped_column(String(8))
    tag: Mapped[Tag] = relationship()
    document: Mapped[Document] = relationship()


class TagParam(Base):
    __tablename__ = "tag_params"
    id: Mapped[int] = _pk()
    tag_id: Mapped[int] = _fk("tags.id")
    param: Mapped[str] = mapped_column(String(40))
    raw_value: Mapped[str] = mapped_column(String(255))
    raw_unit: Mapped[str | None] = mapped_column(String(24), nullable=True)
    number: Mapped[float | None] = mapped_column(Float, nullable=True)
    si_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    si_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_known: Mapped[bool] = mapped_column(Boolean, default=True)
    document_id: Mapped[int] = _fk("documents.id")
    page_no: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(80))
    method: Mapped[Method] = mapped_column(String(8))
    confidence: Mapped[Confidence] = mapped_column(String(8))
    tag: Mapped[Tag] = relationship()
    document: Mapped[Document] = relationship()


class DocRef(Base):
    __tablename__ = "doc_refs"
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = _fk("documents.id")
    ref_doc_number: Mapped[str] = mapped_column(String(64))
    ref_revision: Mapped[str] = mapped_column(String(16))
    page_no: Mapped[int] = mapped_column(Integer)
    document: Mapped[Document] = relationship()


class Standard(Base):
    __tablename__ = "standards"
    id: Mapped[int] = _pk()
    code: Mapped[str] = mapped_column(String(64))
    edition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active/superseded/withdrawn
    license_type: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[int] = _pk()
    code: Mapped[str] = mapped_column(String(8), unique=True)
    title_uz: Mapped[str] = mapped_column(String(255))
    title_en: Mapped[str] = mapped_column(String(255))
    title_ru: Mapped[str] = mapped_column(String(255))
    severity: Mapped[Severity] = mapped_column(String(10))
    standard_id: Mapped[int | None] = mapped_column(ForeignKey("standards.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    standard: Mapped[Standard | None] = relationship()


class ReviewRun(Base):
    __tablename__ = "review_runs"
    id: Mapped[int] = _pk()
    project_id: Mapped[int] = _fk("projects.id")
    started_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ai_mode: Mapped[str] = mapped_column(String(8), default="none")
    errors: Mapped[list] = mapped_column(JSON, default=list)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[int] = _pk()
    run_id: Mapped[int] = _fk("review_runs.id")
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"))
    tag_id: Mapped[int | None] = mapped_column(ForeignKey("tags.id", ondelete="SET NULL"), nullable=True)
    tag_text: Mapped[str | None] = mapped_column(String(64), nullable=True)
    param: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description_key: Mapped[str] = mapped_column(String(40))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(String(10))
    source_type: Mapped[str] = mapped_column(String(8), default="rule")
    confidence: Mapped[Confidence] = mapped_column(String(8))
    status: Mapped[FindingStatus] = mapped_column(String(12), default=FindingStatus.new)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    rule: Mapped[Rule] = relationship()
    evidence: Mapped[list["FindingEvidence"]] = relationship(cascade="all, delete-orphan")
    actions: Mapped[list["FindingAction"]] = relationship(cascade="all, delete-orphan",
                                                          order_by="FindingAction.id")


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    id: Mapped[int] = _pk()
    finding_id: Mapped[int] = _fk("findings.id")
    document_id: Mapped[int] = _fk("documents.id")
    page_no: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(String(255))
    document: Mapped[Document] = relationship()


class FindingAction(Base):
    __tablename__ = "finding_actions"
    id: Mapped[int] = _pk()
    finding_id: Mapped[int] = _fk("findings.id")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = _pk()
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    object_type: Mapped[str] = mapped_column(String(24))
    object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
