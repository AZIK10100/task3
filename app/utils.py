import logging
import random
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)

USD = 840
RUB = 643
UZS = 860

ALLOWED = {USD, RUB, UZS}
STATIC_EXCHANGE_RATES = {
    UZS: Decimal("1"),
    RUB: Decimal("140"),
    USD: Decimal("12600"),
}
OTP_LIFETIME_SECONDS = 300


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
        card = format_card(card_number)
        return f"{card[:4]} **** **** {card[12:]}"
    except ValueError:
        return str(card_number)


def card_mask_spoiler(card_number: str) -> str:
    try:
        card = format_card(card_number)
        return f"{card[:4]} <tg-spoiler>{card[4:8]} {card[8:12]}</tg-spoiler> {card[12:]}"
    except ValueError:
        return str(card_number)


def format_phone(raw_phone) -> str:
    if not raw_phone or str(raw_phone).strip() in ("", "nan", "None"):
        return ""

    digits = re.sub(r"\D", "", str(raw_phone))
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if len(digits) == 13 and digits.startswith("0998"):
        return f"+{digits[1:]}"
    return digits


def parse_expire(raw_expire):
    if not raw_expire:
        raise ValueError("Дата истечения пустая")

    raw = str(raw_expire).strip()
    formats = [
        (r"^\d{2}/\d{2}$", "%m/%y"),
        (r"^\d{2}/\d{4}$", "%m/%Y"),
        (r"^\d{2}\.\d{4}$", "%m.%Y"),
        (r"^\d{2}\.\d{2}$", "%m.%y"),
        (r"^\d{4}-\d{2}$", "%Y-%m"),
        (r"^\d{2}-\d{4}$", "%m-%Y"),
    ]

    for pattern, dt_format in formats:
        if re.match(pattern, raw):
            return datetime.strptime(raw, dt_format).replace(day=1).date()

    raise ValueError(f"Неизвестный формат даты истечения: '{raw_expire}'")


def prepare_message(card_number: str, balance, lang: str = "UZ") -> str:
    masked = card_mask(card_number)
    if lang == "UZ":
        return (
            f"Sizning kartangiz {masked} aktiv va foydalanishga {balance} UZS mavjud!"
        )
    if lang == "RU":
        return f"Ваша карта {masked} активна, доступно {balance} UZS!"
    return f"Your card {masked} is active, balance: {balance} UZS!"


def send_message(message: str, chat_id) -> bool:
    """Send a message via the Telegram Bot API. Returns True on success."""
    token = getattr(settings, "BOT_TOKEN", None)
    if not token:
        logger.error("BOT_TOKEN is not configured in settings")
        return False
    if not chat_id:
        logger.warning("send_message called with empty chat_id — message not sent")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.error(
                "Telegram API error chat_id=%s: %s",
                chat_id,
                data.get("description"),
            )
            return False
        logger.info("OTP sent via Telegram to chat_id=%s", chat_id)
        return True
    except requests.RequestException as exc:
        logger.exception("Failed to send Telegram message to chat_id=%s: %s", chat_id, exc)
        return False


def phone_mask(phone: str) -> str:
    if not phone:
        return "—"

    digits = re.sub(r"\D", "", phone)
    if len(digits) == 12 and digits.startswith("998"):
        return f"+998 {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:12]}"
    return phone


def clean_balance(raw_balance):
    if raw_balance is None or str(raw_balance).strip() in ("", "nan", "None"):
        return Decimal("0.00")

    cleaned = re.sub(r"[,\s]", "", str(raw_balance))
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0.00")


def clean_card_number(card):
    if card is None:
        return ""
    return "".join(symbol for symbol in str(card) if symbol.isdigit())


def convert_date(mm_yy: str) -> str:
    date_obj = datetime.strptime(mm_yy, "%m-%y")
    return date_obj.strftime("%Y-%m-01")


def format_card_number(card_number):
    card = clean_card_number(card_number)
    if len(card) != 16:
        return str(card_number)
    return f"{card[:4]} {card[4:8]} {card[8:12]} {card[12:]}"


def format_phone_number(phone_number):
    phone = re.sub(r"\D", "", str(phone_number))
    if len(phone) != 12:
        return str(phone_number)
    return f"{phone[:3]} {phone[3:5]} {phone[5:8]} {phone[8:10]} {phone[10:12]}"


def validate_card(card_number):
    digits = clean_card_number(card_number)
    if len(digits) != 16:
        return False

    checksum = 0
    reverse_digits = digits[::-1]
    for index, symbol in enumerate(reverse_digits):
        number = int(symbol)
        if index % 2 == 1:
            number *= 2
            if number > 9:
                number -= 9
        checksum += number
    return checksum % 10 == 0


def check_card_by_luhn(card_number):
    return validate_card(card_number)


def normalize_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Amount is not valid") from exc

    if amount <= 0:
        raise ValueError("Amount must be positive")

    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def currency_error(lang="uz"):
    if lang == "ru":
        message = "Разрешены только валюты 860, 643, 840"
    elif lang == "en":
        message = "Currency not allowed except 860, 643, 840"
    else:
        message = "Faqat 860, 643, 840 valyutalari ruxsat etilgan"
    return {"code": 32707, "message": message}


def calculate_exchange(amount, currency):
    normalized_amount = normalize_amount(amount)
    if currency not in STATIC_EXCHANGE_RATES:
        raise ValueError("Currency is not allowed")

    rate = STATIC_EXCHANGE_RATES[currency]
    return (normalized_amount * rate).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def convert(amount, from_currency, to_currency, lang="uz"):
    normalized_amount = normalize_amount(amount)
    if from_currency not in ALLOWED or to_currency not in ALLOWED:
        return currency_error(lang)

    amount_in_uzs = normalized_amount * STATIC_EXCHANGE_RATES[from_currency]
    result = amount_in_uzs / STATIC_EXCHANGE_RATES[to_currency]
    return {
        "amount": result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "from": from_currency,
        "to": to_currency,
    }


def generate_otp(length=6):
    return "".join(random.choice("0123456789") for _ in range(length))


def get_transfer_by_ext_id(ext_id):
    from .models import Transfer

    return Transfer.objects.filter(ext_id=ext_id).first()


def is_otp_expired(transfer, lifetime_seconds=OTP_LIFETIME_SECONDS):
    created_at = transfer.created_at or timezone.now()
    expires_at = created_at + timedelta(seconds=lifetime_seconds)
    return timezone.now() > expires_at


def resolve_telegram_chat_id(phone, default_chat_id=None):
    if not phone:
        return default_chat_id

    from .models import Card, User, UserCard

    formatted_phone = format_phone(phone)

    user = User.objects.filter(phone_number=formatted_phone).only("telegram_id").first()
    if user and user.telegram_id:
        return user.telegram_id

    card = Card.objects.filter(phone=formatted_phone).only("id").first()
    if not card:
        return default_chat_id

    user_card = (
        UserCard.objects.select_related("user")
        .filter(card=card, user__telegram_id__isnull=False)
        .first()
    )
    if user_card and user_card.user.telegram_id:
        return user_card.user.telegram_id

    return default_chat_id


def send_telegram_message(phone, message, chat_id=None):
    resolved_chat_id = resolve_telegram_chat_id(phone, chat_id)
    if not resolved_chat_id:
        logger.warning(
            "send_telegram_message: no telegram_id found for phone=%s, OTP not sent", phone
        )
        return False
    return send_message(message, resolved_chat_id)
