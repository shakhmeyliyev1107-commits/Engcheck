"""Bilimlar bazasi: manba qo'shish, qidirish, indekslash."""
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session as Db, joinedload

from ..ai.base import AiError, Provider
from ..config import Settings
from ..core import audit
from ..core.auth import Perm, can
from ..core.models import KbChunk, KbSource, Project, User
from ..ingest.parsers import ParseError, parse_file
from .chunking import chunk_pages
from .index import bm25_rank, cosine_rank, rrf, to_blob

KINDS = ("standard", "literature", "note", "lesson")
STATUSES = ("active", "superseded", "withdrawn")
LICENSES = ("licensed", "open", "internal")
LICENSED_EXCERPT = 300   # litsenziyali manbadan ko'rsatiladigan eng uzun iqtibos (belgi)
TEXT_SUFFIXES = (".txt", ".md")


class KbError(Exception):
    """code: empty | unreadable | duplicate | invalid"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Hit:
    chunk_id: int
    source_id: int
    title: str
    kind: str
    standard_code: str | None
    edition: str | None
    status: str
    license_type: str
    page_no: int
    excerpt: str
    score: float
    text: str   # to'liq bo'lak — faqat ichki foydalanish uchun, API ga chiqmaydi
    cloud_ok: bool = True   # matnini bulutli provayderga yuborish mumkinmi


def _read_text_file(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _pages(path: Path, filename: str) -> list[tuple[int, str]]:
    if Path(filename).suffix.lower() in TEXT_SUFFIXES:
        return [(1, _read_text_file(path))]
    try:
        return [(p.number, p.text) for p in parse_file(path).pages]
    except ParseError as exc:
        raise KbError("unreadable") from exc


def add_source(db: Db, settings: Settings, user: User | None, title: str, kind: str, *,
               path: Path | None = None, filename: str | None = None, text: str | None = None,
               standard_code: str | None = None, edition: str | None = None, status: str = "active",
               license_type: str = "internal", origin_finding_id: int | None = None,
               origin_project_id: int | None = None,
               approved: bool | None = None) -> KbSource:
    if kind not in KINDS or status not in STATUSES or license_type not in LICENSES or not (title or "").strip():
        raise KbError("invalid")
    sha = stored = None
    if path is not None:
        path = Path(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if db.query(KbSource).filter_by(sha256=sha).first():
            raise KbError("duplicate")
        pages = _pages(path, filename or path.name)
    else:
        pages = [(1, text or "")]
    chunks = chunk_pages(pages)
    if not chunks:
        raise KbError("empty")
    if path is not None:
        kb_dir = settings.data_dir / "kb"
        kb_dir.mkdir(parents=True, exist_ok=True)
        stored = kb_dir / f"{sha}{Path(filename or path.name).suffix.lower()}"
        shutil.copyfile(path, stored)
    if approved is None:
        approved = bool(user and can(user.role, Perm.manage_kb))
    source = KbSource(title=title.strip(), kind=kind, standard_code=standard_code or None,
                      edition=edition or None, status=status, license_type=license_type,
                      filename=filename, sha256=sha, stored_path=str(stored) if stored else None,
                      approved=approved, origin_finding_id=origin_finding_id,
                      origin_project_id=origin_project_id,
                      added_by=user.id if user else None,
                      approved_by=user.id if (approved and user) else None)
    source.chunks = [KbChunk(ordinal=i, page_no=page_no, text=chunk) for i, (page_no, chunk) in enumerate(chunks)]
    db.add(source)
    db.flush()
    audit.record(db, user.id if user else None, "kb.add", "kb_source", source.id,
                 {"title": source.title, "kind": kind, "license_type": license_type, "approved": approved})
    return source


def delete_source(db: Db, settings: Settings, source_id: int, user_id: int | None) -> None:
    source = db.get(KbSource, source_id)
    if source is None:
        return
    title, stored = source.title, source.stored_path
    db.delete(source)
    db.flush()
    if stored:
        Path(stored).unlink(missing_ok=True)
    audit.record(db, user_id, "kb.delete", "kb_source", source_id, {"title": title})


def _eligible(db: Db) -> list[KbChunk]:
    """Faqat tasdiqlangan va bekor qilinmagan manbalar bo'laklari."""
    return (db.query(KbChunk).join(KbSource, KbChunk.source_id == KbSource.id)
            .filter(KbSource.approved.is_(True), KbSource.status != "withdrawn")
            .options(joinedload(KbChunk.source)).order_by(KbChunk.id).all())


