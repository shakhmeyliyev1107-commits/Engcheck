# EngCheck — muhandislik hujjatlarini tekshirish platformasi

Sanoat korxonalari (GTL, MTO, neft va gazni qayta ishlash, suv va oqova suv
tozalash) loyiha hujjatlarini FEED, Detail Design va As-Built bosqichlarida
tekshiradi: hujjatlardan teg va parametrlarni ajratadi, ularni o‘zaro
solishtiradi va nomuvofiqliklarni manbasi bilan ko‘rsatadi.

**Hozirgi holat (1–3-sikllar):** deterministik tekshiruv dvigateli, AI
provayderlarini ulash (bulutli va lokal), bilimlar bazasi (RAG), manbali AI
izoh va AI tekshiruv, desktop qobiq, baza shifrlash, loyiha paketini
eksport/import. Sxema va 3D model keyingi sikllarda — pastdagi "Hali yo‘q"
bo‘limiga qarang.

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
- Teg yozilishi bir xil ko‘rinishga keltiriladi: `p-101 a`, `P101A`, kirillcha
  `Р-101А` → `P-101A`; `P-101A/B` ikki tegga ajraladi. Teg ustunidagi
  tanilmagan qiymatlar hujjat sahifasida ko‘rsatiladi — bu qatorlar o‘qilmagan.
- Sarlavha ostidagi birliklar qatori (`in | barg | °C`) va `DN`/`NPS`
  ustunlari tushuniladi.
- Diapazon (`-29 / 150 °C`) va noaniq yozuv (`1,200` — 1200 ham, 1,2 ham
  bo‘lishi mumkin) songa aylantirilmaydi; R007 ularni "o‘qilmagan qiymat"
  sifatida ko‘rsatadi.
- Bir raqamli hujjatning bir nechta reviziyasi yuklansa, tekshiruvda faqat eng
  yuqorisi qatnashadi. Tartib: harfli (A, B, C) < raqamli (0, 1, 2).
- Belgisiz `bar`, `psi`, `kPa`, `MPa` manometrik deb olinadi va shu qiymatga
  tayangan topilmaning ishonchliligi "O‘rta" ga tushadi.

### Qoidalar

