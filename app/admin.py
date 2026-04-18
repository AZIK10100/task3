from django.contrib import admin
from django.urls import path
from import_export import resources
from import_export.admin import ExportMixin
<<<<<<< HEAD
from .models import Card
from .utils import format_card_number, format_phone_number
=======

from .models import Card
from .utils import card_mask, phone_mask
from . import views
>>>>>>> origin/task_2_exel_import


class CardResource(resources.ModelResource):
    class Meta:
        model = Card


# ... импорты ...

@admin.register(Card)
class CardAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = CardResource
<<<<<<< HEAD
    list_display = ('formatted_card', 'formatted_phone', 'balance', 'status', 'expire_date')
    
    def formatted_card(self, obj):
        return format_card_number(obj.card_number)
    
    def formatted_phone(self, obj):
        return format_phone_number(obj.phone)

    formatted_card.short_description = "Card Number"
    formatted_phone.short_description = "Phone Number"
    
    
=======

    change_list_template = "admin/app/card/change_list.html"
    list_display = ['masked_card', 'masked_phone', 'status', 'expire_date', 'balance']
    list_filter = ['status', 'expire_date', 'phone']
    search_fields = ['card_number', 'phone']
    ordering = ['-id']

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'import-excel/',
                self.admin_site.admin_view(views.import_cards_view),
                name='app_card_import_excel',
            ),
        ]
        return custom + urls

    # ВАЖНО: Мы полностью УДАЛИЛИ функцию changelist_view() отсюда.
    # ExportMixin сам разберется со своей кнопкой Экспорта.

    @admin.display(description="Номер карты")
    def masked_card(self, obj):
        return card_mask(obj.card_number)

    @admin.display(description="Телефон")
    def masked_phone(self, obj):
        return phone_mask(obj.phone) if obj.phone else "—"
>>>>>>> origin/task_2_exel_import
