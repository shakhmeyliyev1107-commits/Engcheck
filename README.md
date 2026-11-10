# EngCheck — muhandislik hujjatlarini tekshirish platformasi

Sanoat korxonalari (GTL, MTO, neft va gazni qayta ishlash, suv va oqova suv
tozalash) loyiha hujjatlarini FEED, Detail Design va As-Built bosqichlarida
tekshiradi: hujjatlardan teg va parametrlarni ajratadi, ularni o‘zaro
solishtiradi va nomuvofiqliklarni manbasi bilan ko‘rsatadi.

**Bu 1-sikl:** yadro va deterministik tekshiruv dvigateli. AI, bilimlar bazasi
(RAG), sxema va 3D model keyingi sikllarda — pastdagi "Hali yo‘q" bo‘limiga
qarang.

## Talablar

- Python 3.11 yoki yangiroq
- Node.js 20 yoki yangiroq (faqat interfeysni qurish uchun)

## O‘rnatish

```bash
pip install -e "backend[dev]"
```

```bash
cd frontend && npm install && npm run build && cd ..
```

## Ishga tushirish

```bash
cd backend && python -m engcheck
```

Brauzerda `http://127.0.0.1:8765` ni oching. Birinchi ochilishda administrator
hisobini yaratasiz.

Xizmat faqat shu kompyuterdan (`127.0.0.1`) ochiladi. Sozlamalar:

| O‘zgaruvchi | Vazifasi | Standart |
|---|---|---|
| `ENGCHECK_DATA_DIR` | Baza va yuklangan fayllar papkasi | `~/.engcheck` |
| `ENGCHECK_PORT` | Port | `8765` |

## Namunaviy loyihada sinab ko‘rish

Namunaviy hujjatlar — amin bilan gaz tozalash bloki; ichiga ataylab 8 ta xato
kiritilgan.

```bash
python samples/generate_sample_project.py sample_project
```

1. **Loyihalar** sahifasida loyiha yarating (soha: Gazni qayta ishlash).
2. **Hujjat yuklash** → `sample_project` papkasidagi 6 ta faylni tanlang.
   Hujjat turi, raqami va reviziyasi fayl nomidan taklif qilinadi — tekshirib,
   **Yuklash** ni bosing.
3. **Tekshirish** ni bosing. 8 ta topilma chiqadi:

| Qoida | Topilma |
|---|---|
| R001 | V-101 loyiha bosimi: P&ID va uskunalar ro‘yxatida 16 barg, datasheetda 14 barg |
| R001 | P-101A quvvati: ro‘yxatda 45 kW, datasheetda 55 kW |
| R002 | E-102 P&ID da bor, uskunalar ro‘yxatida yo‘q |
| R002 | 6"-AM-1004-A1A quvurlar ro‘yxatida bor, P&ID da yo‘q |
| R003 | P-101B datasheetida material ko‘rsatilmagan |
| R004 | V-102 loyiha bosimi (5 barg) ish bosimidan (7 barg) past |
| R005 | B2C quvur sinfi material spetsifikatsiyasida yo‘q |
| R006 | V-101 datasheeti P&ID ning eskirgan Rev A siga havola qiladi (joriy Rev C) |

   V-101 ish bosimi bir hujjatda 12 barg, boshqasida 174 psig — bu teng qiymat,
   shuning uchun topilma chiqmaydi.

4. Topilmani oching: tavsif, jiddiylik, texnik izoh, manba, ishonchlilik,
   tavsiya va dalillar ko‘rinadi. **Hujjatni ochish** dalil joylashgan sahifaga
   olib boradi.
5. Topilmani **Tasdiqlash** yoki izoh bilan **Rad etish** mumkin. Tekshiruv
   qayta ishga tushirilganda qaror saqlanib qoladi.

## Foydalanish

### Hujjat formatlari

| Format | Nima o‘qiladi | Cheklov |
|---|---|---|
| PDF | Matn va jadvallar | Skanerlangan PDF "OCR kerak" deb belgilanadi, tahlil qilinmaydi |
| XLSX | Har varaq alohida sahifa; sarlavha qatori birinchi 15 qatordan qidiriladi | — |
| DOCX | Paragraflar va jadvallar | Sahifa raqami yo‘q, hammasi 1-sahifa |
| DXF | Matnlar va blok atributlari | Parametrlar faqat blok atributlaridan olinadi |
| DWG | — | O‘qilmaydi; DXF ga o‘girib yuklang |

Buzilgan yoki noma'lum fayl "Xato" holatini oladi; qolgan hujjatlar ishlayveradi.

### Parametrlar qanday ajratiladi

- **Ustunli jadval** (uskunalar ro‘yxati, quvurlar ro‘yxati): sarlavhalar
  o‘zbek, ingliz va rus tilidagi lug‘at bo‘yicha taniladi (`Design Pressure,
  barg`, `Loyiha bosimi (MPa)`, `Расчётное давление`).
