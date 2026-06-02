import re
from rest_framework import serializers

class TransferCreateSerializer(serializers.Serializer):
    ext_id = serializers.CharField(max_length=100)
    sender_card_number = serializers.CharField(max_length=16)
    receiver_card_number = serializers.CharField(max_length=16)
    sender_card_expiry = serializers.CharField(max_length=5)
    sending_amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=1)
    currency = serializers.ChoiceField(choices=[643, 840, 860])

    # 1. Валидация номера карты (ровно 16 цифр)
    def validate_sender_card_number(self, value):
        if not re.match(r'^\d{16}$', value):
            raise serializers.ValidationError("Card must be exactly 16 digits.")
        return value

    def validate_receiver_card_number(self, value):
        if not re.match(r'^\d{16}$', value):
            raise serializers.ValidationError("Card must be exactly 16 digits.")
        return value

    # 2. Валидация срока действия (MM/YY)
    def validate_sender_card_expiry(self, value):
        if not re.match(r'^(0[1-9]|1[0-2])\/\d{2}$', value):
            raise serializers.ValidationError("Expiry must be in MM/YY format (e.g., 12/26).")
        return value

# Отдельный сериализатор-помощник для проверки телефона (по ТЗ)
class PhoneValidationSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=13)

    def validate_phone(self, value):
        if not re.match(r'^\+998\d{9}$', value):
            raise serializers.ValidationError("Phone must be in +998xxxxxxxxx format.")
        return value