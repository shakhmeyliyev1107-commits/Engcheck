# EngCheck 1-sikl: yadro va tekshiruv dvigateli — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Muhandis hujjat yuklaydi, tizim teg va parametrlarni ajratadi, 7 ta deterministik qoida bilan tekshiradi va topilmalarni manbasi bilan ko‘rsatadi; muhandis tasdiqlaydi yoki rad etadi.

**Architecture:** Python (FastAPI) xizmati `parsing → ajratish → normallashtirish → qoidalar → topilmalar` zanjirini bajaradi va SQLite ga yozadi. React interfeysi shu xizmatning HTTP API si orqali ishlaydi; xizmat qurilgan interfeysni statik fayl sifatida ham tarqatadi. Har qiymat o‘z manbasini (hujjat, sahifa, joylashuv, usul) olib yuradi.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, argon2-cffi, pdfplumber, openpyxl, python-docx, ezdxf, reportlab (faqat namunaviy PDF yaratish uchun), pytest, httpx; Node 22, Vite, React 18, TypeScript, react-router, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-10-engcheck-yadro-va-tekshiruv-design.md`

## Global Constraints

- Tizim yuklangan hujjatlarni hech qachon o‘zgartirmaydi; tavsiya faqat matn.
- Barcha topilmalar `source_type = "rule"`; izohda faqat hujjatdan o‘qilgan qiymatlar, taxmin yo‘q.
- Standartga havola faqat `standards.status == "active"` yozuvga; aks holda manba matni: "loyiha hujjatlari o‘rtasidagi ichki nomuvofiqlik".
- Rollar: `admin`, `lead`, `engineer`, `viewer`. Ruxsatlar spetsifikatsiya 7-bo‘limidagi jadval bo‘yicha.
- Xizmat faqat `127.0.0.1` da tinglaydi.
- API xatosi shakli: `{"code": str, "message": str}`; `message` foydalanuvchi tilida (`uz`, `en`, `ru`; standart `uz`).
- Bitta buzilgan fayl yoki bitta qoidadagi xato butun jarayonni to‘xtatmaydi.
- Interfeys matnlari kodda emas, `frontend/src/i18n/{uz,en,ru}.json` da.
- Enum qiymatlari spetsifikatsiya 4-bo‘limidan so‘zma-so‘z.
- Har vazifa oxirida `pytest -q` to‘liq o‘tadi va commit qilinadi.

## Review Focus

1. **Sarlavha birinchi qatorda emas** (XLSX tepasida loyiha nomi, birlashtirilgan kataklar) → sarlavha qatori birinchi 15 qator ichidan topiladi. Test: 6-vazifa.
2. **Qiymat va birlik bitta katakda, o‘nli vergul** (`"16 barg"`, `"10,5"`) → to‘g‘ri songa va birlikka ajraladi. Test: 4-vazifa.
3. **Teg yozilishi farq qiladi** (`p-101 a`, `P101A`, `P-101A`) → bitta kanonik tegga keltiriladi, soxta R002 chiqmaydi. Test: 6-vazifa.
4. **Bo‘sh yoki kengaytmasi noto‘g‘ri fayl** (0 bayt; `.xlsx` deb nomlangan PDF) → `parse_status = "error"`, sabab yoziladi, xizmat ishlashda davom etadi. Test: 5 va 8-vazifa.
5. **Tekshiruv qayta ishga tushirilganda** tasdiqlangan yoki rad etilgan topilma yana "yangi" bo‘lib chiqmaydi — qaror `fingerprint` bo‘yicha ko‘chiriladi. Test: 9-vazifa.

---

## Fayllar tuzilmasi

```
engcheck/
├── README.md                       ishga tushirish va foydalanish yo‘riqnomasi
├── backend/
│   ├── pyproject.toml
│   ├── engcheck/
│   │   ├── config.py               Settings: data_dir, db_url, host, port
│   │   ├── core/
│   │   │   ├── db.py               engine, sessiya, init_db()
│   │   │   ├── models.py           barcha jadvallar va enumlar
│   │   │   ├── auth.py             parol, sessiya, ruxsat matritsasi
│   │   │   └── audit.py            xesh-zanjirli jurnal
│   │   ├── ingest/
│   │   │   ├── model.py            ParsedDocument, Page, Table, Cell, TextItem
│   │   │   ├── detect.py           format aniqlash (kengaytma + imzo)
│   │   │   ├── parsers/{pdf,xlsx,docx,dxf}.py
│   │   │   ├── units.py            qiymat ajratish va SI ga o‘girish
│   │   │   ├── tagging.py          teg regexlari va normallashtirish
│   │   │   ├── headers.py          sarlavha lug‘ati (uz/en/ru)
│   │   │   ├── extract.py          ParsedDocument → Extraction
│   │   │   └── service.py          yuklash, saqlash, bazaga yozish
│   │   ├── review/
│   │   │   ├── rules/{base,r001,r002,r003,r004,r005,r006,r007}.py
│   │   │   └── engine.py           seans, fingerprint, qaror ko‘chirish
│   │   └── api/
│   │       ├── app.py              create_app(), statik interfeys
│   │       ├── deps.py             joriy foydalanuvchi, ruxsat, til
│   │       ├── errors.py           ApiError va uch tilli xabarlar
│   │       └── routes_{auth,projects,documents,reviews,findings,dashboard,audit}.py
│   └── tests/                      modul tuzilmasini takrorlaydi
├── samples/
│   └── generate_sample_project.py  namunaviy gaz tozalash bloki hujjatlari
└── frontend/
    ├── package.json, vite.config.ts, playwright.config.ts
    ├── src/{main.tsx, api.ts, i18n/, pages/, components/}
    └── e2e/review-flow.spec.ts
