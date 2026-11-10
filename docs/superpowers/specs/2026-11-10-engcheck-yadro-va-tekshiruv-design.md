# EngCheck — muhandislik hujjatlarini tekshirish platformasi

**Spetsifikatsiya: 1-sikl — yadro va tekshiruv dvigateli**
Sana: 2026-11-10 · Holat: ko‘rib chiqishda

## 1. Maqsad va doira

EngCheck — sanoat korxonalari (GTL, MTO, neftni qayta ishlash, gazni qayta
ishlash, suv va oqova suv tozalash) loyiha hujjatlarini FEED, DD va As-Built
bosqichlarida tekshiradigan desktop ilova. Foydalanuvchilar — loyiha instituti
yoki EPC kompaniyasining muhandislari.

Platforma 6 quyi tizimga bo‘lingan. Har biri alohida spetsifikatsiya, reja va
kod siklidan o‘tadi:

| # | Quyi tizim | Sikl |
|---|---|---|
| 1 | Yadro: loyihalar, rollar, audit, hujjat yuklash va parsing | **1 (shu hujjat)** |
| 2 | Tekshiruv dvigateli va topilmalar reyestri | **1 (shu hujjat)** |
| 3 | Bilimlar bazasi (RAG) va AI provayder qatlami | 2 |
| 4 | To‘liq dashboard va uch tilli interfeys | 3 |
| 5 | Prinsipial sxema generatori | 4 |
| 6 | 3D joylashuv modeli | 5 |

### 1-sikl yakunidagi natija

Muhandis ilovaga kiradi, loyiha yaratadi, PDF/DOCX/XLSX/DXF hujjatlarni
yuklaydi; tizim teg va parametrlarni ajratadi, 6 ta deterministik qoidani
ishga tushiradi, topilmalarni hujjat, sahifa, teg va parametrga bog‘lab
ko‘rsatadi; muhandis har birini tasdiqlaydi yoki rad etadi; barcha harakatlar
audit jurnaliga yoziladi.

### 1-siklga kirmaydi

AI tahlili, RAG, lokal modellar, OCR, sxema generatori, 3D model, loyiha
paketini eksport/import qilish, Electron o‘rnatuvchisi. Ular uchun jadval va
interfeyslar ko‘zda tutiladi (8-bo‘lim), lekin kod yozilmaydi.

## 2. Qabul qilingan qarorlar

| Qaror | Tanlov | Sabab |
|---|---|---|
| O‘rnatish shakli | Desktop ilova | Foydalanuvchi tanlovi; to‘liq oflayn |
| Ma'lumotlar | Lokal shifrlangan SQLite; hamkorlik loyiha paketi orqali | Server kerak emas |
| Stek | Electron qobiq + Python (FastAPI) xizmati + React/TypeScript | Parsing va AI kutubxonalari Pythonda; interfeys veb-texnologiyalarda |
| DWG | To‘g‘ridan-to‘g‘ri o‘qilmaydi | Yopiq format; DXF ga o‘girish talab qilinadi |
| Standart matnlari | Foydalanuvchi o‘z litsenziyasi bilan yuklaydi | Litsenziya cheklovi |

## 3. Arxitektura

```
Electron qobiq
  └─ React UI (uz/en/ru)
        │ HTTP, faqat 127.0.0.1, tasodifiy port, sessiya tokeni
  └─ Python xizmati (FastAPI)
        parsing → ajratish → normallashtirish → qoidalar → topilmalar
        auth/rollar · audit jurnali
        │
     Shifrlangan SQLite (SQLCipher) + fayl ombori (asl hujjatlar)
     Maxfiy kalitlar: OS kalit ombori (keyring)
```

1-siklda interfeys brauzerda ochiladigan React ilova sifatida ishlab chiqiladi
va testlanadi; Electron qobig‘i 3-siklda qo‘shiladi. Backend bunga bog‘liq
emas.

### Modullar (backend)

| Modul | Vazifasi | Bog‘liqligi |
|---|---|---|
| `core/db` | Baza ulanishi, migratsiyalar | SQLAlchemy |
| `core/auth` | Foydalanuvchi, parol xeshi, rollar, sessiya | `core/db` |
| `core/audit` | Xesh-zanjirli jurnal: yozish va butunlikni tekshirish | `core/db` |
| `ingest/parsers` | Har format uchun parser; umumiy `ParsedDocument` qaytaradi | pdfplumber, openpyxl, python-docx, ezdxf |
| `ingest/extract` | Teg va parametr ajratish | `ingest/parsers` |
| `ingest/units` | Birliklarni SI ga o‘girish | — |
| `review/rules` | Qoidalar: har biri alohida sinf | `core/db` |
| `review/engine` | Seansni boshqaradi, qoidalarni chaqiradi, topilma yozadi | `review/rules` |
| `api` | HTTP nuqtalari, rol tekshiruvi | hammasi |

