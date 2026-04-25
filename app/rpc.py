import logging
from datetime import date
from decimal import Decimal

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


logger = logging.getLogger(__name__)

ALLOWED_METHODS = {
    "transfer.create",
    "transfer.confirm",
    "transfer.cancel",
    "transfer.state",
    "transfer.history",
}
ALLOWED_CURRENCIES = {643, 840, 860}
MAX_OTP_TRIES = 3
MIN_TRANSFER_AMOUNT = Decimal("1.00")
MAX_TRANSFER_AMOUNT = Decimal("1000000000.00")


def normalize_lang(lang):
    value = (lang or "uz").lower()
    return value if value in {"uz", "ru", "en"} else "uz"


def get_error_message(code, lang="uz", **context):
    language = normalize_lang(lang)

    error = Error.objects.only("en", "ru", "uz").get(code=code)
    template = getattr(error, language)

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
def transfer_create(
    ext_id,
    sender_card_number,
    sender_card_expiry,
    receiver_card_number,
    sending_amount,
    currency,
    lang="uz",
):
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
def transfer_confirm(ext_id, otp, lang="uz"):
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

            # Receiver ga ham so'mda qo'shish (barcha kartalar so'mda)
            receiver_card.balance += amount_to_deduct
            receiver_card.save(update_fields=["balance"])

            transfer.state = TransferState.CONFIRMED
            transfer.confirmed_at = timezone.now()
            transfer.otp = None
            transfer.save(update_fields=["state", "confirmed_at", "otp", "updated_at"])

        return Success({"ext_id": transfer.ext_id, "state": transfer.state})
    except Exception:
        logger.exception("transfer.confirm failed ext_id=%s", ext_id)
        return rpc_error(32706, language)


@method(name="transfer.cancel")
def transfer_cancel(ext_id, lang="uz"):
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
                "sending_amount": float(transfer.sending_amount),
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
