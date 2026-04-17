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


def format_card_number(card_number):
    return f"{card_number[:4]} {card_number[4:8]} {card_number[8:12]} {card_number[12:]}"
    
def format_phone_number(phone_number):
    return f"{phone_number[:4]} {phone_number[4:6]} {phone_number[6:9]} {phone_number[9:11]} {phone_number[11:13]}"