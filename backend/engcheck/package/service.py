"""Loyiha paketi (.engpkg): loyihani hamkasbga bitta fayl sifatida berish va qabul qilish.

Paketga KIRMAYDI: API kalitlari, AI provayderlari, foydalanuvchilar, audit jurnali, bilimlar bazasi,
AI izohlari va AI topilmalari, bulutli AI roziligi.
"""
import base64
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy.orm import Session as Db

from ..config import Settings
from ..core import audit
from ..core.models import (Discipline, DocType, Document, Finding, FindingAction, FindingStatus, Project,
                           ReviewRun, Stage, User)
from ..ingest.service import DuplicateDocument, ingest_file
from ..review.engine import run_review

FORMAT = 1
MAGIC = b"ENGPKG1\n"            # parol bilan shifrlangan paket sarlavhasi
MAX_TOTAL_BYTES = 2 * 1024 ** 3  # ochilgan hajm chegarasi
MAX_FILES = 2000
RESTORED = ("confirmed", "rejected", "fixed", "reviewed")
_SAFE_PATH = re.compile(r"^files/[0-9a-f]{64}(\.[A-Za-z0-9]{1,8})?$")


class PackageError(Exception):
    """code: invalid_package | unsupported_format | checksum_mismatch | too_large |
    passphrase_required | wrong_passphrase"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class ImportResult:
    project_id: int
    documents: int
    decisions_restored: int
    decisions_unmatched: int


def _key(passphrase: str, salt: bytes) -> bytes:
    return base64.urlsafe_b64encode(Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(passphrase.encode()))


def export_project(db: Db, settings: Settings, project_id: int, user: User | None,
                   passphrase: str | None = None) -> bytes:
    project = db.get(Project, project_id)
    if project is None:
        raise PackageError("invalid_package")
    users = {u.id: u.login for u in db.query(User)}
    documents, files = [], {}
    for doc in db.query(Document).filter_by(project_id=project_id).order_by(Document.id):
        if not doc.stored_path or not Path(doc.stored_path).is_file():
            continue
        path = f"files/{doc.sha256}{Path(doc.filename).suffix.lower()[:9]}"
        if not _SAFE_PATH.match(path):
            path = f"files/{doc.sha256}"
        files[path] = Path(doc.stored_path)
        documents.append({"filename": doc.filename, "doc_type": str(doc.doc_type), "discipline": str(doc.discipline),
                          "doc_number": doc.doc_number, "revision": doc.revision, "sha256": doc.sha256, "path": path})
    decisions = []
    run = db.query(ReviewRun).filter_by(project_id=project_id).order_by(ReviewRun.id.desc()).first()
    if run is not None:
        for f in db.query(Finding).filter_by(run_id=run.id).order_by(Finding.id):
            if f.source_type != "rule" or str(f.status) not in RESTORED:
                continue   # AI topilmalari paketga kirmaydi: ularni qabul qiluvchi tomonda qayta yaratib bo'lmaydi
            decisions.append({"fingerprint": f.fingerprint, "status": str(f.status), "rule": f.rule.code,
                              "tag": f.tag_text,
                              "actions": [{"action": a.action, "comment": a.comment, "user": users.get(a.user_id)}
                                          for a in f.actions]})
    manifest = {"format": FORMAT,
                "project": {"name": project.name, "industry": project.industry, "stage": str(project.stage)},
                "documents": documents, "decisions": decisions}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for path, source in files.items():
            z.write(source, path)
    data = buffer.getvalue()
    if passphrase:
        salt = os.urandom(16)
        data = MAGIC + salt + Fernet(_key(passphrase, salt)).encrypt(data)
    audit.record(db, user.id if user else None, "project.export", "project", project_id,
                 {"documents": len(documents), "decisions": len(decisions), "encrypted": bool(passphrase)})
    return data


def _open(data: bytes, passphrase: str | None) -> zipfile.ZipFile:
    if data.startswith(MAGIC):
        if not passphrase:
            raise PackageError("passphrase_required")
        salt, token = data[len(MAGIC):len(MAGIC) + 16], data[len(MAGIC) + 16:]
        try:
            data = Fernet(_key(passphrase, salt)).decrypt(token)
        except (InvalidToken, ValueError) as exc:
            raise PackageError("wrong_passphrase") from exc
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise PackageError("invalid_package") from exc


def _manifest(z: zipfile.ZipFile) -> dict:
    infos = z.infolist()
    # Hajm ochishdan OLDIN, sarlavhadagi e'lon qilingan o'lchamlar bo'yicha tekshiriladi (zip-bomba).
    if len(infos) > MAX_FILES + 1 or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
        raise PackageError("too_large")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except (KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise PackageError("invalid_package") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("format"), int):
        raise PackageError("invalid_package")
    if manifest["format"] != FORMAT:
        raise PackageError("unsupported_format")
    project, documents = manifest.get("project"), manifest.get("documents")
    try:
        if not str(project["name"]).strip():
            raise ValueError
        Stage(project["stage"])
        str(project["industry"])
        names = set(z.namelist())
        for d in documents:
            DocType(d["doc_type"]); Discipline(d["discipline"])
            # Yo'l faqat files/<sha256>[.kengaytma] ko'rinishida bo'lishi mumkin: "../" va mutlaq yo'llar o'tmaydi.
            if not _SAFE_PATH.match(d["path"]) or d["path"] not in names or not re.fullmatch(r"[0-9a-f]{64}", d["sha256"]):
                raise ValueError
            if not str(d["filename"]).strip():
                raise ValueError
        if not isinstance(manifest.get("decisions", []), list):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageError("invalid_package") from exc
    return manifest


def import_project(db: Db, settings: Settings, user: User | None, data: bytes,
                   passphrase: str | None = None) -> ImportResult:
    """Paketdan yangi loyiha yaratadi. Xato bo'lsa hech narsa qolmaydi (chaqiruvchi tranzaksiyani qaytaradi)."""
    z = _open(data, passphrase)
    manifest = _manifest(z)
    # Avval BARCHA fayllar tekshiriladi, keyingina bazaga yoziladi.
    blobs: list[tuple[dict, bytes]] = []
    for d in manifest["documents"]:
        try:
            blob = z.read(d["path"])
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            raise PackageError("invalid_package") from exc
        if hashlib.sha256(blob).hexdigest() != d["sha256"]:
            raise PackageError("checksum_mismatch")
        blobs.append((d, blob))

    meta = manifest["project"]
    project = Project(name=str(meta["name"]).strip()[:200], industry=str(meta["industry"])[:40],
                      stage=Stage(meta["stage"]), created_by=user.id if user else None,
                      allow_cloud_ai=False)   # bulut roziligi hech qachon ko'chmaydi
    db.add(project)
    db.flush()
    uid = user.id if user else None
    for d, blob in blobs:
        filename = Path(str(d["filename"]).replace("\\", "/")).name[:255] or "file"
        fd, tmp = tempfile.mkstemp(suffix=Path(filename).suffix)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(blob)
            ingest_file(db, settings, project.id, uid, Path(tmp), filename, DocType(d["doc_type"]),
                        Discipline(d["discipline"]), d.get("doc_number") or None, d.get("revision") or None)
        except DuplicateDocument:
            pass   # manifestda bir fayl ikki marta kelsa, bittasi olinadi
        finally:
            Path(tmp).unlink(missing_ok=True)

    run = run_review(db, project.id, uid)
    by_fingerprint = {f.fingerprint: f for f in db.query(Finding).filter_by(run_id=run.id)}
    restored = unmatched = 0
    for decision in manifest.get("decisions", []):
        finding = by_fingerprint.get(decision.get("fingerprint")) if isinstance(decision, dict) else None
        if finding is None or decision.get("status") not in RESTORED:
            unmatched += 1   # hujjatlar bir xil bo'lsa bu bo'lmaydi; bo'lsa — hisobotda ko'rsatiladi
            continue
        finding.status = FindingStatus(decision["status"])
        for a in decision.get("actions") or []:
            if isinstance(a, dict):
                finding.actions.append(FindingAction(
                    user_id=uid, action="imported",
                    comment=f"{a.get('user') or '—'}: {a.get('comment') or ''}"[:2000]))
        restored += 1
    db.flush()
    audit.record(db, uid, "project.import", "project", project.id,
                 {"documents": len(blobs), "decisions_restored": restored, "decisions_unmatched": unmatched})
    return ImportResult(project.id, len(blobs), restored, unmatched)