Parser shartnomasi: `parse(path) -> ParsedDocument(pages=[Page(number, text,
tables, items)])`. Har ajratilgan qiymat o‘z joylashuvini (sahifa, jadval
katagi yoki koordinata) olib yuradi.

## 4. Ma'lumotlar bazasi

| Jadval | Asosiy maydonlar |
|---|---|
| `users` | id, login, password_hash (argon2), role, locale, is_active |
| `projects` | id, name, industry, stage (FEED/DD/AS_BUILT), created_by |
| `documents` | id, project_id, filename, doc_type, discipline, revision, sha256, parse_status, parse_error |
| `doc_pages` | id, document_id, page_no, text |
| `tags` | id, project_id, tag, tag_class (equipment/line/instrument) |
| `tag_params` | id, tag_id, param, raw_value, raw_unit, si_value, si_unit, document_id, page_no, location, method (cell/regex), confidence |
| `rules` | id, code, title_uz/en/ru, severity, standard_id (ixtiyoriy), enabled |
| `review_runs` | id, project_id, started_by, started_at, ai_mode (1-siklda doim `none`) |
| `findings` | id, run_id, rule_id, tag_id, param, description, severity, rationale, recommendation, source_type (rule/ai), confidence, status |
| `finding_evidence` | id, finding_id, document_id, page_no, location, value |
| `finding_actions` | id, finding_id, user_id, action, comment, created_at |
| `standards` | id, code, edition, status (active/superseded/withdrawn), license_type |
| `audit_log` | id, user_id, action, object_type, object_id, details, created_at, prev_hash, hash |

Reja tuzishda qo‘shilgan jadval va maydonlar (R002, R003, R006 va takroriy
tekshiruv uchun zarur):

| Jadval / maydon | Vazifasi |
|---|---|
| `documents.doc_number` | Hujjat raqami (masalan `GP-PID-001`); R006 shu orqali reviziyani solishtiradi |
| `tag_occurrences` (tag_id, document_id, page_no, location, method) | Teg qaysi hujjatda uchraganini saqlaydi; parametrsiz teglar uchun ham (R002, R003) |
| `doc_refs` (document_id, ref_doc_number, ref_revision, page_no) | Hujjat ichidagi boshqa hujjatga havolalar (R006) |
| `sessions` (token_hash, user_id, expires_at) | Kirish sessiyalari |
| `findings.fingerprint` | Qayta tekshirilganda muhandis qarori (tasdiqlangan / rad etilgan) saqlanib qolishi uchun |
| `tags.tag_class` ga `pipe_class` qiymati | Material spetsifikatsiyasidagi quvur sinflari (R005) |

Qo‘shimcha qoida **R007**: sonli qiymatning birligi tanilmadi (minor, high) —
5-bo‘limdagi "birlik noma'lum" topilmasi shu kod bilan chiqadi.

Qiymatlar to‘plami:

- `role`: `admin`, `lead`, `engineer`, `viewer`.
- `doc_type`: `PFD`, `PID`, `DATASHEET`, `EQUIPMENT_LIST`, `LINE_LIST`,
  `MATERIAL_SPEC`, `CALCULATION`, `HAZOP`, `HAZID`, `OTHER`.
- `discipline`: `process`, `mechanical`, `piping`, `instrumentation`,
  `electrical`, `civil`, `hse`, `technical`.
- `severity`: `critical`, `major`, `minor`, `info`.
- `confidence`: `high`, `medium`, `low`.
- `finding.status`: `new` → `reviewed` → `confirmed` | `rejected`;
  `confirmed` → `fixed`.
- `parse_status`: `pending`, `parsed`, `needs_ocr`, `unsupported`, `error`.

## 5. Hujjatlarni qabul qilish

1. Fayl yuklanadi, SHA-256 hisoblanadi, asl nusxa fayl omboriga saqlanadi.
   Bir xil xeshli fayl shu loyihada takror qabul qilinmaydi.
