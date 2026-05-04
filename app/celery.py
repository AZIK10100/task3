from celery import shared_task
from django.conf import settings
from django.db.models import Count
from app.models import Card, Transfer
from app.utils import send_message

@shared_task
def send_stats_report():
    total_cards = Card.objects.count()
    total_transfers = Transfer.objects.count()
    message = f" Daily Report\nTotal cards: {total_cards}\nTotal transfers: {total_transfers}"
    admin_chat_id = getattr(settings, "ADMIN_TELEGRAM_ID", None)
    if admin_chat_id:
        send_message(message, admin_chat_id)
    else:

        pass
