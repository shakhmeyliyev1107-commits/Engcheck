"""Qoidalar uchun umumiy turlar va so'rov yordamchilari."""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session as Db, joinedload

from ...core.models import (Confidence, DocType, Document, Method, ParseStatus, Severity, Tag,
                            TagOccurrence, TagParam)


@dataclass
class Evidence:
    document_id: int
    page_no: int
    location: str
    value: str


@dataclass
class Draft:
    rule_code: str
    tag_id: int | None
    tag_text: str | None
    param: str | None
    severity: Severity
    confidence: Confidence
    description_key: str
    args: dict
    evidence: list[Evidence] = field(default_factory=list)


class RuleBase:
    code: str = ""

    def check(self, db: Db, project_id: int) -> list[Draft]:
        raise NotImplementedError


def doc_label(doc: Document) -> str:
    return doc.doc_number or doc.filename


def project_params(db: Db, project_id: int) -> list[TagParam]:
    return (db.query(TagParam).join(Tag, TagParam.tag_id == Tag.id)
            .join(Document, TagParam.document_id == Document.id)
            .filter(Tag.project_id == project_id, Document.parse_status == ParseStatus.parsed)
            .options(joinedload(TagParam.tag), joinedload(TagParam.document))
            .order_by(TagParam.id).all())


def project_occurrences(db: Db, project_id: int) -> list[TagOccurrence]:
    return (db.query(TagOccurrence).join(Tag, TagOccurrence.tag_id == Tag.id)
            .join(Document, TagOccurrence.document_id == Document.id)
            .filter(Tag.project_id == project_id, Document.parse_status == ParseStatus.parsed)
            .options(joinedload(TagOccurrence.tag), joinedload(TagOccurrence.document))
            .order_by(TagOccurrence.id).all())


def parsed_docs(db: Db, project_id: int, doc_type: DocType | None = None) -> list[Document]:
    q = db.query(Document).filter_by(project_id=project_id, parse_status=ParseStatus.parsed)
    if doc_type is not None:
        q = q.filter_by(doc_type=doc_type)
    return q.order_by(Document.id).all()


def display_value(p: TagParam) -> str:
    """Hujjatdagi qiymat; birlik ustun sarlavhasidan olingan bo'lsa, qiymatga qo'shiladi."""
    if p.raw_unit and p.raw_unit not in p.raw_value:
        return f"{p.raw_value} {p.raw_unit}"
    return p.raw_value


def param_evidence(p: TagParam) -> Evidence:
    return Evidence(p.document_id, p.page_no, p.location, display_value(p))


def values_text(params: list[TagParam]) -> str:
    return "; ".join(f"{doc_label(p.document)}: {display_value(p)}" for p in params)


def all_cell_high(params: list[TagParam]) -> bool:
    return all(p.method == Method.cell and p.confidence == Confidence.high for p in params)
