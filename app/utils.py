from datetime import datetime


def clean_card_number(card):
    card = list(card)
    result = []
    for i in card:
        if i.isdigit():
            result.append(i)
    return "".join(result)


def convert_date(mm_yy: str) -> str:
    date_obj = datetime.strptime(mm_yy, "%m-%y")
    return date_obj.strftime("%Y-%m-01")
