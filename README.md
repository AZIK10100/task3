# 💳 Card Management System

Django asosida qurilgan bank kartalarini boshqarish tizimi. Tizim orqali kartalarni import qilish, eksport qilish, holat bo'yicha filtrlash va Telegram orqali xabar yuborish mumkin.

---

## 📋 Loyiha haqida

Bu loyiha quyidagi imkoniyatlarni taqdim etadi:

- Bank kartalarini Excel fayl orqali import qilish (oddiy va AI yordamida)
- Karta ma'lumotlarini CSV formatida eksport qilish
- Django Admin panelida kartalarni boshqarish
- Karta va telefon raqamlarini avtomatik tozalash va normallash
- Faol kartalar egalariga Telegram bot orqali xabar yuborish
- JSON-RPC API orqali pul o'tkazmalarini amalga oshirish

---

## ⚙️ O'rnatish va sozlash

### 1. Talablar

- Python 3.10+
- pip
- virtualenv

### 2. Loyihani yuklab olish

```bash
git clone https://github.com/username/card-management.git
cd card-management
```

### 3. Virtual muhit yaratish

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate
```

### 4. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 5. `.env` faylini sozlash

Loyiha papkasida `.env` fayl yarating va quyidagilarni to'ldiring:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ADMIN_CHAT_ID=your-chat-id

# Google Gemini AI
GEMINI_API_KEY=your-gemini-api-key
```

### 6. Ma'lumotlar bazasini tayyorlash

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Superuser yaratish

```bash
python manage.py createsuperuser
```

### 8. Serverni ishga tushirish

```bash
python manage.py runserver
```

Admin panel: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## 🗄️ Ma'lumotlar bazasi tuzilmasi

| Model    | Tavsif                                      |
|----------|---------------------------------------------|
| `Card`   | Bank kartasi: raqam, muddati, holat, balans |
| `User`   | Tizim foydalanuvchisi (Django AbstractUser) |
| `Transfer` | Pul o'tkazma ma'lumotlari               |
| `Error`  | API xato kodlari va tarjimalari             |

---

## 📥 Excel Import

Admin panelda ikkita import usuli mavjud:

### Oddiy Import
`/admin/card/card/import-excel/`

Excel faylning ustunlari tartibi:
| # | Ustun        | Misol                  |
|---|--------------|------------------------|
| 1 | card_number  | 8600 1234 5678 9012    |
| 2 | expire       | 12/24, 2024-12, 12.2024|
| 3 | phone        | 97 303 03 03           |
| 4 | status       | active / inactive / expired |
| 5 | balance      | 1 500 000.00           |

### AI Import (Gemini)
`/admin/card/card/ai-import/`

Ifloslangan yoki noto'g'ri formatdagi ma'lumotlarni Google Gemini AI orqali avtomatik tozalaydi.

---

## 📤 Eksport (Management Command)

```bash
# Barcha kartalarni eksport qilish
python manage.py export_cards --file=cards.csv

# Faqat faol kartalar
python manage.py export_cards --status=active --file=active.csv

# Telefon raqami bo'yicha filter
python manage.py export_cards --phone=998901234567 --file=result.csv

# Karta raqami bo'yicha filter
python manage.py export_cards --card_number=8600 --file=result.csv
```

---

## 📨 Telegram Xabar Yuborish (Management Command)

```bash
# Barcha faol kartalarga xabar yuborish (sinov rejimi)
python manage.py send_messages --status=active --dry-run

# Haqiqiy xabar yuborish
python manage.py send_messages --status=active

# O'zbek tilida xabar
python manage.py send_messages --status=active --lang=UZ
```

Xabar namunasi:
```
Sizning kartangiz 8600 **** **** 9012 aktiv va foydalanishga 1 500 000.00 UZS mavjud!
```

---

## 🌐 API Endpointlar (JSON-RPC)

Barcha so'rovlar `POST /api/` manziliga yuboriladi.

| Method             | Tavsif                        |
|--------------------|-------------------------------|
| `card.info`        | Karta ma'lumotlarini olish    |
| `transfer.create`  | Yangi o'tkazma yaratish       |
| `transfer.confirm` | O'tkazmani tasdiqlash (OTP)   |
| `transfer.cancel`  | O'tkazmani bekor qilish       |
| `transfer.state`   | O'tkazma holatini tekshirish  |

So'rov formati:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "transfer.create",
    "params": {
        "ext_id": "tr-001",
        "sender_card_number": "8600123456789012",
        "sender_card_expiry": "12/26",
        "receiver_card_number": "8600987654321098",
        "sending_amount": 500000,
        "currency": 860,
        "sender_phone": "998901234567"
    }
}
```

---

## 🛠️ Foydali Utility Funksiyalar

| Funksiya               | Tavsif                                      |
|------------------------|---------------------------------------------|
| `format_card(raw)`     | Karta raqamini tozalaydi → 16 ta raqam      |
| `format_phone(raw)`    | Telefon raqamini normallaydi → 998XXXXXXXXX |
| `card_mask(number)`    | Karta raqamini yashiradi → 8600 **** **** 9012 |
| `phone_mask(phone)`    | Telefon raqamini yashiradi → 998 (90) 123-45-67 |
| `prepare_message(...)` | Telegram xabar matnini tayyorlaydi          |
| `send_message(...)`    | Telegram orqali xabar yuboradi              |

---

## 📁 Loyiha Tuzilmasi

```
task3/
├── app/
└── management/
│       └── commands/
│           ├── export_cards.py    # Eksport buyrug'i
│           └── send_messages.py 
│   ├── models.py          # Card, User, Transfer modellari
│   ├── admin.py           # Django Admin sozlamalari
│   ├── resource.py        # Import/Export resursi
│   ├── utils.py           # Utility funksiyalar
│   ├── ai_logic.py        # Gemini AI integratsiyasi
│   ├── forms.py           # Excel import formasi
│   
├── config/
|   ├── __init__.py
│   ├── asgi.py
│   ├── celery.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── requirements.txt
├── .env
└── README.md
```

---

## 📦 Asosiy Kutubxonalar

| Kutubxona               | Versiya | Maqsad                        |
|-------------------------|---------|-------------------------------|
| Django                  | 4.2+    | Asosiy framework              |
| django-import-export    | 3.x     | Excel/CSV import-export       |
| openpyxl                | 3.x     | Excel fayllarni o'qish        |
| google-generativeai     | latest  | Gemini AI integratsiyasi      |
| requests                | 2.x     | Telegram API so'rovlari       |
| python-decouple         | 3.x     | .env faylini o'qish           |

---

## 👨‍💻 Muallif: Abduvoris

Loyiha Django Skills vazifasi doirasida ishlab chiqilgan.