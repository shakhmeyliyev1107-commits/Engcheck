# EngCheck 4-sikl: prinsipial sxema — generator va tahrirlagich

Sana: 2026-11-11 · Qarorlar muallif tomonidan qabul qilingan.

## 1. Maqsad

Loyiha hujjatlaridan ajratilgan uskunalar va quvurlar asosida umumiy prinsipial (blok) sxema yaratish,
uni interfeysda ko‘rsatish va **muhandis tahrirlashiga** imkon berish. Bu P&ID o‘rnini bosmaydi — umumiy
ko‘rinish va tekshiruv vositasi.

## 2. Ma'lumot manbalari va ishonchlilik

| Element | Manba | Belgilanishi |
|---|---|---|
| Uskuna tuguni | faol hujjatlardagi uskuna teglari (jadval katagi yoki blok atributi) | uzluksiz chiziq |
| Quvur (qirra) | quvurlar ro‘yxatidagi **Qayerdan / Qayerga** ustunlari | uzluksiz chiziq, "hujjatdan" |
| Quvur (qirra), ustunlar bo‘lmasa | P&ID (DXF) da quvur yozuviga eng yaqin ikki uskuna bloki | **uzuq chiziq, "taxminiy"** |
| Ulanmagan quvurlar | uchi aniqlanmagan quvurlar | sxema ostida ro‘yxat |
| Muhandis qo‘shgan/o‘zgartirgan | tahrirlar qatlami | alohida rang, "qo‘lda" |

Taxminiy ulanish hech qachon hujjatdan olingandek ko‘rsatilmaydi. Uskuna turi (idish, nasos,
issiqlik almashtirgich, kolonna, kompressor, rezervuar) teg prefiksidan olinadi; tanilmasa — umumiy blok.
Quvur uchi teg bo‘lmasa (masalan "B.L.", "Drain"), chegara tuguni yaratiladi.

## 3. Ikki qatlam

- **Yaratilgan qatlam** (`diagrams.generated`): generator natijasi; "Qayta yaratish" uni to‘liq yangilaydi.
- **Tahrirlar qatlami** (`diagram_edits`): tartiblangan amallar — `move`, `add_node`, `remove_node`,
  `rename_node`, `add_edge`, `remove_edge`. Ko‘rsatiladigan sxema = yaratilgan qatlam + bekor
  qilinmagan tahrirlar.
- Qayta yaratishda tahrirlar saqlanadi. Yo‘qolgan elementga tegishli tahrir qo‘llanmaydi va
  "qo‘llanmagan tahrirlar" sifatida sanab ko‘rsatiladi (jim tashlanmaydi).
- **Orqaga / oldinga** (undo/redo): oxirgi tahrir bekor qilinadi yoki qaytariladi. Yangi tahrir
  kiritilsa, oldinga qaytarish imkoni yopiladi.
- Har tahrir, bekor qilish va qayta yaratish audit jurnaliga yoziladi.
- Tahrir faqat sxemaga ta'sir qiladi; yuklangan hujjatlar o‘zgarmaydi.

## 4. Hujjatlardan farqlar

Sxema sahifasida "Hujjatlardan farqlar" ro‘yxati: qo‘lda qo‘shilgan uskuna (hujjatlarda yo‘q), o‘chirilgan
hujjatdagi uskuna, qo‘lda qo‘shilgan yoki o‘chirilgan ulanish, nomi o‘zgartirilgan uskuna. Bu ro‘yxat
tekshiruv topilmalari jadvaliga qo‘shilmaydi (topilmalar hujjatlar haqida; bu esa sxema tahriri haqida),
lekin dashboardda soni ko‘rsatiladi.

Hujjatlar o‘zgarsa (yangi yuklash, o‘chirish), sxema "eskirgan" deb belgilanadi va qayta yaratish taklif qilinadi.

## 5. Joylashtirish

Avtomatik: oqim bo‘yicha chapdan o‘ngga qatlamlar (qirralar yo‘nalishi bo‘yicha), sikl bo‘lsa —
uzilib, panjaraga. Natija bir xil kirish uchun har doim bir xil. Muhandis ko‘chirgan tugun o‘rni
tahrir sifatida saqlanadi.

## 6. Ruxsatlar

Ko‘rish — hamma; yaratish va tahrirlash — muhandis va yuqori. Eksport: SVG (hamma).

## 7. Testlar

Generator (manbalar, taxminiy belgi, chegara tugunlari, ulanmagan quvurlar), joylashtirish
barqarorligi, tahrirlarni qo‘llash, undo/redo, qayta yaratishda tahrirlar saqlanishi va
qo‘llanmagan tahrirlar, farqlar ro‘yxati, eskirish belgisi, API ruxsatlari, SVG eksport;
brauzerda: yaratish → tugunni sudrash → uskuna qo‘shish → ulash → orqaga → qayta yuklashda saqlanishi.