```

---

### Task 1: Loyiha skeleti va ma'lumotlar modeli

**Files:**
- Create: `backend/pyproject.toml`, `backend/engcheck/config.py`, `backend/engcheck/core/db.py`, `backend/engcheck/core/models.py`
- Test: `backend/tests/conftest.py`, `backend/tests/core/test_models.py`

**Interfaces:**
- Produces:
  - `Settings(data_dir: Path, db_url: str, host="127.0.0.1", port=8765)`; `get_settings()` muhit o‘zgaruvchisi `ENGCHECK_DATA_DIR` ni o‘qiydi.
  - `init_db(db_url) -> sessionmaker`; `Base`.
  - Modellar: `User, Session, Project, Document, DocPage, Tag, TagOccurrence, TagParam, DocRef, Rule, ReviewRun, Finding, FindingEvidence, FindingAction, Standard, AuditLog` — maydonlar spetsifikatsiya 4-bo‘limidagidek.
  - `StrEnum` lar: `Role, Stage, DocType, Discipline, Severity, Confidence, FindingStatus, ParseStatus, TagClass(equipment, line, instrument, pipe_class), Method(cell, regex)`.
  - Cheklovlar: `Tag(project_id, tag)` yagona; `Document(project_id, sha256)` yagona.
  - `conftest.py` fixture `db` — vaqtinchalik faylda yangi baza sessiyasi.

- [ ] **Step 1:** `pyproject.toml` (bog‘liqliklar Tech Stack bo‘yicha) va `pip install -e "backend[dev]"`.
- [ ] **Step 2: Test yoz**

```python
def test_tag_unique_per_project(db):
    p = Project(name="GP", industry="gas_processing", stage=Stage.DD)
    db.add(p); db.flush()
    db.add_all([Tag(project_id=p.id, tag="V-101", tag_class=TagClass.equipment),
                Tag(project_id=p.id, tag="V-101", tag_class=TagClass.equipment)])
    with pytest.raises(IntegrityError):
        db.flush()

def test_document_sha_unique_per_project(db): ...   # xuddi shunday
def test_enum_values_match_spec():
    assert [s.value for s in Severity] == ["critical", "major", "minor", "info"]
    assert [s.value for s in FindingStatus] == ["new", "reviewed", "confirmed", "rejected", "fixed"]
```

- [ ] **Step 3:** Testlar yiqilishini tekshir: `pytest backend/tests/core/test_models.py -q` → FAIL.
- [ ] **Step 4:** Modellarni yoz. → PASS.
- [ ] **Step 5:** Commit: `feat: loyiha skeleti va ma'lumotlar modeli`.

### Task 2: Autentifikatsiya va rollar

**Files:**
- Create: `backend/engcheck/core/auth.py`
- Test: `backend/tests/core/test_auth.py`

**Interfaces:**
- Produces:
  - `create_user(db, login, password, role: Role, locale="uz") -> User` — parol 8 belgidan qisqa bo‘lsa `ValueError`.
  - `login(db, login, password) -> str | None` — xom token qaytaradi; bazada faqat SHA-256 xeshi; muddati 12 soat.
  - `user_for_token(db, token) -> User | None` — muddati o‘tgan yoki `is_active=False` → `None`.
  - `logout(db, token) -> None`.
  - `class Perm(StrEnum): view, upload, review, decide, manage_rules, delete_project, manage_users`.
  - `can(role: Role, perm: Perm) -> bool`.

- [ ] **Step 1: Test yoz**

```python
@pytest.mark.parametrize("role,perm,expected", [
    (Role.viewer, Perm.view, True), (Role.viewer, Perm.upload, False),
    (Role.engineer, Perm.decide, True), (Role.engineer, Perm.manage_rules, False),
    (Role.lead, Perm.delete_project, True), (Role.lead, Perm.manage_users, False),
    (Role.admin, Perm.manage_users, True),
])
def test_permission_matrix(role, perm, expected): assert can(role, perm) is expected

def test_login_roundtrip_and_hash_not_plain(db):
    u = create_user(db, "aziz", "S3cret-pass", Role.engineer)
    assert "S3cret-pass" not in u.password_hash
    tok = login(db, "aziz", "S3cret-pass")
    assert user_for_token(db, tok).id == u.id
    assert login(db, "aziz", "wrong") is None
    assert db.query(Session).one().token_hash != tok

def test_expired_token_rejected(db): ...   # expires_at o‘tmishga suriladi → None
def test_short_password_rejected(db): ...
```

- [ ] **Step 2:** FAIL ni ko‘r. **Step 3:** Yoz (argon2 `PasswordHasher`). **Step 4:** PASS. **Step 5:** Commit `feat: autentifikatsiya va rol ruxsatlari`.

### Task 3: Audit jurnali

**Files:**
- Create: `backend/engcheck/core/audit.py`
- Test: `backend/tests/core/test_audit.py`

**Interfaces:**
- Produces:
  - `record(db, user_id: int | None, action: str, object_type: str, object_id: int | None, details: dict | None = None) -> AuditLog`
  - `verify(db) -> int | None` — zanjir butun bo‘lsa `None`, aks holda birinchi buzilgan yozuv `id` si.
  - Xesh: `sha256(prev_hash + json.dumps([user_id, action, object_type, object_id, details, created_at_iso], sort_keys=True, ensure_ascii=False))`; birinchi yozuv uchun `prev_hash = "0"*64`.

- [ ] **Step 1: Test yoz**