2. Format kengaytma va fayl imzosi bo‘yicha aniqlanadi.
3. Parser tanlanadi:
   - PDF — `pdfplumber`: matn va jadvallar. Sahifada matn bo‘lmasa hujjat
     `needs_ocr` holatini oladi.
   - XLSX — `openpyxl`: har varaq bir sahifa, kataklar manzili bilan.
   - DOCX — `python-docx`: paragraflar va jadvallar; sahifa raqami o‘rniga
     bo‘lim/jadval tartib raqami.
   - DXF — `ezdxf`: TEXT, MTEXT va blok atributlari koordinatasi bilan.
   - DWG — `unsupported`, xabar: "DWG ni DXF ga o‘girib yuklang".
4. Hujjat turi foydalanuvchi tomonidan ko‘rsatiladi; fayl nomi va sarlavha
   bo‘yicha taklif beriladi, lekin avtomatik qat'iy belgilanmaydi.
5. Ajratish:
   - Teglar sozlanadigan regex to‘plami bilan topiladi: uskuna
     (`P-101A`, `V-2001`, `E-301`), asbob (ISA 5.1: `PT-1001`, `FIC-2003`),
     quvur (`10"-HC-1001-A1A`).
   - Jadval ustunlari sarlavha lug‘ati (uz/en/ru sinonimlar) orqali
     parametrga bog‘lanadi: `design_pressure`, `design_temperature`,
     `operating_pressure`, `operating_temperature`, `material`, `pipe_class`,
     `size`, `fluid`, `flow_rate`, `power`.
   - Bog‘lanmagan ustunlar tashlab yuborilmaydi; hujjat sahifasida
     "bog‘lanmagan ustunlar" sifatida ko‘rsatiladi.
6. Normallashtirish: bosim → kPa(g), harorat → °C, sarf → m³/h, o‘lcham → mm,
   quvvat → kW. Asl qiymat va birlik saqlanadi. Birlik tanilmasa `si_value`
   bo‘sh qoladi va qiymat solishtirishda "birlik noma'lum" topilmasini beradi.

## 6. Tekshiruv qoidalari

Har bir qoida — `check(project) -> list[Finding]` usuli bor alohida sinf.

| Kod | Qoida | Jiddiylik | Ishonchlilik |
|---|---|---|---|
| R001 | Bir teg va parametr turli hujjatlarda turli qiymatga ega (bardoshlik: son uchun 1 %, matn uchun aniq moslik) | major; bosim va harorat uchun critical | ikkalasi `cell` bo‘lsa high, aks holda medium |
| R002 | Teg bir hujjat turida bor, kutilgan boshqasida yo‘q (PID ↔ EQUIPMENT_LIST ↔ LINE_LIST ↔ DATASHEET) | major | high (jadval), medium (matndan) |
| R003 | Majburiy parametr bo‘sh (hujjat turi bo‘yicha majburiy maydonlar ro‘yxati) | minor; loyiha bosimi/harorati uchun major | high |
| R004 | Mantiqiy chegara buzilgan: loyiha bosimi < ish bosimi; loyiha harorati < ish harorati | critical | high |
| R005 | Quvur sinfi line listda bor, material spetsifikatsiyasida yo‘q yoki boshqacha | major | high |
| R006 | Hujjat boshqa hujjatning eskirgan reviziyasiga havola qiladi | minor | medium |

Har bir topilma quyidagilarni o‘z ichiga oladi: muammo tavsifi, jiddiylik,
texnik izoh (qaysi qiymatlar, qaysi hujjatlardan), manba, tavsiya etilgan
tuzatish, holat.

Manba va ishonchlilik qoidalari:

- 1-sikldagi barcha topilmalar `source_type = rule`. Izohda taxmin
  yozilmaydi — faqat hujjatlardan o‘qilgan qiymatlar.
- Standartga havola faqat `standards` jadvalida mavjud va holati `active`
  bo‘lgan yozuvga beriladi. Aks holda manba sifatida "loyiha hujjatlari
  o‘rtasidagi ichki nomuvofiqlik" ko‘rsatiladi.
- Tizim hujjatlarni o‘zgartirmaydi. Tavsiya — faqat matn.

## 7. Xavfsizlik va xatolarni qayta ishlash

- Parollar argon2 bilan xeshlanadi. Birinchi ishga tushirishda admin
  yaratiladi.
- Ruxsatlar:

  | Harakat | viewer | engineer | lead | admin |
  |---|---|---|---|---|
  | Ko‘rish | ✓ | ✓ | ✓ | ✓ |
  | Hujjat yuklash, tekshiruvni boshlash | | ✓ | ✓ | ✓ |
  | Topilmani tasdiqlash / rad etish | | ✓ | ✓ | ✓ |
  | Qoidalarni yoqish / o‘chirish, loyihani o‘chirish | | | ✓ | ✓ |
  | Foydalanuvchilarni boshqarish | | | | ✓ |

