import json
import logging
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from jsonrpcserver import Error as RpcError
from jsonrpcserver import Success, method

from .models import Card, Error, StatusChoices, Transfer, TransferState
from .utils import (
    clean_card_number,
    calculate_exchange,
    format_phone,
    generate_otp,
    get_transfer_by_ext_id,
    is_otp_expired,
    normalize_amount,
    parse_expire,
    send_telegram_message,
)

from .decorators import log_rpc_method


logger = logging.getLogger(__name__)

ALLOWED_METHODS = {
    "transfer.create",
    "transfer.confirm",
    "transfer.cancel",
    "transfer.state",
    "transfer.history",
    "card.info",
}
ALLOWED_CURRENCIES = {643, 840, 860}
MAX_OTP_TRIES = 3
MIN_TRANSFER_AMOUNT = Decimal("1.00")
MAX_TRANSFER_AMOUNT = Decimal("1000000000.00")
CARD_INFO_CACHE_TTL = 30
ERROR_MESSAGE_CACHE_TTL = 300
CACHE_UNAVAILABLE = False


def safe_cache_get(key):
    global CACHE_UNAVAILABLE
    if CACHE_UNAVAILABLE:
        return None
    try:
        return cache.get(key)
    except Exception:
        CACHE_UNAVAILABLE = True
        logger.warning("cache unavailable, falling back to ORM key=%s", key)
        return None


def safe_cache_set(key, value, timeout):
    global CACHE_UNAVAILABLE
    if CACHE_UNAVAILABLE:
        return
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        CACHE_UNAVAILABLE = True
        logger.warning("cache unavailable, skip set key=%s", key)


def normalize_lang(lang):
    value = (lang or "uz").lower()
    return value if value in {"uz", "ru", "en"} else "uz"


def get_error_message(code, lang="uz", **context):
    language = normalize_lang(lang)
    cache_key = f"error_message:{code}:{language}"
    template = safe_cache_get(cache_key)

    if template is None:
        error = Error.objects.only("en", "ru", "uz").get(code=code)
        template = getattr(error, language)
        safe_cache_set(cache_key, template, ERROR_MESSAGE_CACHE_TTL)

    try:
        return template.format(**context)
    except KeyError:
        return template


def rpc_error(code, lang="uz", message=None, **context):
    return RpcError(
        code=code, message=message or get_error_message(code, lang, **context)
    )


def localize_message(uz, ru, en, lang="uz"):
    translations = {"uz": uz, "ru": ru, "en": en}
    return translations[normalize_lang(lang)]


def get_card(card_number):
    return Card.objects.filter(card_number=clean_card_number(card_number)).first()


def expiry_matches(card_expire_date, expected_expiry):
    return (
        card_expire_date.year == expected_expiry.year
        and card_expire_date.month == expected_expiry.month
    )


def validate_amount(amount, lang="uz"):
    normalized_amount = normalize_amount(amount)
    if normalized_amount < MIN_TRANSFER_AMOUNT:
        raise ValueError(get_error_message(32709, lang))
    if normalized_amount > MAX_TRANSFER_AMOUNT:
        raise ValueError(get_error_message(32708, lang))
    return normalized_amount


def validate_sender_receiver_cards(
    sender_card_number,
    sender_card_expiry,
    receiver_card_number,
    lang="uz",
):
    sender_card = get_card(sender_card_number)
    if not sender_card:
        return (
            None,
            None,
            rpc_error(
                32706,
                lang,
                message=localize_message(
                    "Jo'natuvchi karta topilmadi",
                    "Карта отправителя не найдена",
                    "Sender card was not found",
                    lang,
                ),
            ),
        )

    try:
        expected_expiry = parse_expire(sender_card_expiry)
    except ValueError:
        return None, None, rpc_error(32704, lang)

    if not expiry_matches(sender_card.expire_date, expected_expiry):
        return None, None, rpc_error(32704, lang)

    if sender_card.status != StatusChoices.ACTIVE:
        return None, None, rpc_error(32705, lang)

    if not sender_card.phone:
        return None, None, rpc_error(32703, lang)

    receiver_card = get_card(receiver_card_number)
    if not receiver_card:
        return (
            None,
            None,
            rpc_error(
                32706,
                lang,
                message=localize_message(
                    "Qabul qiluvchi karta topilmadi",
                    "Карта получателя не найдена",
                    "Receiver card was not found",
                    lang,
                ),
            ),
        )

    return sender_card, receiver_card, None