```python
def test_chain_verifies_and_detects_tamper(db):
    for i in range(3): record(db, 1, "finding.confirm", "finding", i, {"comment": "ok"})
    assert verify(db) is None
    row = db.get(AuditLog, 2); row.details = {"comment": "o‘zgartirildi"}; db.flush()
    assert verify(db) == 2

def test_detects_deleted_row(db): ...   # 2-yozuv o‘chiriladi → verify(db) == 3
```

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: xesh-zanjirli audit jurnali`.

### Task 4: Birliklar va qiymat ajratish

**Files:**
- Create: `backend/engcheck/ingest/units.py`
- Test: `backend/tests/ingest/test_units.py`

**Interfaces:**
- Produces:
  - `@dataclass Quantity(raw: str, number: float | None, unit: str | None, si_value: float | None, si_unit: str | None, unit_known: bool, assumed: bool)`
  - `parse_quantity(text: str, param: str, unit_hint: str | None = None) -> Quantity`
  - `PARAM_KIND: dict[str, str]` — `design_pressure, operating_pressure → "pressure"`; `design_temperature, operating_temperature → "temperature"`; `flow_rate → "flow"`; `size → "length"`; `power → "power"`; qolganlari (`material, pipe_class, fluid`) → `"text"`.
  - SI: bosim `kPa(g)`, harorat `°C`, sarf `m³/h`, o‘lcham `mm`, quvvat `kW`.
  - Tan olinadigan birliklar: bosim `barg, bar(g), bar, bara, psig, psi, psia, kPa, kPag, MPa, MPag, kgf/cm2, kg/cm2g, атм, бар, кПа, МПа`; harorat `°C, C, degC, °F, F, degF, K`; sarf `m3/h, m³/h, м3/ч, gpm, l/s, l/min`; o‘lcham `mm, мм, in, inch, "`, `NPS`, `DN`; quvvat `kW, кВт, W, MW, hp`.
  - Absolyut bosim (`bara, psia`) dan 101.325 kPa ayiriladi. Belgisiz `bar, psi, kPa, MPa` manometrik deb olinadi va `assumed=True` (ishonchlilik pasayadi — 6-vazifa foydalanadi).
  - `unit_hint` — ustun sarlavhasidagi birlik (`"Design Pressure, barg"`); katakda birlik bo‘lmasa shu ishlatiladi.
  - `"text"` turidagi parametr: `number=None`, `si_value=None`, `unit_known=True`.

- [ ] **Step 1: Test yoz**

```python
@pytest.mark.parametrize("text,param,hint,si", [
    ("16 barg", "design_pressure", None, 1600.0),
    ("174 psig", "operating_pressure", None, 1199.69),
    ("10,5", "design_pressure", "barg", 1050.0),
    ("2 bara", "design_pressure", None, 98.675),
    ("1.6 MPa", "design_pressure", None, 1600.0),
    ("212 °F", "design_temperature", None, 100.0),
    ("6\"", "size", None, 152.4),
    ("DN150", "size", None, 150.0),
    ("55 кВт", "power", None, 55.0),
    ("100 gpm", "flow_rate", None, 22.712),
])
def test_si_conversion(text, param, hint, si):
    assert parse_quantity(text, param, hint).si_value == pytest.approx(si, rel=1e-3)

def test_bare_bar_is_assumed_gauge():
    q = parse_quantity("16 bar", "design_pressure"); assert q.assumed and q.si_value == 1600.0
def test_unknown_unit():
    q = parse_quantity("16 foo", "design_pressure")
    assert q.number == 16 and q.si_value is None and q.unit_known is False
def test_number_without_any_unit_is_unknown(): ...   # "16", hint=None → unit_known False
def test_text_param_passthrough():
    q = parse_quantity("  CS A516 Gr.70 ", "material"); assert q.raw == "CS A516 Gr.70" and q.unit_known
def test_empty_is_none_number(): assert parse_quantity("", "power").number is None
def test_thousands_and_range_not_misparsed(): ...   # "1 200 kPa" → 1200; "-29/150 °C" → number None, unit_known True (diapazon solishtirilmaydi)
```

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: birliklarni SI ga o‘girish`.

### Task 5: Parserlar va format aniqlash

**Files:**
- Create: `backend/engcheck/ingest/model.py`, `detect.py`, `parsers/{__init__,pdf,xlsx,docx,dxf}.py`
- Test: `backend/tests/ingest/test_parsers.py` (fayllar testda `tmp_path` ichida yaratiladi)

**Interfaces:**
- Produces:
  - `Cell(text: str, location: str)`; `Table(rows: list[list[Cell]])`; `TextItem(text: str, location: str, attrs: dict[str, str] | None = None)`; `Page(number: int, text: str, tables: list[Table], items: list[TextItem])`; `ParsedDocument(pages: list[Page])`.
  - `location` formati: XLSX `"Sheet1!C7"`; PDF `"t1:r3:c2"` (sahifadagi jadval, qator, ustun); DOCX `"table2:r3:c1"` yoki `"para14"`; DXF `"x=120.5,y=88.0"`.
  - `detect_format(path: Path) -> str` → `"pdf" | "xlsx" | "docx" | "dxf" | "dwg" | "unknown"`. Imzo ustun: `%PDF`, ZIP ichida `xl/` yoki `word/`, `AC10` (DWG), matnli `SECTION` (DXF).
  - `class ParseError(Exception)`: `code` ∈ `"unsupported_dwg", "unknown_format", "corrupt", "needs_ocr"`.
  - `parse_file(path: Path) -> ParsedDocument` — formatni aniqlab parserga uzatadi.
  - PDF: har sahifa `extract_text()` va `extract_tables()`; hech bir sahifada matn bo‘lmasa `ParseError("needs_ocr")`.
  - XLSX: har varaq — bitta `Page`, butun ishlatilgan diapazon — bitta `Table`; birlashtirilgan kataklar qiymati birinchi katakda; formulalar `data_only=True`.
  - DOCX: bitta `Page(number=1)`; paragraflar `items` ga, jadvallar `tables` ga.
  - DXF: model fazosidagi `TEXT`, `MTEXT` → `TextItem`; `INSERT` atributlari → `TextItem(text=blok nomi, attrs={TAG: qiymat})`. Bitta `Page(number=1)`.

- [ ] **Step 1: Test yoz** — har format uchun kichik fayl yaratib, tuzilma va `location` ni tekshir:

```python
def test_xlsx_cells_and_location(tmp_path): ...     # A1="Tag", B2=16 → rows[1][1].text=="16", location=="List!B2"
def test_xlsx_merged_title_row(tmp_path): ...       # A1:D1 birlashtirilgan → rows[0][0].text to‘la, qolgani ""
def test_pdf_table_extracted(tmp_path): ...         # reportlab bilan 2x2 jadval → tables[0].rows[1][1].text
def test_pdf_without_text_needs_ocr(tmp_path): ...  # faqat rasm/chiziqli sahifa → ParseError.code=="needs_ocr"
def test_docx_table_and_paragraph(tmp_path): ...
def test_dxf_text_and_block_attrs(tmp_path): ...    # INSERT attrs {"TAG":"V-101","DESIGN_PRESSURE":"16 barg"}
def test_dwg_rejected(tmp_path):                    # b"AC1032" + nol baytlar
    with pytest.raises(ParseError) as e: parse_file(p)
    assert e.value.code == "unsupported_dwg"
