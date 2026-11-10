# EngCheck 2-sikl: AI provayder qatlami va bilimlar bazasi

Sana: 2026-11-10 · Holat: foydalanuvchi "o‘zing to‘g‘ri deb bilganday davom et"
degani asosida qarorlar muallif tomonidan qabul qilingan va shu yerda yozilgan.

## 1. Maqsad

1-sikl deterministik qoidalar bilan ishlaydi. 2-sikl ularning ustiga:

1. istalgan AI provayderini API kaliti bilan ulash, almashtirish va sozlash;
2. onlayn (bulutli) va oflayn (lokal model) rejimlar, avtomatik zaxiraga o‘tish;
3. bilimlar bazasi: standartlar, adabiyotlar va yozma eslatmalarni qo‘shish,
   indekslash va qidirish (RAG);
4. topilmaga manbali AI izoh va hujjatlardan AI topilmalari — doim
   "tasdiqlanmagan" belgisi bilan;
5. muhandis tasdiqlagan natijalardan bilimlar bazasini nazorat ostida boyitish.

Kirmaydi: desktop o‘rnatuvchi (3-sikl), sxema va 3D (4–5-sikllar), OCR.

## 2. Tamoyillar (cheklovlardan)

- AI natijasi hech qachon fakt sifatida ko‘rsatilmaydi: `source_type = "ai"`,
  ishonchlilik `low`, interfeysda "AI taxmini — muhandis tasdiqlamagan".
- AI hujjatni o‘zgartirmaydi va topilmani tasdiqlamaydi.
- AI izohidagi har havola bilimlar bazasidan berilgan parchaga ishora qilishi
  shart; berilmagan manbaga havola tashlab yuboriladi.
- AI topilmasi hujjatdan so‘zma-so‘z iqtibos keltirishi shart; iqtibos hujjat
  matnida topilmasa, topilma qabul qilinmaydi.
- Standart holati hisobga olinadi: `withdrawn` qidiruvga kirmaydi,
  `superseded` "almashtirilgan nashr" belgisi bilan chiqadi.
- Litsenziyali manba: API to‘liq matnni qaytarmaydi (iqtibos ≤ 300 belgi),
  fayli yuklab olinmaydi, **bulutli** provayderga matni yuborilmaydi (faqat
  nomi, nashri va sahifasi). Lokal provayderga yuboriladi.
- Bulutli AI loyiha uchun standart holatda **o‘chiq** (`allow_cloud_ai = false`).

## 3. AI provayder qatlami

| Tur | Aloqa | Izoh |
|---|---|---|
| `anthropic` | rasmiy `anthropic` Python SDK | standart model `claude-opus-5-5`, adaptiv fikrlash, rad etish (`refusal`) holati qayta ishlanadi, server tomonidagi zaxira (`fallbacks="default"`) yoqilgan |
| `openai_compatible` | HTTP (`/chat/completions`, `/embeddings`) | OpenAI, OpenRouter, vLLM, LM Studio va shu protokoldagi boshqa xizmatlar |
| `ollama` | HTTP (`/api/chat`, `/api/embed`) | lokal modellar |

Yagona interfeys: `chat(system, user, max_tokens) -> ChatResult`,
`embed(texts) -> vektorlar`, `ping()`. Xatolar yagona `AiError(code)`:
`auth`, `rate_limit`, `unreachable`, `bad_request`, `refused`, `server`,
`embeddings_unsupported`.

**Lokal yoki bulutli** — foydalanuvchi belgilamaydi, manzildan aniqlanadi:
`localhost`, loopback yoki xususiy tarmoq IP si → lokal; qolgani bulutli.

**Rejimni tanlash** (`resolve`): yoqilgan provayderlar standart provayderdan
boshlab ko‘riladi; bulutli provayder loyiha ruxsat bermasa yoki javob bermasa
o‘tkazib yuboriladi; birinchi yaroqlisi tanlanadi. Natija: `online`, `local`
yoki `none` va sababi. `none` bo‘lsa faqat qoidalar ishlaydi va bu
interfeysda ko‘rsatiladi.