def build_otp_message(otp, lang="uz"):
    return localize_message(
        f"Transferni tasdiqlash uchun OTP: {otp}",
        f"OTP для подтверждения перевода: {otp}",
        f"OTP to confirm the transfer: {otp}",
        lang,
    )


def parse_history_date(raw_value, field_name, lang="uz"):
    if not raw_value:
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(
            localize_message(
                f"{field_name} noto'g'ri formatda",
                f"{field_name} в неверном формате",
                f"{field_name} has an invalid format",
                lang,
            )
        ) from exc


@method(name="transfer.create")
@log_rpc_method
def transfer_create(
    ext_id,
    sender_card_number,
    sender_card_expiry,
    receiver_card_number,
    sending_amount,
    currency,
    lang="uz",
):
    """
    Create a new transfer transaction.

    This method validates sender and receiver cards,
    checks balance and currency, generates OTP,
    creates transfer record, and sends confirmation message.

    Args:
        ext_id (str): External unique transfer identifier.
        sender_card_number (str): Sender card number.
        sender_card_expiry (str): Sender card expiry date.
        receiver_card_number (str): Receiver card number.
        sending_amount (Decimal | int | float): Transfer amount.
        currency (int): Currency code.
        lang (str, optional): Response language. Defaults to 'uz'.

    Returns:
        Success: Transfer creation result with transfer state.
        RpcError: Validation or processing error.

    Example:
        transfer.create(
            ext_id='12345',
            sender_card_number='8600123412341234',
            sender_card_expiry='12/27',
            receiver_card_number='9860123412341234',
            sending_amount=10000,
            currency=860
        )
    """
    language = normalize_lang(lang)
    logger.info("transfer.create ext_id=%s", ext_id)

    try:
        if Transfer.objects.filter(ext_id=ext_id).exists():
            return rpc_error(32701, language)

        amount = validate_amount(sending_amount, language)
        if currency not in ALLOWED_CURRENCIES:
            return rpc_error(32707, language)

        sender_card, receiver_card, validation_error = validate_sender_receiver_cards(
            sender_card_number=sender_card_number,
            sender_card_expiry=sender_card_expiry,
            receiver_card_number=receiver_card_number,
            lang=language,
        )
        if validation_error:
            return validation_error

        # sending_amount ni so'mga o'girish (barcha valyutalar uchun)
        sending_amount_uzs = calculate_exchange(amount, currency)

        if sender_card.balance < sending_amount_uzs:
            return rpc_error(32702, language)

        otp = generate_otp()

        with transaction.atomic():
            transfer = Transfer.objects.create(
                ext_id=ext_id,
                sender_card=sender_card,
                receiver_card=receiver_card,
                sender_card_number=sender_card.card_number,
                receiver_card_number=receiver_card.card_number,
                sender_card_expiry=sender_card_expiry,
                sender_phone=format_phone(sender_card.phone),
                receiver_phone=format_phone(receiver_card.phone),
                sending_amount=amount,
                currency=currency,
                receiving_amount=sending_amount_uzs,
                otp=otp,
            )

            message = build_otp_message(otp, language)
            otp_sent = send_telegram_message(sender_card.phone, message)
            if not otp_sent:
                transfer.delete()
                return rpc_error(32703, language)

        return Success(
            {"ext_id": transfer.ext_id, "state": transfer.state, "otp_sent": True}
        )
    except ValueError as exc:
        logger.warning("transfer.create validation failed ext_id=%s: %s", ext_id, exc)
        if str(exc) == get_error_message(32709, language):
            return rpc_error(32709, language)
        if str(exc) == get_error_message(32708, language):
            return rpc_error(32708, language)
        return rpc_error(32706, language, message=str(exc))
    except Exception:
        logger.exception("transfer.create failed ext_id=%s", ext_id)
        return rpc_error(32706, language)


