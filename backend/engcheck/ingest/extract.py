"""ParsedDocument -> teglar, parametrlar va hujjat havolalari."""
import re
from dataclasses import dataclass, field

from ..core.models import Confidence, DocType, Method, TagClass
from .headers import match_header
from .model import Page, ParsedDocument, Table
from .tagging import classify, find_tags, normalize_tag
from .units import parse_quantity

HEADER_SCAN_ROWS = 15
_META = {"tag", "revision", "doc_number"}
_EMPTY = {"", "-", "–", "—"}
_REF_RE = re.compile(r"\b([A-Z]{2,5}-[A-Z]{2,5}-\d{3,5})\s*,?\s*Rev\.?\s*([A-Z0-9]{1,3})\b")


@dataclass
class ExtractedParam:
    tag: str
    param: str
    raw_value: str
    raw_unit: str | None
    number: float | None
    si_value: float | None
    si_unit: str | None
    page_no: int
    location: str
    method: Method
    confidence: Confidence
    unit_known: bool


@dataclass
class ExtractedTag:
    tag: str
    tag_class: TagClass
    page_no: int
    location: str
    method: Method


@dataclass
class Extraction:
    tags: list[ExtractedTag] = field(default_factory=list)
    params: list[ExtractedParam] = field(default_factory=list)
    refs: list[tuple[str, str, int]] = field(default_factory=list)
    unmapped_headers: list[str] = field(default_factory=list)
    doc_number: str | None = None
    revision: str | None = None


def _param(tag: str, param: str, text: str, hint: str | None, page_no: int, location: str) -> ExtractedParam:
    q = parse_quantity(text, param, hint)
    confidence = Confidence.medium if q.assumed else Confidence.high
    return ExtractedParam(tag, param, q.raw, q.unit, q.number, q.si_value, q.si_unit, page_no,
                          location, Method.cell, confidence, q.unit_known)


class _Collector:
    def __init__(self) -> None:
        self.ex = Extraction()
        self._seen: set[tuple[str, int]] = set()

    def tag(self, tag: str, cls: TagClass, page_no: int, location: str, method: Method) -> None:
        if (tag, page_no) in self._seen:
            return
        self._seen.add((tag, page_no))
        self.ex.tags.append(ExtractedTag(tag, cls, page_no, location, method))

    def unmapped(self, header: str) -> None:
        if header and header not in self.ex.unmapped_headers:
            self.ex.unmapped_headers.append(header)


def _find_header_row(table: Table, doc_type: DocType) -> tuple[int, dict[int, tuple[str, str | None]]] | None:
    for r, row in enumerate(table.rows[:HEADER_SCAN_ROWS]):
        mapped = {c: m for c, cell in enumerate(row) if (m := match_header(cell.text))}
        params = {m[0] for m in mapped.values()}
        if doc_type == DocType.MATERIAL_SPEC and "pipe_class" in params:
            return r, mapped
        if "tag" in params and len(params) >= 2:
            return r, mapped
    return None


def _columnar(table: Table, doc_type: DocType, page: Page, col: _Collector) -> bool:
    found = _find_header_row(table, doc_type)
    if found is None:
        return False
    hrow, mapped = found
    for c, cell in enumerate(table.rows[hrow]):
        if c not in mapped:
            col.unmapped(cell.text)
    by_param = {m[0]: c for c, m in mapped.items()}

    if doc_type == DocType.MATERIAL_SPEC and "tag" not in by_param:
        c = by_param["pipe_class"]
        for row in table.rows[hrow + 1:]:
            value = row[c].text.strip().upper() if c < len(row) else ""
            if value not in _EMPTY:
                col.tag(value, TagClass.pipe_class, page.number, row[c].location, Method.cell)
        return True

    tag_col = by_param["tag"]
    for row in table.rows[hrow + 1:]:
        if tag_col >= len(row):
            continue
        tag = normalize_tag(row[tag_col].text)
        if tag is None:
            continue
        col.tag(tag, classify(tag), page.number, row[tag_col].location, Method.cell)
        for c, (param, hint) in mapped.items():
            if param in _META or c >= len(row) or row[c].text.strip() in _EMPTY:
                continue
            col.ex.params.append(_param(tag, param, row[c].text, hint, page.number, row[c].location))
    return True


def _key_value(table: Table, page: Page, col: _Collector) -> bool:
    pairs = []
    for row in table.rows:
        if len(row) < 2:
            continue
        key = match_header(row[0].text)
        pairs.append((row, key))
    if sum(1 for _, key in pairs if key) < 2:
        return False
    tag = None
    for row, key in pairs:
        if key and key[0] == "tag":
            tag = normalize_tag(row[1].text)
            if tag:
                col.tag(tag, classify(tag), page.number, row[1].location, Method.cell)
            break
    for row, key in pairs:
        value = row[1].text.strip()
        if key is None:
            col.unmapped(row[0].text.strip())
            continue
        param, hint = key
        if param == "doc_number":
            col.ex.doc_number = col.ex.doc_number or (value or None)
        elif param == "revision":
            col.ex.revision = col.ex.revision or (value or None)
        elif param != "tag" and tag and value not in _EMPTY:
            unit = row[2].text.strip() if len(row) > 2 else ""
            col.ex.params.append(_param(tag, param, value, unit or hint, page.number, row[1].location))
    return True


def _attrs(item, page: Page, col: _Collector) -> None:
    """DXF blok atributlari: kalit–qiymat sifatida."""
    keyed = {k: match_header(k) for k in item.attrs}
    tag_key = next((k for k, m in keyed.items() if m and m[0] == "tag"), None)
    tag = normalize_tag(item.attrs[tag_key]) if tag_key else None
    if tag is None:
        return
    col.tag(tag, classify(tag), page.number, item.location, Method.cell)
    for k, m in keyed.items():
        value = item.attrs[k].strip()
        if m is None:
            col.unmapped(k)
        elif m[0] not in _META and value not in _EMPTY:
            col.ex.params.append(_param(tag, m[0], value, m[1], page.number, item.location))


def extract(doc: ParsedDocument, doc_type: DocType) -> Extraction:
    col = _Collector()
    for page in doc.pages:
        for table in page.tables:
            if not _columnar(table, doc_type, page, col):
                _key_value(table, page, col)
        for item in page.items:
            if item.attrs:
                _attrs(item, page, col)
        # Erkin matndan faqat teglar olinadi (parametrlar emas).
        for item in page.items:
            if not item.attrs:
                for tag, cls in find_tags(item.text):
                    col.tag(tag, cls, page.number, item.location, Method.regex)
        for tag, cls in find_tags(page.text):
            col.tag(tag, cls, page.number, "text", Method.regex)
        for m in _REF_RE.finditer(page.text):
            ref = (m.group(1), m.group(2), page.number)
            if ref not in col.ex.refs:
                col.ex.refs.append(ref)
    return col.ex
