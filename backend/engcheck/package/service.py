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
import shutil
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
RESTORED = ("confirmed", "rejected", "fixed")
MAX_MANIFEST_BYTES = 20 * 1024 * 1024
MAX_ACTIONS = 50                 # bitta qaror uchun tiklanadigan tarix yozuvlari
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
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


def _open(data: bytes | Path, passphrase: str | None) -> zipfile.ZipFile:
    """Paketni ochadi. Parolsiz paket fayl yo'li bilan berilsa, xotiraga to'liq o'qilmaydi."""
    if isinstance(data, Path):
        with open(data, "rb") as f:
            encrypted = f.read(len(MAGIC)) == MAGIC
        if not encrypted:
            try:
                return zipfile.ZipFile(data)
            except (zipfile.BadZipFile, ValueError, OSError) as exc:
                raise PackageError("invalid_package") from exc
        data = data.read_bytes()   # shifrlangan paket butunligicha ochiladi (Fernet oqimli emas)
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


def _text(value, limit: int, required: bool = True) -> str | None:
    """Manifest maydoni: satr, boshqaruv belgilarisiz, uzunligi cheklangan. Aks holda ValueError."""
    if value is None and not required:
        return None
    if not isinstance(value, str) or _CONTROL.search(value) or len(value) > limit or (required and not value.strip()):
        raise ValueError
    return value


def _manifest(z: zipfile.ZipFile) -> dict:
    """Manifestni o'qiydi va HAR maydonni tekshiradi. Noto'g'ri narsa — PackageError, boshqa istisno emas."""
    try:
        infos = z.infolist()
        sizes = {i.filename: i.file_size for i in infos}
    except Exception as exc:
        raise PackageError("invalid_package") from exc
    # Hajm ochishdan OLDIN e'lon qilingan o'lchamlar bo'yicha; haqiqiy hajm o'qish paytida yana tekshiriladi.
    if len(infos) > MAX_FILES + 1 or sum(sizes.values()) > MAX_TOTAL_BYTES:
        raise PackageError("too_large")
    if sizes.get("manifest.json", 0) > MAX_MANIFEST_BYTES:
        raise PackageError("too_large")
    try:
        with z.open("manifest.json") as f:
            raw = f.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise PackageError("too_large")
        manifest = json.loads(raw)
    except PackageError:
        raise
    except Exception as exc:   # buzilgan oqim, noto'g'ri JSON, haddan tashqari ichma-ich tuzilma va h.k.
        raise PackageError("invalid_package") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("format"), int):
        raise PackageError("invalid_package")
    if manifest["format"] != FORMAT:
        raise PackageError("unsupported_format")
    try:
        project, documents = manifest["project"], manifest["documents"]
        decisions = manifest.get("decisions", [])
        if not isinstance(project, dict) or not isinstance(documents, list) or not isinstance(decisions, list):
            raise ValueError
        if len(documents) > MAX_FILES:
            raise PackageError("too_large")
        _text(project["name"], 200); _text(project["industry"], 40); Stage(project["stage"])
        seen_paths, seen_sha = set(), set()
        for d in documents:
            if not isinstance(d, dict):
                raise ValueError
            DocType(d["doc_type"]); Discipline(d["discipline"])
            path, sha = _text(d["path"], 100), _text(d["sha256"], 64)
            # Yo'l faqat files/<sha256>[.kengaytma]: "../" va mutlaq yo'llar o'tmaydi. Takror yozuvlar rad etiladi.
            if (not _SAFE_PATH.match(path) or path not in sizes or not re.fullmatch(r"[0-9a-f]{64}", sha)
                    or path in seen_paths or sha in seen_sha):
                raise ValueError
            seen_paths.add(path); seen_sha.add(sha)
            name = Path(_text(d["filename"], 255).replace("\\", "/")).name
            if not name or len(Path(name).suffix) > 9:
                raise ValueError
            _text(d.get("doc_number"), 64, required=False); _text(d.get("revision"), 16, required=False)
        for decision in decisions:
            if not isinstance(decision, dict) or not isinstance(decision.get("fingerprint"), str):
                raise ValueError
            if not isinstance(decision.get("status"), str) or not isinstance(decision.get("actions", []), list):
                raise ValueError
            for action in decision.get("actions", []):
                if not isinstance(action, dict):
                    raise ValueError
                for key in ("user", "comment"):
                    if action.get(key) is not None and not isinstance(action[key], str):
                        raise ValueError
    except PackageError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageError("invalid_package") from exc
    return manifest