@method(name="transfer.confirm")
@log_rpc_method
def transfer_confirm(ext_id, otp, lang="uz"):
    """
    Confirm an existing transfer using OTP code.

    This method validates OTP code, checks transfer state,
    updates balances, and marks transfer as confirmed.

    Args:
        ext_id (str): External transfer identifier.
        otp (str | int): One-time confirmation password.
        lang (str, optional): Response language. Defaults to 'uz'.

    Returns:
        Success: Confirmed transfer information.
        RpcError: Confirmation or validation error.

    Example:
        transfer.confirm(
            ext_id='12345',
            otp='5432'
        )
    """
    language = normalize_lang(lang)
    logger.info("transfer.confirm ext_id=%s", ext_id)

    try:
        with transaction.atomic():
            transfer = (
                Transfer.objects.select_for_update().filter(ext_id=ext_id).first()
            )
            if not transfer:
                return rpc_error(
                    32706,
                    language,
                    message=localize_message(
                        "Transfer topilmadi",
                        "Перевод не найден",
                        "Transfer was not found",
                        language,
                    ),
                )

            if transfer.state != TransferState.CREATED:
                return rpc_error(32713, language)

            if transfer.try_count >= MAX_OTP_TRIES:
                return rpc_error(32711, language)

            if is_otp_expired(transfer):
                return rpc_error(32710, language)

            if transfer.otp != str(otp).strip():
                transfer.try_count += 1
                transfer.save(update_fields=["try_count", "updated_at"])

                if transfer.try_count >= MAX_OTP_TRIES:
                    return rpc_error(32711, language)

                left_try_count = MAX_OTP_TRIES - transfer.try_count
                return rpc_error(32712, language, left=left_try_count)

            # Sender kartadan yechish (select_for_update bilan race condition oldini olish)
            sender_card = (
                Card.objects.select_for_update().get(pk=transfer.sender_card_id)
                if transfer.sender_card_id
                else Card.objects.select_for_update().filter(
                    card_number=transfer.sender_card_number
                ).first()
            )
            if not sender_card:
                return rpc_error(
                    32706,
                    language,
                    message=localize_message(
                        "Jo'natuvchi karta topilmadi",
                        "Карта отправителя не найдена",
                        "Sender card was not found",
                        language,
                    ),
                )
            # receiving_amount - bu so'mdagi ekvivalent (create da hisoblangan)
            amount_to_deduct = transfer.receiving_amount or transfer.sending_amount
            if sender_card.balance < amount_to_deduct:
                return rpc_error(32702, language)

            # Receiver kartaga qo'shish
            receiver_card = (
                Card.objects.select_for_update().get(pk=transfer.receiver_card_id)
                if transfer.receiver_card_id
                else Card.objects.select_for_update().filter(
                    card_number=transfer.receiver_card_number
                ).first()
            )
            if not receiver_card:
                return rpc_error(
                    32706,
                    language,
                    message=localize_message(
                        "Qabul qiluvchi karta topilmadi",
                        "Карта получателя не найдена",
                        "Receiver card was not found",
                        language,
                    ),
                )

            # Sender dan so'mdagi ekvivalentni yechish
            sender_card.balance -= amount_to_deduct
            sender_card.save(update_fields=["balance"])

            spent_amount = amount_to_deduct
            remaining_balance = sender_card.balance

            # Receiver ga ham so'mda qo'shish (barcha kartalar so'mda)
            receiver_card.balance += amount_to_deduct
            receiver_card.save(update_fields=["balance"])

            transfer.state = TransferState.CONFIRMED
            transfer.confirmed_at = timezone.now()
            transfer.otp = None
            transfer.save(update_fields=["state", "confirmed_at", "otp", "updated_at"])

        balance_message = localize_message(
            f"Transfer tasdiqlandi!\n\n"
            f"Yuborilgan summa: {spent_amount:,.2f} so'm\n"
            f"Qoldiq balans: {remaining_balance:,.2f} so'm",

            f"Перевод подтверждён!\n\n"
            f"Потраченная сумма: {spent_amount:,.2f} сум\n"
            f"Остаток баланса: {remaining_balance:,.2f} сум"
            f"Transfer confirmed!\n\n"
            
            f"Spent amount: {spent_amount:,.2f} sum\n"
            f"Remaining balance: {remaining_balance:,.2f} sum",

            language,
        )
        send_telegram_message(sender_card.phone, balance_message)

        return Success({
            "ext_id": transfer.ext_id,
            "state": transfer.state,
            "spent_amount": float(spent_amount),
            "remaining_balance": float(remaining_balance),
        })

    except Exception:
        logger.exception("transfer.confirm failed ext_id=%s", ext_id)
        return rpc_error(32706, language)


