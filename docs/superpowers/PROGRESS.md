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
| 4 | Prinsipial sxema generatori **va tahrirlagichi** | boshlanmagan |
| 5 | 3D joylashuv modeli **va tahrirlash** | boshlanmagan |

## Hozirgi qadam
4-siklni boshlash: `feat/sikl-4` shoxi. Prinsipial sxema generatori va tahrirlagichi.
Talab: `specs/2026-11-10-engcheck-yadro-va-tekshiruv-design.md`, "4- va 5-sikllar uchun qo'shimcha talab"
(generator natijasi va muhandis tahriri alohida qatlamlarda; tahrir qayta yaratishda yo'qolmaydi; audit;
orqaga qaytarish; asl hujjatlar o'zgarmaydi; tahrir va hujjatlar farqi topilma sifatida).
Kirish ma'lumoti: `tags` (uskuna, quvur), `tag_params`, DXF koordinatalari (`tag_occurrences.location`).
Chiqish: SVG blok-sxema (uskunalar tugun, quvurlar qirra); interfeysda sudrab ko'chirish, qo'shish, o'chirish, ulash.

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