def test_empty_file_is_corrupt(tmp_path): ...       # 0 bayt → code=="corrupt"
def test_pdf_named_xlsx_parsed_by_signature(tmp_path): ...  # imzo ustun → PDF sifatida o‘qiladi
def test_truncated_xlsx_is_corrupt(tmp_path): ...   # ZIP boshi kesilgan → code=="corrupt"
```

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: PDF, XLSX, DOCX, DXF parserlari`.

### Task 6: Teg va parametr ajratish

**Files:**
- Create: `backend/engcheck/ingest/tagging.py`, `headers.py`, `extract.py`
- Test: `backend/tests/ingest/test_tagging.py`, `test_headers.py`, `test_extract.py`

**Interfaces:**
- Consumes: `ParsedDocument` (5), `parse_quantity` (4), `DocType, TagClass, Method, Confidence` (1).
- Produces:
  - `find_tags(text: str) -> list[tuple[str, TagClass]]` — kanonik teg va sinfi.
  - `normalize_tag(text: str) -> str | None` — bosh harf, bo‘shliqsiz, harf va raqam orasiga defis: `"p-101 a" → "P-101A"`, `"P101A" → "P-101A"`.
  - Namunalar: quvur `^\d+(\.\d+)?"-[A-Z]{1,4}-\d{3,5}-[A-Z0-9]{2,6}$` (oldin tekshiriladi); asbob — ISA 5.1 harf kodi (`P,T,F,L,A` + `I,C,T,S,V,E,G,Y,H,L` 1–3 ta) + `-` + 3–5 raqam; uskuna — 1–3 harf + `-` + 3–4 raqam + ixtiyoriy `A–D`. Asbob namunasi uskunadan oldin tekshiriladi.
  - `match_header(text: str) -> tuple[str, str | None] | None` — `(param, unit_hint)`; maxsus kalitlar `"tag"`, `"revision"`, `"doc_number"`. Lug‘at uz/en/ru sinonimlari bilan, masalan `design_pressure`: `design pressure, design press., des. press, loyiha bosimi, hisobiy bosim, расчетное давление, расчётное давление`. Birlik sarlavhadan vergul yoki qavsdan keyin olinadi.
  - `@dataclass ExtractedParam(tag, param, raw_value, raw_unit, si_value, si_unit, page_no, location, method: Method, confidence: Confidence, unit_known: bool)`
  - `@dataclass ExtractedTag(tag, tag_class, page_no, location, method)`
  - `@dataclass Extraction(tags, params, refs: list[tuple[str, str, int]], unmapped_headers: list[str], doc_number: str | None, revision: str | None)`
  - `extract(doc: ParsedDocument, doc_type: DocType) -> Extraction`
  - Jadval turlari: **ustunli** — sarlavha qatori birinchi 15 qatordan topiladi (`tag` va kamida bitta boshqa moslik); har keyingi qator — bitta teg. **Kalit–qiymat** (datasheet) — birinchi ustun `match_header` ga mos, ikkinchi ustun qiymat, ixtiyoriy uchinchi ustun birlik; teg `tag` qatoridan. DXF blok atributlari kalit–qiymat sifatida, `method=cell`.
  - Erkin matn va DXF `TEXT` dan faqat teglar olinadi (`method=regex`), parametr olinmaydi.
  - Bo‘sh katak parametr yaratmaydi (R003 shu yo‘qlikni topadi).
  - `MATERIAL_SPEC` da `pipe_class` ustunidagi qiymatlar `TagClass.pipe_class` teglari bo‘ladi.
  - Havolalar: `([A-Z]{2,5}-[A-Z]{2,5}-\d{3,5})\s*,?\s*Rev\.?\s*([A-Z0-9]{1,3})` → `(doc_number, revision, page_no)`.
  - Ishonchlilik: `cell` + birlik aniq → `high`; `cell` + `assumed` birlik → `medium`; `regex` → `medium`.

- [ ] **Step 1: Test yoz**

