import secrets

from django.db import connection
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .security import encrypt_card, is_fernet_token, mask_sensitive_data


CARD_FIELD_NAMES = {
    "card",
    "card_number",
    "card_num",
    "pan",
}


@receiver(pre_save)
def encrypt_card_fields(sender, instance, **kwargs):
    if not getattr(sender, "_meta", None):
        return

    model_name = sender.__name__.lower()
    for field in sender._meta.fields:
        field_name = field.name.lower()
        is_card_number_field = field_name in CARD_FIELD_NAMES or (
            "card" in model_name and field_name == "number"
        )
        if not is_card_number_field:
            continue

        value = getattr(instance, field.name, None)
        if value and not is_fernet_token(str(value)):
            setattr(instance, field.name, encrypt_card(str(value)))


def safe_log(logger, level, message, *args, **kwargs):
    logger.log(level, mask_sensitive_data(message), *args, **kwargs)


@receiver(post_save)
def ensure_user_secret(sender, instance, **kwargs):
    if getattr(sender._meta, "db_table", None) not in {"app_user", "auth_user"}:
        return

    table_name = sender._meta.db_table
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
        if "secret" not in columns:
            return
        cursor.execute(f"SELECT secret FROM {table_name} WHERE id = %s", [instance.pk])
        row = cursor.fetchone()
        if row and row[0]:
            return
        cursor.execute(
            f"UPDATE {table_name} SET secret = %s WHERE id = %s",
            [secrets.token_hex(32), instance.pk],
        )
