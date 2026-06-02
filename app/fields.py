from django.db import models

from .security import decrypt_card, encrypt_card, is_fernet_token


class EncryptedCardField(models.TextField):
    description = "Encrypted card number"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value or is_fernet_token(value):
            return value
        return encrypt_card(value)

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return decrypt_card(value)
        except Exception:
            return value

    def to_python(self, value):
        return value