```python
@pytest.mark.parametrize("raw,canon", [("p-101 a","P-101A"),("P101A","P-101A"),("V-2001","V-2001"),("hello",None)])
def test_normalize_tag(raw, canon): assert normalize_tag(raw) == canon

def test_find_tags_classes():
    got = dict(find_tags('Pump P-101A feeds 10"-HC-1001-A1A, see PT-1001 and FIC-2003'))
    assert got == {"P-101A": TagClass.equipment, '10"-HC-1001-A1A': TagClass.line,
                   "PT-1001": TagClass.instrument, "FIC-2003": TagClass.instrument}

@pytest.mark.parametrize("h,exp", [
    ("Design Pressure, barg", ("design_pressure","barg")),
    ("Loyiha bosimi (MPa)", ("design_pressure","MPa")),
    ("Расчётное давление", ("design_pressure",None)),
    ("Tag No.", ("tag",None)), ("Material", ("material",None)), ("Remarks", None)])
def test_match_header(h, exp): assert match_header(h) == exp

def test_columnar_table_with_title_rows(): ...   # sarlavha 4-qatorda → 2 teg, params to‘g‘ri, location katak manzili
def test_key_value_datasheet(): ...              # tag=V-101, design_pressure si_value==1000.0, method cell, high
def test_empty_cell_yields_no_param(): ...
def test_unmapped_headers_reported(): ...        # "Remarks" unmapped_headers ichida
def test_free_text_gives_tags_only(): ...        # method regex, params bo‘sh
def test_refs_extracted(): ...                   # "Ref. P&ID GP-PID-001 Rev A" → ("GP-PID-001","A",1)
def test_material_spec_pipe_classes(): ...       # A1A, B1A → TagClass.pipe_class
def test_assumed_unit_lowers_confidence(): ...   # "16 bar" → medium
```

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: teg va parametr ajratish`.

### Task 7: Namunaviy sanoat loyihasi

**Files:**
- Create: `samples/generate_sample_project.py`
- Test: `backend/tests/test_sample_project.py`

**Interfaces:**
- Consumes: `parse_file`, `extract`.
- Produces: `generate(out_dir: Path) -> list[SampleDoc]`; `SampleDoc(path, doc_type, discipline, doc_number, revision)`. Buyruq: `python samples/generate_sample_project.py <papka>`.
- Mazmun (amin bilan gaz tozalash bloki, loyiha "GP-100"):

| Fayl | Tur | Raqam / Rev | Mazmun |
|---|---|---|---|
| `GP-PID-001_RevC.dxf` | PID | GP-PID-001 / C | Bloklar: V-101 (DP 16 barg, DT 120 °C), V-102, P-101A, P-101B, E-101, E-102; chiziq matnlari: `10"-HC-1001-A1A`, `8"-AM-1002-A1A`, `6"-AM-1003-B1A`, `4"-AM-1005-B2C`; asboblar PT-1001, FIC-2003 |
| `GP-EQL-001_RevB.xlsx` | EQUIPMENT_LIST | GP-EQL-001 / B | Sarlavha 4-qatorda. V-101 (DP 16 barg, OP 12 barg, DT 120 °C, CS), V-102 (DP 5 barg, OP 7 barg), P-101A (45 kW), P-101B (45 kW, SS316), E-101. **E-102 yo‘q.** |
| `GP-LL-001_RevB.xlsx` | LINE_LIST | GP-LL-001 / B | PID dagi 4 chiziq + `6"-AM-1004-A1A`; ustunlar: line no, size, fluid, pipe class, DP, DT |
| `GP-DS-V101_RevA.pdf` | DATASHEET | GP-DS-V101 / A | V-101: DP **14 barg**, OP **174 psig**, DT 120 °C, CS; "Ref. P&ID GP-PID-001 Rev **A**" |
| `GP-DS-P101_RevA.pdf` | DATASHEET | GP-DS-P101 / A | 1-sahifa P-101A: **55 kW**, SS316; 2-sahifa P-101B: 45 kW, material **bo‘sh**; "Ref. P&ID GP-PID-001 Rev C" |
| `GP-MS-001_RevA.docx` | MATERIAL_SPEC | GP-MS-001 / A | Quvur sinflari jadvali: A1A, B1A (**B2C yo‘q**) |

- [ ] **Step 1: Test yoz**

```python
def test_sample_generates_six_parsable_docs(tmp_path):
    docs = generate(tmp_path); assert len(docs) == 6
    for d in docs: assert extract(parse_file(d.path), d.doc_type).tags

def test_seeded_values_present(tmp_path):
    ex = {d.doc_number: extract(parse_file(d.path), d.doc_type) for d in generate(tmp_path)}
    dp = lambda n, t: next(p.si_value for p in ex[n].params if p.tag == t and p.param == "design_pressure")
    assert dp("GP-PID-001", "V-101") == 1600.0 and dp("GP-DS-V101", "V-101") == 1400.0
    assert "E-102" not in {t.tag for t in ex["GP-EQL-001"].tags}
    assert ("GP-PID-001", "A", 1) in ex["GP-DS-V101"].refs
```

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: namunaviy gaz tozalash loyihasi generatori`.

### Task 8: Qabul qilish xizmati

**Files:**
- Create: `backend/engcheck/ingest/service.py`
- Test: `backend/tests/ingest/test_service.py`

**Interfaces:**
- Consumes: 1, 3, 5, 6-vazifalar.
- Produces:
  - `ingest_file(db, settings, project_id, user_id, src_path: Path, filename: str, doc_type: DocType, discipline: Discipline, doc_number: str | None = None, revision: str | None = None) -> Document`
  - `class DuplicateDocument(Exception)` — shu loyihada bir xil SHA-256.
  - `suggest_doc_type(filename: str) -> DocType | None` — nom bo‘yicha taklif (`PID|P&ID → PID`, `EQL|equipment → EQUIPMENT_LIST`, `LL|line list → LINE_LIST`, `DS|datasheet → DATASHEET`, `MS|material → MATERIAL_SPEC`, `PFD`, `HAZOP`, `HAZID`).
  - Asl fayl `data_dir/files/<project_id>/<sha256><kengaytma>` ga nusxalanadi.
  - `ParseError` → `Document.parse_status` = `needs_ocr | unsupported | error`, `parse_error` = kod; istisno tashqariga chiqmaydi.
  - Muvaffaqiyatda: `DocPage`, `Tag` (mavjud bo‘lsa qayta ishlatiladi), `TagOccurrence`, `TagParam`, `DocRef` yoziladi; `doc_number`/`revision` foydalanuvchi bermagan bo‘lsa ajratilgandan olinadi. Audit: `document.upload`.
  - `delete_document(db, settings, document_id, user_id)` — hujjat va undan olingan qatorlar; faqat boshqa hujjatda uchramaydigan teglar o‘chadi.

- [ ] **Step 1: Test yoz**

```python
def test_ingest_persists_params_with_provenance(db, settings, sample_docs): ...
    # V-101 design_pressure uchun document_id, page_no, location bo‘sh emas
