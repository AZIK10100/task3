from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from app.models import User
from asgiref.sync import sync_to_async
from .utils import menu_builders

login_router = Router()


class LoginStateGroup(StatesGroup):
    phone_number = State()


@login_router.message(CommandStart())
async def start_hanlder(message: types.Message, state: FSMContext):

    user_id = message.from_user.id
    if user_id:
        try:
            user = await sync_to_async(User.objects.get)(telegram_id=user_id)
            builder = menu_builders()
            
            await message.answer(
                "O'zingizga kerakli bo'limni tanlang.", reply_markup=builder.as_markup()
            )
            return

        except User.DoesNotExist:
            pass

    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(
            text="Telefon raqamingizni yuborish",
            request_contact=True,
        )
    )
    await message.answer(
        "Assalomu alekum! iltimos telefon raqamingizni yuboring.",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(LoginStateGroup.phone_number)


@login_router.message(LoginStateGroup.phone_number)
async def send_contact_handler(message: types.Message, state: FSMContext):
    contact = message.contact
    if not contact:
        await message.answer(
            "Iltimos, pastdagi tugma yordamida o'z raqamingizni yuboring!"
        )
        return

    if contact.user_id != message.from_user.id:
        await message.answer("Faqat o'zingizga tegishli raqamni yuboring!")
        return

    else:
        try:
            await sync_to_async(User.objects.update_or_create)(
                phone_number=contact.phone_number,
                defaults={
                    "telegram_id": message.from_user.id,
                    "first_name": contact.first_name,
                    "username":  message.from_user.id,
                },
            )
        except Exception as e:
            print(f"Xatolik: {e}")
            await message.answer(
                "Tizimda xatolik yuz berdi. Birozdan so'ng urunib ko'ring."
            )
            return
        await message.answer(
            f"Raxmat! {contact.first_name}", reply_markup=types.ReplyKeyboardRemove()
        )
        
        await state.clear()

        builder = menu_builders()

        await message.answer(
            "O'zingizga kerakli bo'limni tanlang.", reply_markup=builder.as_markup()
        )