def _stream(z: zipfile.ZipFile, path: str, budget: list[int], out=None) -> str:
    """Faylni bo'laklab o'qiydi (xotiraga to'liq olmaydi), SHA-256 ni qaytaradi; out berilsa, unga yozadi.

    budget — qolgan ruxsat etilgan bayt: sarlavha yolg'on gapirsa ham haqiqiy hajm cheklanadi.
    """
    digest = hashlib.sha256()
    try:
        with z.open(path) as f:
            while chunk := f.read(1 << 20):
                budget[0] -= len(chunk)
                if budget[0] < 0:
                    raise PackageError("too_large")
                digest.update(chunk)
                if out is not None:
                    out.write(chunk)
    except PackageError:
        raise
    except Exception as exc:   # zlib.error, BadZipFile, RuntimeError (shifrlangan yozuv), EOFError ...
        raise PackageError("invalid_package") from exc
    return digest.hexdigest()


def import_project(db: Db, settings: Settings, user: User | None, data: bytes | Path,
                   passphrase: str | None = None) -> ImportResult:
    """Paketdan yangi loyiha yaratadi.

    Avval barcha fayllar tekshiriladi (hech narsa yozilmaydi). Yozish boshlangach xato chiqsa,
    nusxalangan fayllar o'chiriladi; bazadagi o'zgarishlarni chaqiruvchi tranzaksiyani qaytarib bekor qiladi.
    """
    z = _open(data, passphrase)
    manifest = _manifest(z)
    budget = [MAX_TOTAL_BYTES]
    for d in manifest["documents"]:   # 1-o'tish: faqat tekshirish
        if _stream(z, d["path"], budget) != d["sha256"]:
            raise PackageError("checksum_mismatch")

    meta = manifest["project"]
    project = Project(name=meta["name"].strip(), industry=meta["industry"], stage=Stage(meta["stage"]),
                      created_by=user.id if user else None,
                      allow_cloud_ai=False)   # bulut roziligi hech qachon ko'chmaydi
    db.add(project)
    db.flush()
    uid = user.id if user else None
    project_files = settings.files_dir / str(project.id)
    try:
        ingested = 0
        for d in manifest["documents"]:   # 2-o'tish: bittadan ochib, qabul qilish
            filename = Path(d["filename"].replace("\\", "/")).name
            fd, tmp = tempfile.mkstemp(suffix=Path(filename).suffix)
            try:
                with os.fdopen(fd, "wb") as out:
                    _stream(z, d["path"], [MAX_TOTAL_BYTES], out)
                ingest_file(db, settings, project.id, uid, Path(tmp), filename, DocType(d["doc_type"]),
                            Discipline(d["discipline"]), d.get("doc_number") or None, d.get("revision") or None)
                ingested += 1
            except DuplicateDocument:
                pass
            finally:
                Path(tmp).unlink(missing_ok=True)

        run = run_review(db, project.id, uid)
        by_fingerprint = {f.fingerprint: f for f in db.query(Finding).filter_by(run_id=run.id)}
        restored = unmatched = 0
        for decision in manifest.get("decisions", []):
            finding = by_fingerprint.get(decision["fingerprint"])
            if finding is None or decision["status"] not in RESTORED:
                unmatched += 1   # hujjatlar bir xil bo'lsa bu bo'lmaydi; bo'lsa — hisobotda ko'rsatiladi
                continue
            finding.status = FindingStatus(decision["status"])
            for a in decision.get("actions", [])[-MAX_ACTIONS:]:
                finding.actions.append(FindingAction(
                    user_id=uid, action="imported",
                    comment=f"{a.get('user') or '—'}: {a.get('comment') or ''}"[:2000]))
            restored += 1
        db.flush()
    except BaseException:
        shutil.rmtree(project_files, ignore_errors=True)   # yarim import qilingan maxfiy fayllar diskda qolmasin
        raise
    audit.record(db, uid, "project.import", "project", project.id,
                 {"documents": ingested, "decisions_restored": restored, "decisions_unmatched": unmatched})
    return ImportResult(project.id, ingested, restored, unmatched)