def test_duplicate_rejected(db, settings, sample_docs): ...            # DuplicateDocument
def test_same_tag_across_docs_is_one_row(db, settings, sample_docs): ...  # Tag "V-101" bitta, occurrences 3 ta
def test_dwg_marked_unsupported_not_raised(db, settings, tmp_path): ...
def test_corrupt_file_marked_error_and_next_file_still_ingests(db, settings, tmp_path, sample_docs): ...
def test_upload_is_audited(db, settings, sample_docs): ...             # AuditLog.action == "document.upload"
def test_delete_document_keeps_shared_tags(db, settings, sample_docs): ...
def test_suggest_doc_type(): assert suggest_doc_type("GP-PID-001_RevC.dxf") == DocType.PID
```

`sample_docs` fixture — `generate(tmp_path)` natijasi (`conftest.py` ga qo‘shiladi).

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: hujjatlarni qabul qilish xizmati`.

### Task 9: Qoidalar va tekshiruv dvigateli

**Files:**
- Create: `backend/engcheck/review/rules/{__init__,base,r001,r002,r003,r004,r005,r006,r007}.py`, `backend/engcheck/review/engine.py`
- Test: `backend/tests/review/test_rules.py`, `test_engine.py`

**Interfaces:**
- Consumes: modellar (1), audit (3).
- Produces:
  - `@dataclass Evidence(document_id, page_no, location, value: str)`
  - `@dataclass Draft(rule_code, tag_id: int | None, param: str | None, severity, confidence, description_key: str, args: dict, evidence: list[Evidence])`
  - `class RuleBase: code: str; def check(self, db, project_id) -> list[Draft]`
  - `ALL_RULES: list[RuleBase]`; `seed_rules(db)` — `rules` jadvalini uch tilli sarlavha bilan to‘ldiradi (idempotent).
  - `run_review(db, project_id, user_id) -> ReviewRun`
  - `render(description_key, args, locale) -> tuple[str, str, str]` — (tavsif, izoh, tavsiya); shablonlar `review/messages.py` da uch tilda.
  - `fingerprint = sha256(rule_code | tag | param | saralangan (doc_number, value) juftlari)`.
  - Qaror ko‘chirish: yangi topilmaning `fingerprint` i loyihaning oldingi seansidagi `confirmed`, `rejected` yoki `fixed` topilmaga teng bo‘lsa, holat va oxirgi izoh ko‘chiriladi.
  - Faqat `rules.enabled == True` qoidalar ishlaydi. Qoida istisno tashlasa: `ReviewRun.errors` (JSON ro‘yxat) ga `{"rule": kod, "error": matn}` yoziladi, qolganlari davom etadi.
