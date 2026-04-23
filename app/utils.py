import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
import requests
import random

def format_card(raw_card) -> str:
    if not raw_card:
        raise ValueError("Номер карты пустой")
    digits = re.sub(r"\D", "", str(raw_card))
    if len(digits) != 16:
        raise ValueError(
            f"Номер карты должен содержать 16 цифр, получено {len(digits)}: '{raw_card}'"
        )
    return digits


def card_mask(card_number: str) -> str:
    try:
        c = format_card(card_number)
        return f"{c[:4]} **** **** {c[12:]}"
    except ValueError:
        return card_number


def card_mask_spoiler(card_number: str) -> str:
    try:
        c = format_card(card_number)
        return f"{c[:4]} <tg-spoiler>{c[4:8]} {c[8:12]}</tg-spoiler> {c[12:]}"
    except ValueError:
        return card_number


def format_phone(raw_phone) -> str:
    if not raw_phone or str(raw_phone).strip() in ("", "nan", "None"):
        return ""
    digits = re.sub(r"\D", "", str(raw_phone))
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if len(digits) == 13 and digits.startswith("998"):
        return f"+{digits[1:]}" if digits[0] == "0" else f"+{digits}"
    return digits


def parse_expire(raw_expire):
    if not raw_expire:
        raise ValueError("Дата истечения пустая")

    raw = str(raw_expire).strip()

    formats = [
        (r"^\d{2}/\d{2}$", "%m/%y"),  # 12/24
        (r"^\d{2}/\d{4}$", "%m/%Y"),  # 12/2024
        (r"^\d{2}\.\d{4}$", "%m.%Y"),  # 12.2024
        (r"^\d{2}\.\d{2}$", "%m.%y"),  # 12.24
        (r"^\d{4}-\d{2}$", "%Y-%m"),  # 2024-12
        (r"^\d{2}-\d{4}$", "%m-%Y"),  # 12-2024
    ]

    for pattern, fmt in formats:
        if re.match(pattern, raw):
            dt = datetime.strptime(raw, fmt)
            return dt.replace(day=1).date()

    raise ValueError(f"Неизвестный формат даты истечения: '{raw_expire}'")


def prepare_message(card_number: str, balance, lang: str = "UZ") -> str:
    masked = card_mask(card_number)
    if lang == "UZ":
        return (
            f"Sizning kartangiz {masked} aktiv va foydalanishga {balance} UZS mavjud!"
        )
    elif lang == "RU":
        return f"Ваша карта {masked} активна, доступно {balance} UZS!"
    return f"Your card {masked} is active, balance: {balance} UZS!"


def send_message(message: str, chat_id: int = 12345) -> bool:
    print(f"[TELEGRAM] → chat_id={chat_id}: {message}")
    return True


def phone_mask(phone: str) -> str:
    if not phone:
        return "—"
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 12 and digits.startswith("998"):
        return f"+998 {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"
    return phone


def clean_balance(raw_balance):
    """
    Takes: '842,714,800.00', '200.00', '8 911 200'
    Returns: Decimal object
    """
    if raw_balance is None or str(raw_balance).strip() in ("", "nan", "None"):
        return Decimal("0.00")  # Default to 0 if empty

    # Remove commas and spaces
    cleaned = re.sub(r"[,\s]", "", str(raw_balance))

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        # If it still fails, return 0 to prevent the crash
        return Decimal("0.00")


def clean_card_number(card):
    card = list(card)
    result = []
    for i in card:
        if i.isdigit():
            result.append(i)
    return "".join(result)


def convert_date(mm_yy: str) -> str:
    date_obj = datetime.strptime(mm_yy, "%m-%y")
    return date_obj.strftime("%Y-%m-01")


def format_card_number(card_number):
    return (
        f"{card_number[:4]} {card_number[4:8]} {card_number[8:12]} {card_number[12:]}"
    )


def format_phone_number(phone_number):
    return f"{phone_number[:4]} {phone_number[4:6]} {phone_number[6:9]} {phone_number[9:11]} {phone_number[11:13]}"


from functools import reduce


def check_card_by_luhn(card_number):
    clean_cart = clean_card_number(card_number)

    if len(clean_cart) != 16:
        return False

    numbers = list(clean_cart)

    dublicated_evens = []

    for index, number in enumerate(numbers):
        number = int(number)

        if index % 2 == 0:
            number *= 2
            if number > 9:
                number -= 9

        dublicated_evens.append(number)

    total = sum(dublicated_evens)

    return total % 10 == 0


USD = 840
RUB = 643
UZS = 860

ALLOWED = {USD, RUB, UZS}
ERROR_CODE = 32707


def get_rates():
    url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception("API ishlamayapti")

    data = response.json()

    rates = {UZS: 1}

    for item in data:
        if item['Ccy'] == "USD":
            rates[USD] = float(item['Rate'])
        elif item['Ccy'] == "RUB":
            rates[RUB] = float(item['Rate'])

    return rates


def currency_error(lang="uz"):
    if lang == "ru":
        return {"code": ERROR_CODE, "message": "Разрешены только валюты 860, 643, 840"}
    elif lang == "en":
        return {"code": ERROR_CODE, "message": "Currency not allowed except 860, 643, 840"}
    else:
        return {"code": ERROR_CODE, "message": "Faqat 860, 643, 840 valyutalari ruxsat etilgan"}


def convert(amount, from_currency, to_currency, lang="uz"):
    """
    UZS ↔ USD ↔ RUB universal converter
    """

    # ❌ validation
    if amount is None or amount <= 0:
        raise ValueError("Amount must be positive")

    if from_currency not in ALLOWED or to_currency not in ALLOWED:
        return currency_error(lang)

    rates = get_rates()

    # 🔁 UZS ga o'tkazish
    amount_in_uzs = amount * rates[from_currency]

    # 🔁 target currency
    result = amount_in_uzs / rates[to_currency]

    return {
        "amount": round(result, 2),
        "from": from_currency,
        "to": to_currency
    }



def generate_otp(length=6):
    return "".join(str(random.randint(0, 9)) for _ in range(length))
