from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required

from .models import Card
from .utils import format_card, format_phone, parse_expire, clean_balance

try:
    import openpyxl
except ImportError:
    openpyxl = None


@staff_member_required
def import_cards_view(request):
    if request.method != 'POST':
        return redirect('/admin/app/card/')

    if openpyxl is None:
        messages.error(request, "Библиотека openpyxl не установлена. Запустите: pip install openpyxl")
        return redirect('/admin/app/card/')

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, "Файл не выбран!")
        return redirect('/admin/app/card/')

    if not excel_file.name.endswith(('.xlsx', '.xls')):
        messages.error(request, "Неверный формат файла. Нужен .xlsx или .xls")
        return redirect('/admin/app/card/')

    try:
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
    except Exception as e:
        messages.error(request, f"Не удалось открыть файл: {e}")
        return redirect('/admin/app/card/')

    success_count = 0
    error_rows = []

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Пропускаем полностью пустые строки
        if not any(row):
            continue

        try:
            # Распаковываем колонки (добавляем None если меньше 5 колонок)
            cols = (list(row) + [None] * 5)[:5]
            card_raw, expire_raw, phone_raw, status_raw, balance_raw = cols

            # --- Нормализация ---
            card_number = format_card(card_raw)
            phone       = format_phone(phone_raw)
            expire_date = parse_expire(expire_raw)
            balance     = clean_balance(balance_raw)

            # Статус
            status = str(status_raw).strip().lower() if status_raw else ''
            valid_statuses = ['active', 'inactive', 'expired', 'blocked']
            if status not in valid_statuses:
                raise ValueError(f"Неверный статус '{status_raw}'. Допустимо: {valid_statuses}")

            # --- Сохранение (обновляем если уже есть) ---
            Card.objects.update_or_create(
                card_number=card_number,
                defaults={
                    'phone':       phone,
                    'expire_date': expire_date,
                    'status':      status,
                    'balance':     balance,
                }
            )
            success_count += 1

        except Exception as e:
            error_rows.append(f"Строка {row_num}: {e}")

    # Показываем результат
    if success_count:
        messages.success(request, f"✅ Успешно импортировано: {success_count} карт(ы)")
    for err in error_rows:
        messages.error(request, f"❌ {err}")

    if not success_count and not error_rows:
        messages.warning(request, "Файл пустой или не содержит данных")

    return redirect('/admin/app/card/')