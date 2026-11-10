"""Hujjatni qabul qilish: saqlash, parsing, ajratish va bazaga yozish."""
import hashlib
import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session as Db

from ..config import Settings
from ..core import audit
from ..core.models import (Discipline, DocPage, DocRef, DocType, Document, Method, ParseStatus, Tag,
                           TagOccurrence, TagParam)
from .extract import extract
from .parsers import ParseError, parse_file

_STATUS_BY_CODE = {"needs_ocr": ParseStatus.needs_ocr, "unsupported_dwg": ParseStatus.unsupported,
                   "unknown_format": ParseStatus.unsupported}

_TYPE_HINTS: list[tuple[DocType, tuple[str, ...]]] = [
    (DocType.HAZOP, ("HAZOP",)), (DocType.HAZID, ("HAZID",)),
    (DocType.PID, ("PID", "P&ID")), (DocType.PFD, ("PFD",)),
    (DocType.EQUIPMENT_LIST, ("EQL", "EQUIPMENT")),
    (DocType.LINE_LIST, ("LL", "LINELIST", "LINE")),
    (DocType.DATASHEET, ("DS", "DATASHEET", "DATA")),
    (DocType.MATERIAL_SPEC, ("MS", "MATERIAL", "PMS")),
    (DocType.CALCULATION, ("CALC", "CALCULATION")),
]
_NUMBER_REV_RE = re.compile(r"^([A-Z]{2,5}-[A-Z]{2,5}-[A-Z0-9]{3,6})[_ -]+REV[_ .-]*([A-Z0-9]{1,3})$")


class DuplicateDocument(Exception):
    """Shu loyihada bir xil mazmunli (SHA-256) fayl allaqachon bor."""


def suggest_doc_type(filename: str) -> DocType | None:
    tokens = set(re.split(r"[^A-Z0-9&]+", Path(filename).stem.upper()))
    for doc_type, hints in _TYPE_HINTS:
        if tokens & set(hints):
            return doc_type
    return None


def suggest_number_revision(filename: str) -> tuple[str | None, str | None]:
    m = _NUMBER_REV_RE.match(Path(filename).stem.upper())
    return (m.group(1), m.group(2)) if m else (None, None)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_file(db: Db, settings: Settings, project_id: int, user_id: int | None, src_path: Path,
                filename: str, doc_type: DocType, discipline: Discipline,
                doc_number: str | None = None, revision: str | None = None) -> Document:
    src_path = Path(src_path)
    sha = _sha256(src_path)
    if db.query(Document).filter_by(project_id=project_id, sha256=sha).first():
        raise DuplicateDocument(filename)

    target_dir = settings.files_dir / str(project_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored = target_dir / f"{sha}{Path(filename).suffix.lower()}"
    shutil.copyfile(src_path, stored)

    doc = Document(project_id=project_id, filename=filename, doc_type=DocType(doc_type),
                   discipline=Discipline(discipline), doc_number=doc_number or None,
                   revision=revision or None, sha256=sha, stored_path=str(stored),
                   uploaded_by=user_id)
    db.add(doc)
    db.flush()

    try:
        parsed = parse_file(stored)
        ex = extract(parsed, doc.doc_type)
    except ParseError as exc:
        doc.parse_status = _STATUS_BY_CODE.get(exc.code, ParseStatus.error)
        doc.parse_error = exc.code if exc.code != "corrupt" else str(exc)
    except Exception as exc:  # ajratishdagi kutilmagan xato ham yuklashni to'xtatmasin
        doc.parse_status = ParseStatus.error
        doc.parse_error = f"extract: {type(exc).__name__}: {exc}"
    else:
        _persist(db, doc, parsed, ex)
        doc.parse_status = ParseStatus.parsed
    db.flush()
    audit.record(db, user_id, "document.upload", "document", doc.id,
                 {"filename": filename, "sha256": sha, "parse_status": str(doc.parse_status)})
    return doc


def _persist(db: Db, doc: Document, parsed, ex) -> None:
    doc.doc_number = doc.doc_number or ex.doc_number
    doc.revision = doc.revision or ex.revision
    doc.unmapped_headers = ex.unmapped_headers
    doc.skipped_tags = ex.skipped_tags
    for page in parsed.pages:
        db.add(DocPage(document_id=doc.id, page_no=page.number, text=page.text))
    tags: dict[str, Tag] = {}

    def tag_row(name: str, tag_class) -> Tag:
        if name not in tags:
            row = db.query(Tag).filter_by(project_id=doc.project_id, tag=name).first()
            if row is None:
                row = Tag(project_id=doc.project_id, tag=name, tag_class=tag_class)
                db.add(row)
                db.flush()
            tags[name] = row
        return tags[name]

    for t in ex.tags:
        row = tag_row(t.tag, t.tag_class)
        # Jadval katagidan aniqlangan sinf matndan taxmin qilingan sinfdan ustun.
        if t.method == Method.cell and row.tag_class != t.tag_class:
            row.tag_class = t.tag_class
        db.add(TagOccurrence(tag_id=row.id, document_id=doc.id,
                             page_no=t.page_no, location=t.location, method=t.method))
    for p in ex.params:
        db.add(TagParam(tag_id=tags[p.tag].id, param=p.param, raw_value=p.raw_value[:255],
                        raw_unit=p.raw_unit, number=p.number, si_value=p.si_value,
                        si_unit=p.si_unit, unit_known=p.unit_known, document_id=doc.id,
                        page_no=p.page_no, location=p.location, method=p.method,
                        confidence=p.confidence))
    for number, rev, page_no in ex.refs:
        db.add(DocRef(document_id=doc.id, ref_doc_number=number, ref_revision=rev, page_no=page_no))


def delete_document(db: Db, settings: Settings, document_id: int, user_id: int | None) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        return
    project_id, stored, filename = doc.project_id, doc.stored_path, doc.filename
    db.query(Document).filter_by(id=document_id).delete()  # bog'liq qatorlar FK kaskadi bilan
    db.flush()
    used = db.query(TagOccurrence.tag_id)
    db.query(Tag).filter(Tag.project_id == project_id, Tag.id.notin_(used)).delete(
        synchronize_session=False)
    db.flush()
    db.expire_all()
    if stored:
        Path(stored).unlink(missing_ok=True)
    audit.record(db, user_id, "document.delete", "document", document_id, {"filename": filename})
