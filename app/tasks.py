from celery import shared_task
from django.conf import settings

from app.models import Card, Transfer
from app.utils import send_message


@shared_task
def send_stats_report():
    total_cards = Card.objects.count()
    total_transfers = Transfer.objects.count()
    message = (
        "Daily Report\n"
        f"Total cards: {total_cards}\n"
        f"Total transfers: {total_transfers}"
    )
    admin_chat_id = getattr(settings, "ADMIN_TELEGRAM_ID", None)
    if admin_chat_id:
        return send_message(message, admin_chat_id)
    return False
