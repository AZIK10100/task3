from django.contrib import admin
from import_export import resources
from import_export.admin import ExportMixin
from .models import Card


class CardResource(resources.ModelResource):
    class Meta:
        model = Card


@admin.register(Card)
class CardAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = CardResource
    list_display = ('formatted_card', 'formatted_phone', 'balance', 'status', 'expire_date')
    
    def formatted_card(self, obj):
        # 8600 0000 0000 0000 shu kabi format qilib berish uchun
        return f"{obj.card_number[:4]} {obj.card_number[4:8]} {obj.card_number[8:12]} {obj.card_number[12:]}"
    
    def formatted_phone(self, obj):
        # +998 90 123 45 67 shu kabi format qilib berish uchun
        return f"{obj.phone[:4]} {obj.phone[4:6]} {obj.phone[6:9]} {obj.phone[9:11]} {obj.phone[11:13]}"

    # bular yuqorida adminda ko'rinishi uchun
    formatted_card.short_description = "Card Number"
    formatted_phone.short_description = "Phone Number"