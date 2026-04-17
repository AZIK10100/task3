import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

def format_card(raw_card) -> str:
    if not raw_card:
        raise ValueError("Номер карты пустой")
    digits = re.sub(r'\D', '', str(raw_card))
    if len(digits) != 16:
        raise ValueError(f"Номер карты должен содержать 16 цифр, получено {len(digits)}: '{raw_card}'")
    return digits


def card_mask(card_number: str) -> str:
    try:
        c = format_card(card_number)
        return f"{c[:4]} **** **** {c[12:]}"
    except ValueError:
        return card_number


def format_phone(raw_phone) -> str:
    if not raw_phone or str(raw_phone).strip() in ('', 'nan', 'None'):
        return ''
    digits = re.sub(r'\D', '', str(raw_phone))
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    if len(digits) == 13 and digits.startswith('998'):
        return f"+{digits[1:]}" if digits[0] == '0' else f"+{digits}"
    return digits


def phone_mask(phone: str) -> str:
    if not phone:
        return '—'
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('998'):
        return f"+998 {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"
    return phone


def parse_expire(raw_expire) -> 'date':
    if not raw_expire:
        raise ValueError("Дата истечения пустая")

    raw = str(raw_expire).strip()

    formats = [
        (r'^\d{2}/\d{2}$',   '%m/%y'),    # 12/24
        (r'^\d{2}/\d{4}$',   '%m/%Y'),    # 12/2024
        (r'^\d{2}\.\d{4}$',  '%m.%Y'),    # 12.2024
        (r'^\d{2}\.\d{2}$',  '%m.%y'),    # 12.24
        (r'^\d{4}-\d{2}$',   '%Y-%m'),    # 2024-12
        (r'^\d{2}-\d{4}$',   '%m-%Y'),    # 12-2024
    ]

    for pattern, fmt in formats:
        if re.match(pattern, raw):
            dt = datetime.strptime(raw, fmt)
            return dt.replace(day=1).date()

    raise ValueError(f"Неизвестный формат даты истечения: '{raw_expire}'")


def prepare_message(card_number: str, balance, lang: str = "UZ") -> str:
    masked = card_mask(card_number)
    if lang == "UZ":
        return f"Sizning kartangiz {masked} aktiv va foydalanishga {balance} UZS mavjud!"
    elif lang == "RU":
        return f"Ваша карта {masked} активна, доступно {balance} UZS!"
    return f"Your card {masked} is active, balance: {balance} UZS!"


def send_message(message: str, chat_id: int = 12345) -> bool:
    print(f"[TELEGRAM] → chat_id={chat_id}: {message}")
    return True


def clean_balance(raw_balance):
    """
    Takes: '842,714,800.00', '200.00', '8 911 200'
    Returns: Decimal object
    """
    if raw_balance is None or str(raw_balance).strip() in ('', 'nan', 'None'):
        return Decimal('0.00')  # Default to 0 if empty

    # Remove commas and spaces
    cleaned = re.sub(r'[,\s]', '', str(raw_balance))

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        # If it still fails, return 0 to prevent the crash
        return Decimal('0.00')

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