- Audit jurnali faqat qo‘shiladi; har yozuv oldingi yozuv xeshini o‘z ichiga
  oladi. `verify()` zanjir buzilganini aniqlaydi.
- Baza shifrlash: SQLCipher, kalit OS kalit omborida. 1-siklda ishlab chiqish
  muhitida oddiy SQLite ishlatiladi; shifrlash sozlama orqali yoqiladi va
  3-siklda o‘rnatuvchi bilan birga majburiy bo‘ladi.
- Xizmat faqat `127.0.0.1` da tinglaydi.
- Xatolar: buzilgan fayl `parse_status = error` va sabab matnini oladi,
  boshqa hujjatlar davom etadi. Bitta qoidadagi xato seansni to‘xtatmaydi —
  seans natijasida "qoida bajarilmadi" yozuvi qoladi. API xatolari yagona
  shaklda qaytadi: `{code, message}`; xabar foydalanuvchi tilida.

## 8. Keyingi sikllar uchun tayyorgarlik

- `findings.source_type` va `review_runs.ai_mode` AI topilmalari uchun.
- `standards` jadvali bilimlar bazasi manbalari uchun asos.
- `tags` va `tag_params` sxema va 3D generatori uchun kirish ma'lumoti;
  DXF parser koordinatalarni saqlaydi.
- Interfeys matnlari boshidan uch tilli kalit-qiymat fayllarida.

## 9. Interfeys (1-sikl, minimal)

Sahifalar: kirish; loyihalar ro‘yxati; loyiha sahifasi (hujjatlar, yuklash,
"Tekshirish" tugmasi); topilmalar ro‘yxati (jiddiylik, holat, hujjat turi
bo‘yicha filtr); topilma kartasi (dalillar, hujjat sahifasiga havola,
tasdiqlash/rad etish); oddiy dashboard (hujjatlar soni, jiddiylik bo‘yicha
topilmalar, ochiq topilmalar — har biri bosilganda filtrlangan ro‘yxat
ochiladi). Til almashtirgich: uz/en/ru.

## 10. Testlar

- **Birlik testlari (pytest):** har parser, teg regexlari, sarlavha lug‘ati,
  birlik o‘girgich, har qoida (ijobiy va salbiy holat), audit zanjiri.
- **Namunaviy loyiha:** skript gazni qayta ishlash qurilmasi (amin bilan
  tozalash bloki) hujjatlarini yaratadi: P&ID (DXF), equipment list (XLSX),
  line list (XLSX), nasos va idish datasheetlari (PDF), material spec (DOCX).
  Ichiga ataylab kiritilgan xatolar:

  | # | Xato | Kutilgan qoida |
  |---|---|---|
  | 1 | V-101 loyiha bosimi: P&ID 16 barg, datasheet 10 barg | R001 |
  | 2 | P-101A quvvati: equipment list 45 kW, datasheet 55 kW | R001 |
  | 3 | E-102 P&ID da bor, equipment listda yo‘q | R002 |
  | 4 | 6"-AM-1004-A1A line listda bor, P&ID da yo‘q | R002 |
  | 5 | P-101B datasheetda material bo‘sh | R003 |
  | 6 | V-102 loyiha bosimi 5 barg, ish bosimi 7 barg | R004 |
  | 7 | Line list quvur sinfi B2C, material specda yo‘q | R005 |
  | 8 | Datasheet P&ID ning Rev A siga havola qiladi, joriy Rev C | R006 |
  | 9 | Bosim psi da, boshqa hujjatda barg da — qiymat aslida teng | Topilma bo‘lmasligi kerak |

- **Integratsion test:** namunaviy loyiha yuklanadi, tekshiruv ishlaydi;
  aynan 8 topilma kutiladi, 9-holat topilma bermasligi tekshiriladi.
- **API testlari:** har rol uchun ruxsatlar, buzilgan fayl, DWG rad etilishi,
  takror fayl, audit yozuvlari.
- **Interfeys (Playwright):** kirish → loyiha → yuklash → tekshiruv →
  topilmani ochish → tasdiqlash; til almashtirish uch tilda.

## 11. Ochiq savollar

Yo‘q. 2–5-sikllar bo‘yicha qarorlar o‘z spetsifikatsiyalarida qabul qilinadi.
