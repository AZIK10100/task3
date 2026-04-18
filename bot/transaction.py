from aiogram import F, types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async
from app.models import User, Card, UserCard
from app.utils import clean_card_number, card_mask_spoiler, card_mask

transaction_router = Router()


class DepositStateGroup(StatesGroup):
    select_cart = State()
    quantity = State()


@transaction_router.callback_query(F.data == "deposit")
async def select_cart_for_deposit_handler(
    callback: types.CallbackQuery, state: FSMContext
):
    user_telegram_id = callback.from_user.id
    try:
        user = await sync_to_async(User.objects.get)(telegram_id=user_telegram_id)
    except User.DoesNotExist:
        await callback.message.answer("Boshlash uchun /start yuboring")
        await callback.answer("")
        return

    cards_list = await sync_to_async(list)(
        user.cards.values_list("card__card_number", flat=True)
    )
    # cards_list = [card for card in user_cards]
    if not len(cards_list):
        await callback.message.answer(text="Karta topilmadi iltimos karta qoshing")
        await callback.answer("")
        return
    builder = InlineKeyboardBuilder()
    for card in cards_list:
        builder.row(
            types.InlineKeyboardButton(text=card_mask(card), callback_data=card)
        )
    await state.set_state(DepositStateGroup.select_cart)
    await callback.message.answer(
        text="Toldirmoqchi bolgan kartanigzni tanlang", reply_markup=builder.as_markup()
    )
    await callback.answer("")


@transaction_router.callback_query(DepositStateGroup.select_cart)
async def get_deposit_handler(callback: types.CallbackQuery, state: FSMContext):
    cart = callback.data

    await state.update_data(cart=cart)
    await state.set_state(DepositStateGroup.quantity)

    await callback.message.answer("Toldiriladigan summani kiriting.")
    await callback.answer()


@transaction_router.message(DepositStateGroup.quantity)
async def deposit_handler(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    card_number = state_data.get("cart")
    deposit_sum = int(message.text)

    cart = await sync_to_async(Card.objects.get)(card_number=card_number)

    cart.balance += deposit_sum
    await sync_to_async(cart.save)()
    await message.answer(
        f"{card_number} kartasi {deposit_sum}so'm ga to'ldirildi. Xisobingiz {cart.balance}so'm"
    )


class TransactionStateGroup(StatesGroup):
    select_cart = State()
    third_cart = State()
    quantity = State()


@transaction_router.callback_query(F.data == "transfer")
async def select_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    user = await sync_to_async(User.objects.get)(telegram_id=callback.from_user.id)

    cards = await sync_to_async(list)(
        user.cards.values_list("card__card_number", flat=True)
    )

    if not cards:
        await callback.message.answer("Karta yo'q")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for card in cards:
        builder.row(
            types.InlineKeyboardButton(text=card_mask(card), callback_data=card)
        )

    await state.set_state(TransactionStateGroup.select_cart)
    await callback.message.answer("Kartani tanlang:", reply_markup=builder.as_markup())
    await callback.answer()


@transaction_router.callback_query(TransactionStateGroup.select_cart)
async def get_sender_card(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart=callback.data)
    await state.set_state(TransactionStateGroup.third_cart)

    await callback.message.answer("Qabul qiluvchi karta raqamini kiriting:")
    await callback.answer()


@transaction_router.message(TransactionStateGroup.third_cart)
async def get_receiver_card(message: types.Message, state: FSMContext):
    clean_cart = clean_card_number(message.text)

    try:
        await sync_to_async(Card.objects.get)(card_number=clean_cart)
    except Card.DoesNotExist:
        await message.answer("Bunday karta yo'q")
        return

    await state.update_data(third_cart=clean_cart)
    await state.set_state(TransactionStateGroup.quantity)

    await message.answer("Summani kiriting:")


@transaction_router.message(TransactionStateGroup.quantity)
async def process_transfer(message: types.Message, state: FSMContext):
    data = await state.get_data()

    sender = data.get("cart")
    receiver = data.get("third_cart")

    try:
        amount = int(message.text)
    except:
        await message.answer("Faqat raqam kiriting")
        return

    if amount <= 0:
        await message.answer("Noto'g'ri summa")
        return

    try:
        sender_card = await sync_to_async(Card.objects.get)(card_number=sender)
        receiver_card = await sync_to_async(Card.objects.get)(card_number=receiver)
    except Card.DoesNotExist:
        await message.answer("Karta topilmadi")
        return

    if sender_card.balance < amount:
        await message.answer("Balans yetarli emas")
        return

    sender_card.balance -= amount
    receiver_card.balance += amount

    await sync_to_async(sender_card.save)()
    await sync_to_async(receiver_card.save)()

    receiver_user_card = await sync_to_async(
        UserCard.objects.select_related("user").get
    )(card=receiver_card)

    receiver_user = receiver_user_card.user

    if receiver_user.telegram_id:
        await message.bot.send_message(
            chat_id=receiver_user.telegram_id,
            text=f"Sizning kartangizga {amount} so‘m tushdi.\n"
            f"Karta: {card_mask_spoiler(receiver_card.card_number)}",
            parse_mode="HTML",
        )

    await message.answer(
        f"{amount} so‘m yuborildi\n{card_mask_spoiler(sender)} → {card_mask_spoiler(receiver)}",
        parse_mode="HTML",
    )

    await state.clear()