@method(name="transfer.cancel")
@log_rpc_method
def transfer_cancel(ext_id, lang="uz"):
    """
    Cancel a created transfer.

    This method changes transfer state to CANCELLED
    if transfer has not been confirmed yet.

    Args:
        ext_id (str): External transfer identifier.
        lang (str, optional): Response language. Defaults to 'uz'.

    Returns:
        Success: Cancelled transfer information.
        RpcError: Validation or state error.

    Example:
        transfer.cancel(
            ext_id='12345'
        )
    """
    language = normalize_lang(lang)
    logger.info("transfer.cancel ext_id=%s", ext_id)

    try:
        with transaction.atomic():
            transfer = (
                Transfer.objects.select_for_update().filter(ext_id=ext_id).first()
            )
            if not transfer:
                return rpc_error(
                    32706,
                    language,
                    message=localize_message(
                        "Transfer topilmadi",
                        "Перевод не найден",
                        "Transfer was not found",
                        language,
                    ),
                )

            if transfer.state != TransferState.CREATED:
                return rpc_error(32713, language)

            transfer.state = TransferState.CANCELLED
            transfer.cancelled_at = timezone.now()
            transfer.save(update_fields=["state", "cancelled_at", "updated_at"])

        return Success({"ext_id": transfer.ext_id, "state": transfer.state})
    except Exception:
        logger.exception("transfer.cancel failed ext_id=%s", ext_id)
        return rpc_error(32706, language)


@method(name="transfer.state")
def transfer_state(ext_id, lang="uz"):
    language = normalize_lang(lang)
    logger.info("transfer.state ext_id=%s", ext_id)

    try:
        transfer = get_transfer_by_ext_id(ext_id)
        if not transfer:
            return rpc_error(
                32706,
                language,
                message=localize_message(
                    "Transfer topilmadi",
                    "Перевод не найден",
                    "Transfer was not found",
                    language,
                ),
            )

        return Success({"ext_id": transfer.ext_id, "state": transfer.state})
    except Exception:
        logger.exception("transfer.state failed ext_id=%s", ext_id)
        return rpc_error(32706, language)


