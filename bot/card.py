from aiogram import F, Router, types

from app.models import UserCard, Card, User
from app.utils import convert_date
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.utils import clean_card_number
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from asgiref.sync import sync_to_async
from .utils import menu_builders
from app.utils import card_mask_spoiler

card_router = Router()


class AddCardStateGroup(StatesGroup):
    add_card = State()
    expire_date = State()


@card_router.callback_query(F.data == "add_card")
async def add_card_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddCardStateGroup.add_card)
    await callback.message.answer("Iltimos kartani 16 xonali sonini yuboring:")
    await callback.answer()


@card_router.message(AddCardStateGroup.add_card)
async def add_card(message: types.Message, state: FSMContext):
    card = message.text
    clean_card = clean_card_number(card)
    if not len(clean_card) == 16:
        await message.answer("Iltimos 16 xonali son yuboring:")
        return

    else:
        await state.update_data(card_number=clean_card)
        await state.set_state(AddCardStateGroup.expire_date)
        await message.answer(f"Yaroqlilik mudatini yuboring. Namuna: MM-YY")
        return


@card_router.message(AddCardStateGroup.expire_date)
async def expire_date_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    card_number = data.get("card_number")

    expire = message.text
    # sanani tekshirish
    try:
        clean_date = convert_date(expire)
    except:
        await message.answer("Notog'ri format. MM-YY bo'lsin.")
        return
    # user olish
    try:
        user = await sync_to_async(User.objects.get)(telegram_id=message.from_user.id)
    except User.DoesNotExist:
        await message.answer("Login qilish uchun /start yuboring!")
        return

    # cartani yaratish
    try:
        card = await sync_to_async(Card.objects.create)(
            card_number=card_number,
            phone=user.phone_number,
            balance=0,
            status="active",
            expire_date=clean_date,
        )

        await sync_to_async(UserCard.objects.create)(user=user, card=card)
    except IntegrityError:
        await message.answer("Bu karta sizniki emas yoki avval qoshgansiz!")
        return
    except:
        await message.answer("Kutilmagan xatolik")
        return
    builders = menu_builders()
    await message.answer(
        f"{card} muvofaqiyatli qoshildi.", reply_markup=builders.as_markup()
    )
    await state.clear()


@card_router.callback_query(F.data == "card_list")
async def card_list_handler(callback: types.CallbackQuery):
    message: types.Message = callback.message

    try:
        user = await sync_to_async(User.objects.prefetch_related("cards").get)(
            telegram_id=callback.from_user.id
        )
    except User.DoesNotExist:
        await message.answer("Login qilish uchun /start yuboring!")
        await callback.answer("")
        return
    user_cards = await sync_to_async(list)(
        UserCard.objects.filter(user=user).select_related("card")
    )

    cards = [card_mask_spoiler(uc.card.card_number) for uc in user_cards]
    builders = menu_builders()
    await message.answer(
        "Sizning Kartalaringiz:\n \n".join(cards), reply_markup=builders.as_markup(), parse_mode="HTML"

    )
    await callback.answer("")
