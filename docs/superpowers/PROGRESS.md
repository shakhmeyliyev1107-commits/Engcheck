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
| 4 | Prinsipial sxema generatori **va tahrirlagichi** | `main` da (ko'rikdan o'tgan, tuzatilgan) |
| 5 | 3D joylashuv modeli **va tahrirlash** | boshlanmagan |

## Hozirgi qadam
5-siklni boshlash: `feat/sikl-5` shoxi. 3D joylashuv modeli va tahrirlash.
Reja: uskunalar (sxemadagi tugunlar) + civil ma'lumoti (DXF koordinatalari bo'lsa — joylashuv; bo'lmasa — avtomatik panjara,
"taxminiy joylashuv" belgisi bilan). O'lchamlar: datasheetdagi diametr/uzunlik bo'lsa — hujjatdan, aks holda turi bo'yicha shartli
o'lcham ("shartli" deb belgilanadi). three.js sahnasi; tahrirlar qatlami sxemadagidek (`backend/engcheck/diagram/edits.py` namunasi:
move/rotate/resize/add/remove, undo/redo, qayta yaratishda saqlanadi, audit). Testlarni QISMLAB yuritish kerak
(to'liq `pytest` bitta buyruqda ba'zan to'xtatiladi): `tests/core tests/review tests/kb tests/ai`, `tests/api`, `tests/package tests/test_cycle3_core.py`, `tests/diagram tests/ingest`.

## 4-sikldan qolgan
- Sxema `stale` belgisi faqat faol hujjatlar to'plami o'zgarsa yonadi (hujjat turi o'zgarsa — yo'q).
- Qo'llanmagan (orphan) tahrirlar faqat son sifatida ko'rsatiladi; alohida o'chirib bo'lmaydi.
- Sxemani klaviatura bilan tahrirlab bo'lmaydi (faqat sichqoncha/sensor).
- Ketma-ket tez tahrirlarda javoblar tartibi nazorat qilinmaydi.
- Sxema loyiha paketiga kirmaydi (import qilgan tomonda qayta yaratiladi, tahrirlar ko'chmaydi).

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
