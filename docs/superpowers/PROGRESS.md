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
| 3 | Desktop qobiq (Electron), baza shifrlash, loyiha paketini eksport/import | `main` da (ko'rikdan o'tgan, tuzatilgan) |
| 4 | Prinsipial sxema generatori **va tahrirlagichi** | `feat/sikl-4` (GitHub'da): kod tayyor, yakuniy ko'rik kutilmoqda |
| 5 | 3D joylashuv modeli **va tahrirlash** | boshlanmagan |

## Hozirgi qadam
4-sikl ko'rigi: tekshiruvchi natijasini kutish → Critical/Important ni test bilan tuzatish →
`main` ga `--no-ff` merge → `git push origin main` → 5-sikl (3D joylashuv modeli va tahrirlash:
uskunalar va civil ma'lumotidan three.js sahnasi; tahrirlar qatlami sxemadagidek — `backend/engcheck/diagram/edits.py` namunasi).
Tekshiruvchi javob bermasa: `git diff main..feat/sikl-4` ni o'zim ko'rib chiqaman (tahrir amallarini tekshirish,
SVG eksportda XSS, ruxsatlar, undo/redo tartibi, generatorning taxminiy ulanishlari to'g'ri belgilanishi).

## 3-sikldan qolgan
- O'rnatuvchini yig'ish (PyInstaller + electron-builder) sinalmagan; kod imzolash yo'q.
- Yuklangan asl fayllar diskda shifrlanmaydi.
- Shifrlangan paket importi butun faylni xotiraga oladi (1 GiB gacha).
- `encrypt-db` ilova ishlab turganda bajarilsa, ilova yozishda xato beradi (README: avval to'xtating).
- ~/.engcheck dagi eski ma'lumot desktop ilovaning userData papkasiga avtomatik ko'chmaydi.
- Paket parolining eng kichik uzunligi talab qilinmaydi.

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
