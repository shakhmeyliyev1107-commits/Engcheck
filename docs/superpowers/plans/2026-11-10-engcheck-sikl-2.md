# EngCheck 2-sikl: AI va bilimlar bazasi — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-11-10-engcheck-sikl-2-ai-va-bilimlar-bazasi-design.md`
**Tech:** 1-sikl steki + `anthropic` (rasmiy SDK), `numpy`, ixtiyoriy `keyring`.

Har vazifa: avval yiqiladigan test → kod → to‘liq `python -m pytest -q` → commit.

| # | Vazifa | Fayllar | Asosiy interfeys |
|---|---|---|---|
| 1 | Modellar va ustun qo‘shish | `core/models.py`, `core/db.py` | `AiProvider, KbSource, KbChunk, FindingAiNote`; `Project.allow_cloud_ai`; `ReviewRun.ai_provider/ai_note`; `add_missing_columns(engine)` |
| 2 | Kalitlar ombori | `core/secrets.py` | `SecretStore(data_dir).set/get/delete(name)`, `.backend` |
| 3 | Provayderlar | `ai/base.py`, `ai/anthropic_provider.py`, `ai/openai_compat.py`, `ai/ollama.py` | `Provider.chat/embed/ping`, `ChatResult`, `AiError`, `is_local_url(url)` |
| 4 | Reyestr va rejim tanlash | `ai/registry.py` | `build(row, key)`, `resolve(db, settings, project) -> Resolution(provider, mode, reason)` |
| 5 | Bilimlar bazasi | `kb/chunking.py`, `kb/index.py`, `kb/service.py` | `chunk_pages`, `bm25_rank`, `add_source`, `search(db, query, k, provider, for_cloud) -> list[Hit]`, `reindex` |
| 6 | AI izoh | `ai/assist.py` | `explain_finding(db, settings, finding, user, locale) -> FindingAiNote` |
| 7 | AI tekshiruv | `ai/review.py`, `review/engine.py` | `ai_findings(db, project_id, provider, locale) -> list[Draft]`; `run_review(..., use_ai=False, settings=None, locale="uz")` |
| 8 | Nazoratli o‘rganish | `kb/service.py` | `propose_lesson(db, finding, user, text) -> KbSource` |
| 9 | API | `api/routes_ai.py`, `api/routes_kb.py`, mavjud marshrutlar | spetsifikatsiya 3–6-bo‘limlar |
| 10 | Interfeys | `pages/Kb.tsx`, `pages/Admin.tsx`, `pages/Project.tsx`, `pages/FindingDetail.tsx`, i18n | — |
| 11 | README va yakuniy tekshiruv | `README.md` | — |

## Review Focus

1. Provayder javobi JSON emas yoki ```json bilan o‘ralgan → ajratib olinadi yoki xato aniq ko‘rsatiladi, 500 emas.
2. Provayder tekshiruv o‘rtasida o‘chadi → qoida topilmalari saqlanadi, seansda sabab yoziladi.
3. Kalit noto‘g‘ri (401) → foydalanuvchi "kalit noto‘g‘ri" xabarini ko‘radi; kalit matni xabarda yo‘q.
4. Litsenziyali standart bulutli provayder tanlanganda → matn so‘rovda yo‘q.
5. Juda katta hujjat → so‘rov hajmi chegaralanadi, hujjat qismlari jim tashlanmaydi (qancha sahifa ko‘rilgani yoziladi).
