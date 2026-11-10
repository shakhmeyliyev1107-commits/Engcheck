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
| 2 | AI provayderlari, bilimlar bazasi (RAG) | `main` da (ko'rikdan o'tgan, tuzatilgan) |
| 3 | Desktop qobiq (Electron), baza shifrlash, loyiha paketini eksport/import | boshlanmagan |
| 4 | Prinsipial sxema generatori **va tahrirlagichi** | boshlanmagan |
| 5 | 3D joylashuv modeli **va tahrirlash** | boshlanmagan |

## Hozirgi qadam
3-siklni boshlash: `feat/sikl-3` shoxi, spetsifikatsiya → reja → kod.
Doira: Electron qobiq (yupqa: Python xizmatini ishga tushiradi, tasodifiy port, oynani ochadi),
baza shifrlash (SQLCipher mavjud bo'lsa; bo'lmasa aniq ogohlantirish), loyiha paketini
eksport/import (imzolangan zip; litsenziyali bilimlar bazasi manbalari va API kalitlari paketga kirmaydi).
GitHub: foydalanuvchi repozitoriy ulashni va'da qilgan; nomini yozsa — add_repo, push (main va shoxlar).

## 2-sikldan qolgan mayda kamchiliklar
- Har so'rovda provayder obyekti qayta quriladi va yopilmaydi; `ai-status` har safar ping qiladi (kesh kerak).
- AI izohidan noma'lum [Kn] olib tashlanganda gap qoldig'i qolishi mumkin.
- Lokal modelga berilgan litsenziyali matnni model izohda so'zma-so'z takrorlashi mumkin (uzunlik cheklanmagan).
- Provayderlar haqiqiy xizmatlarga ulanib sinalmagan (faqat soxta transport/server).

## 1-sikldan qolgan mayda kamchiliklar
- Hujjat o'chirilgach, eski tekshiruv topilmalari dalilsiz ko'rinadi.
- Teg namunalari kodda qotirilgan (sozlanadigan bo'lishi kerak).
- 405 javobiga "internal_error" kodi.
- Harf bilan tugaydigan hujjat raqamiga havola aniqlanmaydi (`GP-DS-V101 Rev A`).