@method(name="transfer.history")
def transfer_history(
    card_number=None,
    start_date=None,
    end_date=None,
    status=None,
    lang="uz",
):
    language = normalize_lang(lang)
    logger.info(
        "transfer.history card_number=%s start_date=%s end_date=%s status=%s",
        card_number,
        start_date,
        end_date,
        status,
    )

    try:
        start_date_value = parse_history_date(start_date, "start_date", language)
        end_date_value = parse_history_date(end_date, "end_date", language)

        queryset = Transfer.objects.all().order_by("-created_at")

        if card_number:
            clean_number = clean_card_number(card_number)
            queryset = queryset.filter(
                Q(sender_card_number=clean_number)
                | Q(receiver_card_number=clean_number)
            )

        if start_date_value:
            queryset = queryset.filter(created_at__date__gte=start_date_value)

        if end_date_value:
            queryset = queryset.filter(created_at__date__lte=end_date_value)

        if status:
            queryset = queryset.filter(state=status)

        result = [
            {
                "ext_id": transfer.ext_id,
                "sending_amount": float(
                    transfer.receiving_amount
                    if transfer.receiving_amount is not None
                    else transfer.sending_amount
                ),
                "state": transfer.state,
                "created_at": transfer.created_at.isoformat(),
            }
            for transfer in queryset
        ]

        return Success(result)
    except ValueError as exc:
        logger.warning("transfer.history validation failed: %s", exc)
        return rpc_error(32706, language, message=str(exc))
    except Exception:
        logger.exception("transfer.history failed")
        return rpc_error(32706, language)

def mask_card(card_number: str) -> str:
    """
    8600121234561234  →  860012******1234
    первые 6 цифр + ****** + последние 4
    """
    if len(card_number) < 10:
        return card_number
    return card_number[:6] + "******" + card_number[-4:]


@method(name="card.info")
def card_info(card_number, expiry, lang="uz"):
    """
    Retrieve payment card information.

    This method validates card number and expiry date,
    checks cache storage, and returns card details
    including masked card number and balance.

    Args:
        card_number (str): Full card number.
        expiry (str): Card expiry date.
        lang (str, optional): Response language. Defaults to 'uz'.

    Returns:
        Success: Card information response.
        RpcError: Card validation or lookup error.

    Example:
        card.info(
            card_number='8600123412341234',
            expiry='12/27'
        )
    """
    language = normalize_lang(lang)

    # --- Уникальный ключ для каждой карты ---
    cache_key = f"card_info:{card_number}:{expiry}"

    # --- Шаг 1: смотрим в Redis ---
    cached = safe_cache_get(cache_key)
    if cached:
        data = json.loads(cached)
        if data.get("error"):
            # Закэшированная ошибка — возвращаем ошибку, БД не трогаем
            return rpc_error(data["code"], language)
        # Закэшированный успех — возвращаем сразу
        return Success(data)

    # --- Шаг 2: валидация expiry ---
    try:
        parsed_expiry = parse_expire(expiry)
    except ValueError:
        # Кэшируем ошибку тоже!
        error_data = {"error": True, "code": 32704}
        safe_cache_set(cache_key, json.dumps(error_data), CARD_INFO_CACHE_TTL)
        return rpc_error(32704, language)

    # --- Шаг 3: ORM запрос к БД ---
    card = Card.objects.filter(
        card_number=clean_card_number(card_number)
    ).first()

    if not card:
        # Карта не найдена — кэшируем ошибку
        error_data = {"error": True, "code": 32706}
        safe_cache_set(cache_key, json.dumps(error_data), CARD_INFO_CACHE_TTL)
        return rpc_error(32706, language)

    if not expiry_matches(card.expire_date, parsed_expiry):
        # Срок не совпадает — кэшируем ошибку
        error_data = {"error": True, "code": 32704}
        safe_cache_set(cache_key, json.dumps(error_data), CARD_INFO_CACHE_TTL)
        return rpc_error(32704, language)

    # --- Шаг 4: формируем ответ ---
    response_data = {
        "error": False,
        "card_status": card.status,
        "balance":     str(card.balance),
        "phone":       card.phone,
        "masked_card": mask_card(card.card_number),
    }

    # --- Шаг 5: кэшируем успех на 30 секунд ---
    safe_cache_set(cache_key, json.dumps(response_data), CARD_INFO_CACHE_TTL)

    return Success(response_data)
    