**Kalitlar:** `keyring` kutubxonasi va OS kalit ombori mavjud bo‘lsa — o‘sha
yerda. Aks holda `secrets.enc` (Fernet) + alohida `secret.key` (ruxsat 0600).
Kalit bazaga, jurnalga, audit yozuviga va API javobiga tushmaydi; API faqat
`has_key` ni qaytaradi.

## 4. Bilimlar bazasi

- `kb_sources`: title, kind (`standard`, `literature`, `note`, `lesson`),
  standard_code, edition, status (`active`, `superseded`, `withdrawn`),
  license_type (`licensed`, `open`, `internal`), fayl, approved,
  origin_finding_id, added_by, approved_by.
- `kb_chunks`: source_id, ordinal, page_no, text, embedding, embed_model.
- Qabul: PDF, DOCX, XLSX, TXT, MD yoki to‘g‘ridan-to‘g‘ri matn. Bo‘laklash:
  taxminan 900 belgi, 150 belgi ustma-ust.
- Qidiruv: BM25 (lokal, bog‘liqliksiz — oflayn ishlaydi). Provayder
  embedding bersa, gibrid: BM25 va kosinus reytinglari RRF bilan qo‘shiladi.
- Faqat `approved = true` manbalar qidiruvda qatnashadi. Muhandis qo‘shgan
  manba tasdiqlanmagan; yetakchi muhandis yoki administrator qo‘shgani —
  darhol tasdiqlangan.

## 5. AI funksiyalari

**AI izoh (topilmaga).** Topilma faktlari + bilimlar bazasidan 5 tagacha
parcha modelga beriladi. Model JSON qaytaradi: `explanation`,
`citations` (`K1`…), `assumptions`. Natija `finding_ai_notes` ga `proposed`
holatida yoziladi; muhandis qabul qiladi yoki rad etadi.

**AI tekshiruv (hujjatlarga).** `POST /reviews {use_ai: true}`. Har hujjat
sahifasi matni modelga beriladi; model `[{quote, issue, recommendation,
severity}]` qaytaradi. Iqtibosi sahifa matnida topilmagan element tashlanadi.
Qolganlari `AI01` qoidasi ostida, `source_type = "ai"`, ishonchlilik `low`.

**Nazoratli o‘rganish.** Tasdiqlangan, rad etilgan yoki tuzatilgan topilmadan
muhandis "dars" taklif qiladi → `kb_sources.kind = "lesson"`,
`approved = false`. Yetakchi muhandis tasdiqlagach qidiruvga kiradi.

## 6. Ruxsatlar

| Harakat | viewer | engineer | lead | admin |
|---|---|---|---|---|
| Bilimlar bazasida qidirish | ✓ | ✓ | ✓ | ✓ |
| Manba qo‘shish (tasdiqlanmagan), AI izoh so‘rash, dars taklif qilish | | ✓ | ✓ | ✓ |
| Manbani tasdiqlash, holatini o‘zgartirish, o‘chirish; loyihada bulutli AI ga ruxsat | | | ✓ | ✓ |
| AI provayderlari va kalitlar | | | | ✓ |

## 7. Mavjud bazalar

1-sikl bazasi bor foydalanuvchilar uchun: ishga tushishda yetishmayotgan
ustunlar `ALTER TABLE … ADD COLUMN` bilan qo‘shiladi (ma'lumot yo‘qolmaydi).

## 8. Testlar

- Har provayder: so‘rov shakli va xatolarni soxta transport orqali.
- Rejim tanlash: bulut taqiqlangan, provayder o‘chgan, hech biri yo‘q.
- Kalit: bazada, auditda va API javobida yo‘qligi.
- Bilimlar bazasi: bo‘laklash, BM25, gibrid, holat va litsenziya qoidalari.
- AI izoh va AI tekshiruv: soxta provayder bilan — noto‘g‘ri havola va
  uydirma iqtibos tashlanishi.
- Interfeys (Playwright): lokal soxta OpenAI-mos server bilan provayder
  qo‘shish, sinash, almashtirish; manba yuklash va qidirish; AI izoh; oflayn
  zaxira.