| Kod | Nimani tekshiradi | Jiddiylik |
|---|---|---|
| R001 | Bir teg va parametr turli hujjatlarda turlicha (son uchun 1 % bardoshlik) | Jiddiy; bosim va harorat — Kritik |
| R002 | Teg P&ID ↔ uskunalar ro‘yxati ↔ quvurlar ro‘yxatida, datasheet → uskunalar ro‘yxatida yo‘q. P&ID matnidan topilgan teg faqat prefiksi loyihada uskuna sifatida ma'lum bo‘lsa tekshiriladi | Jiddiy |
| R003 | Datasheet yoki quvurlar ro‘yxatida majburiy maydon bo‘sh | Kichik; loyiha bosimi/harorati — Jiddiy |
| R004 | Loyiha bosimi yoki harorati ish qiymatidan past; manfiy loyiha harorati minimal harorat deb olinadi | Kritik |
| R005 | Quvur sinfi material spetsifikatsiyasida yo‘q | Jiddiy |
| R006 | Hujjat boshqa hujjatning eskirgan yoki loyihaga yuklanmagan reviziyasiga havola qiladi | Kichik |
| R007 | Sonli qiymatning birligi tanilmadi (Kichik) yoki qiymat o‘qilmadi (Ma'lumot) | Kichik / Ma'lumot |

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
| AI izoh so‘rash, manba qo‘shish (tasdiqlanmagan), dars taklif qilish | | ✓ | ✓ | ✓ |
| Manbani tasdiqlash, loyihada bulutli AI ga ruxsat | | | ✓ | ✓ |
| Foydalanuvchilar, audit jurnali, AI provayderlari va kalitlar | | | | ✓ |

### Xavfsizlik

- Parollar argon2 bilan xeshlanadi; sessiya tokeni 12 soat amal qiladi.
- Har bir o‘zgartiruvchi harakat audit jurnaliga yoziladi. Jurnal
  xesh-zanjirli: **Boshqaruv** sahifasi uning butunligini tekshiradi.
- Baza shifrlash va boshqa himoya choralari — "Ma'lumotlar himoyasi" bo‘limida.

## Desktop ilova

Ilovani oynada ochish (brauzersiz). Qobiq Python xizmatini o‘zi ishga
tushiradi (har safar bo‘sh portda) va yopilganda to‘xtatadi.

```bash
cd desktop && npm install && npm start
```

Ma'lumotlar Electron'ning foydalanuvchi papkasida saqlanadi (Windows:
`%APPDATA%\EngCheck\data`, macOS: `~/Library/Application Support/EngCheck/data`,
Linux: `~/.config/EngCheck/data`).

### O‘rnatuvchini yig‘ish

O‘rnatuvchi shu kompyuterda, o‘sha operatsion tizim uchun quriladi. Bu
buyruqlar ishlab chiqish muhitida sinalmagan — birinchi yig‘ishda xato chiqsa,
xabarini saqlab qo‘ying.

```bash
cd frontend && npm install && npm run build && cd ..
```

```bash
cd backend && pip install pyinstaller && pyinstaller --name engcheck-server --onedir --collect-all engcheck --collect-all sqlcipher3 --collect-all ezdxf --collect-all pdfplumber server_entry.py && cd ..
```

```bash
cd desktop && npm install && npm run dist
```

Natija `desktop/dist/` da. Ilova imzolanmagan: Windows va macOS birinchi
ochishda ogohlantiradi.

## Ma'lumotlar himoyasi

- **Baza shifrlash (SQLCipher).** `pip install -e "backend[encryption]"`
  o‘rnatilgan bo‘lsa, yangi baza shifrlangan holda yaratiladi. Mavjud ochiq
  bazani ko‘chirish (ilova to‘xtatilgan holda):

  ```bash
  cd backend && python -m engcheck encrypt-db
  ```

  Ochiq nusxa `engcheck.db.plain.bak` nomi bilan qoladi — tekshirib, o‘zingiz
  o‘chiring. O‘chirib qo‘yish: `ENGCHECK_ENCRYPT=0`.
- **Kalit qayerda.** Baza kaliti API kalitlari bilan bir omborda. OS kalit
  ombori (`backend[keyring]`) bo‘lmasa, kalit ma'lumotlar papkasidagi faylda
  turadi: bu baza faylining alohida nusxasi tarqalishidan himoya qiladi,
  butun papkani olgan odamdan emas.
- **Yuklangan asl hujjatlar diskda shifrlanmaydi.** Maxfiy loyihalar uchun
  diskni shifrlang (BitLocker, FileVault, LUKS).
- **Kalit yo‘qolsa, shifrlangan bazani ochib bo‘lmaydi.** Ma'lumotlar
  papkasini boshqa kompyuterga ko‘chirganda `secret.key` va `secrets.enc` ni
  ham ko‘chiring (yoki loyiha paketidan foydalaning).
- **Boshqaruv** sahifasi joriy himoya darajasini ko‘rsatadi.
- Xizmat faqat `127.0.0.1` da tinglaydi va begona `Host` sarlavhali
  so‘rovlarni rad etadi.

## Loyiha paketi

Loyihani hamkasbga bitta `.engpkg` fayl sifatida berish:

- **Eksport** (loyiha sahifasi; yetakchi muhandis yoki administrator): asl
  hujjatlar va topilmalar bo‘yicha qarorlar. **Kirmaydi:** API kalitlari, AI
  provayderlari, foydalanuvchilar, audit jurnali, bilimlar bazasi, AI izohlari
  va AI topilmalari.
- **Parol ixtiyoriy.** Parol qo‘yilsa, paket shifrlanadi. Parolsiz paket faqat
  shikastlanishdan himoyalangan — uni ochib o‘qish va o‘zgartirish mumkin.
  Maxfiy loyihani faqat parol bilan yuboring; parolni boshqa kanal orqali ayting.
- **Import** (Loyihalar sahifasi): yangi loyiha yaratiladi, hujjatlar qayta
  tahlil qilinadi, qoidalar ishga tushadi, qarorlar tiklanadi. Bulutli AI
  roziligi ko‘chmaydi — qabul qiluvchi o‘zi beradi.

## AI va bilimlar bazasi

AI ixtiyoriy: usiz ham barcha qoidalar ishlaydi.

### Provayder ulash

**Boshqaruv → AI provayderlari** (faqat administrator):

| Tur | Nima uchun | Manzil | Kalit |
|---|---|---|---|
| Anthropic (Claude) | bulutli; standart model `claude-opus-5-5` | bo‘sh qoldiring | kerak |
| OpenAI-mos API | OpenAI, OpenRouter, vLLM, LM Studio va shu protokoldagi boshqa xizmatlar | masalan `https://api.openai.com/v1` yoki `http://127.0.0.1:1234/v1` | xizmatga qarab |
| Ollama | lokal modellar, oflayn | `http://127.0.0.1:11434` | kerak emas |

- **Sinash** tugmasi ulanishni tekshiradi; xato sababi (kalit noto‘g‘ri,
  ulanib bo‘lmadi va h.k.) ko‘rsatiladi.
- Bir nechta provayder qo‘shib, **Standart qilish** bilan almashtirasiz.
- Provayder lokalmi yoki bulutlimi — manzildan aniqlanadi (`localhost`,
  loopback yoki xususiy tarmoq IP si → lokal). Qo‘lda belgilab bo‘lmaydi.
- **Kalitlar** OS kalit omborida saqlanadi (`pip install -e "backend[keyring]"`
  o‘rnatilgan va ombor mavjud bo‘lsa). Aks holda ma'lumotlar papkasidagi
  shifrlangan `secrets.enc` faylida (kaliti `secret.key`, ruxsat 0600). Fayl
  varianti baza nusxasi tarqalganda kalitlarni himoya qiladi, lekin butun
  papkaga kira olgan odamdan emas. Kalit bazaga, audit jurnaliga va
  interfeysga hech qachon chiqmaydi.

### Onlayn va oflayn rejim

Loyiha sahifasida joriy rejim ko‘rinadi:

- **Bulutli AI har loyiha uchun standart holatda o‘chiq.** Yetakchi muhandis
  yoki administrator loyiha sahifasida ruxsat beradi.
- Standart provayder javob bermasa (internet yo‘q), tizim keyingi yoqilgan
  provayderga — odatda lokal modelga — o‘tadi.
- Hech biri ishlamasa, sababi ko‘rsatiladi va faqat qoidalar ishlaydi.

### Bilimlar bazasi

**Bilimlar bazasi** sahifasida standart, adabiyot yoki eslatma qo‘shasiz
(PDF, DOCX, XLSX, TXT, MD yoki matn).

- Har manbada nashr, amal qilish holati (amalda / almashtirilgan / bekor
  qilingan) va litsenziya turi bor. Bekor qilingan manba qidiruvga kirmaydi;
  almashtirilgan nashr belgisi bilan chiqadi.
- **Litsenziyali manba:** faqat 300 belgigacha iqtibos ko‘rsatiladi, fayli
  yuklab olinmaydi, matni bulutli AI ga yuborilmaydi (faqat nomi, nashri va
  sahifasi). Standart matnini yuklash huquqi sizda borligiga o‘zingiz
  javobgarsiz.
- Muhandis qo‘shgan manba tasdiqlanmaguncha qidiruvda qatnashmaydi;
  yetakchi muhandis tasdiqlaydi.
- Qidiruv lokal ishlaydi (BM25). Provayderda embedding modeli sozlangan
  bo‘lsa, **Embedding indeksini yangilash** dan keyin ma'no bo‘yicha qidiruv
  ham qo‘shiladi.

### AI nima qiladi

- **AI izoh** (topilma sahifasida): topilma faktlari va bilimlar bazasidan
  topilgan parchalar asosida tushuntirish. Har havola berilgan parchaga
  ishora qiladi; berilmagan manbaga havola tashlab yuboriladi. AI taxminlari
  alohida ro‘yxatda.
- **AI bilan tekshirish** (loyiha sahifasida "AI bilan" belgisi): AI hujjat
  matnidan muammo qidiradi. Har AI topilmasi hujjatdan so‘zma-so‘z iqtibos
  keltirishi shart — iqtibos hujjatda topilmasa, topilma qabul qilinmaydi.
  Bir tekshiruvda 40 sahifagacha ko‘riladi; qolgani sanab ko‘rsatiladi.
- AI natijalari doim **"AI taxmini — muhandis tasdiqlamagan"** belgisi va
  "Past" ishonchlilik bilan chiqadi. AI topilmani tasdiqlamaydi va hujjatni
  o‘zgartirmaydi.
- **Dars taklif qilish:** tasdiqlangan, rad etilgan yoki tuzatilgan
  topilmadan bilimlar bazasiga dars taklif qilasiz; yetakchi muhandis
  tasdiqlagach, u keyingi AI izohlariga manba bo‘ladi.

Provayderlar soxta server va soxta transport bilan testlangan; haqiqiy
Anthropic, OpenAI yoki Ollama xizmatiga ulanib sinalmagan — birinchi
ulashda **Sinash** tugmasidan foydalaning.

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

```bash
cd desktop && npm test
```

Playwright testlari interfeysni o‘zi qurib, xizmatni vaqtinchalik ma'lumotlar
papkasi bilan 8799-portda va soxta lokal AI serverini 8796-portda ishga tushiradi.

## Tuzilma

```
backend/engcheck/
  core/      modellar, autentifikatsiya, audit jurnali
  ingest/    parserlar, birliklar, teg va parametr ajratish
  review/    qoidalar (R001–R007), dvigatel, uch tilli matnlar
  ai/        provayderlar, rejim tanlash, AI izoh va AI tekshiruv
  kb/        bilimlar bazasi: bo'laklash, qidiruv, indekslash
  api/       HTTP API
frontend/    React interfeysi (uz / en / ru)
desktop/     Electron qobig'i
samples/     namunaviy loyiha generatori
docs/superpowers/   spetsifikatsiya va amalga oshirish rejasi
```

## Hali yo‘q

| Imkoniyat | Sikl |
|---|---|
| Prinsipial sxema generatori va tahrirlagichi | 4 |
| 3D joylashuv modeli va uni tahrirlash | 5 |
| Yuklangan fayllarni diskda shifrlash, kod imzolash, avtomatik yangilanish | rejalashtirilmagan |
| OCR (skanerlangan PDF) | rejalashtirilmagan |