def cloud_ok(db: Db, source: KbSource) -> bool:
    """Manba matnini bulutli provayderga yuborish mumkinmi.

    Litsenziyali matn — hech qachon. Dars loyiha ma'lumotini o'z ichiga oladi, shuning uchun
    faqat o'sha loyiha bulutli AI ga ruxsat bergan bo'lsa.
    """
    if source.license_type == "licensed":
        return False
    if source.kind == "lesson":
        project = db.get(Project, source.origin_project_id) if source.origin_project_id else None
        return bool(project and project.allow_cloud_ai)
    return True


def _excerpt(chunk: KbChunk) -> str:
    text = chunk.text
    if chunk.source.license_type == "licensed" and len(text) > LICENSED_EXCERPT:
        return text[:LICENSED_EXCERPT - 1].rstrip() + "…"
    return text


def search(db: Db, query: str, k: int = 5, provider: Provider | None = None) -> list[Hit]:
    """BM25; provayder embedding bersa va bo'laklar indekslangan bo'lsa — gibrid qidiruv."""
    chunks = _eligible(db)
    rankings = [bm25_rank(query, [c.text for c in chunks])]
    if provider is not None and provider.embed_model:
        blobs = [c.embedding if c.embed_model == provider.embed_model else None for c in chunks]
        if any(blobs):
            try:
                rankings.append(cosine_rank(provider.embed([query])[0], blobs))
            except (AiError, IndexError, ValueError):
                pass   # embedding ishlamasa BM25 natijasi qoladi
    hits = []
    for idx, score in rrf(*rankings)[:k]:
        c, s = chunks[idx], chunks[idx].source
        hits.append(Hit(c.id, s.id, s.title, s.kind, s.standard_code, s.edition, s.status, s.license_type,
                        c.page_no, _excerpt(c), score, c.text, cloud_ok(db, s)))
    return hits


def prompt_text(hit: Hit, for_cloud: bool) -> str | None:
    """AI ga beriladigan matn. Litsenziyali manba va ruxsatsiz loyiha darsi bulutga yuborilmaydi."""
    if for_cloud and not hit.cloud_ok:
        return None
    return hit.text


def reindex(db: Db, provider: Provider, batch: int = 32) -> int:
    """Bo'laklar uchun embedding hisoblaydi. Bulutli provayderga litsenziyali matn yuborilmaydi."""
    todo = [c for c in db.query(KbChunk).options(joinedload(KbChunk.source)).order_by(KbChunk.id)
            if c.embed_model != provider.embed_model or c.embedding is None]
    if not provider.is_local:
        todo = [c for c in todo if cloud_ok(db, c.source)]
    done = 0
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        vectors = provider.embed([c.text for c in part])
        for chunk, vector in zip(part, vectors):
            chunk.embedding, chunk.embed_model = to_blob(vector), provider.embed_model
            done += 1
    db.flush()
    return done


LESSON_STATUSES = ("confirmed", "rejected", "fixed")


def propose_lesson(db: Db, settings: Settings, finding, user: User | None, text: str | None = None) -> KbSource:
    """Muhandis qaror qilgan topilmadan bilimlar bazasiga "dars" taklif qiladi.

    Dars doim tasdiqlanmagan holda qo'shiladi: yetakchi muhandis tasdiqlamaguncha qidiruvga kirmaydi.
    """
    from ..review.messages import render

    if str(finding.status) not in LESSON_STATUSES:
        raise KbError("invalid")
    description, rationale, recommendation = render(finding.description_key, finding.args, "en")
    if not (text or "").strip():
        comment = finding.actions[-1].comment if finding.actions else ""
        text = (f"{description}. {rationale} Engineer decision: {finding.status}."
                + (f" Comment: {comment}" if comment else "") + f" Recommended correction: {recommendation}")
    from ..core.models import ReviewRun
    title = render(finding.description_key, finding.args, "uz")[0]
    run = db.get(ReviewRun, finding.run_id)
    return add_source(db, settings, user, f"Dars: {title}"[:255], "lesson", text=text,
                      origin_finding_id=finding.id, origin_project_id=run.project_id if run else None,
                      approved=False)