- Qoidalar mantig‘i:
  - **R001** — teg + parametr bo‘yicha turli hujjatlardagi qiymatlar. Sonli: `max−min > 1 % × max(|qiymat|)` (SI da); matnli: bosh-kichik harf va bo‘shliqlarni hisobga olmay teng emas. Bitta topilma, barcha qiymatlar dalil. Jiddiylik: `*_pressure`, `*_temperature` → `critical`, qolgani `major`. Ishonchlilik: barcha dalil `cell` va `high` → `high`, aks holda `medium`. `si_value` yo‘q qiymatlar solishtirilmaydi.
  - **R002** — faqat ikkala hujjat turi loyihada `parsed` holatda mavjud bo‘lsa: uskuna `PID ↔ EQUIPMENT_LIST` (ikki tomonga), chiziq `PID ↔ LINE_LIST` (ikki tomonga), `DATASHEET → EQUIPMENT_LIST` (bir tomonga). `major`; dalil `cell` bo‘lsa `high`, `regex` bo‘lsa `medium`.
  - **R003** — majburiy parametrlar: `DATASHEET`: `design_pressure, design_temperature, material`; `LINE_LIST`: `size, fluid, pipe_class`; `EQUIPMENT_LIST`: yo‘q. Faqat hujjatda shu teg uchun kamida bitta boshqa parametr bor bo‘lsa (ya'ni teg haqiqatan shu hujjatning qatori/varag‘i). Datasheetda uskuna turi bo‘yicha: nasos (`P-`) uchun `design_pressure` va `design_temperature` majburiy emas. `minor`; `design_*` uchun `major`; `high`.
  - **R004** — bitta hujjat ichida yoki hujjatlararo: `design_pressure < operating_pressure` yoki `design_temperature < operating_temperature` (SI da). `critical`, `high`.
  - **R005** — `LINE_LIST` dagi `pipe_class` qiymati `MATERIAL_SPEC` dan olingan `pipe_class` teglari orasida yo‘q. Material spec loyihada bo‘lmasa qoida ishlamaydi. `major`, `high`. Har sinf uchun bitta topilma.
  - **R006** — `DocRef.ref_revision` ≠ shu `doc_number` li hujjatning `revision` i. `minor`, `medium`.
  - **R007** — `TagParam` sonli turda, `number` bor, lekin `si_value` yo‘q. `minor`, `high`.

- [ ] **Step 1: Qoida testlari** — har qoida uchun bazaga to‘g‘ridan-to‘g‘ri yozilgan kichik holatlar (`make_param(db, project, doc, tag, param, raw, si)` yordamchisi `tests/review/factories.py` da):

```python
def test_r001_flags_mismatch_and_is_critical_for_pressure(db): ...   # 1600 vs 1000 → 1 draft, 2 evidence, critical
def test_r001_within_tolerance_ok(db): ...                           # 1200.0 vs 1199.69 → []
def test_r001_text_case_insensitive(db): ...                         # "SS316" vs "ss316 " → []
def test_r001_same_document_twice_not_compared(db): ...
def test_r002_both_directions(db): ...
def test_r002_skipped_when_counterpart_doc_type_absent(db): ...
def test_r002_datasheet_one_way_only(db): ...                        # EQL dagi teg datasheetda yo‘q → topilma yo‘q
def test_r003_missing_material_on_datasheet(db): ...
def test_r003_pump_does_not_need_design_pressure(db): ...
def test_r004_design_below_operating(db): ...
def test_r004_equal_is_ok(db): ...
def test_r005_class_missing_from_spec(db): ...
def test_r005_skipped_without_material_spec(db): ...
def test_r006_stale_revision(db): ...
def test_r006_unknown_doc_number_ignored(db): ...
def test_r007_unknown_unit(db): ...
```

- [ ] **Step 2:** FAIL → qoidalarni yoz → PASS.
- [ ] **Step 3: Dvigatel testlari**

```python
def test_run_persists_findings_with_evidence_and_text(db): ...       # description/rationale/recommendation bo‘sh emas
def test_disabled_rule_not_run(db): ...
def test_failing_rule_recorded_and_others_continue(db, monkeypatch): ...
def test_rerun_carries_decision_by_fingerprint(db): ...              # confirmed → ikkinchi seansda ham confirmed
def test_changed_value_gets_new_finding(db): ...                     # qiymat o‘zgarsa fingerprint boshqa → status new
def test_render_three_locales(): ...                                 # uz/en/ru matnlari farq qiladi va teg bor
def test_source_text_is_internal_inconsistency_without_standard(db): ...
```

- [ ] **Step 4:** FAIL → dvigatelni yoz → PASS. **Step 5:** Commit `feat: tekshiruv qoidalari va dvigatel`.

### Task 10: Namunaviy loyihada integratsion tekshiruv

**Files:**
- Test: `backend/tests/test_sample_review.py`

**Interfaces:**
- Consumes: `generate` (7), `ingest_file` (8), `run_review` (9).

- [ ] **Step 1: Test yoz**

```python
EXPECTED = {
    ("R001", "V-101", "design_pressure"), ("R001", "P-101A", "power"),
    ("R002", "E-102", None), ("R002", '6"-AM-1004-A1A', None),
    ("R003", "P-101B", "material"), ("R004", "V-102", "design_pressure"),
    ("R005", "B2C", "pipe_class"), ("R006", None, None),
}
def test_sample_project_yields_exactly_seeded_findings(db, settings, sample_docs):
    # 6 hujjat yuklanadi, run_review
    assert got == EXPECTED            # ortiqcha ham, kam ham bo‘lmasin

def test_psi_vs_barg_equal_value_not_flagged(db, settings, sample_docs):
    assert ("R001", "V-101", "operating_pressure") not in got

def test_every_finding_points_to_document_and_page(db, settings, sample_docs): ...
```

- [ ] **Step 2:** Ishga tushir. Ortiqcha yoki yetishmayotgan topilma bo‘lsa, sababini top: qoida xatosi bo‘lsa qoidani, namuna xatosi bo‘lsa generatorni tuzat (testdagi `EXPECTED` o‘zgarmaydi).
- [ ] **Step 3:** PASS. **Step 4:** Commit `test: namunaviy loyihada to‘liq tekshiruv`.

### Task 11: HTTP API

**Files:**
- Create: `backend/engcheck/api/{app,deps,errors}.py`, `routes_{auth,projects,documents,reviews,findings,dashboard,audit}.py`, `backend/engcheck/__main__.py`
- Test: `backend/tests/api/conftest.py`, `test_auth_api.py`, `test_documents_api.py`, `test_findings_api.py`, `test_permissions.py`

**Interfaces:**
- Consumes: hammasi.
- Produces: `create_app(settings) -> FastAPI`; `python -m engcheck` → `127.0.0.1:8765`.
- Nuqtalar (hammasi `/api` ostida; `Authorization: Bearer <token>`):

| Metod va yo‘l | Ruxsat | Vazifasi |
|---|---|---|
| `GET /setup` | ochiq | `{"needs_setup": bool}` |
| `POST /setup` | ochiq, faqat foydalanuvchi yo‘q paytda | Birinchi admin |
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | — | |
| `GET/POST /users`, `PATCH /users/{id}` | manage_users | |
| `GET/POST /projects`, `GET /projects/{id}` | view / upload | |
| `DELETE /projects/{id}` | delete_project | |
| `GET /projects/{id}/documents` | view | |
| `POST /projects/{id}/documents` (multipart: file, doc_type, discipline, doc_number?, revision?) | upload | 201; takror → 409 `duplicate_document` |
| `GET /documents/{id}` | view | Metama'lumot, sahifalar matni, ajratilgan parametrlar |
| `GET /documents/{id}/file` | view | Asl fayl |
| `DELETE /documents/{id}` | upload | |
| `GET /doc-type-suggestion?filename=` | view | |
| `POST /projects/{id}/reviews` | review (= upload) | Tekshiruvni boshlaydi |
| `GET /projects/{id}/findings?severity=&status=&rule=&document_id=&tag=` | view | Oxirgi seans topilmalari |
| `GET /findings/{id}` | view | Dalillar va qarorlar tarixi bilan |
| `POST /findings/{id}/actions` `{action: review|confirm|reject|mark_fixed, comment}` | decide | Noto‘g‘ri o‘tish → 409 `invalid_transition`; `reject` izohsiz → 422 |
| `GET /projects/{id}/dashboard` | view | Hujjatlar soni (tur va parse_status bo‘yicha), topilmalar (jiddiylik va holat bo‘yicha), ochiq kritiklar |
| `GET/PATCH /rules` | view / manage_rules | |
| `GET /audit?limit=`, `GET /audit/verify` | manage_users | |

- Til: foydalanuvchi `locale` i, kirishdan oldin `Accept-Language`. Topilma matni so‘rov vaqtida `render` qilinadi.
- Har o‘zgartiruvchi nuqta audit yozadi.
- `frontend/dist` mavjud bo‘lsa `/` da statik tarqatiladi.

- [ ] **Step 1: Test yoz** (`TestClient`; `client_as(role)` fixture):

```python
def test_setup_then_login_then_me(client): ...
def test_setup_closed_after_first_admin(client): ...                 # 409
def test_upload_review_decide_flow(client_as, sample_docs): ...      # 8 topilma; confirm → status confirmed; audit yozuvi bor
def test_duplicate_upload_409(client_as, sample_docs): ...
def test_dwg_upload_201_with_unsupported_status(client_as, tmp_path): ...
@pytest.mark.parametrize("role,method,path,code", [
    ("viewer","POST","/api/projects",403), ("viewer","GET","/api/projects",200),
    ("engineer","PATCH","/api/rules",403), ("lead","GET","/api/users",403),
    (None,"GET","/api/projects",401)])
def test_permissions(role, method, path, code, ...): ...
def test_invalid_transition_409(client_as, ...): ...                 # new → mark_fixed
def test_reject_requires_comment(client_as, ...): ...
def test_error_message_localized(client): ...                        # Accept-Language: ru → ruscha xabar
def test_findings_filter_by_severity(client_as, ...): ...
def test_dashboard_counts(client_as, ...): ...                       # critical == 2, major, minor sonlari
def test_audit_verify_ok(client_as, ...): ...
```

- [ ] **Step 2–5:** FAIL → yoz → PASS → commit `feat: HTTP API`.

### Task 12: Interfeys

**Files:**
- Create: `frontend/` (Vite React-TS shabloni), `src/api.ts`, `src/i18n/{index.ts,uz.json,en.json,ru.json}`, `src/pages/{Setup,Login,Projects,Project,Findings,FindingDetail,DocumentView,Dashboard}.tsx`, `src/components/{Layout,SeverityBadge,StatusBadge,LanguageSwitch,UploadDialog}.tsx`, `e2e/review-flow.spec.ts`, `e2e/i18n.spec.ts`, `playwright.config.ts`
- Test: `src/i18n/i18n.test.ts` (vitest), `e2e/*.spec.ts`

**Interfaces:**
- Consumes: 11-vazifadagi API.
- Yo‘llar: `/setup`, `/login`, `/projects`, `/projects/:id` (dashboard + hujjatlar), `/projects/:id/findings?severity=&status=`, `/findings/:id`, `/documents/:id?page=`.
- Dashboard kartalari havola: har biri filtrlangan topilmalar ro‘yxatini ochadi. Topilma kartasidagi har dalil `/documents/:id?page=N` ga olib boradi; hujjat sahifasida ajratilgan matn, parametrlar jadvali va "asl faylni ochish" havolasi.
- Topilma kartasida: tavsif, jiddiylik, izoh, manba, ishonchlilik, tavsiya, holat, qarorlar tarixi; `viewer` uchun qaror tugmalari ko‘rinmaydi.
- Til tanlovi `localStorage` da va kirgandan so‘ng foydalanuvchi profilida.
- Dizayn: bitta ustunli sodda tartib, chap navigatsiya; jiddiylik ranglari matn belgisi bilan birga (faqat rangga tayanmaydi).

- [ ] **Step 1: i18n testi**

```ts
test("uch til kalitlari bir xil", () => {
  expect(keys(en)).toEqual(keys(uz)); expect(keys(ru)).toEqual(keys(uz));
});
```

- [ ] **Step 2:** FAIL → i18n va sahifalarni yoz → `npm run build`, `npx vitest run` PASS.
- [ ] **Step 3: Playwright testlari** (`webServer`: vaqtinchalik `ENGCHECK_DATA_DIR` bilan `python -m engcheck`; namunaviy fayllar `globalSetup` da yaratiladi):

```ts
test("yuklash → tekshiruv → topilma → tasdiqlash", async ({ page }) => {
  // setup → login → loyiha yaratish → 6 fayl yuklash → "Tekshirish"
  await expect(page.getByTestId("finding-row")).toHaveCount(8);
  // dashboard "Kritik" kartasi → ro‘yxat 2 ta
  // V-101 topilmasi → dalil havolasi → /documents/…?page=1 ochiladi
  // orqaga → "Tasdiqlash" → holat "Tasdiqlangan"
});
test("uch tilda sarlavhalar", ...);   // uz/en/ru almashtirilganda "Topilmalar" / "Findings" / "Замечания"
test("viewer qaror tugmalarini ko‘rmaydi", ...);
```

- [ ] **Step 4:** `npx playwright test --trace off` PASS; asosiy sahifalardan skrinshot olib ko‘zdan kechir.
- [ ] **Step 5:** Commit `feat: uch tilli interfeys`.

### Task 13: Yo‘riqnoma va yakuniy tekshiruv

**Files:**
- Create: `README.md`

- [ ] **Step 1:** `README.md` (o‘zbek tilida): talablar, o‘rnatish, ishga tushirish (`python -m engcheck`), namunaviy loyihani yaratish va yuklash, rollar, qo‘llab-quvvatlanadigan formatlar va cheklovlar (DWG, OCR), testlarni ishga tushirish, ma'lumotlar qayerda saqlanishi, 1-siklga kirmagan narsalar.
- [ ] **Step 2:** Toza muhitda README bo‘yicha boshidan oxirigacha yur: o‘rnatish → namunani yaratish → ishga tushirish → brauzerda 8 topilma.
- [ ] **Step 3:** `pytest -q`, `npx vitest run`, `npx playwright test --trace off` — hammasi PASS; natijalarni hisobotga yoz.
- [ ] **Step 4:** Commit `docs: foydalanish yo‘riqnomasi`.
