# EngCheck 3-sikl: desktop qobiq, baza shifrlash, loyiha paketi

Sana: 2026-11-10 · Qarorlar muallif tomonidan qabul qilingan (foydalanuvchi: "o‘zing to‘g‘ri deb bilganday davom et").

## 1. Maqsad

1. **Desktop qobiq (Electron):** ilova oynada ochiladi; qobiq Python xizmatini o‘zi ishga tushiradi va yopadi.
2. **Baza shifrlash (SQLCipher):** `engcheck.db` diskda shifrlangan holda saqlanadi.
3. **Loyiha paketi:** loyihani hamkasbga bitta fayl sifatida berish va qabul qilish.
4. **Lokal xizmat himoyasi:** tasodifiy port, faqat `127.0.0.1`, begona `Host` sarlavhali so‘rovlar rad etiladi.

Kirmaydi: yuklangan asl fayllarni diskda shifrlash (4-bo‘lim), avtomatik yangilanish, kod imzolash.

## 2. Desktop qobiq

- `desktop/` — Electron. `src/backend.js` (Electron'ga bog‘liq emas, alohida testlanadi): bo‘sh portni
  tanlaydi, `python -m engcheck --port N --data-dir D` ni ishga tushiradi, `/api/setup` javob berguncha
  kutadi (30 s), chiqishda jarayonni to‘xtatadi. `src/main.js`: oynani `http://127.0.0.1:N` da ochadi;
  `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`; tashqi havolalar tizim brauzerida
  ochiladi; boshqa manzilga navigatsiya taqiqlanadi.
- Xizmat ishga tushmasa — sababi ko‘rsatilgan xato oynasi (jim osilib qolmaydi).
- Ma'lumotlar papkasi: Electron `userData`.
- Yig‘ish: `electron-builder` sozlamasi; Python xizmati `extraResources` sifatida (PyInstaller bilan
  yig‘ilgan `engcheck-server`). Yig‘ish buyruqlari README da; o‘rnatuvchi foydalanuvchi kompyuterida quriladi.
- Xizmat CLI: `--port` (0 = bo‘sh port), `--data-dir`; ishga tushgach stdout ga bitta JSON satr:
  `{"event": "ready", "port": N}`.

## 3. Baza shifrlash

- `sqlcipher3` o‘rnatilgan bo‘lsa (`pip install -e "backend[encryption]"`) va `ENGCHECK_ENCRYPT` `0` bo‘lmasa,
  yangi baza shifrlangan holda yaratiladi. Kalit (32 bayt, tasodifiy) `SecretStore` da `db_key` nomi bilan.
- Mavjud ochiq baza: `python -m engcheck encrypt-db` — shifrlangan nusxa yaratadi, tekshiradi, asl faylni
  `engcheck.db.plain.bak` ga ko‘chiradi (o‘chirmaydi: foydalanuvchi tekshirib, o‘zi o‘chiradi).
- Ochiq baza topilsa va shifrlash yoqilgan bo‘lsa, ilova ishlayveradi (ochiq rejimda) va holatni
  `/api/system` da ko‘rsatadi: `{"db_encrypted": bool, "secret_backend": "keyring"|"file", ...}`.
- Halol cheklov: kalit ombori fayl varianti bo‘lsa, kalit baza yonida turadi — bu baza faylining
  alohida nusxasi/zaxirasi tarqalishidan himoya qiladi, butun papkani olgan odamdan emas. To‘liq himoya
  uchun OS kalit ombori (`backend[keyring]`) kerak. Interfeys buni Boshqaruv sahifasida ko‘rsatadi.

## 4. Yuklangan fayllar

Asl hujjatlar va bilimlar bazasi fayllari diskda shifrlanmaydi (bu siklda). Sabab: parserlar fayl yo‘li bilan
ishlaydi, shifrlash vaqtinchalik ochiq nusxalarni talab qiladi — alohida, puxta ish. README da disk shifrlash
tavsiyasi qoladi; `/api/system` `files_encrypted: false` ni qaytaradi.

## 5. Loyiha paketi (`.engpkg`)

- ZIP: `manifest.json` (format versiyasi, loyiha, hujjatlar metama'lumoti va SHA-256, topilma qarorlari) +
  `files/<sha256><kengaytma>` (asl hujjatlar, o‘zgarmagan).
- **Parol ixtiyoriy.** Parol berilsa, butun ZIP scrypt + Fernet bilan shifrlanadi — maxfiylik va parolni
  bilmagan odam o‘zgartira olmasligi ta'minlanadi. Parolsiz paketda faqat butunlik tekshiruvi (SHA-256) bor:
  shikastlanishni aniqlaydi, ataylab o‘zgartirishdan himoya qilmaydi. Interfeys shuni aytadi.
- Paketga **kirmaydi:** API kalitlari, AI provayderlari, foydalanuvchilar va parollar, audit jurnali,
  bilimlar bazasi (jumladan litsenziyali manbalar va darslar), AI izohlari va AI topilmalari.
- **Import:** yangi loyiha yaratiladi; hujjatlar asl fayllardan qayta tahlil qilinadi; qoidalar ishga
  tushiriladi; paketdagi qarorlar (tasdiqlangan / rad etilgan / tuzatilgan, izoh va muallif logini bilan)
  topilma barmoq izi (fingerprint) bo‘yicha tiklanadi. Mos topilma topilmagan qarorlar soni hisobotda.
  `allow_cloud_ai` import qilinmaydi (har doim `false`).
- Xavfsizlik: fayl nomlari faqat manifestdan olinadi (yo‘l qismlarisiz), SHA-256 mos kelmasa import to‘xtaydi;
  ochilgan hajm 2 GB, fayllar soni 2000 bilan cheklanadi; noto‘g‘ri parol va buzilgan paket aniq xabar beradi.
- Ruxsat: eksport — yetakchi muhandis va administrator (ma'lumot tizimdan chiqadi); import — muhandis va yuqori.
  Ikkalasi auditga yoziladi.

## 6. Lokal xizmat himoyasi

`Host` sarlavhasi `127.0.0.1`, `localhost` yoki `[::1]` (istalgan port) bo‘lmagan so‘rovga 400. Bu DNS
rebinding orqali brauzerdagi begona sahifa lokal xizmatga murojaat qilishining oldini oladi.

## 7. Testlar

- Host tekshiruvi; CLI `--port 0` va `ready` satri (haqiqiy jarayon bilan).
- Shifrlash: yangi baza shifrlangan (faylda SQLite sarlavhasi va ma'lum matn yo‘q), kalitsiz ochilmaydi,
  `encrypt-db` ma'lumotni saqlaydi, `sqlcipher3` yo‘q bo‘lsa ochiq rejim va aniq holat.
- Paket: aylanma sayohat (eksport → boshqa bazaga import → bir xil topilmalar va qarorlar), parolli/parolsiz,
  noto‘g‘ri parol, buzilgan fayl, SHA mos kelmasligi, yo‘l hujumi (`../`), zip-bomba chegarasi, istisno
  qilingan ma'lumotlar paketda yo‘qligi.
- Qobiq: `backend.js` — node:test bilan haqiqiy Python xizmatini ishga tushirish/to‘xtatish, band port,
  ishga tushmaydigan buyruq. Muhit imkon bersa, Electron oynasi `xvfb` ostida tutun testi.
- Interfeys (Playwright): eksport → import → topilmalar va qaror tiklanganini ko‘rish; tizim holati.
