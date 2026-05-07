from django.http import HttpResponse


def import_cards_view(request):
    if request.method == "POST":
        # сюда позже можно добавить Excel/CSV импорт
        return HttpResponse("Cards imported successfully")

    return HttpResponse("Upload cards file (POST request required)")


def import_transfers_view(request):
    if request.method == "POST":
        # сюда позже можно добавить импорт переводов
        return HttpResponse("Transfers imported successfully")

    return HttpResponse("Upload transfers file (POST request required)")