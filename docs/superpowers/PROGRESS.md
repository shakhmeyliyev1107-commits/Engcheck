# EngCheck — ish holati (avtomatik davom etish uchun)

Foydalanuvchi ko'rsatmasi (2026-11-10): "o'zing to'g'ri deb bilganday tartib bilan davom etaver";
"limit yangilansa, men aytmasam ham avtomatik davom et". Tasdiq so'rab to'xtamaslik kerak.

## Ish tartibi (har sikl)
1. Spetsifikatsiya → `docs/superpowers/specs/`, reja → `docs/superpowers/plans/` (qisqa, qarorlar yozilgan).
2. Har vazifa: avval yiqiladigan test → kod → `cd backend && python -m pytest -q` → commit.
3. Interfeys: `cd frontend && npx vitest run && npx playwright test --trace off`.
4. Yakunda bitta mustaqil tekshiruvchi (subagent) → Critical/Important tuzatiladi (test bilan) → `main` ga `--no-ff` merge.
5. README yangilanadi. Barcha hujjat va izohlar o'zbek tilida.

## Sikllar
| # | Mazmun | Holat |
|---|---|---|
| 1 | Yadro va tekshiruv dvigateli | `main` da |
| 2 | AI provayderlari, bilimlar bazasi (RAG) | `feat/sikl-2`: kod tayyor, yakuniy ko'rik kutilmoqda |
| 3 | Desktop qobiq (Electron), baza shifrlash, loyiha paketini eksport/import | boshlanmagan |
| 4 | Prinsipial sxema generatori **va tahrirlagichi** | boshlanmagan |
| 5 | 3D joylashuv modeli **va tahrirlash** | boshlanmagan |

## Hozirgi qadam
2-sikl ko'rigi: tekshiruvchi natijasini kutish → tuzatish → merge → 3-sikl.
Tekshiruvchi javob bermasa: `git diff main..feat/sikl-2` ni o'zim ko'rib chiqib (xavfsizlik: kalit sizishi,
bulut roziligi, litsenziyali matn, AI natijasi fakt bo'lib ko'rinmasligi), keyin davom etaman.

## 1-sikldan qolgan mayda kamchiliklar
- Hujjat o'chirilgach, eski tekshiruv topilmalari dalilsiz ko'rinadi.
- Teg namunalari kodda qotirilgan (sozlanadigan bo'lishi kerak).
- 405 javobiga "internal_error" kodi.
- Harf bilan tugaydigan hujjat raqamiga havola aniqlanmaydi (`GP-DS-V101 Rev A`).
