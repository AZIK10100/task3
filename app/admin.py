from django.contrib import admin
from import_export import resources
from import_export.admin import ExportMixin
from .models import Card
from .utils import format_card_number, format_phone_number


class CardResource(resources.ModelResource):
    class Meta:
        model = Card


@admin.register(Card)
class CardAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = CardResource
    list_display = ('formatted_card', 'formatted_phone', 'balance', 'status', 'expire_date')
    
    def formatted_card(self, obj):
        return format_card_number(obj.card_number)
    
    def formatted_phone(self, obj):
        return format_phone_number(obj.phone)

    formatted_card.short_description = "Card Number"
    formatted_phone.short_description = "Phone Number"
    
    