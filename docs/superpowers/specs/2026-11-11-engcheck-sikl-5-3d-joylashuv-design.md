# EngCheck 5-sikl: 3D joylashuv modeli va tahrirlash

Sana: 2026-11-11 · Qarorlar muallif tomonidan qabul qilingan.

## 1. Maqsad

Hujjatlardan ajratilgan uskunalar asosida qurilmaning soddalashtirilgan 3D joylashuv modelini yaratish,
ko‘rsatish va **muhandis tahrirlashiga** imkon berish. Bu loyiha 3D modeli (PDMS/E3D) o‘rnini bosmaydi —
hajmiy ko‘rinish va joylashuvni muhokama qilish vositasi.

## 2. Manbalar va ishonchlilik

Har uskuna uchun ikki narsa alohida belgilanadi: **joylashuv** va **o‘lcham**.

| Nima | Manba | Belgisi |
|---|---|---|
| Joylashuv | intizomi **civil** bo‘lgan DXF chizmadagi (bosh reja) uskuna bloki koordinatasi | `position_source = "document"` |
| Joylashuv, bosh reja bo‘lmasa yoki uskuna unda yo‘q | avtomatik panjara | `"assumed"` — shaffofroq, "taxminiy joylashuv" |
| O‘lcham | datasheet yoki uskunalar ro‘yxatidagi diametr, balandlik, uzunlik | `size_source = "document"` |
| O‘lcham, hujjatda yo‘q | uskuna turi bo‘yicha shartli o‘lcham | `"assumed"` — "shartli o‘lcham" |
| Muhandis o‘zgartirgan | tahrirlar qatlami | `"manual"` |

- **Chizma birligi:** DXF birligini ishonchli aniqlab bo‘lmaydi. Chizma o‘lchami 2000 birlikdan katta bo‘lsa
  millimetr, aks holda metr deb olinadi; bu **taxmin** va model sahifasida aniq yozib ko‘rsatiladi.
- **Balandlik belgisi (z):** hujjatlardan olinmaydi, hamma uskuna 0 da. Bu ham sahifada aytiladi.
- Shakl turi bo‘yicha: idish, kolonna, reaktor, rezervuar — tik silindr; issiqlik almashtirgich — yotiq
  silindr; nasos, kompressor, pech, boshqalar — quti.
- Quvurlar 3D da chizilmaydi (trassa ma'lumoti hujjatlarda yo‘q) — taxmin bilan to‘ldirilmaydi.

## 3. Ikki qatlam (sxemadagidek)

- Yaratilgan qatlam (`layouts.generated`) va tahrirlar qatlami (`layout_edits`): `move`, `rotate`, `resize`,
  `rename`, `add_item`, `remove_item`.
- Qayta yaratishda tahrirlar saqlanadi; qo‘llanmagan tahrirlar sanab ko‘rsatiladi.
- Orqaga / oldinga; har tahrir audit jurnalida; hujjatlar o‘zgarmaydi.
- "Hujjatlardan farqlar": qo‘shilgan, o‘chirilgan, nomi o‘zgargan, joyi yoki o‘lchami hujjatdagidan
  o‘zgartirilgan uskunalar (faqat manbasi hujjat bo‘lgan qiymat o‘zgarsa farq hisoblanadi).

## 4. Interfeys

- three.js sahnasi: zamin panjarasi, uskunalar, yozuvlar; aylantirish, yaqinlashtirish, surish.
- Uskunani tanlash (sahnada yoki ro‘yxatda) va zamin bo‘ylab sudrab ko‘chirish.
- **Ro‘yxat paneli:** har uskuna uchun X, Y, burilish va o‘lchamlarni son bilan kiritish — sichqonchasiz,
  klaviatura bilan ham tahrirlash mumkin.
- Shartli belgilar: hujjatdan / taxminiy / qo‘lda; birlik va balandlik haqidagi izohlar.
- WebGL bo‘lmasa: ro‘yxat paneli ishlayveradi va sababi ko‘rsatiladi.

## 5. Ruxsatlar

Ko‘rish — hamma; yaratish va tahrirlash — muhandis va yuqori.

## 6. Testlar

Generator (bosh rejadan joylashuv, birlik taxmini, panjara, hujjatdagi va shartli o‘lchamlar, eskirgan
reviziyalar), tahrirlar (tekshirish, qo‘llash, undo/redo, qayta yaratishda saqlanish, farqlar), API
ruxsatlari; brauzerda: yaratish → ro‘yxat panelida ko‘chirish va burish → uskuna qo‘shish → orqaga →
qayta yuklashda saqlanishi; sahna chizilgani.
