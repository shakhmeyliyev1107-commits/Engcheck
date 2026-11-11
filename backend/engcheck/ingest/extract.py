"""ParsedDocument -> teglar, parametrlar va hujjat havolalari."""
import re
from dataclasses import dataclass, field

from ..core.models import Confidence, DocType, Method, TagClass
from .headers import match_header
from .model import Page, ParsedDocument, Table
from .tagging import classify, find_tags, normalize_tags
from .units import is_unit, parse_quantity

HEADER_SCAN_ROWS = 15
_META = {"tag", "revision", "doc_number"}
_EMPTY = {"", "-", "–", "—"}
_REF_RE = re.compile(r"\b([A-Z]{2,5}-[A-Z]{2,5}-\d{3,5})\s*,?\s*Rev\.?\s*([A-Z0-9]{1,3})\b", re.IGNORECASE)
_CELL_CONTEXT = (DocType.EQUIPMENT_LIST, DocType.DATASHEET)
MAX_SKIPPED = 50
_LINE_ONLY = ("line_from", "line_to")
# "Length"/"Height" faqat uskuna hujjatlarida gabarit; quvurlar ro'yxatidagi "Length" — quvur uzunligi
_EQUIPMENT_ONLY = ("equipment_height", "equipment_length")
_EQUIPMENT_DIM_DOCS = (DocType.DATASHEET, DocType.EQUIPMENT_LIST)


def _usable(match, doc_type: DocType, line_ok: bool = False):
    """Sarlavha mosligi shu hujjat turida ma'noga egami."""
    if not match:
        return None
    if match[0] in _LINE_ONLY and not (line_ok and doc_type == DocType.LINE_LIST):
        return None
    if match[0] in _EQUIPMENT_ONLY and doc_type not in _EQUIPMENT_DIM_DOCS:
        return None
    return match


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
    skipped_tags: list[str] = field(default_factory=list)   # teg ustunidagi tanilmagan qiymatlar
    doc_number: str | None = None
    revision: str | None = None


def _param(tag: str, param: str, text: str, hint: str | None, page_no: int, location: str) -> ExtractedParam:
    q = parse_quantity(text, param, hint)
    confidence = Confidence.medium if q.assumed else Confidence.high
    return ExtractedParam(tag, param, q.raw, q.unit, q.number, q.si_value, q.si_unit, page_no,
                          location, Method.cell, confidence, q.unit_known)


class _Collector:
    def __init__(self, doc_type: DocType) -> None:
        self.ex = Extraction()
        self.doc_type = doc_type
        self.cell_texts: list[str] = []   # jadvaldan o'qilgan teg kataklari (matnda qayta qidirilmaydi)
        self._seen: set[tuple[str, int]] = set()

    def cell_class(self, tag: str) -> TagClass:
        """Uskunalar ro'yxati va datasheetning teg katagi — ko'rinishidan qat'i nazar uskuna."""
        cls = classify(tag)
        return TagClass.equipment if cls != TagClass.line and self.doc_type in _CELL_CONTEXT else cls

    def skipped(self, text: str) -> None:
        if text and text not in self.ex.skipped_tags and len(self.ex.skipped_tags) < MAX_SKIPPED:
            self.ex.skipped_tags.append(text)

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
        # "From"/"To" boshqa hujjatlarda (transmittal, yozishmalar) quvur uchi emas
        mapped = {c: m for c, cell in enumerate(row) if (m := _usable(match_header(cell.text), doc_type, line_ok=True))}
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
    body = table.rows[hrow + 1:]
    # Sarlavha ostidagi birliklar qatori ("in | barg | °C") ustunlarga birlik beradi.
    if body and tag_col < len(body[0]) and not normalize_tags(body[0][tag_col].text):
        units = {c: body[0][c].text.strip() for c, (param, hint) in mapped.items()
                 if param not in _META and c < len(body[0]) and is_unit(param, body[0][c].text)}
        if units:
            mapped = {c: (param, hint or units.get(c)) for c, (param, hint) in mapped.items()}
            body = body[1:]
    for row in body:
        if tag_col >= len(row):
            continue
        raw = row[tag_col].text.strip()
        tags = normalize_tags(raw)
        if not tags:
            if raw not in _EMPTY:
                col.skipped(raw)
            continue
        col.cell_texts.append(raw)
        for tag in tags:   # "P-101A/B" qatori ikkala tegga tegishli
            col.tag(tag, col.cell_class(tag), page.number, row[tag_col].location, Method.cell)
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
        key = _usable(match_header(row[0].text), col.doc_type)
        pairs.append((row, key))
    if sum(1 for _, key in pairs if key) < 2:
        return False
    tag = None
    for row, key in pairs:
        if key and key[0] == "tag":
            raw = row[1].text.strip()
            tags = normalize_tags(raw)
            if len(tags) == 1:
                tag = tags[0]
                col.cell_texts.append(raw)
                col.tag(tag, col.cell_class(tag), page.number, row[1].location, Method.cell)
            elif raw not in _EMPTY:
                col.skipped(raw)
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
    keyed = {k: _usable(match_header(k), col.doc_type) for k in item.attrs}
    tag_key = next((k for k, m in keyed.items() if m and m[0] == "tag"), None)
    tags = normalize_tags(item.attrs[tag_key]) if tag_key else []
    if len(tags) != 1:
        if tag_key and item.attrs[tag_key].strip() not in _EMPTY:
            col.skipped(item.attrs[tag_key].strip())
        return
    tag = tags[0]
    col.tag(tag, col.cell_class(tag), page.number, item.location, Method.cell)
    for k, m in keyed.items():
        value = item.attrs[k].strip()
        if m is None:
            col.unmapped(k)
        elif m[0] not in _META and value not in _EMPTY:
            col.ex.params.append(_param(tag, m[0], value, m[1], page.number, item.location))


def extract(doc: ParsedDocument, doc_type: DocType) -> Extraction:
    col = _Collector(doc_type)
    for page in doc.pages:
        col.cell_texts = []
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
        # Jadvaldan allaqachon o'qilgan teg kataklari matnda qayta qidirilmaydi:
        # aks holda "p-101 a" dan soxta "P-101" tegi chiqadi.
        text = page.text
        for raw in sorted(set(col.cell_texts), key=len, reverse=True):
            text = re.sub(re.escape(raw), " " * len(raw), text, flags=re.IGNORECASE)
        for tag, cls in find_tags(text):
            col.tag(tag, cls, page.number, "text", Method.regex)
        for m in _REF_RE.finditer(page.text):
            ref = (m.group(1).upper(), m.group(2).upper(), page.number)
            if ref not in col.ex.refs:
                col.ex.refs.append(ref)
    return col.ex