- **Kalit–qiymat jadval** (datasheet): birinchi ustun — parametr nomi,
  ikkinchisi — qiymat.
- Tanilmagan ustunlar hujjat sahifasida "Bog‘lanmagan ustunlar" sifatida
  ko‘rsatiladi — ular tekshiruvda qatnashmaydi.
- Qiymatlar SI ga keltiriladi (bosim kPa(g), harorat °C, sarf m³/h, o‘lcham mm,
  quvvat kW); asl qiymat ham saqlanadi.
- Belgisiz `bar`, `psi`, `kPa`, `MPa` manometrik deb olinadi va shu qiymatga
  tayangan topilmaning ishonchliligi "O‘rta" ga tushadi.

### Qoidalar

| Kod | Nimani tekshiradi | Jiddiylik |
|---|---|---|
| R001 | Bir teg va parametr turli hujjatlarda turlicha (son uchun 1 % bardoshlik) | Jiddiy; bosim va harorat — Kritik |
| R002 | Teg P&ID ↔ uskunalar ro‘yxati ↔ quvurlar ro‘yxatida, datasheet → uskunalar ro‘yxatida yo‘q | Jiddiy |
| R003 | Datasheet yoki quvurlar ro‘yxatida majburiy maydon bo‘sh | Kichik; loyiha bosimi/harorati — Jiddiy |
| R004 | Loyiha bosimi yoki harorati ish qiymatidan past | Kritik |
| R005 | Quvur sinfi material spetsifikatsiyasida yo‘q | Jiddiy |
| R006 | Hujjat boshqa hujjatning eskirgan reviziyasiga havola qiladi | Kichik |
| R007 | Sonli qiymatning o‘lchov birligi tanilmadi | Kichik |

Qoidalarni yetakchi muhandis yoki administrator **Boshqaruv** sahifasida
yoqadi va o‘chiradi.

### Tamoyillar

- Topilmada faqat hujjatlardan o‘qilgan qiymatlar yoziladi. Har birida manba
  va ishonchlilik darajasi ko‘rsatiladi.
- Tizim yuklangan hujjatlarni hech qachon o‘zgartirmaydi. Tuzatishni muhandis
  asl hujjatda bajaradi.
- Standartga havola faqat amaldagi standart qoidaga biriktirilgan bo‘lsa
  chiqadi; aks holda manba — "Loyiha hujjatlari o‘rtasidagi ichki
  nomuvofiqlik". 1-siklda standartlar bazasi bo‘sh.

### Rollar

| Harakat | Kuzatuvchi | Muhandis | Yetakchi muhandis | Administrator |
|---|---|---|---|---|
| Ko‘rish | ✓ | ✓ | ✓ | ✓ |
| Hujjat yuklash, tekshiruvni boshlash | | ✓ | ✓ | ✓ |
| Topilmani tasdiqlash / rad etish | | ✓ | ✓ | ✓ |
| Qoidalarni boshqarish, loyihani o‘chirish | | | ✓ | ✓ |
| Foydalanuvchilar, audit jurnali | | | | ✓ |

### Xavfsizlik

- Parollar argon2 bilan xeshlanadi; sessiya tokeni 12 soat amal qiladi.
- Har bir o‘zgartiruvchi harakat audit jurnaliga yoziladi. Jurnal
  xesh-zanjirli: **Boshqaruv** sahifasi uning butunligini tekshiradi.
- **Baza hozircha shifrlanmagan** (oddiy SQLite fayli `ENGCHECK_DATA_DIR`
  ichida). Maxfiy loyihalar uchun papkani disk shifrlash (BitLocker,
  FileVault, LUKS) bilan himoyalang. SQLCipher 3-siklda qo‘shiladi.

## Testlar

```bash
cd backend && python -m pytest -q
```

```bash
cd frontend && npx vitest run
```

```bash
cd frontend && npx playwright test --trace off
```

Playwright testlari interfeysni o‘zi qurib, xizmatni vaqtinchalik ma'lumotlar
papkasi bilan 8799-portda ishga tushiradi.

## Tuzilma

```
backend/engcheck/
  core/      modellar, autentifikatsiya, audit jurnali
  ingest/    parserlar, birliklar, teg va parametr ajratish
  review/    qoidalar (R001–R007), dvigatel, uch tilli matnlar
  api/       HTTP API
frontend/    React interfeysi (uz / en / ru)
samples/     namunaviy loyiha generatori
docs/superpowers/   spetsifikatsiya va amalga oshirish rejasi
```

## Hali yo‘q

| Imkoniyat | Sikl |
|---|---|
| AI tahlili, provayderni API kaliti bilan ulash, lokal modellar | 2 |
| Bilimlar bazasi (standartlar, adabiyotlar), RAG | 2 |
| Desktop o‘rnatuvchi (Electron), baza shifrlash, loyiha paketini eksport/import | 3 |
| Prinsipial sxema generatori | 4 |
| 3D joylashuv modeli | 5 |
| OCR (skanerlangan PDF) | rejalashtirilmagan |
