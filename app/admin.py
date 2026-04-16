from django.contrib import admin
from import_export import resources
from import_export.admin import ExportMixin
from django.contrib import admin
from .models import Card


class CardResource(resources.ModelResource):
    class Meta:
        model = Card


@admin.register(Card)
class CardAdmin(ExportMixin, admin.ModelAdmin):
    resource_class = CardResource
