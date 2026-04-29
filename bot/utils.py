from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types


def menu_builders():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Karta qoshish", callback_data="add_card"),
    )
    builder.row(
        types.InlineKeyboardButton(text="Kartalarim", callback_data="card_list"),
    )
    builder.row(
        types.InlineKeyboardButton(text="Kartani toldirish", callback_data="deposit"),
    )
    builder.row(
        types.InlineKeyboardButton(text="Pul yuborish", callback_data="transfer"),
    )
    return builder
